using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RP-AXE funds economy — DECISION: "generous" bite (locked; not for further tuning).
    /// Parts unlock free with science (see <see cref="FreePartUnlock"/>); RealFuels engine-config
    /// development is the one engineering buy-to-unlock; LAUNCH COST is the only ongoing funds sink.
    /// Money should reward exploration / milestones and good engineering (recover-and-reuse), never wall.
    ///
    /// The locked levers (most already in place; documented here as the record):
    ///   - Starting funds 100,000           -> this scenario (stock Normal default is 25k; CustomBarnKit
    ///                                          has no startingFunds field, so we grant it in code).
    ///   - Recovery 90% parts / 95% propellant -> CustomBarnKit default (kept; rewards recoverable design).
    ///   - Contract income x1.25            -> design/Rewards/{FundsTrim,ProgramRewards}.cfg (kept).
    ///   - Building upgrades modest         -> CustomBarnKit defaults, left as-is (not a second grind-wall).
    /// Open (not a config fix): mid/late solvency vs procedural-priced big vehicles = a play-session /
    /// per-era funds-audit question.
    ///
    /// A ScenarioModule (auto-added to career games) is the robust trigger: it persists a one-time
    /// `granted` flag, so a brand-new career is topped up to 100k exactly once and existing careers are
    /// left alone. (An onGameNewStart hook raced with the AutoTest's game creation and missed.)
    /// </summary>
    [KSPScenario(ScenarioCreationOptions.AddToNewCareerGames | ScenarioCreationOptions.AddToExistingCareerGames,
                 GameScenes.SPACECENTER)]
    public class GenerousStart : ScenarioModule
    {
        private const double StartingFunds = 100000;

        [KSPField(isPersistant = true)] public bool granted;

        private void Start()
        {
            if (granted || HighLogic.CurrentGame == null || HighLogic.CurrentGame.Mode != Game.Modes.CAREER)
                return;
            if (Funding.Instance == null) return;

            double have = Funding.Instance.Funds;
            granted = true;
            if (have < StartingFunds)
            {
                Funding.Instance.AddFunds(StartingFunds - have, TransactionReasons.None);
                Debug.Log($"[AXE] GenerousStart: new career funds topped up {have:N0} -> {StartingFunds:N0}.");
            }
        }
    }
}
