using System;
using System.Collections.Generic;
using System.Text;
using HarmonyLib;
using RPAxe.Simulation;
using UnityEngine;

namespace RPAxe.DevParts
{
    /// <summary>
    /// Where dev parts get paid for: the moment a craft is committed to a real flight.
    ///
    /// HOOK: <c>FlightDriver.StartWithNewLaunch</c>, the single funnel both stock launch paths run
    /// through — the editor's Launch button (EditorLogic.goForLaunch) and the KSC launchpad's craft
    /// browser (LaunchSiteFacility). Patching the funnel instead of the editor closes the obvious
    /// dodge of saving the craft and launching it from the pad. It also means we always have the saved
    /// craft file to read, so one code path serves both.
    ///
    /// SIMULATIONS ARE EXEMPT by design: AXE's simulator calls this same method, but sets
    /// <c>AxeSimulation.IsSimulatedFlight</c> first, so a sim flies unpaid parts for free. Testing a
    /// design you have not bought yet is the whole point of pairing the two features.
    /// </summary>
    [HarmonyPatch(typeof(FlightDriver), nameof(FlightDriver.StartWithNewLaunch))]
    internal static class AxeDevPartsLaunchGate
    {
        /// <summary>Set for the one re-entry we make ourselves after the player pays.</summary>
        private static bool _paid;

        private static bool Prefix(string fullFilePath, string missionFlagURL, string launchSiteName, VesselCrewManifest manifest)
        {
            if (_paid)
            {
                _paid = false;
                return true;
            }

            try
            {
                if (!AxeDevParts.IsCareer) return true;
                if (AxeSimulation.IsSimulatedFlight) return true;

                List<AvailablePart> unpaid = AxeDevParts.UnpaidPartsInCraft(fullFilePath);
                if (unpaid.Count == 0) return true;

                ShowPurchaseDialog(unpaid, () =>
                {
                    _paid = true;
                    FlightDriver.StartWithNewLaunch(fullFilePath, missionFlagURL, launchSiteName, manifest);
                });

                return false;    // hold the launch until the dialog decides
            }
            catch (Exception e)
            {
                // Never strand the player in the editor because of a bug in here.
                Debug.LogError("[AXE][DevParts] Launch gate failed, allowing launch: " + e);
                return true;
            }
        }

        private static void ShowPurchaseDialog(List<AvailablePart> parts, Callback onPaid)
        {
            double cost = AxeDevParts.UnlockCost(parts);
            bool affordable = Funding.Instance != null && Funding.Instance.Funds >= cost;

            var body = new StringBuilder();
            body.AppendLine("This vessel uses parts you have researched but not yet paid the entry cost for:\n");

            const int shown = 12;
            for (int i = 0; i < parts.Count && i < shown; i++)
                body.AppendLine($"  • {parts[i].title}  —  <sprite=\"CurrencySpriteAsset\" name=\"Funds\" tint=1>{parts[i].entryCost:N0}");
            if (parts.Count > shown)
                body.AppendLine($"  … and {parts.Count - shown} more");

            body.AppendLine($"\nTotal: <sprite=\"CurrencySpriteAsset\" name=\"Funds\" tint=1>{cost:N0}");
            if (!affordable)
                body.AppendLine($"\n<color=#ff8000>You cannot afford this — you have <sprite=\"CurrencySpriteAsset\" name=\"Funds\" tint=1>{(Funding.Instance?.Funds ?? 0):N0}.</color>");
            else
                body.AppendLine("\n(Simulating this craft would cost nothing.)");

            string unlockLabel = $"Unlock {parts.Count} part{(parts.Count > 1 ? "s" : "")} for <sprite=\"CurrencySpriteAsset\" name=\"Funds\" tint=1>{cost:N0} and launch";

            var buttons = new List<DialogGUIButton>
            {
                new DialogGUIButton("Back to editor", () => { })
            };

            if (affordable)
            {
                buttons.Add(new DialogGUIButton(unlockLabel, () =>
                {
                    if (AxeDevParts.Purchase(parts, out string err))
                    {
                        onPaid();
                    }
                    else
                    {
                        ScreenMessages.PostScreenMessage("Could not unlock parts: " + err, 6f, ScreenMessageStyle.UPPER_CENTER);
                    }
                }));
            }

            PopupDialog.SpawnPopupDialog(
                new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                new MultiOptionDialog("AxeDevPartsPurchase", body.ToString(), "Unpaid parts", HighLogic.UISkin,
                    new Rect(0.5f, 0.5f, 320f, 100f),
                    new DialogGUIFlexibleSpace(),
                    new DialogGUIVerticalLayout(buttons.ToArray())),
                persistAcrossScenes: false, skin: HighLogic.UISkin);
        }
    }
}
