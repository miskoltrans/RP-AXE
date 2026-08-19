using HarmonyLib;
using RealFuels;
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Tells the player why the bimodal-engine toggle did nothing, instead of silently swallowing the click.
    ///
    /// A <c>ModuleBimodalEngineConfigs</c> engine has a second operating mode only on the CONFIGs that
    /// declare a <c>SUBCONFIG</c> — on the J58 that is J58-P-4B (N2O injection) alone, not J58-P-4 or
    /// J58-P-4A. But the toggle is advertised on all of them: its <c>[KSPEvent]</c> is declared
    /// <c>guiActive = true, guiActiveEditor = true</c> unconditionally and <c>SetConfiguration()</c> only
    /// ever rewrites the event's <c>guiName</c> — it never touches <c>.active</c>. So "Engage N2O Injection"
    /// renders on every J58 regardless of which configuration is selected, and on two of the three
    /// <c>ToggleMode()</c> falls straight off the end of its <c>if (ConfigHasSecondary(config))</c> guard:
    ///
    ///     public void ToggleMode()
    ///     {
    ///         if (ConfigHasSecondary(config)) { ...swap... }
    ///         // else: no swap, no message, no log line.
    ///     }
    ///
    /// A button that is present, enabled, and inert reads as a bug. The fix is not to hide it — a vanished
    /// button teaches nothing either — but to answer the click: name the configuration that actually carries
    /// the mode and say which of the three gates (researched / bought / selected) is the one in the way.
    /// Same shape as <see cref="AxeEngineConfigPurchaseGate"/>, which turns RealFuels' other silent refusal
    /// into a screen message.
    ///
    /// This is upstream RealFuels behaviour, not an AXE divergence — RP-1 swallows the click identically.
    ///
    /// A void prefix, deliberately: it changes no control flow and skips nothing. When there IS a secondary
    /// mode it says nothing and the original runs untouched; when there isn't, the original's own guard
    /// no-ops exactly as before and we have added only the explanation.
    /// </summary>
    [HarmonyPatch(typeof(ModuleBimodalEngineConfigs), "ToggleMode")]
    internal static class AxeBimodalToggleExplain
    {
        [HarmonyPrefix]
        internal static void Prefix(ModuleBimodalEngineConfigs __instance)
        {
            try
            {
                if (__instance == null || HasSecondary(__instance.config)) return;
                ScreenMessages.PostScreenMessage(Explain(__instance), 6f, ScreenMessageStyle.UPPER_CENTER);
            }
            catch (Exception e)
            {
                // Never let the explanation break the toggle it is explaining.
                Debug.LogError("[AXE] Bimodal toggle explain failed: " + e);
            }
        }

        /// <summary>
        /// Mirrors RealFuels' own <c>GetPatchesOfConfig</c> (protected) using only public API, display
        /// filters included, so a config that is filtered out of the UI is not advertised here either.
        /// </summary>
        private static List<ConfigNode> Patches(ConfigNode config)
        {
            if (config == null) return new List<ConfigNode>();
            return ConfigFilters.Instance.FilterDisplayConfigs(
                config.GetNodes(ModuleEngineConfigs.PatchNodeName).ToList());
        }

        private static bool HasSecondary(ConfigNode config) => Patches(config).Count > 0;

        private static string DisplayName(ConfigNode config)
            => config.HasValue("displayName") ? config.GetValue("displayName") : config.GetValue("name");

        private static string Explain(ModuleBimodalEngineConfigs module)
        {
            string action = string.IsNullOrEmpty(module.toSecondaryText) ? "That mode" : module.toSecondaryText;
            string current = module.config == null ? null : DisplayName(module.config);

            // Of the configs that carry the mode, report on the one the player is closest to having:
            // owned beats researched beats locked, so the message names the nearest gate, not the worst.
            ConfigNode best = null;
            int bestRank = -1;
            foreach (ConfigNode cfg in module.configs ?? new List<ConfigNode>())
            {
                if (cfg == null || !HasSecondary(cfg)) continue;
                int rank = EngineConfigTechLevels.UnlockedConfig(cfg, module.part) ? 2
                         : EngineConfigTechLevels.CanConfig(cfg) ? 1
                         : 0;
                if (rank > bestRank) { bestRank = rank; best = cfg; }
            }

            if (best == null)
                return action + ": this engine has no second operating mode.";

            string head = $"{action} needs the {DisplayName(best)} configuration"
                        + (string.IsNullOrEmpty(current) ? "" : $" (this engine is on {current})") + ".\n";

            if (bestRank == 2)
                return head + "Select it in the engine configs window.";

            if (bestRank == 1)
            {
                double cost = EntryCostManager.Instance == null
                    ? 0.0
                    : EntryCostManager.Instance.ConfigEntryCost(best.GetValue("name"));
                return head + $"Unlock it in the engine configs window — {cost:N0} funds.";
            }

            string tech = best.GetValue("techRequired");
            string title = string.IsNullOrEmpty(tech) ? null : ResearchAndDevelopment.GetTechnologyTitle(tech);
            return head + "Not researched yet: " + (string.IsNullOrEmpty(title) ? "its tech node" : title);
        }
    }
}
