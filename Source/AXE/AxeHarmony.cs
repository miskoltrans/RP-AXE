using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Applies AXE's Harmony patches once at startup (Instantly + once). Every class in AXE.dll
    /// annotated with [HarmonyPatch] is picked up here, and ONLY here: a second PatchAll over this
    /// assembly under another Harmony id applies every patch twice (0.9.0 did that from
    /// AxeTreeHighlight, which ran the avionics degradation twice per frame).
    ///
    /// This is PatchAll, one class at a time. PatchAll itself stops at the first class that throws,
    /// so a single upstream API change took every AXE patch after it down too -- RealFuels 15.16
    /// reshaped EngineConfigGUI.DrawActionCell and the 0.9.0 log showed only "PatchAll failed".
    /// Now a class whose target moved costs only itself, and the log names it.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Instantly, true)]
    public class AxeHarmony : MonoBehaviour
    {
        internal const string HarmonyId = "RPAxe.AXE";

        private void Start()
        {
            var harmony = new Harmony(HarmonyId);
            int applied = 0, failed = 0;
            foreach (Type type in AccessTools.GetTypesFromAssembly(Assembly.GetExecutingAssembly()))
            {
                try
                {
                    List<MethodInfo> patched = harmony.CreateClassProcessor(type).Patch();
                    if (patched != null && patched.Count > 0) applied++;
                }
                catch (Exception e)
                {
                    failed++;
                    Debug.LogError("[AXE] Harmony patch " + type.FullName + " NOT applied: " + e);
                }
            }
            Debug.Log("[AXE] Harmony patches applied: " + applied + " class(es), " + failed + " failed.");
        }
    }
}
