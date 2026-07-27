using System.Collections;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// A standalone flight-scene gameplay nudge cherry-picked from RP-1's GameplayTips —
    /// only the one that stands alone with no sacked-system dependency:
    ///   * "landed while actually flying" — warns when KSP thinks the vessel has landed while it is
    ///     really still airborne (a known stock physics glitch); ported verbatim.
    ///
    /// Deliberately NOT ported: the interplanetary-avionics reminder (AXE's avionics rewrite has no
    /// interplanetary control-lockout to trigger it) and the airlaunch tip (RP-1's text/trigger are
    /// specific to its SCM simulation UI; AXE's airlaunch has its own editor UX). The "excess EC"
    /// oversized-battery hint was ported once but removed — it fired too indiscriminately to be worth it.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Flight, false)]
    public class AxeGameplayTips : MonoBehaviour
    {
        private void Start()
        {
            // Polls ActiveVessel itself, so it's safe to start regardless of whether a vessel exists yet.
            StartCoroutine(CheckLandedWhileActuallyFlying());
        }

        private static IEnumerator CheckLandedWhileActuallyFlying()
        {
            while (true)
            {
                yield return new WaitForSeconds(5f);

                Vessel v = FlightGlobals.ActiveVessel;
                if (v != null && v.LandedOrSplashed)
                {
                    const float checkThreshold = 150;
                    // radarAltitude reads from the seabed once submerged, so require altitude > 0.
                    if (v.altitude > 0 && v.radarAltitude - v.vesselSize.magnitude > checkThreshold)
                    {
                        ShowTip("ShowLandedWhileActuallyFlyingTip", "Vessel landed",
                            "Error: the game thinks you've landed while you're actually flying. " +
                            "Revert to launch and try again.");
                        yield break;
                    }
                }
            }
        }

        private static void ShowTip(string name, string title, string message)
        {
            PopupDialog.SpawnPopupDialog(new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                name, title, message, "OK", false, HighLogic.UISkin);
        }
    }
}
