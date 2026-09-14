// Checks that the SHIM is sound. The orbital mechanics are KSP's and are not re-derived here;
// what can break is the scaffolding around them, and each of these failed at least once while
// this was being written.

using System;
using System.Collections.Generic;
using System.Globalization;

namespace RPAxe.KspOracle
{
    internal static class SelfTest
    {
        static int _pass, _fail;

        static void Check(string what, bool ok, string detail)
        {
            if (ok) { _pass++; Console.WriteLine("  ok   " + what); }
            else { _fail++; Console.WriteLine("  FAIL " + what + "\n         " + detail); }
        }

        internal static bool Run()
        {
            Console.WriteLine(Program.Version + " selftest");

            const double muE = 3.986004418e14, rE = 6371000.0, soiE = 9.2464e8;
            const double muM = 4.9028e12, rM = 1737100.0, soiM = 6.616716e7;

            CelestialBody earth = Shim.MakeBody("Earth", muE, rE, soiE);
            CelestialBody moon = Shim.MakeBody("Moon", muM, rM, soiM);
            Orbit moonOrbit = new Orbit(0.0, 0.0, 384400000.0, 0.0, 0.0, 0.0, 0.0, earth);
            moonOrbit.Init();
            Shim.Attach(moon, earth, moonOrbit);

            // 1. The liveness fake. Without a non-zero m_CachedPtr this reads false and
            //    _CalculatePatch silently skips every body, finding no encounter ever.
            Check("a shimmed CelestialBody reads as alive to Unity's null check",
                  (bool)moon && (bool)(moon.orbitDriver.celestialBody),
                  "m_CachedPtr fake is not taking");

            Check("the driver is registered where PatchedConics looks for it",
                  Planetarium.Orbits.Count == 1 && Planetarium.Orbits[0].celestialBody == moon,
                  "Planetarium.Orbits has " + Planetarium.Orbits.Count + " entries");

            // 2. The frame. Assert Zup IS the identity, not merely that a round trip survives it:
            //    UpdateFromStateVectors applies Zup.LocalToWorld to its input and
            //    getRelativePositionAtUT applies WorldToLocal on the way out, so ANY Zup round
            //    trips cleanly. A wrong one still puts the vessel in a different frame from the
            //    bodies, whose orbits are built from elements and never pass through Zup at all --
            //    which reads as "no encounter ever", with every element still bit-perfect.
            Check("Zup is the identity, so the element frame is the working frame",
                  (Planetarium.Zup.X - new Vector3d(1, 0, 0)).magnitude < 1e-15 &&
                  (Planetarium.Zup.Y - new Vector3d(0, 1, 0)).magnitude < 1e-15 &&
                  (Planetarium.Zup.Z - new Vector3d(0, 0, 1)).magnitude < 1e-15,
                  "Zup.X=" + Planetarium.Zup.X + " Y=" + Planetarium.Zup.Y + " Z=" + Planetarium.Zup.Z);

            double sma = rE + 300000.0;
            Vector3d r = new Vector3d(sma, 0.0, 0.0);
            Vector3d v = new Vector3d(0.0, 3264.3287207024, -7006.80997137897);
            Orbit o = new Orbit();
            o.UpdateFromStateVectors(r, v, earth, 0.0);
            o.Init();
            Vector3d rb = o.getRelativePositionAtUT(0.0);
            Vector3d vb = o.getOrbitalVelocityAtUT(0.0);
            Check("a state vector round-trips unrotated (Zup is the identity)",
                  (rb - r).magnitude < 1e-6 && (vb - v).magnitude < 1e-9,
                  "dr = " + (rb - r).magnitude.ToString("R", CultureInfo.InvariantCulture) +
                  " m, dv = " + (vb - v).magnitude.ToString("R", CultureInfo.InvariantCulture) + " m/s");

            // 3. Init() after UpdateFromStateVectors. UpdateFromFixedVectors sets the elements but
            //    leaves period and ObT untouched, so without the Init the patch window is garbage.
            double analytic = 2.0 * Math.PI * Math.Sqrt(sma * sma * sma / muE);
            Check("period is set after UpdateFromStateVectors + Init",
                  Math.Abs(o.period - analytic) < 1e-6,
                  "got " + o.period.ToString("R", CultureInfo.InvariantCulture) + ", analytic " + analytic);

            Check("a hyperbolic orbit reports an infinite period, as KSP's patch window expects",
                  double.IsPositiveInfinity(
                      MakeHyperbolic(earth, rE + 200000.0, 12000.0).period),
                  "hyperbolic period is finite");

            // 4. The end to end thing: KSP's solver finds a real SOI entry and builds the patch
            //    inside it. This is the answer that took StartUT/EndUT to get -- without them the
            //    solver reports ORBIT_INTERSECT forever and never ENCOUNTER.
            int encounters = 0, sampled = 0;
            double rp = rE + 200000.0, ra = 400000000.0;
            double a2 = 0.5 * (rp + ra), e2 = (ra - rp) / (ra + rp);
            for (int k = 0; k < 360; k += 2)
            {
                Shim.SetField(moon.orbitDriver, "orbit", Phased(earth, k));
                Orbit sh = new Orbit(0.0, e2, a2, 0.0, 0.0, 0.0, 0.0, earth);
                sh.Init(); sh.UpdateFromUT(0.0);
                sh.patchStartTransition = Orbit.PatchTransitionType.INITIAL;
                sh.StartUT = 0.0;
                sh.EndUT = sh.StartUT + sh.period;
                Orbit nx = new Orbit();
                sampled++;
                if (PatchedConics.CalculatePatch(sh, nx, 0.0, new PatchedConics.SolverParameters(), null)
                    && sh.patchEndTransition == Orbit.PatchTransitionType.ENCOUNTER
                    && nx.referenceBody == moon
                    && nx.PeR > 0.0 && nx.eccentricity > 1.0)
                    encounters++;
            }
            Check("KSP's own solver finds lunar SOI entries and builds the patch inside",
                  encounters > 20 && encounters < sampled,
                  encounters + " encounters over " + sampled + " Moon phases (expected some, not all)");

            Console.WriteLine(_fail == 0
                ? string.Format("{0} checks, all passed", _pass)
                : string.Format("{0} passed, {1} FAILED", _pass, _fail));
            return _fail == 0;
        }

        static Orbit Phased(CelestialBody earth, int degrees)
        {
            Orbit m = new Orbit(0.0, 0.0, 384400000.0, 0.0, 0.0, degrees * Math.PI / 180.0, 0.0, earth);
            m.Init();
            return m;
        }

        static Orbit MakeHyperbolic(CelestialBody earth, double rp, double vp)
        {
            Orbit h = new Orbit();
            h.UpdateFromStateVectors(new Vector3d(rp, 0, 0), new Vector3d(0, 0, -vp), earth, 0.0);
            h.Init();
            return h;
        }
    }
}
