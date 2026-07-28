using System;
using System.Reflection;
using HarmonyLib;
using KSP.UI.Screens;

namespace RPAxe
{
    /// <summary>
    /// Suppresses a NullReferenceException thrown by DynamicBatteryStorage every time the application
    /// launcher comes up in the editor or in flight.
    ///
    /// DBS switches itself off when Kerbalism is installed: <c>DynamicBatteryStorage.Settings</c>
    /// walks the loaded assemblies and any name starting with "Kerbalism" sets
    /// <c>Settings.Enabled = false</c> (logged as "Kerbalism detected. DBS will disable itself.").
    /// Nothing restores it — DynamicBatteryStorageSettings.cfg carries no <c>Enabled</c> key, so the
    /// <c>TryGetValue("Enabled", ref Enabled)</c> in <c>Settings.Load()</c> that runs afterwards is a
    /// no-op.
    ///
    /// <c>SystemsMonitorUI.OnGUIAppLauncherReady()</c> then honours that flag only halfway:
    /// <code>
    ///   if (ApplicationLauncher.Ready &amp;&amp; stockToolbarButton == null &amp;&amp; Settings.Enabled &amp;&amp; ...)
    ///       stockToolbarButton = ApplicationLauncher.Instance.AddModApplication(...);
    ///   CreateToolbarPanel();          // <-- outside the guard
    /// </code>
    /// The button is never created, but CreateToolbarPanel() runs regardless and ends with
    /// <c>toolbarTag.Position(stockToolbarButton)</c>. <c>ToolbarIconTag.Position</c> opens by
    /// dereferencing <c>button.toggleButton</c>, so the null button throws. (DBS's own
    /// <c>ResetAppLauncher</c> guards the same field correctly, so this is an oversight in the one
    /// method, not a deliberate contract.)
    ///
    /// The throw is contained by EventVoid's per-listener try/catch — no other app-launcher
    /// registration is skipped — but it puts an [ERR]+[EXC] pair in the log on every editor/flight
    /// scene load, which buries real errors in AXE's smoke-test output.
    ///
    /// The fix skips CreateToolbarPanel outright when there is no button to hang the panel off. DBS's
    /// <c>Update()</c> and <c>DestroyToolbarPanel()</c> already null-check <c>toolbarPanel</c>, and the
    /// hover/click handlers that do not are only reachable through the button that does not exist, so
    /// leaving it null is safe.
    ///
    /// Uninstalling DBS is not an option: it is a transitive CKAN dependency of the Nertea mods in
    /// RP-AXE-deps.ckan, so rebuild-instance.ps1 pulls it back in. Nothing else in the instance uses
    /// it — no assembly references it, no :NEEDS[] patch mentions it, and no part carries
    /// ModuleDynamicBatteryStorage (RealismOverhaul's DynamicBatteryStorageNuker strips that
    /// VesselModule outright).
    ///
    /// DBS is reached by reflection so AXE keeps no compile-time dependency on it; if the mod is
    /// absent, Prepare() returns false and the patch is never applied.
    /// </summary>
    [HarmonyPatch]
    internal static class AxeDbsToolbarNreFix
    {
        private const string UiTypeName = "DynamicBatteryStorage.UI.SystemsMonitorUI";

        private static MethodBase _createToolbarPanel;
        private static FieldInfo _stockToolbarButton;      // protected STATIC on SystemsMonitorUI

        /// <summary>
        /// Harmony calls Prepare() before TargetMethod(); returning false drops the whole patch class.
        /// That is what keeps DBS a soft dependency — and what makes a future DBS release that renames
        /// or fixes these members degrade to "patch not applied" instead of a PatchAll failure that
        /// would take every other AXE patch down with it.
        /// </summary>
        private static bool Prepare()
        {
            Type ui = AccessTools.TypeByName(UiTypeName);
            if (ui == null) return false;                  // DBS not installed

            _createToolbarPanel = AccessTools.Method(ui, "CreateToolbarPanel");
            _stockToolbarButton = AccessTools.Field(ui, "stockToolbarButton");
            return _createToolbarPanel != null && _stockToolbarButton != null;
        }

        private static MethodBase TargetMethod()
        {
            return _createToolbarPanel;
        }

        private static bool Prefix()
        {
            // Typed as ApplicationLauncherButton so this uses Unity's operator== (a destroyed button
            // is fake-null and must count as absent), matching how DBS itself tests the field.
            ApplicationLauncherButton button = (ApplicationLauncherButton)_stockToolbarButton.GetValue(null);
            return button != null;
        }
    }
}
