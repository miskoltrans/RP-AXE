using System;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
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
