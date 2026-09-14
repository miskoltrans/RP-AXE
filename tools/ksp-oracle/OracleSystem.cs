// The body tree, built from whatever rss_ephem already worked out.
//
// This deliberately does NOT read Kopernicus configs. rss_ephem already resolves the hard parts
// -- the post-ModuleManager radii, the SOIs Kopernicus actually logged rather than the Hill
// values, the B1950 epoch, the RSS renames -- and duplicating that here would create a second
// source of truth that could drift from the one every other tool uses. The oracle's job is to
// be KSP's arithmetic, not a second ephemeris.

using System;
using System.Collections.Generic;
using RPAxe.Bridge;

namespace RPAxe.KspOracle
{
    internal sealed class OracleSystem
    {
        readonly Dictionary<string, CelestialBody> _byName =
            new Dictionary<string, CelestialBody>(StringComparer.OrdinalIgnoreCase);

        internal int Count { get { return _byName.Count; } }

        internal CelestialBody Body(string name)
        {
            CelestialBody b;
            if (!_byName.TryGetValue(name, out b))
                throw new InvalidOperationException("no body '" + name + "'; known: " + string.Join(", ", Names()));
            return b;
        }

        internal string[] Names()
        {
            var n = new string[_byName.Count];
            _byName.Keys.CopyTo(n, 0);
            return n;
        }

        // Angles arrive in RADIANS, as rss_ephem holds them. KSP's Orbit constructor wants
        // inclination, LAN and argument of periapsis in DEGREES and the mean anomaly at epoch in
        // RADIANS -- the same asymmetry a .sfs has, where MNA is radians and INC/LPE/LAN are not.
        internal static OracleSystem FromJson(List<object> bodies)
        {
            var sys = new OracleSystem();

            // Two passes: every body must exist before any orbit can name its parent, and the
            // input is not required to be in parent-first order.
            var raw = new List<Dictionary<string, object>>();
            foreach (object o in bodies)
            {
                Dictionary<string, object> d = AxeJsonReader.AsObj(o);
                string name = AxeJsonReader.Str(d, "name");
                double soi = AxeJsonReader.Num(d, "soi", double.PositiveInfinity);
                if (double.IsNaN(soi)) soi = double.PositiveInfinity;
                sys._byName[name] = Shim.MakeBody(
                    name,
                    AxeJsonReader.NumRequired(d, "mu"),
                    AxeJsonReader.NumRequired(d, "radius"),
                    soi);
                raw.Add(d);
            }

            foreach (Dictionary<string, object> d in raw)
            {
                string parent = AxeJsonReader.Str(d, "parent");
                if (string.IsNullOrEmpty(parent)) continue;          // the root has no orbit

                CelestialBody child = sys.Body(AxeJsonReader.Str(d, "name"));
                CelestialBody par = sys.Body(parent);

                Orbit o = new Orbit(
                    AxeJsonReader.NumRequired(d, "inc") * 180.0 / Math.PI,
                    AxeJsonReader.NumRequired(d, "e"),
                    AxeJsonReader.NumRequired(d, "a"),
                    AxeJsonReader.NumRequired(d, "lan") * 180.0 / Math.PI,
                    AxeJsonReader.NumRequired(d, "argp") * 180.0 / Math.PI,
                    AxeJsonReader.NumRequired(d, "m0"),
                    AxeJsonReader.NumRequired(d, "epoch"),
                    par);
                o.Init();
                Shim.Attach(child, par, o);
            }

            return sys;
        }
    }
}
