using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using System.Text;
using CommNet;                 // CommNetHome (RA subclasses it, so FindObjectsOfType finds them all)
using UnityEngine;

namespace RPAxe.AutoTest
{
    /// <summary>
    /// AutoTest self-check for FREE KSC switching (the KSCSwitcher mod, which RELOCATES the single KSC
    /// to another real-world site — not multi-pad). Verifies the downstream behaviour we rely on:
    ///   1. the active site actually changes (regexKSP KSCSiteManager.lastSite),
    ///   2. the CommNet ground-station network is unaffected (fixed real-world stations incl. one at
    ///      every launch site — nothing needs to "follow" the KSC), and
    ///   3. the choice PERSISTS — regexKSP.LastKSC.OnSave writes LastLaunchSite, then a real SaveGame
    ///      lands it on disk (the harness greps the .sfs afterwards).
    ///
    /// IMPORTANT: KSCSwitcher's switch UI + its LastKSC scenario module live in the TRACKING STATION
    /// scene only ([KSPAddon(Startup.TrackingStation)]). Switching from the Space Center via the raw
    /// API sets the live site but LastKSC.OnSave never fires there, so it would not persist. This test
    /// therefore runs the switch IN THE TRACKING STATION, the same scene the player uses.
    /// </summary>
    internal static class AxeKscSwitchSelfTest
    {
        private const string Tag = "[AXE][AutoTest][KSC] ";

        // Set by the Space Center driver once its screen walk is done; consumed by RunSequence to load
        // the Tracking Station, where the TS driver below performs the actual switch test.
        public static bool TrackingStationPhaseRequested;
        private static bool _tsDone;
        public static void RequestTrackingStationPhase() => TrackingStationPhaseRequested = true;

        // --- regexKSP reflection handles (bound once) ---
        private static bool _bound, _ok;
        private static object _sites;                        // regexKSP.KSCSiteManager instance
        private static FieldInfo _fiLastSite, _fiDefaultSite;
        private static MethodInfo _miGetSiteByName;          // ConfigNode GetSiteByName(string)
        private static MethodInfo _miSetSiteAndResetCamera;  // static void (ConfigNode, bool)
        private static PropertyInfo _piLastKscFetch;         // static regexKSP.LastKSC fetch
        private static FieldInfo _fiLastKscLastSite;         // regexKSP.LastKSC.lastSite
        private static MethodInfo _miLastKscOnSave;          // OnSave(ConfigNode)

        private const double KourouLat = 5.239380, KourouLon = -52.768487;
        private const double CapeLat = 28.608389, CapeLon = -80.604333;

        private static bool Bind()
        {
            if (_bound) return _ok;
            _bound = true;
            try
            {
                Assembly a = AssemblyLoader.loadedAssemblies
                    .FirstOrDefault(la => string.Equals(la.name, "KSCSwitcher", StringComparison.OrdinalIgnoreCase))?.assembly;
                if (a == null) { Debug.LogWarning(Tag + "KSCSwitcher assembly not loaded; skipping self-test."); return false; }

                Type tLoader = a.GetType("regexKSP.KSCLoader");
                object loader = tLoader?.GetField("instance", BindingFlags.Public | BindingFlags.Static)?.GetValue(null);
                _sites = tLoader?.GetField("Sites", BindingFlags.Public | BindingFlags.Instance)?.GetValue(loader);

                Type tMgr = a.GetType("regexKSP.KSCSiteManager");
                _fiLastSite = tMgr?.GetField("lastSite", BindingFlags.Public | BindingFlags.Instance);
                _fiDefaultSite = tMgr?.GetField("defaultSite", BindingFlags.Public | BindingFlags.Instance);
                _miGetSiteByName = tMgr?.GetMethod("GetSiteByName", BindingFlags.Public | BindingFlags.Instance);

                Type tSw = a.GetType("regexKSP.KSCSwitcher");
                _miSetSiteAndResetCamera = tSw?.GetMethod("SetSiteAndResetCamera", BindingFlags.Public | BindingFlags.Static);

                Type tLast = a.GetType("regexKSP.LastKSC");
                _piLastKscFetch = tLast?.GetProperty("fetch", BindingFlags.Public | BindingFlags.Static);
                _fiLastKscLastSite = tLast?.GetField("lastSite", BindingFlags.Public | BindingFlags.Instance);
                _miLastKscOnSave = tLast?.GetMethod("OnSave", BindingFlags.Public | BindingFlags.Instance, null, new[] { typeof(ConfigNode) }, null);

                _ok = _sites != null && _fiLastSite != null && _miGetSiteByName != null && _miSetSiteAndResetCamera != null;
                if (!_ok)
                    Debug.LogError(Tag + "bind failed (sites=" + (_sites != null) + " last=" + (_fiLastSite != null) +
                                   " get=" + (_miGetSiteByName != null) + " set=" + (_miSetSiteAndResetCamera != null) + ")");
                return _ok;
            }
            catch (Exception e) { Debug.LogError(Tag + "bind threw: " + e); return false; }
        }

        private static string ActiveSite()
        {
            string s = _fiLastSite?.GetValue(_sites) as string;
            if (string.IsNullOrEmpty(s)) s = _fiDefaultSite?.GetValue(_sites) as string;
            return string.IsNullOrEmpty(s) ? "(null)" : s;
        }

        /// <summary>Runs in the Tracking Station scene: switch site, prove persistence, dump comms, save.</summary>
        private static IEnumerator RunTrackingStation()
        {
            Debug.Log(Tag + "=== free-switch downstream self-test (Tracking Station scene) ===");

            // KSCSwitcher builds its LastKSC module when its own TS addon runs; wait for it.
            float t = 0f;
            while (t < 15f && (!Bind() || LastKscFetch() == null)) { t += Time.unscaledDeltaTime; yield return null; }
            if (!Bind()) { Debug.LogError(Tag + "KSCSwitcher not bound; aborting."); yield break; }

            CelestialBody home = FlightGlobals.GetHomeBody();
            string before = ActiveSite();
            string target = string.Equals(before, "fr_kourou", StringComparison.OrdinalIgnoreCase) ? "us_cape_canaveral" : "fr_kourou";
            double tgtLat = target == "fr_kourou" ? KourouLat : CapeLat;
            double tgtLon = target == "fr_kourou" ? KourouLon : CapeLon;
            Debug.Log(Tag + "active site BEFORE = " + before + "; switching to " + target);

            DumpHomes("BEFORE", home);

            ConfigNode cn = _miGetSiteByName.Invoke(_sites, new object[] { target }) as ConfigNode;
            if (cn == null) { Debug.LogError(Tag + "GetSiteByName('" + target + "') returned null; aborting."); yield break; }
            bool switched = false;
            try { _miSetSiteAndResetCamera.Invoke(null, new object[] { cn, false }); switched = true; }
            catch (Exception e) { Debug.LogError(Tag + "SetSiteAndResetCamera threw: " + e); }
            if (!switched) yield break;

            yield return AutoTestUtil.Dwell(2.5f);   // let CommNet / PQS settle

            string after = ActiveSite();
            bool siteChanged = string.Equals(after, target, StringComparison.OrdinalIgnoreCase);
            Debug.Log(Tag + "active site AFTER = " + after + "  (siteChanged=" + siteChanged + ")");
            DumpHomes("AFTER", home);
            bool siteHasStation = HomeNear(tgtLat, tgtLon, 0.6, home);
            Debug.Log(Tag + "co-located ground station at " + target + "? " + siteHasStation +
                      " (expect True — comms need no 'home follow')");

            // --- Persistence mechanism: what LastKSC.OnSave would serialize right now ---
            object lastKsc = LastKscFetch();
            string fieldVal = "(no LastKSC)";
            string onSaveVal = "(not probed)";
            if (lastKsc != null)
            {
                try { fieldVal = _fiLastKscLastSite?.GetValue(lastKsc) as string ?? "(null)"; } catch (Exception e) { fieldVal = "ERR " + e.Message; }
                try
                {
                    var probe = new ConfigNode();
                    _miLastKscOnSave?.Invoke(lastKsc, new object[] { probe });
                    onSaveVal = probe.GetValue("LastLaunchSite") ?? "(absent)";
                }
                catch (Exception e) { onSaveVal = "ERR " + e.Message; }
            }
            Debug.Log(Tag + "LastKSC.fetch.lastSite=" + fieldVal + " ; OnSave writes LastLaunchSite=" + onSaveVal);

            // --- End-to-end: a real save; harness then greps saves/<folder>/persistent.sfs ---
            try
            {
                GamePersistence.SaveGame("persistent", HighLogic.SaveFolder, SaveMode.OVERWRITE);
                Debug.Log(Tag + "SaveGame('persistent','" + HighLogic.SaveFolder + "') done.");
            }
            catch (Exception e) { Debug.LogError(Tag + "SaveGame threw: " + e); }

            bool persistOk = string.Equals(onSaveVal, target, StringComparison.OrdinalIgnoreCase);
            Debug.Log(Tag + "RESULT siteChanged=" + siteChanged + " persistMechanism=" + persistOk +
                      " coLocatedStation=" + siteHasStation +
                      ((siteChanged && persistOk && siteHasStation) ? "  => PASS" : "  => CHECK LOG"));
        }

        private static object LastKscFetch()
        {
            try { return _piLastKscFetch?.GetValue(null); } catch { return null; }
        }

        // --- CommNet ground-station helpers (comms already verified; kept as context in the dump) ---

        private static void DumpHomes(string when, CelestialBody body)
        {
            try
            {
                CommNetHome[] homes = UnityEngine.Object.FindObjectsOfType<CommNetHome>();
                if (homes == null || homes.Length == 0) { Debug.LogWarning(Tag + when + ": no CommNetHome objects found."); return; }
                var sb = new StringBuilder();
                sb.Append(Tag).Append(when).Append(": ").Append(homes.Length).Append(" ground node(s). Sample: ");
                foreach (CommNetHome h in homes.Take(6))
                {
                    (double la, double lo, bool have) = HomeLatLon(h, body);
                    sb.Append(NameOf(h)).Append('(').Append(have ? la.ToString("F2") + "," + lo.ToString("F2") : "?").Append(") ");
                }
                Debug.Log(sb.ToString());
            }
            catch (Exception e) { Debug.LogError(Tag + "DumpHomes threw: " + e); }
        }

        private static bool HomeNear(double lat, double lon, double tolDeg, CelestialBody body)
        {
            foreach (CommNetHome h in UnityEngine.Object.FindObjectsOfType<CommNetHome>())
            {
                (double la, double lo, bool have) = HomeLatLon(h, body);
                if (!have) continue;
                if (Math.Abs(la - lat) <= tolDeg && Math.Abs(AngleDiff(lo, lon)) <= tolDeg) return true;
            }
            return false;
        }

        private static string NameOf(CommNetHome h)
        {
            try { if (!string.IsNullOrEmpty(h.nodeName)) return h.nodeName; } catch { }
            return h.GetType().Name;
        }

        private static (double, double, bool) HomeLatLon(CommNetHome h, CelestialBody body)
        {
            if (h == null || body == null) return (0, 0, false);
            try
            {
                FieldInfo cf = h.GetType().GetField("comm",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.FlattenHierarchy);
                object comm = cf?.GetValue(h);
                if (comm != null)
                {
                    FieldInfo pf = comm.GetType().GetField("precisePosition") ?? comm.GetType().GetField("position");
                    if (pf != null)
                    {
                        object pv = pf.GetValue(comm);
                        Vector3d pos;
                        if (pv is Vector3d dv) pos = dv;
                        else if (pv is Vector3 v3) pos = new Vector3d(v3.x, v3.y, v3.z);
                        else pos = Vector3d.zero;
                        if (pos.magnitude > 1) return (body.GetLatitude(pos), body.GetLongitude(pos), true);
                    }
                }
            }
            catch { }
            try
            {
                Vector3 tp = h.transform.position;
                Vector3d pos = new Vector3d(tp.x, tp.y, tp.z);
                if (pos.magnitude > 1) return (body.GetLatitude(pos), body.GetLongitude(pos), true);
            }
            catch { }
            return (0, 0, false);
        }

        private static double AngleDiff(double a, double b)
        {
            double d = (a - b) % 360.0;
            if (d > 180) d -= 360;
            if (d < -180) d += 360;
            return d;
        }

        /// <summary>Tracking Station scene driver: once the Space Center phase requested it, run the
        /// switch test here (where KSCSwitcher's UI + LastKSC live), then quit.</summary>
        [KSPAddon(KSPAddon.Startup.TrackingStation, false)]
        public class AxeKscSwitchTSDriver : MonoBehaviour
        {
            private void Start()
            {
                AutoTestConfig.EnsureLoaded();
                if (!AutoTestConfig.Enabled || !TrackingStationPhaseRequested || _tsDone) return;
                if (HighLogic.CurrentGame == null) return;
                _tsDone = true;
                StartCoroutine(Sequence());
            }

            private IEnumerator Sequence()
            {
                yield return AutoTestUtil.Dwell(AutoTestConfig.SettleSeconds);
                yield return RunTrackingStation();

                if (AutoTestConfig.QuitWhenDone)
                {
                    Debug.Log(Tag + "test finished; quitting KSP in " + AutoTestConfig.QuitDelaySeconds + "s...");
                    yield return AutoTestUtil.Dwell(AutoTestConfig.QuitDelaySeconds);
                    AutoTestUtil.HardQuit();
                }
            }
        }
    }
}
