using System;
using System.Reflection;
using HarmonyLib;

namespace RPAxe
{
    /// <summary>
    /// Two fixes to the Adjustable Heatshield's part action window, both caused by ROHeatshields
    /// assuming RP-1 is installed. AXE has no RP0.dll, so the mod takes its "no career mod" branch.
    ///
    /// <b>1. The RO-Tanks group re-collapses itself while you drag the Diameter slider.</b>
    ///
    /// <c>ModuleROHeatshield.OnStartFinished</c> chains <c>UpdateHeatshieldValues()</c> onto
    /// <c>ModuleROTank</c>'s <c>currentDiameter</c> / <c>currentVScale</c> field-changed callbacks, and
    /// that method ends in <c>UpdatePAW()</c> — which sets <c>UIPartActionWindow.displayDirty</c>. Stock
    /// consumes that with <c>CreatePartList(clearFirst: true)</c>: every item and every group in the
    /// window is destroyed and rebuilt, on every increment of the slider. Each rebuild re-runs
    /// <c>UIPartActionGroup.Initialize</c>, which re-derives the collapsed state from
    /// <c>GameSettings.collpasedPAWGroups</c> (or, with KSPCommunityFixes' PAWGroupMemory patch on, from
    /// its own dictionary). Both of those are written by <c>Collapse()</c>/<c>Expand()</c>, and both
    /// <b>call <c>window.UpdateWindow()</c> before returning</b> — so a click that expands the group
    /// rebuilds the window, and re-Initializes the replacement group, before the state write that would
    /// have kept it open lands. The group snaps shut and the Diameter control goes with it.
    ///
    /// None of ModuleROHeatshield's own displayed fields (Type, Description, Max Temp, Max Skin Temp)
    /// depend on diameter, and stock re-reads label and resource items every frame in
    /// <c>UpdateItem()</c>, so the rebuild buys nothing on that path. It IS needed on the preset path:
    /// <c>ApplyPreset</c> toggles <c>Fields["description"].guiActiveEditor</c> and adds/removes the
    /// Ablator + CharredAblator resources, which are structural changes to the item list. So the rebuild
    /// is allowed only while <c>ApplyPreset</c> is on the stack, and skipped otherwise.
    ///
    /// <b>2. The Type selector shows one option and appears dead.</b>
    ///
    /// <c>ModuleROHeatshield.OnStart</c> branches on <c>RP1Found</c>, which is literally "is an assembly
    /// named RP0 loaded". RP-1 gets the full preset list with unresearched entries drawn in orange;
    /// everyone else gets <c>GetUnlockedPresets()</c>, which filters the list down to what is actually
    /// researched. AXE's tree grants the part and the Heatsink preset together on cmp_ablativeTPS
    /// (MercuryHS/GeminiHS one node later on cmp_ablativeRefinement — the same shape RP-1 uses), so at
    /// unlock the chooser holds exactly one entry and cycling it does nothing.
    ///
    /// Taking RP-1's presentation instead is not an option here: it relies on its Engineer's Report to
    /// stop you launching with a preset you have not researched, and AXE cut that. So the filter stays
    /// and the row is hidden when there is nothing to choose between — which is the convention ROLib
    /// already applies to its own choosers (<c>ROLupdateUIChooseOptionControl</c> sets
    /// <c>guiActiveEditor = options.Length > 1</c>). The tech tree remains the only signal that better
    /// shields exist, which is where that signal belongs.
    ///
    /// ROHeatshields is reached by reflection so AXE keeps no compile-time dependency on it; if the mod
    /// is absent, Prepare() returns false and the patch is dropped rather than failing PatchAll.
    /// </summary>
    internal static class AxeRoHeatshieldPawShared
    {
        internal const string ModuleTypeName = "ROHeatshields.ModuleROHeatshield";

        /// <summary>
        /// Depth, not a bool: ApplyPreset is not reentrant today, but a counter cannot leave the flag
        /// stuck on if it ever becomes so.
        /// </summary>
        internal static int ApplyPresetDepth;
    }

    /// <summary>Brackets ApplyPreset so <see cref="AxeRoHeatshieldSkipPawRebuild"/> can tell the
    /// structural path (preset changed) from the per-tick path (diameter dragged).</summary>
    [HarmonyPatch]
    internal static class AxeRoHeatshieldApplyPresetScope
    {
        private static MethodBase _applyPreset;

        private static bool Prepare()
        {
            Type module = AccessTools.TypeByName(AxeRoHeatshieldPawShared.ModuleTypeName);
            if (module == null) return false;                 // ROHeatshields not installed
            _applyPreset = AccessTools.Method(module, "ApplyPreset");
            return _applyPreset != null;
        }

        private static MethodBase TargetMethod() => _applyPreset;

        private static void Prefix() => AxeRoHeatshieldPawShared.ApplyPresetDepth++;

        // Finalizer, not Postfix: runs even if ApplyPreset throws, so the depth cannot latch.
        private static void Finalizer() => AxeRoHeatshieldPawShared.ApplyPresetDepth--;
    }

    /// <summary>Drops the full PAW teardown on diameter/V-scale changes; see
    /// <see cref="AxeRoHeatshieldPawShared"/> for why it is safe.</summary>
    [HarmonyPatch]
    internal static class AxeRoHeatshieldSkipPawRebuild
    {
        private static MethodBase _updatePaw;

        private static bool Prepare()
        {
            Type module = AccessTools.TypeByName(AxeRoHeatshieldPawShared.ModuleTypeName);
            if (module == null) return false;
            _updatePaw = AccessTools.Method(module, "UpdatePAW");
            return _updatePaw != null;
        }

        private static MethodBase TargetMethod() => _updatePaw;

        private static bool Prefix() => AxeRoHeatshieldPawShared.ApplyPresetDepth > 0;
    }

    /// <summary>Hides the Type row when the researched presets leave nothing to pick between.</summary>
    [HarmonyPatch]
    internal static class AxeRoHeatshieldHideSinglePreset
    {
        private static MethodBase _onStart;

        private static bool Prepare()
        {
            Type module = AccessTools.TypeByName(AxeRoHeatshieldPawShared.ModuleTypeName);
            if (module == null) return false;
            _onStart = AccessTools.Method(module, "OnStart");
            return _onStart != null;
        }

        private static MethodBase TargetMethod() => _onStart;

        /// <summary>
        /// Postfix, so it reads the option list OnStart has already narrowed via UpdatePresetsList.
        /// __instance is typed as the base PartModule to avoid a compile-time reference to the mod.
        /// </summary>
        private static void Postfix(PartModule __instance)
        {
            if (!HighLogic.LoadedSceneIsEditor) return;

            BaseField field = __instance.Fields["heatShieldType"];
            if (field == null) return;

            UI_ChooseOption chooser = field.uiControlEditor as UI_ChooseOption;
            if (chooser?.options == null) return;

            field.guiActiveEditor = chooser.options.Length > 1;
        }
    }
}
