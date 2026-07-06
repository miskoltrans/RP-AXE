#!/usr/bin/env python3
"""Extract the parts + upgrades RP-1 places at the 'modular stations, rovers & ISS assembly'
milestone nodes, from the rp1_expanded ConfigCache, cross-referenced against our curated manifest.

Node set (user's x-axis method, 2026-07-06): the sixth milestone batch, picking up immediately where
`space-stations-shuttle-partlist` left off (anchor `spaceShuttles`, x=-1592). Take every RP-1 tree node
in x=-1507..-1167 (the next five tree columns), ordered by tree x (progression). Anchor =
`largeScaleOrbitalCon` ("Large Scale Orbital Construction", the last/most-advanced column in this
batch, x=-1167).

Key milestone = MODULAR STATIONS, ROBOTIC EXPLORATION & ISS ASSEMBLY (Mir: `modularSpaceStations`;
Sojourner/Pathfinder/Huygens/Stardust-era probes: `interplanetaryRovers`; ISS assembly begins:
`largeScaleOrbitalCon`, `largeStationControl`). Excludes ORPHANS/orphanParts and ModularLaunchPads
(per prior batches)."""
import os, collections

CC = r"C:\git\ksp\ksp_rp1_expanded\GameData\ModuleManager.ConfigCache"
REPO = r"C:\git\ksp\RP-AXE"
CURATED = os.path.join(REPO, "manifest", "curated-parts.tsv")
UPGRADES = os.path.join(REPO, "manifest", "upgrades-curated.tsv")
PREV = [os.path.join(REPO, "manifest", "first-orbit-partlist.tsv"),
        os.path.join(REPO, "manifest", "human-orbital-partlist.tsv"),
        os.path.join(REPO, "manifest", "interplanetary-lunar-probes-partlist.tsv"),
        os.path.join(REPO, "manifest", "crewed-lunar-landing-partlist.tsv"),
        os.path.join(REPO, "manifest", "space-stations-shuttle-partlist.tsv")]
OUT_TSV = os.path.join(REPO, "manifest", "modular-stations-rovers-partlist.tsv")
OUT_MD  = os.path.join(REPO, "manifest", "modular-stations-rovers-partlist.md")

# (id, title, x) ordered by x ascending = progression. Auto-derived from RP0TechTree.cfg
# (all nodes with -1507 <= x <= -1167); titles verified against the tree.
NODES = [
 ("materialsScienceLongTerm", "Long-Term Space Habitation Era Materials Science", -1507),
 ("electronicsLongTerm", "Long-Term Space Habitation Era Electronics Research", -1507),
 ("refinedTurbofans", "Refined Turbofans", -1422),
 ("improvedSpaceplanes", "Improved Spaceplanes", -1422),
 ("advancedCapsules", "Advanced Capsules", -1422),
 ("modularSpaceStations", "Modular Space Stations", -1422),
 ("standardDockingPorts", "Standardized Docking Ports", -1422),
 ("hydrolox1986", "1986-1991 Hydrolox Engines", -1422),
 ("FRSC1986", "1986-1991 FRSC Engines", -1422),
 ("orbitalRocketry1986", "1986-1991 Orbital Rocketry", -1422),
 ("stagedCombustion1986", "1986-1991 ORSC Engines", -1422),
 ("solids1986", "1986-1991 Solid Rocket Engines", -1422),
 ("elecPropulsion1986", "1986-1997 Electric Propulsion", -1422),
 ("improvedNuclearPropulsion", "Improved Nuclear Propulsion", -1422),
 ("longTermLifeSupport", "Long-Term Life Support and ISRU", -1422),
 ("improvedNuclearPower", "Improved Nuclear Power Generation", -1422),
 ("largeScaleSolarArrays", "Large Scale Solar Arrays", -1422),
 ("massiveScaleComms", "Massive Scale Communications", -1422),
 ("longTermAvionics", "Long-Term Space Habitation Era Avionics and Probes", -1422),
 ("sampleReturnScience", "Sample Return Science Experiments", -1422),
 ("interplanetaryRovers", "Interplanetary Rovers", -1337),
 ("hydrolox1992", "1992-1997 Hydrolox Engines", -1337),
 ("FRSC1992", "1992-1997 FRSC Engines", -1337),
 ("orbitalRocketry1992", "1992-1997 Orbital Rocketry", -1337),
 ("stagedCombustion1992", "1992-1997 ORSC Engines", -1337),
 ("solids1992", "1992-1997 Solid Rocket Engines", -1337),
 ("materialsScienceInternational", "International Cooperation Era Materials Science", -1252),
 ("electronicsInternational", "International Cooperation Era Electronics Research", -1252),
 ("scramjetEngines", "Scramjet Engines", -1167),
 ("advancedSpaceplanes", "Advanced Spaceplanes", -1167),
 ("largeScaleOrbitalCon", "Large Scale Orbital Construction", -1167),   # <-- anchor
 ("largeStationControl", "Large Station Attitude Control", -1167),
 ("hydrolox1998", "1998-2003 Hydrolox Engines", -1167),
 ("FRSC1998", "1998-2008 FRSC Engines", -1167),
 ("orbitalRocketry1998", "1998-2003 Orbital Rocketry", -1167),
 ("stagedCombustion1998", "1998-2003 ORSC Engines", -1167),
 ("solids1998", "1998-2008 Solid Rocket Engines", -1167),
 ("elecPropulsion1998", "1998-2008 Electric Propulsion", -1167),
 ("advancedNuclearPropulsion", "Advanced Nuclear Propulsion", -1167),
 ("advancedLifeSupport", "Advanced Life Support and ISRU", -1167),
 ("advancedNuclearPower", "Advanced Nuclear Power Generation", -1167),
 ("advancedPower", "Advanced Power Generation and Storage", -1167),
 ("efficientComms", "Efficient Communications", -1167),
 ("internationalAvionics", "International Era Avionics and Probes", -1167),
 ("advancedScience", "Advanced Science Experiments", -1167),
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
md = ["# Modular Stations, Rovers & ISS Assembly Milestone Partlist (extracted from RP-1 @ rp1_expanded)\n",
      "The batch after `space-stations-shuttle-partlist.md`. **Anchor = `largeScaleOrbitalCon`",
      "(\"Large Scale Orbital Construction\", tree x=-1167).** Node set = every RP-1 tree node in",
      "x=-1507..-1167 (the five tree columns immediately after the space-stations-shuttle batch's",
      "cutoff), ordered by tree x (progression). Key milestone = **modular stations, robotic",
      "exploration & ISS assembly** (Mir: `modularSpaceStations`; Sojourner/Pathfinder/Huygens/",
      "Stardust-era probes: `interplanetaryRovers`; ISS assembly begins: `largeScaleOrbitalCon`,",
      "`largeStationControl`).\n",
      "✓=curated (in manifest), ✗=uncurated, ⟳=already in a prior partlist. Upgrade tag = our disposition.",
      "Excludes ORPHANS/orphanParts (Non-RP-1 catch-all) and ModularLaunchPads.\n",
      "Source: `C:\\git\\ksp_rp1_expanded` ConfigCache. Generated by tools/extract_modular_stations_rovers_partlist.py.\n"]
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
