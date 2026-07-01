#!/usr/bin/env python3
"""Extract the parts + upgrades RP-1 places at the 'moon-landing probes + interplanetary flyby probes'
milestone nodes, from the rp1_expanded ConfigCache, cross-referenced against our curated manifest.

Node set (user-confirmed 2026-07-01): every RP-1 node at/behind the 'Interplanetary Era Science' column
(scienceAdvCapsules, pos.x = -2612) that was NOT already pulled in first-orbit-partlist.md /
human-orbital-partlist.md, PLUS the three -2442 spillover nodes that carry the Luna-9/Surveyor
soft-landing hardware. Ordered by tree x (progression order). See PROGRAMS.md / the tree x-axis method."""
import os, collections

CC = r"C:\git\ksp_rp1_expanded\GameData\ModuleManager.ConfigCache"
REPO = r"C:\git\ksp\RP-AXE"
CURATED = os.path.join(REPO, "manifest", "curated-parts.tsv")
UPGRADES = os.path.join(REPO, "manifest", "upgrades-curated.tsv")
PREV = [os.path.join(REPO, "manifest", "first-orbit-partlist.tsv"),
        os.path.join(REPO, "manifest", "human-orbital-partlist.tsv")]
OUT_TSV = os.path.join(REPO, "manifest", "interplanetary-lunar-probes-partlist.tsv")
OUT_MD  = os.path.join(REPO, "manifest", "interplanetary-lunar-probes-partlist.md")

# (id, title, x) ordered by x ascending = progression. Titles/x verified against RP0TechTree.cfg.
NODES = [
 ("solids1958", "1958 Solid Rocket Engines", -3292),
 ("firstStagedCombustion", "First ORSC Engines", -2952),
 ("firstRTG", "First RTGs", -2952),
 ("earlyPower", "Early Power Generation and Storage", -2952),
 ("scienceHuman", "Early Human Spaceflight Era Science", -2952),
 ("interplanetaryProbes", "Early Interplanetary Avionics and Probes", -2952),
 ("interplanetaryComms", "Interplanetary Communications", -2952),
 ("prototypeHydrolox", "Prototype Hydrolox Engines", -2867),
 ("orbitalRocketry1962", "1962 Orbital Rocketry", -2867),
 ("solids1962", "1962-1963 Solid Rocket Engines", -2867),
 ("improvedAvionics", "Improved Avionics", -2867),
 ("earlyHydrolox", "Early Hydrolox Engines", -2782),
 ("stagedCombustion1963", "1963 ORSC Engines", -2782),
 ("orbitalRocketry1963", "1963 Orbital Rocketry", -2782),
 ("basicPower", "Basic Power Generation and Storage", -2782),
 ("earlyRTG", "Early RTGs", -2782),
 ("improvedFlightControl", "Improved Flight Control", -2782),
 ("electronicsAdvCapsules", "Advanced Capsules Era Electronics Research", -2697),
 ("materialsScienceAdvCapsules", "Advanced Capsules Era Materials Science", -2697),
 ("scienceAdvCapsules", "Interplanetary Era Science", -2612),
 ("matureAvionics", "Mature Avionics and Probes", -2612),
 ("improvedComms", "Improved Communications", -2612),
 ("improvedPower", "Improved Power Generation and Storage", -2612),
 ("orbitalRocketry1964", "1964 Orbital Rocketry", -2612),
 ("solids1964", "1964-1965 Solid Rocket Engines", -2612),
 ("advancedJetEngines", "Advanced Jet Engines", -2612),
 ("earlyDocking", "Early Docking Procedures", -2612),
 ("earlyLanding", "Early Landing", -2612),
 ("earlyLifeSupport", "Early Life Support and ISRU", -2612),
 ("secondGenCapsules", "Second Generation Capsules", -2612),
 # -2442 spillover: completes the Luna-9 / Surveyor soft-lander (moon-landing probe milestone)
 ("lunarRatedHeatshields", "Lunar Rated Heatshields", -2442),
 ("solids1966", "1966 Solid Rocket Engines", -2442),
 ("orbitalRocketry1966", "1966 Orbital Rocketry", -2442),
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
md = ["# Interplanetary-Flyby + Moon-Landing Probes Milestone Partlist (extracted from RP-1 @ rp1_expanded)\n",
      "The next batch after `human-orbital-partlist.md`. Node set = every RP-1 node at/behind the",
      "'Interplanetary Era Science' column (`scienceAdvCapsules`, tree x=-2612) not already pulled, plus the",
      "three x=-2442 spillover nodes that carry the Luna-9/Surveyor soft-lander. Ordered by tree x (progression).",
      "✓=curated (in manifest), ✗=uncurated, ⟳=already in a prior partlist. Upgrade tag = our disposition.\n",
      "Source: `C:\\git\\ksp_rp1_expanded` ConfigCache. Generated by tools/extract_interplanetary_lunar_partlist.py.\n"]
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
