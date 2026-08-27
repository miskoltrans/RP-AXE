using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Makes reputation arithmetic LINEAR. AXE's economy has always assumed it is; stock has never
    /// provided it, and the gap silently ate a career's reputation (docs/ECONOMY.md §15).
    ///
    /// WHAT STOCK ACTUALLY DOES. <c>Reputation.AddReputation(r, reason)</c> does not add <c>r</c>:
    ///     float num = addReputation_granular(r);                       // balance moves HERE, on RAW r
    ///     var q = new CurrencyModifierQuery(reason, 0f, 0f, r);        // strategies see RAW r too
    ///     GameEvents.Modifiers.OnCurrencyModifierQuery.Fire(q);        // CurrencyConverter adds deltas
    ///     GameEvents.Modifiers.OnCurrencyModified.Fire(q);             // Funding/Reputation apply them
    /// and <c>addReputation_granular</c> walks the payout ONE POINT AT A TIME, re-evaluating
    /// <c>GameVariables.reputationAddition.Evaluate(rep / RepRange)</c> after every single point. A
    /// large award therefore climbs its own damping curve and banks only a fraction of itself, while
    /// <c>CurrencyConverter.OnEffectQuery</c> reads <c>qry.GetInput(input)</c> — the RAW value — and
    /// takes a flat share of that. The two disagree, and the disagreement grows with payout size.
    ///
    /// MEASURED, save default3, 2026-08-27 14:10:34 (KSP.log), FundraisingCampaign at commit 0.5:
    ///     Awarding 1350 reputation to player for contract completion
    ///     [CurrencyConverter for Fundraising Campaign]: 1046.25 Reputation taken, yields 147521.3 Funds
    ///     Added 403.0052 (1350) reputation: 'ContractReward'.
    /// Banked 403, charged 1046: the Second Generation Space Station capstone COST 619 reputation and
    /// the UI reported it as a gain of 304. Reputation went 376.59 -> -170.67, reconciled to the
    /// decimal against the save. This is not an edge case — stock's band is +/-1000 and AXE routinely
    /// pays four-figure reputation, because reputation IS our contract currency.
    ///
    /// THE FIX. Replace the two damping curves with constant 1.0, so <c>ModifyReputationDelta</c> is
    /// the identity and <c>addReputation_granular(v) == v</c>. Reputation then behaves the way
    /// docs/ECONOMY.md §3 and tools/rep_budget.py have always modelled it: linear, so a contract nets
    /// exactly <c>reward x (1 - share)</c> and can never net negative.
    ///
    /// WHY NOT RAISE <c>Reputation.RepRange</c> (the obvious one-liner). It is read in four places,
    /// and one of them is load-bearing: <c>ContractSystem</c> calls
    /// <c>GetContractCounts(Reputation.UnitRep, ...)</c>, where <c>UnitRep = rep / RepRange</c>,
    /// to decide how many Trivial/Significant/Exceptional contracts are offered. Widening the band
    /// pins UnitRep near zero, the game concludes we are unknown, and it stops rolling the higher
    /// prestige tiers — which Contract Configurator filters AXE's contracts on, so most of the tree's
    /// contracts would simply never appear. Flattening the curves touches only
    /// <c>ModifyReputationDelta</c> and leaves RepRange, UnitRep and the +/-1000 clamp alone.
    ///
    /// KNOWN CONSEQUENCE, ACCEPTED. With no damping the balance can climb past RepRange. Nothing
    /// clamps it (<c>OnLoad</c> assigns <c>rep</c> directly and <c>SetReputation</c>'s clamp is only
    /// reachable from the debug console), and the two consumers degrade safely: <c>GetContractCounts</c>
    /// runs its input through <c>Mathf.InverseLerp</c>, which saturates at "maximum fame", and
    /// <c>ReputationWidget</c>'s gauge pins full — the same state rep 1000 already produced. In
    /// practice the balance stays low anyway: Fundraising diverts 55-100% of every contract award, so
    /// only the uncommitted slice and crew recovery accrue.
    ///
    /// RE-ASSERTED EVERY SCENE, deliberately. GameVariables is a ScriptableObject that CustomBarnKit
    /// also writes; a correction applied once is a correction that stops existing the moment anything
    /// replaces the instance. Awake checks by reference and re-applies if needed, then self-destructs.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EveryScene, false)]
    public class AxeReputationScale : MonoBehaviour
    {
        // Separate instances: sharing one curve object between the two fields would let anything that
        // mutates one silently mutate the other.
        private static AnimationCurve _flatAdd;
        private static AnimationCurve _flatSub;

        private void Awake()
        {
            Apply();
            Destroy(gameObject);
        }

        /// <summary>True once the curves are ours. False means GameVariables was not up yet — the
        /// next scene retries, so this must never latch (see docs/BUG-CLASSES.md, "lazily-loaded
        /// means EMPTY, not absent").</summary>
        internal static bool Apply()
        {
            GameVariables gv = GameVariables.Instance;
            if (gv == null) return false;

            if (IsLinear(gv)) return true;

            // Sampled off the OLD curves so the log records what we displaced. 0.377 is where save
            // default3 sat when the 1350-point award landed; add ~0.79 / sub ~1.03 there is the
            // asymmetry that made a contract net negative.
            string was = Describe(gv.reputationAddition) + "/" + Describe(gv.reputationSubtraction);

            if (_flatAdd == null) _flatAdd = AnimationCurve.Constant(-1f, 1f, 1f);
            if (_flatSub == null) _flatSub = AnimationCurve.Constant(-1f, 1f, 1f);
            gv.reputationAddition = _flatAdd;
            gv.reputationSubtraction = _flatSub;

            Debug.Log("[AXE][rep] reputation curves flattened to 1.0 — gains/losses are now linear. "
                      + "Displaced add/sub at t=0.377: " + was);
            return true;
        }

        /// <summary>Reference check, not a value check: another mod replacing the curve with its own
        /// flat one still needs re-asserting, because it may not stay flat.</summary>
        private static bool IsLinear(GameVariables gv)
        {
            return _flatAdd != null && _flatSub != null
                && ReferenceEquals(gv.reputationAddition, _flatAdd)
                && ReferenceEquals(gv.reputationSubtraction, _flatSub);
        }

        private static string Describe(AnimationCurve c)
        {
            return c == null ? "null" : c.Evaluate(0.377f).ToString("0.###");
        }
    }
}
