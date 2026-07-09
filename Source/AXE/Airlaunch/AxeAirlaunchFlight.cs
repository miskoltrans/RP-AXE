using System;
using System.Collections;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// Flight-scene half of the airlaunch. If the editor hook left a pending choice, wait for the vessel to
    /// finish spawning on the runway, teleport it into the released state, then clobber the situation back to
    /// PRELAUNCH -&gt; FLYING (the Principia / persistent-rotation safety dance ported from RP-1's
    /// AirlaunchUtils).
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
                AxeAirlaunchTeleport.DoAirlaunch(v, p.Altitude, p.Velocity, p.Heading);
            }
            catch (Exception e)
            {
                Debug.LogError("[AXE] airlaunch teleport failed: " + e);
                yield break;
            }

            StartCoroutine(ClobberToPrelaunch(id));
            ScreenMessages.PostScreenMessage(
                $"Airlaunch — released at {p.Altitude:0} m, {p.Velocity:0} m/s",
                6f, ScreenMessageStyle.UPPER_CENTER);
        }

        // Hold the vessel in PRELAUNCH while it is still packed, then fire the transition to FLYING so trip
        // loggers etc. notice we are airborne. Ported from RP-1 AirlaunchUtils.ClobberToPrelaunch.
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
