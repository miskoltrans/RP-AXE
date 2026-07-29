using System;
using HarmonyLib;
using Strategies;
using Strategies.Effects;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// One-time discovery nudge for the Fundraising Campaign — Channel 2 of the funds economy
    /// (docs/ECONOMY.md §3, §11). AXE's contracts pay REPUTATION, and reputation becomes money only
    /// through the Administration building. Nothing in the stock game says so, and the conversion is
    /// FLOW-ONLY, so a player who banks reputation before activating loses that conversion for good.
    ///
    /// WHY THIS IS NOT COSMETIC. tools/gate_feasibility.py: at the first-orbit gate Channel 1 alone
    /// banks 572,852 against 590,000 of gates — BLOCKED by 17,148. Channel 2 contributes 56,386,
    /// which is the whole margin. The tree's early pacing is balanced on Fundraising being active,
    /// so a player who never opens Administration is hard-blocked at first orbit with no diagnosis
    /// available in game. That is exactly the state the 2026-07 playtest save reached: 596
    /// reputation across 38 completed contracts, Administration never opened, −348 funds.
    ///
    /// WHY NOT BACK-PAY THE BANKED BALANCE INSTEAD. Retroactive conversion looks like the kinder
    /// fix and is the wrong one: the rate rises with Administration level (and with the commitment
    /// slider), so paying out a hoard on activation would reward delaying activation — a worse
    /// incentive than the one being fixed. Flow-only is correct game design; only the silence is the
    /// bug, so the fix is to say it, once, early enough to act on.
    ///
    /// Decompiled facts this text relies on (Assembly-CSharp, 2026-07-29):
    ///   * CurrencyConverter.OnEffectQuery reads qry.GetInput(input) and is registered only between
    ///     OnRegister/OnUnregister — hence flow-only, and only while the strategy is active.
    ///   * Strategy.LeastDuration and Strategy.LongestDuration BOTH lerp the minLeastDuration/
    ///     maxLeastDuration *fields*, which no code ever assigns for a config-defined strategy
    ///     (GetStrategyType("FundraisingCampaignCfg") finds no class, so the base Strategy is used).
    ///     Both therefore evaluate to 0, which means (a) the strategy never auto-expires and (b)
    ///     CanBeDeactivated's `dateActivated + LeastDuration &lt; now` is satisfied immediately.
    ///     So "start small, raise it later" is genuinely available. NB this is exactly the stock bug
    ///     KSPCommunityFixes' StrategyDuration patch repairs — AxeCommunityFixes.cfg deliberately does
    ///     NOT take it, because repairing it would put a 1200–1600 day expiry clock on Channel 2.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.SpaceCentre, false)]
    public class AxeFundraisingTip : MonoBehaviour
    {
        private const string TipKey = "fundraisingUnconverted";

        /// <summary>
        /// Reputation at which the nudge fires. Activating costs reputation —
        /// initialCostReputationMin/Max = 4/70 lerped over the commitment slider, so ~7 at the stock
        /// 0.05 default — and the requiredReputation lerp is far negative down there, so ~10 is the
        /// point where the advice becomes actionable rather than premature. The reputation forgone
        /// before this fires is worth about a thousand funds, i.e. nothing against the 56,386 the
        /// channel is carrying pre-orbit.
        /// </summary>
        private const float RepThreshold = 10f;

        private bool _evaluated;

        private void Update()
        {
            if (_evaluated) return;

            // Career is the only mode with a Channel 2, and the mode is known immediately and never
            // changes — so this is the one condition it is safe to latch on.
            if (HighLogic.CurrentGame == null) return;
            if (HighLogic.CurrentGame.Mode != Game.Modes.CAREER) { _evaluated = true; return; }

            AxeTipState state = AxeTipState.Instance;
            if (state == null) return;   // scenario module not spun up yet; retry next frame

            // Everything below is LOAD-ORDER SENSITIVE, so nothing here latches: this addon is
            // respawned on every return to the Space Center, and a not-yet condition must stay
            // retryable rather than being mistaken for a settled answer.
            if (Reputation.Instance == null) return;
            if (Reputation.CurrentRep < RepThreshold) return;
            if (!StrategiesLoaded()) return;

            _evaluated = true;

            if (state.WasShown(TipKey)) return;
            if (ConversionIsLive()) return;

            state.MarkShown(TipKey);
            ShowTip();
        }

        /// <summary>
        /// Whether the strategy system has finished populating, as distinct from having no active
        /// strategies.
        ///
        /// THIS DISTINCTION IS THE WHOLE POINT. `StrategySystem.OnLoad` does
        /// `StartCoroutine(OnLoadRoutine(node))`, and that routine opens with `yield return null` —
        /// so for at least one frame `StrategySystem.Instance` exists, `Strategies` is a non-null
        /// **empty** list, and every "is anything converting?" question answers "no". The first
        /// version of this file guarded only against null and latched its verdict immediately, so it
        /// fired the nudge at a career that had been running Fundraising for years (caught in the
        /// `default3` playtest, 2026-07-30). Empty means NOT LOADED YET.
        ///
        /// `LoadStrategies` fills the list in one synchronous pass over every *defined* strategy —
        /// active or not — so the count is either 0 (has not run) or complete. `> 0` is therefore a
        /// sound readiness signal, and if an install genuinely defines no strategies at all there is
        /// no Channel 2 to advertise and staying silent forever is the right outcome.
        /// </summary>
        private static bool StrategiesLoaded()
        {
            StrategySystem sys = StrategySystem.Instance;
            return sys != null && sys.Strategies != null && sys.Strategies.Count > 0;
        }

        /// <summary>
        /// True if some ACTIVE strategy already converts reputation into funds. Assumes the caller has
        /// established readiness via <see cref="StrategiesLoaded"/> — this method cannot tell an empty
        /// strategy list from an unloaded one, and must never be asked to.
        ///
        /// Detected STRUCTURALLY — by the effect's own input/output currencies — not by matching
        /// "FundraisingCampaignCfg" by name, which would be the silent-string-binding failure
        /// docs/BUG-CLASSES.md family 1 warns about: a renamed or replaced strategy would leave this
        /// check passing while the player earned nothing. input/output are private on
        /// CurrencyConverter, so they are read with Traverse, the same way AxeEconomySelfTest reads
        /// minRate/maxRate off this very class.
        ///
        /// (The alternative — firing a probe CurrencyModifierQuery and looking for a funds delta —
        /// would test the behaviour rather than the shape, but it dispatches a GameEvent that any
        /// third-party listener also sees. Not worth the blast radius for a tip.)
        /// </summary>
        private static bool ConversionIsLive()
        {
            StrategySystem sys = StrategySystem.Instance;
            if (sys == null || sys.Strategies == null) return true;   // can't tell — never cry wolf

            try
            {
                foreach (Strategy s in sys.Strategies)
                {
                    if (s == null || !s.IsActive || s.Effects == null) continue;

                    foreach (StrategyEffect eff in s.Effects)
                    {
                        if (!(eff is CurrencyConverter)) continue;

                        Traverse t = Traverse.Create(eff);
                        if (t.Field("input").GetValue<Currency>() == Currency.Reputation &&
                            t.Field("output").GetValue<Currency>() == Currency.Funds)
                            return true;
                    }
                }
            }
            catch (Exception e)
            {
                // Unreadable means unknown, and an unknown must not produce a false alarm telling a
                // player to switch on something they already run. Loud in the log, silent in game.
                Debug.LogWarning("[AXE] Fundraising tip could not inspect the strategy system: " + e);
                return true;
            }

            return false;
        }

        private static void ShowTip()
        {
            PopupDialog.SpawnPopupDialog(new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                "AxeFundraisingTip", "Turning reputation into funds",
                "Most of what your contracts pay is reputation, and reputation only becomes money " +
                "through the Fundraising Campaign in the Administration building.\n\n" +
                "It converts reputation as it arrives — whatever you have already banked stays " +
                "reputation for good. Activating early therefore matters far more than waiting for a " +
                "good rate.\n\n" +
                "Start at whatever commitment your reputation allows. You can end the campaign and " +
                "start it again at a higher one later, as your reputation grows and the " +
                "Administration building is upgraded.",
                "OK", false, HighLogic.UISkin);
        }
    }
}
