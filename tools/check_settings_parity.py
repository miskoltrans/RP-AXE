#!/usr/bin/env python3
"""
check_settings_parity.py -- which global settings did RP-1 own that RP-AXE never re-authored?

The one bug family in docs/BUG-CLASSES.md with no other detector (A5). RP-1 was the SOLE source
of a large number of singleton settings keys -- CustomBarnKit facility ladders, difficulty
defaults, physics globals, RealFuels settings. RO supplies none of them. So deleting RP-1 did not
leave those settings unset; it silently restored the STOCK value that RP-1 existed to override,
and a stock value nobody chose looks exactly like a designed one. That is how AXE shipped with the
stock building-upgrade grind, a 30-part VAB cap, autostrut that never unlocked, and 27 stock
contract types leaking into Mission Control.

Per-object rows (PART, PARTUPGRADE, CONTRACT_TYPE, ...) are out of scope -- AXE re-authors those
by design and the diff would be the whole mod. This looks only at SETTINGS nodes: the singletons
where one missing key changes the whole career.

Every divergence must carry a disposition below. That is the point: a KNOWN cut stays quiet, and
anything new -- an RP-1 update, a section nobody noticed -- shows up as UNDISPOSITIONED and fails.

  python tools/check_settings_parity.py
  python tools/check_settings_parity.py --rp1 <path to RP-1/GameData/RP-1>
  python tools/check_settings_parity.py --show-cut     # also list what we deliberately dropped
"""
import argparse, os, re, sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AXE = os.path.join(REPO, "GameData", "RP-AXE")
DEFAULT_RP1 = os.path.join(os.path.dirname(REPO), "RP-1", "GameData", "RP-1")

# Settings nodes: singletons whose keys are global career levers. Anything not listed here is
# treated as a per-object collection and skipped.
SETTINGS_NODES = {
    "CUSTOMBARNKIT", "GAMEPARAMETERS", "PHYSICSGLOBALS", "KSP_COMMUNITY_FIXES", "MFSSETTINGS",
    "RFSETTINGS", "SPACECENTERSETTINGS", "PROGRAMHANDLERSETTINGS", "CREWSETTINGS", "TRAININGTIMES",
    "TFRNDSETTINGS", "KCTBUILDINGTECHS", "KCTAIRLAUNCHTECHS", "KCTTAGS", "KCT_TECH_NODE_PERIODS",
    "KCT_TECH_NODE_TYPES", "SCMModuleTemplates", "RP1_Resource_Info", "AVIONICSCONFIGS",
    "IGNORED_EXPERIMENTS", "KERBALISM_HDD_SIZES", "STRATEGY_DEPARTMENT", "CUSTOMSCENARIO",
    "ENTRYCOSTMODS",
    # Added 2026-07-29. RP-1 patches EXPERIENCE_TRAIT[Pilot/Engineer/Scientist] and this gate had
    # never looked, so the stock 2.0x veteran-pilot G-tolerance bonus sat next to RP-1's PHYSICSGLOBALS
    # values undetected -- the two are one dial (they multiply). COARSE ON PURPOSE, and worth knowing:
    # the walker strips `[index]` decorations, so all three traits collapse to the single path
    # EXPERIENCE_TRAIT/EFFECT/<key>. That detects "AXE never re-authored trait effects at all"; it
    # does NOT detect "AXE re-authored one trait and forgot the other two". Un-stripping would need a
    # different key scheme for the whole tool.
    "EXPERIENCE_TRAIT",
}

# Disposition of every RP-1 settings area AXE does not match. Keyed by node name or by an exact
# `NODE/sub/key` path (a path wins over its node). CUT = deliberate, with the reason; anything
# absent from here is an UNDISPOSITIONED divergence and fails the gate.
#
# Keep the reasons specific enough that a future reader can tell "we decided this" from
# "nobody looked". See docs/RESTART.md for the redesign decisions these point at.
DISPOSITIONS = {
    # --- whole subsystems AXE removed (VISION.md / RESTART.md) ---
    "PROGRAMHANDLERSETTINGS": "CUT: RP-1's Programs layer is not ported; AXE has its own charters.",
    "CREWSETTINGS":           "CUT: crew progression cut forever (rp-axe-missing-rp1-mechanics).",
    "TRAININGTIMES":          "CUT: crew training cut with the crew system.",
    "TFRNDSETTINGS":          "CUT: TestFlight R&D grind bypassed (always-max-data, commit 0cd875e).",
    "KCTBUILDINGTECHS":       "CUT: no KCT. AXE gates facilities itself (AXEBUILDINGTECHS).",
    "KCTTAGS":                "CUT: no KCT build-time model.",
    "KCT_TECH_NODE_PERIODS":  "CUT: no KCT.",
    "KCT_TECH_NODE_TYPES":    "CUT: no KCT.",
    "SCMModuleTemplates":     "CUT: no KCT simulation/module-reset layer.",
    "RP1_Resource_Info":      "CUT: no KCT fuel-cost model.",
    "AVIONICSCONFIGS":        "CUT: AXE ships its own avionics (ModuleAxeAvionics); the vendored "
                              "block is inert -- see docs/BUG-CLASSES.md finding 5.",
    "STRATEGY_DEPARTMENT":    "CUT: AXE uses stock Administration departments (commit fc0d025).",
    "CUSTOMSCENARIO":         "CUT: RP-1's 1957 start scenario; AXE seeds its own career state.",
    "IGNORED_EXPERIMENTS":    "CUT: reader lives in RP0.dll; overlaps design/Science/EarthScienceRemoval.cfg.",

    # --- kept subsystems, deliberately different values ---
    "ENTRYCOSTMODS": "KEPT, re-authored: AxeEntryCostMods.cfg is generated from AXE's own tier "
                     "table, so RP-1's hand-tuned graph is expected to differ wholesale.",
    "KERBALISM_HDD_SIZES": "KEPT, re-authored: design/Science/HardDriveConfigs.cfg owns the sizes.",

    "SPACECENTERSETTINGS":    "CUT: RP-1's SpaceCenterManagement economy -- salaries, LC efficiency, "
                              "construction rush, subsidies, contract applicants. Read by RP0.dll, so "
                              "the node is not even present in the merged cache (live=node absent).",

    # --- kept sections where AXE deliberately runs the STOCK value ---
    "CUSTOMBARNKIT/ADMINISTRATION/levels":
        "STOCK, deliberate: AXE keeps the 3-level Administration and stock strategies (they are "
        "funds-economy Channel 2). RP-1's 9 levels exist because Programs replaced strategies.",
    "CUSTOMBARNKIT/ADMINISTRATION/upgrades":        "STOCK, deliberate: rides with levels above.",
    "CUSTOMBARNKIT/ADMINISTRATION/upgradesVisual":  "STOCK, deliberate: rides with levels above.",
    "CUSTOMBARNKIT/ADMINISTRATION/strategyCommitRange":
        "STOCK, deliberate and load-bearing: 0.25/0.6/1 is what the reputation-requirement analysis "
        "was done against when the override was deleted (commit fc0d025). RP-1 zeroes it because it "
        "does not use strategies at all. Do NOT copy RP-1 here.",

    # --- crew progression, cut with the crew system ---
    "CUSTOMBARNKIT/ASTRONAUTS/levels":            "CUT: crew progression. Stock 3-level Astronaut Complex.",
    "CUSTOMBARNKIT/ASTRONAUTS/upgrades":          "CUT: crew progression.",
    "CUSTOMBARNKIT/ASTRONAUTS/upgradesVisual":    "CUT: crew progression.",
    "CUSTOMBARNKIT/ASTRONAUTS/recruitHireBaseCost":   "CUT: crew progression (no hiring model).",
    "CUSTOMBARNKIT/ASTRONAUTS/recruitHireFixedRate":  "CUT: crew progression.",
    "CUSTOMBARNKIT/ASTRONAUTS/activeCrewLimit":
        "STOCK, deliberate: 5/12/-1 IS enforced (KerbalRoster + AstronautComplex, on hiring), but "
        "RP-1's own first rung is 4, so stock is the MORE generous of the two. Nothing to fix. "
        "(Was 'CUT: crew progression' -- true of the ladder, wrong about the cap being inert.)",
    "CUSTOMBARNKIT/ASTRONAUTS/crewLevelLimit":
        "STOCK, and INERT -- checked, not assumed. GameVariables.GetCrewLevelLimit has exactly two "
        "references in Assembly-CSharp: its own definition and Upgradeables/KSCFacilityLevelText, "
        "the facility upgrade TOOLTIP. KSP 1.12 never enforces it, so 1/3/-1 caps no kerbal. This "
        "is what closes the KerbalismLab crew-star question (docs/KERBALISMLAB.md): Scientist:4+ is "
        "reachable at any Astronaut Complex level.",

    # --- individual keys inside kept sections ---
    "CUSTOMBARNKIT/RESEARCH/scienceCostLimit":
        "KEPT, re-authored 2026-07-29: AXE owns an 8-level ladder (82 … -1) in "
        "design/Settings/AxeFacilities.cfg @RESEARCH. RP-1 is NOT the precedent -- it DELETED this "
        "mechanic (-1,-1,-1) because KCT still paced research by time; AXE cut KCT, so this is its "
        "only funds gate across the tree. Divergence is the design. See docs/ECONOMY.md §8.",
    "CUSTOMBARNKIT/RESEARCH/dataToScienceRatio":
        "KEPT, re-authored: flattened to 1 at all 8 levels, matching RP-1's intent (rides with "
        "scienceCostLimit above; the key diverges only because the ARRAY LENGTH does).",
    "CUSTOMBARNKIT/ADMINISTRATION/activeStrategyLimit":
        "DEFERRED: touches the programs economy; no user opinion yet.",

    # --- The EVA group: raised OPEN by this gate 2026-07-29, all five DECIDED the same day. ---
    # EVA capability is NOT crew progression -- it rides on the Astronaut Complex level, so cutting
    # the crew system silently handed these to stock. The decision (user call) was to take RP-1's
    # SHAPE -- EVA in Earth's SOI costs nothing, the facility gates only beyond-Earth EVA -- at
    # AXE's price. That shipped as @ASTRONAUTS in design/Settings/AxeFacilities.cfg, which sets
    # homebodyAtmoEVA and unlockedEVAChute; those two now MATCH RP-1 and no longer reach this table.
    # The three below still diverge, deliberately:
    "CUSTOMBARNKIT/ASTRONAUTS/unlockedEVA":
        "STOCK value, deliberate: L2 = 75,000 is AXE's beyond-Earth EVA gate. RP-1's 4 is L4 on its "
        "own 5-level ladder = 480,000. Same shape, an eighth of the price, and with "
        "homebodyAtmoEVA = true (now set) it never bites on a near-Earth career at all.",
    "CUSTOMBARNKIT/ASTRONAUTS/unlockedEVAClamber":
        "STOCK value, deliberate: 3 of 3 levels == RP-1's 5 of 5. The number differs only because "
        "the ladders are different lengths; both put clamber at the TOP level. No divergence in fact.",
    "CUSTOMBARNKIT/ASTRONAUTS/unlockedEVAFlags":
        "STOCK value, deliberate: L2, where RP-1 uses its top level. AXE is the more permissive of "
        "the two and flag-planting is cosmetic.",

    # Stock pays reputation per recovered kerbal; RP-1 all but disables it.
    "CUSTOMBARNKIT/MISSION/reputationKerbalRecovery":
        "STOCK value, deliberate (user call 2026-07-29): live 25/kerbal x RepGainMultiplier = +30 "
        "on Normal for every recovered crew member, vs RP-1's 1. Kept as a real reputational win "
        "for bringing people home. It does NOT convert to funds (FundraisingCampaign fires only on "
        "ContractReward/ScienceTransmission/Progression) but reputation is what the strategy "
        "commitment slider is measured against, so it still moves Channel 2. KNOWN GAP: "
        "tools/rep_budget.py does not model it, so Channel 2's ceiling is understated by roughly "
        "30 x (crew recovered) -- see docs/ECONOMY.md §3.",
    "CUSTOMBARNKIT/MISSION/reputationKerbalDeath":
        "STOCK value, deliberate (user call 2026-07-29): live 10 x RepLossMultiplier = -7.5 on "
        "Normal, vs RP-1's 200 (= -150). Deaths are cheap, and cheaper than the +30 the same crew "
        "would have paid on recovery. Accepted: AXE has no crew system for a loss to propagate "
        "through, so a heavy rep penalty would be the only consequence and a purely punitive one.",

    # RP-1 turns these KSPCF patches on; AXE inherited the mod's defaults (all false). Four are now
    # taken in design/Settings/AxeCommunityFixes.cfg and no longer reach this table. One is not:
    "KSP_COMMUNITY_FIXES/StrategyDuration":
        "MOD DEFAULT, deliberate (user call 2026-07-29): would make the 7 live strategies honour "
        "minLeastDuration 60-100 / maxLongestDuration 1200-1600 days. AXE runs stock strategies as "
        "funds Channel 2, so that locks the channel after each commit and expires it every 3-4 "
        "years -- a time-pressure mechanic AXE cut with KCT. See AxeCommunityFixes.cfg.",
}

MM_SUFFIX = re.compile(r"(?::[A-Za-z]+(?:\[[^\]]*\])?)+$")
NODE_LINE = re.compile(r"^([@+\-!%*]*)([A-Za-z_][A-Za-z0-9_]*)((?:\[[^\]]*\])?(?::[^\s{]*)?)\s*(\{)?\s*$")
KEY_LINE = re.compile(r"^([@+\-!%*]*)([A-Za-z_][A-Za-z0-9_.]*)((?:\[[^\]]*\])?(?::[^\s=]*)?)\s*[+\-*/^!]?=")


def clean(name):
    return MM_SUFFIX.sub("", name)


def scan_file(path, wanted, out, label, values=None):
    """Walk one cfg, recording `NODE/sub/key` for every leaf assignment under a settings node.

    The path is rooted at the first ancestor that IS a settings node, not at the file's top
    level -- that way the same walker handles a repo cfg (settings node at depth 0) and a merged
    ConfigCache (everything wrapped in UrlConfig). MM operators and :NEEDS/:FOR/[index]
    decorations are stripped, so RP-1's `@upgrades` and AXE's `@upgrades` compare equal: what
    matters is which key is SET, not how."""
    stack, pending = [], None
    for i, raw in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        s = raw.split("//")[0].strip()
        if not s:
            continue
        if s.startswith("{"):
            stack.append(pending or "?")
            pending = None
            s = s[1:].strip()
            if not s:
                continue
        if s in ("}", "};"):
            if stack:
                stack.pop()
            continue
        m = NODE_LINE.match(s)
        if m:
            name = clean(m.group(2))
            if m.group(4):                               # `NAME {` on one line
                stack.append(name)
            else:
                pending = name                           # brace is on the next line
            continue
        m = KEY_LINE.match(s)
        if not m:
            continue
        root_at = next((k for k, n in enumerate(stack) if n in wanted), None)
        if root_at is None:
            continue
        key = clean(m.group(2))
        p = "/".join(stack[root_at:] + [key])
        out[p].add(f"{label}:{i}")
        if values is not None and p not in values:
            values[p] = s.split("=", 1)[1].strip()


def harvest(root, wanted):
    """-> ({path: {where}}, {path: first value seen})"""
    out, values = defaultdict(set), {}
    if os.path.isfile(root):
        scan_file(root, wanted, out, os.path.basename(root), values)
        return out, values
    for dp, _, fs in os.walk(root):
        for fn in sorted(fs):
            if fn.endswith(".cfg"):
                p = os.path.join(dp, fn)
                scan_file(p, wanted, out, os.path.relpath(p, root), values)
    return out, values


def same(a, b):
    """Config values compare loosely: whitespace around list commas is not meaningful, and
    `true`/`True` are the same boolean to KSP."""
    def norm(v):
        v = re.sub(r"\s*,\s*", ",", (v or "").strip()).lower()
        return re.sub(r"\s+", " ", v)
    return norm(a) == norm(b)


def disposition(path):
    if path in DISPOSITIONS:
        return DISPOSITIONS[path]
    node = path.split("/")[0]
    return DISPOSITIONS.get(node)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rp1", default=DEFAULT_RP1)
    ap.add_argument("--show-cut", action="store_true")
    ap.add_argument("--cache", default=os.path.join(os.path.dirname(REPO), "Instance", "GameData",
                                                    "ModuleManager.ConfigCache"),
                    help="merged cache, to report the value actually in effect for each gap")
    args = ap.parse_args()

    if not os.path.isdir(args.rp1):
        print(f"FATAL: RP-1 not found at {args.rp1} (pass --rp1). This gate needs RP-1 checked out "
              f"as the reference; it is what AXE replaced, not what AXE depends on.")
        return 2

    rp1, rp1v = harvest(args.rp1, SETTINGS_NODES)
    axe, _ = harvest(AXE, SETTINGS_NODES)
    print(f"RP-1 settings keys: {len(rp1)}   RP-AXE settings keys: {len(axe)}")

    # The value actually in effect. RP-1 being the SOLE source is the whole point of this class:
    # where the live cache still carries RP-1's value, some other mod supplies it and the gap is
    # harmless. Only a value that DIFFERS is a setting the career silently reverted on.
    live = {}
    if os.path.exists(args.cache):
        live = harvest(args.cache, SETTINGS_NODES)[1]
        print(f"live values from {args.cache}")
    else:
        print(f"(no merged cache at {args.cache} -- cannot tell a real revert from a harmless gap;"
              f" boot the instance for a sharper answer)")

    missing = sorted(set(rp1) - set(axe))
    agree = [p for p in missing if live and p in live and same(live[p], rp1v.get(p))]
    missing = [p for p in missing if p not in set(agree)]
    dispositioned, undispositioned, still_open = [], [], []
    for p in missing:
        d = disposition(p)
        if d is None:
            undispositioned.append(p)
        elif d.startswith("OPEN"):
            still_open.append(p)
        else:
            dispositioned.append(p)

    print(f"RP-1 sets but AXE does not: {len(missing)} diverging "
          f"({len(dispositioned)} settled, {len(still_open)} OPEN, {len(undispositioned)} undispositioned)"
          f"{f', + {len(agree)} where another mod already supplies RP-1s value' if agree else ''}\n")

    if still_open:
        print(f"=== OPEN -- a recorded divergence with no decision yet ({len(still_open)}) ===")
        for p in still_open:
            shown = f"live={live[p]}" if p in live else "live=(node absent)"
            print(f"  {p}\n      {shown}   RP-1 {rp1v.get(p, '?')}\n      {disposition(p)}")
        print()

    if undispositioned:
        print(f"=== UNDISPOSITIONED -- these silently fall back to stock/RO ({len(undispositioned)}) ===")
        bynode = defaultdict(list)
        for p in undispositioned:
            bynode[p.split("/")[0]].append(p)
        for node in sorted(bynode):
            print(f"  {node}")
            for p in bynode[node]:
                where = sorted(rp1[p])[0]
                shown = f"live={live[p]}" if p in live else "live=(node absent)"
                print(f"      {p.split('/', 1)[1]:46s}{shown:<32s}"
                      f"RP-1 {rp1v.get(p, '?')}   ({where})")
        print("\n  Decide each one, then add it to DISPOSITIONS in this file (CUT/OPEN + why) or")
        print("  re-author it under GameData/RP-AXE/design/Settings/.\n")

    if args.show_cut:
        print(f"=== dispositioned ({len(dispositioned)}) ===")
        seen = set()
        for p in dispositioned:
            d = disposition(p)
            k = (p if p in DISPOSITIONS else p.split("/")[0])
            if k in seen:
                continue
            seen.add(k)
            print(f"  {k}\n      {d}")
        print()

    if undispositioned:
        print("FAIL -- undispositioned settings divergence.")
        return 1
    print("OK -- every RP-1 settings key AXE does not set is a recorded decision.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
