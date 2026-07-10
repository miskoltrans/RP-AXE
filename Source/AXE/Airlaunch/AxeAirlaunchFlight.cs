using System;
using System.Collections;
using System.Reflection;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// Flight-scene half of the airlaunch. If the editor hook left a pending choice, wait for the vessel to
    /// finish spawning on the runway, teleport it to the release point, then run a 10-second countdown that
    /// holds the vessel on a straight, constant-velocity line (counteracting Keplerian drift while it sits
    /// on rails) before releasing control. Ported from RP-1's AirlaunchUtils.DoAirlaunchRoutine; the
    /// teleport + situation clobber are AXE's, everything else is the original hold logic.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Flight, false)]
    public class AxeAirlaunchFlight : MonoBehaviour
    {
        private void Start()
        {
            AxeAirlaunchParams p = AxeAirlaunchState.ConsumePending();
            if (p == null) return;
            Debug.Log($"[AXE] airlaunch pending -> alt {p.Altitude:0} m, vel {p.Velocity:0} m/s, hdg {p.Heading:0}°");
            StartCoroutine(Run(p));
        }

        private IEnumerator Run(AxeAirlaunchParams p)
        {
            // Wait for the vessel to finish spawning before we move it.
            do { yield return new WaitForFixedUpdate(); }
            while (FlightGlobals.ActiveVessel != null && FlightGlobals.ActiveVessel.vesselSpawning);

            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null)
            {
                Debug.LogWarning("[AXE] airlaunch aborted: no active vessel after spawn.");
                yield break;
            }
            Guid id = v.id;

            // The teleport wants the vessel out of PRELAUNCH first (matching RP-1).
            if (v.situation == Vessel.Situations.PRELAUNCH)
                v.situation = Vessel.Situations.LANDED;

            try
            {
                AxeAirlaunchTeleport.DoAirlaunch(v, p.Altitude, p.Velocity, p.Heading, p.Distance, p.Bearing);
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE] airlaunch teleport failed: " + e);
                yield break;
            }

            StartCoroutine(ClobberToPrelaunch(id));

            // --- Countdown + straight-line physics hold (ported from RP-1 AirlaunchUtils) ---

            // Keep the vessel on rails with both of RP-1's holds, refreshed every fixed update below:
            // OrbitPhysicsManager.HoldVesselUnpack (the FixedUpdate-based GoOffRails gate) and
            // Vessel.SetPhysicsHoldExpiryOverride (the render-frame direct-GoOffRails guard). The latter is an
            // INTERNAL stock method, so we reach it through a cached reflection delegate — see _setPhysHold.
            HoldPhysics(v);

            // One fixed update for the teleport to settle before we snapshot the state to hold.
            yield return new WaitForFixedUpdate();

            // The artificial hold keeps the physics-hold control lock set; drop it so controls work on release.
            InputLockManager.RemoveControlLock("physicsHold");

            v = FlightGlobals.ActiveVessel;
            if (v == null || v.id != id) yield break;

            // Snapshot the trajectory we want to hold constant: a straight line at constant surface velocity.
            // Without re-patching each frame, patched-conic propagation would curve the velocity down and
            // change speed over the 10-second hold.
            double holdStartUT = Planetarium.GetUniversalTime();
            Vector3d holdStartRelPos = v.GetWorldPos3D() - v.mainBody.position;   // Unity XYZ, rel body centre
            Vector3d up = holdStartRelPos.normalized;
            Vector3d omega = v.mainBody.angularVelocity;
            Vector3d planetRotVelocity = Vector3d.Cross(omega, holdStartRelPos);  // atmosphere co-rotation
            Vector3d east = planetRotVelocity.normalized;
            Vector3d north = Vector3d.Cross(east, up);
            double headRad = p.Heading * Mathf.Deg2Rad;
            Vector3d holdStartSurfVel = (Math.Sin(headRad) * east + Math.Cos(headRad) * north) * p.Velocity;

            for (int i = 10; i > 0; i--)
            {
                ScreenMessages.PostScreenMessage($"Airlaunching in {i}...", 1f, ScreenMessageStyle.UPPER_CENTER, XKCDColors.Red);

                float elapsed = 0f;
                while (elapsed < 1f)
                {
                    v = FlightGlobals.ActiveVessel;
                    if (v == null || v.id != id)
                    {
                        Debug.LogWarning("[AXE] airlaunch: active vessel changed mid-countdown; aborting hold.");
                        yield break;
                    }

                    // Advance the position along the launch heading at the release velocity, co-rotated with
                    // the planet — the distance a carrier aircraft would cover during the count.
                    double deltaT = Planetarium.GetUniversalTime() - holdStartUT;
                    float rotAngleDeg = (float)(omega.magnitude * deltaT * Mathf.Rad2Deg);
                    Quaternion rot = Quaternion.AngleAxis(rotAngleDeg, (Vector3)omega.normalized);
                    Vector3d velocityOffset = holdStartSurfVel - planetRotVelocity;
                    Vector3d newRelPos = (Vector3d)(rot * (Vector3)(holdStartRelPos + velocityOffset * deltaT));

                    // Inertial velocity = frame velocity at the new position + rotated surface launch velocity.
                    Vector3d newObtVel = Vector3d.Cross(omega, newRelPos) + (Vector3d)(rot * (Vector3)holdStartSurfVel);

                    // UpdateFromStateVectors expects Zup (orbital) space = the .xzy swizzle of Unity space.
                    v.orbit.UpdateFromStateVectors(newRelPos.xzy, newObtVel.xzy, v.mainBody, Planetarium.GetUniversalTime());

                    // Move the transform to match now, mirroring OrbitDriver.updateFromParameters — otherwise
                    // the transform stays at last frame's Keplerian position until the next frame.
                    Vector3d localCom = (QuaternionD)v.orbitDriver.driverTransform.rotation * (Vector3d)v.localCoM;
                    v.SetPosition(v.mainBody.position + newRelPos - localCom);

                    HoldPhysics(v);
                    yield return new WaitForFixedUpdate();
                    elapsed += Time.fixedDeltaTime;
                }
            }

            // Release the holds; the vessel comes off rails and ClobberToPrelaunch fires the FLYING event.
            OrbitPhysicsManager.HoldVesselUnpack(1);
            v = FlightGlobals.ActiveVessel;
            if (v != null) _setPhysHold?.Invoke(v, 1);

            ScreenMessages.PostScreenMessage(
                $"Airlaunch — released at {p.Altitude:0} m, {p.Velocity:0} m/s",
                5f, ScreenMessageStyle.UPPER_CENTER);
        }

        // Refresh both unpack holds for a couple of fixed updates (call every FixedUpdate to sustain them).
        private static void HoldPhysics(Vessel v)
        {
            OrbitPhysicsManager.HoldVesselUnpack(2);
            _setPhysHold?.Invoke(v, 60);
        }

        // Vessel.SetPhysicsHoldExpiryOverride(int) is INTERNAL in stock Assembly-CSharp, so AXE (a separate
        // assembly) can't call it directly — RP-1 builds against a publicized assembly. Bind it once via
        // reflection; null if a future KSP renames/removes it, in which case we degrade to HoldVesselUnpack.
        private static readonly Action<Vessel, int> _setPhysHold = ResolveSetPhysHold();

        private static Action<Vessel, int> ResolveSetPhysHold()
        {
            MethodInfo mi = typeof(Vessel).GetMethod("SetPhysicsHoldExpiryOverride",
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public,
                null, new[] { typeof(int) }, null);
            if (mi == null)
            {
                Debug.LogWarning("[AXE] airlaunch: Vessel.SetPhysicsHoldExpiryOverride(int) not found; using HoldVesselUnpack only.");
                return null;
            }
            return (Action<Vessel, int>)Delegate.CreateDelegate(typeof(Action<Vessel, int>), mi);
        }

        // Hold the vessel in PRELAUNCH while still packed, then fire the transition to FLYING so trip loggers
        // etc. notice we are airborne. Ported from RP-1 AirlaunchUtils.ClobberToPrelaunch.
        private IEnumerator ClobberToPrelaunch(Guid id)
        {
            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null || v.id != id) yield break;

            do
            {
                v.situation = Vessel.Situations.PRELAUNCH;
                yield return new WaitForFixedUpdate();
                v = FlightGlobals.ActiveVessel;
            } while (v != null && v.id == id && v.packed);

            if (v == null || v.id != id) yield break;

            v.situation = Vessel.Situations.FLYING;
            GameEvents.onVesselSituationChange.Fire(
                new GameEvents.HostedFromToAction<Vessel, Vessel.Situations>(
                    v, Vessel.Situations.PRELAUNCH, Vessel.Situations.FLYING));
        }
    }
}
