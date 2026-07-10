using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// F7 clears all control input locks — a panic key ported verbatim from RP-1's ClearInputLocks.
    /// Especially useful in AXE because AxeAvionicsController sets a control lock ("AxeAvionicsLock")
    /// that a bug could otherwise leave stuck, stranding the player. Runs in every scene; touches
    /// nothing except the stock InputLockManager, and (unlike RP-1's ScenarioModule form) writes
    /// nothing to the save.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EveryScene, false)]
    public class AxeClearInputLocks : MonoBehaviour
    {
        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.F7))
                InputLockManager.ClearControlLocks();
        }
    }
}
