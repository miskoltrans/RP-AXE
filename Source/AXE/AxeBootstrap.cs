using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Minimal load-time sentinel so we can confirm AXE.dll is present and loading
    /// (look for the "[AXE]" prefix in KSP.log). Real systems — the program starter
    /// (AxeProgramHandler) and the ContractConfigurator type registrations — get added
    /// in Phase 3+/Phase 4+/Phase 5 (see docs/RESTART.md).
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Instantly, true)]
    public class AxeBootstrap : MonoBehaviour
    {
        private void Awake()
        {
            Debug.Log("[AXE] plugin loaded — RP-AXE minimal plugin online (v0.1.0).");
        }
    }
}
