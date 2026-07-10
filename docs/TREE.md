# RP-AXE Tech Tree — Architecture & Handoff (tree built; P2/P3 realization ongoing)

SSOT for the tree work. Read with [`RESTART.md`](RESTART.md) (roadmap) + [`SCIENCE.md`](SCIENCE.md) (budget).
**TL;DR:** the tree architecture (nodes + flavour + disciplines) is DONE and good — **do not rebuild it.**
It was built out band-by-band to ~217 nodes with all 8 milestone partlists placed (see RESTART.md);
what remains is part-placement realization + economy calibration (P2/P3). §2/§7 (architecture + settled
decisions) are the durable reference; §3 is the record of how the placement approach was resolved.

---

## 1. STATUS

- **P1 — tree architecture: DONE.** `tree/nodes.yaml` (~217 nodes) + `tree/disciplines.yaml` (19 lanes),
  research-paper node names, scatter-by-difficulty homing, convergence web, front-loaded cost ~300k
  (≈ SCIENCE.md target at scalar 1.0). Compiles clean via `tools/build_tree.py`. **This is the keeper.**
- **P2 — part placement: RESOLVED (auto-place-everything abandoned, §3A).** The tree was built out
  band-by-band — band 1 (to orbit) → band 2 (appsats / humans / lunar probes) → band 3 (crewed lunar) —
  hand-homing the iconic parts per milestone while procedural + config-upgrades carry the bulk. **All 8
  milestone partlists are placed** (only RP-1's post-2051 colonization scaffold is deliberately deferred;
  RESTART.md P6). Remaining: realization config + economy calibration (P3).
- **Settled since:** (B) single-root rocketry-default (§3B); (C) convergence relaxed to irreducible
  physics only (§8).

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
2. `AxeTreeMeta.cfg` — `id→{discipline,tier,cost}` + the discipline table, read by the in-game render plugin.
3. `AxePartPlacement.cfg` — `@PART{%TechRequired}` / `@PARTUPGRADE{%techRequired}` (how parts attach in-game).
4. `tree/render/axe-tree.{svg,png}` (graphviz) + `axe-tree.html` (interactive: click node → its parts).

`build_tree.py` also: validates (unique ids / known disc / parents exist / no cycles); `validate_design()`
non-fatal checks (unreachable, non-forward edge, no-op anyToUnlock, stray roots — **caught several flat-tier
bugs**); `delta_layout()` = barycenter/Sugiyama layered layout (tier=column); merges the placement TSVs into
node unlocks (inline `parts:` seeds win as hand overrides).

### Editor — the HTML render (`tree/render/`)
The tree editor/viewer is the **HTML render** emitted by `build_tree.py`, not an external tool:
- `tree/render/prototype/` — the Canvas-2D renderer (`index.html` + `renderer.js` + generated `tree-data.js`):
  discipline bands, lane-routed arrows, fan endpoints, research-state toggles. This is the **canonical editor**
  and the layout/routing design bench (bands vs sugiyama, lane vs stock elbow).
- `tree/render/axe-tree.html` — lightweight click-a-node → its-parts viewer; `axe-tree.{svg,png}` = graphviz
  review render.

Both are **generated snapshots**: edit `tree/nodes.yaml` → `python tools/build_tree.py` → refresh the browser
(no auto-rebuild / no watcher). The same build emits `AxeTreeMeta.cfg`, so the **in-game R&D render** (the AXE
plugin ports this exact layout into KSP — see [`RENDER-PORT.md`](RENDER-PORT.md)) never drifts from the HTML.

> **Sacked:** the old `linuxgurugamer/ksp-techtree-edit` + `AxeTechTree.editor.cfg` path. A standalone editor
> `TechTree{}` shipped in GameData was aggregated by KSP's `GetConfigNodes("TechTree")` and **doubled every
> node in-game** (54 → 108). The HTML render is the editor now; `build_tree.py` no longer emits `.editor.cfg`.

---

## 3. HOW THE OPEN PROBLEMS WERE RESOLVED (record)

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
   manifest but only PLACE the iconic subset on-tree.

**RESOLVED — this is the path taken.** The manifest was kept at 1820, but only the representative/iconic
subset is PLACED on-tree; procedural + config-upgrades carry the bulk and the rest fall to the
`experimental` catch-all. §3A stands as the record of why auto-place-everything was abandoned.
- Keep the *useful* placement tooling (`cluster_parts.py` review families; `extract_capability.py` thrust/Isp;
  the capability-ladder idea for engines — that part worked). Discard the "auto-route everything" ambition.

### B. TWO TREE ENTRIES (rocketry + x-plane) — ✅ SETTLED: single-root rocketry-default (won't build two roots)
VISION mused about a symmetric "choose x-plane or rocket start"; the DECISION (2026-07-01, early-tree review) is
**rocketry is the default and aviation is an opt-in branch off `start`** — this supersedes the symmetric-choice
idea. Aviation is deliberately roleplay/side-content: it is NOT expected to pay for itself in science (its regime
is the SCIENCE.md-zeroed sub-40 km band), and its reward loop is **special x-plane-program contracts** (money, not
science — see RESTART parked ideas), not a tree change. So `start`'s flavor promise of "whether to fly aeroplanes at
all, is yours to choose" stands as-is. No two-root fork.

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
- `build_part_origin.py` → `GameData/RP-AXE/design/Tree/AxePartOrigin.cfg` — tags every installed part's
  description with its source mod (`From <mod>[/<sub-pack>] mod`, green), RP-1 parity. Reads the **live
  Instance ConfigCache** (`Instance/GameData/ModuleManager.ConfigCache`) — not the frozen 1820-part manifest,
  which misses ~500 installed parts (e.g. RN_US_Probes/KH9) — deriving origin from each part's `parentUrl`
  path (root folder + meaningful sub-pack; generic `Parts/` collapses to the mod). Skips parts under
  `RP-AXE/seed` and any part a seed cfg already tags, so RP-1's own tags aren't doubled. Needs a built
  instance (deploy + launch KSP once so the cache exists).
- `tree_inventory.py` → `manifest/part-capabilities.tsv` — per-part modules/propellants/category/RP-1-tech +
  coarse discipline classification (the inverse rubric: derive nodes from real parts).
- `extract_capability.py` → `manifest/part-capability.tsv` — peak maxThrust + vac Isp (+ solar rate) from the
  cache (450 engines). Drives capability spread. **Keep.**
- `place_parts.py` → `part-placement.tsv` + `upgrade-placement.tsv` — the auto-router being pivoted. Engine
  capability-ladder logic (`engine_node()`) worked; the "route everything" is the part to reconsider.
- `cluster_parts.py` → `manifest/clusters/*.tsv` — groups placed parts into review families. **Keep** (the
  review surface for hand-placing the iconic set).
- `node_density.py` — dense-pile vs empty-node report by discipline.
- `tree_layouts.py` — the geometry bake-off that picked delta/bands (concluded; `tree/render/layouts/` pruned).
- `manifest/part-overrides.tsv` — hand placement overrides (28 engine notables). Extend for iconic placement.

## 5. KEY FILES
- `tree/nodes.yaml`, `tree/disciplines.yaml` — the tree source (KEEP).
- `GameData/RP-AXE/design/Tree/AxeTechTree.cfg` / `AxeTreeMeta.cfg` / `AxePartPlacement.cfg` / `AxePartOrigin.cfg` — generated.
- `manifest/curated-parts.tsv` (1820), `upgrades-curated.tsv` (553 KEEP), `part-capabilities.tsv`,
  `part-capability.tsv`, `part-placement.tsv`, `upgrade-placement.tsv`, `part-overrides.tsv`, `clusters/`.

## 6. COMMIT TRAIL (branch `restart`)
Tree stages: `920984f`→`f97646b`→`1154f78`→`9768884` (full 219-node tree) → `3324965` (convergence + Systems
Integration lane) → naming passes (`72cbd2a`, `e0a73d4`, `67eee0f`) → `62a4071` (declutter) → wiring
(`c6551b4` delta+validator, `3906041` placement→viewer). P2: `58fbfc8` (complete first-pass placement),
`e462e17` (engine capability spread), `ad13be5` (solar spread). **All committed — nothing lost on a context reset.**

## 7. SETTLED DECISIONS (do not re-litigate)
18 disciplines (+Integration) · scatter-by-difficulty · research-paper names (breakthrough not artifact) ·
convergence parents = limiting only · compile-from-YAML pipeline · delta/bands layout · HTML-render editor + in-game render port · ~300k cost /
scalar-tuned at P3 · experimental off-tree catch-all · fuel-as-usability-gate parked · engines spread by
capability (thrust/Isp) where data exists · **rocketry-default single-root** (aviation opt-in, rewarded by
x-plane contracts not science; §3B) · **relaxed convergence** (milestone/integration `int_*` nodes gate ONLY
on irreducible physics — this is a what-if sim, so don't hard-gate on route-around-able enablers; §8).

## 8. EARLY-TREE REVIEW PASS (2026-07-01) — applied + open
3-lens review of the to-orbit spine (game-design / vision-fidelity / plausibility; all Opus). Verdict: bones
strong, issues few + concentrated. **Applied to `tree/nodes.yaml`:**
- **Orbital mass-fraction is now multi-entry** (unanimous top finding): new `str_orbitalMassFraction` gate
  (`met_isogrid` ‖ `str_balloonTank`, anyToUnlock) feeds `int_orbitalInsertion`, mirroring `fd_orbitalThrust`.
  Fixes the Atlas-balloon railroad (R-7/Sputnik flew conventional-light, not a balloon) and gives `met_isogrid`
  a critical-path role instead of being an orphan side-grade.
- **`th_regenCooling` → `fd_turbopumpFeed`** (plausibility): the V-2's real breakthrough vs a sounding motor was
  the turbopump breaking the tank-pressure ceiling, not regen cooling (V-2 was film-cooled; ORM-65 in `start` is
  already regen-cooled). Re-homed Thermodynamics→FluidDynamics, matching the early-tree review + library `fd_turbopumps`;
  also resolves the spine/library `th_regenCooling` id collision.
- **Polish:** `met_isogrid` "Chemical Milling"→"Machined Isogrid Stiffening" (isogrid is machined, not etched);
  `aero_afterburner` reparented off `aero_areaRule` @T4 (reheat predates Mach-2 shock inlets); `opt_vidicon`
  →T1 (equal-cost sidegrade to film, was dominated); header multi-entry claim tightened.
- **Relaxed the orbit convergence (what-if principle, user call):** `int_orbitalInsertion` now gates on ONLY the
  irreducible axes — `fd_orbitalThrust` (an engine) + `str_orbitalMassFraction` (a light tank). Dropped `str_staging`
  and `gnc_pitchProgram` as hard parents: "no chemical SSTO exists" is a fact about *our* timeline, not a law, and
  this is a what-if sim — if your engine+tank can single-stage it, the tree must not block you "for no reason."
  Staging/guidance stay expected-but-optional (the probe-style soft checklist is the home for "you'll want X"
  nudges, not tree edges). **General rule for the SystemsIntegration lane:** convergence/milestone nodes gate on
  irreducible physics only; keep their inputs relaxed.
- **Settled (no edit):** aviation-as-roleplay + x-plane contracts (§3B); rocketry-default (§3B).
### 9. ENGINE PASS (in progress — user workflow: get current placements happy → library-sort → re-review → other parts → whole tree)
Step-1 "are we happy with current engine placements" done. **Applied:**
- `fd_verniers` → FluidDynamics @T2 off `fd_turbopumpFeed` (was GuidanceControl @T1 — homed by function, id/tag
  mismatch, tier below the engines it trims), retitled "Vernier Trim Chambers" (commit 2aaa73d).
- `fd_baffledInjector` → "Single Large-Chamber Combustion" — it hosted the tier-2 Western single-chamber boosters
  (LR89/LR79/LR105/X-405/Gamma/Stentor) that didn't use baffles; baffles are the later F-1 node (out of phase).
- **Corrected framing:** the "9 solids / 6 multi-chamber on one node" is NOT a lump — it's correct king+ride-along
  (one breakthrough, many variant outcomes; cost abstracts the rest) per the node philosophy. Engines don't feel
  weak from too-few-nodes; they feel weak from a **flat choice**.
- **DEFERRED (user: "skip now fix later") — engine DIVERGENCE.** The three paths (multi-chamber ‖ single-chamber ‖
  hydrolox) are all T2, same cost, converge identically at `fd_orbitalThrust` → no opportunity cost, pick is
  arbitrary. Decision options worked out (pick later): (a) **cost-differentiated now + divergent successor lines
  later** [recommended] — price paths apart this phase; each roots a distinct mid-game line already in `library.yaml`
  (Soviet→RD-170/Metallurgy, Western→F-1/FluidDyn, hydrolox→J-2/Cryo), built when we extend past orbit; (b) cost dial
  only; (c) inherent-physics only; (d) full divergence now (breaks phase order). This also decides `fd_orbitalThrust`'s
  payload (thin marker if successors carry the uprated configs; else it carries them). Other review leftovers folded
  here: reward-desert part-less `fd_orbitalThrust`/`int_orbitalInsertion`; `mic_massSpec` discipline home.
- **NEXT when resumed:** settle divergence (a–d) → then library-sort the rest of this phase's parts → re-review → whole-tree pass.
