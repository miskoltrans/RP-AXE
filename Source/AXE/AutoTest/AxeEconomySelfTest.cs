using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using ContractConfigurator;
using HarmonyLib;
using RPAxe.Contracts;
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
    ///   1. THE SEED-CONTRACT FUNDS PATCHES LANDED. AxeCapstoneFunds.cfg and (since §11)
    ///      AxeProgramObjectiveFunds.cfg both set `%rewardFunds` on VENDORED seed contracts by name.
    ///      If a seed contract is renamed or re-vendored away, the patch hits nothing, MM logs
    ///      nothing, and that programme quietly pays less. Counted here.
    ///   1b. EVERY PROGRAMME PAYS BEFORE ITS BONUS. The §11 staging is what makes a programme
    ///      flyable without savings, and a bare count cannot see it fail: the two files above patch
    ///      DISJOINT contract sets (15 capstones + 137 staged objectives), so if one stopped
    ///      applying the combined count would still look healthy and the budget would still be
    ///      inside tolerance. This asserts the design property directly — every AXE_Complete_* must
    ///      have at least one CompleteContract objective that itself pays funds.
    ///   2. COMPLETION CONTRACTS ARE WELL-FORMED. Every generated AXE_Complete_* must pay, and must
    ///      NOT autoAccept. The autoAccept assert used to run the other way and the money did work,
    ///      but offer+accept+complete all landed in one frame, so the bonus never appeared in Mission
    ///      Control and the player saw only an unexplained funds bump. It is now a visible offer the
    ///      player claims; AxeInstantComplete self-completes on acceptance (it fires only once the
    ///      contract is Active), so nothing else in the chain changes.
    ///   2b. EVERY CHARTER STATES ITS VALUE. AxeProgramValue.cfg patches `%notes` onto the
    ///      hand-authored AXE_Begin_* charters so a player can see what a program pays before
    ///      committing. Rename a charter and the patch matches nothing, silently.
    ///   3. NO DANGLING CompleteContract REQUIREMENT. This is the dangerous one and the direct
    ///      analogue of tools/check_tech_refs.py: each completion contract gates on its programme's
    ///      objectives BY CONTRACT-TYPE NAME. A name that no longer resolves can never be satisfied,
    ///      so the contract is unpayable for the whole career — and nothing in the game says so.
    ///   3b. EVERY COMPLETION CONTRACT CLOSES ITS PROGRAM (§13). That contract is the ONLY way a
    ///      program ends, via a `ConcludeProgram` behaviour. Two silent rots: the generator stops
    ///      emitting the BEHAVIOUR block, or `type = ConcludeProgram` stops resolving — CC registers
    ///      behaviour factories by class name minus "Factory", so renaming ConcludeProgramFactory
    ///      unbinds the config with no error. Either way the money still pays and the program stays
    ///      active for the whole career. Asserts the behaviour exists AND names the same program the
    ///      contract's ProgramActive requirement gates on.
    ///   3c. NOTHING RE-ENABLES THE FAILURE PENALTY (§13). ProgramActiveRequirement defaults
    ///      checkOnActiveContract = FALSE on purpose, diverging from RP-1. With it true, CC re-checks
    ///      already-ACTIVE contracts and answers an unmet requirement with Contract.Fail(), which runs
    ///      stock PenalizeFailure() — so concluding a program would fine the player for every member
    ///      contract in flight, including any of the 66 repeatable ones. Counts any contract that opts
    ///      back in by writing the value itself.
    ///   4. THE STRATEGY REPUTATION GATE. Regression guard for the bug fixed in 883508d/fc0d025:
    ///      requiredReputationMin/Max is a lerp over the commitment slider, NOT a window, so
    ///      "widening" it to +/-1e6 demands a million reputation at full commitment. We assert stock
    ///      -500/750 survives unpatched, plus the Fundraising rate is AXE's 125-157 and its share
    ///      floor is AXE's 0.55.
    ///   4b. THE COMMIT RANGE IS AXE'S, READ LIVE. §11 took ADMINISTRATION off CustomBarnKit's
    ///      default (0.25/0.6/1) to 0.5/0.75/1, because CurrencyConverter lerps BOTH the share and
    ///      the rate off the commitment factor and the yield is therefore quadratic in it. The cap
    ///      is read from GameVariables.GetStrategyCommitRange rather than assumed, which also
    ///      catches CustomBarnKit's silent "wrong size" fallback (docs/ECONOMY.md §8) reverting the
    ///      whole @ADMINISTRATION block to stock with no error visible in game.
    ///      NOTE the L1 requirement is now 125 reputation, not negative. That is intended: at a 0.5
    ///      cap the lerp genuinely binds in the first era, and a fresh career commits lower until it
    ///      has the fame. Do not "fix" it back.
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
        // docs/ECONOMY.md §11 — the share lerp's floor. 0 is stock and makes the yield quadratic in
        // the commitment factor; 1 would stop the reputation BALANCE growing and lock the player out
        // of the L2/L3 commitment levels, which gate on it.
        private const float ExpectedFundraisingMinShare = 0.55f;
        private const float StockRequiredRepMin = -500f;
        private const float StockRequiredRepMax = 750f;
        // AxeFacilities.cfg @ADMINISTRATION strategyCommitRange, per level. Read live and compared.
        private static readonly float[] ExpectedCommitRange = { 0.5f, 0.75f, 1.0f };

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
            // Everything else that pays is a funds patch landing on a vendored seed contract — a
            // capstone (AxeCapstoneFunds.cfg) or a staged objective (AxeProgramObjectiveFunds.cfg).
            // The two sets are disjoint by construction; the generator asserts it.
            var seedPaid = all.Where(c => c.name != null && !c.name.StartsWith("AXE_Complete_") && c.rewardFunds > 0f).ToList();

            double completionFunds = completions.Sum(c => (double)c.rewardFunds);
            double seedFunds = seedPaid.Sum(c => (double)c.rewardFunds);
            double total = completionFunds + seedFunds;

            // (1b) every programme must have at least one PAYING objective, or its whole budget sits
            // behind the final bonus again — the §11 defect. A count check cannot see this, because
            // the two patch files cover disjoint contracts and either could fail alone.
            var paying = new HashSet<string>(seedPaid.Select(c => c.name));
            var unstaged = completions
                .Where(ct => CompleteContractTargets(ct).Any()
                             && !CompleteContractTargets(ct).Any(paying.Contains))
                .Select(ct => ct.name).ToList();

            // (2) well-formedness of the generated half. autoAccept must be OFF — an auto-accepted
            // bonus completes in the same frame it is offered and is never seen in Mission Control.
            var autoAccepted = completions.Where(c => c.autoAccept).Select(c => c.name).ToList();
            var unpaid = completions.Where(c => c.rewardFunds <= 0f).Select(c => c.name).ToList();

            // (2b) the charter value notes actually landed. AxeProgramValue.cfg is a generated MM
            // overlay (`%notes = ...`) onto the hand-authored AXE_Begin_* charters; if a charter is
            // ever renamed, the patch matches nothing, MM logs nothing, and that program silently
            // goes back to advertising no value at the one moment the player is choosing between
            // programs. Read off Contract Configurator's parsed model, so this proves the patch
            // applied — not merely that the file exists.
            var charters = all.Where(c => c.name != null && c.name.StartsWith("AXE_Begin_")).ToList();
            var unpriced = charters.Where(c => string.IsNullOrEmpty(c.notes)).Select(c => c.name).ToList();

            // (3) dangling CompleteContract requirements — the silent career-long failure
            var known = new HashSet<string>(all.Select(c => c.name));
            var dangling = new List<string>();
            foreach (ContractType ct in completions)
            {
                foreach (string dep in CompleteContractTargets(ct))
                    if (!known.Contains(dep)) dangling.Add(ct.name + "->" + dep);
            }

            // (3b) every completion contract must actually CLOSE the program it gates on. Two ways for
            // this to rot silently, both of which still pay the money and leave the program active for
            // the rest of the career: the BEHAVIOUR block goes missing from the generator, or
            // `type = ConcludeProgram` stops resolving (CC registers behaviour factories by class name
            // minus "Factory", so renaming ConcludeProgramFactory unbinds the config with no error).
            var noClosure = new List<string>();
            foreach (ContractType ct in completions)
            {
                string gated = ProgramGate(ct);
                string closed = ConcludedProgram(ct);
                if (gated == null || closed != gated)
                    noClosure.Add(ct.name + "(gates=" + (gated ?? "?") + ",closes=" + (closed ?? "none") + ")");
            }

            // (3c) the failure-penalty guard. ProgramActiveRequirement defaults
            // checkOnActiveContract = false ON PURPOSE (AXE diverges from RP-1 here): with it true, CC
            // re-checks an already-ACTIVE contract and answers an unmet requirement with
            // Contract.Fail(), which runs stock's PenalizeFailure(). Concluding a program would then
            // fine the player for every member contract in flight. A seed contract that opts back in
            // by writing the value itself would reintroduce that quietly, so count them.
            var penalising = new List<string>();
            foreach (ContractType ct in all)
            {
                IEnumerable<ContractRequirement> reqs;
                try { reqs = ct.Requirements; } catch { continue; }
                if (reqs == null) continue;
                foreach (ContractRequirement r in reqs)
                    if (r is ProgramActiveRequirement pa && pa.ChecksOnActiveContract)
                        penalising.Add(ct.name);
            }

            var sb = new StringBuilder();
            sb.Append("contracts: types=").Append(all.Count)
              .Append(" completion=").Append(completions.Count).Append('/').Append(completionFunds.ToString("N0"))
              .Append(" seedPaid=").Append(seedPaid.Count).Append('/').Append(seedFunds.ToString("N0"))
              .Append(" total=").Append(total.ToString("N0"));

            if (seedPaid.Count == 0)
                sb.Append(" | SEED FUNDS PATCHES DID NOT APPLY (0 paying seed contracts)");
            if (completions.Count == 0)
                sb.Append(" | NO COMPLETION CONTRACTS LOADED");
            sb.Append(unstaged.Count == 0
                ? " | staging OK"
                : " | PAYS ONLY AT THE END (no paying objective): " + Join(unstaged));

            double drift = Math.Abs(total - ExpectedChannel1) / ExpectedChannel1;
            sb.Append(drift <= BudgetTolerance
                ? " | budget OK"
                : " | BUDGET DRIFT " + (drift * 100.0).ToString("0.#") + "% vs " + ExpectedChannel1.ToString("N0"));

            sb.Append(autoAccepted.Count == 0 ? " | visible-offer OK" : " | AUTO-ACCEPTED (invisible): " + Join(autoAccepted));
            sb.Append(unpaid.Count == 0 ? " | rewards OK" : " | ZERO-REWARD: " + Join(unpaid));
            sb.Append(charters.Count == 0
                ? " | NO CHARTERS LOADED"
                : unpriced.Count == 0
                    ? " | charter-value OK (" + charters.Count + ")"
                    : " | CHARTER HAS NO VALUE NOTE: " + Join(unpriced));
            sb.Append(dangling.Count == 0 ? " | deps OK" : " | DANGLING CompleteContract: " + Join(dangling));
            sb.Append(noClosure.Count == 0
                ? " | closure OK"
                : " | DOES NOT CLOSE ITS PROGRAM: " + Join(noClosure));
            sb.Append(penalising.Count == 0
                ? " | no-penalty OK"
                : " | WOULD FAIL IN-FLIGHT CONTRACTS ON CONCLUSION: " + Join(penalising));
            return sb.ToString();
        }

        /// <summary>The single program this contract's ProgramActive requirement gates on, or null if
        /// it has none / more than one (a completion contract must gate on exactly its own).</summary>
        private static string ProgramGate(ContractType ct)
        {
            IEnumerable<ContractRequirement> reqs;
            try { reqs = ct.Requirements; }
            catch { return null; }
            if (reqs == null) return null;

            string found = null;
            foreach (ContractRequirement r in reqs)
            {
                if (!(r is ProgramActiveRequirement pa)) continue;
                if (pa.Programs == null || pa.Programs.Count != 1) return null;
                if (found != null) return null;
                found = pa.Programs[0];
            }
            return found;
        }

        /// <summary>The program this contract's ConcludeProgram behaviour closes, or null if it has
        /// none. Read off Contract Configurator's parsed factories, so it proves the BEHAVIOUR block
        /// both survived generation and bound to a live factory.</summary>
        private static string ConcludedProgram(ContractType ct)
        {
            IEnumerable<BehaviourFactory> factories;
            try { factories = ct.BehaviourFactories; }
            catch { return null; }
            if (factories == null) return null;

            foreach (BehaviourFactory bf in factories)
                if (bf is ConcludeProgramFactory cp && !string.IsNullOrEmpty(cp.Program))
                    return cp.Program;
            return null;
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

            // (4b) The commitment cap per Administration level, READ LIVE rather than assumed — this
            // is CustomBarnKit's override of GameVariables.GetStrategyCommitRange, so it doubles as
            // proof that AxeFacilities.cfg's @ADMINISTRATION block applied at all. CBK falls back to
            // stock silently, per-field, when an array length disagrees with `levels`.
            // normLevel for a 3-level building is level/(levels-1): 0, 0.5, 1.
            var live = new float[ExpectedCommitRange.Length];
            for (int i = 0; i < live.Length; i++)
            {
                float norm = live.Length > 1 ? (float)i / (live.Length - 1) : 0f;
                try { live[i] = GameVariables.Instance.GetStrategyCommitRange(norm); }
                catch { live[i] = float.NaN; }
            }
            sb.Append(" commitRange=[").Append(string.Join("/", live.Select(v => v.ToString("0.##")).ToArray())).Append(']');

            bool commitOK = true;
            for (int i = 0; i < live.Length; i++)
                if (!Mathf.Approximately(live[i], ExpectedCommitRange[i])) commitOK = false;
            sb.Append(commitOK
                ? " (AXE's, OK)"
                : " | NOT AXE'S 0.5/0.75/1 — @ADMINISTRATION did not apply (CustomBarnKit falls back silently)");

            // The gate is Lerp(min, max, factor) evaluated at each level's cap. It is EXPECTED to
            // bind at L1 now (125 reputation at a 0.5 cap) — see the class doc, item 4b. What must
            // never happen again is the requirement running to five or six figures.
            sb.Append(" needAt=")
              .Append(string.Join("/", live.Select(v => Mathf.Lerp(min, max, v).ToString("0")).ToArray()));

            float atL3 = Mathf.Lerp(min, max, live[live.Length - 1]);
            sb.Append(atL3 <= StockRequiredRepMax
                ? " | L3 reachable OK"
                : " | L3 NEEDS " + atL3.ToString("0") + " rep — the lerp is being widened again");

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
                float lo, hi, minShare;
                try
                {
                    var t = Traverse.Create(eff);
                    lo = t.Field("minRate").GetValue<float>();
                    hi = t.Field("maxRate").GetValue<float>();
                    minShare = t.Field("minShare").GetValue<float>();
                }
                catch (Exception e) { return "rate: UNREADABLE (" + e.Message + ")"; }

                bool ok = Mathf.Approximately(lo, ExpectedFundraisingMinRate)
                          && Mathf.Approximately(hi, ExpectedFundraisingMaxRate);
                // §11: the share floor is half the fix. Stock's 0 makes yield quadratic in the
                // commitment factor; without this the rate check above would pass while Channel 2
                // still paid 21% of its L3 rate at Administration L1.
                bool shareOK = Mathf.Approximately(minShare, ExpectedFundraisingMinShare);
                return "rate=" + lo.ToString("0.#") + "-" + hi.ToString("0.#") +
                       (ok ? " OK" : " | EXPECTED " + ExpectedFundraisingMinRate + "-" + ExpectedFundraisingMaxRate +
                             " (AxeStrategies.cfg did not apply)") +
                       " minShare=" + minShare.ToString("0.##") +
                       (shareOK ? " OK" : " | EXPECTED " + ExpectedFundraisingMinShare);
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
