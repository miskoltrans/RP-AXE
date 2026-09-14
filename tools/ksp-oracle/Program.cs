// A long-lived worker that answers trajectory questions with KSP's own code.
//
// Line-delimited JSON on stdin/stdout, one request per line, one reply per line. Not a socket:
// there is no reason to open a port for something that only ever talks to its own parent, and a
// pipe cannot be reached by anything else on the machine.
//
// The batch op exists because the point of this worker is throughput. A flown search over a moon
// tour is tens of thousands of trajectories; at ~0.1 ms of arithmetic each, per-call overhead is
// what would decide the runtime, so the search sends its whole frontier at once.
//
// Infinity and NaN serialise as null, exactly as the in-game bridge does -- so a null soi, apR or
// end_ut means infinite, and the client converts it back.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using RPAxe.Bridge;

namespace RPAxe.KspOracle
{
    internal static class Program
    {
        internal const string Version = "ksp-oracle 1.0";

        static OracleSystem _sys;

        static int Main(string[] args)
        {
            CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
            Shim.BootPlanetarium();

            if (args.Length > 0 && args[0] == "--selftest")
                return SelfTest.Run() ? 0 : 1;

            var stdin = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false), false, 1 << 16);
            var stdout = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false), 1 << 16);
            stdout.AutoFlush = false;

            string line;
            while ((line = stdin.ReadLine()) != null)
            {
                if (line.Length == 0) continue;
                string reply;
                try { reply = Dispatch(line); }
                catch (Exception e)
                {
                    reply = new AxeJson().Obj()
                        .Val("ok", false)
                        .Val("error", e.GetType().Name + ": " + e.Message)
                        .EndObj().ToString();
                }
                stdout.Write(reply);
                stdout.Write('\n');
                stdout.Flush();
            }
            return 0;
        }

        static string Dispatch(string line)
        {
            Dictionary<string, object> req = AxeJsonReader.ParseObject(line);
            string op = AxeJsonReader.Str(req, "op");

            switch (op)
            {
                case "ping":
                    return new AxeJson().Obj()
                        .Val("ok", true).Val("version", Version)
                        .Val("bodies", _sys == null ? 0 : _sys.Count)
                        .EndObj().ToString();

                case "system":
                    _sys = OracleSystem.FromJson(AxeJsonReader.Arr(req, "bodies"));
                    return new AxeJson().Obj()
                        .Val("ok", true).Val("bodies", _sys.Count)
                        .EndObj().ToString();

                // Ephemeris crosscheck. A body in the wrong place moves every encounter
                // consistently, so nothing internal notices -- this is the only way to see it.
                case "body":
                {
                    RequireSystem();
                    CelestialBody b = _sys.Body(AxeJsonReader.Str(req, "name"));
                    double ut = AxeJsonReader.NumRequired(req, "ut");
                    var j = new AxeJson().Obj().Val("ok", true)
                        .Val("name", b.bodyName).Val("mu", b.gravParameter)
                        .Val("radius", b.Radius).Val("soi", b.sphereOfInfluence);
                    if (b.orbitDriver != null && b.orbitDriver.orbit != null)
                    {
                        Orbit ob = b.orbitDriver.orbit;
                        j.Val("parent", ob.referenceBody.bodyName)
                         .Vec("r", ob.getRelativePositionAtUT(ut))
                         .Vec("v", ob.getOrbitalVelocityAtUT(ut))
                         .Val("sma", ob.semiMajorAxis).Val("ecc", ob.eccentricity)
                         .Val("inc", ob.inclination).Val("lan", ob.LAN)
                         .Val("argp", ob.argumentOfPeriapsis)
                         .Val("mna", ob.meanAnomalyAtEpoch).Val("epoch", ob.epoch);
                    }
                    return j.EndObj().ToString();
                }

                case "shoot":
                {
                    RequireSystem();
                    var j = new AxeJson().Obj().Val("ok", true);
                    WriteResult(j, "result", RunJob(req));
                    return j.EndObj().ToString();
                }

                case "shoot_batch":
                {
                    RequireSystem();
                    List<object> jobs = AxeJsonReader.Arr(req, "jobs");
                    var j = new AxeJson().Obj().Val("ok", true).Arr("results");
                    foreach (object o in jobs)
                    {
                        Dictionary<string, object> job = AxeJsonReader.AsObj(o);
                        try
                        {
                            j.Obj().Val("ok", true);
                            WriteResult(j, "result", RunJob(job));
                            j.EndObj();
                        }
                        catch (Exception e)
                        {
                            // One bad job must not lose the other 40,000.
                            j.Obj().Val("ok", false)
                                   .Val("error", e.GetType().Name + ": " + e.Message)
                                   .EndObj();
                        }
                    }
                    return j.EndArr().EndObj().ToString();
                }

                default:
                    throw new InvalidOperationException("unknown op '" + op + "'");
            }
        }

        static void RequireSystem()
        {
            if (_sys == null)
                throw new InvalidOperationException("no system loaded -- send op 'system' first");
        }

        static ShootResult RunJob(Dictionary<string, object> job)
        {
            double utEnd = AxeJsonReader.Num(job, "ut_end", double.NaN);
            bool utEndGiven = !double.IsNaN(utEnd);
            return Shooter.Shoot(
                _sys,
                AxeJsonReader.Str(job, "body"),
                Vec3(job, "r"), Vec3(job, "v"),
                AxeJsonReader.NumRequired(job, "ut0"),
                utEnd, utEndGiven,
                (int)AxeJsonReader.Num(job, "max_patches", Shooter.DefaultMaxPatches));
        }

        internal static Vector3d Vec3(Dictionary<string, object> d, string key)
        {
            List<object> a = AxeJsonReader.Arr(d, key);
            if (a == null || a.Count != 3)
                throw new InvalidOperationException("'" + key + "' must be [x,y,z]");
            return new Vector3d(Convert.ToDouble(a[0], CultureInfo.InvariantCulture),
                                Convert.ToDouble(a[1], CultureInfo.InvariantCulture),
                                Convert.ToDouble(a[2], CultureInfo.InvariantCulture));
        }

        internal static void WriteResult(AxeJson j, string key, ShootResult res)
        {
            j.Obj(key);
            j.Val("truncated", res.Truncated);
            if (res.Note != null) j.Val("note", res.Note);
            j.Arr("patches");
            foreach (PatchOut p in res.Patches)
            {
                j.Obj()
                 .Val("body", p.Body == null ? null : p.Body.bodyName)
                 .Val("end", p.End)
                 .Val("start_ut", p.StartUT)
                 .Val("end_ut", p.EndUT)
                 .Val("sma", p.Sma).Val("ecc", p.Ecc).Val("inc", p.Inc)
                 .Val("lan", p.Lan).Val("argp", p.ArgP).Val("mna", p.Mna)
                 .Val("epoch", p.Epoch).Val("peR", p.PeR).Val("apR", p.ApR)
                 .Vec("r0", p.R0).Vec("v0", p.V0)
                 .EndObj();
            }
            j.EndArr().EndObj();
        }
    }
}
