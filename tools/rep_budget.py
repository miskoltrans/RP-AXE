#!/usr/bin/env python3
"""Measure a career's total REPUTATION — the denominator of the funds economy's Channel 2.

Channel 2 (docs/ECONOMY.md §3) converts reputation into funds through the Administration
building's FundraisingCampaign strategy, so "how much funds does Channel 2 pay over a career" is
entirely a question of how much reputation the player earns. That number was asserted (~114k) when
the economy was authored and later contradicted by a hand sum (65,595); this tool derives it from
the merged ModuleManager.ConfigCache, which is what actually loads.

WHAT THE CONFIG VALUE IS NOT
`rewardReputation` in a CONTRACT_TYPE is not what the player receives. Contract Configurator hands
it to stock's own setter (`ConfiguredContract.Initialize` -> `Contract.SetReputation`), which does:

    ReputationCompletion = Round(rewardReputation
                                 * GetContractPrestigeFactor(prestige)   // 1.0 / 1.25 / 1.5
                                 * contractReputationCompletionFactor    // 1 (CBK MISSION section)
                                 * Career.RepGainMultiplier              // preset: 1.6/1.2/1/0.8
                                 * GetDestinationWeight(targetBody))     // see below

so a raw sum of the config field understates the career by the prestige mix times the difficulty
multiplier — **38.5% at AXE's own Normal preset** (prestige mix x1.155, RepGainMultiplier x1.2).

`prestige` in a CONTRACT_TYPE is a Contract Configurator FILTER, not an assignment
(`ContractType.MeetRequirements` throws "Wrong prestige level" when the generated contract's
prestige is not in the list) — but every paying AXE contract declares exactly one level, so a type
can only ever be generated at that level and the factor above is fully determined. If a future
contract omits `prestige`, it can roll any level and this tool's Trivial default understates it.

The destination weight (`body.scienceValues.RecoveryValue`) does NOT apply here: Contract
Configurator only passes a target body when the contract's group sets `useTargetBodyForReward`, and
`seed/Contracts/Groups.cfg` sets it **false** on the root RP0 group with no child override. That is
inherited from RP-1 and is load-bearing — flipping it would multiply every deep-space contract's
reputation by that body's recovery value.

WHAT FEEDS THE CHANNEL — AND WHAT DOES NOT
`FundraisingCampaign`'s CurrencyConverter only fires for the transaction reasons it lists:
`AffectReasons = ContractReward, ScienceTransmission, Progression`. Reputation from **crew recovery**
(stock pays `reputationKerbalRecovery` 25 x RepGainMultiplier **per kerbal**, every time a crewed
vessel is recovered) carries `TransactionReasons.VesselRecovery`, which is NOT in that list — so it
accrues as a reputation BALANCE but is never converted to funds. That is what keeps the strategy's
own `requiredReputation` gate (750 held reputation at Administration L3) reachable even at 100%
commitment, where every converted point is deducted from the gain. It also means crewed flight
spam cannot be farmed for money through this channel.

REPUTATION IS ONLY LINEAR BECAUSE WE MAKE IT SO
Everything above adds reputation as if a contract paying N adds N. Stock does not
(`Reputation.addReputation_granular` damps gains and amplifies losses through a curve indexed on
rep/RepRange), which cost save default3 619 reputation on one capstone — docs/ECONOMY.md §15.
`Source/AXE/SpaceCenter/AxeReputationScale.cs` flattens both curves so the assumption holds;
`granular_check()` below is the offline regression detector for that patch.

Usage:
    python tools/rep_budget.py [--cache PATH] [--preset Easy|Normal|Moderate|Hard]
    python tools/rep_budget.py --by-group          # per-programme breakdown
    python tools/rep_budget.py --strict            # exit 1 on any net-negative contract (gate)
"""
import argparse
import os
import sys
from collections import defaultdict

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Instance", "GameData", "ModuleManager.ConfigCache",
)

# GameVariables defaults, confirmed live in the cache's CustomBarnKit MISSION section.
PRESTIGE_FACTOR = {"Trivial": 1.0, "Significant": 1.25, "Exceptional": 1.5}
REP_COMPLETION_FACTOR = 1.0

# AxeGameParameters.cfg, CAREER block of each preset.
REP_GAIN_MULTIPLIER = {"Easy": 1.6, "Normal": 1.2, "Moderate": 1.0, "Hard": 0.8}

# AxeStrategies.cfg — FundraisingCampaign after AXE's rescale.
RATE_MIN, RATE_MAX = 125.0, 157.0
# AxeStrategies.cfg minShare (docs/ECONOMY.md §11). The share of incoming reputation diverted is
# Lerp(SHARE_MIN, 1.0, f), NOT f itself — this file modelled `share = f` until 2026-08-27, which
# understated every sub-L3 row (and, worse, understated the take that the break-even check below
# tests against).
SHARE_MIN = 0.55
# Administration levels 1/2/3. AXE's own strategyCommitRange, not CustomBarnKit's stock 0.25/0.6/1
# (AxeFacilities.cfg @ADMINISTRATION, §11) — confirmed live in the cache's CBK dump. The commitment
# slider drives BOTH the share diverted and the rate, so the yield is quadratic in f.
COMMIT_RANGE = [0.5, 0.75, 1.0]

CHANNEL2_TARGET = 16_000_000

# Reputation.RepRange (Assembly-CSharp). Stock's reputation band is +/-1000 and every damping curve
# is indexed on rep/RepRange. See granular_check() for why this number bounds a contract's payout.
REP_RANGE = 1000.0


def share_at(f):
    """Fraction of an incoming reputation award that FundraisingCampaign diverts at commitment f."""
    return SHARE_MIN + (1.0 - SHARE_MIN) * f


def rate_at(f):
    """Funds paid per diverted reputation point at commitment f."""
    return RATE_MIN + (RATE_MAX - RATE_MIN) * f


def parse_cache(path):
    """Yield (contract_type_node, source_url) for every CONTRACT_TYPE in the merged cache."""
    stack, pending, out = [], None, []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            if line == "{":
                node = {"_type": pending, "_f": defaultdict(list), "_kids": []}
                if stack:
                    stack[-1]["_kids"].append(node)
                stack.append(node)
                pending = None
            elif line == "}":
                if stack:
                    done = stack.pop()
                    if done["_type"] == "UrlConfig":
                        src = (done["_f"].get("parentUrl") or ["?"])[0]
                        for kid in done["_kids"]:
                            if kid["_type"] == "CONTRACT_TYPE":
                                out.append((kid, src))
            elif "=" in line and not line.endswith("{"):
                k, _, v = line.partition("=")
                if stack:
                    stack[-1]["_f"][k.strip()].append(v.strip())
            else:
                pending = line
    return out


def walk(node):
    yield node
    for k in node["_kids"]:
        yield from walk(k)


def field(node, key, default=None):
    v = node["_f"].get(key)
    return v[0] if v else default


def fnum(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def collect(cache_path, preset):
    mult = REP_GAIN_MULTIPLIER[preset]
    rows = []
    for ct, src in parse_cache(cache_path):
        own = fnum(field(ct, "rewardReputation"))
        # Reputation attached to PARAMETERs is awarded the same way, on the same contract — but as
        # its OWN AddReputation call when that parameter completes, not folded into the contract's.
        # The career total wants the sum; granular_check wants the largest SINGLE call, because the
        # damping is a property of one award's size (log: the same contract paid 180 per optional
        # parameter and 1350 on completion, five separate awards).
        params = [
            fnum(v)
            for kid in ct["_kids"]
            for n in walk(kid)
            for v in n["_f"].get("rewardReputation", [])
        ]
        raw = own + sum(params)
        if raw <= 0:
            continue
        prestige = field(ct, "prestige", "Trivial")
        factor = PRESTIGE_FACTOR.get(prestige, 1.0)
        scale = factor * REP_COMPLETION_FACTOR * mult
        rows.append(dict(
            name=field(ct, "name", "?"),
            group=field(ct, "group", "(none)"),
            src=src,
            raw=raw,
            prestige=prestige,
            maxc=field(ct, "maxCompletions", "1"),
            paid=round(raw * scale),
            single=round(max([own] + params) * scale),
        ))
    return rows


def granular_check(rows, commit):
    """Contracts whose single reputation payout is large enough to net NEGATIVE reputation.

    Stock does not add a reputation award linearly. `Reputation.addReputation_granular` walks the
    payout ONE POINT AT A TIME, scaling each point by
    `GameVariables.reputationAddition.Evaluate(rep / RepRange)` — a curve that falls to zero at
    t = 1. Two consequences, and only the first is obvious:

      * a payout banks less than its face value, and the shortfall GROWS with payout size, because a
        big award climbs its own damping curve;
      * the balance can therefore never be carried above RepRange by an award, however large it is.

    Meanwhile `CurrencyConverter.OnEffectQuery` reads `qry.GetInput(Reputation)` — the RAW award, not
    the banked amount — and diverts a flat `share` of it. So for one contract:

        banked <= RepRange - rep_before        (the curve cannot push past the band)
        taken   = share * paid                 (flat, undamped)

    which makes the failure condition exact rather than fitted, with no need to know the curve:

        taken >= RepRange            ->  net <= -rep_before.  Negative from ANY non-negative start.
        taken >= RepRange / 2        ->  negative from any start above RepRange / 2.

    MEASURED (save default3, KSP.log 2026-08-27 14:10:34, commit 0.5): "Second Generation Space
    Station" paid 1350, share 0.775 -> taken 1046.25 >= 1000. Banked 403, charged 1046, net -619.
    Reputation went 376.59 -> -170.67 and the UI reported the contract as a gain of 304.

    AxeReputationScale (Source/AXE/SpaceCenter) flattens both curves to 1.0, which removes the whole
    effect — banked == paid, net == paid * (1 - share) >= 0 always. This check therefore stays as a
    REGRESSION DETECTOR: it reports what would break if that patch ever stops applying, and it is the
    only offline view of it, since the curves live in a Unity asset and not in any config.
    """
    share = share_at(commit)
    out = []
    for r in rows:
        taken = r["single"] * share
        if taken >= REP_RANGE:
            sev = "FAIL"
        elif taken >= REP_RANGE / 2.0:
            sev = "WARN"
        else:
            continue
        out.append(dict(sev=sev, taken=taken, **r))
    out.sort(key=lambda r: -r["taken"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--preset", default="Normal", choices=sorted(REP_GAIN_MULTIPLIER))
    ap.add_argument("--by-group", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any contract would net negative reputation (build gate)")
    args = ap.parse_args()

    if not os.path.exists(args.cache):
        sys.exit(f"cache not found: {args.cache}\n(build it by launching the instance once)")

    rows = collect(args.cache, args.preset)
    mult = REP_GAIN_MULTIPLIER[args.preset]

    once = [r for r in rows if r["maxc"] != "0"]
    unlimited = [r for r in rows if r["maxc"] == "0"]

    raw_total = sum(r["raw"] for r in rows)
    paid_once = sum(r["paid"] for r in once)
    paid_unl = sum(r["paid"] for r in unlimited)

    print(f"cache : {args.cache}")
    print(f"preset: {args.preset}  (RepGainMultiplier = {mult})\n")

    print(f"contract types paying reputation : {len(rows)}")
    print(f"  raw config sum                 : {raw_total:10,.0f}")
    print(f"  as PAID, one completion each   : {paid_once + paid_unl:10,.0f}"
          f"   (x{(paid_once + paid_unl) / raw_total:.3f} over raw)")
    print(f"    bounded contracts            : {paid_once:10,.0f}  ({len(once)} types)")
    print(f"    unlimited-repeat, first pass : {paid_unl:10,.0f}  ({len(unlimited)} types,"
          f" repeatable without limit)")

    mix = defaultdict(lambda: [0, 0.0])
    for r in rows:
        b = mix[r["prestige"]]
        b[0] += 1
        b[1] += r["raw"]
    print("\nprestige mix (raw reputation):")
    for k in ("Trivial", "Significant", "Exceptional"):
        if k in mix:
            n, v = mix[k]
            print(f"  {k:12s} x{PRESTIGE_FACTOR[k]:<5}: {n:3d} types, {v:8,.0f} raw")

    career = paid_once + paid_unl
    print("\n--- Channel 2: reputation -> funds (FundraisingCampaign 125-157) ---")
    print(f"{'Administration level':24s} {'share':>7s} {'rate':>7s} {'funds':>12s}")
    for i, cap in enumerate(COMMIT_RANGE, start=1):
        share, rate = share_at(cap), rate_at(cap)
        print(f"  L{i} (commit cap {cap:.2f}){'':4s} {share:7.3f} {rate:7.0f} "
              f"{career * share * rate:12,.0f}")
    best = career * share_at(COMMIT_RANGE[-1]) * rate_at(COMMIT_RANGE[-1])
    print(f"\nceiling (Admin L3, full commitment, every contract once): {best:,.0f}")
    print(f"Channel 2 target                                        : {CHANNEL2_TARGET:,.0f}")
    print(f"ratio                                                   : {best / CHANNEL2_TARGET:.2f}x")

    if args.by_group:
        print("\n--- by contract group (as paid, one completion each) ---")
        g, gn = defaultdict(float), defaultdict(int)
        for r in rows:
            g[r["group"]] += r["paid"]
            gn[r["group"]] += 1
        for k in sorted(g, key=lambda x: -g[x]):
            print(f"  {g[k]:9,.0f}  ({gn[k]:3d})  {k}")

    print("\n--- granular break-even: contracts that would net NEGATIVE reputation ---")
    print(f"(stock Reputation.RepRange = {REP_RANGE:,.0f}; a payout cannot bank more than the band,")
    print(" but Fundraising diverts a flat share of the RAW award — see granular_check.__doc__)")
    worst = 0
    for i, cap in enumerate(COMMIT_RANGE, start=1):
        hits = granular_check(rows, cap)
        fails = [h for h in hits if h["sev"] == "FAIL"]
        warns = [h for h in hits if h["sev"] == "WARN"]
        worst = max(worst, len(fails))
        print(f"\n  Admin L{i}, commit cap {cap:.2f}, share {share_at(cap):.3f}"
              f"  ->  {len(fails)} FAIL, {len(warns)} WARN")
        for h in hits[:12]:
            print(f"    {h['sev']}  award {h['single']:6,.0f}  taken {h['taken']:7,.0f}  {h['name']}")
        if len(hits) > 12:
            print(f"    ... and {len(hits) - 12} more (not shown)")

    if worst:
        print(f"\n  FAIL means net-negative reputation from any starting balance. Requires")
        print( "  AxeReputationScale to be live; see docs/ECONOMY.md §15.")
    else:
        print("\n  no contract payout reaches the band — safe even without AxeReputationScale.")

    if args.strict and worst:
        sys.exit(1)


if __name__ == "__main__":
    main()
