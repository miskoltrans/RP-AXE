using System;
using KSP.UI.Screens;
using UnityEngine;

namespace RPAxe.Simulation
{
    /// <summary>
    /// Editor half of the simulation feature: an app-launcher button (VAB/SPH) that opens a small config
    /// window — pick a target world + orbit (Pe/Ap/inc, or "on the pad" for home) — and launches a
    /// throwaway simulated flight. The body chooser greys worlds that aren't unlocked yet (see
    /// <see cref="AxeSimulationGate"/>), so the progression is visible and aspirational.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EditorAny, false)]
    public class AxeSimulationEditor : MonoBehaviour
    {
        private static Texture2D _icon;
        private ApplicationLauncherButton _button;

        private bool _open, _chooser, _startQueued;
        private Rect _win = new Rect(Screen.width / 2 - 160, Screen.height / 2 - 150, 320, 10);
        private Rect _chooserWin = new Rect(Screen.width / 2 - 120, Screen.height / 2 - 180, 240, 10);
        private Vector2 _scroll;
        private AxeSimulationParams _p;
        private string _sPe = "200", _sAp = "200", _sInc = "0", _sDelay = "0", _sWarp = "0", _err;
        private static GUIStyle _warn, _dim;

        private void Start()
        {
            if (!AxeSimulation.FeatureEnabled) return;
            GameEvents.onGUIApplicationLauncherReady.Add(AddButton);
            if (ApplicationLauncher.Ready) AddButton();
        }

        private void OnDestroy()
        {
            GameEvents.onGUIApplicationLauncherReady.Remove(AddButton);
            RemoveButton();
            Remember();
            _open = false;
        }

        private void Update()
        {
            // Defer the real launch out of OnGUI so the scene transition never fires mid-GUILayout.
            if (!_startQueued) return;
            _startQueued = false;
            if (!AxeSimulation.StartSim(_p, out string err))
                ScreenMessages.PostScreenMessage("Simulation: " + err, 6f, ScreenMessageStyle.UPPER_CENTER);
        }

        // --- App launcher button ---

        private void AddButton()
        {
            if (_button != null || ApplicationLauncher.Instance == null) return;
            _button = ApplicationLauncher.Instance.AddModApplication(
                Open, Close, null, null, null, null,
                ApplicationLauncher.AppScenes.VAB | ApplicationLauncher.AppScenes.SPH,
                Icon());
        }

        private void RemoveButton()
        {
            if (_button != null && ApplicationLauncher.Instance != null)
                ApplicationLauncher.Instance.RemoveModApplication(_button);
            _button = null;
        }

        private void Open()
        {
            EnsureParams();
            _chooser = false;
            _err = null;
            _open = true;
        }

        private void Close()
        {
            Remember();
            _open = false;
        }

        private void CloseFromCode()
        {
            Remember();
            _open = false;
            _button?.SetFalse(false);
        }

        /// <summary>Seed the window from the last simulation the player set up (see
        /// <see cref="AxeSimulationPrefs"/>); first ever run falls back to "home, on the pad".</summary>
        private void EnsureParams()
        {
            if (_p != null) return;

            AxeSimulationPrefs.Load();
            CelestialBody body = AxeSimulationPrefs.ResolveBody();
            bool home = Planetarium.fetch != null && body == Planetarium.fetch.Home;

            _p = new AxeSimulationParams
            {
                Body = body,
                InOrbit = !home || AxeSimulationPrefs.InOrbit,
                Periapsis = 200000,
                Apoapsis = 200000,
                Inclination = 0,
                DelaySeconds = 0,
            };

            _sPe = AxeSimulationPrefs.Pe;
            _sAp = AxeSimulationPrefs.Ap;
            _sInc = AxeSimulationPrefs.Inc;
            _sDelay = AxeSimulationPrefs.Delay;
            _sWarp = AxeSimulationPrefs.Warp;
        }

        /// <summary>Persist the current window contents as next session's defaults.</summary>
        private void Remember()
        {
            if (_p == null) return;
            AxeSimulationPrefs.Capture(_p.Body, _p.InOrbit, _sPe, _sAp, _sInc, _sDelay, _sWarp);
            AxeSimulationPrefs.Save();
        }

        // --- GUI ---

        private void OnGUI()
        {
            if (!_open) return;
            GUI.skin = HighLogic.Skin;
            if (_chooser)
                _chooserWin = GUILayout.Window(GetInstanceID() + 1, _chooserWin, DrawChooser, "Simulate — target");
            else
                _win = GUILayout.Window(GetInstanceID(), _win, DrawConfig, "Simulate");
        }

        private void DrawConfig(int id)
        {
            EnsureParams();
            GUILayout.BeginVertical();

            GUILayout.BeginHorizontal();
            GUILayout.Label("Target:", GUILayout.Width(70));
            GUILayout.Label(_p.Body != null ? _p.Body.bodyName : "—");
            GUILayout.FlexibleSpace();
            if (GUILayout.Button("Select", GUILayout.Width(80))) _chooser = true;
            GUILayout.EndHorizontal();

            bool isHome = Planetarium.fetch != null && _p.Body == Planetarium.fetch.Home;
            if (isHome)
            {
                _p.InOrbit = GUILayout.Toggle(_p.InOrbit, " Start in orbit (otherwise on the launch pad)");
            }
            else
            {
                _p.InOrbit = true;
                Dim("Other worlds start in orbit — fly down to test descent/ascent.");
            }

            if (_p.InOrbit)
            {
                Row("Periapsis (km)", ref _sPe);
                Row("Apoapsis (km)", ref _sAp);
                Row("Inclination (deg)", ref _sInc);
                Row("Pad delay (s)", ref _sDelay);
                if (_p.Body != null)
                {
                    double minKm = _p.Body.atmosphere ? _p.Body.atmosphereDepth / 1000.0 : 0.0;
                    double maxKm = (_p.Body.sphereOfInfluence - _p.Body.Radius) / 1000.0;
                    Dim($"Orbit band ≈ {minKm:0}–{maxKm:0} km  (Pe = Ap for circular)");
                }

                // Arbitrary time is a rung-B capability (unlocks with the same node as other worlds).
                if (AxeSimulationGate.NodeResearched(AxeSimulationGate.RungBNode))
                    Row("Warp forward (days)", ref _sWarp);
            }

            GUILayout.Space(4);
            if (_err != null) Warn(_err);

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Simulate")) TrySimulate();
            if (GUILayout.Button("Close")) CloseFromCode();
            GUILayout.EndHorizontal();

            GUILayout.EndVertical();
            GUI.DragWindow();
        }

        private void DrawChooser(int id)
        {
            GUILayout.BeginVertical();
            _scroll = GUILayout.BeginScrollView(_scroll, GUILayout.Height(320));
            foreach (CelestialBody b in FlightGlobals.Bodies)
            {
                bool can = AxeSimulationGate.CanSimulate(b);
                GUI.enabled = can;
                if (GUILayout.Button(b.bodyName))
                {
                    _p.Body = b;
                    if (Planetarium.fetch != null && b != Planetarium.fetch.Home) _p.InOrbit = true;
                    _chooser = false;
                }
                GUI.enabled = true;
            }
            GUILayout.EndScrollView();

            if (!AxeSimulationGate.NodeResearched(AxeSimulationGate.RungBNode))
                Dim("Locked worlds need: " + AxeSimulationGate.RungBTitle());

            if (GUILayout.Button("Back")) _chooser = false;
            GUILayout.EndVertical();
            GUI.DragWindow();
        }

        private void TrySimulate()
        {
            _err = null;
            if (_p.Body == null) { _err = "Pick a target world."; return; }
            if (!AxeSimulationGate.CanSimulate(_p.Body))
            {
                _err = "Requires " + AxeSimulationGate.RungBTitle() + ".";
                return;
            }

            if (_p.InOrbit)
            {
                if (!double.TryParse(_sPe, out double peKm)) { _err = "Enter a valid periapsis."; return; }
                if (!double.TryParse(_sAp, out double apKm)) { _err = "Enter a valid apoapsis."; return; }
                _p.Periapsis = peKm * 1000.0;
                _p.Apoapsis = apKm * 1000.0;
                double.TryParse(_sInc, out double inc);
                _p.Inclination = inc;
                int.TryParse(_sDelay, out int d);
                _p.DelaySeconds = Math.Max(0, d);

                _p.WarpDays = 0;
                if (AxeSimulationGate.NodeResearched(AxeSimulationGate.RungBNode) &&
                    double.TryParse(_sWarp, out double days))
                    _p.WarpDays = Math.Max(0, days);
            }

            _startQueued = true;   // Update() performs the actual launch
            CloseFromCode();
        }

        // --- helpers (match AxeAirlaunchEditor style) ---

        private static void Row(string label, ref string val)
        {
            GUILayout.BeginHorizontal();
            GUILayout.Label(label, GUILayout.Width(150));
            val = GUILayout.TextField(val ?? "", GUILayout.Width(90));
            GUILayout.EndHorizontal();
        }

        private static void Warn(string s)
        {
            if (_warn == null)
            {
                _warn = new GUIStyle(GUI.skin.label);
                _warn.normal.textColor = XKCDColors.Orange;
                _warn.wordWrap = true;
            }
            GUILayout.Label(s, _warn);
        }

        private static void Dim(string s)
        {
            if (_dim == null)
            {
                _dim = new GUIStyle(GUI.skin.label);
                _dim.normal.textColor = new Color(0.7f, 0.7f, 0.7f);
                _dim.wordWrap = true;
                _dim.fontSize = Mathf.Max(10, _dim.fontSize - 2);
            }
            GUILayout.Label(s, _dim);
        }

        private static Texture2D Icon()
        {
            if (_icon != null) return _icon;
            const int N = 38;
            _icon = new Texture2D(N, N, TextureFormat.ARGB32, false);
            Color clear = new Color(0, 0, 0, 0);
            Color disc = new Color(0.25f, 0.55f, 0.95f);
            Color ring = new Color(0.90f, 0.90f, 0.98f);
            var px = new Color[N * N];
            Vector2 c = new Vector2((N - 1) / 2f, (N - 1) / 2f);
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = Vector2.Distance(new Vector2(x, y), c);
                    Color col = clear;
                    if (d < 10f) col = disc;                 // planet
                    else if (d > 13.5f && d < 15.5f) col = ring;  // orbit ring
                    px[y * N + x] = col;
                }
            _icon.SetPixels(px);
            _icon.Apply();
            return _icon;
        }
    }
}
