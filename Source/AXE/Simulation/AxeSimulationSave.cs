using System;
using System.IO;
using UnityEngine;

namespace RPAxe.Simulation
{
    /// <summary>
    /// The "nothing persists" backbone. Before a simulation launches we snapshot the whole save
    /// (<see cref="MakeBackup"/>); when the player returns to a non-flight scene we swap that snapshot
    /// back over <c>persistent.sfs</c> (<see cref="Restore"/>), so no science / contract / comm-net / UT
    /// change made during the sim leaks into the real career.
    ///
    /// The <b>existence of the backup file</b> is the source of truth for "a sim is in progress" — which
    /// makes the whole thing fail-safe: an alt-F4 or crash mid-sim still self-heals on the next load into
    /// the editor / space centre / tracking station (see <see cref="AxeSimulationRestore"/>).
    ///
    /// Mirrors ROUtils/KCT <c>Utilities.MakeSimulationSave / LoadSimulationSave / DeleteSimulationSave</c>,
    /// reimplemented from the stock API.
    /// </summary>
    internal static class AxeSimulationSave
    {
        private const string BackupName = "AXE_sim_backup";
        private const string QsLock = "AXESimQuicksaveLock";
        private const string QlLock = "AXESimQuickloadLock";

        private static string SaveDir => $"{KSPUtil.ApplicationRootPath}saves/{HighLogic.SaveFolder}";
        private static string BackupPath => $"{SaveDir}/{BackupName}.sfs";
        private static string PersistentPath => $"{SaveDir}/persistent.sfs";

        public static bool BackupExists() => File.Exists(BackupPath);

        public static void MakeBackup()
        {
            Debug.Log("[AXE][Sim] Writing pre-simulation backup save.");
            GamePersistence.SaveGame(BackupName, HighLogic.SaveFolder, SaveMode.OVERWRITE);
        }

        /// <summary>Swap <c>persistent.sfs</c> back to the pre-sim snapshot and re-sync the live game state
        /// from it, then archive the backup. Safe to call only when <see cref="BackupExists"/> is true.</summary>
        public static void Restore()
        {
            DisableSimLocks();

            if (FlightGlobals.fetch != null)
            {
                FlightGlobals.PersistentVesselIds.Clear();
                FlightGlobals.PersistentLoadedPartIds.Clear();
                FlightGlobals.PersistentUnloadedPartIds.Clear();
            }

            try
            {
                Debug.Log("[AXE][Sim] Restoring pre-simulation save (swapping persistent.sfs).");
                File.Copy(BackupPath, PersistentPath, true);
                Game loaded = GamePersistence.LoadGame(BackupName, HighLogic.SaveFolder, true, false);
                if (loaded != null)
                    GameEvents.onGameStatePostLoad.Fire(loaded.config);
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE][Sim] Restore failed: " + e + "\nYour pre-sim save is at " + BackupPath +
                               " — copy it over persistent.sfs manually if needed.");
            }

            DeleteBackup();
        }

        /// <summary>Archive the backup into the save's Backup/ folder and remove it from the live save
        /// folder, so <see cref="BackupExists"/> reads false afterwards.</summary>
        public static void DeleteBackup()
        {
            try
            {
                if (!File.Exists(BackupPath)) return;
                string backupFolder = $"{SaveDir}/Backup";
                Directory.CreateDirectory(backupFolder);
                string archived = $"{backupFolder}/{BackupName}.sfs";
                if (File.Exists(archived)) File.Delete(archived);
                File.Move(BackupPath, archived);
            }
            catch (Exception e) { Debug.LogError("[AXE][Sim] archiving backup failed: " + e); }
        }

        // --- Quicksave / quickload locks: keep the player from entangling the real save mid-sim. ---
        public static void EnableSimLocks()
        {
            InputLockManager.SetControlLock(ControlTypes.QUICKSAVE, QsLock);
            InputLockManager.SetControlLock(ControlTypes.QUICKLOAD, QlLock);
        }

        public static void DisableSimLocks()
        {
            InputLockManager.RemoveControlLock(QsLock);
            InputLockManager.RemoveControlLock(QlLock);
        }
    }
}
