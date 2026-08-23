using System;
using System.Collections;
using System.Linq;
using UnityEngine;

namespace RPAxe.Bridge
{
    /// <summary>
    /// Load a named save straight from the main menu, so a bridge/crosscheck session can be
    /// driven without a human clicking through it.
    ///
    ///     KSP_x64.exe -axe-bridge -axe-load=default3
    ///     KSP_x64.exe -axe-bridge -axe-load=default3 -axe-focus=Perun 1
    ///
    /// Without <c>-axe-focus</c> it stops in the Tracking Station, which is enough for the AXE
    /// bridge (FlightGlobals.Vessels and every vessel.orbit are live there). KSPTOT Connect is
    /// <c>[KSPAddon(Startup.Flight)]</c>, so talking to THAT needs a vessel focused, which is
    /// what -axe-focus is for.
    ///
    /// Command line ONLY -- deliberately not readable from a cfg. A stray config value that
    /// silently loads someone's save on every launch is a much worse failure than having to
    /// type a flag.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, true)]
    public class AxeAutoLoad : MonoBehaviour
    {
        private const string LoadFlag = "-axe-load=";
        private const string FocusFlag = "-axe-focus=";
        private static bool _done;

        private void Start()
        {
            if (_done) return;
            string save = null, focus = null;
            foreach (string arg in Environment.GetCommandLineArgs())
            {
                if (arg.StartsWith(LoadFlag, StringComparison.OrdinalIgnoreCase))
                    save = arg.Substring(LoadFlag.Length).Trim('"');
                else if (arg.StartsWith(FocusFlag, StringComparison.OrdinalIgnoreCase))
                    focus = arg.Substring(FocusFlag.Length).Trim('"');
            }
            if (string.IsNullOrEmpty(save)) return;
            _done = true;
            StartCoroutine(Load(save, focus));
        }

        private IEnumerator Load(string save, string focus)
        {
            // Let the menu settle; loading during its own start-up races the scene.
            yield return new WaitForSeconds(2f);
            Debug.Log("[AXE][AutoLoad] loading save '" + save + "'"
                      + (focus != null ? " and focusing '" + focus + "'" : " into the Tracking Station"));
            Game game;
            try
            {
                HighLogic.SaveFolder = save;
                game = GamePersistence.LoadGame("persistent", save, true, false);
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE][AutoLoad] could not load '" + save + "': " + e.Message);
                yield break;
            }
            if (game == null || game.flightState == null)
            {
                Debug.LogError("[AXE][AutoLoad] save '" + save + "' did not produce a game with a flight state.");
                yield break;
            }
            // Game.Start() reads HighLogic.CurrentGame internally, so assigning it is not
            // bookkeeping -- skip it and Start() throws an NRE with a stack that points at
            // the caller rather than at the missing assignment.
            HighLogic.CurrentGame = game;

            int idx = -1;
            if (!string.IsNullOrEmpty(focus))
            {
                // Index into the game's OWN vessel list; FlightGlobals is not populated yet.
                var protos = game.flightState.protoVessels;
                idx = protos.FindIndex(p => p != null && p.vesselName == focus);
                if (idx < 0)
                    idx = protos.FindIndex(p => p != null && p.vesselName != null
                            && p.vesselName.IndexOf(focus, StringComparison.OrdinalIgnoreCase) >= 0);
                if (idx < 0)
                    Debug.LogWarning("[AXE][AutoLoad] no vessel matching '" + focus
                        + "'; falling back to the Tracking Station. Known: "
                        + string.Join(", ", protos.Where(p => p != null).Select(p => p.vesselName).ToArray()));
            }

            if (idx >= 0)
            {
                Debug.Log("[AXE][AutoLoad] focusing vessel " + idx + " ("
                          + game.flightState.protoVessels[idx].vesselName + ")");
                bool ok = false;
                try
                {
                    FlightDriver.StartAndFocusVessel(game, idx);
                    ok = true;
                }
                catch (Exception e)
                {
                    Debug.LogError("[AXE][AutoLoad] StartAndFocusVessel failed: " + e);
                }
                if (ok) yield break;
            }

            try
            {
                game.startScene = GameScenes.TRACKSTATION;
                game.Start();
                Debug.Log("[AXE][AutoLoad] started into the Tracking Station.");
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE][AutoLoad] Game.Start() failed: " + e);
            }
        }
    }
}
