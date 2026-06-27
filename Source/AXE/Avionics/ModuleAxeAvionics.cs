using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RP-AXE unified avionics core. Total avionics mass is the sum of TWO curves, calibrated to RP-1's
    /// Near-Earth procedural avionics:
    ///   * a HARDWARE curve — RP-1's mass polynomial evaluated on the per-craft load (the same whole-vessel
    ///     load that sets the EC draw), so it reproduces RP-1's hardware mass at every craft size
    ///     (172 kg @1 t, ~367 @ V-2, 822 @100 t…). Computed in the editor and FROZEN at launch (persisted),
    ///     like RP-1's static hardware mass — never recomputed in flight.
    ///   * a BATTERY curve — the RealFuels EC tank the player sizes for endurance (the single slider). The
    ///     hardware reserves its own footprint out of the part's procedural volume (RP-1-style), the rest is EC.
    ///
    /// The EC DRAW runs LIVE off the current vessel mass (falls as fuel burns / stages drop) and gets cheaper
    /// as the avionics tech line is researched. There is NO controllable-mass gate: a bigger rocket just draws
    /// more power and weighs a bit more, never "insufficient avionics, cannot fly this". Control is a separate,
    /// tech-unlocked + toggleable GUIDANCE capability (see <see cref="AxeAvionicsController"/> /
    /// <see cref="AxeControlLockerUtils"/>) that ALSO needs power: run the battery flat and the craft goes dumb
    /// (throttle + staging only) until power returns.
    ///
    /// The per-tier mass/power ladder lives in config as TIER nodes (single source of truth, mirrored by
    /// tools/avionics_compare.py); a hardcoded copy is kept as a fallback.
    /// </summary>
    public class ModuleAxeAvionics : PartModule, IPartMassModifier
    {
        const string PAWGroup = "AxeAvionics";
        const string GroupDisplay = "Avionics Core";
        const string EcName = "ElectricCharge";

        // ---- tech that unlocks attitude guidance ----
        [KSPField] public string guidanceTech = "postWarAvionics";

        // ---- EC draw curve (RP-1 Near-Earth): watts = (vesselMass^exp + const) * powerFactor(tier) ----
        [KSPField] public float powerExponent = 0.57853f;
        [KSPField] public float powerConstant = 1.035f;
        [KSPField] public float idleFactor = 0.1f;   // draw multiplier while guidance is inactive

        // ---- hardware MASS curve (RP-1 Near-Earth): tons = (load^exp + const) * massFactor(tier) / 1000 ----
        [KSPField] public float massExponent = 0.46172f;
        [KSPField] public float massConstant = 0.96f;

        // ---- volume emulation: hardware reserves part volume (mass/density), the rest is EC battery ----
        [KSPField] public float avionicsDensity = 0.5f;   // t/m^3

        // ---- "is powered" runtime gate (flight only): go dumb when the EC reserve runs out, with hysteresis ----
        [KSPField] public float poweredCutoffSeconds = 2f;    // brown-out below this many seconds of reserve
        [KSPField] public float poweredRecoverSeconds = 10f;  // re-power above this many seconds of reserve

        // ---- persistent player state ----
        [KSPField(isPersistant = true)] public bool guidanceEnabled = true;

        // ---- readouts (VAB-visible) ----
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Avionics Power",
                  guiFormat = "N1", guiUnits = " W", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float currentWatts = 0f;

        // Frozen hardware mass: recomputed in the editor from the per-craft load, persisted with the craft,
        // held fixed in flight. IPartMassModifier returns this; the battery mass is RealFuels'.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Avionics Mass",
                  guiFormat = "F3", guiUnits = " t", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float avionicsMass = 0f;

        [KSPField(guiActiveEditor = true, guiName = "Endurance (guided)",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceEndurance = "";

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceStatus = "";

        // ---- runtime ----
        float _massFactor = 87.99f;   // current tier's mass factor
        float _powerFactor = 56.415f; // current tier's power factor
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

        // ---- config-driven tier ladder (RP-1 Near-Earth coeffs), with a hardcoded fallback ----
        static string[] _ladTech =
        {
            "postWarAvionics", "avionicsPrototypes", "earlyAvionics", "basicAvionics", "interplanetaryProbes",
            "improvedAvionics", "matureAvionics", "largeScaleAvionics", "advancedAvionics", "nextGenAvionics",
            "longTermAvionics", "internationalAvionics", "modernAvionics"
        };
        static float[] _ladMass =
        { 87.99f, 69.712f, 59.13f, 50.153f, 42.54f, 36.082f, 30.605f, 25.959f, 22.018f, 18.675f, 15.84f, 13.436f, 11.396f };
        static float[] _ladPower =
        { 56.415f, 47.851f, 40.587f, 34.426f, 29.2f, 24.767f, 21.007f, 17.818f, 15.113f, 12.819f, 10.873f, 9.222f, 7.822f };

        public bool GuidanceUnlocked => Researched(guidanceTech);
        // Guidance needs the tech, the toggle ON, and POWER. Out of EC in flight => dumb until repowered.
        public bool GuidanceActive => GuidanceUnlocked && guidanceEnabled && IsPowered;
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
            foreach (ConfigNode t in tiers)
            {
                string tn = t.GetValue("tech");
                if (string.IsNullOrEmpty(tn)) continue;
                float mf = 0f, pf = 0f;
                t.TryGetValue("massFactor", ref mf);
                t.TryGetValue("powerFactor", ref pf);
                if (mf <= 0f || pf <= 0f) continue;
                tech.Add(tn); mass.Add(mf); power.Add(pf);
            }
            if (tech.Count == 0) return;
            _ladTech = tech.ToArray();
            _ladMass = mass.ToArray();
            _ladPower = power.ToArray();
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
            }
        }

        float ReadProceduralVolume()
        {
            if (_procPM == null || _procVolumeProp == null) return _cachedVolume;
            try { return Convert.ToSingle(_procVolumeProp.GetValue(_procPM, null)); }
            catch { return _cachedVolume; }
        }

        // Pick the best researched tier (lowest mass factor; tier 0 if none researched) and apply its
        // mass + power factors. SAS is no longer touched here — it is a flat level 3 set in config.
        void ApplyTier()
        {
            int best = 0;
            for (int i = 1; i < _ladTech.Length; i++)
                if (Researched(_ladTech[i]) && _ladMass[i] < _ladMass[best]) best = i;
            _massFactor = _ladMass[best];
            _powerFactor = _ladPower[best];
        }

        // Editor only: the frozen hardware mass = RP-1's mass polynomial on the per-craft load. Load excludes
        // this part's own hardware modifier so it can't feed back on itself; it's ≈ whole-vessel for any real
        // craft, and slightly under RP-1 (which rates controllableMass with margin) — erring easier.
        void UpdateHardwareMass()
        {
            float load = VesselMassTons() - avionicsMass;
            if (load < 0f) load = 0f;
            avionicsMass = Poly(load, massExponent, massConstant, _massFactor) / 1000f;
        }

        float AvionicsVolume() => avionicsDensity > 0f ? avionicsMass / avionicsDensity : 0f;  // m^3

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

        static float Poly(float value, float exponent, float constant, float factor)
            => (Mathf.Pow(value, exponent) + constant) * factor;

        // Full-guidance EC draw (watts) for the current vehicle, lighter per researched tier.
        float ComputeActiveWatts()
        {
            float m = VesselMassTons();
            if (m <= 0f) return 0f;
            return Poly(m, powerExponent, powerConstant, _powerFactor);
        }

        float ComputeWatts() => ComputeActiveWatts() * (GuidanceActive ? 1f : idleFactor);

        void UpdateRate()
        {
            currentWatts = ComputeWatts();
            _ecConsumption = new KeyValuePair<string, double>(EcName, -currentWatts / 1000.0);
            UpdateEndurance();
            SetGui();
        }

        // How long full-guidance draw can run on a full battery — the key VAB sizing readout.
        void UpdateEndurance()
        {
            float w = ComputeActiveWatts();
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
            bool unlocked = GuidanceUnlocked;
            Events[nameof(ToggleGuidance)].guiActive = unlocked;
            Events[nameof(ToggleGuidance)].guiActiveEditor = unlocked;
            Events[nameof(ToggleGuidance)].guiName = guidanceEnabled ? "Disable Guidance" : "Enable Guidance";
            guidanceStatus = !unlocked ? "locked (research required)"
                           : !guidanceEnabled ? "off (dumb — low power)"
                           : !IsPowered ? "dumb — no power"
                           : "active";
        }

        [KSPEvent(guiActive = true, guiActiveEditor = true, guiName = "Disable Guidance", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleGuidance()
        {
            guidanceEnabled = !guidanceEnabled;
            UpdateRate();
            if (HighLogic.LoadedSceneIsEditor)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
            else if (vessel != null)
                GameEvents.onVesselWasModified.Fire(vessel); // re-run the control-lock check
        }

        // ---- IPartMassModifier: the frozen hardware mass (battery mass is RealFuels') ----
        public float GetModuleMass(float defaultMass, ModifierStagingSituation sit) => avionicsMass;
        public ModifierChangeWhen GetModuleMassChangeWhen() => ModifierChangeWhen.CONSTANTLY;

        public override string GetInfo()
        {
            return "Unified avionics core: command, guidance, electric power, science storage and flight computer.\n\n"
                 + "<b>Guidance</b> unlocks with avionics tech; until then uncrewed craft fly dumb (throttle + staging "
                 + "only, no steering). A crewed pod or a separate probe core always restores control. Guidance also "
                 + "needs power — run the battery flat and the craft goes dumb until it recharges.\n\n"
                 + "<b>Hardware mass</b> scales with the vehicle it flies and drops as you research better avionics, "
                 + "matching RP-1; it is set in the VAB and fixed at launch. <b>Power draw</b> scales the same way "
                 + "but runs live, falling as you burn fuel and stage. No mass gate — a bigger rocket just costs more, "
                 + "never lost control.\n\n"
                 + "<b>Battery</b>: the hardware reserves part of the procedural volume; size the rest for your "
                 + "mission's endurance and choose the battery chemistry in the tank menu as you unlock better cells.";
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
