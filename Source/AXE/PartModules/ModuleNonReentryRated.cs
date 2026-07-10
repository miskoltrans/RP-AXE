using System;
using System.Collections.Generic;
using ModularFI;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Marks a part as NOT rated for atmospheric reentry: a ModularFlightIntegrator pre-thermo hook
    /// floors the part's convective multipliers at 0.75 so it can't hide in another part's drag shadow
    /// and instead takes full reentry heating — i.e. it burns up. Ported verbatim from RP-1
    /// (RP0ThermoChanger -> AxeThermoChanger, RP0Debug -> Debug). Depends only on ModularFI, which the
    /// RO stack ships. Makes AXE's crewed test-flight contract check "no parts not rated for reentry"
    /// (NONE { partModule = ModuleNonReentryRated }) actually enforce something; class name is kept so
    /// those PartValidation checks resolve.
    /// </summary>
    public class ModuleNonReentryRated : PartModule
    {
        public override void OnStart(StartState state)
        {
            if (HighLogic.LoadedSceneIsFlight)
                AxeThermoChanger.Instance?.RegisterPart(part);
        }

        public override string GetInfo() => "Part is not rated for reentry!";

        protected void OnDestroy()
        {
            AxeThermoChanger.Instance?.UnregisterPart(part);
        }
    }

    [KSPAddon(KSPAddon.Startup.FlightAndKSC, false)]
    public class AxeThermoChanger : MonoBehaviour
    {
        private static bool _isRegisteredWithMFI = false;
        private static readonly List<Part> _registeredNonReentryParts = new List<Part>();

        public static AxeThermoChanger Instance { get; private set; } = null;

        public void Awake()
        {
            if (Instance != null)
                Destroy(Instance);
            Instance = this;
        }

        public void Start()
        {
            if (!_isRegisteredWithMFI)
            {
                Debug.Log("[AXE] Registering non-reentry-rated thermo override with ModularFlightIntegrator");
                ModularFlightIntegrator.RegisterUpdateThermodynamicsPre(UpdateThermodynamicsPre);
                _isRegisteredWithMFI = true;
            }
        }

        public void OnDestroy()
        {
            _registeredNonReentryParts.Clear();
        }

        public static void UpdateThermodynamicsPre(ModularFlightIntegrator fi)
        {
            foreach (Part part in _registeredNonReentryParts)
            {
                if (part.vessel != fi.Vessel) continue;

                PartThermalData ptd = part.ptd;
                ptd.convectionTempMultiplier = Math.Max(ptd.convectionTempMultiplier, 0.75d);
                ptd.convectionCoeffMultiplier = Math.Max(ptd.convectionCoeffMultiplier, 0.75d);
                ptd.convectionAreaMultiplier = Math.Max(ptd.convectionAreaMultiplier, 0.75d);

                ptd.postShockExtTemp = UtilMath.LerpUnclamped(part.vessel.atmosphericTemperature, part.vessel.externalTemperature, ptd.convectionTempMultiplier);
                ptd.finalCoeff = part.vessel.convectiveCoefficient * ptd.convectionArea * 0.001d * part.heatConvectiveConstant * ptd.convectionCoeffMultiplier;
            }
        }

        public void RegisterPart(Part part) => _registeredNonReentryParts.Add(part);

        public void UnregisterPart(Part part) => _registeredNonReentryParts.Remove(part);
    }
}
