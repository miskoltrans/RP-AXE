using UnityEngine;

namespace RPAxe.Simulation
{
    /// <summary>
    /// Fail-safe restore trigger. Lives for the whole session (Instantly + once) and listens for scene
    /// loads; whenever we arrive in the editor, space centre or tracking station AND a simulation backup
    /// exists, it swaps the real save back and clears the sim flags. Because it keys off the backup
    /// <b>file</b> rather than an in-memory flag, it recovers a sim even after a crash / alt-F4 mid-flight.
    ///
    /// Mirrors ROUtils/KCT <c>KCTEvents</c>'s scene-change restore.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Instantly, true)]
    public class AxeSimulationRestore : MonoBehaviour
    {
        private void Awake()
        {
            DontDestroyOnLoad(this);
            GameEvents.onLevelWasLoaded.Add(OnLevelWasLoaded);
        }

        private void OnDestroy()
        {
            GameEvents.onLevelWasLoaded.Remove(OnLevelWasLoaded);
        }

        private void OnLevelWasLoaded(GameScenes scene)
        {
            if (scene != GameScenes.EDITOR && scene != GameScenes.SPACECENTER && scene != GameScenes.TRACKSTATION)
                return;
            // Restore if a backup is present (normal + crash-recovery case) OR the sim flag is somehow still
            // set without one (belt-and-suspenders so we never strand the session in "sim mode").
            if (!AxeSimulationSave.BackupExists() && !AxeSimulation.IsSimulatedFlight) return;

            Debug.Log("[AXE][Sim] Non-flight scene reached mid-simulation — restoring.");
            AxeSimulation.EndSimAndRestore();
        }
    }
}
