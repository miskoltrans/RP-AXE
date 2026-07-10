using System.Collections;
using System.Linq;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// A couple of standalone flight-scene gameplay nudges cherry-picked from RP-1's GameplayTips —
    /// only the ones that stand alone with no sacked-system dependency:
    ///   * "landed while actually flying" — warns when KSP thinks the vessel has landed while it is
    ///     really still airborne (a known stock physics glitch); ported verbatim.
    ///   * "excess EC" — an early-game hint that multi-MW·h battery banks are unnecessary; shown once
    ///     per launch until the electronics era. RP-1 gated this on its own `electronicsSatellite`
    ///     tech; AXE gates it on <see cref="EarlyEraTechId"/> (change the id to re-tune when it stops).
    ///
    /// Deliberately NOT ported: the interplanetary-avionics reminder (AXE's avionics rewrite has no
    /// interplanetary control-lockout to trigger it) and the airlaunch tip (RP-1's text/trigger are
    /// specific to its SCM simulation UI; AXE's airlaunch has its own editor UX).
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Flight, false)]
    public class AxeGameplayTips : MonoBehaviour
    {
        // Once this tech is researched we stop nagging about oversized batteries. Early electronics
        // node in AXE's tree; re-point if the tree changes.
        private const string EarlyEraTechId = "elec_transistor";
        private const double ExcessECThreshold = 10000;

        private void Start()
        {
            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null) return;

            if (VesselHasExcessEC(v))
                ShowTip("ShowExcessECTip", "Oversized battery",
                    "This vessel carries a very large electric-charge reserve. Early missions rarely " +
                    "need more than a modest battery — the extra mass is usually better spent elsewhere.");

            StartCoroutine(CheckLandedWhileActuallyFlying());
        }

        private static bool VesselHasExcessEC(Vessel v)
        {
            // Beyond the early electronics era this is no longer worth flagging.
            if (ResearchAndDevelopment.GetTechnologyState(EarlyEraTechId) == RDTech.State.Available)
                return false;

            double ecTotal = v.Parts.Sum(p => p.Resources.Get("ElectricCharge")?.maxAmount ?? 0);
            return ecTotal > ExcessECThreshold;
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
