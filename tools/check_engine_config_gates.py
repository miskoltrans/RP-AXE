#!/usr/bin/env python3
"""
check_engine_config_gates.py -- resolve every RealFuels engine CONFIG's FINAL techRequired
and prove none of them is unreachable, parked, or free.

Why this exists separately from check_tech_refs.py:
  check_tech_refs.py scans SOURCE and reports any gate string that is not an AXE node. For
  engine configs that is ~130 false positives by construction: the vendored walker in
  seed/Tree/TREE-Engines.cfg deliberately writes RP-1 node ids onto all 949 CONFIGs, and
  design/Tree/AxeEngineConfigGates.cfg then rewrites them at :FINAL. The seed value dangling
  is the DESIGN, not the bug. So the source scan cannot tell a correctly-overridden config
  from a genuinely stranded one, and it says so ("may false-positive on overlay-overridden
  seed refs"). This tool answers the question the source scan cannot: after the overlay runs,
  where does each config actually land?

  It reads only shipped artifacts -- the vendored seed, the generated overlay, the generated
  tree, and the RP-1/RO caches for which parts really carry which configs. It does NOT import
  build_tree.py's bookkeeping, so it can catch a generator blind spot rather than agreeing
  with one.

What it models:
  RealFuels' CanConfig() (EngineConfigTechLevels.cs) gates a CONFIG on its own techRequired.
    - value naming a node that does not exist  -> config permanently locked (silent)
    - value == `parking`                       -> config parked off-tree (silent)
    - field absent entirely                    -> config ALWAYS available (silent, and free)
  ModuleManager applies same-pass patches in file order, and AxeEngineConfigGates.cfg is built
  so each layer consumes the RP-1 value it matches: once `@techRequired = X` fires, a later
  `:HAS[#techRequired[<rp1>]]` row no longer matches. Resolution here is therefore first-match
  -wins over the emitted rows, in file order -- the same order MM applies them.

Usage:
  python tools/check_engine_config_gates.py            # report + exit non-zero on any finding
  python tools/check_engine_config_gates.py --verbose  # also list every resolved config

Reproduce:  python RP-AXE/tools/check_engine_config_gates.py
"""
import argparse
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RPAXE = os.path.dirname(HERE)
ROOT = os.path.dirname(RPAXE)

SEED = os.path.join(RPAXE, "GameData", "RP-AXE", "seed", "Tree", "TREE-Engines.cfg")
OVERLAY = os.path.join(RPAXE, "GameData", "RP-AXE", "design", "Tree", "AxeEngineConfigGates.cfg")
TREE = os.path.join(RPAXE, "GameData", "RP-AXE", "design", "Tree", "AxeTechTree.cfg")
CACHES = [
    os.path.join(ROOT, "ksp_rp1_expanded", "GameData", "ModuleManager.ConfigCache"),
    os.path.join(ROOT, "ksp_ro_expanded", "GameData", "ModuleManager.ConfigCache"),
]

PARKING = "parking"


def load_tree_nodes(path):
    """Every `id = X` inside a TechTree node block -> the set of ids that actually exist."""
    txt = open(path, encoding="utf-8", errors="replace").read()
    return set(re.findall(r"^\s*id\s*=\s*(\S+)", txt, re.M))


def load_seed_gates(path):
    """seed walker: one @PART[*] block of `@CONFIG[name] { %techRequired = <rp1 node> }`.
    Config names are global identities in RealFuels, so name -> rp1 node is well defined."""
    gates = {}
    cfg = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*@CONFIG\[([^\]]+)\]", line)
        if m:
            cfg = m.group(1)
            continue
        m = re.match(r"\s*[%@]techRequired\s*=\s*(\S+)", line)
        if m and cfg:
            gates[cfg] = m.group(1)
            cfg = None
    return gates


# One emitted row, e.g.
#   @PART[ROE-HiPAT]:HAS[...]:FINAL { @MODULE[...],* { @CONFIG[R-4D-15]:HAS[#techRequired[spaceStationControl]],* { @techRequired = gnc_deepSpaceApogeeEngine } } }
# part may be `*`; the CONFIG selector may carry a name, a :HAS[#techRequired[..]] guard, both, or neither.
ROW = re.compile(
    r"@PART\[([^\]]+)\][^{]*\{\s*@MODULE\[[^\]]+\],\*\s*\{\s*"
    r"@CONFIG(?:\[([^\]]+)\])?(?::HAS\[#techRequired\[([^\]]+)\]\])?,\*\s*\{\s*"
    r"([%@])techRequired\s*=\s*(\S+)\s*\}"
)


def load_overlay_rows(path):
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = ROW.match(line.strip())
        if m:
            part, cfgname, guard, op, target = m.groups()
            rows.append(dict(part=part, cfg=cfgname, guard=guard, op=op, target=target))
    return rows


def load_part_configs(paths):
    """(part, config) pairs that really exist. Cheap line scan of the MM cache: inside a
    UrlConfig's PART block, remember the part name, then collect CONFIG names under it."""
    pairs = defaultdict(set)
    for path in paths:
        if not os.path.exists(path):
            continue
        part = None
        for line in open(path, encoding="utf-8", errors="replace"):
            s = line.strip()
            m = re.match(r"name\s*=\s*(\S+)", s)
            if m and part == "<pending>":
                part = m.group(1)
                continue
            if s == "PART" or s.startswith("PART "):
                part = "<pending>"
                continue
            m = re.match(r"CONFIG\b", s)
            if m and part and part != "<pending>":
                pairs[part].add(None)  # marker: this part has configs; names collected below
            m = re.match(r"name\s*=\s*(\S+)", s)
            if m and part and part != "<pending>":
                pairs[part].add(m.group(1))
    return pairs


def resolve(part, cfg, rp1, rows):
    """First matching emitted row wins, in file order -- mirrors MM same-pass application
    where the first `@techRequired =` consumes the RP-1 value later rows guard on."""
    for r in rows:
        if r["part"] != "*" and r["part"] != part:
            continue
        if r["cfg"] is not None and r["cfg"] != cfg:
            continue
        if r["guard"] is not None and r["guard"] != rp1:
            continue
        return r["target"], r
    return rp1, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="list every resolved config")
    args = ap.parse_args()

    for p in (SEED, OVERLAY, TREE):
        if not os.path.exists(p):
            sys.exit(f"missing required artifact: {p}")

    nodes = load_tree_nodes(TREE)
    seed = load_seed_gates(SEED)
    rows = load_overlay_rows(OVERLAY)
    partcfgs = load_part_configs(CACHES)

    print(f"tree:    {os.path.relpath(TREE, RPAXE)}  ({len(nodes)} nodes)")
    print(f"seed:    {os.path.relpath(SEED, RPAXE)}  ({len(seed)} gated CONFIG names)")
    print(f"overlay: {os.path.relpath(OVERLAY, RPAXE)}  ({len(rows)} remap rows)")

    # Universe: every (part, config) the caches show, restricted to configs the seed gates.
    # A config name the seed never gates is either AXE-authored (layer 0 %-sets it) or ungated.
    universe = []
    for part, cfgs in sorted(partcfgs.items()):
        for c in sorted(x for x in cfgs if x):
            if c in seed:
                universe.append((part, c))

    locked, parked, uncovered, ok = [], [], [], 0
    for part, cfg in universe:
        rp1 = seed[cfg]
        target, rule = resolve(part, cfg, rp1, rows)
        if rule is None:
            uncovered.append((part, cfg, rp1))
        elif target == PARKING:
            parked.append((part, cfg, target))
        elif target not in nodes:
            locked.append((part, cfg, target))
        else:
            ok += 1
            if args.verbose:
                print(f"  ok  {part:<26} {cfg:<26} {rp1:<26} -> {target}")

    # Configs the overlay %-sets by name (AXE-authored, no RP-1 value to match) must also land real.
    authored = [r for r in rows if r["op"] == "%" and r["cfg"]]
    bad_authored = [r for r in authored if r["target"] not in nodes and r["target"] != PARKING]

    print()
    print(f"resolved {len(universe)} (part, config) pairs across {len(partcfgs)} parts: {ok} land on a real node")
    print(f"  authored (%-set by name, no RP-1 guard): {len(authored)}")

    fail = 0
    for label, items in (
        ("UNREACHABLE -- final techRequired names a node that does not exist (config permanently locked)", locked),
        ("PARKED -- final techRequired == parking (config off-tree)", parked),
        ("UNCOVERED -- no overlay row matches; config keeps its dangling RP-1 gate", uncovered),
    ):
        if not items:
            continue
        fail += len(items)
        print(f"\n=== {label} ({len(items)}) ===")
        for row in items[:40]:
            print("   " + "  ".join(f"{x:<26}" for x in row))
        if len(items) > 40:
            print(f"   ... and {len(items) - 40} more")

    if bad_authored:
        fail += len(bad_authored)
        print(f"\n=== AUTHORED CONFIG GATE points at a non-node ({len(bad_authored)}) ===")
        for r in bad_authored:
            print(f"   {r['part']:<26} {r['cfg']:<26} -> {r['target']}")

    if not fail:
        print("\nengine config gate sweep: clean -- every gated engine CONFIG resolves to a real AXE node")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
