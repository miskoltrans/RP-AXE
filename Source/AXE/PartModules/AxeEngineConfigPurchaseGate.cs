using HarmonyLib;
using RealFuels;
using System;
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
    /// </summary>
    [HarmonyPatch(typeof(EngineConfigGUI), "DrawActionCell")]
    internal static class AxeEngineConfigPurchaseGate
    {
        private static readonly AccessTools.FieldRef<EngineConfigGUI, ModuleEngineConfigsBase> ModuleOf =
            AccessTools.FieldRefAccess<EngineConfigGUI, ModuleEngineConfigsBase>("_module");

        /// <summary>
        /// Wrap the caller's apply delegate so the switch only lands when the config is owned. The check has
        /// to happen at INVOKE time, not here: on the Buy path RealFuels purchases first and then invokes
        /// apply within this same call, so a decision made now would reject a config the player just bought.
        /// </summary>
        [HarmonyPrefix]
        internal static void Prefix(EngineConfigGUI __instance, ConfigNode node, ref Action apply)
        {
            if (apply == null || node == null) return;

            ModuleEngineConfigsBase module;
            try { module = ModuleOf(__instance); }
            catch (Exception e) { Debug.LogError("[AXE] Engine config gate: cannot read _module: " + e); return; }
            if (module == null) return;

            Action original = apply;
            apply = () =>
            {
                if (EngineConfigTechLevels.UnlockedConfig(node, module.part)) { original(); return; }
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
}
