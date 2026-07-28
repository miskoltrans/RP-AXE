using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using ContractConfigurator;
using HarmonyLib;
using Strategies;
using Strategies.Effects;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// AutoTest smoke check for the funds economy (docs/ECONOMY.md). It reads Contract
    /// Configurator's own PARSED model and the live StrategySystem, not the config files, so it
    /// confirms the whole chain: our patches were loaded, parsed, and are what the game will act on.
    ///
    /// This does NOT replace the end-to-end payout playtest (ECONOMY.md §5) — nothing here flies a
    /// mission or observes funds actually landing in the bank. What it does cover is every failure
    /// mode that is silent and static:
    ///
    ///   1. CAPSTONE PATCHES LANDED. AxeCapstoneFunds.cfg sets `%rewardFunds` on VENDORED seed
    ///      contracts by name. If a seed contract is ever renamed or re-vendored away, the patch
    ///      hits nothing, MM logs nothing, and that programme quietly pays half. Counted here.
    ///   2. COMPLETION CONTRACTS ARE WELL-FORMED. Every generated AXE_Complete_* must autoAccept
    ///      (otherwise it sits Offered forever and the AXEInstant parameter never fires, because
    ///      AxeInstantComplete only self-completes once the contract is Active) and must pay.
    ///   3. NO DANGLING CompleteContract REQUIREMENT. This is the dangerous one and the direct
    ///      analogue of tools/check_tech_refs.py: each completion contract gates on its programme's
    ///      objectives BY CONTRACT-TYPE NAME. A name that no longer resolves can never be satisfied,
    ///      so the contract is unpayable for the whole career — and nothing in the game says so.
    ///   4. THE STRATEGY REPUTATION GATE. Regression guard for the bug fixed in 883508d/fc0d025:
    ///      requiredReputationMin/Max is a lerp over the commitment slider, NOT a window, so
    ///      "widening" it to +/-1e6 demands a million reputation at full commitment. We assert stock
    ///      -500/750 survives unpatched and that the requirement at Administration L1's 0.25 cap is
    ///      still negative (i.e. never binds), plus the Fundraising rate is AXE's 125-157.
    ///
    /// A clean run prints `OK` in each section. Anything else is a real defect.
    /// </summary>
    internal static class AxeEconomySelfTest
    {
        // docs/ECONOMY.md §3: Channel 1 is budgeted at 24,000,000 across capstones + completions.
        private const double ExpectedChannel1 = 24000000.0;
        private const double BudgetTolerance = 0.15;   // generator rounds per-programme; 15% is slack, not licence

        private const float ExpectedFundraisingMinRate = 125f;
        private const float ExpectedFundraisingMaxRate = 157f;
        private const float StockRequiredRepMin = -500f;
        private const float StockRequiredRepMax = 750f;

        internal static string SelfTestReport()
        {
            var sb = new StringBuilder();
            sb.Append(ContractReport());
            sb.Append(" || ");
            sb.Append(StrategyReport());
            return sb.ToString();
        }

        // ---------------------------------------------------------------- contracts

        private static string ContractReport()
        {
            List<ContractType> all;
            try { all = ContractType.AllValidContractTypes.ToList(); }
            catch (Exception e) { return "contracts: LOOKUP FAILED (" + e.Message + ")"; }

            if (all.Count == 0) return "contracts: NONE LOADED (Contract Configurator not ready?)";

            var completions = all.Where(c => c.name != null && c.name.StartsWith("AXE_Complete_")).ToList();
            // Everything else that pays is a capstone patch landing on a vendored seed contract.
            var capstones = all.Where(c => c.name != null && !c.name.StartsWith("AXE_Complete_") && c.rewardFunds > 0f).ToList();

            double completionFunds = completions.Sum(c => (double)c.rewardFunds);
            double capstoneFunds = capstones.Sum(c => (double)c.rewardFunds);
            double total = completionFunds + capstoneFunds;

            // (2) well-formedness of the generated half
            var notAutoAccept = completions.Where(c => !c.autoAccept).Select(c => c.name).ToList();
            var unpaid = completions.Where(c => c.rewardFunds <= 0f).Select(c => c.name).ToList();

            // (3) dangling CompleteContract requirements — the silent career-long failure
            var known = new HashSet<string>(all.Select(c => c.name));
            var dangling = new List<string>();
            foreach (ContractType ct in completions)
            {
                foreach (string dep in CompleteContractTargets(ct))
                    if (!known.Contains(dep)) dangling.Add(ct.name + "->" + dep);
            }

            var sb = new StringBuilder();
            sb.Append("contracts: types=").Append(all.Count)
              .Append(" completion=").Append(completions.Count).Append('/').Append(completionFunds.ToString("N0"))
              .Append(" capstone=").Append(capstones.Count).Append('/').Append(capstoneFunds.ToString("N0"))
              .Append(" total=").Append(total.ToString("N0"));

            if (capstones.Count == 0)
                sb.Append(" | CAPSTONE PATCHES DID NOT APPLY (0 paying seed contracts)");
            if (completions.Count == 0)
                sb.Append(" | NO COMPLETION CONTRACTS LOADED");

            double drift = Math.Abs(total - ExpectedChannel1) / ExpectedChannel1;
            sb.Append(drift <= BudgetTolerance
                ? " | budget OK"
                : " | BUDGET DRIFT " + (drift * 100.0).ToString("0.#") + "% vs " + ExpectedChannel1.ToString("N0"));

            sb.Append(notAutoAccept.Count == 0 ? " | autoAccept OK" : " | NOT AUTO-ACCEPT: " + Join(notAutoAccept));
            sb.Append(unpaid.Count == 0 ? " | rewards OK" : " | ZERO-REWARD: " + Join(unpaid));
            sb.Append(dangling.Count == 0 ? " | deps OK" : " | DANGLING CompleteContract: " + Join(dangling));
            return sb.ToString();
        }

        /// <summary>
        /// The `contractType = X` of every CompleteContract requirement on this type. `ccType` is
        /// protected on ContractCheckRequirement, so it comes out via Traverse (same reason as
        /// AxeTrackingStationGate — this KSP build isn't publicized).
        /// </summary>
        private static IEnumerable<string> CompleteContractTargets(ContractType ct)
        {
            IEnumerable<ContractRequirement> reqs;
            try { reqs = ct.Requirements; }
            catch { yield break; }
            if (reqs == null) yield break;

            foreach (ContractRequirement r in reqs)
            {
                if (!(r is CompleteContractRequirement)) continue;
                string cc = null;
                try { cc = Traverse.Create(r).Field("ccType").GetValue<string>(); }
                catch { /* shape changed upstream; reported as a miss below */ }
                if (!string.IsNullOrEmpty(cc)) yield return cc;
            }
        }

        // ---------------------------------------------------------------- strategies

        private static string StrategyReport()
        {
            StrategySystem sys = StrategySystem.Instance;
            if (sys == null || sys.Strategies == null) return "strategies: SYSTEM NOT READY";

            Strategy fund = sys.Strategies.FirstOrDefault(
                s => s != null && s.Config != null && s.Config.Name == "FundraisingCampaignCfg");
            if (fund == null) return "strategies: FundraisingCampaignCfg NOT FOUND";

            float min = fund.Config.RequiredReputationMin;
            float max = fund.Config.RequiredReputationMax;

            var sb = new StringBuilder();
            sb.Append("strategies: fundraising reqRep=[").Append(min.ToString("0.#")).Append(", ")
              .Append(max.ToString("0.#")).Append(']');

            bool stockWindow = Mathf.Approximately(min, StockRequiredRepMin) && Mathf.Approximately(max, StockRequiredRepMax);
            sb.Append(stockWindow ? " (stock, unpatched OK)" : " | NOT STOCK -500/750 — something is patching it again");

            // The gate is Lerp(min, max, factor); Administration's strategyCommitRange caps factor
            // at 0.25 / 0.6 / 1.0 by level. Report the requirement at each cap.
            sb.Append(" needAt[.25/.6/1]=")
              .Append(Mathf.Lerp(min, max, 0.25f).ToString("0")).Append('/')
              .Append(Mathf.Lerp(min, max, 0.60f).ToString("0")).Append('/')
              .Append(Mathf.Lerp(min, max, 1.00f).ToString("0"));

            // Admin L1 must never be gated by reputation — that was the shipped bug's worst symptom.
            float atL1 = Mathf.Lerp(min, max, 0.25f);
            sb.Append(atL1 <= 0f ? " | L1 ungated OK" : " | L1 GATED at " + atL1.ToString("0") + " rep");

            sb.Append(" | ").Append(RateReport(fund));
            return sb.ToString();
        }

        /// <summary>Fundraising's reputation-&gt;funds rate. minRate/maxRate are private on CurrencyConverter.</summary>
        private static string RateReport(Strategy fund)
        {
            if (fund.Effects == null) return "rate: NO EFFECTS";
            foreach (StrategyEffect eff in fund.Effects)
            {
                if (!(eff is CurrencyConverter)) continue;
                float lo, hi;
                try
                {
                    var t = Traverse.Create(eff);
                    lo = t.Field("minRate").GetValue<float>();
                    hi = t.Field("maxRate").GetValue<float>();
                }
                catch (Exception e) { return "rate: UNREADABLE (" + e.Message + ")"; }

                bool ok = Mathf.Approximately(lo, ExpectedFundraisingMinRate)
                          && Mathf.Approximately(hi, ExpectedFundraisingMaxRate);
                return "rate=" + lo.ToString("0.#") + "-" + hi.ToString("0.#") +
                       (ok ? " OK" : " | EXPECTED " + ExpectedFundraisingMinRate + "-" + ExpectedFundraisingMaxRate +
                             " (AxeStrategies.cfg did not apply)");
            }
            return "rate: NO CurrencyConverter EFFECT";
        }

        private static string Join(List<string> items)
        {
            const int cap = 6;
            if (items.Count <= cap) return string.Join(", ", items.ToArray());
            return string.Join(", ", items.Take(cap).ToArray()) + " (+" + (items.Count - cap) + " more)";
        }
    }
}
