using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RP-AXE fixed-capacity avionics — the "buy it off the shelf" counterpart to the procedural
    /// <see cref="ModuleAxeAvionics"/> core.
    ///
    /// A named part (Sputnik, Voyager, an Apollo CM, an Agena bus, a Titan guidance ring) has real
    /// hardware inside a fixed model. There is no box to resize and no battery/hardware split to make —
    /// the part author already made it — so this module carries ONE authored number, <see cref="capacityTons"/>,
    /// the vessel mass this unit can steer. That is exactly RP-1's `ModuleAvionics.massLimit`, and the
    /// values are ported from RP-1's own hand-authored table (GameData/RP-1/Avionics.cfg, ~1283 lines of
    /// per-spacecraft judgement: "Cassini 5712 kg Launch mass" -> 6.0 t, "Voyager 825.5 kg" -> 0.875 t).
    /// It is NOT derivable from part data — a part's mass is mostly structure, tankage and instruments,
    /// so running AXE's own inverse mass polynomial on it yields nonsense (a 150 t launch stand "derives"
    /// ~10 million tonnes of capacity). The one place the two models do agree is the bottom of the range:
    /// AXE's curve needs 84.5 kg of hardware (a 169 L box) before capacity goes positive at tier 0, and
    /// Sputnik 1's entire 83 kg falls under that floor — independently reproducing RP-1's authored 0.
    ///
    /// OVERLOAD CONSEQUENCE differs from the procedural core, deliberately. The proc core answers going
    /// over capacity with a smooth exp(8*(r-1)) power penalty rather than a lock, because a player who
    /// sized their own box slightly small made a sizing mistake worth softening. A fixed part has no
    /// sizing decision to get wrong, so it uses RP-1's own rule instead: over capacity locks attitude
    /// (see <see cref="AxeControlLockerUtils"/>), while command itself keeps working — staging and
    /// throttle still respond, the craft just can't steer. Routing these through the penalty path instead
    /// would mean a capacity-0 part draws exp(80) watts, flattens the battery and drops ModuleCommand
    /// entirely, which is both harsher than RP-1 and much less legible in the VAB.
    ///
    /// SHIELDING is a fact about the part, not a player choice: Voyager was radiation-hardened, Sputnik
    /// was not. <see cref="shielded"/> is baked per part (ported from RP-1's `interplanetary` flag, which
    /// marked exactly the units rated to work beyond near-Earth) and still gated on researching
    /// <see cref="shieldedTech"/>, so the shd_* lane keeps its value without duplicating a per-tier ladder
    /// onto every named part. Its effect here is hibernation: stock probe hibernation stays enabled only
    /// on a shielded unit whose tech is in hand, and is switched off otherwise — which also ports RP-1's
    /// blanket "disable hibernation on every ModuleCommand part" rule (Avionics.cfg:2).
    ///
    /// NOTE ON techRequired: RP-1's ModuleAvionics has an optional `techRequired` gate, and a handful of
    /// its guidance rings use it. It is deliberately NOT ported. Those values name RP-1 tech IDs, none of
    /// which exist in AXE's from-scratch tree, and ResearchAndDevelopment.GetTechnologyState() returns
    /// Unavailable (not an error) on an unrecognised ID — so a ported gate would silently zero the
    /// capacity of every part carrying it, forever. In AXE the part's own tech-tree node is the gate.
    /// </summary>
    public class ModuleAxeFixedAvionics : PartModule
    {
        const string PAWGroup = "AxeAvionics";
        const string GroupDisplay = "Avionics";

        /// <summary>Vessel mass this unit can steer, in tons. RP-1's `massLimit`. 0 = payload only.</summary>
        [KSPField] public float capacityTons = 0f;

        /// <summary>Axial thrust permitted while over capacity (spin-stabilized kick stages). RP-1's `allowAxial`.</summary>
        [KSPField] public bool allowAxial = false;

        /// <summary>Radiation-hardened hardware. Ported from RP-1's `interplanetary`.</summary>
        [KSPField] public bool shielded = false;

        /// <summary>The shd_* node that must be researched before <see cref="shielded"/> counts.</summary>
        [KSPField] public string shieldedTech = "shd_basicAvionics";

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Steerable Mass",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string capacityDisplay = "";

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceStatus = "";

        ModuleCommand _command;
        float _nextGuiRefresh;
        const float GuiRefreshInterval = 1f;   // ShouldLock() walks every part; don't do it per frame

        /// <summary>What this unit contributes to the vessel's steerable-mass budget.</summary>
        public float CapacityTons => capacityTons > 0f ? capacityTons : 0f;

        /// <summary>Hardened AND the hardening researched — the only state that keeps hibernation.</summary>
        public bool ShieldingActive => shielded && Researched(shieldedTech);

        static bool Researched(string tech)
        {
            if (string.IsNullOrEmpty(tech)) return true;
            if (HighLogic.CurrentGame == null || HighLogic.CurrentGame.Mode == Game.Modes.SANDBOX) return true;
            return ResearchAndDevelopment.GetTechnologyState(tech) == RDTech.State.Available;
        }

        public override void OnStart(StartState state)
        {
            base.OnStart(state);
            _command = part.FindModuleImplementing<ModuleCommand>();
            ApplyHibernation();
            UpdateGui();
        }

        // Ports RP-1's Avionics.cfg:2 ("Disable hibernation" on every ModuleCommand part), but gives the
        // shd_* lane something to buy on named parts: a hardened unit whose tech is researched keeps it.
        void ApplyHibernation()
        {
            if (_command == null) return;
            _command.hasHibernation = ShieldingActive;
            if (!_command.hasHibernation) _command.hibernation = false;
        }

        public void Update()
        {
            if (!HighLogic.LoadedSceneIsEditor && !HighLogic.LoadedSceneIsFlight) return;
            if (Time.unscaledTime < _nextGuiRefresh) return;
            _nextGuiRefresh = Time.unscaledTime + GuiRefreshInterval;
            ApplyHibernation();   // shieldedTech can be researched mid-flight
            UpdateGui();
        }

        void UpdateGui()
        {
            capacityDisplay = capacityTons > 0f ? $"{capacityTons:N2} t" : "none (payload only)";

            // The Flight controller already holds the active vessel's level; anywhere else (editor, or a
            // PAW opened on an unfocused vessel) recompute from the relevant part list.
            AxeAvionicsController ctl = HighLogic.LoadedSceneIsFlight ? AxeAvionicsController.Instance : null;
            AxeControlLockerUtils.LockLevel level =
                (ctl != null && vessel != null && vessel.isActiveVessel)
                    ? ctl.Level
                    : AxeControlLockerUtils.ShouldLock(HighLogic.LoadedSceneIsEditor
                        ? EditorLogic.fetch?.ship?.parts
                        : vessel?.parts);

            if (capacityTons <= 0f)
                guidanceStatus = "payload only — cannot steer";
            else if (level == AxeControlLockerUtils.LockLevel.Unlocked)
                guidanceStatus = shielded
                    ? (ShieldingActive ? "guiding — hardened" : "guiding — hardening not yet researched")
                    : "guiding";
            else if (level == AxeControlLockerUtils.LockLevel.Axial)
                guidanceStatus = "over capacity — axial thrust only";
            else
                guidanceStatus = "over capacity — attitude locked";
        }

        public override string GetInfo()
        {
            string s = capacityTons > 0f
                ? $"Steers up to <b>{capacityTons:N2} t</b> of vessel (whole-vessel wet mass).\n"
                : "Carries no guidance — provides command, telemetry and power only. The vessel needs an avionics core to steer.\n";
            if (capacityTons > 0f)
            {
                s += "Going over that mass locks attitude control; staging and throttle keep working.\n";
                if (allowAxial) s += "Axial thrust stays available while over capacity (spin-stabilized).\n";
                s += shielded
                    ? $"Radiation-hardened: rated for deep space, and may hibernate once <b>{shieldedTech}</b> is researched.\n"
                    : "Not radiation-hardened: no hibernation.\n";
            }
            return s;
        }
    }
}
