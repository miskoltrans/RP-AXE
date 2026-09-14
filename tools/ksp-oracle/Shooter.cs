// The patch chain, mirroring PatchedConicSolver.LateUpdate exactly.
//
// The whole point of this file is that it contains no orbital mechanics. Every number comes out
// of KSP's own Orbit and PatchedConics; this only sequences the calls the way the game does, so
// that "what the map view would show" and "what the tool says" cannot drift apart.

using System;
using System.Collections.Generic;

namespace RPAxe.KspOracle
{
    internal sealed class PatchOut
    {
        internal CelestialBody Body;
        internal string End;              // enter:<Body> | exit | horizon | impact | <transition>
        internal double StartUT, EndUT;
        internal double Sma, Ecc, Inc, Lan, ArgP, Mna, Epoch, PeR, ApR;
        internal Vector3d R0, V0;
    }

    internal sealed class ShootResult
    {
        internal List<PatchOut> Patches = new List<PatchOut>();
        internal bool Truncated;         // stopped at max_patches with more ahead
        internal string Note;
    }

    internal static class Shooter
    {
        internal const int DefaultMaxPatches = 8;

        internal static ShootResult Shoot(OracleSystem sys, string bodyName,
                                          Vector3d r, Vector3d v,
                                          double ut0, double utEnd, bool utEndGiven,
                                          int maxPatches)
        {
            CelestialBody body = sys.Body(bodyName);
            var res = new ShootResult();

            // PatchedConicSolver reads the clock for the first patch's epoch. Ours is ut0.
            Planetarium.fetch.time = ut0;

            var patches = new List<Orbit>();
            for (int i = 0; i <= maxPatches + 1; i++) patches.Add(new Orbit());

            Orbit first = patches[0];
            first.UpdateFromStateVectors(r, v, body, ut0);
            first.Init();                       // UpdateFromFixedVectors leaves period/ObT unset
            first.UpdateFromUT(ut0);
            first.patchStartTransition = Orbit.PatchTransitionType.INITIAL;
            first.StartUT = ut0;

            // KSP gives patch 0 exactly one revolution (and no bound at all when hyperbolic,
            // since period is +Infinity there). That is why the map view never shows an
            // encounter two orbits out. A caller who wants to search further says so with
            // end_ut, which is a deliberate, reported departure from the game's own window --
            // not a silent one.
            double kspEnd = (first.eccentricity < 1.0) ? ut0 + first.period : first.period;
            if (utEndGiven && utEnd > kspEnd)
            {
                first.EndUT = utEnd;
                res.Note = "patch 0 searched to end_ut, past KSP's own one-revolution window";
            }
            else
            {
                first.EndUT = kspEnd;
            }

            var pars = new PatchedConics.SolverParameters();
            int num = 0;
            bool more;

            while (true)
            {
                Orbit p = patches[num];
                Orbit next = patches[num + 1];
                double startEpoch = (num != 0) ? p.epoch : Planetarium.GetUniversalTime();

                more = PatchedConics.CalculatePatch(p, next, startEpoch, pars, null);
                res.Patches.Add(Describe(p, next, more));

                num++;
                if (!more) break;
                if (utEndGiven && p.EndUT >= utEnd) { res.Truncated = false; break; }
                if (num >= maxPatches) { res.Truncated = true; break; }
            }

            return res;
        }

        static PatchOut Describe(Orbit p, Orbit next, bool more)
        {
            var o = new PatchOut
            {
                Body = p.referenceBody,
                StartUT = p.StartUT,
                EndUT = p.EndUT,
                Sma = p.semiMajorAxis,
                Ecc = p.eccentricity,
                Inc = p.inclination,
                Lan = p.LAN,
                ArgP = p.argumentOfPeriapsis,
                Mna = p.meanAnomalyAtEpoch,
                Epoch = p.epoch,
                PeR = p.PeR,
                ApR = p.ApR,
                R0 = p.getRelativePositionAtUT(p.StartUT),
                V0 = p.getOrbitalVelocityAtUT(p.StartUT),
            };

            switch (p.patchEndTransition)
            {
                case Orbit.PatchTransitionType.ENCOUNTER:
                    // The name of the body entered is on the patch KSP just built, not on this one.
                    o.End = "enter:" + (more && next.referenceBody != null
                                        ? next.referenceBody.bodyName : "?");
                    o.EndUT = p.UTsoi;
                    break;
                case Orbit.PatchTransitionType.ESCAPE:
                    o.End = "exit";
                    o.EndUT = p.UTsoi;
                    break;
                case Orbit.PatchTransitionType.IMPACT:
                    o.End = "impact";
                    break;
                case Orbit.PatchTransitionType.FINAL:
                    o.End = "horizon";
                    break;
                default:
                    o.End = p.patchEndTransition.ToString().ToLowerInvariant();
                    break;
            }
            return o;
        }
    }
}
