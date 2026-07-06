#!/usr/bin/env python3
"""Extract the parts + upgrades RP-1 places at the 'ISS completion -> commercial/reusable era'
milestone nodes, from the rp1_expanded ConfigCache, cross-referenced against our curated manifest.

Node set (user's x-axis method, 2026-07-06): the seventh milestone batch, picking up immediately
where `modular-stations-rovers-partlist` left off (anchor `largeScaleOrbitalCon`, x=-1167). Take
every RP-1 tree node in x=-1082..-402 (the next eight tree columns), ordered by tree x (progression).
Anchor = `advancedHabitats` ("Advanced Habitats", the last/most-advanced column in this batch that
still carries curated parts, x=-402 — the rest of that column is generic "Near Future" (NF) gate
nodes, mostly empty, marking where RP-1's real-hardware modeling tapers off).

Key milestone = ISS COMPLETION -> COMMERCIAL/REUSABLE SPACEFLIGHT (ISS assembly wraps up:
`improvedOrbitalConstruction`, `largeRoverDesigns`; grid fins & booster reuse: `gridFins`,
`reusability`; Commercial Crew: `commercialCapsules` (CST-100/Orion); BEAM-style habitats:
`inflatableHabitats`, `improvedHabitats`, `advancedHabitats`). Density drops off sharply after
x=-742 — real hardware modeling thins fast as the tree approaches the present day. Excludes
ORPHANS/orphanParts and ModularLaunchPads (per prior batches)."""
import os, collections

CC = r"C:\git\ksp\ksp_rp1_expanded\GameData\ModuleManager.ConfigCache"
REPO = r"C:\git\ksp\RP-AXE"
CURATED = os.path.join(REPO, "manifest", "curated-parts.tsv")
UPGRADES = os.path.join(REPO, "manifest", "upgrades-curated.tsv")
PREV = [os.path.join(REPO, "manifest", "first-orbit-partlist.tsv"),
        os.path.join(REPO, "manifest", "human-orbital-partlist.tsv"),
        os.path.join(REPO, "manifest", "interplanetary-lunar-probes-partlist.tsv"),
        os.path.join(REPO, "manifest", "crewed-lunar-landing-partlist.tsv"),
        os.path.join(REPO, "manifest", "space-stations-shuttle-partlist.tsv"),
        os.path.join(REPO, "manifest", "modular-stations-rovers-partlist.tsv")]
OUT_TSV = os.path.join(REPO, "manifest", "iss-commercial-reusable-partlist.tsv")
OUT_MD  = os.path.join(REPO, "manifest", "iss-commercial-reusable-partlist.md")

# (id, title, x) ordered by x ascending = progression. Auto-derived from RP0TechTree.cfg
# (all nodes with -1082 <= x <= -402); titles verified against the tree.
NODES = [
 ("improvedOrbitalConstruction", "Improved Orbital Construction", -1082),
 ("largeDockingPorts", "Large Docking Ports", -1082),
 ("largeRoverDesigns", "Large Rover Designs", -1082),
 ("hydrolox2004", "2004-2008 Hydrolox Engines", -1082),
 ("orbitalRocketry2004", "2004-2008 Orbital Rocketry", -1082),
 ("stagedCombustion2004", "2004-2008 ORSC Engines", -1082),
 ("materialsScienceCommercial", "Commercial Spaceflight Era Materials Science", -997),
 ("electronicsCommercial", "Commercial Spaceflight Era Electronics Research", -997),
 ("advancedTurbofans", "Advanced Turbofans", -912),
 ("highTechSpaceplanes", "High-Tech Spaceplanes", -912),
 ("modernCapsules", "Modern Capsules", -912),
 ("gridFins", "Grid Fins", -912),
 ("reusability", "Reusability", -912),
 ("hydrolox2009", "2009-2013 Hydrolox Engines", -912),
 ("FRSC2009", "2009-2013 FRSC Engines", -912),
 ("orbitalRocketry2009", "2009-2013 Orbital Rocketry", -912),
 ("stagedCombustion2009", "2009-2013 ORSC Engines", -912),
 ("solids2009", "2009-2018 Solid Rocket Engines", -912),
 ("elecPropulsion2009", "2009-2018 Electric Propulsion", -912),
 ("efficientNuclearPropulsion", "Efficient Nuclear Propulsion", -912),
 ("efficientLifeSupport", "Efficient Life Support and ISRU", -912),
 ("modernNuclearPower", "Modern Nuclear Power Generation", -912),
 ("modernPower", "Modern Power Generation and Storage", -912),
 ("modernComms", "Modern Communications", -912),
 ("modernAvionics", "Modern Avionics and Probes", -912),
 ("advancedSurfaceScience", "Advanced Surface Experiments", -912),
 ("inflatableHabitats", "Inflatable Habitats", -827),
 ("advancedLanding", "Advanced Landing", -827),
 ("hydrolox2014", "2014-2018 Hydrolox Engines", -827),
 ("FRSC2014", "2014-2018 FRSC Engines", -827),
 ("orbitalRocketry2014", "2014-2018 Orbital Rocketry", -827),
 ("stagedCombustion2014", "2014-2018 ORSC Engines", -827),
 ("materialsScienceMatureCommercial", "Mature Commercial Spaceflight Era Materials Science", -742),
 ("electronicsMatureCommercial", "Mature Commercial Spaceflight Era Electronics Research", -742),
 ("commercialSpaceplanes", "Commercial Spaceplanes", -657),
 ("commercialCapsules", "Commercial Capsules", -657),
 ("improvedHabitats", "Improved Habitats", -657),
 ("reusableControl", "Reusable Attitude Control", -657),
 ("SIAD", "Supersonic Inflatable Aerodynamic Decelerator", -657),
 ("hydrolox2019", "2019-2028 Hydrolox Engines", -657),
 ("FRSC2019", "2019-2028 FRSC Engines", -657),
 ("orbitalRocketry2019", "2019-2028 Orbital Rocketry", -657),
 ("stagedCombustion2019", "2019-2028 ORSC Engines", -657),
 ("solids2019", "2019-2028 Solid Rocket Engines", -657),
 ("elecPropulsion2019", "2019-2028 Electric Propulsion", -657),
 ("nuclearPropulsionNF", "Bimodal Nuclear Propulsion", -657),
 ("commercialLifeSupport", "Commercial Life Support and ISRU", -657),
 ("advModernNuclearPower", "Advanced Modern Nuclear Power Generation", -657),
 ("advModernPower", "Advanced Modern Power Generation and Storage", -657),
 ("advModernComms", "Advanced Modern Communications", -657),
 ("advModernAvionics", "Advanced Modern Avionics and Probes", -657),
 ("advModernScience", "Advanced Modern Science", -657),
 ("materialsScienceNF", "Near Future Era Materials Science", -487),
 ("electronicsNF", "Near Future Era Electronics Research", -487),
 ("experimentalAircraft", "Experimental Aircraft Engines", -402),
 ("experimentalSpaceplanes", "Experimental Spaceplanes", -402),
 ("capsulesNF", "Near Future Capsules", -402),
 ("advancedHabitats", "Advanced Habitats", -402),   # <-- anchor
 ("flightControlNF", "Near Future Flight Control", -402),
 ("HIAD", "Hypersonic Inflatable Aerodynamic Decelerator", -402),
 ("hydroloxNF", "Near Future Hydrolox Engines", -402),
 ("FRSCNF", "Near Future FRSC Engines", -402),
 ("orbitalRocketryNF", "Near Future Orbital Rocketry", -402),
 ("stagedCombustionNF", "Near Future ORSC Engines", -402),
 ("solidsNF", "Near Future Solid Rocket Engines", -402),
 ("elecPropulsionNF", "Near Future Electric Propulsion", -402),
 ("nuclearPropulsionNF2", "Near Future Nuclear Propulsion", -402),
 ("lifeSupportNF", "Near Future Life Support and ISRU", -402),
 ("nuclearPowerNF", "Near Future Nuclear Power Generation", -402),
 ("powerNF", "Near Future Power Generation and Storage", -402),
 ("commsNF", "Near Future Communications", -402),
 ("avionicsNF", "Near Future Avionics and Probes", -402),
 ("scienceNF", "Near Future Science", -402),
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
md = ["# ISS Completion -> Commercial/Reusable Era Milestone Partlist (extracted from RP-1 @ rp1_expanded)\n",
      "The batch after `modular-stations-rovers-partlist.md`. **Anchor = `advancedHabitats`",
      "(\"Advanced Habitats\", tree x=-402 — the last column that still carries curated parts; its",
      "\"NF\" (Near Future) siblings are almost all empty gate nodes).** Node set = every RP-1 tree",
      "node in x=-1082..-402 (the eight tree columns immediately after the modular-stations-rovers",
      "batch's cutoff), ordered by tree x (progression). Key milestone = **ISS completion ->",
      "commercial/reusable spaceflight** (ISS assembly wraps up: `improvedOrbitalConstruction`,",
      "`largeRoverDesigns`; grid fins & booster reuse: `gridFins`, `reusability`; Commercial Crew:",
      "`commercialCapsules` (CST-100/Orion); BEAM-style habitats: `inflatableHabitats`,",
      "`improvedHabitats`, `advancedHabitats`). Density drops off sharply after x=-742 — real",
      "hardware modeling thins fast as the tree approaches the present day.\n",
      "✓=curated (in manifest), ✗=uncurated, ⟳=already in a prior partlist. Upgrade tag = our disposition.",
      "Excludes ORPHANS/orphanParts (Non-RP-1 catch-all) and ModularLaunchPads.\n",
      "Source: `C:\\git\\ksp_rp1_expanded` ConfigCache. Generated by tools/extract_iss_commercial_reusable_partlist.py.\n"]
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
