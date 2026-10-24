using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using HarmonyLib;
using UnityEngine;

namespace RPAxe.AutoTest
{
    /// <summary>
    /// AutoTest flight phase: the over-capacity control corruption, measured in a real flight scene.
    ///
    /// Launches a one-part probe (picked from the loaded parts: an uncrewed command part with a reaction
    /// wheel and AXE avionics), sets it into a 300 km circular orbit, then for each overload level
    /// (sigma = NoiseFor(1.02 / 1.05 / 1.10 / 1.20), pinned through AxeAvionicsController.TestNoiseOverride):
    ///   * TRANSFER -- a scripted command (a held yaw plus a moving pitch) goes in, the corrupted command
    ///     comes out: how far the signal is bent, in stick units and in degrees off-axis;
    ///   * HOLD -- a PD attitude controller (full stick at 10 deg of error, gains from a measured
    ///     authority matrix) holds a fixed inertial direction through a "burn" (throttle commanded, which
    ///     is what keeps the corruption armed; the probe has no engine): how far off it ends up.
    /// Every level runs twice: SHIPPED (CorruptionPasses inside one registration) and 0.9.0 REBUILT the way
    /// it actually happened (one pass, AxeFlightControlLast registered a second time under another Harmony
    /// id), so "the restore matches what was played" is measured on the same craft, not argued.
    ///
    /// Hard checks (RESULT FAIL if any breaks): one AXE prefix + postfix on Vessel.FeedInputFeed and on
    /// ModuleRCS.Update; sigma 0 passes the command through untouched; a zero command at full sigma
    /// stays zero (zero in, zero out); the controller holds within 1 deg when clean (else the HOLD
    /// numbers mean nothing). Everything else is reported, not judged. Samples go to
    /// &lt;KSP&gt;/axe_autotest/avionics-flight.csv.
    ///
    /// Opt in with `avionicsTest = true` in AutoTest.cfg or `-axe-autotest-avionics` on the command line.
    /// </summary>
    internal static class AxeAvionicsFlightTest
    {
        internal const string Tag = "[AXE][AutoTest][AVI-FLIGHT] ";
        internal const string CmdFlag = "-axe-autotest-avionics";
        const string TestHarmonyId = "AxeAutoTest.avionics.hooks";
        const string DoubleHarmonyId = "AxeAutoTest.avionics.double";

        internal static readonly float[] Overloads = { 0f, 0.02f, 0.05f, 0.10f, 0.20f };
        const float SettleSec = 5f, TransferSec = 3f, RecoverSec = 6f, HoldSec = 12f;
        const float FullStickErrDeg = 10f;   // the PD commands full stick at 10 degrees off target

        internal static bool FlightPhaseRequested { get; private set; }
        internal static bool Ran;
        internal static void RequestFlightPhase() => FlightPhaseRequested = true;

        // ------------------------------------------------------------------ launch (Space Center scene)

        internal static bool Launch()
        {
            AvailablePart ap = PickProbe();
            if (ap == null)
            {
                Debug.LogError(Tag + "FAIL: no uncrewed command part with a reaction wheel, AXE avionics and EC is loaded");
                return false;
            }
            string dir = Path.Combine(KSPUtil.ApplicationRootPath, "axe_autotest");
            Directory.CreateDirectory(dir);
            string path = Path.Combine(dir, "AxeAvionicsTest.craft");
            File.WriteAllText(path, CraftText(ap));
            Debug.Log(Tag + "probe " + ap.name + " (\"" + ap.title + "\", " + ap.partPrefab.mass.ToString("0.###") + " t), craft " + path);
            VesselCrewManifest manifest = VesselCrewManifest.FromConfigNode(ConfigNode.Load(path));
            FlightDriver.StartWithNewLaunch(path, "Squad/Flags/default", "LaunchPad", manifest);
            return true;
        }

        /// <summary>The candidate with the most wheel torque per tonne. NOT the lightest: RO wheels are
        /// realistic, and the lightest bus (SSTL-150, 0.1 t) measured 0.001 rad/s^2 per unit stick -- far
        /// too slow for a hold to settle inside the test's windows (first run, 2026-10-24).</summary>
        static AvailablePart PickProbe()
        {
            AvailablePart best = null;
            float bestScore = 0f;
            foreach (AvailablePart ap in PartLoader.LoadedPartsList)
            {
                Part p = ap?.partPrefab;
                if (p == null || ap.TechHidden || p.mass <= 0f) continue;
                bool cmd = false, axe = false;
                float torque = 0f;
                foreach (PartModule m in p.Modules)
                {
                    if (m is ModuleCommand mc && mc.minimumCrew == 0) cmd = true;
                    else if (m is ModuleReactionWheel rw) torque = Mathf.Min(rw.PitchTorque, Mathf.Min(rw.YawTorque, rw.RollTorque));
                    else if (m.moduleName == "ModuleAxeAvionics" || m.moduleName == "ModuleAxeFixedAvionics") axe = true;
                }
                if (!(cmd && axe) || torque <= 0f || !p.Resources.Contains("ElectricCharge")) continue;
                float score = torque / p.mass;
                if (score > bestScore) { best = ap; bestScore = score; }
            }
            if (best != null)
                Debug.Log(Tag + "picked for wheel torque per tonne: " + bestScore.ToString("0.###") + " kN·m/t");
            return best;
        }

        static string CraftText(AvailablePart ap)
        {
            var sb = new StringBuilder();
            sb.AppendLine("ship = AXE avionics flight test");
            sb.AppendLine("version = 1.12.5");
            sb.AppendLine("description = Generated by AxeAvionicsFlightTest");
            sb.AppendLine("type = VAB");
            sb.AppendLine("size = 1,1,1");
            sb.AppendLine("persistentId = 1");
            sb.AppendLine("rot = 0,0,0,1");
            sb.AppendLine("missionFlag = Squad/Flags/default");
            sb.AppendLine("vesselType = Probe");
            sb.AppendLine("PART");
            sb.AppendLine("{");
            sb.AppendLine("\tpart = " + ap.name + "_4294000000");
            sb.AppendLine("\tpartName = Part");
            sb.AppendLine("\tpersistentId = 2");
            sb.AppendLine("\tpos = 0,10,0");
            sb.AppendLine("\tattPos = 0,0,0");
            sb.AppendLine("\tattPos0 = 0,10,0");
            sb.AppendLine("\trot = 0,0,0,1");
            sb.AppendLine("\tattRot = 0,0,0,1");
            sb.AppendLine("\tattRot0 = 0,0,0,1");
            sb.AppendLine("\tmir = 1,1,1");
            sb.AppendLine("\tsymMethod = Radial");
            sb.AppendLine("\tautostrutMode = Off");
            sb.AppendLine("\trigidAttachment = False");
            sb.AppendLine("\tistg = 0");
            sb.AppendLine("\tresPri = 0");
            sb.AppendLine("\tdstg = 0");
            sb.AppendLine("\tsidx = -1");
            sb.AppendLine("\tsqor = -1");
            sb.AppendLine("\tsepI = 0");
            sb.AppendLine("\tattm = 0");
            sb.AppendLine("\tsameVesselCollision = False");
            sb.AppendLine("\tmodCost = 0");
            sb.AppendLine("\tmodMass = 0");
            sb.AppendLine("\tmodSize = 0,0,0");
            sb.AppendLine("}");
            return sb.ToString();
        }

        // ------------------------------------------------------------------ per-tick hooks

        /// <summary>Wraps AXE's own FeedInputFeed patches: the prefix (Priority.First) writes the test
        /// command before AXE samples it as stick intent; the postfix (Priority.Last) reads what AXE left.</summary>
        static class Hooks
        {
            internal static Func<Vessel, Vector3> Command;   // null = pass-through, nothing recorded
            internal static float Throttle;                  // commanded throttle; > deadband ARMS the corruption
            internal static List<Sample> Sink;
            static Vector3 _in;

            static void Prefix(Vessel __instance)
            {
                if (Command == null || __instance != FlightGlobals.ActiveVessel) return;
                _in = Command(__instance);
                FlightCtrlState st = __instance.ctrlState;
                st.pitch = _in.x; st.yaw = _in.y; st.roll = _in.z;
                st.mainThrottle = Throttle;
            }

            static void Postfix(Vessel __instance)
            {
                if (Command == null || __instance != FlightGlobals.ActiveVessel) return;
                FlightCtrlState st = __instance.ctrlState;
                Sink?.Add(new Sample
                {
                    T = Time.fixedTime, In = _in, Out = new Vector3(st.pitch, st.yaw, st.roll),
                    ErrDeg = PointingErrorDeg(__instance),
                });
            }
        }

        struct Sample { public float T; public Vector3 In, Out; public float ErrDeg; }

        // ------------------------------------------------------------------ the flight run

        static Vector3 _target;                 // inertial direction the HOLD phase keeps the nose on
        static Matrix4x4 _authInv;              // desired local angular accel -> (pitch, yaw, roll)
        static float _kp, _kd;
        static readonly StringBuilder Csv = new StringBuilder("mode,sigma,phase,t,in_p,in_y,in_r,out_p,out_y,out_r,err_deg\n");

        static float PointingErrorDeg(Vessel v) => Vector3.Angle(v.ReferenceTransform.up, _target);

        static Vector3 OmegaLocal(Vessel v) =>
            Quaternion.Inverse(v.ReferenceTransform.rotation) * v.rootPart.Rigidbody.angularVelocity;

        static Vector3 HoldCommand(Vessel v)
        {
            Transform rt = v.ReferenceTransform;
            Vector3 nose = rt.up;
            Vector3 axis = Vector3.Cross(nose, _target);
            float ang = Vector3.Angle(nose, _target) * Mathf.Deg2Rad;
            Vector3 errW = axis.sqrMagnitude > 1e-12f ? axis.normalized * ang : Vector3.zero;
            Vector3 aW = _kp * errW - _kd * v.rootPart.Rigidbody.angularVelocity;
            Vector3 u = _authInv.MultiplyVector(Quaternion.Inverse(rt.rotation) * aW);
            return new Vector3(Mathf.Clamp(u.x, -1f, 1f), Mathf.Clamp(u.y, -1f, 1f), Mathf.Clamp(u.z, -1f, 1f));
        }

        static IEnumerator Ticks(float seconds)
        {
            int n = Mathf.Max(1, Mathf.RoundToInt(seconds / Mathf.Max(0.005f, Time.fixedDeltaTime)));
            for (int i = 0; i < n; i++) yield return new WaitForFixedUpdate();
        }

        internal static IEnumerator Run()
        {
            Ran = true;
            bool ok = true;
            var report = new List<string>();
            void Check(bool pass, string what)
            {
                ok &= pass;
                string line = (pass ? "PASS " : "FAIL ") + what;
                report.Add(line);
                Debug.Log(Tag + line);
            }

            // 1. a loaded, unpacked vessel
            float deadline = Time.realtimeSinceStartup + 180f;
            while (!(FlightGlobals.ready && FlightGlobals.ActiveVessel != null && !FlightGlobals.ActiveVessel.packed
                     && AxeAvionicsController.Instance != null))
            {
                if (Time.realtimeSinceStartup > deadline) { Finish(false, "vessel never became ready", report); yield break; }
                yield return null;
            }
            Vessel v = FlightGlobals.ActiveVessel;
            Debug.Log(Tag + "vessel '" + v.vesselName + "' ready on " + v.mainBody.bodyName + ", " + v.Parts.Count + " part(s)");

            // 2. orbit, power, no autopilot
            int home = FlightGlobals.GetHomeBodyIndex();
            CelestialBody body = FlightGlobals.Bodies[home];
            FlightGlobals.fetch.SetShipOrbit(home, 0.0, body.Radius + 300000.0, 0.0, 0.0, 0.0, 0.0, 0.0);
            deadline = Time.realtimeSinceStartup + 60f;
            yield return Ticks(1f);
            while (v.packed || v.situation != Vessel.Situations.ORBITING)
            {
                if (Time.realtimeSinceStartup > deadline) { Finish(false, "orbit insertion did not settle (" + v.situation + ")", report); yield break; }
                yield return null;
            }
            foreach (Part p in v.Parts)
            {
                PartResource ec = p.Resources["ElectricCharge"];
                if (ec != null) { ec.maxAmount = 1e7; ec.amount = 1e7; }
            }
            v.ActionGroups.SetGroup(KSPActionGroup.SAS, false);
            v.Autopilot.Disable();
            yield return Ticks(3f);
            Debug.Log(Tag + "orbit " + (v.altitude / 1000.0).ToString("0") + " km, situation " + v.situation +
                      ", avionics level " + AxeAvionicsController.Instance.Level);
            Check(AxeAvionicsController.Instance.Level == AxeControlLockerUtils.LockLevel.Unlocked,
                  "probe is guided (avionics level Unlocked) -- otherwise a control lock would hide the corruption");

            // 3. patch integrity: the 0.9.0 defect itself
            Check(OwnedBy("Vessel.FeedInputFeed", AccessTools.Method(typeof(Vessel), "FeedInputFeed"), report),
                  "exactly one AXE prefix + postfix on Vessel.FeedInputFeed");
            Check(OwnedBy("ModuleRCS.Update", AccessTools.Method(typeof(ModuleRCS), "Update"), report),
                  "exactly one AXE prefix + postfix on ModuleRCS.Update");

            // 4. our own hooks around AXE's
            var hooks = new Harmony(TestHarmonyId);
            MethodInfo feed = AccessTools.Method(typeof(Vessel), "FeedInputFeed");
            hooks.Patch(feed,
                prefix: new HarmonyMethod(AccessTools.Method(typeof(Hooks), "Prefix")) { priority = Priority.First },
                postfix: new HarmonyMethod(AccessTools.Method(typeof(Hooks), "Postfix")) { priority = Priority.Last });
            var buf = new List<Sample>();
            Hooks.Sink = buf;
            _target = v.ReferenceTransform.up;

            AxeAvionicsController.TestNoiseOverride = 0f;

            // 5. authority: pulse each axis clean, measure the angular acceleration it buys
            Vector3[] auth = new Vector3[3];
            float pulse = 0.4f;
            for (int k = 0; k < 3; k++)
            {
                Vector3 e = Vector3.zero; e[k] = 1f;
                Vector3 w0 = OmegaLocal(v);
                Hooks.Command = _ => e;
                yield return Ticks(pulse);
                Vector3 w1 = OmegaLocal(v);
                Hooks.Command = _ => -e;
                yield return Ticks(pulse);
                Hooks.Command = _ => Vector3.zero;
                yield return Ticks(0.5f);
                auth[k] = (w1 - w0) / pulse;
            }
            float authMean = (auth[0].magnitude + auth[1].magnitude + auth[2].magnitude) / 3f;
            Debug.Log(Tag + "authority rad/s^2 per unit stick: pitch " + auth[0].ToString("0.###") + " yaw " +
                      auth[1].ToString("0.###") + " roll " + auth[2].ToString("0.###"));
            var a = Matrix4x4.identity;
            a.SetColumn(0, auth[0]); a.SetColumn(1, auth[1]); a.SetColumn(2, auth[2]);
            _authInv = a.inverse;
            _kp = authMean / (FullStickErrDeg * Mathf.Deg2Rad);
            _kd = 1.6f * Mathf.Sqrt(_kp);
            bool controllable = auth.All(x => x.magnitude > 1e-2f) && Mathf.Abs(a.determinant) > 1e-9f;
            Check(controllable, "probe has three-axis authority (" + authMean.ToString("0.###") + " rad/s^2 mean)");

            var rows = new List<string>();
            if (controllable)
            {
                // settle the nose onto the target before measuring anything
                Hooks.Command = HoldCommand;
                yield return Ticks(8f);

                foreach (bool dbl in new[] { false, true })
                {
                    var twice = new Harmony(DoubleHarmonyId);
                    if (dbl)
                    {
                        AxeAvionicsController.TestPassesOverride = 1;
                        twice.CreateClassProcessor(typeof(AxeFlightControlLast)).Patch();
                    }
                    string mode = dbl ? "0.9.0(ref)" : "shipped(x" + AxeControlLockerUtils.CorruptionPasses + ")";
                    foreach (float over in Overloads)
                    {
                        float sigma = AxeControlLockerUtils.NoiseFor(1f + over);

                        AxeAvionicsController.TestNoiseOverride = 0f;
                        Hooks.Command = HoldCommand;
                        yield return Ticks(SettleSec);

                        // TRANSFER
                        AxeControlLockerUtils.ResetAdversarial();
                        AxeAvionicsController.TestNoiseOverride = sigma;
                        float t0 = Time.fixedTime;
                        Hooks.Command = _ =>
                        {
                            float t = Time.fixedTime - t0;
                            return new Vector3(0.3f * Mathf.Sin(2f * Mathf.PI * 0.5f * t), 0.2f, 0f);
                        };
                        buf.Clear();
                        yield return Ticks(TransferSec);
                        var transfer = buf.ToList();
                        Dump(mode, sigma, "transfer", transfer);

                        AxeAvionicsController.TestNoiseOverride = 0f;
                        Hooks.Command = HoldCommand;
                        yield return Ticks(RecoverSec);

                        // HOLD through a burn. Throttle is what arms it: a settled hold commands ~0, below
                        // the arming deadband, so without it the corruption never switches on (run 2,
                        // 2026-10-24: 0.00 deg at every sigma). The probe has no engine; throttle only arms.
                        AxeControlLockerUtils.ResetAdversarial();
                        AxeAvionicsController.TestNoiseOverride = sigma;
                        Hooks.Throttle = 1f;
                        buf.Clear();
                        yield return Ticks(HoldSec);
                        Hooks.Throttle = 0f;
                        var hold = buf.Skip(buf.Count / 4).ToList();
                        Dump(mode, sigma, "hold", buf);

                        string row = RowFor(mode, over, sigma, transfer, hold);
                        rows.Add(row);
                        Debug.Log(Tag + row);

                        if (transfer.Count == 0 || hold.Count == 0)
                        {
                            Check(false, "no samples recorded at " + mode + " sigma " + sigma.ToString("0.00") + " -- the test hooks never ran");
                            continue;
                        }
                        if (over == 0f && !dbl)
                        {
                            float maxDev = transfer.Max(s => (s.Out - s.In).magnitude);
                            Check(maxDev < 1e-5f, "sigma 0 passes the command through untouched (max |out-in| " + maxDev.ToString("0.######") + ")");
                            float p95 = Pct(hold.Select(s => s.ErrDeg), 0.95f);
                            Check(p95 < 1f, "clean controller holds the target (p95 error " + p95.ToString("0.00") + " deg) -- HOLD numbers valid");
                        }
                    }
                    if (dbl)
                    {
                        twice.UnpatchAll(DoubleHarmonyId);
                        AxeAvionicsController.TestPassesOverride = -1;
                    }
                }

                // ZERO IN, ZERO OUT at full sigma (disarmed: no stick, no throttle, no autopilot target)
                AxeAvionicsController.TestNoiseOverride = AxeControlLockerUtils.NoiseFor(1.5f);
                Hooks.Command = _ => Vector3.zero;
                buf.Clear();
                yield return Ticks(2f);
                float zmax = buf.Count == 0 ? 0f : buf.Max(s => s.Out.magnitude);
                Check(buf.Count > 0 && zmax < 1e-6f, "zero command stays zero at sigma " +
                      AxeControlLockerUtils.NoiseFor(1.5f).ToString("0.000") + " (max |out| " + zmax.ToString("0.######") + ")");
            }

            Hooks.Command = null;
            Hooks.Throttle = 0f;
            Hooks.Sink = null;
            AxeAvionicsController.TestNoiseOverride = -1f;
            AxeAvionicsController.TestPassesOverride = -1;
            hooks.UnpatchAll(TestHarmonyId);

            try
            {
                string dir = Path.Combine(KSPUtil.ApplicationRootPath, "axe_autotest");
                Directory.CreateDirectory(dir);
                File.WriteAllText(Path.Combine(dir, "avionics-flight.csv"), Csv.ToString());
            }
            catch (Exception e) { Debug.LogWarning(Tag + "csv write failed: " + e.Message); }

            Debug.Log(Tag + "SUMMARY  mode | over | sigma | transfer mean|out-in| p95 | off-axis mean max deg | hold err mean p95 max deg");
            foreach (string r in rows) Debug.Log(Tag + "SUMMARY  " + r);
            Finish(ok, null, report);
        }

        static bool OwnedBy(string label, MethodBase m, List<string> report)
        {
            Patches info = m == null ? null : Harmony.GetPatchInfo(m);
            // case-insensitive: 0.9.0's duplicate registered as "rpaxe.tree.highlight"
            int pre = info?.Prefixes.Count(p => p.owner.StartsWith("RPAxe", StringComparison.OrdinalIgnoreCase)) ?? 0;
            int post = info?.Postfixes.Count(p => p.owner.StartsWith("RPAxe", StringComparison.OrdinalIgnoreCase)) ?? 0;
            string owners = info == null ? "none" : string.Join(", ", info.Owners.ToArray());
            Debug.Log(Tag + label + ": AXE prefixes " + pre + ", postfixes " + post + " (all owners: " + owners + ")");
            return pre == 1 && post == 1;
        }

        static string RowFor(string mode, float over, float sigma, List<Sample> transfer, List<Sample> hold)
        {
            var dev = transfer.Select(s => (s.Out - s.In).magnitude).ToList();
            var ang = transfer.Where(s => s.In.magnitude > 0.05f && s.Out.magnitude > 1e-6f)
                              .Select(s => Vector3.Angle(s.In, s.Out)).ToList();
            var err = hold.Select(s => s.ErrDeg).ToList();
            return string.Format("{0,-13} | {1,4:0}% | {2:0.00} | {3:0.000} {4:0.000} | {5,5:0.0} {6,5:0.0} | {7,6:0.00} {8,6:0.00} {9,6:0.00}",
                mode, over * 100f, sigma,
                dev.Count > 0 ? dev.Average() : 0f, Pct(dev, 0.95f),
                ang.Count > 0 ? ang.Average() : 0f, ang.Count > 0 ? ang.Max() : 0f,
                err.Count > 0 ? err.Average() : 0f, Pct(err, 0.95f), err.Count > 0 ? err.Max() : 0f);
        }

        static float Pct(IEnumerable<float> xs, float q)
        {
            var s = xs.OrderBy(x => x).ToList();
            return s.Count == 0 ? 0f : s[Mathf.Clamp(Mathf.FloorToInt(q * (s.Count - 1)), 0, s.Count - 1)];
        }

        static void Dump(string mode, float sigma, string phase, List<Sample> samples)
        {
            foreach (Sample s in samples)
                Csv.AppendFormat(System.Globalization.CultureInfo.InvariantCulture,
                    "{0},{1:0.0000},{2},{3:0.000},{4:0.0000},{5:0.0000},{6:0.0000},{7:0.0000},{8:0.0000},{9:0.0000},{10:0.000}\n",
                    mode, sigma, phase, s.T, s.In.x, s.In.y, s.In.z, s.Out.x, s.Out.y, s.Out.z, s.ErrDeg);
        }

        static void Finish(bool ok, string why, List<string> report)
        {
            AxeAvionicsController.TestNoiseOverride = -1f;
            Debug.Log(Tag + "RESULT " + (ok ? "PASS" : "FAIL") + (why != null ? " -- " + why : "") +
                      " (" + report.Count(r => r.StartsWith("PASS")) + " passed, " + report.Count(r => r.StartsWith("FAIL")) + " failed)");
            if (AutoTestConfig.QuitWhenDone)
            {
                Debug.Log("[AXE][AutoTest] Avionics flight test finished; quitting KSP.");
                AutoTestUtil.HardQuit();
            }
        }
    }

    /// <summary>Starts <see cref="AxeAvionicsFlightTest.Run"/> once the launched probe's flight scene is up.</summary>
    [KSPAddon(KSPAddon.Startup.Flight, false)]
    public class AxeAvionicsFlightTestDriver : MonoBehaviour
    {
        void Start()
        {
            if (AxeAvionicsFlightTest.FlightPhaseRequested && !AxeAvionicsFlightTest.Ran)
                StartCoroutine(AxeAvionicsFlightTest.Run());
        }
    }
}
