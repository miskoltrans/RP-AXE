using System;
using System.Collections.Generic;
using HarmonyLib;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Re-applies AXE's GAMEPARAMETERS overrides to every set of parameters KSP hands out for a new
    /// CAREER game. This — not the preset-dictionary patch below — is what actually reaches the
    /// new-game dialog.
    ///
    /// WHY: <c>MainMenu.Start</c> caches <c>newGameParameters =
    /// GameParameters.GetDefaultParameters(CAREER, Normal)</c> on the first main-menu load
    /// (MainMenu.cs:262, decompiled), and that cached object is what "Start New Game" uses. Our
    /// KSPAddon(MainMenu) Start() races it and lost — so the dictionary was patched a moment too
    /// late and every new career came out stock (25,000 funds, BypassEntryPurchaseAfterResearch
    /// True). Patching the accessor instead makes ordering irrelevant: MainMenu's cache, its
    /// UpdatedGameParameters(), and DifficultyOptionsMenu (DifficultyOptionsMenu.cs:2723) all route
    /// through this one method.
    ///
    /// It also fixes a second clobber that no dictionary patch can: GetDefaultParameters ends by
    /// calling <c>SetDifficultyPreset(p)</c> on every custom parameter node with
    /// <c>HasPresets</c> — which AdvancedParams has — overwriting fields we set. That is a no-op on
    /// Normal but not on Easy/Moderate/Hard. Running as a postfix, we get the last word.
    ///
    /// CAREER ONLY, deliberately: stock forces BypassEntryPurchaseAfterResearch = true for
    /// SANDBOX / SCIENCE_SANDBOX / MISSION, and re-imposing AXE's False there would make sandbox
    /// parts need purchasing.
    /// </summary>
    [HarmonyPatch(typeof(GameParameters), nameof(GameParameters.GetDefaultParameters))]
    internal static class AxeDifficultyPresetsPatch
    {
        private static ConfigNode _root;
        private static bool _loaded;

        /// <summary>The GAMEPARAMETERS node, fetched on first use (GameDatabase is not ready when
        /// Harmony patches are applied at Instantly).</summary>
        internal static ConfigNode Root
        {
            get
            {
                if (_loaded || GameDatabase.Instance == null)
                    return _root;

                foreach (ConfigNode n in GameDatabase.Instance.GetConfigNodes("GAMEPARAMETERS"))
                    _root = n;    // last one wins, as RP-1 does

                _loaded = true;
                if (_root == null)
                    Debug.LogWarning("[AXE] No GAMEPARAMETERS node found; difficulty left at stock defaults.");

                return _root;
            }
        }

        private static void Postfix(Game.Modes mode, GameParameters.Preset p, GameParameters __result)
        {
            if (__result == null || mode != Game.Modes.CAREER)
                return;

            try
            {
                ConfigNode preset = Root?.GetNode(p.ToString());
                if (preset == null)
                    return;    // Preset.Custom has no section, by design

                __result.Load(preset);
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE] Failed to apply GAMEPARAMETERS to " + p + " parameters: " + e);
            }
        }
    }

    /// <summary>
    /// Applies AXE's difficulty defaults (design/Settings/AxeGameParameters.cfg) to KSP's built-in
    /// difficulty presets, so a new career starts with them instead of stock Normal.
    ///
    /// WHY THIS EXISTS: <c>GAMEPARAMETERS</c> is NOT a stock KSP config node — the string does not
    /// appear anywhere in Assembly-CSharp, and no installed mod reads it. It is purely an RP-1
    /// convention, applied by RP-1's own plugin (RP0/Singletons/DifficultyPresetChanger.cs); LRTR
    /// ships the identical config+plugin pair. AXE ported RP-1's config and not its reader, so the
    /// whole file sat inert and every career booted stock Normal — which is how
    /// <c>BypassEntryPurchaseAfterResearch = True</c> (research a node, get every part in it free)
    /// came back despite the config setting it False in all four presets.
    ///
    /// MECHANISM (same as RP-1's): <c>GameParameters.SetDifficultyPresets()</c> rebuilds the static
    /// preset dictionary from stock code defaults; we then Load() our per-preset sub-node over each
    /// one. The new-game "Difficulty Options" screen reads that dictionary, so this must run before
    /// the player reaches it — MainMenu/Start is early enough (AxeEnableCareer runs there too), and
    /// re-running on every return to the main menu is harmless because SetDifficultyPresets() resets
    /// to stock first.
    ///
    /// SCOPE: NEW games only. A save stores its own resolved parameters, so an existing career keeps
    /// whatever it was created with — change those in-game via Settings -> Difficulty Options
    /// ("No Entry Purchase Required on Research") or by editing persistent.sfs.
    ///
    /// NB this dictionary patch is NOT sufficient on its own: MainMenu caches its new-game
    /// parameters during the same scene load, so it can read the presets before this runs. The
    /// Harmony postfix in <see cref="AxeDifficultyPresetsPatch"/> is what makes the settings stick;
    /// this remains for anything that reads GameParameters.DifficultyPresets directly.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, false)]
    public class AxeDifficultyPresets : MonoBehaviour
    {
        private void Start()
        {
            try
            {
                ConfigNode paramsNode = null;
                foreach (ConfigNode n in GameDatabase.Instance.GetConfigNodes("GAMEPARAMETERS"))
                    paramsNode = n;    // last one wins, as RP-1 does

                if (paramsNode == null)
                {
                    Debug.LogWarning("[AXE] No GAMEPARAMETERS node found; difficulty presets left at stock defaults.");
                    return;
                }

                GameParameters.SetDifficultyPresets();

                int applied = 0;
                foreach (KeyValuePair<GameParameters.Preset, GameParameters> kvp in GameParameters.DifficultyPresets)
                {
                    ConfigNode n = paramsNode.GetNode(kvp.Key.ToString());
                    if (n == null)
                    {
                        // Preset.Custom is expected: it is the stock "custom difficulty" slot, which
                        // neither AXE nor RP-1 authors. Any OTHER missing preset is an authoring bug.
                        if (kvp.Key != GameParameters.Preset.Custom)
                            Debug.LogWarning("[AXE] GAMEPARAMETERS has no section for preset " + kvp.Key + "; it keeps stock values.");
                        continue;
                    }

                    kvp.Value.Load(n);
                    applied++;
                }

                Debug.Log("[AXE] Difficulty presets reset from GAMEPARAMETERS (" + applied + " presets applied).");
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE] Failed to apply GAMEPARAMETERS difficulty presets: " + e);
            }
        }
    }
}
