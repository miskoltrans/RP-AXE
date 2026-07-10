using System;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// The airlaunch teleport, ported self-contained from ROUtils/KCT <c>HyperEdit_Utilities.DoAirlaunch</c>
    /// (originally the HyperEdit lander by khyperia &amp; Ezriilc). Stock API only — no ROUtils reference.
    ///
    /// The one change from the original: the reference point is the vessel's own current position — the
    /// runway it just launched from — instead of a canonical KSC found via KCT's RSS-aware FindKSC. The
    /// launch site IS the reference, which is both simpler and the right semantics for a relocatable launch
    /// site. <paramref name="distance"/> then offsets the drop point downrange along a great circle on the
    /// <paramref name="bearingDeg"/> bearing; distance 0 releases straight above the site.
    /// </summary>
    internal static class AxeAirlaunchTeleport
    {
        public static void DoAirlaunch(Vessel vessel, double altitude, double velocity, double headingDeg,
                                       double distance, double bearingDeg)
        {
            CelestialBody body = vessel.mainBody;

            // Reference = the launch site the vessel is sitting on (its current position, Unity XYZ rel body).
            Vector3d sitePos = vessel.GetWorldPos3D() - body.position;
            Vector3d siteUp = sitePos.normalized;
            Vector3d siteEast = Vector3d.Cross(body.angularVelocity, sitePos).normalized;
            Vector3d siteNorth = Vector3d.Cross(siteEast, siteUp);
            double siteAltitude = sitePos.magnitude - body.Radius;

            // Great-circle offset: travel `distance` m along the surface from the site on the `bearingDeg`
            // compass bearing (0=N, 90=E), then lift to the release altitude. distance 0 => straight above.
            double delta = distance / body.Radius;
            double bear = bearingDeg * Mathf.Deg2Rad;
            Vector3d dir = siteNorth * Math.Cos(bear) + siteEast * Math.Sin(bear);
            Vector3d teleportPosition = sitePos * Math.Cos(delta) + body.Radius * dir * Math.Sin(delta);
            teleportPosition += teleportPosition.normalized * (altitude - siteAltitude);

            // Release velocity at the drop point: planet co-rotation + surface launch velocity along heading.
            Vector3d up = teleportPosition.normalized;
            Vector3d east = Vector3d.Cross(body.angularVelocity, teleportPosition).normalized;
            Vector3d north = Vector3d.Cross(east, up);
            Vector3d teleportVelocity = Vector3d.Cross(body.angularVelocity, teleportPosition);
            double head = headingDeg * Mathf.Deg2Rad;
            teleportVelocity += (Math.Sin(head) * east + Math.Cos(head) * north) * velocity;
            // Counter the momentary fall while the vessel is on rails (from the original).
            teleportVelocity += up * (body.gravParameter / teleportPosition.sqrMagnitude / 2);

            // Orbit state goes in Zup (orbital) space = the .xzy swizzle of Unity space.
            Vector3d posZup = teleportPosition.xzy;
            Vector3d velZup = teleportVelocity.xzy;

            // Rotation is applied in Unity space, so LookRotation takes the original (unswizzled) up.
            Vector3d to = teleportPosition.normalized;
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
