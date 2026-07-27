using System;
using UnityEngine;

namespace RPAxe.Simulation
{
    /// <summary>
    /// Session state + entry/exit orchestration for the editor simulation feature.
    ///
    /// Purpose: validate a craft in an environment you have not reached yet (does the lunar ascent stage
    /// actually make orbit?) before committing a real mission. Free, nothing persists, orbit-only
    /// placement (land yourself in-sim), 2-rung body gate (<see cref="AxeSimulationGate"/>).
    /// </summary>
    public static class AxeSimulation
    {
        /// <summary>True while a simulated flight is live (editor -> flight, static, survives the scene
        /// hop). The persistent source of truth for "restore needed" is the backup file, not this flag.</summary>
        public static bool IsSimulatedFlight;

        public static AxeSimulationParams Params;

        // Original revert difficulty flags, captured before we force them on for the sim. The save-swap
        // already restores them on disk; these also put the *live* session back (matters for reverts-off).
        private static bool _revertsSnapshot;
        private static bool _origCanLeaveToEditor, _origCanRestart, _origCanQuickLoad;

        // --- Feature flag (AXE_SIMULATION { enabled }); defaults on if no config present. ---
        private static bool? _enabled;
        public static bool FeatureEnabled
        {
            get { if (_enabled == null) LoadSettings(); return _enabled.Value; }
        }

        private static void LoadSettings()
        {
            _enabled = true;
            try
            {
                foreach (ConfigNode n in GameDatabase.Instance.GetConfigNodes("AXE_SIMULATION"))
                {
                    bool v = true;
                    if (n.TryGetValue("enabled", ref v)) _enabled = v;
                }
            }
            catch (Exception e) { Debug.LogWarning("[AXE][Sim] settings load failed, defaulting enabled: " + e.Message); }
        }

        /// <summary>Launch the current editor craft into a simulated flight. Returns false + a reason if it
        /// can't start. Must be called from Update, not OnGUI (it triggers a scene transition).</summary>
        public static bool StartSim(AxeSimulationParams p, out string err)
        {
            err = null;

            if (IsSimulatedFlight || AxeSimulationSave.BackupExists())
            {
                err = "A simulation is already in progress.";
                return false;
            }
            if (EditorLogic.fetch == null || EditorLogic.fetch.ship == null ||
                EditorLogic.fetch.ship.parts == null || EditorLogic.fetch.ship.parts.Count == 0)
            {
                err = "Nothing to simulate — the editor is empty.";
                return false;
            }
            if (p == null || p.Body == null)
            {
                err = "No target body selected.";
                return false;
            }
            if (!AxeSimulationGate.CanSimulate(p.Body))
            {
                err = "Simulating " + p.Body.bodyName + " requires " + AxeSimulationGate.RungBTitle() + ".";
                return false;
            }

            try
            {
                p.Facility = EditorDriver.editorFacility;
                Params = p;

                // Save-safety: if the backup didn't actually land on disk, abort BEFORE committing to the
                // sim. Otherwise the restore trigger (which keys off the backup file) would never fire and
                // the sim's changes would leak into the real career.
                AxeSimulationSave.MakeBackup();
                if (!AxeSimulationSave.BackupExists())
                {
                    err = "Could not write the pre-simulation backup save; aborting to protect your career.";
                    Params = null;
                    return false;
                }

                ConfigNode shipNode = EditorLogic.fetch.ship.SaveShip();
                string tempFile = $"{KSPUtil.ApplicationRootPath}saves/{HighLogic.SaveFolder}/Ships/AXE_sim_temp.craft";
                System.IO.Directory.CreateDirectory(System.IO.Path.GetDirectoryName(tempFile));
                shipNode.Save(tempFile);

                VesselCrewManifest manifest = KSP.UI.CrewAssignmentDialog.Instance != null
                    ? KSP.UI.CrewAssignmentDialog.Instance.GetManifest()
                    : null;
                if (manifest == null)
                    manifest = HighLogic.CurrentGame.CrewRoster.DefaultCrewForVessel(shipNode, null, true);

                IsSimulatedFlight = true;
                AxeSimulationSave.EnableSimLocks();
                ForceEnableReverts();

                Debug.Log($"[AXE][Sim] Starting simulation: body={p.Body.bodyName} inOrbit={p.InOrbit} " +
                          $"pe={p.Periapsis:0}m ap={p.Apoapsis:0}m inc={p.Inclination:0}deg " +
                          $"warpDays={p.WarpDays:0.#} delay={p.DelaySeconds}s");

                FlightDriver.StartWithNewLaunch(tempFile, EditorLogic.FlagURL,
                                                EditorLogic.fetch.launchSiteName, manifest);
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE][Sim] StartSim failed: " + e);
                // Undo the partial start so we don't strand a backup or forced-on reverts.
                IsSimulatedFlight = false;
                Params = null;
                AxeSimulationSave.DisableSimLocks();
                RestoreReverts();
                if (AxeSimulationSave.BackupExists()) AxeSimulationSave.Restore();
                err = "Simulation failed to start (see log).";
                return false;
            }
        }

        /// <summary>Called by <see cref="AxeSimulationRestore"/> on returning to a non-flight scene: swap
        /// the real save back and clear sim state.</summary>
        public static void EndSimAndRestore()
        {
            if (AxeSimulationSave.BackupExists())
                AxeSimulationSave.Restore();          // swaps the save back + archives the backup
            else
                AxeSimulationSave.DisableSimLocks();   // no backup to restore (stock revert already handled state)
            RestoreReverts();
            IsSimulatedFlight = false;
            Params = null;
        }

        // The sim is a sanctioned test channel even for reverts-off (immersion) careers, so the player is
        // never stranded in a simulation with no way back to the editor.
        private static void ForceEnableReverts()
        {
            var f = HighLogic.CurrentGame?.Parameters?.Flight;
            if (f == null) return;
            _origCanLeaveToEditor = f.CanLeaveToEditor;
            _origCanRestart = f.CanRestart;
            _origCanQuickLoad = f.CanQuickLoad;
            _revertsSnapshot = true;
            f.CanLeaveToEditor = true;
            f.CanRestart = true;
            f.CanQuickLoad = true;
        }

        private static void RestoreReverts()
        {
            if (!_revertsSnapshot) return;
            _revertsSnapshot = false;
            var f = HighLogic.CurrentGame?.Parameters?.Flight;
            if (f == null) return;
            f.CanLeaveToEditor = _origCanLeaveToEditor;
            f.CanRestart = _origCanRestart;
            f.CanQuickLoad = _origCanQuickLoad;
        }

        internal static string SelfTestReport()
        {
            CelestialBody home = Planetarium.fetch != null ? Planetarium.fetch.Home : null;
            CelestialBody other = null;
            foreach (CelestialBody b in FlightGlobals.Bodies)
                if (b != home) { other = b; break; }
            string homeStr = home != null ? home.bodyName + "=" + AxeSimulationGate.CanSimulate(home) : "n/a";
            string otherStr = other != null
                ? other.bodyName + "=" + AxeSimulationGate.CanSimulate(other) + " (needs " + AxeSimulationGate.RungBTitle() + ")"
                : "n/a";
            return "featureEnabled=" + FeatureEnabled + " isSim=" + IsSimulatedFlight +
                   " backupPresent=" + AxeSimulationSave.BackupExists() +
                   " gate: " + homeStr + ", " + otherStr;
        }
    }
}
