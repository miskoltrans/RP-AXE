using System.Collections.Generic;
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
    /// OVERLOAD CONSEQUENCE is now SHARED with the procedural core, not different from it. Both feed one
    /// vessel-wide MAX and both get whichever <see cref="AxeControlPenalty"/> is selected. The old
    /// asymmetry — proc core pays watts, named part locks — is gone: the EC penalty behind it was inert,
    /// and neither justification survived (the exp(80) hazard was removed by its own cap 19 hours after it
    /// was written; "a fixed part has no sizing decision to get wrong" is false, because choosing a
    /// 0.875 t Voyager bus for a 2 t spacecraft is exactly a sizing decision, made in the VAB).
    ///
    /// A unit that cannot fly the vessel it is on can Disengage rather than contribute a rating it cannot
    /// honour — capacity-only, no tier gate, no power effect, and distinct from Shutdown Avionics.
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

        /// <summary>
        /// This unit's own power draw, in kW. Ports RP-1's <c>ModuleAvionics.enabledkW</c>, including its
        /// default of -1 meaning "not authored -- adopt whatever the part's own ModuleCommand already
        /// draws" (RP-1 authors this on 8 of its 124 entries; the rest inherit exactly this way).
        ///
        /// Named parts are control hardware WITHOUT a battery -- 85 of the 90 installed here carry no EC
        /// storage at all -- so the draw is real and the storage comes from elsewhere on the craft. Today
        /// that draw is whatever the upstream mod or RO happened to ship: present on 57 parts, absent on
        /// 33, and spanning 0.01 to 14 EC/s with no pattern, because AXE never had a field for it.
        ///
        /// B3: this module now TAKES DELIVERY, matching RP-1. It adopts the rate, zeroes the ModuleCommand
        /// resource so the draw is not double-counted, and reports the load itself -- through Kerbalism's
        /// duck-typed bridge (PlannerUpdate / ResourceUpdate / BackgroundUpdate) when Kerbalism is present,
        /// and by driving the ModuleCommand resource directly when it is not. Zeroing WITHOUT that bridge
        /// would have silently made every named part free to run, which is why this waited for the bridge.
        /// Net vessel draw is unchanged; what changes is that the value is now ours to modulate.
        /// </summary>
        [KSPField(isPersistant = true)] public float enabledkW = -1f;

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Avionics Power",
                  guiFormat = "F1", guiUnits = " W", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float currentWatts = 0f;

        // ---- A1/A2: Engage / Disengage Guidance. Same semantics as the procedural core (see
        // docs/AVIONICS_PLAN.md): capacity-only, no tier gate, no power effect. A named unit riding a stage
        // it cannot fly must be able to stand down rather than contribute a rating it cannot honour.
        [KSPField(isPersistant = true)]
        public bool guidanceEngaged = true;

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Guidance auto",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "manual", enabledText = "auto", scene = UI_Scene.All)]
        public bool autoGuidance = true;

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Steerable Mass",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string capacityDisplay = "";

        // A4. Same editor readouts as the procedural core.
        [KSPField(guiActiveEditor = true, guiName = "Vessel vs rating",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string vesselRatioDisplay = "";

        [KSPField(guiActiveEditor = true, guiName = "At full tanks",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string fullTankDisplay = "";

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceStatus = "";

        ModuleCommand _command;
        float _nextGuiRefresh;
        const float GuiRefreshInterval = 1f;   // ShouldLock() walks every part; don't do it per frame

        /// <summary>What this unit contributes to the vessel's steerable-mass budget.</summary>
        public float CapacityTons => (guidanceEngaged && capacityTons > 0f) ? capacityTons : 0f;

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
            GameEvents.onPartCouple.Add(OnCouple);
            InitializeResourceRate();
            ApplyHibernation();
            UpdateGui();
        }

        // Ports RP-1's ModuleAvionics.InitializeResourceRate, minus the part that takes delivery -- see the
        // enabledkW field comment for why. An unauthored rate adopts the part's own ModuleCommand draw; a
        // part with no EC input at all (33 of them: service modules, equipment sections, station cores)
        // adopts 0, which is honest rather than invented.
        void InitializeResourceRate()
        {
            _commandEC = FindCommandEC();
            if (enabledkW < 0f) enabledkW = _commandEC != null ? (float)_commandEC.rate : 0f;
            // Ours now. Under Kerbalism the module reports the load instead; without Kerbalism we drive
            // this same resource from UpdateDraw, so either way it must not also bill itself.
            if (_commandEC != null) _commandEC.rate = 0f;
        }

        // Mirrors ModuleAxeAvionics: Kerbalism reads ecConsumption off the module, so ModuleCommand's own
        // input must be zero there or the draw is counted twice.
        void UpdateDraw()
        {
            currentWatts = Mathf.Max(0f, enabledkW) * 1000f;
            _ecConsumption = new KeyValuePair<string, double>(EcName, -currentWatts / 1000.0);
            if (_commandEC != null) _commandEC.rate = KerbalismPresent ? 0f : currentWatts / 1000f;
        }

        // ---- Kerbalism bridge (duck-typed, same shape as the procedural core) ----------------------
        const string EcName = "ElectricCharge";
        KeyValuePair<string, double> _ecConsumption = new KeyValuePair<string, double>(EcName, 0);
        ModuleResource _commandEC;
        static bool? _kerbalismPresent;

        // See AxeKerbalism.Present — same silent inversion this module shared with ModuleAxeAvionics:
        // the old AssemblyLoader.loadedAssemblies scan can never match "Kerbalism", so EC was charged
        // twice (stock ModuleCommand + the Kerbalism API report).
        static bool KerbalismPresent
        {
            get
            {
                if (_kerbalismPresent == null) _kerbalismPresent = AxeKerbalism.Present;
                return _kerbalismPresent.Value;
            }
        }

        public string PlannerUpdate(List<KeyValuePair<string, double>> resources, CelestialBody _,
                                    Dictionary<string, double> environment)
        {
            resources.Add(_ecConsumption);
            return "avionics";
        }

        public string ResourceUpdate(Dictionary<string, double> availableResources,
                                     List<KeyValuePair<string, double>> resourceChangeRequest)
        {
            resourceChangeRequest.Add(_ecConsumption);
            return "avionics";
        }

        // Kerbalism reads currentWatts straight out of the module snapshot for an unloaded vessel, so the
        // persisted figure must be the one a parked craft should actually be billed.
        public static string BackgroundUpdate(Vessel v,
            ProtoPartSnapshot partSnapshot, ProtoPartModuleSnapshot moduleSnapshot,
            PartModule protoPartModule, Part protoPart,
            Dictionary<string, double> availableResources,
            List<KeyValuePair<string, double>> resourceChangeRequest, double elapsed_s)
        {
            if (availableResources.ContainsKey(EcName))
            {
                float cw = 0f;
                if (moduleSnapshot.moduleValues.TryGetValue("currentWatts", ref cw) && cw > 0f)
                    resourceChangeRequest.Add(new KeyValuePair<string, double>(EcName, -cw / 1000.0));
            }
            return "avionics";
        }

        ModuleResource FindCommandEC()
        {
            if (_command?.resHandler?.inputResources == null) return null;
            foreach (ModuleResource r in _command.resHandler.inputResources)
                if (r != null && r.id == PartResourceLibrary.ElectricityHashcode) return r;
            return null;
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
            EvaluateAutoGuidance();
            UpdateGui();
        }

        [KSPEvent(guiActive = true, guiActiveEditor = true, guiName = "Disengage Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleGuidanceEngaged() => SetEngaged(!guidanceEngaged, manual: true);

        [KSPAction("Engage Guidance")]
        public void EngageAction(KSPActionParam _) => SetEngaged(true, manual: true);

        [KSPAction("Disengage Guidance")]
        public void DisengageAction(KSPActionParam _) => SetEngaged(false, manual: true);

        void SetEngaged(bool value, bool manual)
        {
            if (value == guidanceEngaged) return;
            guidanceEngaged = value;
            if (HighLogic.LoadedSceneIsFlight)
            {
                float mass = VesselMassTons();
                if (value)
                    AxeAvionicsController.Announce(mass > capacityTons
                        ? "Guidance engaged over capacity — control will be unreliable."
                        : "Vessel within rating. Guidance engaged.");
                else
                    AxeAvionicsController.Announce(manual
                        ? "Guidance disengaged — attitude control lost, staging and throttle retained."
                        : $"Docked mass {mass:N1} t exceeds {capacityTons:N1} t rating. Guidance disengaged — attitude locked.");
                if (vessel != null) GameEvents.onVesselWasModified.Fire(vessel);
            }
            UpdateGui();
        }

        // Auto-engage against THIS unit's rating, never the vessel MAX -- a disengaged unit contributes 0,
        // so a MAX-based test could never become true again. Auto-disengage on coupling events only.
        void EvaluateAutoGuidance()
        {
            if (!autoGuidance || !HighLogic.LoadedSceneIsFlight || capacityTons <= 0f) return;
            float mass = VesselMassTons();
            if (mass <= 0f) return;
            if (!guidanceEngaged && mass <= capacityTons) SetEngaged(true, manual: false);
            else if (guidanceEngaged && _coupledThisTick && mass > capacityTons) SetEngaged(false, manual: false);
            _coupledThisTick = false;
        }

        bool _coupledThisTick;
        void OnCouple(GameEvents.FromToAction<Part, Part> _) { _coupledThisTick = true; }

        void OnDestroy() => GameEvents.onPartCouple.Remove(OnCouple);

                // Reports THIS unit against the vessel, in the same vocabulary the procedural core uses: capacity is
        // "guided up to this mass; over it, unguided", and allowAxial decides whether unguided keeps axial
        // thrust. Locked and Axial are not separate concepts here -- they ARE unguided-without-axial and
        // unguided-with-axial.
        //
        // Two things this replaces, both of which were the readout contradicting the mechanic:
        //   * it used to report the VESSEL-wide lock level, so a 0.875 t Voyager bus riding a 40 t stack
        //     that a procedural core had unlocked said "guiding" -- a capability it was not providing.
        //   * capacity 0 short-circuited to "payload only -- cannot steer" even with allowAxial set, while
        //     ShouldLock was actually granting that part Axial. A Vostok flew retro-capable and said it
        //     could not steer at all.
        // Judging this unit locally also drops the per-second ShouldLock walk over every part.
        void UpdateGui()
        {
            UpdateDraw();
            UpdateEditorRatios();

            // A capacity-0 unit is unguided by authorship -- nothing to engage or auto-manage.
            BaseEvent ge = Events[nameof(ToggleGuidanceEngaged)];
            ge.guiName = guidanceEngaged ? "Disengage Guidance" : "Engage Guidance";
            ge.guiActive = ge.guiActiveEditor = capacityTons > 0f;

            BaseField af = Fields[nameof(autoGuidance)];
            af.guiActive = af.guiActiveEditor = capacityTons > 0f;

            if (capacityTons > 0f && !guidanceEngaged)
            {
                capacityDisplay = $"{capacityTons:N2} t (disengaged)";
                guidanceStatus = "Disengaged — contributing no guidance";
                return;
            }

            if (capacityTons <= 0f)
            {
                capacityDisplay = "n/a — unguided";
                guidanceStatus = allowAxial ? "Unguided — axial thrust only (spin-stabilized)"
                                            : "Unguided — no steering";
                return;
            }

            capacityDisplay = $"{capacityTons:N2} t";

            // mass 0 means there is nothing to judge against yet (empty editor); report the capability
            // rather than a verdict.
            float mass = VesselMassTons();
            if (mass > capacityTons)
            {
                guidanceStatus = allowAxial ? "Over capacity — unguided, axial thrust only"
                                            : "Over capacity — unguided, no steering";
                return;
            }

            guidanceStatus = shielded
                ? (ShieldingActive ? "Guided — Shielded — guidance active"
                                   : "Guided — hardening not yet researched")
                : "Guided — guidance active";
        }

        void UpdateEditorRatios()
        {
            if (!HighLogic.LoadedSceneIsEditor) return;
            if (capacityTons <= 0f) { vesselRatioDisplay = fullTankDisplay = "n/a"; return; }
            float now = VesselMassTons();
            float full = AxeControlLockerUtils.FullTankMassTons(EditorLogic.fetch?.ship?.parts);
            vesselRatioDisplay = Verdict(now, capacityTons);
            fullTankDisplay = full > now + 0.01f ? Verdict(full, capacityTons) : "same as configured";
        }

        static string Verdict(float mass, float cap)
        {
            float r = mass / cap;
            string state = r <= 1f ? "clean"
                         : AxeControlPenalties.Current.LocksInstead ? "guidance lost"
                         : "degraded";
            return $"{mass:N2} t  ({r:0.00}x — {state})";
        }

        float VesselMassTons()
        {
            if (HighLogic.LoadedSceneIsEditor)
                return EditorLogic.fetch?.ship != null ? EditorLogic.fetch.ship.GetTotalMass() : 0f;
            return vessel != null ? (float)vessel.totalMass : 0f;
        }

        public override string GetInfo()
        {
            string s = capacityTons > 0f
                ? $"Guided up to <b>{capacityTons:N2} t</b> of vessel (whole-vessel wet mass).\n"
                : "<b>Unguided</b> — provides command and telemetry, but never steers.\n";
            if (capacityTons > 0f)
            {
                s += "Over that mass it becomes <b>unguided</b>: attitude control is lost, staging and throttle keep working.\n";
            }
            if (allowAxial) s += "Axial thrust stays available while unguided (spin-stabilized).\n";
            if (capacityTons > 0f)
            {
                s += shielded
                    ? $"Radiation-hardened: rated for deep space, and may hibernate once <b>{shieldedTech}</b> is researched.\n"
                    : "Not radiation-hardened: no hibernation.\n";
            }
            return s;
        }
    }
}
