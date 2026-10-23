using HarmonyLib;
using RealFuels;
using System;
using System.Linq;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Makes an engine CONFIG's unlock state actually bind in the editor: you cannot switch an engine to a
    /// configuration you have not researched and paid for.
    ///
    /// RealFuels gates a config on two things -- <c>CanConfig()</c> (its techRequired, which AXE homes per
    /// variant via AxeEngineConfigGates.cfg) and <c>UnlockedConfig()</c> -> EntryCostDatabase, priced by
    /// AXE's ENTRYCOSTMODS (AxeEntryCostMods.cfg). But nothing *enforces* either one at the point of
    /// selection. In <c>EngineConfigGUI.DrawActionCell</c> the two buttons disagree:
    ///
    ///     GUI.enabled = !isSelected;                        // "Switch"  -- any row that isn't current
    ///     ...  apply?.Invoke();                             //              switches unconditionally
    ///     GUI.enabled = flag &amp;&amp; !flag2 &amp;&amp; num > 0.0;        // "Buy (N)" -- correctly gated
    ///
    /// The Buy button knows about tech and ownership; the Switch button next to it does not. RealFuels
    /// papers over this for FREE configs only (the <c>num &lt;= 0.0</c> branch auto-purchases on switch) and
    /// otherwise relies on <c>ModuleEngineConfigsBase.Validate()</c>, a pre-launch validation hook whose
    /// only consumer is RP-1's RP0.dll. AXE has no RP-0, and nothing else in the install references
    /// ModuleEngineConfigsBase, so an unowned paid config was simply selectable and flyable.
    ///
    /// Tank type-switching is unaffected and always worked: those are genuine <c>PARTUPGRADE</c>s that parts
    /// reference from their own <c>UPGRADES{}</c> block (<c>RFTech-Tank-*</c> -> <c>typeAvailable</c>), which
    /// stock KSP's PartUpgradeManager enforces — a type whose upgrade is locked is simply absent from the
    /// dropdown. What that gate now enforces is research alone: AXE grants every upgrade on research instead
    /// of selling it (AxeGrantUpgradeUnlock, docs/SCIENCE.md §5d). Engine configs are the exception, and
    /// deliberately so — they are RealFuels' own parallel unlock system, priced per variant.
    ///
    /// We gate at the point of action rather than at launch. RP-1 lets you configure freely and blocks the
    /// *launch* until you settle up, which needs a PreFlightCheck subsystem and a pay-to-resolve dialog it
    /// builds itself; blocking the switch gets the same guarantee in one patch, gives feedback at the moment
    /// of the click, and leaves the Buy button -- which RealFuels already wired correctly -- as the way in.
    ///
    /// DrawActionCell has two shapes, one patch class each; Prepare() keeps exactly one of them:
    ///   RealFuels &lt;= 15.15  DrawActionCell(Rect, ConfigNode node, bool isSelected, Action apply)
    ///   RealFuels &gt;= 15.16  DrawActionCell(Rect, CachedRow cached) -- node and apply live in
    ///                       cached.Row (a ConfigRowDefinition struct), see AxeEngineConfigPurchaseGateRows.
    /// </summary>
    [HarmonyPatch(typeof(EngineConfigGUI), "DrawActionCell")]
    internal static class AxeEngineConfigPurchaseGate
    {
        private static readonly AccessTools.FieldRef<EngineConfigGUI, ModuleEngineConfigsBase> ModuleOf =
            AccessTools.FieldRefAccess<EngineConfigGUI, ModuleEngineConfigsBase>("_module");

        private static bool Prepare() => AxeEngineConfigGateShared.HasParameter("apply");

        /// <summary>
        /// Wrap the caller's apply delegate so the switch only lands when the config is owned. The check has
        /// to happen at INVOKE time, not here: on the Buy path RealFuels purchases first and then invokes
        /// apply within this same call, so a decision made now would reject a config the player just bought.
        /// </summary>
        [HarmonyPrefix]
        internal static void Prefix(EngineConfigGUI __instance, ConfigNode node, ref Action apply)
        {
            Action gated = Gate(__instance, node, apply);
            if (gated != null) apply = gated;
        }

        /// <summary>The gated replacement for <paramref name="apply"/>, or null to leave it alone.</summary>
        internal static Action Gate(EngineConfigGUI gui, ConfigNode node, Action apply)
        {
            if (apply == null || node == null) return null;

            ModuleEngineConfigsBase module;
            try { module = ModuleOf(gui); }
            catch (Exception e) { Debug.LogError("[AXE] Engine config gate: cannot read _module: " + e); return null; }
            if (module == null) return null;

            return () =>
            {
                if (EngineConfigTechLevels.UnlockedConfig(node, module.part)) { apply(); return; }
                Refuse(node, module);
            };
        }

        private static void Refuse(ConfigNode node, ModuleEngineConfigsBase module)
        {
            string message;
            try
            {
                if (!EngineConfigTechLevels.CanConfig(node))
                {
                    string tech = node.GetValue("techRequired");
                    string title = string.IsNullOrEmpty(tech) ? null : ResearchAndDevelopment.GetTechnologyTitle(tech);
                    message = "Not researched yet: " + (string.IsNullOrEmpty(title) ? "this configuration" : title);
                }
                else
                {
                    double cost = EntryCostManager.Instance == null
                        ? 0.0
                        : EntryCostManager.Instance.ConfigEntryCost(node.GetValue("name"));
                    message = "Unlock this configuration first — " + cost.ToString("N0") + " funds";
                }
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE] Engine config gate: refusal message failed: " + e);
                message = "This configuration is not unlocked";
            }

            ScreenMessages.PostScreenMessage(message, 4f, ScreenMessageStyle.UPPER_CENTER);
        }
    }

    /// <summary>
    /// The same gate for RealFuels &gt;= 15.16, whose DrawActionCell takes a private CachedRow. The row is
    /// CACHED across frames, so the gated delegate is swapped into cached.Row.Apply only for the duration
    /// of the call and the original is put back in the finalizer -- writing it permanently would wrap the
    /// wrapper again on every OnGUI pass. ConfigRowDefinition is a struct and absent from the RealFuels
    /// this compiles against, hence reflection on a boxed copy that is written back.
    /// </summary>
    [HarmonyPatch(typeof(EngineConfigGUI), "DrawActionCell")]
    internal static class AxeEngineConfigPurchaseGateRows
    {
        private static FieldInfo _row, _node, _apply;

        private static bool Prepare()
        {
            if (!AxeEngineConfigGateShared.HasParameter("cached")) return false;
            _row = AccessTools.Field(AccessTools.Inner(typeof(EngineConfigGUI), "CachedRow"), "Row");
            if (_row == null) return false;
            _node = AccessTools.Field(_row.FieldType, "Node");
            _apply = AccessTools.Field(_row.FieldType, "Apply");
            return _node != null && _apply != null;
        }

        [HarmonyPrefix]
        internal static void Prefix(EngineConfigGUI __instance, object cached, out Action __state)
        {
            __state = null;
            if (cached == null) return;
            object row = _row.GetValue(cached);
            Action apply = _apply.GetValue(row) as Action;
            Action gated = AxeEngineConfigPurchaseGate.Gate(__instance, _node.GetValue(row) as ConfigNode, apply);
            if (gated == null) return;
            _apply.SetValue(row, gated);
            _row.SetValue(cached, row);
            __state = apply;
        }

        [HarmonyFinalizer]
        internal static void Finalizer(object cached, Action __state)
        {
            if (cached == null || __state == null) return;
            object row = _row.GetValue(cached);
            _apply.SetValue(row, __state);
            _row.SetValue(cached, row);
        }
    }

    internal static class AxeEngineConfigGateShared
    {
        /// <summary>Does EngineConfigGUI.DrawActionCell, in the RealFuels actually loaded, take a parameter of this name?</summary>
        internal static bool HasParameter(string name)
        {
            MethodInfo m = AccessTools.Method(typeof(EngineConfigGUI), "DrawActionCell");
            return m != null && m.GetParameters().Any(p => p.Name == name);
        }
    }
}
