#!/usr/bin/env python3
"""Extract the parts + upgrades RP-1 places at the 'colonization scaffold' milestone nodes, from the
rp1_expanded ConfigCache, cross-referenced against our curated manifest.

Node set (user's x-axis method, 2026-07-06): the eighth and final milestone batch, picking up
immediately where `iss-commercial-reusable-partlist` left off (anchor `advancedHabitats`, x=-402).
Take every RP-1 tree node in x=-232..-62 (the last four tree columns; x=-62 is the tree's absolute
maximum x — the literal end of RP0TechTree.cfg), ordered by tree x (progression). Anchor =
`colonization2150Science` ("2150+ Science", the last node in the tree).

**This is NOT a real milestone batch like the prior seven — it's RP-1's post-2051 "Colonization Era"
scaffolding, and it is almost entirely EMPTY.** RP-1 stops modeling real hardware once the tree
reaches the present day (confirmed by `iss-commercial-reusable-partlist`'s density collapse past
x=-742); everything from x=-232 onward exists only as bare tech-gate nodes (`colonization2051*`,
`colonization2100*`, `colonization2150*` — Flight/Spaceplanes/Command/Control/EDL/Hydrolox/FRSC/
Orbital/Staged/Solid/ElecProp/NuclearProp/LifeSupport/NuclearPower/Power/Comms/Avionics/Science ×3
generations), with no curated parts assigned. The lone exception is `largeScaleHabitats` (x=-147,
6 parts, all curated — SSPX 9m centrifuge/dome habitat modules) which is real content RP-1 placed
here. Per `docs/RESTART.md` (P6 — "author gap-fill configs... finalize mod set"), this is where AXE's
own authored content has to take over — there is no more RP-1 hardware left to port past this point.
Excludes ORPHANS/orphanParts and ModularLaunchPads (per prior batches, though neither applies here)."""
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
        os.path.join(REPO, "manifest", "modular-stations-rovers-partlist.tsv"),
        os.path.join(REPO, "manifest", "iss-commercial-reusable-partlist.tsv")]
OUT_TSV = os.path.join(REPO, "manifest", "colonization-scaffold-partlist.tsv")
OUT_MD  = os.path.join(REPO, "manifest", "colonization-scaffold-partlist.md")

# (id, title, x) ordered by x ascending = progression. Auto-derived from RP0TechTree.cfg
# (all nodes with -232 <= x <= -62 — the last four tree columns); titles verified against the tree.
NODES = [
 ("materialsScienceColonization", "Colonization Era Materials Science", -232),
 ("electronicsColonization", "Colonization Era Electronics Research", -232),
 ("colonization2051Flight", "2051-2099 Regular Flight", -147),
 ("sstoSpaceplanes", "SSTO Spaceplanes", -147),
 ("highTechCapsules", "High-Tech Capsules", -147),
 ("largeScaleHabitats", "Large Scale Habitats", -147),
 ("colonization2051Control", "2051-2099 Control", -147),
 ("colonization2051EDL", "2051-2099 EDL", -147),
 ("colonization2051Hydrolox", "2051-2099 Hydrolox Engines", -147),
 ("colonization2051FRSC", "2051-2099 FRSC Engines", -147),
 ("colonization2051Orbital", "2051-2099 Orbital Rocketry", -147),
 ("colonization2051Staged", "2051-2099 ORSC", -147),
 ("colonization2051Solid", "2051-2099 Solids", -147),
 ("colonization2051ElecProp", "2051-2099 Electric Propulsion", -147),
 ("colonization2051NuclearProp", "2051-2099 Nuclear Propulsion", -147),
 ("colonization2051LifeSupport", "2051-2099 Life Support and ISRU", -147),
 ("colonization2051NuclearPower", "2051-2099 Nuclear Power", -147),
 ("colonization2051Power", "2051-2099 Power Generation and Storage", -147),
 ("colonization2051Comms", "2051-2099 Communications", -147),
 ("colonization2051Avionics", "2051-2099 Avionics and Probes", -147),
 ("colonization2051Science", "2051-2099 Science", -147),
 ("colonization2100Flight", "2100-2149 Regular Flight", -105),
 ("colonization2100Spaceplanes", "2100-2149 Spaceplanes", -105),
 ("colonization2100Command", "2100-2149 Command Modules", -105),
 ("colonization2100SpaceStations", "2100-2149 Space Stations", -105),
 ("colonization2100Control", "2100-2149 Control", -105),
 ("colonization2100EDL", "2100-2149 EDL", -105),
 ("colonization2100Hydrolox", "2100-2149  Hydrolox Engines", -105),
 ("colonization2100FRSC", "2100-2149 FRSC Engines", -105),
 ("colonization2100Orbital", "2100-2149  Orbital Rocketry", -105),
 ("colonization2100Staged", "2100-2149  ORSC", -105),
 ("colonization2100Solid", "2100-2149 Solids", -105),
 ("colonization2100ElecProp", "2100-2149 Electric Propulsion", -105),
 ("colonization2100NuclearProp", "2100-2149 Nuclear Propulsion", -105),
 ("colonization2100LifeSupport", "2100-2149 Life Support and ISRU", -105),
 ("colonization2100NuclearPower", "2100-2149 Nuclear Power", -105),
 ("colonization2100Power", "2100-2149 Power Generation and Storage", -105),
 ("colonization2100Comms", "2100-2149 Communications", -105),
 ("colonization2100Avionics", "2100-2149 Avionics and Probes", -105),
 ("colonization2100Science", "2100-2149 Science", -105),
 ("colonization2150Flight", "2150+ Regular Flight", -62),
 ("colonization2150Spaceplanes", "2150+ Spaceplanes", -62),
 ("colonization2150Command", "2150+ Command Modules", -62),
 ("colonization2150SpaceStations", "2150+ Space Stations", -62),
 ("colonization2150Control", "2150+ Control", -62),
 ("colonization2150EDL", "2150+ EDL", -62),
 ("colonization2150Hydrolox", "2150+  Hydrolox Engines", -62),
 ("colonization2150FRSC", "2150+ FRSC Engines", -62),
 ("colonization2150Orbital", "2150+  Orbital Rocketry", -62),
 ("colonization2150Staged", "2150+  ORSC", -62),
 ("colonization2150Solid", "2150+ Solids", -62),
 ("colonization2150ElecProp", "2150+ Electric Propulsion", -62),
 ("colonization2150NuclearProp", "2150+ Nuclear Propulsion", -62),
 ("colonization2150LifeSupport", "2150+ Life Support and ISRU", -62),
 ("colonization2150NuclearPower", "2150+ Nuclear Power", -62),
 ("colonization2150Power", "2150+ Power Generation and Storage", -62),
 ("colonization2150Comms", "2150+ Communications", -62),
 ("colonization2150Avionics", "2150+ Avionics and Probes", -62),
 ("colonization2150Science", "2150+ Science", -62),   # <-- anchor (last node in the tree)
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
md = ["# Colonization Scaffold Milestone Partlist (extracted from RP-1 @ rp1_expanded)\n",
      "The eighth and final batch, after `iss-commercial-reusable-partlist.md`. **Anchor =",
      "`colonization2150Science` (\"2150+ Science\", tree x=-62 — the last node in RP0TechTree.cfg).**",
      "Node set = every RP-1 tree node in x=-232..-62 (the four tree columns after the",
      "iss-commercial-reusable batch's cutoff), ordered by tree x (progression).\n",
      "**This is not a real milestone like the prior seven batches — it's RP-1's post-2051",
      "\"Colonization Era\" scaffolding, almost entirely empty.** RP-1 stops modeling real hardware once",
      "the tree reaches the present day; everything here is bare tech-gate nodes with no parts, except",
      "`largeScaleHabitats` (6 curated SSPX 9m centrifuge/dome habitat parts). Per `docs/RESTART.md`",
      "(P6), this is where AXE's own gap-fill authoring has to take over — no more RP-1 hardware is",
      "left to port past this point.\n",
      "✓=curated (in manifest), ✗=uncurated, ⟳=already in a prior partlist. Upgrade tag = our disposition.",
      "Excludes ORPHANS/orphanParts (Non-RP-1 catch-all) and ModularLaunchPads.\n",
      "Source: `C:\\git\\ksp_rp1_expanded` ConfigCache. Generated by tools/extract_colonization_scaffold_partlist.py.\n"]
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
