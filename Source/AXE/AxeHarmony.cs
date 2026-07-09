using System;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Applies AXE's Harmony patches once at startup (Instantly + once). Currently just the
    /// tracking-station tech gate (<see cref="AxeTrackingStationGate"/>); future AXE.dll patches
    /// annotated with [HarmonyPatch] are picked up automatically by PatchAll.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Instantly, true)]
    public class AxeHarmony : MonoBehaviour
    {
        internal const string HarmonyId = "RPAxe.AXE";

        private void Start()
        {
            try
            {
                new Harmony(HarmonyId).PatchAll(Assembly.GetExecutingAssembly());
                Debug.Log("[AXE] Harmony patches applied.");
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE] Harmony PatchAll failed: " + e);
            }
        }
    }
}
