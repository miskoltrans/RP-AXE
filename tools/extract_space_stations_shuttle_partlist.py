#!/usr/bin/env python3
"""Extract the parts + upgrades RP-1 places at the 'space stations & shuttle era' milestone nodes,
from the rp1_expanded ConfigCache, cross-referenced against our curated manifest.

Node set (user's x-axis method, 2026-07-06): the fifth milestone batch, picking up immediately where
`crewed-lunar-landing-partlist` left off (anchor `improvedLandingEngines`, x=-2017, down to x=-2537;
confirmed contiguous handoff, no gap). Take every RP-1 tree node in x=-1932..-1592 (the next two tree
columns), ordered by tree x (progression order). Anchor = `spaceShuttles` ("Space Shuttles", the last/
most-advanced column in this batch, x=-1592).

Key milestone = SPACE STATIONS & SHUTTLE (Skylab/Salyut: `earlySpaceStations`; deep-space probes:
`deepSpaceScience`, `advancedUncrewedLanding`; Space Shuttle: `spaceShuttles`, `matureTurbofans`,
`largeSpaceplaneControl`). Excludes ORPHANS/orphanParts and ModularLaunchPads (per prior batches)."""
import os, collections

CC = r"C:\git\ksp\ksp_rp1_expanded\GameData\ModuleManager.ConfigCache"
REPO = r"C:\git\ksp\RP-AXE"
CURATED = os.path.join(REPO, "manifest", "curated-parts.tsv")
UPGRADES = os.path.join(REPO, "manifest", "upgrades-curated.tsv")
PREV = [os.path.join(REPO, "manifest", "first-orbit-partlist.tsv"),
        os.path.join(REPO, "manifest", "human-orbital-partlist.tsv"),
        os.path.join(REPO, "manifest", "interplanetary-lunar-probes-partlist.tsv"),
        os.path.join(REPO, "manifest", "crewed-lunar-landing-partlist.tsv")]
OUT_TSV = os.path.join(REPO, "manifest", "space-stations-shuttle-partlist.tsv")
OUT_MD  = os.path.join(REPO, "manifest", "space-stations-shuttle-partlist.md")

# (id, title, x) ordered by x ascending = progression. Auto-derived from RP0TechTree.cfg
# (all nodes with -1932 <= x <= -1592); titles verified against the tree.
NODES = [
 ("materialsScienceSpaceStation", "Space Station Era Materials Science", -1932),
 ("electronicsSpaceStation", "Space Station Era Electronics Research", -1932),
 ("earlySpaceStations", "Early Space Stations", -1847),
 ("spaceStationControl", "Space Station Attitude Control", -1847),
 ("advancedUncrewedLanding", "Advanced Uncrewed Landing", -1847),
 ("hydrolox1972", "1972-1975 Hydrolox Engines", -1847),
 ("prototypeFRSC", "Prototype FRSC Engines", -1847),
 ("orbitalRocketry1972", "1972-1975 Orbital Rocketry", -1847),
 ("stagedCombustion1972", "1972-1975 ORSC Engines", -1847),
 ("solids1972", "1972-1975 Solid Rocket Engines", -1847),
 ("earlyElecPropulsion", "Early Electric Propulsion", -1847),
 ("earlyNuclearPropulsion", "Early Nuclear Propulsion", -1847),
 ("basicLifeSupport", "Basic Life Support and ISRU", -1847),
 ("spaceStationSolarPanels", "Space Station Solar Panels", -1847),
 ("deepSpaceComms", "Deep Space Communications", -1847),
 ("advancedAvionics", "Advanced Avionics and Probes", -1847),
 ("deepSpaceScience", "Deep Space Science Experiments", -1847),
 ("improvedCapsules", "Improved Capsules", -1762),
 ("hydrolox1976", "1976-1980 Hydrolox Engines", -1762),
 ("FRSC1976", "1976-1980 FRSC Engines", -1762),
 ("orbitalRocketry1976", "1976-1980 Orbital Rocketry", -1762),
 ("stagedCombustion1976", "1976-1980 ORSC Engines", -1762),
 ("solids1976", "1976-1980 Solid Rocket Engines", -1762),
 ("multihundredWattRTG", "Multi-Hundred Watt RTGs", -1762),
 ("highDataRateComms", "High Data Rate Communications", -1762),
 ("materialsScienceSpaceplanes", "Spaceplanes Era Materials Science", -1677),
 ("electronicsSpaceplanes", "Spaceplanes Era Electronics Research", -1677),
 ("matureTurbofans", "Mature Turbofans", -1592),
 ("spaceShuttles", "Space Shuttles", -1592),   # <-- anchor
 ("largeSpaceplaneControl", "Large Spaceplane Control", -1592),
 ("hydrolox1981", "1981-1985 Hydrolox Engines", -1592),
 ("FRSC1981", "1981-1985 FRSC Engines", -1592),
 ("orbitalRocketry1981", "1981-1985 Orbital Rocketry", -1592),
 ("stagedCombustion1981", "1981-1985 ORSC Engines", -1592),
 ("solids1981", "1981-1985 Solid Rocket Engines", -1592),
 ("elecPropulsion1981", "1981-1985 Electric Propulsion", -1592),
 ("basicNuclearPropulsion", "Basic Nuclear Propulsion", -1592),
 ("improvedLifeSupport", "Improved Life Support and ISRU", -1592),
 ("gphsRTG", "GPHS-RTGs", -1592),
 ("maturePower", "Mature Power Generation and Storage", -1592),
 ("largeScaleComms", "Large Scale Communications", -1592),
 ("nextGenAvionics", "Next Generation Avionics and Probes", -1592),
 ("scienceExploration", "Exploration Era Science", -1592),
]
NSET = {k for k, _, _ in NODES}

def load_tsv(path):
    with open(path, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        rows = [l.rstrip("\n").split("\t") for l in f]
    return header, rows

ph, prows = load_tsv(CURATED)
pn = ph.index("name"); pt = ph.index("title"); pm = ph.index("mod")
curated_title = {r[pn]: r[pt] for r in prows if len(r) > pt}
EXCLUDE_MODS = {"ModularLaunchPads"}
excluded = {r[pn] for r in prows if len(r) > pm and r[pm] in EXCLUDE_MODS}

uh, urows = load_tsv(UPGRADES)
un = uh.index("name") if "name" in uh else 0
ud = uh.index("disposition") if "disposition" in uh else None
curated_up = {r[un]: (r[ud] if ud is not None and len(r) > ud else "?") for r in urows if len(r) > un}

# parts already pulled by prior milestone partlists (for the "prev" de-dup flag)
prev_parts = set()
for f in PREV:
    if os.path.exists(f):
        for i, line in enumerate(open(f, encoding="utf-8")):
            if i == 0: continue
            c = line.rstrip("\n").split("\t")
            if len(c) > 3 and c[2] == "part": prev_parts.add(c[3])

# --- parse ConfigCache: brace-depth walk, capture PART/PARTUPGRADE name+title+TechRequired ---
part_nodes = collections.defaultdict(list); up_nodes = collections.defaultdict(list); titles = {}
stack, pending, cur = [], None, None
with open(CC, encoding="utf-8", errors="replace") as f:
    for line in f:
        s = line.strip()
        if s == "{":
            stack.append(pending)
            if pending in ("PART", "PARTUPGRADE") and cur is None:
                cur = {"type": pending, "name": None, "title": None, "tech": None, "depth": len(stack)}
            pending = None
        elif s == "}":
            if stack: stack.pop()
            if cur and len(stack) < cur["depth"]:
                if cur["tech"] in NSET and cur["name"]:
                    (part_nodes if cur["type"] == "PART" else up_nodes)[cur["tech"]].append(cur["name"])
                    if cur["title"]: titles[cur["name"]] = cur["title"]
                cur = None
        elif "=" in s and not s.startswith("//"):
            k, _, v = s.partition("="); k = k.strip(); v = v.strip()
            if cur and stack and stack[-1] in ("PART", "PARTUPGRADE"):
                if k == "name" and cur["name"] is None: cur["name"] = v
                elif k == "title" and cur["title"] is None: cur["title"] = v
                elif k.lower() == "techrequired": cur["tech"] = v
            pending = None
        elif s and not s.startswith("//"):
            pending = s

# --- emit ---
tot_p = tot_pc = tot_u = tot_prev = 0
md = ["# Space Stations & Shuttle Era Milestone Partlist (extracted from RP-1 @ rp1_expanded)\n",
      "The batch after `crewed-lunar-landing-partlist.md`. **Anchor = `spaceShuttles`",
      "(\"Space Shuttles\", tree x=-1592).** Node set = every RP-1 tree node in x=-1932..-1592 (the two",
      "tree columns immediately after the crewed-lunar-landing batch's cutoff, confirmed contiguous),",
      "ordered by tree x (progression). Key milestone = **space stations & the Shuttle** (Skylab/Salyut:",
      "`earlySpaceStations`; deep-space probes: `deepSpaceScience`, `advancedUncrewedLanding`; Space",
      "Shuttle: `spaceShuttles`, `matureTurbofans`, `largeSpaceplaneControl`).\n",
      "✓=curated (in manifest), ✗=uncurated, ⟳=already in a prior partlist. Upgrade tag = our disposition.",
      "Excludes ORPHANS/orphanParts (Non-RP-1 catch-all) and ModularLaunchPads.\n",
      "Source: `C:\\git\\ksp_rp1_expanded` ConfigCache. Generated by tools/extract_space_stations_shuttle_partlist.py.\n"]
tsv = ["node\tnode_title\tx\tkind\tname\tcurated\tprev\ttitle"]
for nid, ntitle, x in NODES:
    parts = [p for p in sorted(set(part_nodes.get(nid, []))) if p not in excluded]
    ups = sorted(set(up_nodes.get(nid, [])))
    nc = sum(1 for p in parts if p in curated_title)
    npv = sum(1 for p in parts if p in prev_parts)
    md.append(f"\n## {ntitle}  `{nid}`  (x={x})  — {len(parts)} parts ({nc} curated, {npv} already-pulled), {len(ups)} upgrades")
    for p in parts:
        c = p in curated_title; pv = p in prev_parts
        t = curated_title.get(p) or titles.get(p, "")
        flag = "⟳" if pv else ("✓" if c else "✗")
        md.append(f"- {flag} `{p}`  {t}")
        tsv.append(f"{nid}\t{ntitle}\t{x}\tpart\t{p}\t{'yes' if c else 'no'}\t{'yes' if pv else 'no'}\t{t}")
        tot_p += 1; tot_pc += c; tot_prev += pv
    for u in ups:
        disp = curated_up.get(u)
        if disp is None:
            disp = "KEEP-techlevel-TODO" if u.startswith(("solarTL", "commsTL")) else "not-in-curated"
        md.append(f"  - ⬆ `{u}`  [{disp}]")
        tsv.append(f"{nid}\t{ntitle}\t{x}\tupgrade\t{u}\t{disp}\t\t")
        tot_u += 1

with open(OUT_TSV, "w", encoding="utf-8") as f: f.write("\n".join(tsv) + "\n")
with open(OUT_MD, "w", encoding="utf-8") as f: f.write("\n".join(md) + "\n")
print(f"TOTAL: {tot_p} parts ({tot_pc} curated / {tot_p-tot_pc} uncurated; {tot_prev} already pulled), {tot_u} upgrades")
print("per-node (curated/total parts, prev, upgrades):")
for nid, ntitle, x in NODES:
    parts = [p for p in sorted(set(part_nodes.get(nid, []))) if p not in excluded]
    ups = sorted(set(up_nodes.get(nid, [])))
    nc = sum(1 for p in parts if p in curated_title); npv = sum(1 for p in parts if p in prev_parts)
    print(f"  x={x:>6}  {nc:>2}/{len(parts):<3} ({npv} prev) {len(ups):>2}up  {nid:<28} {ntitle}")
print(f"-> {OUT_MD}\n-> {OUT_TSV}")
