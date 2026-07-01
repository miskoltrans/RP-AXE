# RP-AXE Tech Tree — Architecture & Handoff (P1 done, P2 pivoting)

SSOT for the tree work. Read with [`RESTART.md`](RESTART.md) (roadmap) + [`SCIENCE.md`](SCIENCE.md) (budget).
**TL;DR:** the tree architecture (nodes + flavour + disciplines) is DONE and good — **do not rebuild it.**
The *part-placement methodology* is being reset. Three open problems below.

---

## 1. STATUS

- **P1 — tree architecture: DONE.** `tree/nodes.yaml` (~238 nodes) + `tree/disciplines.yaml` (19 lanes),
  research-paper node names, scatter-by-difficulty homing, convergence web, front-loaded cost ~310–335k
  (≈ SCIENCE.md target at scalar 1.0). Compiles clean via `tools/build_tree.py`. **This is the keeper.**
- **P2 — part placement: FIRST PASS DONE but METHODOLOGY REJECTED.** Auto-placement homed all 1820 parts
  + 553 upgrades (0 orphans) but the result is lumpy + 181 empty nodes. **Auto-placing all 1820 does not
  work for this part set** (see §3A). Pivot required.
- **Open design gaps:** (B) two tree entries (rocketry + x-plane) not built; (C) line clutter too high.

---

## 2. THE ARCHITECTURE (P1 — keep, don't redo)

**Core inversion:** a **discipline** is a field of applied science you fund; **nodes** are real *breakthroughs*
within it; **parts/upgrades are scattered outcomes**, homed at the breakthrough that enabled them. NOT
vehicle-function/era lanes (that's RP-1/ETT).

- **19 lanes** = 18 science disciplines + a **Systems Integration** convergence lane (vehicles-as-convergence
  nodes: capsule, probe bus, lunar lander, station, reusable booster, observatory, nuclear cruiser…; also the
  home for integrated composite parts). Disciplines: Metallurgy · Composite Materials · Propellant Chemistry ·
  Resource Engineering · Cryogenics · Thermodynamics · Fluid Dynamics · Electrical Power · Nuclear Engineering ·
  Aerodynamics · Structures & Mechanisms · Robotics · Microelectronics · Computing · Guidance & Control ·
  Telecommunications · Optics & Photonics · Life Support.
- **Homing rule = SCATTER BY DIFFICULTY:** a part lives at its *signature breakthrough* (the bottleneck), NOT
  its fuel/function. F-1→Fluid Dynamics (combustion instability), RD-170→Metallurgy (ox-rich superalloys),
  J-2→Cryogenics, hypergolic→Prop Chem. Convergence PARENTS carry the other enabling breakthroughs.
- **Naming rule:** node names the ENABLING BREAKTHROUGH, not the artifact ("Stellar Attitude Determination",
  not "Star Trackers"). Bare device names are artifacts — allowed only when *qualified by the innovation*
  (Inducer-Stabilized Turbopumps, Alkaline Fuel Cells) or a canonical field (GN&C). Research-paper grade,
  nerdy + accurate (education pillar). See memory [[clean-group-names-no-x-and-y]].
- **PARENT rule:** convergence parents = *limiting* breakthroughs only, not routine consumed inputs (drop
  kerosene→F-1; keep cryogen-liquefaction→hydrolox). `anyToUnlock=False` = convergence (ALL parents);
  `True` = multi-entry (ANY). Node payload = `unlocks:{parts, upgrades}`.
- **Tiers 0–10, cost front-loaded** (`meta.tier_cost * scalar`; peak T5–7). Scalar is the P3 balance dial.
- **Parked:** fuel-as-usability-gate (Prop-Chem ladder = fuel timeline; engine usable only when its fuel tier
  is reached; same plugin family as the VISION probe checklist; post-MVP). See RESTART parked ideas.

### Pipeline (compile-from-source)
`tree/nodes.yaml` + `tree/disciplines.yaml` → **`tools/build_tree.py`** →
1. `GameData/RP-AXE/design/Tree/AxeTechTree.cfg` — game form (`@TechTree:FOR[ZZZZZ-AXE-Tree]{ !RDNode,*{} … }`).
2. `AxeTechTree.editor.cfg` — plain `TechTree{}` for the editor (opens without KSP).
3. `AxePartPlacement.cfg` — `@PART{%TechRequired}` / `@PARTUPGRADE{%techRequired}` (how parts attach in-game).
4. `tree/render/axe-tree.{svg,png}` (graphviz) + `axe-tree.html` (interactive: click node → its parts).

`build_tree.py` also: validates (unique ids / known disc / parents exist / no cycles); `validate_design()`
non-fatal checks (unreachable, non-forward edge, no-op anyToUnlock, stray roots — **caught several flat-tier
bugs**); `delta_layout()` = barycenter/Sugiyama layered layout (tier=column); merges the placement TSVs into
node unlocks (inline `parts:` seeds win as hand overrides).

### Editor
`linuxgurugamer/ksp-techtree-edit` cloned at `C:\git\ksp\ksp-techtree-edit`, **built** =
`...\bin\Release\KSP Tech Tree Editor v0.5.exe` (v0.5.4; both csprojs retargeted to net48 — LOCAL
uncommitted edits, reapply if reset). Reads `AxeTechTree.editor.cfg`. Layout geometry decided = **delta**
(bake-off in `tree/render/layouts/`; lanes vs pinwheel vs delta vs force). graphviz text exporters (`-Tplain`)
are dead on this box (missing core plugin); only `-Tpng/-Tsvg` work → delta layout is computed pure-Python.

---

## 3. THE THREE OPEN PROBLEMS (what the fresh session tackles)

### A. PLACEMENT PIVOT — auto-placing all 1820 parts does not work
**Why it fails:** RP-1 dumps ~460 parts at `start` (no era signal to tier on); the set is variant-heavy (241
ROEngines w/ configs, 233 ModularLaunchPads, 172 ROCapsules — near-duplicates, not distinct breakthroughs);
scatter-by-difficulty needs a *per-part judgment* ("what made THIS engine hard") that no heuristic derives
(~73% of parts are the judgment kind). Result: lumps (139 hypergolics / 132 structures on one node) + 181/238
empty nodes + endless overrides. **The mismatch is 1:1 placement of the whole variant-mass, not the tree.**

**Proposed new direction (aligns with VISION: "procedural is the workhorse; cut filler variants; iconic parts
earn their place"):**
1. **Home only the ICONIC/representative parts** (the few hundred that teach a design or carry an aha), placed
   thoughtfully — mostly by hand via the cluster review.
2. **Procedural + upgrades carry the bulk** — procedural tanks/structures unlock at capability nodes; engine
   variants ride their config-upgrades (already wired: upgrade→its engine's node).
3. **Off-tree / cut the non-tech mass** — launchpads (233 MLP), ground support, uncurated → `experimental`
   node (already done) or cut.
4. **Likely implies re-curating the manifest** (is 1820 too many? cut variants) — a T1 revisit, OR keep the
   manifest but only PLACE the iconic subset on-tree. **Decide this with the user first.**
- Keep the *useful* placement tooling (`cluster_parts.py` review families; `extract_capability.py` thrust/Isp;
  the capability-ladder idea for engines — that part worked). Discard the "auto-route everything" ambition.

### B. TWO TREE ENTRIES (rocketry + x-plane) — not built
Design requirement from VISION ("choose x-plane or rocket start"). Currently everything roots from a single
`start` node. Fix = structural edit: create **two roots** (e.g. `start_rocketry`, `start_xplane`), reparent the
early Propellant-Chemistry/Fluid-Dynamics lanes under rocketry and the early Aerodynamics lane under x-plane,
converging at first-orbital-capability. Soft fork (both reachable; science scarcity enforces commitment). ~20 min.

### C. LINE CLUTTER — convergence web too dense
The convergence pass raised cross-discipline edges 11→35 (great for the VISION web) but the render/editor read
as cluttered. Transitive-reduction check found **0 redundant edges** (every line is real gating), so decluttering
= relaxing genuine convergences (done a little: dropped 3 weak servo/comms edges) OR better layout. Options for
the fresh session: relax more low-value convergences; tune the delta layout spacing/edge-routing; or accept
density. SystemsIntegration lane was re-ordered to mid-lane (order 12) to shorten its cross-links (~28% less edge
length) — a layout lever that helped.

---

## 4. TOOLING INVENTORY (`tools/`)
- **`build_tree.py`** — the compiler (§2). The one that matters.
- `tree_inventory.py` → `manifest/part-capabilities.tsv` — per-part modules/propellants/category/RP-1-tech +
  coarse discipline classification (the inverse rubric: derive nodes from real parts).
- `extract_capability.py` → `manifest/part-capability.tsv` — peak maxThrust + vac Isp (+ solar rate) from the
  cache (450 engines). Drives capability spread. **Keep.**
- `place_parts.py` → `part-placement.tsv` + `upgrade-placement.tsv` — the auto-router being pivoted. Engine
  capability-ladder logic (`engine_node()`) worked; the "route everything" is the part to reconsider.
- `cluster_parts.py` → `manifest/clusters/*.tsv` — groups placed parts into review families. **Keep** (the
  review surface for hand-placing the iconic set).
- `node_density.py` — dense-pile vs empty-node report by discipline.
- `tree_layouts.py` → `tree/render/layouts/compare.html` — the geometry bake-off (delta won).
- `manifest/part-overrides.tsv` — hand placement overrides (28 engine notables). Extend for iconic placement.

## 5. KEY FILES
- `tree/nodes.yaml`, `tree/disciplines.yaml` — the tree source (KEEP).
- `GameData/RP-AXE/design/Tree/AxeTechTree.cfg` / `.editor.cfg` / `AxePartPlacement.cfg` — generated.
- `manifest/curated-parts.tsv` (1820), `upgrades-curated.tsv` (553 KEEP), `part-capabilities.tsv`,
  `part-capability.tsv`, `part-placement.tsv`, `upgrade-placement.tsv`, `part-overrides.tsv`, `clusters/`.

## 6. COMMIT TRAIL (branch `restart`)
Tree stages: `920984f`→`f97646b`→`1154f78`→`9768884` (full 219-node tree) → `3324965` (convergence + Systems
Integration lane) → naming passes (`72cbd2a`, `e0a73d4`, `67eee0f`) → `62a4071` (declutter) → wiring
(`c6551b4` delta+validator, `3906041` placement→viewer). P2: `58fbfc8` (complete first-pass placement),
`e462e17` (engine capability spread), `ad13be5` (solar spread). **All committed — nothing lost on a context reset.**

## 7. SETTLED DECISIONS (do not re-litigate)
18 disciplines (+Integration) · scatter-by-difficulty · research-paper names (breakthrough not artifact) ·
convergence parents = limiting only · compile-from-YAML pipeline · delta layout · lgg editor · ~300k cost /
scalar-tuned at P3 · experimental off-tree catch-all · fuel-as-usability-gate parked · engines spread by
capability (thrust/Isp) where data exists.
