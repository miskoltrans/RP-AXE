using System;
using System.Collections;
using KSP.UI.Screens;
using KSP.UI.Screens.Flight;
using UnityEngine;
using UnityEngine.UI;

namespace RPAxe.Simulation
{
    /// <summary>
    /// Flight half of the simulation. When a simulated flight spawns it: suppresses autosave, hijacks the
    /// recovery button to open the sim controls instead of recovering, teleports the craft to the chosen
    /// orbit (after an optional pad delay), and offers free Restart / Revert-to-Editor — which work even in
    /// a reverts-off career because <see cref="AxeSimulation.StartSim"/> force-enabled reverts for the sim.
    ///
    /// Leaving to the editor / space centre triggers <see cref="AxeSimulationRestore"/>, which swaps the
    /// real save back. Mirrors ROUtils/KCT <c>FlightAddon</c> + <c>ProcessSimulation</c>.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Flight, false)]
    public class AxeSimulationFlight : MonoBehaviour
    {
        private enum Pending { None, Restart, Revert }

        private bool _showWindow;
        private Pending _pending;
        private Rect _win = new Rect(Screen.width / 2 - 135, 40, 270, 10);
        private static GUIStyle _hdr;

        private void Start()
        {
            if (!AxeSimulation.IsSimulatedFlight) return;
            _showWindow = true;
            if (HighLogic.CurrentGame?.Parameters?.Flight != null)
                HighLogic.CurrentGame.Parameters.Flight.CanAutoSave = false;
            // Instance handler, never a static one: GameEvents' EvtDelegate ctor dereferences the target.
            GameEvents.OnRevertToLaunchFlightState.Add(OnRevertToLaunch);
            StartCoroutine(HookRecoveryButton());
            StartCoroutine(MoveRoutine());
        }

        private void OnDestroy()
        {
            GameEvents.OnRevertToLaunchFlightState.Remove(OnRevertToLaunch);
        }

        /// <summary>
        /// A revert-to-launch re-runs this scene from the pad spawn, so the sim has to place the craft in
        /// its orbit again — drop the "already moved" latch. Hooked on the event rather than done in the
        /// Restart button below because stock's own pause menu reverts too (PauseMenu calls
        /// FlightDriver.RevertToLaunch directly, gated on CanRestart, which a sim force-enables), and a
        /// player who takes that door would otherwise be dumped on the pad with the simulated orbit gone.
        /// The event fires inside RevertToLaunch, before the scene reloads, so the clear lands in time.
        /// </summary>
        private void OnRevertToLaunch(FlightState st)
        {
            if (AxeSimulation.IsSimulatedFlight) AxeSimulation.Params?.Reset();
        }

        private void Update()
        {
            // Run reverts out of OnGUI so the scene transition never fires mid-GUILayout.
            if (_pending == Pending.None) return;
            Pending action = _pending;
            _pending = Pending.None;

            if (action == Pending.Restart)
            {
                AxeSimulationSave.EnableSimLocks();
                // The Moved latch is cleared by OnRevertToLaunch, so it only drops if the revert really
                // happens — clearing it here would strand it cleared when CanRevertToPostInit is false.
                if (FlightDriver.CanRevertToPostInit) FlightDriver.RevertToLaunch();
            }
            else if (action == Pending.Revert)
            {
                EditorFacility f = AxeSimulation.Params != null ? AxeSimulation.Params.Facility : EditorFacility.VAB;
                if (FlightDriver.CanRevertToPrelaunch) FlightDriver.RevertToPrelaunch(f);
            }
        }

        // Redirect the recovery button to the sim controls (mirrors KCT FlightAddon). Retries because the
        // altimeter widget isn't present for the first frame or two.
        private IEnumerator HookRecoveryButton()
        {
            for (int i = 0; i < 20; i++)
            {
                var alt = FindObjectOfType<AltimeterSliderButtons>();
                if (alt != null && alt.vesselRecoveryButton != null)
                {
                    alt.vesselRecoveryButton.onClick = new Button.ButtonClickedEvent();
                    alt.vesselRecoveryButton.onClick.AddListener(() => _showWindow = true);
                    yield break;
                }
                yield return new WaitForSeconds(0.25f);
            }
        }

        private IEnumerator MoveRoutine()
        {
            AxeSimulationParams p = AxeSimulation.Params;
            if (p == null || !p.InOrbit || p.Moved) yield break;

            var spawn = new AxeSpawnWait();
            yield return StartCoroutine(spawn.Run());
            if (spawn.Vessel == null)
            {
                Debug.LogWarning("[AXE][Sim] no vessel finished spawning; not moving to orbit.");
                yield break;
            }

            for (int i = p.DelaySeconds; i > 0; i--)
            {
                ScreenMessages.PostScreenMessage($"Moving to orbit in {i}...", 1f, ScreenMessageStyle.UPPER_CENTER);
                yield return new WaitForSeconds(1f);
            }

            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null) yield break;
            yield return new WaitForEndOfFrame();

            try
            {
                AxeVesselTeleport.PutInOrbit(v, p.Body, p.Periapsis, p.Apoapsis, p.Inclination, p.Lan, p.ArgPe);
                // Advance time only once the vessel is on rails (SetOrbit did GoOnRails) — safe to move the
                // whole system to the target date without disturbing physics.
                if (p.WarpDays > 0)
                    Planetarium.SetUniversalTime(Planetarium.GetUniversalTime() + p.WarpDays * 86400.0);
            }
            catch (Exception e) { Debug.LogError("[AXE][Sim] teleport to orbit failed: " + e); yield break; }

            p.Moved = true;
            string when = p.WarpDays > 0 ? $", +{p.WarpDays:0.#} d" : "";
            ScreenMessages.PostScreenMessage(
                $"Simulation — orbiting {p.Body.bodyName} {p.Periapsis / 1000.0:0}×{p.Apoapsis / 1000.0:0} km{when}",
                6f, ScreenMessageStyle.UPPER_CENTER);
        }

        private void OnGUI()
        {
            if (!AxeSimulation.IsSimulatedFlight) return;
            GUI.skin = HighLogic.Skin;
            if (_showWindow)
                _win = GUILayout.Window(GetInstanceID(), _win, DrawWindow, "Simulation");
            else if (GUI.Button(new Rect(Screen.width / 2 - 40, 0, 80, 24), "SIM"))
                _showWindow = true;
        }

        private void DrawWindow(int id)
        {
            GUILayout.BeginVertical();
            Header("This is a simulation.");
            GUILayout.Label("Nothing here is saved — funds, science and time revert on exit.");
            GUILayout.Space(4);

            GUI.enabled = FlightDriver.CanRevertToPostInit;
            if (GUILayout.Button("Restart Simulation")) _pending = Pending.Restart;
            GUI.enabled = FlightDriver.CanRevertToPrelaunch;
            if (GUILayout.Button("Revert to Editor")) _pending = Pending.Revert;
            GUI.enabled = true;

            if (GUILayout.Button("Close")) _showWindow = false;

            GUILayout.EndVertical();
            GUI.DragWindow();
        }

        private static void Header(string s)
        {
            if (_hdr == null)
            {
                _hdr = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold };
                _hdr.normal.textColor = XKCDColors.Orange;
            }
            GUILayout.Label(s, _hdr);
        }
    }
}
