using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RP-AXE unified avionics core. A single VAB-chosen MODEL (the guided/unguided toggle) selects between two
    /// RP-1 hardware curves, frozen at launch:
    ///   * NEAR-EARTH (guided) — RP-1's Near-Earth mass polynomial on the per-craft load (vessel-scaled): full
    ///     3-axis control, heavy, reproducing RP-1's hardware mass at every size (172 kg @1 t, ~367 @ V-2…).
    ///   * SCIENCE-CORE (unguided) — RP-1's Science-Core flat per-tier mass (scMassFactor/1000 t, size-independent):
    ///     no steering (axial-thrust spin-stabilization from improvedAvionics up), a fraction of the mass + power.
    /// Plus a BATTERY curve — the RealFuels EC tank the player sizes; the hardware reserves its own footprint out
    /// of the procedural volume (RP-1-style), the rest is EC. The hardware mass AND COST are computed in the
    /// editor and FROZEN at launch (persisted), so the model cannot change in flight. Cost follows the same
    /// polynomial/flat split as mass (RP-1's hardware-efficiency curve — a hump, not monotonic, since early
    /// sophistication costs more before mass-production brings it back down).
    ///
    /// The EC DRAW runs LIVE off the vehicle's DRY mass (steady as fuel burns, steps down as stages drop) and gets
    /// cheaper per researched tier. There is NO controllable-mass and NO distance gate — a bigger/farther rocket
    /// just draws more power and weighs a bit more (range belongs to comms). Control is gated by guidance/axial
    /// being active (see <see cref="AxeAvionicsController"/> / <see cref="AxeControlLockerUtils"/>), which needs
    /// power: run the battery flat, or HIBERNATE the core (deep sleep, in flight), and the craft goes dumb
    /// (throttle + staging only) until power returns / it is woken.
    ///
    /// Science storage (ModuleScienceContainer) is tier-gated like RP-1 (on from basicAvionics, both models) —
    /// the seed part carries the module statically; this checks it off at flight start if the as-built tier
    /// doesn't have it yet (matches RP-1's own Start()-only gating).
    ///
    /// kOS integration (disk space / EC-per-instruction / cost / mass, all per tier) is reflected onto a
    /// kOSProcessor module if one is present on the part — same duck-typed pattern as the RealFuels/ProceduralPart
    /// bridge below. kOS isn't currently an AXE dependency, so today this is a no-op; it activates automatically
    /// if kOS is ever added, instead of the flat non-scaling disk space the old RP-1 kOS patch would otherwise give.
    ///
    /// The per-tier ladders (mass/power/cost, Near-Earth + Science-Core, plus kOS + science-container gating)
    /// live in config as TIER nodes (single source of truth, mirrored by tools/avionics_compare.py); a hardcoded
    /// copy of the required mass/power fields is kept as a fallback.
    /// </summary>
    public class ModuleAxeAvionics : PartModule, IPartMassModifier, IPartCostModifier
    {
        const string PAWGroup = "AxeAvionics";
        const string GroupDisplay = "Avionics Core";
        const string EcName = "ElectricCharge";

        // ---- tech that unlocks attitude guidance ----
        [KSPField] public string guidanceTech = "postWarAvionics";

        // ---- EC draw curve (RP-1 Near-Earth): watts = (vesselMass^exp + const) * powerFactor(tier) ----
        [KSPField] public float powerExponent = 0.57853f;
        [KSPField] public float powerConstant = 1.035f;
        [KSPField] public float idleFactor = 0.1f;          // Near-Earth draw multiplier while guidance is inactive (dumb)
        [KSPField] public float hibernationFactor = 0.05f;  // deep-sleep (Hibernate toggle) draw multiplier, RP-1 deep-space depth

        // ---- hardware MASS curve (RP-1 Near-Earth): tons = (load^exp + const) * massFactor(tier) / 1000 ----
        [KSPField] public float massExponent = 0.46172f;
        [KSPField] public float massConstant = 0.96f;

        // ---- hardware COST curve (RP-1 Near-Earth): funds = (load^exp + const) * costFactor(tier), no /1000 ----
        [KSPField] public float costExponent = 0.46172f;
        [KSPField] public float costConstant = 3.034f;

        // ---- volume emulation: hardware reserves part volume (mass/density), the rest is EC battery ----
        [KSPField] public float avionicsDensity = 0.5f;   // t/m^3

        // ---- "is powered" runtime gate (flight only): go dumb when the EC reserve runs out, with hysteresis ----
        [KSPField] public float poweredCutoffSeconds = 2f;    // brown-out below this many seconds of reserve
        [KSPField] public float poweredRecoverSeconds = 10f;  // re-power above this many seconds of reserve

        // ---- persistent player state ----
        // The as-built avionics MODEL, chosen in the VAB and frozen at launch:
        //   true  = Near-Earth  (guided — full 3-axis control, heavy vessel-scaled hardware)
        //   false = Science-Core (unguided — light flat-mass sequencer, axial thrust only at high tiers)
        [KSPField(isPersistant = true)] public bool guidanceEnabled = true;
        // Flight-only deep sleep: cuts EC draw to hibernationFactor and suspends control until woken.
        [KSPField(isPersistant = true)] public bool hibernating = false;

        // ---- readouts (VAB-visible) ----
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Avionics Power",
                  guiFormat = "N1", guiUnits = " W", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float currentWatts = 0f;

        // Frozen hardware mass: recomputed in the editor from the per-craft load, persisted with the craft,
        // held fixed in flight. IPartMassModifier returns this; the battery mass is RealFuels'.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Avionics Mass",
                  guiFormat = "F3", guiUnits = " t", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float avionicsMass = 0f;

        // Frozen hardware cost (funds): same load basis + freeze-at-launch as avionicsMass. RP-1's hump-shaped
        // costFactor ladder (peaks ~matureAvionics) — a distinct hardware-efficiency signal from the monotonic
        // mass/power curves. GetModuleCost returns this; the battery's funds cost is RealFuels'.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Avionics Cost",
                  guiFormat = "F0", guiUnits = " f", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float avionicsCost = 0f;

        // VAB sizing readout: full-battery endurance at operating draw (editor-only — in flight it would read
        // as total, not remaining, which misleads).
        [KSPField(guiActiveEditor = true, guiName = "Endurance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceEndurance = "";

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceStatus = "";

        // ---- runtime ----
        float _massFactor = 87.99f;   // current tier's Near-Earth mass factor
        float _powerFactor = 56.415f; // current tier's Near-Earth power factor
        float _costFactor = 48.12f;   // current tier's Near-Earth cost factor
        float _scMassFactor = 33f;    // current tier's Science-Core flat mass factor (kg)
        float _scPowerFactor = 50f;   // current tier's Science-Core flat power (W)
        float _scCostFactor = 6f;     // current tier's Science-Core flat cost factor (funds)
        float _scDensity = 2.4f;      // current tier's Science-Core hardware density (t/m^3)
        bool _scAllowAxial = false;   // current tier: Science-Core permits axial-thrust control
        bool _hasScienceContainer = false; // current tier: RP-1 gates science storage on from basicAvionics
        // current tier's kOS ladder (applied to a kOSProcessor module if present; no-op otherwise)
        float _kosDiskSpace = 500f;
        float _kosSpaceCostFactor = 0.1f;
        float _kosSpaceMassFactor = 0.0001f;
        float _kosEcPerInstruction = 0.000001f;
        bool _powered = true;
        KeyValuePair<string, double> _ecConsumption = new KeyValuePair<string, double>(EcName, 0);
        ModuleResource _commandEC;
        float _nextFlightRecalc;

        // RealFuels / ProceduralPart bridge (reflected — AXE.dll doesn't reference RealFuels, same as the
        // MechJeb/Kerbalism reflection elsewhere). Used to reserve the hardware footprint from the EC tank.
        PartModule _rfPM;
        MethodInfo _rfCalcMass;
        PartModule _procPM;
        PropertyInfo _procVolumeProp;    // ProceduralPart.Volume (m^3)
        FieldInfo _procMinVolField;      // ProceduralPart.volumeMin — floor so the box always fits the hardware
        PropertyInfo _procShapeProp;     // ProceduralPart.CurrentShape
        MethodInfo _procSeekVolume;      // ProceduralPart.SeekVolume — auto-grow to fit
        float _cachedVolume = -1f;       // m^3 — the procedural part's total volume
        float _lastAppliedMass = -1f;
        float _lastAppliedVolume = -1f;

        // kOS bridge (reflected — AXE.dll doesn't reference kOS, same duck-typed pattern as RealFuels above).
        // Not currently an AXE dependency, so ResolveKosBridge finds nothing and ApplyKosTier is a no-op; wired
        // so per-tier disk/power/cost/mass scaling activates automatically if kOS is ever added, instead of the
        // flat non-scaling disk space the RP-1 kOS patch would otherwise give now that ModuleProceduralAvionics
        // (which drove that scaling in RP-1) is stripped.
        PartModule _kosPM;
        FieldInfo _kosDiskSpaceField;         // int — current disk space (raised to the new floor, never lowered)
        FieldInfo _kosBaseDiskSpaceField;     // int — floor of the VAB slider
        FieldInfo _kosDiskSpaceCostFactorField; // float
        FieldInfo _kosDiskSpaceMassFactorField; // float
        FieldInfo _kosEcPerInstructionField;    // float

        // ---- config-driven tier ladder (RP-1 Near-Earth coeffs), with a hardcoded fallback ----
        // Tier 0 ("start") is the unconditional floor — no tech required, ApplyTier always starts there. Its
        // NE numbers equal postWarAvionics' (RP-1 Near-Earth has no rung below start); its SC numbers are RP-1
        // Science-Core's own heavier start techLevel (48 kg/100 W/density 3.35), one rung below RP-1 SC's
        // postWarAvionics — without it, AXE's earliest Science-Core was lighter than RP-1's actual starting one.
        static string[] _ladTech =
        {
            "start", "postWarAvionics", "avionicsPrototypes", "earlyAvionics", "basicAvionics",
            "interplanetaryProbes", "improvedAvionics", "matureAvionics", "largeScaleAvionics",
            "advancedAvionics", "nextGenAvionics", "longTermAvionics", "internationalAvionics", "modernAvionics"
        };
        static float[] _ladMass =
        { 87.99f, 87.99f, 69.712f, 59.13f, 50.153f, 42.54f, 36.082f, 30.605f, 25.959f, 22.018f, 18.675f, 15.84f, 13.436f, 11.396f };
        static float[] _ladPower =
        { 56.415f, 56.415f, 47.851f, 40.587f, 34.426f, 29.2f, 24.767f, 21.007f, 17.818f, 15.113f, 12.819f, 10.873f, 9.222f, 7.822f };
        // Near-Earth cost ladder (RP-1's hardware-efficiency hump, funds): peaks at matureAvionics.
        static float[] _ladCost =
        { 48.12f, 48.12f, 51.56f, 54.13f, 56.84f, 59.68f, 62.67f, 65.8f, 58.85f, 47.08f, 37.67f, 30.13f, 24.11f, 19.29f };
        // Science-Core ladder (RP-1 Science-Core coeffs): flat mass = scMass/1000 t, flat draw = scPower/1000 kW,
        // flat cost = scCost funds, hardware density scDensity, and axial-thrust control allowed from
        // improvedAvionics up. Index-aligned with _ladTech.
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
        // RP-1 gates ModuleScienceContainer on from basicAvionics — same tier for both models.
        static bool[] _ladHasSci =
        { false, false, false, false, true, true, true, true, true, true, true, true, true, true };
        // kOS per-tier ladder (RP-1 Near-Earth's kOS numbers; shared by both models — see class remarks).
        static float[] _ladKosDisk =
        { 500f, 500f, 500f, 500f, 500f, 5120f, 10240f, 20480f, 51200f, 102400f, 204800f, 307200f, 409600f, 512000f };
        static float[] _ladKosCostFactor =
        { 0.1f, 0.1f, 0.1f, 0.1f, 0.1f, 0.01f, 0.005f, 0.0025f, 0.001f, 0.0005f, 0.00025f, 0.0001f, 0.0001f, 0.0001f };
        static float[] _ladKosMassFactor =
        { 0.0001f, 0.0001f, 0.0001f, 0.0001f, 0.0001f, 0.0000005f, 0.0000002f, 0.0000001f, 0.00000005f, 0.000000005f, 0.000000002f, 0.000000001f, 0.0000000005f, 0.0000000002f };
        static float[] _ladKosEcPerInstr =
        { 0.000001f, 0.000001f, 0.000004f, 0.000002f, 0.000001f, 0.0000004f, 0.0000002f, 0.0000001f, 0.00000008f, 0.00000004f, 0.00000001f, 0.00000001f, 0.00000001f, 0.00000001f };

        public bool GuidanceUnlocked => Researched(guidanceTech);
        // Near-Earth full 3-axis guidance: needs the model (guidanceEnabled), the tech, POWER, and not hibernating.
        // Out of EC in flight or asleep => dumb until repowered/woken.
        public bool GuidanceActive => GuidanceUnlocked && guidanceEnabled && IsPowered && !hibernating;
        // Science-Core model (the "unguided" half of the VAB toggle).
        public bool ScienceCoreMode => !guidanceEnabled;
        // Science-Core axial-thrust control (spin-stabilized stages) at improvedAvionics+; still needs power + awake.
        public bool AxialActive => ScienceCoreMode && _scAllowAxial && IsPowered && !hibernating;
        // Hardware footprint density for the current model (NE fixed 0.5; SC varies by tier).
        float EffectiveDensity => guidanceEnabled ? avionicsDensity : (_scDensity > 0f ? _scDensity : avionicsDensity);
        public string GuidanceTech => guidanceTech;

        bool IsPowered
        {
            get
            {
                if (!HighLogic.LoadedSceneIsFlight) return true;     // never gate in the editor
                if (CheatOptions.InfiniteElectricity) return true;
                return _powered;
            }
        }

        static bool Researched(string tech)
        {
            if (string.IsNullOrEmpty(tech)) return true;
            if (HighLogic.CurrentGame == null || HighLogic.CurrentGame.Mode == Game.Modes.SANDBOX) return true;
            return ResearchAndDevelopment.GetTechnologyState(tech) == RDTech.State.Available;
        }

        // Parse the per-tier ladder from config TIER nodes (single source of truth). Craft-instance loads carry
        // no TIER children, so the prefab-parsed values (or the hardcoded fallback) stay in force.
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

                // Cost/kOS/science-container are optional per tier (default to 0/false, not tier-dropping).
                float cf = 0f, scc = 0f, kd = 0f, kcf = 0f, kmf = 0f, kec = 0f;
                bool hsc = false;
                t.TryGetValue("costFactor", ref cf);
                t.TryGetValue("scCostFactor", ref scc);
                t.TryGetValue("hasScienceContainer", ref hsc);
                t.TryGetValue("kosDiskSpace", ref kd);
                t.TryGetValue("kosSpaceCostFactor", ref kcf);
                t.TryGetValue("kosSpaceMassFactor", ref kmf);
                t.TryGetValue("kosECPerInstruction", ref kec);
                cost.Add(cf); scCost.Add(scc); hasSci.Add(hsc);
                kosDisk.Add(kd); kosCostFactor.Add(kcf); kosMassFactor.Add(kmf); kosEcPerInstr.Add(kec);
            }
            if (tech.Count == 0) return; // no complete tiers ⇒ keep the hardcoded fallback ladders
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
        }

        public override void OnStartFinished(StartState state)
        {
            _commandEC = FindCommandEC();
            if (_commandEC != null) _commandEC.rate = 0; // hand EC draw to this module / Kerbalism (no double count)

            ResolveTankBridge();
            ApplyTier();

            if (HighLogic.LoadedSceneIsEditor)
            {
                _cachedVolume = ReadProceduralVolume();
                UpdateHardwareMass();             // editor: compute the frozen hardware mass from current load
                SetPartVolumeLimit();             // grow the box to fit the hardware if needed
                ApplyVolumeReservation(true);     // reserve the hardware footprint out of the EC tank
                GameEvents.onEditorShipModified.Add(OnShipModified);
            }
            else
            {
                // Flight: hardware mass is frozen (persisted). Legacy craft (mass 0) get one fallback compute.
                if (avionicsMass <= 0f) UpdateHardwareMass();
                GameEvents.onStageActivate.Add(OnStage);

                // Science storage is tier-gated (RP-1: on from basicAvionics). Checked once at flight start,
                // same as RP-1's own Start()-only gating — a mid-flight tech unlock doesn't retroactively add
                // it back to an already-flying craft (matches RP-1; the module is always present in the editor).
                if (!_hasScienceContainer)
                {
                    ModuleScienceContainer sci = part.FindModuleImplementing<ModuleScienceContainer>();
                    if (sci != null) part.RemoveModule(sci);
                }
            }

            UpdateRate();
            SetGui();
        }

        void OnDestroy()
        {
            GameEvents.onEditorShipModified.Remove(OnShipModified);
            GameEvents.onStageActivate.Remove(OnStage);
        }

        // Editor: hardware mass + draw + the EC-volume reservation track the build.
        void OnShipModified(ShipConstruct _)
        {
            if (!HighLogic.LoadedSceneIsEditor) return;
            ApplyTier();
            _cachedVolume = ReadProceduralVolume();
            UpdateHardwareMass();
            SetPartVolumeLimit();
            ApplyVolumeReservation(false);
            UpdateRate();
        }

        void OnStage(int _) => UpdateRate();

        // Flight: recompute the powered state + EC DRAW ~1 Hz so they track recharge / fuel burn / staging.
        // The hardware mass is frozen and never changes in flight.
        void Update()
        {
            if (!HighLogic.LoadedSceneIsFlight) return;
            if (Time.time < _nextFlightRecalc) return;
            _nextFlightRecalc = Time.time + 1f;
            UpdatePowered();
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

        // Resolve RealFuels' ModuleFuelTanks + the ProceduralPart volume property by reflection (RealFuels and
        // ProceduralParts aren't referenced by AXE.dll). Missing either ⇒ skip volume reservation gracefully.
        // Also resolves a kOSProcessor module, if present, for the kOS tier bridge below.
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
                    Type pt = m.GetType();
                    _procVolumeProp = pt.GetProperty("Volume", F);
                    _procMinVolField = pt.GetField("volumeMin", F);
                    _procShapeProp = pt.GetProperty("CurrentShape", F);
                    _procSeekVolume = pt.GetMethod("SeekVolume", BindingFlags.Public | BindingFlags.Instance);
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
        // Raises the disk-space floor (baseDiskSpace) and the current disk space if it's now below that floor,
        // but never lowers disk space the player already sized up — same "floor, don't clobber" rule as the
        // procedural-part volume reservation.
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

        // Pick the best researched tier (lowest-or-tied NE mass factor; tier 0 — the unconditional floor — if
        // none researched) and apply its mass + power factors. <= (not <) so a researched tier that ties the
        // floor on NE mass (tier 0 "start" vs tier 1 postWarAvionics currently tie: RP-1 has no NE rung below
        // start) still advances — otherwise research could never step Science-Core down off the tied floor.
        // SAS is no longer touched here — it is a flat level 3 set in config.
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
            ApplyKosTier();
        }

        // Editor only: the frozen hardware mass.
        //   Near-Earth  = RP-1's mass polynomial on the per-craft load (vessel-scaled). Load excludes this part's
        //                 own modifier so it can't feed back on itself; ≈ whole-vessel for any real craft.
        //   Science-Core = RP-1's flat per-tier mass (scMassFactor/1000 t), independent of vessel size.
        void UpdateHardwareMass()
        {
            if (guidanceEnabled)
            {
                float load = VesselMassTons() - avionicsMass;
                if (load < 0f) load = 0f;
                avionicsMass = Poly(load, massExponent, massConstant, _massFactor) / 1000f;
                avionicsCost = Poly(load, costExponent, costConstant, _costFactor);
            }
            else
            {
                avionicsMass = _scMassFactor / 1000f;
                avionicsCost = _scCostFactor;
            }
        }

        float AvionicsVolume() => EffectiveDensity > 0f ? avionicsMass / EffectiveDensity : 0f;  // m^3

        // Editor only: keep the procedural box at least big enough to hold the hardware (RP-1-style), growing it
        // to fit when the craft (and thus the hardware) outgrows the current size. The player grows it further
        // for battery endurance. All reflection is guarded — missing ProceduralPart ⇒ skip silently.
        void SetPartVolumeLimit()
        {
            if (!HighLogic.LoadedSceneIsEditor || _procPM == null || _procMinVolField == null) return;
            float minVolume = AvionicsVolume();
            try
            {
                _procMinVolField.SetValue(_procPM, minVolume);
                object shape = _procShapeProp?.GetValue(_procPM, null);
                shape?.GetType().GetMethod("AdjustDimensionBounds",
                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy)
                    ?.Invoke(shape, Array.Empty<object>());
                if (minVolume > _cachedVolume + 1e-4f) SeekVolume(minVolume);
            }
            catch { }
        }

        void SeekVolume(float target)
        {
            if (_procSeekVolume == null) return;
            try
            {
                object[] args = _procSeekVolume.GetParameters().Length == 1
                    ? new object[] { target } : new object[] { target, 1 };
                _procSeekVolume.Invoke(_procPM, args);
                _cachedVolume = ReadProceduralVolume();
            }
            catch { }
        }

        // Editor only: reserve the hardware footprint out of the procedural part, hand the rest to the EC tank
        // (RP-1-style — send the leftover volume to RealFuels and recompute its mass). Driven from
        // onEditorShipModified, which fires AFTER RealFuels has handled a resize, so there's no event race.
        // Guarded so our own CalculateMass-triggered ship-modified can't loop.
        void ApplyVolumeReservation(bool force)
        {
            if (!HighLogic.LoadedSceneIsEditor || _rfPM == null) return;
            if (_cachedVolume <= 0f) return;
            if (!force && Mathf.Abs(avionicsMass - _lastAppliedMass) < 1e-4f
                       && Mathf.Abs(_cachedVolume - _lastAppliedVolume) < 1e-5f) return;
            _lastAppliedMass = avionicsMass;
            _lastAppliedVolume = _cachedVolume;

            float avail = _cachedVolume - AvionicsVolume();
            if (avail < 0f) avail = 0f;
            SendVolumeChangedEvent(avail);
            try { _rfCalcMass?.Invoke(_rfPM, null); } catch { }
        }

        void SendVolumeChangedEvent(double newVolume)
        {
            var data = new BaseEventDetails(BaseEventDetails.Sender.USER);
            data.Set<string>("volName", "Tankage");
            data.Set("newTotalVolume", newVolume);     // m^3 — RealFuels' ModuleFuelTanks listens for this
            part.SendEvent("OnPartVolumeChanged", data, 0);
        }

        // Flight only: latch _powered from the measured EC reserve, with hysteresis so it doesn't flap at the
        // threshold (and so a solar trickle can re-power a dumb craft, whose idle draw is low).
        void UpdatePowered()
        {
            if (!HighLogic.LoadedSceneIsFlight || vessel == null) { _powered = true; return; }
            bool was = _powered;
            vessel.GetConnectedResourceTotals(PartResourceLibrary.ElectricityHashcode, out double ec, out double _);
            double perSec = currentWatts / 1000.0;
            double low = Math.Max(0.5, perSec * poweredCutoffSeconds);
            double high = Math.Max(2.0, perSec * poweredRecoverSeconds);
            if (_powered && ec <= low) _powered = false;
            else if (!_powered && ec >= high) _powered = true;
            if (_powered != was) GameEvents.onVesselWasModified.Fire(vessel); // re-run the control-lock check now
        }

        float VesselMassTons()
        {
            if (HighLogic.LoadedSceneIsEditor)
                return EditorLogic.fetch?.ship != null ? EditorLogic.fetch.ship.GetTotalMass() : 0f;
            return vessel != null ? (float)vessel.totalMass : 0f;
        }

        // Live DRY mass (tons) — vessel mass excluding propellant/resources, so EC draw is independent of fuel load
        // and steps down only when stages/parts are dropped. Sums part dry mass + module-modifier mass.
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

        // Operating EC draw (watts) for the current model, before idle/hibernation reduction:
        //   Near-Earth  scales with live DRY mass and gets lighter per researched tier;
        //   Science-Core draws a flat per-tier rate (size-independent).
        float ComputeBaseWatts()
        {
            if (!guidanceEnabled) return _scPowerFactor;  // Science-Core: flat
            float m = VesselDryMassTons();
            if (m <= 0f) return 0f;
            return Poly(m, powerExponent, powerConstant, _powerFactor);
        }

        // Actual live draw: deep sleep cuts to hibernationFactor; otherwise Science-Core stays flat, while
        // Near-Earth draws full when guiding and idleFactor when dumb (unresearched / browned-out).
        float ComputeWatts()
        {
            float b = ComputeBaseWatts();
            if (hibernating) return b * hibernationFactor;
            if (!guidanceEnabled) return b;
            return GuidanceActive ? b : b * idleFactor;
        }

        void UpdateRate()
        {
            // VAB readout shows the operating draw (what it draws awake & working) so the player can size the
            // battery; flight uses the actual gated/hibernating draw that feeds the powered check + Kerbalism.
            currentWatts = HighLogic.LoadedSceneIsEditor ? ComputeBaseWatts() : ComputeWatts();
            _ecConsumption = new KeyValuePair<string, double>(EcName, -currentWatts / 1000.0);
            UpdateEndurance();
            SetGui();
        }

        // How long the operating draw can run on a full battery — the key VAB sizing readout.
        void UpdateEndurance()
        {
            float w = ComputeBaseWatts();
            double ecMax = 0.0;
            PartResource r = part.Resources?.Get(PartResourceLibrary.ElectricityHashcode);
            if (r != null) ecMax = r.maxAmount;
            if (w <= 0f || ecMax <= 0.0) { guidanceEndurance = "—"; return; }
            guidanceEndurance = FormatDuration(ecMax / (w / 1000.0));
        }

        static string FormatDuration(double s)
        {
            if (s >= 3600.0) return $"{(int)(s / 3600)}h {(int)(s % 3600 / 60)}m";
            if (s >= 60.0) return $"{(int)(s / 60)}m {(int)(s % 60)}s";
            return $"{(int)s}s";
        }

        void SetGui()
        {
            // Model selector: VAB-only (model + mass are frozen at launch). Always available — picking Near-Earth
            // before guidance is researched just means it can't guide yet (build Science-Core for early rockets).
            BaseEvent mt = Events[nameof(ToggleGuidance)];
            mt.guiActive = false;
            mt.guiActiveEditor = true;
            mt.guiName = guidanceEnabled ? "Switch to Unguided" : "Switch to Guided";

            // Hibernation: flight-only deep sleep.
            BaseEvent hb = Events[nameof(ToggleHibernation)];
            hb.guiActive = true;
            hb.guiActiveEditor = false;
            hb.guiName = hibernating ? "Wake from Hibernation" : "Hibernate";

            guidanceStatus = hibernating ? "hibernating — low power, control suspended"
                           : ScienceCoreMode ? (_scAllowAxial ? "Unguided — axial thrust only (spin-stabilized)"
                                                              : "Unguided — no steering")
                           : !GuidanceUnlocked ? "Guided — guidance not yet researched (dumb)"
                           : !IsPowered ? "Guided — dumb (no power)"
                           : "Guided — guidance active";
        }

        // VAB-only: pick the as-built model. Firing onEditorShipModified re-runs the full editor recompute
        // (mass, volume reservation, draw); mass is then frozen at launch.
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

        // Flight: toggle deep sleep. Cuts draw to hibernationFactor and suspends control (re-run the lock check).
        [KSPEvent(guiActive = true, guiActiveEditor = false, guiName = "Hibernate", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleHibernation()
        {
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

        // ---- IPartCostModifier: the frozen hardware cost (RP-1's hardware-efficiency hump; battery funds cost is RealFuels') ----
        public float GetModuleCost(float defaultCost, ModifierStagingSituation sit) => avionicsCost;
        public ModifierChangeWhen GetModuleCostChangeWhen() => ModifierChangeWhen.CONSTANTLY;

        public override string GetInfo()
        {
            return "Unified avionics core: command, guidance, electric power, science storage and flight computer.\n\n"
                 + "<b>Model</b> (chosen in the VAB, fixed at launch):\n"
                 + "• <b>Guided</b> — full 3-axis control; hardware mass scales with the vehicle and "
                 + "drops as you research better avionics. Needs power and the guidance tech; until "
                 + "then, or if the battery runs flat, the craft flies dumb (throttle + staging only).\n"
                 + "• <b>Unguided</b> — no steering, but a fraction of the mass and almost no power; "
                 + "from improved avionics it permits axial-thrust spin-stabilization. For sounding rockets and kick "
                 + "stages.\n\n"
                 + "A crewed pod or a separate probe core always restores full control regardless of model.\n\n"
                 + "<b>Power draw</b> runs live off the vehicle's <i>dry</i> mass — steady as you burn fuel, stepping "
                 + "down as you stage. <b>Hibernate</b> (in flight) puts the core into deep sleep, cutting draw to a "
                 + "trickle and suspending control until woken. No mass gate — a bigger rocket just costs more, never "
                 + "lost control.\n\n"
                 + "<b>Battery</b>: the hardware reserves part of the procedural volume; size the rest for your "
                 + "mission's endurance and choose the battery chemistry in the tank menu as you unlock better cells.\n\n"
                 + "<b>Cost</b> follows the vehicle load like mass, but peaks mid-tree before falling — early "
                 + "sophistication costs more, before mass production brings it back down.\n\n"
                 + "<b>Science storage</b> is unlocked from Basic Avionics on; earlier tiers are pure sequencers "
                 + "with no onboard data storage.";
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
