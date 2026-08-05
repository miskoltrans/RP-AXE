using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Heater load for an avionics bus, reported to Kerbalism as its OWN line.
    ///
    /// WHY A SEPARATE MODULE AT ALL. Kerbalism labels a resource contribution once per PartModule:
    /// <c>ResourceSimulator</c> takes the single string returned by <c>PlannerUpdate</c> and applies it to
    /// every entry that call produced (<c>Consume(-item.Value, name)</c>). So one module can never split
    /// itself across two lines, and folding heaters into <see cref="ModuleAxeAvionics"/> meant the planner
    /// could only ever show one lumped "avionics" figure. A player sizing a deep-space probe needs to see
    /// where the watts actually went, so the heaters get their own module and their own label.
    ///
    /// OWNERSHIP. This module owns the thermal STATE (<see cref="busTemperature"/>) and does the
    /// integration; <see cref="ModuleAxeAvionics"/> owns the two inputs that depend on the bus
    /// configuration -- the insulation coefficient and the radiating area -- and pushes them in via
    /// <see cref="SetBusThermal"/> whenever they change. Keeping the state here is what lets
    /// <see cref="BackgroundUpdate"/> be self-contained: it reads its own module snapshot, steps the
    /// temperature, and writes it straight back, so an unloaded craft keeps cooling on its own.
    ///
    /// The physics, the deadband and the mass dependence all live in
    /// <see cref="ModuleAxeAvionics.StepThermal"/> -- shared deliberately so the loaded, background and
    /// planner paths cannot drift apart.
    /// </summary>
    public class ModuleAxeThermal : PartModule
    {
        const string PAWGroup = "AxeAvionics";
        const string GroupDisplay = "Avionics";
        const string EcName = "ElectricCharge";

        /// <summary>Insulation coefficient, W/m^2. Pushed in by the avionics core (eps_eff * sigma * T^4).</summary>
        [KSPField(isPersistant = true)] public float thermalK = 0f;

        /// <summary>
        /// Radiating area comes from VESSEL DRY MASS, not the avionics box (changed 2026-08-05 after
        /// checking real craft). It is the whole spacecraft that radiates, and box area was wrong by ~7x:
        /// measured across 74 cores in the dev save, real probe cores are 0.017 m^3 / 0.39 m^2 while the
        /// earlier calibration assumed 0.30 m^3 / 2.69 m^2 — so a Luna-class probe was being charged 2 W at
        /// Jupiter instead of something that matters.
        ///
        ///     A ~= 0.04 * m_dry^(2/3)     (m in kg)
        ///
        /// Checked against real spacecraft: Luna 1 at 361 kg -> 2.0 m^2 (actual sphere ~2 m^2); Voyager at
        /// 825 kg -> 3.5 m^2 (actual bus ~4 m^2).
        ///
        /// DRY mass, so the area does not shrink as tanks drain — a tank's skin stays the same size. The
        /// thermal CAPACITY below uses TOTAL mass, because propellant really does store heat.
        ///
        /// A big ascending stack gets a big area (a 300 t stack -> 34 m^2, ~2 kW at full deficit) and that
        /// is fine, because it also gets enormous heat capacity: tau ~2550 h, so a 10-minute ascent moves
        /// its temperature 0.00 K even launching at night. The integration protects ascent on its own; no
        /// special case is needed or wanted.
        /// </summary>
        [KSPField] public float areaCoefficient = 0.04f;   // m^2 per kg^(2/3)

        /// <summary>Live radiating area, m^2 — a readout, recomputed from the vessel each update.</summary>
        [KSPField(isPersistant = true)] public float thermalArea = 0f;

        [KSPField] public float specificHeat = 900f;   // J/kg.K
        [KSPField] public float setpointK = 293f;      // nominal electronics temperature
        [KSPField] public float minK = 273f;           // battery floor -- heaters defend THIS, not setpoint
        [KSPField] public float bodyIrFraction = 0.35f;

        [KSPField(isPersistant = true)] public float busTemperature = -1f;

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Thermal Load",
                  guiFormat = "N1", guiUnits = " W", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float thermalWatts = 0f;

        [KSPField(isPersistant = true, guiActive = true, guiName = "Bus Temperature",
                  guiFormat = "N0", guiUnits = " K", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float busTemperatureDisplay = 0f;

        // ---- VAB simulation: pick a body, see the heater bill before you fly it ----
        // At the home body in sunlight the live load is 0, so without this the mechanic is invisible
        // exactly where it has to be designed against. Kerbalism's planner has its own body picker and this
        // module feeds that too (PlannerUpdate), but the planner only answers "the body I am orbiting right
        // now" -- a probe is designed for where it is GOING, so the part needs its own selector.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Simulate at",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_ChooseOption(scene = UI_Scene.Editor)]
        public int simBodyIndex = 0;

        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Simulate",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "in orbit", enabledText = "in deep space", scene = UI_Scene.Editor)]
        public bool simDeepSpace = false;

        [KSPField(guiActiveEditor = true, guiName = "Heater draw (sim)", guiFormat = "N1", guiUnits = " W",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float simWatts = 0f;

        [KSPField(guiActiveEditor = true, guiName = "Radiating area", guiFormat = "N1", guiUnits = " m²",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float simArea = 0f;

        static readonly List<CelestialBody> _simBodies = new List<CelestialBody>();

        double _lastUT = -1d;
        KeyValuePair<string, double> _ec = new KeyValuePair<string, double>(EcName, 0d);

        /// <summary>Called by the avionics core when the bus configuration changes. Area is ours now.</summary>
        public void SetBusThermal(float k, float unusedBoxArea)
        {
            thermalK = k;
        }

        /// <summary>Radiating area from vessel DRY mass. See <see cref="areaCoefficient"/>.</summary>
        public static float VesselArea(Vessel v, float coeff)
        {
            if (v == null) return 0f;
            double dryTons = 0d;
            if (v.Parts != null && v.Parts.Count > 0)
                for (int i = 0; i < v.Parts.Count; i++) dryTons += v.Parts[i].mass;   // part.mass is DRY
            else if (v.protoVessel?.protoPartSnapshots != null)
                for (int i = 0; i < v.protoVessel.protoPartSnapshots.Count; i++)
                    dryTons += v.protoVessel.protoPartSnapshots[i].mass;
            if (dryTons <= 0d) return 0f;
            return coeff * Mathf.Pow((float)(dryTons * 1000d), 2f / 3f);
        }

        /// <summary>
        /// Exactly ONE thermal module per vessel charges the heater load.
        ///
        /// Now that area comes from the whole vessel rather than each avionics box, every core aboard would
        /// otherwise compute the SAME vessel area and bill it independently — and real craft carry 2-4
        /// cores (measured: Luna 1 has three, most launchers two), so the load would be overcharged
        /// severalfold. Ownership is the lowest stable id among live thermal modules on the vessel, which
        /// mirrors how avionics capacity already resolves as a vessel-wide MAX rather than a sum.
        ///
        /// Re-evaluated every update rather than cached, so staging simply hands ownership to whatever is
        /// left: if the owner departs with a spent booster, the payload's module takes over on the next
        /// tick. (The new owner inherits its own busTemperature, which was tracking the same stack anyway.)
        /// </summary>
        bool IsThermalOwner()
        {
            if (vessel?.Parts == null) return true;
            uint mine = part.flightID;
            for (int i = 0; i < vessel.Parts.Count; i++)
            {
                Part p = vessel.Parts[i];
                for (int j = 0; j < p.Modules.Count; j++)
                    if (p.Modules[j] is ModuleAxeThermal t && t.thermalK > 0f && p.flightID < mine)
                        return false;
            }
            return true;
        }

        public override void OnStart(StartState state)
        {
            base.OnStart(state);
            if (busTemperature <= 0f) busTemperature = setpointK;
        }

        void FixedUpdate()
        {
            if (!HighLogic.LoadedSceneIsFlight || vessel == null) return;
            double now = Planetarium.GetUniversalTime();
            double dt = _lastUT > 0d ? now - _lastUT : 0d;
            if (dt < 0d) dt = 0d;
            _lastUT = now;

            thermalArea = VesselArea(vessel, areaCoefficient);

            if (!IsThermalOwner())
            {
                // Someone else aboard is billing the vessel's heaters; stay silent rather than double-bill.
                thermalWatts = 0f;
                busTemperature = setpointK;
                busTemperatureDisplay = busTemperature;
                _ec = new KeyValuePair<string, double>(EcName, 0d);
                return;
            }

            float deficit = ModuleAxeAvionics.VesselDeficit(vessel, bodyIrFraction);
            // Area from DRY mass (skin does not shrink as tanks drain); capacity from TOTAL mass
            // (propellant genuinely stores heat, and it is what makes an ascending stack thermally inert).
            thermalWatts = ModuleAxeAvionics.StepThermal(deficit, thermalArea, thermalK,
                vessel.GetTotalMass() * 1000d, specificHeat, setpointK, minK, dt, ref busTemperature);
            busTemperatureDisplay = busTemperature;
            _ec = new KeyValuePair<string, double>(EcName, -thermalWatts / 1000.0);
        }

        #region Kerbalism (duck-typed; invoked by reflection only if Kerbalism is present)
        // Returning "heaters" rather than "avionics" is the entire point of this module existing.
        public string PlannerUpdate(List<KeyValuePair<string, double>> resources, CelestialBody body,
                                    Dictionary<string, double> environment)
        {
            double sunDist = 0d, sunlight = 1d;
            bool haveEnv = environment != null
                           && environment.TryGetValue("sun_dist", out sunDist) && sunDist > 0d;
            if (environment != null) environment.TryGetValue("sunlight", out sunlight);

            float area = 0f;
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
            {
                double dry = 0d;
                foreach (Part p in EditorLogic.fetch.ship.Parts) dry += p.mass;
                if (dry > 0d) area = areaCoefficient * Mathf.Pow((float)(dry * 1000d), 2f / 3f);
            }
            else area = thermalArea;
            thermalArea = area;

            float watts = 0f;
            if (haveEnv && area > 0f && thermalK > 0f)
            {
                // Planner toggle is a WORST-CASE switch, so honour it as a hard 0/1 and report the
                // STEADY-STATE load for that state -- "what does it cost if this lasts". Flight integrates
                // and will read lower whenever thermal mass is carrying the craft through a short eclipse.
                double bodyDist = body != null ? body.Radius * 1.1d : 0d;
                float deficit = ModuleAxeAvionics.ThermalDeficit(sunDist, sunlight < 0.5d ? 0d : 1d,
                                                                 body, bodyDist, bodyIrFraction);
                float t = 0f;   // fresh: steady state, not the live craft's history
                watts = ModuleAxeAvionics.StepThermal(deficit, area, thermalK,
                                                      1d, specificHeat, setpointK, minK, double.MaxValue / 4d, ref t);
            }
            resources.Add(new KeyValuePair<string, double>(EcName, -watts / 1000.0));
            return "heaters";
        }

        public string ResourceUpdate(Dictionary<string, double> availableResources,
                                     List<KeyValuePair<string, double>> resourceChangeRequest)
        {
            resourceChangeRequest.Add(_ec);
            return "heaters";
        }

        public static string BackgroundUpdate(Vessel v,
            ProtoPartSnapshot partSnapshot, ProtoPartModuleSnapshot moduleSnapshot,
            PartModule protoPartModule, Part protoPart,
            Dictionary<string, double> availableResources, List<KeyValuePair<string, double>> resourceChangeRequest,
            double elapsed_s)
        {
            if (!availableResources.ContainsKey(EcName)) return "heaters";

            float k = 0f, temp = -1f, sh = 900f, tSet = 293f, tMin = 273f, irf = 0.35f, coeff = 0.04f;
            moduleSnapshot.moduleValues.TryGetValue("thermalK", ref k);
            moduleSnapshot.moduleValues.TryGetValue("areaCoefficient", ref coeff);
            float area = VesselArea(v, coeff);

            // Same one-owner-per-vessel rule as the loaded path, or an unloaded multi-core craft would be
            // billed once per core. Cheapest stable test on a proto vessel is the lowest part flightID.
            if (partSnapshot != null && v?.protoVessel?.protoPartSnapshots != null)
                foreach (ProtoPartSnapshot ps in v.protoVessel.protoPartSnapshots)
                    if (ps.flightID < partSnapshot.flightID)
                        foreach (ProtoPartModuleSnapshot ms in ps.modules)
                            if (ms.moduleName == "ModuleAxeThermal") return "heaters";
            moduleSnapshot.moduleValues.TryGetValue("busTemperature", ref temp);
            moduleSnapshot.moduleValues.TryGetValue("specificHeat", ref sh);
            moduleSnapshot.moduleValues.TryGetValue("setpointK", ref tSet);
            moduleSnapshot.moduleValues.TryGetValue("minK", ref tMin);
            moduleSnapshot.moduleValues.TryGetValue("bodyIrFraction", ref irf);
            if (k <= 0f || area <= 0f) return "heaters";
            moduleSnapshot.moduleValues.SetValue("thermalArea", area, true);

            float w = ModuleAxeAvionics.StepThermal(ModuleAxeAvionics.VesselDeficit(v, irf), area, k,
                v != null ? v.totalMass * 1000d : 1000d, sh, tSet, tMin, elapsed_s, ref temp);

            // Write the evolved temperature back, or an unloaded craft would never actually cool.
            moduleSnapshot.moduleValues.SetValue("busTemperature", temp, true);
            moduleSnapshot.moduleValues.SetValue("thermalWatts", w, true);

            if (w > 0f) resourceChangeRequest.Add(new KeyValuePair<string, double>(EcName, -w / 1000.0));
            return "heaters";
        }
        #endregion
    }
}
