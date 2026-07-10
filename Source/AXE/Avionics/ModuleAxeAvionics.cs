using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RP-AXE unified avionics core, V2. A VAB-chosen MODEL (guided/unguided) selects between two RP-1
    /// hardware curves:
    ///   * NEAR-EARTH (guided) — RP-1's Near-Earth mass polynomial, now run in the INVERSE direction: the
    ///     player sizes the box (a 3-way battery/hardware/empty-space split of the procedural volume), the
    ///     hardware segment's volume x density gives the hardware MASS, and that mass is run back through
    ///     the inverse of RP-1's polynomial to yield a CAPACITY ("how much vessel mass this core can steer").
    ///     A live ratio of actual vessel mass to the vessel's effective capacity (MAX across active cores,
    ///     RP-1's own anti-cheese rule) drives a smooth EC-draw PENALTY when over capacity — no hard lock.
    ///   * SCIENCE-CORE (unguided) — RP-1's Science-Core flat per-tier mass (unchanged): no steering
    ///     (axial-thrust spin-stabilization from improvedAvionics up), a fraction of the mass + power, and
    ///     no capacity concept (RP-1: Science-Core always contributes 0 to controllable mass).
    /// A second, Guided-only axis picks UNSHIELDED vs SHIELDED (RP-1's Deep-Space): its own full per-tier
    /// mass/cost ladder (not a multiplier), unlocked ~10 tiers late of Guided's own ladder, plus a deeper/
    /// earlier-available hibernation depth. Both mass AND cost are computed in the editor and FROZEN at
    /// launch (persisted); the model/shielding/split all freeze with them.
    ///
    /// The EC DRAW runs LIVE off the vehicle's DRY mass (steady as fuel burns, steps down as stages drop),
    /// gets cheaper per researched tier, and auto-drops to the hibernate-equivalent rate while on rails
    /// (timewarp), independent of the manual Hibernate toggle. Control is gated by guidance/axial being
    /// active (see <see cref="AxeAvionicsController"/>/<see cref="AxeControlLockerUtils"/>, both untouched
    /// by this redesign — they read only <see cref="GuidanceActive"/>/<see cref="AxialActive"/>, never the
    /// capacity penalty) and by HIBERNATE (Guided only; Unshielded needs a late tier to unlock a shallow
    /// depth, Shielded gets a deep depth from its own tier 0). Running the battery flat is NOT tracked by
    /// this module at all — the computed draw is fed live into stock ModuleCommand's own EC input resource,
    /// so an empty battery loses control the same way any vanilla probe does (matches RP-1; no custom
    /// brownout/hysteresis check).
    ///
    /// Science storage (ModuleScienceContainer) is tier-gated like RP-1 (on from basicAvionics, both
    /// models) — the seed part carries the module statically; this checks it off at flight start if the
    /// as-built tier doesn't have it yet (matches RP-1's own Start()-only gating).
    ///
    /// kOS integration (disk space / EC-per-instruction / cost / mass, all per tier) is reflected onto a
    /// kOSProcessor module if one is present on the part — same duck-typed pattern as the RealFuels/
    /// ProceduralPart bridge below. kOS isn't currently an AXE dependency, so today this is a no-op.
    ///
    /// A "Set to Debris: Never/On Stage" toggle (ported from RP-1's ModuleAvionics) lets a spent stage that
    /// happened to carry avionics not clutter the tracking station as a permanent "Ship" after separating.
    ///
    /// Kerbalism's radiation-reliability wiring described in docs/AVIONICS_SPEC.md is deliberately NOT part
    /// of this pass (Kerbalism's Reliability feature is off instance-wide; that is a separate, later,
    /// game-wide balance task).
    ///
    /// The per-tier ladders (mass/power/cost, Near-Earth + Science-Core + Shielded, plus kOS + science-
    /// container gating + hibernate-depth gating) live in config as TIER nodes (single source of truth,
    /// mirrored by tools/avionics_compare.py); a hardcoded copy of the required fields is kept as a
    /// fallback.
    /// </summary>
    public class ModuleAxeAvionics : PartModule, IPartMassModifier, IPartCostModifier
    {
        internal const string PAWGroup = "AxeAvionics";
        const string GroupDisplay = "Avionics Core";
        const string EcName = "ElectricCharge";

        // ---- tech that unlocks attitude guidance ----
        [KSPField] public string guidanceTech = "gnc_postWarAvionics";

        // ---- EC draw curve (Unshielded / Near-Earth): watts = (dryMass^exp + const) * powerFactor(tier) ----
        [KSPField] public float powerExponent = 0.57853f;
        [KSPField] public float powerConstant = 1.035f;
        [KSPField] public float idleFactor = 0.1f;          // draw multiplier while guidance is inactive (dumb)
        [KSPField] public float hibernationFactor = 0.05f;  // Shielded hibernate depth (tier-invariant, RP-1 Deep-Space)

        // ---- hardware MASS curve exponent/constant (Unshielded / Near-Earth) ----
        [KSPField] public float massExponent = 0.46172f;
        [KSPField] public float massConstant = 0.96f;

        // ---- hardware COST curve exponent/constant (Unshielded / Near-Earth) ----
        [KSPField] public float costExponent = 0.46172f;
        [KSPField] public float costConstant = 3.034f;

        // ---- Shielded axis: own constants (ground-truthed against RP-1's real Deep-Space AVIONICSCONFIG) ----
        [KSPField] public float shMassConstant = 1.043f;
        [KSPField] public float shCostConstant = 9.1f;
        [KSPField] public float shPowerConstant = 1.096f;
        // Extra surface-area-scaled shielding mass RP-1 adds on top of the curve mass for Deep-Space
        // (ModuleProceduralAvionics.GetShieldingMass: avionicsMass^(2/3) * shieldingMassFactor), tier-invariant.
        // No cost equivalent -- RP-1's cost polynomial has no shielding add-on, mass only.
        [KSPField] public float shieldingMassFactor = 0.1f;

        // ---- volume: hardware occupies part of the box; density converts volume<->mass ----
        [KSPField] public float avionicsDensity = 0.5f;   // t/m^3

        // ---- persistent player state ----
        // The as-built avionics MODEL, chosen in the VAB and frozen at launch:
        //   true  = Near-Earth  (guided — full 3-axis control, capacity-derived hardware)
        //   false = Science-Core (unguided — light flat-mass sequencer, axial thrust only at high tiers)
        [KSPField(isPersistant = true)] public bool guidanceEnabled = true;
        // Guided-only second axis, VAB-frozen: Shielded uses its own full ladder (mass/cost/hibernate-depth),
        // not a multiplier on Unshielded. Blocked until at least one Shielded tier is researched.
        [KSPField(isPersistant = true)] public bool shieldedEnabled = false;
        // Flight-only deep sleep: cuts EC draw to the current hibernate depth and suspends control until woken.
        [KSPField(isPersistant = true)] public bool hibernating = false;
        // Per-part "Set to Debris" preference (RP-1 ModuleAvionics): a spent stage with this off (any one
        // command-capable part vetoes) never gets force-renamed to Debris on staging.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Set to Debris",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "Never", enabledText = "On Stage", affectSymCounterparts = UI_Scene.Editor)]
        public bool setToDebrisOnStage = false;

        // ---- 3-segment volume split (battery / hardware / empty) ----
        // The LIVE, current-box-clamped volumes (m^3) -- what everything else (mass, cost, capacity,
        // RealFuels) actually reads. On every resize these are re-derived from desiredBattVolume/
        // desiredHwVolume below, NOT from their own previous values -- otherwise a shrink-then-grow cycle
        // would permanently lose whatever got clamped away by the shrink (growing back up would only ever
        // enlarge "empty," never restore the original split).
        [KSPField(isPersistant = true)] public float battVolume = 0f;
        [KSPField(isPersistant = true)] public float hwVolume = 0f;
        // The REMEMBERED explicit intent (m^3) -- the last values the player actually dragged to, never
        // clamped themselves. A resize always tries to re-fit these first: battery gets priority (fit it
        // first), then hardware gets whatever room is left, then empty absorbs anything remaining --
        // matching the reverse order for shrinking (empty gives way first, then hardware, battery last).
        [KSPField(isPersistant = true)] public float desiredBattVolume = 0f;
        [KSPField(isPersistant = true)] public float desiredHwVolume = 0f;
        // The box's total volume at the moment the split above was last explicitly committed. Any
        // volume the box GAINS since then (a resize bigger, not a drag) flows to the player-adjustable
        // segment (hardware for Guided, battery for Unguided) by default -- otherwise growing the box
        // without re-dragging would silently balloon "empty" instead of giving usable capacity/charge,
        // and the player would have to re-drag every single time after a resize for it to do anything.
        // A deliberately-left empty gap (dragging a handle short of the box's far edge) is unaffected --
        // only volume PAST this remembered total counts as new growth.
        [KSPField(isPersistant = true)] public float desiredTotalVolume = 0f;
        // False until the player applies a manual split via the allocation window; while false, every
        // resize uses the default 25% battery / 75% hardware / 0% empty proportion.
        [KSPField(isPersistant = true)] public bool hasExplicitSplit = false;

        // ---- readouts (VAB-visible) ----
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Avionics Power",
                  guiFormat = "N1", guiUnits = " W", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float currentWatts = 0f;

        // Frozen hardware mass: recomputed in the editor from hwVolume, persisted with the craft, held
        // fixed in flight. IPartMassModifier returns this; the battery mass is RealFuels'.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Avionics Mass",
                  guiFormat = "F3", guiUnits = " t", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float avionicsMass = 0f;

        // Frozen hardware cost (funds): same hwVolume basis + freeze-at-launch as avionicsMass.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Avionics Cost",
                  guiFormat = "F0", guiUnits = " f", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float avionicsCost = 0f;

        // Guided only: how much vessel mass this core can steer, derived from hwVolume via the inverse of
        // the mass polynomial. 0 for Unguided (matches RP-1: Science-Core always contributes 0).
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Capacity",
                  guiFormat = "F2", guiUnits = " t", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float capacityTons = 0f;

        // How much of the current draw is "penalty" from being over capacity (MAX across active cores).
        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Overload Penalty",
                  guiFormat = "F0", guiUnits = "%", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float penaltyPercent = 0f;

        [KSPField(guiActiveEditor = true, guiName = "Split",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string allocationSummary = "";

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceStatus = "";

        // ---- runtime ----
        float _massFactor = 87.99f;   // current tier's Unshielded mass factor
        float _powerFactor = 56.415f; // current tier's power factor (shared by Unshielded/Shielded)
        float _costFactor = 48.12f;   // current tier's Unshielded cost factor
        float _scMassFactor = 33f;    // current tier's Science-Core flat mass factor (kg)
        float _scPowerFactor = 50f;   // current tier's Science-Core flat power (W)
        float _scCostFactor = 6f;     // current tier's Science-Core flat cost factor (funds)
        float _scDensity = 2.4f;      // current tier's Science-Core hardware density (t/m^3)
        bool _scAllowAxial = false;   // current tier: Science-Core permits axial-thrust control
        bool _hasScienceContainer = false; // current tier: RP-1 gates science storage on from basicAvionics
        float _unshHibernateFactor = -1f;  // current tier's Unshielded hibernate depth; <=0 = can't hibernate
        // current tier's kOS ladder (applied to a kOSProcessor module if present; no-op otherwise)
        float _kosDiskSpace = 500f;
        float _kosSpaceCostFactor = 0.1f;
        float _kosSpaceMassFactor = 0.0001f;
        float _kosEcPerInstruction = 0.000001f;
        // Shielded axis: best-researched Shielded tier's factors, and which ladder index it is (-1 = none
        // researched yet — unlike the Unshielded ladder, Shielded has no unconditional tier-0 floor).
        float _shMassFactor = 0f;
        float _shCostFactor = 0f;
        int _bestShieldedIdx = -1;
        KeyValuePair<string, double> _ecConsumption = new KeyValuePair<string, double>(EcName, 0);
        ModuleResource _commandEC;
        float _nextFlightRecalc;
        bool _onRails;                  // transient, not persisted — forces hibernate-depth draw while on rails
        static bool? _kerbalismPresent;

        // RealFuels bridge (reflected — AXE.dll doesn't reference RealFuels, same as the MechJeb/Kerbalism
        // reflection elsewhere). Used to read the box's total volume and push the battery segment into RF.
        PartModule _rfPM;
        MethodInfo _rfCalcMass;
        PartModule _procPM;
        PropertyInfo _procVolumeProp;    // ProceduralPart.Volume (m^3)
        float _cachedVolume = -1f;       // m^3 — the procedural part's total volume

        // kOS bridge (reflected — AXE.dll doesn't reference kOS, same duck-typed pattern as RealFuels above).
        PartModule _kosPM;
        FieldInfo _kosDiskSpaceField;
        FieldInfo _kosBaseDiskSpaceField;
        FieldInfo _kosDiskSpaceCostFactorField;
        FieldInfo _kosDiskSpaceMassFactorField;
        FieldInfo _kosEcPerInstructionField;

        // ---- config-driven tier ladder, with a hardcoded fallback ----
        // Tier 0 ("start") is the unconditional floor for the Guided/Unguided axis — no tech required,
        // ApplyTier always starts there. The Shielded axis has NO floor: its first rung is at basicAvionics.
        static string[] _ladTech =
        {
            "start", "gnc_postWarAvionics", "gnc_avionicsPrototypes", "gnc_earlyAvionics", "gnc_basicAvionics",
            "gnc_interplanetaryAvionics", "comp_digitalGuidanceComputer", "comp_realTimeFlightComputer", "comp_networkedAvionics",
            "comp_multiplyRedundantFlightComputer", "comp_distributedAvionicsBus", "comp_softwareDefinedFlightControl", "comp_interoperableAvionicsStandard", "comp_commercialOffTheShelfAvionics"
        };
        static float[] _ladMass =
        { 87.99f, 87.99f, 69.712f, 59.13f, 50.153f, 42.54f, 36.082f, 30.605f, 25.959f, 22.018f, 18.675f, 15.84f, 13.436f, 11.396f };
        static float[] _ladPower =
        { 56.415f, 56.415f, 47.851f, 40.587f, 34.426f, 29.2f, 24.767f, 21.007f, 17.818f, 15.113f, 12.819f, 10.873f, 9.222f, 7.822f };
        static float[] _ladCost =
        { 48.12f, 48.12f, 51.56f, 54.13f, 56.84f, 59.68f, 62.67f, 65.8f, 58.85f, 47.08f, 37.67f, 30.13f, 24.11f, 19.29f };
        static float[] _ladScMass =
        { 48f, 33f, 17f, 4f, 1.5f, 1f, 0.81f, 0.73f, 0.66f, 0.59f, 0.53f, 0.48f, 0.43f, 0.39f };
        static float[] _ladScPower =
        { 100f, 50f, 25f, 0.15f, 0.1f, 0.09f, 0.081f, 0.073f, 0.066f, 0.059f, 0.053f, 0.048f, 0.043f, 0.039f };
        static float[] _ladScCost =
        { 3f, 6f, 8f, 10f, 12f, 12f, 12f, 12f, 10f, 9f, 8.1f, 7.3f, 6.6f, 5.9f };
        static float[] _ladScDensity =
        { 3.35f, 2.4f, 1.4f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f };
        static bool[] _ladScAxial =
        { false, false, false, false, false, false, true, true, true, true, true, true, true, true };
        static bool[] _ladHasSci =
        { false, false, false, false, true, true, true, true, true, true, true, true, true, true };
        static float[] _ladKosDisk =
        { 500f, 500f, 500f, 500f, 500f, 5120f, 10240f, 20480f, 51200f, 102400f, 204800f, 307200f, 409600f, 512000f };
        static float[] _ladKosCostFactor =
        { 0.1f, 0.1f, 0.1f, 0.1f, 0.1f, 0.01f, 0.005f, 0.0025f, 0.001f, 0.0005f, 0.00025f, 0.0001f, 0.0001f, 0.0001f };
        static float[] _ladKosMassFactor =
        { 0.0001f, 0.0001f, 0.0001f, 0.0001f, 0.0001f, 0.0000005f, 0.0000002f, 0.0000001f, 0.00000005f, 0.000000005f, 0.000000002f, 0.000000001f, 0.0000000005f, 0.0000000002f };
        static float[] _ladKosEcPerInstr =
        { 0.000001f, 0.000001f, 0.000004f, 0.000002f, 0.000001f, 0.0000004f, 0.0000002f, 0.0000001f, 0.00000008f, 0.00000004f, 0.00000001f, 0.00000001f, 0.00000001f, 0.00000001f };
        // Shielded axis (ground-truthed against RP-1's real Deep-Space AVIONICSCONFIG for indices 4-13,
        // "basicAvionics" on -- RP-1 has no Deep-Space data before that). Indices 0-3 ("start" through
        // "earlyAvionics") have no RP-1 equivalent to port; reused from the Unshielded ladder verbatim
        // (matches _ladMass/_ladCost at the same indices) so the ladder has no gaps for tree/tooling
        // symmetry. The Shielded TOGGLE itself stays gated behind ShieldedUnlocked (gnc_basicAvionics),
        // same as before this fill-in -- see ShieldedUnlocked below.
        static float[] _ladShMass =
        { 87.99f, 87.99f, 69.712f, 59.13f, 55.168f, 46.794f, 39.69f, 33.665f, 28.554f, 24.22f, 20.543f, 17.424f, 14.779f, 12.536f };
        static float[] _ladShCost =
        { 48.12f, 48.12f, 51.56f, 54.13f, 85.26f, 89.52f, 94.0f, 98.7f, 88.28f, 70.62f, 56.5f, 45.2f, 36.16f, 28.93f };
        // Unshielded hibernate depth: <=0 sentinel = can't hibernate. First 9 tiers can't; the last 5
        // (advancedAvionics-equivalent on) reach a shallow 0.1 — ground-truthed against RP-1's real
        // disabledPowerFactor boundary.
        static float[] _ladUnshHibernate =
        { -1f, -1f, -1f, -1f, -1f, -1f, -1f, -1f, -1f, 0.1f, 0.1f, 0.1f, 0.1f, 0.1f };

        public bool GuidanceUnlocked => Researched(guidanceTech);
        public bool GuidanceActive => GuidanceUnlocked && guidanceEnabled && !hibernating;
        public bool ScienceCoreMode => !guidanceEnabled;
        public bool AxialActive => ScienceCoreMode && _scAllowAxial && !hibernating;
        float EffectiveDensity() => guidanceEnabled ? avionicsDensity : (_scDensity > 0f ? _scDensity : avionicsDensity);
        public string GuidanceTech => guidanceTech;

        // Guided only: can this core hibernate at all right now, and how deep. Shielded needs a researched
        // Shielded tier (any of them — depth is tier-invariant); Unshielded needs the late tier that
        // unlocks the shallow depth.
        public bool CanHibernate => guidanceEnabled && (shieldedEnabled ? _bestShieldedIdx >= 0 : _unshHibernateFactor > 0f);
        public float CurrentHibernateFactor => (shieldedEnabled && _bestShieldedIdx >= 0) ? hibernationFactor : _unshHibernateFactor;

        static bool KerbalismPresent
        {
            get
            {
                if (_kerbalismPresent == null)
                {
                    _kerbalismPresent = false;
                    foreach (var a in AssemblyLoader.loadedAssemblies)
                        if (a.name == "Kerbalism") { _kerbalismPresent = true; break; }
                }
                return _kerbalismPresent.Value;
            }
        }

        static bool Researched(string tech)
        {
            if (string.IsNullOrEmpty(tech)) return true;
            if (HighLogic.CurrentGame == null || HighLogic.CurrentGame.Mode == Game.Modes.SANDBOX) return true;
            return ResearchAndDevelopment.GetTechnologyState(tech) == RDTech.State.Available;
        }

        // Parse the per-tier ladder from config TIER nodes (single source of truth). Craft-instance loads
        // carry no TIER children, so the prefab-parsed values (or the hardcoded fallback) stay in force.
        public override void OnLoad(ConfigNode node)
        {
            base.OnLoad(node);
            ConfigNode[] tiers = node?.GetNodes("TIER");
            if (tiers == null || tiers.Length == 0) return;

            var tech = new List<string>();
            var mass = new List<float>();
            var power = new List<float>();
            var cost = new List<float>();
            var scMass = new List<float>();
            var scPower = new List<float>();
            var scCost = new List<float>();
            var scDensity = new List<float>();
            var scAxial = new List<bool>();
            var hasSci = new List<bool>();
            var kosDisk = new List<float>();
            var kosCostFactor = new List<float>();
            var kosMassFactor = new List<float>();
            var kosEcPerInstr = new List<float>();
            var shMass = new List<float>();
            var shCost = new List<float>();
            var unshHib = new List<float>();
            foreach (ConfigNode t in tiers)
            {
                string tn = t.GetValue("tech");
                if (string.IsNullOrEmpty(tn)) continue;
                float mf = 0f, pf = 0f, scm = 0f, scp = 0f, scd = 0f;
                bool sca = false;
                t.TryGetValue("massFactor", ref mf);
                t.TryGetValue("powerFactor", ref pf);
                t.TryGetValue("scMassFactor", ref scm);
                t.TryGetValue("scPowerFactor", ref scp);
                t.TryGetValue("scDensity", ref scd);
                t.TryGetValue("scAllowAxial", ref sca);
                if (mf <= 0f || pf <= 0f || scm <= 0f || scp <= 0f || scd <= 0f) continue; // all-or-nothing per tier
                tech.Add(tn); mass.Add(mf); power.Add(pf);
                scMass.Add(scm); scPower.Add(scp); scDensity.Add(scd); scAxial.Add(sca);

                // Cost/kOS/science-container/Shielded/hibernate-gate are optional per tier (default to
                // 0/false/-1, not tier-dropping).
                float cf = 0f, scc = 0f, kd = 0f, kcf = 0f, kmf = 0f, kec = 0f, shm = 0f, shc = 0f, uh = -1f;
                bool hsc = false;
                t.TryGetValue("costFactor", ref cf);
                t.TryGetValue("scCostFactor", ref scc);
                t.TryGetValue("hasScienceContainer", ref hsc);
                t.TryGetValue("kosDiskSpace", ref kd);
                t.TryGetValue("kosSpaceCostFactor", ref kcf);
                t.TryGetValue("kosSpaceMassFactor", ref kmf);
                t.TryGetValue("kosECPerInstruction", ref kec);
                t.TryGetValue("shMassFactor", ref shm);
                t.TryGetValue("shCostFactor", ref shc);
                t.TryGetValue("unshHibernateFactor", ref uh);
                cost.Add(cf); scCost.Add(scc); hasSci.Add(hsc);
                kosDisk.Add(kd); kosCostFactor.Add(kcf); kosMassFactor.Add(kmf); kosEcPerInstr.Add(kec);
                shMass.Add(shm); shCost.Add(shc); unshHib.Add(uh);
            }
            if (tech.Count == 0) return; // no complete tiers => keep the hardcoded fallback ladders
            _ladTech = tech.ToArray();
            _ladMass = mass.ToArray();
            _ladPower = power.ToArray();
            _ladCost = cost.ToArray();
            _ladScMass = scMass.ToArray();
            _ladScPower = scPower.ToArray();
            _ladScCost = scCost.ToArray();
            _ladScDensity = scDensity.ToArray();
            _ladScAxial = scAxial.ToArray();
            _ladHasSci = hasSci.ToArray();
            _ladKosDisk = kosDisk.ToArray();
            _ladKosCostFactor = kosCostFactor.ToArray();
            _ladKosMassFactor = kosMassFactor.ToArray();
            _ladKosEcPerInstr = kosEcPerInstr.ToArray();
            _ladShMass = shMass.ToArray();
            _ladShCost = shCost.ToArray();
            _ladUnshHibernate = unshHib.ToArray();
        }

        public override void OnStartFinished(StartState state)
        {
            _commandEC = FindCommandEC();
            ResolveTankBridge();
            ApplyTier();
            ApplyShieldedTier();

            if (HighLogic.LoadedSceneIsEditor)
            {
                GameEvents.onEditorShipModified.Add(OnShipModified);
                // ProceduralPart's own shape/volume isn't necessarily settled the same frame this part
                // starts (its shape application can run across a frame boundary) -- reading volume
                // synchronously here can catch it before that settles, producing a near-zero cached
                // volume that then sticks (near-zero capacity -> tripped overload penalty) until the
                // next onEditorShipModified event, e.g. the player's first resize -- matches "broken
                // right after placing the part, fine after the first resize." One frame's delay mirrors
                // the same idiom AxeAllocationBarHook already uses for onPartActionUICreate/CreatePartList.
                StartCoroutine(EditorFirstFrameSetup());
            }
            else
            {
                _cachedVolume = ReadProceduralVolume();
                // Flight: hardware mass/cost/capacity are frozen (persisted). Legacy craft (mass 0) get one
                // fallback compute from whatever hwVolume was persisted (0 for pre-redesign saves).
                if (avionicsMass <= 0f) UpdateHardwareMass();
                GameEvents.onStageActivate.Add(OnStage);
                GameEvents.onVesselGoOnRails.Add(GoOnRails);
                GameEvents.onVesselGoOffRails.Add(GoOffRails);

                // Science storage is tier-gated (RP-1: on from basicAvionics). Checked once at flight start,
                // same as RP-1's own Start()-only gating.
                if (!_hasScienceContainer)
                {
                    ModuleScienceContainer sci = part.FindModuleImplementing<ModuleScienceContainer>();
                    if (sci != null) part.RemoveModule(sci);
                }
            }

            UpdateRate();
            SetGui();
        }

        // See the comment at its call site in OnStartFinished: gives ProceduralPart's own shape/volume
        // a frame to settle before this module's first read of it.
        IEnumerator EditorFirstFrameSetup()
        {
            yield return null;
            _cachedVolume = ReadProceduralVolume();
            RecomputeSplit(_cachedVolume);
            UpdateHardwareMass();
            PushBatteryToTank();
            UpdateRate();
            SetGui();
        }

        void OnDestroy()
        {
            GameEvents.onEditorShipModified.Remove(OnShipModified);
            GameEvents.onStageActivate.Remove(OnStage);
            GameEvents.onVesselGoOnRails.Remove(GoOnRails);
            GameEvents.onVesselGoOffRails.Remove(GoOffRails);
        }

        // Editor: tier, split, hardware mass/cost/capacity, and the battery push all track the build.
        void OnShipModified(ShipConstruct _)
        {
            if (!HighLogic.LoadedSceneIsEditor) return;
            ApplyTier();
            ApplyShieldedTier();
            _cachedVolume = ReadProceduralVolume();
            RecomputeSplit(_cachedVolume);
            UpdateHardwareMass();
            PushBatteryToTank();
            UpdateRate();
        }

        void OnStage(int _)
        {
            UpdateRate();
            if (setToDebrisOnStage) StartCoroutine(CheckRenameDebris());
        }

        // Ported from RP-1's ModuleAvionics.CheckRenameDebris(): 1s after staging, if this vessel is no
        // longer the active one (the piece just left behind), scan it for any command-capable part whose
        // avionics is explicitly set to "Never" (any one vetoes) — otherwise mark it Debris. Pure tracking-
        // station hygiene; no funds/recovery/science effect.
        IEnumerator CheckRenameDebris()
        {
            yield return new WaitForSeconds(1f);
            if (vessel == null || vessel == FlightGlobals.ActiveVessel) yield break;
            bool rename = true;
            foreach (Part p in vessel.Parts)
            {
                if (p.FindModuleImplementing<ModuleCommand>() == null) continue;
                ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
                bool debris = axe?.setToDebrisOnStage ?? true;
                if (!debris) { rename = false; break; }
            }
            if (rename) vessel.vesselType = VesselType.Debris;
        }

        void GoOnRails(Vessel v) => RailChange(v, true);
        void GoOffRails(Vessel v) => RailChange(v, false);

        // Ported from RP-1's ModuleAvionics: while on rails (unloaded/timewarping), draw auto-drops to the
        // current hibernate-equivalent rate regardless of the manual toggle, and reverts the instant it's
        // back off rails.
        void RailChange(Vessel v, bool onRails)
        {
            if (vessel != v) return;
            _onRails = onRails;
            UpdateRate();
        }

        // Flight only: recompute EC draw ~1 Hz so it tracks fuel burn / staging / on-rails state. Hardware
        // mass/cost/capacity are frozen and never change in flight. The editor-side allocation bar is driven
        // entirely by AxeAllocationBarHook reacting to PAW open/close events, not polled here.
        void Update()
        {
            if (!HighLogic.LoadedSceneIsFlight) return;
            if (Time.time < _nextFlightRecalc) return;
            _nextFlightRecalc = Time.time + 1f;
            UpdateRate();
        }

        ModuleResource FindCommandEC()
        {
            ModuleCommand cmd = part.FindModuleImplementing<ModuleCommand>();
            if (cmd?.resHandler?.inputResources == null) return null;
            foreach (ModuleResource r in cmd.resHandler.inputResources)
                if (r != null && r.id == PartResourceLibrary.ElectricityHashcode) return r;
            return null;
        }

        // Resolve RealFuels' ModuleFuelTanks + the ProceduralPart volume property by reflection (RealFuels
        // and ProceduralParts aren't referenced by AXE.dll). Missing either => degrade gracefully. Also
        // resolves a kOSProcessor module, if present, for the kOS tier bridge below.
        void ResolveTankBridge()
        {
            const BindingFlags F = BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy;
            foreach (PartModule m in part.Modules)
            {
                string n = m.GetType().Name;
                if (_rfPM == null && n == "ModuleFuelTanks")
                {
                    _rfPM = m;
                    _rfCalcMass = m.GetType().GetMethod("CalculateMass", BindingFlags.Public | BindingFlags.Instance);
                }
                else if (_procPM == null && n == "ProceduralPart")
                {
                    _procPM = m;
                    _procVolumeProp = m.GetType().GetProperty("Volume", F);
                }
                else if (_kosPM == null && n == "kOSProcessor")
                {
                    _kosPM = m;
                    Type kt = m.GetType();
                    _kosDiskSpaceField = kt.GetField("diskSpace", F);
                    _kosBaseDiskSpaceField = kt.GetField("baseDiskSpace", F);
                    _kosDiskSpaceCostFactorField = kt.GetField("diskSpaceCostFactor", F);
                    _kosDiskSpaceMassFactorField = kt.GetField("diskSpaceMassFactor", F);
                    _kosEcPerInstructionField = kt.GetField("ECPerInstruction", F);
                }
            }
        }

        // Push the current tier's kOS ladder onto the resolved kOSProcessor (no-op if kOS isn't installed).
        void ApplyKosTier()
        {
            if (_kosPM == null) return;
            try
            {
                int floor = Mathf.RoundToInt(_kosDiskSpace);
                _kosBaseDiskSpaceField?.SetValue(_kosPM, floor);
                if (_kosDiskSpaceField != null && (int)_kosDiskSpaceField.GetValue(_kosPM) < floor)
                    _kosDiskSpaceField.SetValue(_kosPM, floor);
                _kosDiskSpaceCostFactorField?.SetValue(_kosPM, _kosSpaceCostFactor);
                _kosDiskSpaceMassFactorField?.SetValue(_kosPM, _kosSpaceMassFactor);
                _kosEcPerInstructionField?.SetValue(_kosPM, _kosEcPerInstruction);
            }
            catch { }
        }

        float ReadProceduralVolume()
        {
            if (_procPM == null || _procVolumeProp == null) return _cachedVolume;
            try { return Convert.ToSingle(_procVolumeProp.GetValue(_procPM, null)); }
            catch { return _cachedVolume; }
        }

        // Pick the best researched Guided/Unguided tier (lowest-or-tied NE mass factor; tier 0 "start" if
        // none researched — the unconditional floor). <= (not <) so a researched tier tying the floor on NE
        // mass (start vs postWarAvionics) still advances, letting Science-Core step down off the tied floor.
        void ApplyTier()
        {
            int best = 0;
            for (int i = 1; i < _ladTech.Length; i++)
                if (Researched(_ladTech[i]) && _ladMass[i] <= _ladMass[best]) best = i;
            _massFactor = _ladMass[best];
            _powerFactor = _ladPower[best];
            _costFactor = _ladCost[best];
            _scMassFactor = _ladScMass[best];
            _scPowerFactor = _ladScPower[best];
            _scCostFactor = _ladScCost[best];
            _scDensity = _ladScDensity[best];
            _scAllowAxial = _ladScAxial[best];
            _hasScienceContainer = _ladHasSci[best];
            _kosDiskSpace = _ladKosDisk[best];
            _kosSpaceCostFactor = _ladKosCostFactor[best];
            _kosSpaceMassFactor = _ladKosMassFactor[best];
            _kosEcPerInstruction = _ladKosEcPerInstr[best];
            _unshHibernateFactor = _ladUnshHibernate[best];
            ApplyKosTier();
        }

        // Shielded axis: pick the best-researched tier among only those that carry a Shielded rung
        // (shMassFactor > 0). No floor/fallback — -1 means "not available yet."
        void ApplyShieldedTier()
        {
            int best = -1;
            for (int i = 0; i < _ladTech.Length; i++)
            {
                if (_ladShMass[i] <= 0f) continue;
                if (!Researched(_ladTech[i])) continue;
                if (best == -1 || _ladShMass[i] <= _ladShMass[best]) best = i;
            }
            _bestShieldedIdx = best;
            if (best >= 0)
            {
                _shMassFactor = _ladShMass[best];
                _shCostFactor = _ladShCost[best];
            }
        }

        bool ShieldedActive => shieldedEnabled && _bestShieldedIdx >= 0;
        // Whether the Shielded TOGGLE itself is unlocked -- independent of _bestShieldedIdx, which can
        // now be valid from tier 0 since the ladder was filled in for tree symmetry (see _ladShMass).
        // Deliberately still keyed to gnc_basicAvionics specifically (the first tier RP-1 itself ever
        // offered Deep-Space at) so the toggle doesn't appear before that, matching pre-fill-in behavior.
        public bool ShieldedUnlocked => Researched("gnc_basicAvionics");
        float EffectiveMassFactor() => ShieldedActive ? _shMassFactor : _massFactor;
        float EffectiveCostFactor() => ShieldedActive ? _shCostFactor : _costFactor;
        float EffectiveMassConstant() => ShieldedActive ? shMassConstant : massConstant;
        float EffectiveCostConstant() => ShieldedActive ? shCostConstant : costConstant;
        float EffectivePowerConstant() => ShieldedActive ? shPowerConstant : powerConstant;

        // Editor only: how much box volume Unguided's flat per-tier hardware mass occupies. Not player-
        // adjustable (Unguided's mass doesn't scale with box size) — pinned every recompute.
        float FixedUnguidedHwVolume() => EffectiveDensity() > 0f ? (_scMassFactor / 1000f) / EffectiveDensity() : 0f;

        // Editor only: split total box volume V into battery/hardware/empty. If the player hasn't
        // explicitly set a split, use the default 25% battery / 75% hardware (Unguided: hardware is pinned,
        // battery gets the rest). If they have, re-fit toward the REMEMBERED desired values (not whatever
        // battVolume/hwVolume happened to be clamped to on the last resize) -- battery gets priority (fit
        // it first), then hardware gets whatever room is left. Any volume the box has GAINED since the
        // split was last explicitly committed (desiredTotalVolume) flows to the player-adjustable segment
        // (hardware for Guided, battery for Unguided) -- growing the box is how you get more capacity/
        // charge; without this, a resize bigger would only ever balloon "empty," and the player would have
        // to re-drag the handle every single time after a resize for it to do anything. Volume the box has
        // LOST (a shrink) still re-fits toward the remembered values exactly as before.
        void RecomputeSplit(float v)
        {
            float growth = hasExplicitSplit ? Mathf.Max(0f, v - desiredTotalVolume) : 0f;
            if (!guidanceEnabled)
            {
                hwVolume = FixedUnguidedHwVolume();
                battVolume = hasExplicitSplit ? Mathf.Min(desiredBattVolume + growth, Mathf.Max(0f, v - hwVolume))
                                               : Mathf.Max(0f, v - hwVolume);
            }
            else if (!hasExplicitSplit)
            {
                battVolume = 0.25f * v;
                hwVolume = 0.75f * v;
            }
            else
            {
                battVolume = Mathf.Min(desiredBattVolume, v);
                hwVolume = Mathf.Min(desiredHwVolume + growth, Mathf.Max(0f, v - battVolume));
            }
            battVolume = Mathf.Max(battVolume, EnduranceFloorVolume());
            battVolume = Mathf.Min(battVolume, v);
            hwVolume = Mathf.Max(0f, Mathf.Min(hwVolume, v - battVolume));
        }

        // Minimum battery volume — ground-truthed verbatim against RP-1's real reservedRFTankVolume
        // (ProceduralAvionics.cfg): a small FIXED constant, identical at every tier, not runtime/draw-based.
        // RP-1 has NO equivalent floor on the hardware side at all — hardware volume there is purely
        // GetAvionicsMass()/avionicsDensity, whatever the player's rating computes, with nothing enforced
        // as a minimum. This matches both facts: only battVolume gets a floor, hwVolume never does.
        const float GuidedReservedVolume = 0.003f;    // 3 L — RP-1's Near-Earth/Deep-Space, every tier
        const float UnguidedReservedVolume = 0.0015f; // 1.5 L — RP-1's Science-Core, every tier
        float EnduranceFloorVolume() => guidanceEnabled ? GuidedReservedVolume : UnguidedReservedVolume;

        // Editor only: hardware mass/cost/capacity, all derived from hwVolume (frozen at launch, persisted).
        //   Guided   = hwVolume * density -> mass; capacity = inverse mass-polynomial of that mass; cost is
        //              the (forward) cost-polynomial of that capacity — mirrors RP-1's real
        //              GetAvionicsCost(controllableMass), which takes the rating, not the mass, as input.
        //   Unguided = RP-1's flat per-tier mass (scMassFactor/1000 t); no capacity concept.
        void UpdateHardwareMass()
        {
            if (guidanceEnabled)
            {
                // avionicsMass is the HONEST mass the player actually built (box volume -> mass) -- this
                // is what IPartMassModifier reports and must never be adjusted down.
                avionicsMass = hwVolume * EffectiveDensity();
                // Shielded: RP-1 adds an extra surface-area-scaled shielding mass ON TOP of the curve's
                // own mass (GetShieldedAvionicsMass = curveMass + curveMass^(2/3)*shieldingMassFactor) --
                // i.e. part of avionicsMass is "spent" on shielding rather than contributing to capacity.
                // AXE's box-first model runs the opposite direction (physical mass -> capacity, not
                // capacity -> mass), so recover the equivalent "curve mass" that capacity should be
                // derived from by inverting that relation: curveMass = avionicsMass - curveMass^(2/3)*
                // shieldingMassFactor. A few fixed-point iterations converge to well under 0.05% error
                // (shieldingMassFactor is a ~10-20% term).
                float curveMass = avionicsMass;
                if (ShieldedActive)
                {
                    for (int i = 0; i < 4; i++)
                        curveMass = avionicsMass - Mathf.Pow(curveMass, 2f / 3f) * shieldingMassFactor;
                    curveMass = Mathf.Max(0f, curveMass);
                }
                capacityTons = GetInversePolynomial(curveMass * 1000f, massExponent, EffectiveMassConstant(), EffectiveMassFactor());
                avionicsCost = Poly(capacityTons, costExponent, EffectiveCostConstant(), EffectiveCostFactor());
            }
            else
            {
                avionicsMass = _scMassFactor / 1000f;
                avionicsCost = _scCostFactor;
                capacityTons = 0f;
            }
        }

        // Push the battery segment's volume into RealFuels (RF then sizes the EC tank + recomputes its
        // mass/cost). Driven from OnShipModified/OnStartFinished, after RecomputeSplit/UpdateHardwareMass.
        void PushBatteryToTank()
        {
            if (!HighLogic.LoadedSceneIsEditor || _rfPM == null) return;
            SendVolumeChangedEvent(battVolume);
            try { _rfCalcMass?.Invoke(_rfPM, null); } catch { }
        }

        void SendVolumeChangedEvent(double newVolume)
        {
            var data = new BaseEventDetails(BaseEventDetails.Sender.USER);
            data.Set<string>("volName", "Tankage");
            data.Set("newTotalVolume", newVolume);     // m^3 — RealFuels' ModuleFuelTanks listens for this
            part.SendEvent("OnPartVolumeChanged", data, 0);
        }

        // Called every drag-move frame by the allocation bar: writes the live split directly, so every
        // other readout (mass, cost, capacity, EC draw, penalty, endurance, and the actual RealFuels
        // battery pool via PushBatteryToTank) updates in real time as the player drags -- whatever the
        // last position is IS the state, no separate preview/pending shadow copy to keep in sync (that
        // duplication was the likely source of the "doesn't update" / "snaps back" bugs). Clamped by the
        // same endurance floor as everywhere else, so the floor's effect is visible live, not just on
        // release. Symmetry sync and the comparatively expensive onEditorShipModified event are deliberately
        // NOT fired here every frame -- see CommitAllocationDrag(), called once on release.
        public void LiveUpdateSplit(float battVolumeM3, float hwVolumeM3)
        {
            float v = _cachedVolume;
            if (v <= 0f) return;
            // Remember the RAW dragged-to values (pre-floor) as the desired intent -- a resize re-fits
            // toward these, not toward whatever the floor/clamp forced the live battVolume/hwVolume to.
            desiredBattVolume = Mathf.Max(0f, battVolumeM3);
            desiredHwVolume = Mathf.Max(0f, hwVolumeM3);
            float floor = EnduranceFloorVolume();
            battVolume = Mathf.Clamp(Mathf.Max(desiredBattVolume, floor), 0f, v);
            hwVolume = Mathf.Clamp(desiredHwVolume, 0f, v - battVolume);
            UpdateHardwareMass();
            PushBatteryToTank();
            UpdateRate();
        }

        // Called once when the drag ends: the values are already live-correct (LiveUpdateSplit clamps
        // continuously), so this just marks the split explicit, syncs symmetry counterparts to match, and
        // fires the one onEditorShipModified other systems need to react to.
        public void CommitAllocationDrag()
        {
            hasExplicitSplit = true;
            desiredTotalVolume = _cachedVolume;
            foreach (Part p in part.symmetryCounterparts)
            {
                ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
                if (axe == null) continue;
                axe.battVolume = battVolume; axe.hwVolume = hwVolume;
                axe.desiredBattVolume = desiredBattVolume; axe.desiredHwVolume = desiredHwVolume;
                axe.desiredTotalVolume = axe._cachedVolume;
                axe.hasExplicitSplit = true;
            }
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
        }

        // Called by the allocation window's Reset button.
        public void ResetAllocationToDefault()
        {
            foreach (Part p in part.symmetryCounterparts)
            {
                ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
                if (axe != null) axe.hasExplicitSplit = false;
            }
            hasExplicitSplit = false;
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
        }

        public float CachedVolumeLiters => _cachedVolume * 1000f;
        public float FixedUnguidedHwVolumeLiters => FixedUnguidedHwVolume() * 1000f;

        float VesselMassTons()
        {
            if (HighLogic.LoadedSceneIsEditor)
                return EditorLogic.fetch?.ship != null ? EditorLogic.fetch.ship.GetTotalMass() : 0f;
            return vessel != null ? (float)vessel.totalMass : 0f;
        }

        // Live DRY mass (tons) — vessel mass excluding propellant/resources, so EC draw is independent of
        // fuel load and steps down only when stages/parts are dropped.
        float VesselDryMassTons()
        {
            float t = 0f;
            List<Part> parts = HighLogic.LoadedSceneIsEditor ? EditorLogic.fetch?.ship?.parts : vessel?.parts;
            if (parts == null) return 0f;
            for (int i = 0; i < parts.Count; i++)
            {
                Part p = parts[i];
                if (p == null) continue;
                t += p.mass + p.GetModuleMass(p.mass);
            }
            return t;
        }

        static float Poly(float value, float exponent, float constant, float factor)
            => (Mathf.Pow(value, exponent) + constant) * factor;

        // RP-1's GetInversePolynomial (ModuleProceduralAvionics.cs), ground-truthed verbatim: given a mass,
        // solve for the "load"/capacity that would produce it under the forward polynomial. Clamps to 0 on
        // NaN/Infinity, reproducing RP-1's own "hard minimum box size for any positive capacity" floor.
        static float GetInversePolynomial(float value, float exponent, float constant, float factor)
        {
            if (factor <= 0f) return 0f;
            float res = Mathf.Pow(value / factor - constant, 1f / exponent);
            if (float.IsNaN(res) || float.IsInfinity(res)) return 0f;
            return res;
        }

        // MAX across the vessel's active Guided cores (RP-1's own 2021 anti-cheese rule — SUM lets a
        // stack of cheap small cores cheese capacity). Ground-truthed against RP-1's real
        // ControlLockerUtils.ShouldLock(): it aggregates every ModuleAvionics' CurrentMassLimit
        // unconditionally (gated only on having EC connected, or being in the editor) -- there is NO
        // "is guidance tech researched" gate on whether a core's mass counts. A core's tier (and
        // therefore capacityTons) is ALWAYS valid -- ApplyTier()'s tier-0 floor guarantees that -- so
        // "dumb" avionics (guidance not yet researched) still needs to not overload for its own rated
        // mass; GuidanceUnlocked only gates whether the vessel can actively STEER (GuidanceActive),
        // a separate concern handled elsewhere. Previously this method also excluded un-researched
        // cores here, which meant EVERY Guided core showed max overload penalty from the moment it was
        // placed until guidanceTech was researched, regardless of how it was sized -- a real bug, not
        // RP-1 parity. Hibernating cores still don't contribute (asleep, not actively protecting the
        // vessel's overload budget).
        float EffectiveCapacityTons()
        {
            List<Part> parts = HighLogic.LoadedSceneIsEditor ? EditorLogic.fetch?.ship?.parts : vessel?.parts;
            if (parts == null) return capacityTons;
            float max = 0f;
            for (int i = 0; i < parts.Count; i++)
            {
                ModuleAxeAvionics axe = parts[i]?.FindModuleImplementing<ModuleAxeAvionics>();
                if (axe == null || !axe.guidanceEnabled || axe.hibernating) continue;
                if (axe.capacityTons > max) max = axe.capacityTons;
            }
            return max;
        }

        // r = live vessel mass / effective capacity. r<=1 -> no penalty. Past that, a smooth exponential
        // penalty (spec-locked k=8) — gentle at small overages, prohibitive past ~25-50% over. Deliberately
        // NOT guarded when capacity floors at 0 while mass>0 (r -> +Infinity, multiplier -> +Infinity) —
        // that hard-wall consequence is the spec's explicitly accepted outcome of an undersized core.
        // Exponent argument is clamped (not the multiplier itself) so a badly undersized core (capacity
        // near/at 0 while mass>0, r -> +Infinity) still reads as an enormous but FINITE watts figure
        // instead of the literal string "Infinity" -- Mathf.Exp(80) alone is ~5.5e34, comfortably under
        // float's ~3.4e38 ceiling. The severe-penalty intent for an undersized core is unchanged; this
        // only fixes the display/precision overflow, not the underlying "hard floor" behavior.
        const float PenaltyExponentCap = 80f;

        float PenaltyMultiplier()
        {
            if (!guidanceEnabled) return 1f;
            float mass = VesselMassTons();
            if (mass <= 0f) return 1f;
            float capacity = EffectiveCapacityTons();
            float r = mass / capacity;
            return r <= 1f ? 1f : Mathf.Exp(Mathf.Min(8f * (r - 1f), PenaltyExponentCap));
        }

        // Operating EC draw (watts) for the current model, before idle/hibernation reduction, WITH the
        // overload penalty already folded in (so both the editor preview and the flight readout show it):
        //   Guided draws off live DRY mass and gets lighter per researched tier, then scaled by the
        //   overload penalty; Science-Core draws a flat per-tier rate (no capacity concept, no penalty).
        float ComputeBaseWatts() => TierWatts() * (guidanceEnabled ? PenaltyMultiplier() : 1f);

        // The tier/mass-based draw BEFORE the overload penalty is applied (ComputeBaseWatts() multiplies
        // this by PenaltyMultiplier()) -- kept separate since some callers need the unpenalized figure.
        float TierWatts()
        {
            if (!guidanceEnabled) return _scPowerFactor;
            float m = VesselDryMassTons();
            if (m <= 0f) return 0f;
            return Poly(m, powerExponent, EffectivePowerConstant(), _powerFactor);
        }

        // Actual live draw: forced to the current hibernate depth while hibernating OR on rails (matches
        // RP-1's auto-drop-on-warp, independent of the manual toggle); otherwise Science-Core stays flat,
        // Guided draws full when guiding and idleFactor when dumb.
        float ComputeWatts()
        {
            float b = ComputeBaseWatts();
            if (guidanceEnabled && CanHibernate && (hibernating || _onRails)) return b * CurrentHibernateFactor;
            if (!guidanceEnabled) return b;
            return GuidanceActive ? b : b * idleFactor;
        }

        void UpdateRate()
        {
            currentWatts = HighLogic.LoadedSceneIsEditor ? ComputeBaseWatts() : ComputeWatts();
            penaltyPercent = (PenaltyMultiplier() - 1f) * 100f;
            _ecConsumption = new KeyValuePair<string, double>(EcName, -currentWatts / 1000.0);
            if (_commandEC != null) _commandEC.rate = KerbalismPresent ? 0f : currentWatts / 1000f;
            UpdateAllocationSummary();
            SetGui();
        }

        void UpdateAllocationSummary()
        {
            float empty = Mathf.Max(0f, _cachedVolume - battVolume - hwVolume);
            allocationSummary = $"{battVolume * 1000f:F0} L batt / {hwVolume * 1000f:F0} L hw / {empty * 1000f:F0} L empty";
        }

        void SetGui()
        {
            // Model selector: VAB-only (model + mass are frozen at launch).
            BaseEvent mt = Events[nameof(ToggleGuidance)];
            mt.guiActive = false;
            mt.guiActiveEditor = true;
            mt.guiName = guidanceEnabled ? "Switch to Unguided" : "Switch to Guided";

            // Shielding selector: VAB-only, Guided-only, blocked until ShieldedUnlocked (gnc_basicAvionics).
            BaseEvent sh = Events[nameof(ToggleShielding)];
            sh.guiActive = false;
            sh.guiActiveEditor = guidanceEnabled && ShieldedUnlocked;
            sh.guiName = shieldedEnabled ? "Switch to Unshielded" : "Switch to Shielded";

            // Hibernation: flight-only deep sleep, Guided only, gated by CanHibernate (Unshielded needs a
            // late tier; Shielded is available from its own tier 0).
            BaseEvent hb = Events[nameof(ToggleHibernation)];
            hb.guiActive = CanHibernate;
            hb.guiActiveEditor = false;
            hb.guiName = hibernating ? "Wake from Hibernation" : "Hibernate";
            Actions[nameof(HibernateAction)].active = CanHibernate;

            guidanceStatus = hibernating ? "hibernating — low power, control suspended"
                           : ScienceCoreMode ? (_scAllowAxial ? "Unguided — axial thrust only (spin-stabilized)"
                                                              : "Unguided — no steering")
                           : !GuidanceUnlocked ? "Guided — guidance not yet researched (dumb)"
                           : shieldedEnabled ? "Guided — Shielded — guidance active"
                           : "Guided — Unshielded — guidance active";
        }

        // VAB-only: pick the as-built model. Firing onEditorShipModified re-runs the full editor recompute;
        // mass/cost/capacity are then frozen at launch.
        [KSPEvent(guiActive = false, guiActiveEditor = true, guiName = "Switch to Unguided", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleGuidance()
        {
            guidanceEnabled = !guidanceEnabled;
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
            else
                UpdateRate();
            SetGui();
        }

        // VAB-only, Guided-only: pick Shielded vs Unshielded. Blocked (no-op) until ShieldedUnlocked.
        [KSPEvent(guiActive = false, guiActiveEditor = true, guiName = "Switch to Shielded", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleShielding()
        {
            if (!guidanceEnabled || !ShieldedUnlocked) return;
            shieldedEnabled = !shieldedEnabled;
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
            else
                UpdateRate();
            SetGui();
        }

        // Flight: toggle deep sleep. Guarded on CanHibernate (Guided only; Unshielded needs its late tier,
        // Shielded is available from its own tier 0).
        [KSPEvent(guiActive = true, guiActiveEditor = false, guiName = "Hibernate", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleHibernation()
        {
            if (!CanHibernate) return;
            hibernating = !hibernating;
            UpdateRate();
            if (vessel != null) GameEvents.onVesselWasModified.Fire(vessel);
            SetGui();
        }

        [KSPAction("Toggle Hibernation")]
        public void HibernateAction(KSPActionParam _) => ToggleHibernation();

        // ---- IPartMassModifier: the frozen hardware mass (battery mass is RealFuels') ----
        public float GetModuleMass(float defaultMass, ModifierStagingSituation sit) => avionicsMass;
        public ModifierChangeWhen GetModuleMassChangeWhen() => ModifierChangeWhen.CONSTANTLY;

        // ---- IPartCostModifier: the frozen hardware cost (battery funds cost is RealFuels') ----
        public float GetModuleCost(float defaultCost, ModifierStagingSituation sit) => avionicsCost;
        public ModifierChangeWhen GetModuleCostChangeWhen() => ModifierChangeWhen.CONSTANTLY;

        public override string GetInfo()
        {
            return "Unified avionics core: command, guidance, electric power, science storage and flight computer.\n\n"
                 + "<b>Model</b> (chosen in the VAB, fixed at launch):\n"
                 + "• <b>Guided</b> — full 3-axis control; size the box's hardware segment for the vessel "
                 + "mass you want to steer (shown as Capacity). Going over capacity doesn't lock control, it "
                 + "costs a smoothly rising power penalty instead. Needs the guidance tech to steer; until "
                 + "then the craft flies dumb.\n"
                 + "• <b>Unguided</b> — no steering, but a fraction of the mass and almost no power; "
                 + "from improved avionics it permits axial-thrust spin-stabilization.\n\n"
                 + "<b>Shielded</b> (Guided only, unlocked later): its own heavier/pricier hardware ladder, "
                 + "in exchange for a deeper hibernation depth available from its own first tier — "
                 + "Unshielded only reaches a shallow hibernate late, Shielded reaches deep from the start.\n\n"
                 + "A crewed pod or a separate probe core always restores full control regardless of model.\n\n"
                 + "<b>Power draw</b> runs live off the vehicle's <i>dry</i> mass, drawn through the vessel's "
                 + "normal electric charge system — an empty battery loses control the same way it would for "
                 + "any uncrewed probe. Draw auto-drops during timewarp for any hibernate-capable core, and "
                 + "<b>Hibernate</b> (flight-only) does the same on demand.\n\n"
                 + "<b>Battery/hardware/empty split</b>: drag the bar in the Avionics Core PAW section to "
                 + "divide the box's volume between battery and hardware; the rest is legitimately unused.\n\n"
                 + "<b>Set to Debris</b>: mark a stage's avionics so, once it separates, an otherwise-idle "
                 + "spent stage doesn't clutter the tracking station.\n\n"
                 + "<b>Science storage</b> is unlocked from Basic Avionics on; earlier tiers are pure "
                 + "sequencers with no onboard data storage.";
        }

        #region Kerbalism (duck-typed; invoked by reflection only if Kerbalism is present)
        public string PlannerUpdate(List<KeyValuePair<string, double>> resources, CelestialBody _, Dictionary<string, double> environment)
        {
            resources.Add(_ecConsumption);
            return "avionics";
        }

        public string ResourceUpdate(Dictionary<string, double> availableResources, List<KeyValuePair<string, double>> resourceChangeRequest)
        {
            resourceChangeRequest.Add(_ecConsumption);
            return "avionics";
        }

        public static string BackgroundUpdate(Vessel v,
            ProtoPartSnapshot partSnapshot, ProtoPartModuleSnapshot moduleSnapshot,
            PartModule protoPartModule, Part protoPart,
            Dictionary<string, double> availableResources, List<KeyValuePair<string, double>> resourceChangeRequest,
            double elapsed_s)
        {
            if (availableResources.ContainsKey(EcName))
            {
                float cw = 0f;
                if (moduleSnapshot.moduleValues.TryGetValue("currentWatts", ref cw) && cw > 0f)
                    resourceChangeRequest.Add(new KeyValuePair<string, double>(EcName, -cw / 1000.0));
            }
            return "avionics";
        }
        #endregion
    }
}
