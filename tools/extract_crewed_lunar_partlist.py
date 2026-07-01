#!/usr/bin/env python3
"""Extract the parts + upgrades RP-1 places at the 'crewed lunar landing' milestone nodes, from the
rp1_expanded ConfigCache, cross-referenced against our curated manifest.

Node set (user's x-axis method, 2026-07-01): anchor = `improvedLandingEngines` ("Improved Landing
Engines", pos.x = -2017). Take EVERY RP-1 tree node at/behind the anchor column (x <= -2017) that was
NOT already pulled by the three prior milestone batches (first-orbit / human-orbital /
interplanetary-lunar-probes partlists). Ordered by tree x (progression order).

Key milestone = the CREWED LUNAR LANDING (Apollo: lunarLanding LM, improvedLandingEngines LMDE,
lunarOrbiterCapsules, matureCapsules, dockingCrewTransfer, largeHydrolox/J-2). Alternative goal =
DEEP SPACE EXPLORATION (nuclearFissionReactors, prototypeNuclearPropulsion/NERVA, space stations,
lifeSupportISRU, surfaceScience) + the parallel spaceplane track (prototype/effectiveSpaceplanes,
efficientSupersonic). Both fall under the single x<=-2017 cutoff. See the tree x-axis method in
rp-axe-partlist-batches memory / PROGRAMS.md. Excludes ORPHANS/orphanParts (the Non-RP-1 catch-all
bucket, x=-3810, not a milestone) and ModularLaunchPads (launch-pad bloat, inserted separately)."""
import os, collections

CC = r"C:\git\ksp_rp1_expanded\GameData\ModuleManager.ConfigCache"
REPO = r"C:\git\ksp\RP-AXE"
CURATED = os.path.join(REPO, "manifest", "curated-parts.tsv")
UPGRADES = os.path.join(REPO, "manifest", "upgrades-curated.tsv")
PREV = [os.path.join(REPO, "manifest", "first-orbit-partlist.tsv"),
        os.path.join(REPO, "manifest", "human-orbital-partlist.tsv"),
        os.path.join(REPO, "manifest", "interplanetary-lunar-probes-partlist.tsv")]
OUT_TSV = os.path.join(REPO, "manifest", "crewed-lunar-landing-partlist.tsv")
OUT_MD  = os.path.join(REPO, "manifest", "crewed-lunar-landing-partlist.md")

# (id, title, x) ordered by x ascending = progression. Auto-derived from RP0TechTree.cfg
# (all x<=-2017 nodes minus the 73 already pulled + the 2 orphan buckets); titles verified against the tree.
NODES = [
 ("electronicsLunar", "Lunar Exploration Era Electronics Research", -2537),
 ("materialsScienceLunar", "Lunar Exploration Era Materials Science", -2537),
 ("nuclearFissionReactors", "Small Nuclear Fission Reactors", -2527),
 ("orbitalRocketry1965", "1965 Orbital Rocketry", -2527),
 ("prototypeSpaceplanes", "Prototype Spaceplanes", -2527),
 ("stagedCombustion1965", "1965 ORSC Engines", -2527),
 ("improvedHydrolox", "Improved Hydrolox Engines", -2442),
 ("stagedCombustion1966", "1966 ORSC Engines", -2442),
 ("lunarOrbiterCapsules", "Lunar Orbiter Capsules", -2415),
 ("dockingCrewTransfer", "Docking and Crew Transfer", -2357),
 ("advancedComms", "Advanced Communications", -2272),
 ("improvedRTG", "Improved RTGs", -2272),
 ("largeHydrolox", "Large Hydrolox Engines", -2272),
 ("largeScaleAvionics", "Large Scale Avionics", -2272),
 ("lifeSupportISRU", "Life Support and ISRU", -2272),
 ("lunarRatedPower", "Lunar Rated Power Generation", -2272),
 ("matureCapsules", "Mature Capsules", -2272),
 ("orbitalRocketry1967", "1967 Orbital Rocketry", -2272),
 ("prototypeNuclearPropulsion", "Prototype Nuclear Propulsion", -2272),
 ("scienceLunar", "Lunar Exploration Era Science", -2272),
 ("solids1967", "1967-1968 Solid Rocket Engines", -2272),
 ("spaceStationPrototypes", "Space Station Prototypes", -2272),
 ("stagedCombustion1967", "1967 ORSC Engines", -2272),
 ("hydrolox1968", "1968 Hydrolox Engines", -2187),
 ("lunarLanding", "Lunar Landing", -2187),
 ("orbitalRocketry1968", "1968 Orbital Rocketry", -2187),
 ("stagedCombustion1968", "1968 ORSC Engines", -2187),
 ("hydrolox1969", "1969 Hydrolox Engines", -2102),
 ("orbitalRocketry1969", "1969 Orbital Rocketry", -2102),
 ("solids1969", "1969-1971 Solid Rocket Engines", -2102),
 ("stagedCombustion1969", "1969 ORSC Engines", -2102),
 ("surfaceScience", "Surface Science", -2102),
 ("effectiveSpaceplanes", "Effective Spaceplanes", -2017),
 ("efficientSupersonic", "Efficient Supersonic Engines", -2017),
 ("improvedLandingEngines", "Improved Landing Engines", -2017),   # <-- anchor
 ("orbitalRocketry1970", "1970-1971 Orbital Rocketry", -2017),
 ("spaceStationDev", "Space Station Development", -2017),
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
md = ["# Crewed Lunar Landing Milestone Partlist (extracted from RP-1 @ rp1_expanded)\n",
      "The batch after `interplanetary-lunar-probes-partlist.md`. **Anchor = `improvedLandingEngines`",
      "(\"Improved Landing Engines\", tree x=-2017).** Node set = every RP-1 tree node at/behind the anchor",
      "column (x <= -2017) NOT already pulled by the three prior batches (first-orbit / human-orbital /",
      "interplanetary-lunar-probes), ordered by tree x (progression). Key milestone = the **crewed lunar",
      "landing** (Apollo LM/CSM: `lunarLanding`, `improvedLandingEngines`, `lunarOrbiterCapsules`,",
      "`matureCapsules`, `dockingCrewTransfer`, `largeHydrolox`). Alternative goal = **deep space",
      "exploration** (`nuclearFissionReactors`, `prototypeNuclearPropulsion`/NERVA, space stations,",
      "`lifeSupportISRU`, `surfaceScience`) + the parallel spaceplane track.\n",
      "✓=curated (in manifest), ✗=uncurated, ⟳=already in a prior partlist. Upgrade tag = our disposition.",
      "Excludes ORPHANS/orphanParts (Non-RP-1 catch-all) and ModularLaunchPads.\n",
      "Source: `C:\\git\\ksp_rp1_expanded` ConfigCache. Generated by tools/extract_crewed_lunar_partlist.py.\n"]
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
