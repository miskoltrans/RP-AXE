#!/usr/bin/env python3
"""T3 addendum — classify PARTUPGRADEs that are gated on an RP-1 tech node but authored OUTSIDE
RP-1's own folder (RealismOverhaul, RealFuels).

tools/upgrade_audit.py + curate_upgrades.py scoped T3 to "RP-1-authored PARTUPGRADEs absent under
AXE" by walking only GameData/RP-1 for FRESH `PARTUPGRADE { }` definitions. That misses two related
cases (found 2026-07-01 investigating the `[not-in-curated]` upgrades in what was then
manifest/human-orbital-partlist.md -- one of the RP-1 milestone extractions, removed once the
tree was authored; see git history if the original listing is ever wanted):

  1. Upgrades that ship from a KEPT dependency and bake an RP-1 techRequired directly into their own
     definition (RealismOverhaul/RO_RealFuels.cfg's per-tank-TYPE ladder — 21 upgrades). No RP-1
     folder involvement at all; upgrade_audit.py's RP-1-only walk can't see them.
  2. Upgrades defined in a dependency against a STOCK techRequired, then re-gated onto the RP-1 tree
     by an `@PARTUPGRADE[name]{ %techRequired = ... }` PATCH inside RP-1's own folder (not a fresh
     definition) — RO's heatshield-material presets (ROHeatshields, 6) and RealFuels' MLI-wrapping
     tiers (RealFuels, 5). upgrade_audit.py's regex only matches fresh `PARTUPGRADE {` headers, so
     it never saw these patch-only blocks either.

Both are live under AXE (the base upgrade ships from a kept dependency) but their techRequired is an
RP-1 node id that doesn't exist in AXE's tree, so they fall through AXE's wildcard
`@PARTUPGRADE[*]{ %techRequired = parking }` placement — same as anything else not yet homed.

Explicitly OUT of scope (handled elsewhere, not silently dropped):
  - `commsTL1-10` / `solarTL*` — RealAntennas/ProceduralAvionics tech-level ladders already carry a
    deliberate `KEEP-techlevel-TODO` placeholder in the extract_*_partlist.py scripts (prior user
    note); adding them here would fork that decision onto a second mechanism.
  - `Upgrade-Colony` (KerbalismConfig/System/Sickbay.cfg, techRequired=improvedHabitats) — a single
    Kerbalism one-off, different mod family, gates a node far past current milestone scope.

Ground truth for every name/tech/title below is looked up live from the compiled reference cache
(same source extract_*_partlist.py uses), not guessed from source text — two RP-1 patch targets
(`RFTech-Tank-Iso-Al`, `RFTech-Tank-Balloon-SteelAl`) and two more (`RFTech-Balloon-SteelAlCu/Li`,
RP-1's own naming-mismatch typo for the `-Tank-` versions) were checked and confirmed orphaned
(compile to nothing) — correctly excluded.

Output: manifest/upgrades-curated.tsv (merged, re-sorted; 626 -> 658 rows)
"""
import os

# Reference instances live NEXT TO this repo, i.e. <ksp root>/ksp_rp1_*. Derive that root from
# __file__ rather than hardcoding it: seven tools had "C:\git\ksp_rp1_*" (one directory too
# high), which made them die on FileNotFoundError while the data sat there intact. 2026-07-29.
_KSPROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
MAN = os.path.join(ROOT, "manifest")
CURATED_TSV = os.path.join(MAN, "upgrades-curated.tsv")
CC = os.path.join(_KSPROOT, "ksp_rp1_expanded", "GameData", "ModuleManager.ConfigCache")

RO_REALFUELS_COMPANION = (
    "RealismOverhaul/RO_RealFuels.cfg (already live under AXE -- RealismOverhaul ships it whole, "
    "TANK_DEFINITION/TANK_TYPE_OPTION already wires each upgrade to every curated RF tank; only "
    "needs the P2 techRequired remap RP-1 node -> AXE node, same as the other KEEP-* rows)")
RO_REALFUELS_REASON = (
    "RealFuels per-TANK-TYPE tech tier (Sep/Iso/Balloon/ServiceModule/Battery/WetWing material & "
    "capacity grade + the AddLifeSupport/AddOxygenGas resource-unlock pair); sibling ladder to "
    "Tree/RFTechLevels.cfg's already-KEEP-engine-typelevel per-engine-TYPE tiers; targets the curated "
    "procedural+modular RF tank family (RO-RFTank-*/ROT-*-{Separate,Integral,Balloon,ServiceModule})")

GROUPS = [
    {  # baked-in RP-1 techRequired directly in the RealismOverhaul definition -- no RP-1 patch exists
        "sourcefile": "RealismOverhaul/RO_RealFuels.cfg",
        "disposition": "KEEP-tank-typelevel",
        "companion": RO_REALFUELS_COMPANION,
        "reason": RO_REALFUELS_REASON,
        "names": [
            "RFTech-AddLifeSupport", "RFTech-AddOxygenGas",
            "RFTech-Battery-II", "RFTech-Battery-III", "RFTech-Battery-IV",
            "RFTech-SM-II", "RFTech-SM-III", "RFTech-SM-IV",
            "RFTech-Tank-Balloon-SteelAlCu", "RFTech-Tank-Balloon-SteelAlLi",
            "RFTech-Tank-Iso-AlCu", "RFTech-Tank-Iso-AlLi", "RFTech-Tank-Iso-Comp", "RFTech-Tank-Iso-Magic",
            "RFTech-Tank-Sep-Al", "RFTech-Tank-Sep-Al2", "RFTech-Tank-Sep-AlCu", "RFTech-Tank-Sep-AlLi",
            "RFTech-Tank-Sep-Starship", "RFTech-Tank-Sep-Stir", "RFTech-Tank-Wet-Wing2",
        ],
    },
    {  # ROHeatshields base def (techRequired=engineering101, stock) + RP-1/Tree/ROHeatshields.cfg patch
        "sourcefile": "ROHeatshields/Parts/Upgrade.cfg",
        "disposition": "KEEP-capability",
        "companion_tmpl": (
            "ROHeatshields/Parts/Upgrade.cfg (base upgrade, live) + RP-1/Tree/ROHeatshields.cfg "
            "`@PARTUPGRADE[{name}]:FOR[RP-0]{{%techRequired={tech}}}` (the tech-remap patch -- must "
            "be ported/reauthored since RP-1 itself is absent under AXE)"),
        "reason": (
            "ROHeatshields ablator/heat-sink material preset on the curated procedural heatshield "
            "(ROH-AdjustableHS); base techRequired is the stock id `engineering101` -- RP-1's own "
            "Tree/ROHeatshields.cfg patch is what re-gates it onto the RP-1 tree"),
        "names": ["Heatsink", "MercuryHS", "GeminiHS", "EarlyLunarHS", "LunarHS", "Inflatable"],
    },
    {  # RealFuels base def (techRequired=generalConstruction, stock) + RP-1/Tree/RFTechLevels.cfg patch
        "sourcefile": "RealFuels/Resources/MLITechUpgrades.cfg",
        "disposition": "KEEP-capability",
        "companion_tmpl": (
            "RealFuels/Resources/MLITechUpgrades.cfg (base upgrade, live) + "
            "RP-1/Tree/RFTechLevels.cfg `@PARTUPGRADE[{name}]{{%techRequired={tech}}}` (the tech-remap "
            "patch -- must be ported/reauthored since RP-1 itself is absent under AXE)"),
        "reason": (
            "RealFuels multi-layer-insulation wrapping-density tier (thermal-protection tank tech); "
            "sibling of the already-curated `RFTech-MLI-UpgradeBalloon`; base techRequired is the "
            "stock id `generalConstruction` -- RP-1's own Tree/RFTechLevels.cfg patch re-gates it"),
        "names": ["MLI.Upgrade1", "MLI.Upgrade2", "MLI.Upgrade3", "MLI.Upgrade4", "MLI.Upgrade5"],
    },
]

# ---------------------------------------------------------------- ground truth: live cache lookup
def lookup_cache(names):
    stack, pending, cur = [], None, None
    found = {}
    with open(CC, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if s == "{":
                stack.append(pending)
                if pending == "PARTUPGRADE" and cur is None:
                    cur = {"name": None, "tech": None, "title": None, "depth": len(stack)}
                pending = None
            elif s == "}":
                if stack: stack.pop()
                if cur and len(stack) < cur["depth"]:
                    if cur["name"] in names:
                        found[cur["name"]] = (cur["tech"], cur["title"])
                    cur = None
            elif "=" in s and not s.startswith("//"):
                k, _, v = s.partition("="); k = k.strip(); v = v.strip()
                if cur is not None:
                    if k == "name" and cur["name"] is None: cur["name"] = v
                    elif k.lower() == "techrequired": cur["tech"] = v
                    elif k == "title" and cur["title"] is None: cur["title"] = v
                pending = None
            elif s and not s.startswith("//"):
                pending = s
    return found

def main():
    all_names = {n for g in GROUPS for n in g["names"]}
    live = lookup_cache(all_names)

    with open(CURATED_TSV, encoding="utf-8") as f:
        header = f.readline()
        existing_lines = f.readlines()
    existing_names = {l.split("\t", 1)[0] for l in existing_lines}

    new_rows, missing, skipped = [], [], []
    for g in GROUPS:
        for name in g["names"]:
            if name in existing_names:
                skipped.append(name); continue
            if name not in live:
                missing.append(name); continue
            tech, title = live[name]
            companion = g.get("companion") or g["companion_tmpl"].format(name=name, tech=tech)
            new_rows.append((name, tech, g["sourcefile"], g["disposition"], companion, g["reason"], title or ""))

    if missing:
        print(f"WARNING - not found live in reference cache (skipped, verify manually): {missing}")
    if skipped:
        print(f"already curated (skipped): {skipped}")

    all_rows = [l.rstrip("\n").split("\t") for l in existing_lines] + [list(r) for r in new_rows]
    all_rows.sort(key=lambda r: (r[3], r[2], r[0]))

    with open(CURATED_TSV, "w", encoding="utf-8", newline="") as f:
        f.write(header)
        for r in all_rows:
            f.write("\t".join(r) + "\n")

    print(f"added: {len(new_rows)} (expected {len(all_names)})")
    print(f"total rows now: {len(all_rows)}")
    print(f"-> {CURATED_TSV}")

if __name__ == "__main__":
    main()
