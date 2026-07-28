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

Usage:
    python tools/rep_budget.py [--cache PATH] [--preset Easy|Normal|Moderate|Hard]
    python tools/rep_budget.py --by-group          # per-programme breakdown
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
# Administration levels 1/2/3 (stock strategyCommitRange). The commitment slider drives BOTH the
# share of reputation diverted and the rate, so funds = rep * share * Lerp(RATE_MIN, RATE_MAX).
COMMIT_RANGE = [0.25, 0.6, 1.0]

CHANNEL2_TARGET = 16_000_000


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
        raw = fnum(field(ct, "rewardReputation"))
        # reputation attached to PARAMETERs is awarded the same way, on the same contract
        raw += sum(
            fnum(v)
            for kid in ct["_kids"]
            for n in walk(kid)
            for v in n["_f"].get("rewardReputation", [])
        )
        if raw <= 0:
            continue
        prestige = field(ct, "prestige", "Trivial")
        factor = PRESTIGE_FACTOR.get(prestige, 1.0)
        rows.append(dict(
            name=field(ct, "name", "?"),
            group=field(ct, "group", "(none)"),
            src=src,
            raw=raw,
            prestige=prestige,
            maxc=field(ct, "maxCompletions", "1"),
            paid=round(raw * factor * REP_COMPLETION_FACTOR * mult),
        ))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--preset", default="Normal", choices=sorted(REP_GAIN_MULTIPLIER))
    ap.add_argument("--by-group", action="store_true")
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
    for i, share in enumerate(COMMIT_RANGE, start=1):
        rate = RATE_MIN + (RATE_MAX - RATE_MIN) * share
        print(f"  L{i} (commit cap {share:.2f}){'':4s} {share:7.2f} {rate:7.0f} "
              f"{career * share * rate:12,.0f}")
    best = career * COMMIT_RANGE[-1] * RATE_MAX
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


if __name__ == "__main__":
    main()
