using System;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RP-AXE economy: parts unlock free with science; RealFuels engine-CONFIG costs are kept.
    ///
    /// We deliberately do NOT use BypassEntryPurchaseAfterResearch — that switch also disables
    /// RealFuels' config charging (the "develop this engine variant" engineering gate we want to keep).
    /// Instead we force every AvailablePart.entryCost to 0 so unlocking the PART is free, while
    /// RealFuels' separate EntryCostManager keeps charging to unlock each engine CONFIG.
    ///
    /// A ModuleManager patch (design/EntryCosts/ZeroEntryCost.cfg) zeroes the config value, but
    /// RealFuels/ProceduralParts recompute some parts' entryCost at load, so we re-zero in code after
    /// modules have run, and again on entering the Space Center / Editor (where parts get unlocked).
    /// </summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, true)]
    public class FreePartUnlock : MonoBehaviour
    {
        private bool _verified;
        // AvailablePart.entryCost is a read-only property; resolve a way to set it (nonpublic setter
        // or auto-property backing field) once, then reuse.
        private static MethodInfo _setter;
        private static FieldInfo _backing;
        private static bool _resolved;

        private void Start()
        {
            ZeroAll(verify: true);
            GameEvents.onLevelWasLoaded.Add(OnSceneLoaded);
            DontDestroyOnLoad(this);
        }

        private bool _rfChecked;

        private void OnSceneLoaded(GameScenes scene)
        {
            if (scene == GameScenes.SPACECENTER || scene == GameScenes.EDITOR)
            {
                ZeroAll(verify: false);
                // RealFuels' EntryCostManager only exists inside a career save, so confirm the kept
                // config gate here (once) rather than at the main menu.
                if (!_rfChecked) { _rfChecked = true; LogRealFuelsConfigCost(); }
            }
        }

        private static void ResolveEntryCostSetter()
        {
            _resolved = true;
            PropertyInfo p = typeof(AvailablePart).GetProperty("entryCost",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            _setter = p?.GetSetMethod(true);
            if (_setter == null)
                _backing = typeof(AvailablePart).GetField("_entryCost",
                              BindingFlags.NonPublic | BindingFlags.Instance)
                          ?? typeof(AvailablePart).GetField("<entryCost>k__BackingField",
                              BindingFlags.NonPublic | BindingFlags.Instance);
        }

        private void ZeroAll(bool verify)
        {
            if (PartLoader.LoadedPartsList == null) return;
            if (!_resolved) ResolveEntryCostSetter();
            if (_setter == null && _backing == null)
            {
                if (!_verified) { _verified = true; Debug.LogWarning("[AXE] FreePartUnlock: could not resolve AvailablePart.entryCost backing field."); }
                return;
            }

            int changed = 0;
            object[] zero = { 0 };
            foreach (AvailablePart ap in PartLoader.LoadedPartsList)
            {
                if (ap == null || ap.entryCost == 0) continue;
                if (_setter != null) _setter.Invoke(ap, zero);
                else _backing.SetValue(ap, 0);
                changed++;
            }
            if (changed > 0)
                Debug.Log($"[AXE] FreePartUnlock: zeroed entryCost on {changed} parts (parts unlock free).");

            // One-time sanity check: confirm parts really are free now, and RealFuels still charges
            // for engine configs (the kept gate).
            if (verify && !_verified)
            {
                _verified = true;
                int stillPriced = 0;
                foreach (AvailablePart ap in PartLoader.LoadedPartsList)
                    if (ap != null && ap.entryCost != 0) stillPriced++;
                Debug.Log($"[AXE] FreePartUnlock: parts still priced after zeroing = {stillPriced} (want 0).");
                LogRealFuelsConfigCost();
            }
        }

        private void LogRealFuelsConfigCost()
        {
            try
            {
                Type tMgr = null;
                foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (!asm.FullName.StartsWith("RealFuels")) continue;
                    tMgr = asm.GetType("RealFuels.EntryCostManager");
                    if (tMgr != null) break;
                }
                if (tMgr == null) return;

                object inst = tMgr.GetProperty("Instance",
                                  BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static)?.GetValue(null, null)
                              ?? tMgr.GetField("Instance",
                                  BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static)?.GetValue(null);
                MethodInfo mCfg = tMgr.GetMethod("ConfigEntryCost",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance,
                    null, new[] { typeof(string) }, null);
                if (inst == null || mCfg == null) return;

                object aestus = mCfg.Invoke(inst, new object[] { "Aestus" });
                Debug.Log($"[AXE] FreePartUnlock: RealFuels config gate intact (e.g. Aestus config = {aestus} funds).");
            }
            catch (Exception e)
            {
                Debug.Log($"[AXE] FreePartUnlock: RF config check skipped ({e.Message}).");
            }
        }
    }
}
