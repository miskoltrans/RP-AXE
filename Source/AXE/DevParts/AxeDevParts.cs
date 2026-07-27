using System.Collections.Generic;
using KSP.UI.Screens;
using UnityEngine;

namespace RPAxe.DevParts
{
    /// <summary>
    /// Per-save persistence for the dev-parts toggle. Its own ScenarioModule rather than a field on
    /// <see cref="AxeProgramHandler"/> because it is a pure editor convenience with no relation to
    /// programs; keeping it separate means neither can corrupt the other's node.
    /// </summary>
    [KSPScenario(
        ScenarioCreationOptions.AddToNewCareerGames | ScenarioCreationOptions.AddToExistingCareerGames,
        GameScenes.SPACECENTER, GameScenes.FLIGHT, GameScenes.TRACKSTATION, GameScenes.EDITOR)]
    public class AxeDevPartsScenario : ScenarioModule
    {
        public static AxeDevPartsScenario Instance { get; private set; }

        /// <summary>NB not named "enabled" — ScenarioModule derives from MonoBehaviour, which owns that.</summary>
        public bool DevPartsOn;

        public override void OnAwake()
        {
            base.OnAwake();
            Instance = this;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        public override void OnLoad(ConfigNode node)
        {
            base.OnLoad(node);
            DevPartsOn = node.HasValue("devPartsOn") && bool.TryParse(node.GetValue("devPartsOn"), out bool v) && v;
        }

        public override void OnSave(ConfigNode node)
        {
            base.OnSave(node);
            node.SetValue("devPartsOn", DevPartsOn, createIfNotFound: true);
        }
    }

    /// <summary>
    /// "Dev parts": design with parts you have researched but not paid the entry cost for, and settle
    /// the bill when you actually launch. Ported from RP-1, where the same feature is a top-right
    /// editor toggle (GUI_DevPartsButton) plus a purchase prompt in KCT's build validator.
    ///
    /// MECHANISM (all stock API): a researched-but-unpurchased part is handed to
    /// <c>ResearchAndDevelopment.AddExperimentalPart</c> — the same flag stock uses for parts a
    /// contract lends you — which makes the editor accept it without payment. Turning the toggle off
    /// hands them all back via RemoveExperimentalPart.
    ///
    /// WHERE THE BILL LANDS: at launch, in <see cref="AxeDevPartsLaunchGate"/>. RP-1 charges when KCT
    /// integrates the vessel; AXE has no KCT, and the deliberate design choice here is that
    /// SIMULATIONS STAY FREE — the simulator is the try-before-you-buy bench, and only committing to a
    /// real flight costs funds.
    ///
    /// NOT covered, on purpose: RealFuels engine CONFIGS. Those are sold separately inside the VAB's
    /// engine-config GUI and priced by design/Tree/AxeEntryCostMods.cfg, so they already have their own
    /// buy-in-the-editor flow. Nor is RP-1's unlock-credit system, which AXE does not have — the price
    /// here is a plain sum of entry costs.
    /// </summary>
    public static class AxeDevParts
    {
        public static bool IsCareer =>
            HighLogic.CurrentGame != null && HighLogic.CurrentGame.Mode == Game.Modes.CAREER;

        public static bool Enabled =>
            AxeDevPartsScenario.Instance != null && AxeDevPartsScenario.Instance.DevPartsOn;

        public static void SetEnabled(bool on)
        {
            if (AxeDevPartsScenario.Instance == null)
            {
                Debug.LogWarning("[AXE][DevParts] No scenario module; toggle ignored.");
                return;
            }

            AxeDevPartsScenario.Instance.DevPartsOn = on;

            if (on) MarkAllUnpaidExperimental();
            else UnmarkAllUnpaidExperimental();

            Debug.Log("[AXE][DevParts] " + (on ? "enabled" : "disabled") + ".");
        }

        /// <summary>
        /// Researched but entry cost never paid. RP-1 reads ResearchAndDevelopment.protoTechNodes
        /// directly — it builds against a publicized Assembly-CSharp and AXE does not — but the two
        /// public helpers say the same thing.
        /// </summary>
        public static bool IsUnlockedButNotPurchased(AvailablePart ap)
        {
            if (ap == null || ResearchAndDevelopment.Instance == null || string.IsNullOrEmpty(ap.TechRequired))
                return false;

            return ResearchAndDevelopment.PartTechAvailable(ap) && !ResearchAndDevelopment.PartModelPurchased(ap);
        }

        public static void MarkAllUnpaidExperimental()
        {
            if (!IsCareer || ResearchAndDevelopment.Instance == null) return;

            foreach (AvailablePart ap in PartLoader.LoadedPartsList)
                if (IsUnlockedButNotPurchased(ap) && !ResearchAndDevelopment.IsExperimentalPart(ap))
                    ResearchAndDevelopment.AddExperimentalPart(ap);
        }

        public static void UnmarkAllUnpaidExperimental()
        {
            if (!IsCareer || ResearchAndDevelopment.Instance == null) return;

            foreach (AvailablePart ap in PartLoader.LoadedPartsList)
                if (IsUnlockedButNotPurchased(ap))
                    ResearchAndDevelopment.RemoveExperimentalPart(ap);
        }

        /// <summary>
        /// Researched-but-unpaid parts used by a saved craft file. Parts whose tech is NOT researched
        /// are ignored: those are genuine contract-lent experimentals and stay free, exactly as stock
        /// intends.
        /// </summary>
        public static List<AvailablePart> UnpaidPartsInCraft(string craftPath)
        {
            var result = new List<AvailablePart>();
            if (!IsCareer || ResearchAndDevelopment.Instance == null || string.IsNullOrEmpty(craftPath))
                return result;

            ConfigNode craft = ConfigNode.Load(craftPath);
            if (craft == null) return result;

            var seen = new HashSet<string>();
            foreach (ConfigNode partNode in craft.GetNodes("PART"))
            {
                string id = partNode.GetValue("part");
                if (string.IsNullOrEmpty(id)) continue;

                string name = KSPUtil.GetPartName(id);
                if (!seen.Add(name)) continue;

                AvailablePart ap = PartLoader.getPartInfoByName(name);
                if (ap != null && IsUnlockedButNotPurchased(ap))
                    result.Add(ap);
            }

            return result;
        }

        public static double UnlockCost(List<AvailablePart> parts)
        {
            double total = 0d;
            foreach (AvailablePart ap in parts)
                total += ap.entryCost;
            return total;
        }

        /// <summary>Spends the funds and marks every part purchased. Returns false (charging nothing) if unaffordable.</summary>
        public static bool Purchase(List<AvailablePart> parts, out string err)
        {
            err = null;
            if (parts == null || parts.Count == 0) return true;

            if (Funding.Instance == null || ResearchAndDevelopment.Instance == null)
            {
                err = "Career systems unavailable.";
                return false;
            }

            double cost = UnlockCost(parts);
            if (Funding.Instance.Funds < cost)
            {
                err = "Insufficient funds.";
                return false;
            }

            Funding.Instance.AddFunds(-cost, TransactionReasons.RnDPartPurchase);
            foreach (AvailablePart ap in parts)
                MarkPurchased(ap);

            EditorPartList.Instance?.Refresh();
            Debug.Log($"[AXE][DevParts] Unlocked {parts.Count} part(s) for {cost:N0} funds at launch.");
            return true;
        }

        private static void MarkPurchased(AvailablePart ap)
        {
            ProtoTechNode node = ResearchAndDevelopment.Instance.GetTechState(ap.TechRequired);
            if (node == null) return;

            AddPurchased(node, ap);

            // Parts sharing a model come along, as stock and RP-1 both do.
            if (!string.IsNullOrEmpty(ap.identicalParts))
            {
                foreach (string raw in ap.identicalParts.Split(','))
                {
                    AvailablePart twin = PartLoader.getPartInfoByName(raw.Replace('_', '.').Trim());
                    if (twin != null && twin.TechRequired == ap.TechRequired)
                        AddPurchased(node, twin);
                }
            }

            ResearchAndDevelopment.RemoveExperimentalPart(ap);
        }

        private static void AddPurchased(ProtoTechNode node, AvailablePart ap)
        {
            if (node.partsPurchased.Contains(ap)) return;

            node.partsPurchased.Add(ap);

            // costsFunds off across the event: we have already paid, and stock listeners would
            // otherwise charge the entry cost a second time.
            ap.costsFunds = false;
            GameEvents.OnPartPurchased.Fire(ap);
            ap.costsFunds = true;
        }
    }
}
