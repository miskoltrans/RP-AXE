using System;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// The airlaunch teleport. Computes an atmospheric release point from the vessel's own launch site
    /// (its current position) plus a downrange offset, then hands the resulting orbit state to the shared
    /// <see cref="AxeVesselTeleport"/> primitive (ported from ROUtils/KCT HyperEdit_Utilities).
    ///
    /// The reference point is the vessel's own current position — the runway it just launched from —
    /// instead of a canonical KSC. The launch site IS the reference, which is both simpler and the right
    /// semantics for a relocatable launch site. <paramref name="distance"/> then offsets the drop point
    /// downrange along a great circle on the <paramref name="bearingDeg"/> bearing; distance 0 releases
    /// straight above the site.
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

            Orbit orbit = AxeVesselTeleport.Clone(vessel.orbitDriver.orbit);
            orbit.UpdateFromStateVectors(posZup, velZup, body, Planetarium.GetUniversalTime());
            AxeVesselTeleport.SetOrbit(vessel, orbit);
            vessel.SetRotation(rotation);
            AxeVesselTeleport.ResetGroundContact(vessel);
        }
    }
}
