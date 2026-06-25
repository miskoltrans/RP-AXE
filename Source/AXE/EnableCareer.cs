using System;
using System.Linq;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Re-enables Career and Science modes under Realism Overhaul.
    ///
    /// RealismOverhaul.dll Harmony-patches MainMenu.ConfirmNewGame and forces "Only Sandbox
    /// Supported" unless a loaded assembly is named "RP-0" (how it detects RP-1) OR its private
    /// static <c>_overrideCareer</c> flag is true. Its config-node override path
    /// (REALISMOVERHAULSETTINGS { allowCareer }) is dead code in the shipped build: the gating
    /// field <c>_needCheckDB</c> is initialised false and never set true — so no pure-config fix
    /// exists. (Verified against RealismOverhaul Source/Harmony/MainMenu.cs.)
    ///
    /// We flip <c>_overrideCareer</c> by reflection rather than impersonating RP-1 via an
    /// "RP-0"-named assembly, which would also activate every :NEEDS[RP-0] ModuleManager patch.
    /// This touches RO's gate and nothing else. See docs/DECISIONS.md D5.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, false)]
    public class AxeEnableCareer : MonoBehaviour
    {
        private void Start()
        {
            try
            {
                Type patch = AppDomain.CurrentDomain.GetAssemblies()
                    .Select(a => a.GetType("RealismOverhaul.Harmony.PatchMainMenu"))
                    .FirstOrDefault(t => t != null);

                if (patch == null)
                {
                    Debug.Log("[AXE] RealismOverhaul main-menu patch not found; career gate left as-is (RO absent?).");
                    return;
                }

                FieldInfo overrideCareer = patch.GetField("_overrideCareer", BindingFlags.NonPublic | BindingFlags.Static);
                if (overrideCareer == null)
                {
                    Debug.LogWarning("[AXE] RO PatchMainMenu._overrideCareer not found; RO internals changed. Career may stay Sandbox-only.");
                    return;
                }

                overrideCareer.SetValue(null, true);
                Debug.Log("[AXE] Career/Science enabled: set RealismOverhaul PatchMainMenu._overrideCareer = true.");
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE] Failed to enable Career/Science via RO reflection: " + e);
            }
        }
    }
}
