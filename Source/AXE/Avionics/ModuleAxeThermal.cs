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

        /// <summary>Radiating area, m^2. Pushed in by the avionics core.</summary>
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

        double _lastUT = -1d;
        KeyValuePair<string, double> _ec = new KeyValuePair<string, double>(EcName, 0d);

        /// <summary>Called by the avionics core when the bus configuration changes.</summary>
        public void SetBusThermal(float k, float area)
        {
            thermalK = k;
            thermalArea = area;
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

            float deficit = ModuleAxeAvionics.VesselDeficit(vessel, bodyIrFraction);
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

            float watts = 0f;
            if (haveEnv && thermalArea > 0f && thermalK > 0f)
            {
                // Planner toggle is a WORST-CASE switch, so honour it as a hard 0/1 and report the
                // STEADY-STATE load for that state -- "what does it cost if this lasts". Flight integrates
                // and will read lower whenever thermal mass is carrying the craft through a short eclipse.
                double bodyDist = body != null ? body.Radius * 1.1d : 0d;
                float deficit = ModuleAxeAvionics.ThermalDeficit(sunDist, sunlight < 0.5d ? 0d : 1d,
                                                                 body, bodyDist, bodyIrFraction);
                float t = 0f;   // fresh: steady state, not the live craft's history
                watts = ModuleAxeAvionics.StepThermal(deficit, thermalArea, thermalK,
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

            float k = 0f, area = 0f, temp = -1f, sh = 900f, tSet = 293f, tMin = 273f, irf = 0.35f;
            moduleSnapshot.moduleValues.TryGetValue("thermalK", ref k);
            moduleSnapshot.moduleValues.TryGetValue("thermalArea", ref area);
            moduleSnapshot.moduleValues.TryGetValue("busTemperature", ref temp);
            moduleSnapshot.moduleValues.TryGetValue("specificHeat", ref sh);
            moduleSnapshot.moduleValues.TryGetValue("setpointK", ref tSet);
            moduleSnapshot.moduleValues.TryGetValue("minK", ref tMin);
            moduleSnapshot.moduleValues.TryGetValue("bodyIrFraction", ref irf);
            if (k <= 0f || area <= 0f) return "heaters";

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
