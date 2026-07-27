using System;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// Editor half of the airlaunch. Intercepts the stock Launch button (via a Harmony prefix on
    /// EditorLogic.goForLaunch — the same commit point RP-1 patches) and, when an airlaunch envelope is
    /// unlocked, offers the player a choice: launch normally to the runway, or configure an airlaunch and
    /// spawn already airborne. SPH only — a carrier drops spaceplanes, so the VAB launch button is left
    /// alone. The choice + release params are stashed in <see cref="AxeAirlaunchState"/>;
    /// <see cref="AxeAirlaunchFlight"/> carries out the teleport once the vessel spawns.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EditorAny, false)]
    public class AxeAirlaunchEditor : MonoBehaviour
    {
        internal static AxeAirlaunchEditor Instance;
        private static bool _patched;
        private static MethodInfo _goForLaunch;
        private static bool _resume;   // set while we re-invoke goForLaunch, so the prefix lets it pass

        private bool _open;
        private bool _launchQueued;   // defer the actual (re)launch out of OnGUI to Update
        private Rect _win = new Rect(Screen.width / 2 - 175, Screen.height / 2 - 170, 350, 10);
        private AxeAirlaunchTechLevel _lvl;
        private AxeAirlaunchParams _p;
        private string _sAlt, _sVel, _sHead, _sDist, _sBear, _err;
        private double _shipMassT;
        private Vector3 _shipSize;
        private bool _fits;
        private string _fitReason;
        private static GUIStyle _warn;

        private void Awake()
        {
            Instance = this;
            if (_patched) return;
            _patched = true;
            _goForLaunch = AccessTools.Method(typeof(EditorLogic), "goForLaunch");
            if (_goForLaunch == null)
            {
                Debug.LogError("[AXE] airlaunch: EditorLogic.goForLaunch not found; editor hook disabled.");
                return;
            }
            var prefix = new HarmonyMethod(typeof(AxeAirlaunchEditor)
                .GetMethod(nameof(GoForLaunchPrefix), BindingFlags.Static | BindingFlags.NonPublic));
            new Harmony("rpaxe.airlaunch").Patch(_goForLaunch, prefix: prefix);
            Debug.Log("[AXE] airlaunch editor hook applied (EditorLogic.goForLaunch).");
        }

        private void OnDestroy()
        {
            if (_open) ReleaseStockLaunchLock();   // never leave the editor locked behind a live window
            if (Instance == this) Instance = null;
        }

        private void Update()
        {
            // Trigger the (re)launch outside OnGUI so the scene transition never fires mid-GUILayout.
            if (!_launchQueued) return;
            _launchQueued = false;
            Resume();
        }

        /// <summary>Harmony prefix. Returns false to suppress the stock launch while our window is up.</summary>
        private static bool GoForLaunchPrefix()
        {
            if (_resume) { _resume = false; return true; }          // our own re-invoke -> let it launch
            if (Instance == null) return true;
            if (Instance._open) return false;                        // window already up, keep suppressing
            if (EditorDriver.editorFacility != EditorFacility.SPH) return true;   // airlaunch is an SPH feature
            if (!AxeAirlaunchTechLevel.AnyUnlocked()) return true;   // no capability -> normal launch
            return !Instance.OpenWindow();                           // opened -> suppress; couldn't -> proceed
        }

        /// <summary>
        /// Release the editor-wide lock stock takes on the way into a launch. EditorLogic.launchVessel()
        /// calls Lock(load, exit, save, "EditorLogic_launchSequence") before running the pre-flight tests,
        /// and only goForLaunch() / abortLaunch() take it back off. We suppress goForLaunch to put our
        /// window up, so anything that closes that window without letting the launch through has to drop
        /// the lock itself — otherwise the editor is left frozen: no launch, save, load, exit or staging,
        /// with no in-game way out short of the F7 panic key.
        /// </summary>
        private static void ReleaseStockLaunchLock()
        {
            InputLockManager.RemoveControlLock("EditorLogic_launchSequence");
        }

        /// <summary>Prime and show the window. Returns true if it opened (=> the launch should be suppressed).</summary>
        private bool OpenWindow()
        {
            _lvl = AxeAirlaunchTechLevel.GetCurrentLevel();
            if (_lvl == null) return false;

            ShipConstruct ship = EditorLogic.fetch != null ? EditorLogic.fetch.ship : null;
            if (ship == null || ship.parts == null || ship.parts.Count == 0) return false;

            double t = 0;
            foreach (Part part in ship.parts) t += part.mass + part.GetResourceMass();
            _shipMassT = t;
            _shipSize = ShipConstruction.CalculateCraftSize(ship);
            _fits = _lvl.CanLaunch(_shipMassT, _shipSize, out _fitReason);

            _p = new AxeAirlaunchParams { Altitude = _lvl.MaxAltitude, Velocity = _lvl.MaxVelocity, Heading = 270, Distance = 0, Bearing = 90 };
            _sAlt = _p.Altitude.ToString("0");
            _sVel = _p.Velocity.ToString("0");
            _sHead = _p.Heading.ToString("0");
            _sDist = "0";
            _sBear = _p.Bearing.ToString("0");
            _err = null;
            _open = true;
            return true;
        }

        private void OnGUI()
        {
            if (!_open) return;
            GUI.skin = HighLogic.Skin;
            _win = GUILayout.Window(GetInstanceID(), _win, DrawWindow, "Airlaunch");
        }

        private void DrawWindow(int id)
        {
            GUILayout.BeginVertical();

            GUILayout.Label($"Envelope: ≤ {_lvl.MaxMass / 1000.0:0.#} t,  ≤ {_lvl.MaxAltitude:0} m,  ≤ {_lvl.MaxVelocity:0} m/s");
            GUILayout.Label($"Ship: {_shipMassT:0.#} t,  {_shipSize.x:0.#} x {_shipSize.y:0.#} x {_shipSize.z:0.#} m");
            if (!_fits) Warn(_fitReason);

            GUILayout.Space(4);
            Row("Altitude (m)", ref _sAlt);
            Row("Velocity (m/s)", ref _sVel);
            Row("Heading (°)", ref _sHead);
            Row("Downrange (km)", ref _sDist);
            Row("Bearing from site (°)", ref _sBear);
            ParseValidate();

            double fee = _lvl.LaunchCost;
            GUILayout.Label(fee > 0 ? $"Airlaunch fee: {fee:N0} funds" : "Airlaunch fee: none");
            if (_err != null) Warn(_err);

            GUILayout.Space(4);
            GUILayout.BeginHorizontal();
            GUI.enabled = _fits && _err == null;
            if (GUILayout.Button("Airlaunch")) DoAirlaunch(fee);
            GUI.enabled = true;
            if (GUILayout.Button("Max"))
            {
                _sAlt = _lvl.MaxAltitude.ToString("0");
                _sVel = _lvl.MaxVelocity.ToString("0");
            }
            if (GUILayout.Button("Runway")) { _open = false; _launchQueued = true; }   // real goForLaunch unlocks
            if (GUILayout.Button("Cancel")) { _open = false; ReleaseStockLaunchLock(); }
            GUILayout.EndHorizontal();

            GUILayout.EndVertical();
            GUI.DragWindow();
        }

        private void DoAirlaunch(double fee)
        {
            ParseValidate();
            if (!_fits || _err != null) return;

            if (Funding.Instance != null)   // career/science with funds; null in sandbox
            {
                if (Funding.Instance.Funds < fee)
                {
                    _err = $"Insufficient funds ({Funding.Instance.Funds:N0} < {fee:N0})";
                    return;
                }
                if (fee > 0) Funding.Instance.AddFunds(-fee, TransactionReasons.VesselRollout);
            }

            AxeAirlaunchState.SetPending(_p);
            _open = false;
            _launchQueued = true;
            Debug.Log($"[AXE] airlaunch armed: alt {_p.Altitude:0} m, vel {_p.Velocity:0} m/s, hdg {_p.Heading:0}°, fee {fee:N0}");
        }

        /// <summary>Re-run the stock launch we suppressed; the prefix waves it through via _resume.</summary>
        private void Resume()
        {
            _resume = true;
            try
            {
                _goForLaunch.Invoke(EditorLogic.fetch, null);
            }
            catch (Exception e)
            {
                _resume = false;
                Debug.LogError("[AXE] airlaunch: re-invoking goForLaunch failed: " + e);
            }
        }

        private void ParseValidate()
        {
            try
            {
                _p.Altitude = double.Parse(_sAlt);
                _p.Velocity = double.Parse(_sVel);
                _p.Heading = double.Parse(_sHead);
                _p.Distance = double.Parse(_sDist) * 1000.0;   // km -> m
                _p.Bearing = double.Parse(_sBear);
                _p.Validate(_lvl, out _err);
            }
            catch
            {
                _err = "Enter valid numbers";
            }
        }

        private static void Row(string label, ref string val)
        {
            GUILayout.BeginHorizontal();
            GUILayout.Label(label, GUILayout.Width(130));
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
    }
}
