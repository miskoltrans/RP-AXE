using System;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// The airlaunch teleport, ported self-contained from ROUtils/KCT <c>HyperEdit_Utilities.DoAirlaunch</c>
    /// (originally the HyperEdit lander by khyperia &amp; Ezriilc). Stock API only — no ROUtils reference.
    ///
    /// The one change from the original: instead of deriving a launch point at a configured distance/azimuth
    /// from the KSC (which needs KCT's RSS-aware FindKSC), we release the vessel straight above wherever it
    /// currently sits — the runway it just launched onto. Simpler and RSS/KSCSwitcher-proof; the KSC-offset
    /// feature can come back later if wanted.
    /// </summary>
    internal static class AxeAirlaunchTeleport
    {
        public static void DoAirlaunch(Vessel vessel, double altitude, double velocity, double headingDeg)
        {
            CelestialBody body = vessel.mainBody;

            // Current ground position relative to the body centre (Unity XYZ). Release straight up from here.
            Vector3d currentRel = vessel.GetWorldPos3D() - body.position;
            Vector3d up = currentRel.normalized;
            Vector3d teleportPosition = up * (body.Radius + altitude);

            Vector3d east = Vector3d.Cross(body.angularVelocity, teleportPosition).normalized;
            Vector3d north = Vector3d.Cross(east, up);

            // Start from the atmosphere's co-rotation velocity at the release point, then add the surface-
            // relative launch velocity along the heading.
            Vector3d teleportVelocity = Vector3d.Cross(body.angularVelocity, teleportPosition);
            double head = headingDeg * Mathf.Deg2Rad;
            teleportVelocity += (Math.Sin(head) * east + Math.Cos(head) * north) * velocity;
            // Counter the momentary fall while the vessel is on rails (from the original).
            teleportVelocity += up * (body.gravParameter / teleportPosition.sqrMagnitude / 2);

            Vector3d posZup = teleportPosition.xzy;
            Vector3d velZup = teleportVelocity.xzy;

            Vector3d to = teleportPosition.xzy.normalized;
            Quaternion rotation = Quaternion.LookRotation(-to);
            rotation *= Quaternion.AngleAxis((float)headingDeg, Vector3.back);

            Orbit orbit = Clone(vessel.orbitDriver.orbit);
            orbit.UpdateFromStateVectors(posZup, velZup, body, Planetarium.GetUniversalTime());
            SetOrbit(vessel, orbit);
            vessel.SetRotation(rotation);
            ResetGroundContact(vessel);
        }

        // ---- ported HyperEdit helpers (stock API only) ----

        private static Orbit Clone(Orbit o) =>
            new Orbit(o.inclination, o.eccentricity, o.semiMajorAxis, o.LAN,
                      o.argumentOfPeriapsis, o.meanAnomalyAtEpoch, o.epoch, o.referenceBody);

        private static void SetOrbit(Vessel vessel, Orbit newOrbit)
        {
            PrepVesselTeleport(vessel);

            try { OrbitPhysicsManager.HoldVesselUnpack(60); }
            catch (NullReferenceException) { Debug.LogError("[AXE] airlaunch HoldVesselUnpack NRE"); }

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

        private static void PrepVesselTeleport(Vessel vessel)
        {
            if (vessel.Landed) vessel.Landed = false;
            if (vessel.Splashed) vessel.Splashed = false;
            if (vessel.landedAt != string.Empty) vessel.landedAt = string.Empty;

            List<Part> parts = vessel.parts;
            if (parts == null) return;
            foreach (Part part in parts)
                if (part.Modules.Contains<LaunchClamp>())
                    part.Die();
        }

        private static void ResetGroundContact(Vessel vessel)
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
