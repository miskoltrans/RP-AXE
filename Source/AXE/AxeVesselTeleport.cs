using System;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Shared low-level vessel teleport primitive, ported self-contained from ROUtils/KCT
    /// <c>HyperEdit_Utilities</c> (originally the HyperEdit lander by khyperia &amp; Ezriilc). Stock API
    /// only — no ROUtils reference.
    ///
    /// This is the body-agnostic "put a vessel into an arbitrary orbit state" core. Two features call it
    /// and are otherwise unrelated:
    ///   * <see cref="RPAxe.Airlaunch.AxeAirlaunchTeleport"/> — a real, committing atmospheric drop that
    ///     builds its target state from the launch site + downrange offset.
    ///   * <see cref="RPAxe.Simulation"/> — a throwaway editor simulation that builds a circular orbit
    ///     around a chosen body via <see cref="PutInCircularOrbit"/>.
    /// Neither owns the primitive; both call it.
    /// </summary>
    internal static class AxeVesselTeleport
    {
        /// <summary>Drop the vessel into a fresh orbit around <paramref name="body"/> from
        /// periapsis/apoapsis altitudes (m ASL) + orientation. Both altitudes are clamped into the body's
        /// usable band (above atmosphere/surface, inside the SOI); pe/ap are swapped if entered backwards.
        /// A circular orbit is just pe == ap (see <see cref="PutInCircularOrbit"/>).</summary>
        public static void PutInOrbit(Vessel vessel, CelestialBody body, double periapsis, double apoapsis,
                                      double inclination, double lan, double argPe)
        {
            if (vessel == null || body == null) return;

            if (apoapsis < periapsis) { double t = periapsis; periapsis = apoapsis; apoapsis = t; }

            double minAlt = Math.Max(body.atmosphere ? body.atmosphereDepth : 0.0, 0.0) + 1000.0;
            double soiAlt = body.sphereOfInfluence - body.Radius;                 // SOI is measured from body centre
            if (double.IsInfinity(soiAlt) || soiAlt <= minAlt) soiAlt = body.Radius * 4.0; // Sun / degenerate
            double pe = Math.Min(Math.Max(periapsis, minAlt), soiAlt * 0.9);
            double ap = Math.Min(Math.Max(apoapsis, pe), soiAlt * 0.9);

            double rPe = body.Radius + pe;
            double rAp = body.Radius + ap;
            double sma = (rPe + rAp) / 2.0;
            double ecc = (rAp - rPe) / (rAp + rPe);
            // new Orbit(inc, e, sma, LAN, argPe, meanAnomalyAtEpoch, epoch, referenceBody) — same ctor as Clone.
            Orbit orbit = new Orbit(inclination, ecc, sma, lan, argPe, 0.0, Planetarium.GetUniversalTime(), body);
            SetOrbit(vessel, orbit);
        }

        /// <summary>Convenience: a circular orbit at <paramref name="altitude"/> (m ASL).</summary>
        public static void PutInCircularOrbit(Vessel vessel, CelestialBody body, double altitude, double inclination)
            => PutInOrbit(vessel, body, altitude, altitude, inclination, 0.0, 0.0);

        // ---- ported HyperEdit helpers (stock API only) ----

        public static Orbit Clone(Orbit o) =>
            new Orbit(o.inclination, o.eccentricity, o.semiMajorAxis, o.LAN,
                      o.argumentOfPeriapsis, o.meanAnomalyAtEpoch, o.epoch, o.referenceBody);

        public static void SetOrbit(Vessel vessel, Orbit newOrbit)
        {
            PrepVesselTeleport(vessel);

            try { OrbitPhysicsManager.HoldVesselUnpack(60); }
            catch (NullReferenceException) { Debug.LogError("[AXE] teleport HoldVesselUnpack NRE"); }

            IEnumerable<Vessel> allVessels = FlightGlobals.fetch?.vessels ?? (IEnumerable<Vessel>)new[] { vessel };
            foreach (Vessel v in allVessels) v.GoOnRails();

            CelestialBody oldBody = vessel.orbitDriver.orbit.referenceBody;
            HardsetOrbit(vessel.orbitDriver, newOrbit);
            vessel.orbitDriver.pos = vessel.orbit.pos.xzy;
            vessel.orbitDriver.vel = vessel.orbit.vel;

            CelestialBody newBody = vessel.orbitDriver.orbit.referenceBody;
            if (newBody != oldBody)
                GameEvents.onVesselSOIChanged.Fire(
                    new GameEvents.HostedFromToAction<Vessel, CelestialBody>(vessel, oldBody, newBody));
        }

        private static void HardsetOrbit(OrbitDriver orbitDriver, Orbit newOrbit)
        {
            Orbit orbit = orbitDriver.orbit;
            bool changedBody = orbit.referenceBody != newOrbit.referenceBody;
            orbit.inclination = newOrbit.inclination;
            orbit.eccentricity = newOrbit.eccentricity;
            orbit.semiMajorAxis = newOrbit.semiMajorAxis;
            orbit.LAN = newOrbit.LAN;
            orbit.argumentOfPeriapsis = newOrbit.argumentOfPeriapsis;
            orbit.meanAnomalyAtEpoch = newOrbit.meanAnomalyAtEpoch;
            orbit.epoch = newOrbit.epoch;
            orbit.referenceBody = newOrbit.referenceBody;
            orbit.Init();
            orbit.UpdateFromUT(Planetarium.GetUniversalTime());
            if (changedBody)
                orbitDriver.OnReferenceBodyChange?.Invoke(newOrbit.referenceBody);
        }

        public static void PrepVesselTeleport(Vessel vessel)
        {
            if (vessel.Landed) vessel.Landed = false;
            if (vessel.Splashed) vessel.Splashed = false;
            if (vessel.landedAt != string.Empty) vessel.landedAt = string.Empty;

            List<Part> parts = vessel.parts;
            if (parts == null) return;
            // Part.Die() removes the part from vessel.parts, so the clamps must be collected before any
            // are killed -- walking the live list throws "Collection was modified" on the first clamp,
            // which on a pad launch aborts the teleport entirely.
            List<Part> clamps = null;
            for (int i = parts.Count - 1; i >= 0; --i)
            {
                Part part = parts[i];
                if (part != null && part.Modules.Contains<LaunchClamp>())
                    (clamps ?? (clamps = new List<Part>())).Add(part);
            }
            if (clamps == null) return;
            foreach (Part part in clamps)
                if (part != null) part.Die();
        }

        public static void ResetGroundContact(Vessel vessel)
        {
            if (vessel.parts == null) return;
            for (int i = vessel.parts.Count - 1; i >= 0; --i)
            {
                Part part = vessel.parts[i];
                part.GroundContact = false;
                if (part.Modules.Contains("KSPWheelBase"))
                    part.Modules["KSPWheelBase"].Fields.SetValue("grounded", false);
            }
        }
    }
}
