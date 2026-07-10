using UnityEngine;

namespace RPAxe.Contracts
{
    /// <summary>
    /// ContractConfigurator caps the number of simultaneously-offered contracts per prestige tier
    /// (trivial / significant / exceptional). AXE's stripped contract pack still carries `prestige =`
    /// tags, so without this the offer count is silently split across tiers. Ported from RP-1's
    /// ContractLimitOverrider: flatten all three tier caps to the stock active-contracts limit, which
    /// matches "money/grind is not the bottleneck." Runs on entering the Space Center (idempotent; the
    /// value persists on HighLogic.CurrentGame.Parameters for the rest of the session).
    /// </summary>
    [KSPAddon(KSPAddon.Startup.SpaceCentre, false)]
    public class ContractLimitOverrider : MonoBehaviour
    {
        private void Start()
        {
            if (HighLogic.CurrentGame == null || HighLogic.CurrentGame.Mode != Game.Modes.CAREER)
                return;

            int maxActive = GameVariables.Instance.GetActiveContractsLimit(
                ScenarioUpgradeableFacilities.GetFacilityLevel(SpaceCenterFacility.MissionControl));

            var p = HighLogic.CurrentGame.Parameters.CustomParams<ContractConfigurator.ContractConfiguratorParameters>();
            p.trivialContractLimit = maxActive;
            p.significantContractLimit = maxActive;
            p.exceptionalContractLimit = maxActive;

            Debug.Log($"[AXE] Contract tier limits flattened to {maxActive}.");
        }
    }
}
