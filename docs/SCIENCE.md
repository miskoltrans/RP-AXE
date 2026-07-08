# RP-AXE — Science Budget & KerbalismLab Audit (T2)

Pre-P1 science measurement (see [`RESTART.md`](RESTART.md) T2). The tree's total cost is
balanced against total collectable science, so we measure the budget **before** setting node
costs. Science splits on **two cross-cutting axes**: by *source system* — RP-1's **RP0\* suite**
(instrument experiments) and **KerbalismLab** (lab/station) — and by *crew requirement* —
**crewed** (needs a Kerbal) vs **uncrewed** (robotic). These are NOT the same cut: the RP0\* suite
is itself ~61% crewed *by experiment count* (60 of 98 — life-sciences, habitats, EVA, crew/TV reports),
though only ~7% by whole-system science *value* since those crewed experiments are Earth/Moon-locked
(§2). This doc measures
the **crewed vs uncrewed** budget — Uncrewed = RP0\* robotic instruments; Crewed = RP0\* crewed
experiments + all of KerbalismLab. (An earlier version wrongly equated "probe science = uncrewed" —
half the RP0\* suite is crewed.)

Reproduce: `python tools/science_budget.py` (RP0\* crewed/uncrewed split) and `python tools/lab_budget.py`
(KerbalismLab). Data artifacts: [`../manifest/experiment-crew.tsv`](../manifest/experiment-crew.tsv)
(crew classification, via `tools/experiment_crew.py`),
[`../manifest/lab-experiments.tsv`](../manifest/lab-experiments.tsv).

> **⚠️ STATUS 2026-07-08 — the RP0\* science WIRING is now SHIPPED (was P3-deferred).** RP-1's actual
> experiment configs are live in the mod, so this doc's budget is no longer only theoretical calibration —
> the experiments now exist and produce science:
> - **Instrument suite** — 16 experiment files + `GlobalExperimentPatches` + `CleanupParts/PartExperimentAdder`
>   + `Results/` vendored verbatim into `GameData/RP-AXE/seed/Science/`. Instruments are **part-gated** (parts
>   already placed via `design/Tree/AxePartPlacement.cfg`) so **no tech remap was needed** (0 `techRequired` in
>   those files, verified). `PartExperimentAdder`'s clean-slate strips the 5 dead DMagic-native modules (DMagic
>   is out of deps → those `experimentID`s never worked).
> - **CrewScience** (capsule/cockpit/station/lunar-surface, 8 files) authored into
>   `GameData/RP-AXE/design/Science/CrewScience/` with all 17 RP-1 tech-node references remapped to real AXE
>   nodes (remap table + rationale in that folder's `_README.md`; every target verified in `AxeTechTree.cfg`).
> - **Telemetry** (`RP0telemetry1`) is free from mission 1 — stapled onto every `ModuleCommand` part.
> - Shipped **96 of the 98** budgeted RP0\* experiments; the 2 absent (`RP0ALFMED`, `RP0BistaticRadar`) have
>   **no definition in RP-1 itself** (phantom budget rows). **0 unbudgeted extras** → the locked ~298k tree-cost
>   calibration is unchanged.
>
> **Still deferred:** the **KerbalismLab** lab framework (§1, §4) — the crewed-lab value-add — remains
> blocked/unintegrated. This status covers the RP0\* backbone only.

---

## 1. The KerbalismLab load blocker — diagnosed

**Symptom (from the rp1_expanded instance):** installing `KerbalismLabExperimentsExpandedContinued`
throws ~132 ModuleManager errors (`Can't find nodeType:KERBALISM_GROUP_SETTINGS`), value lookups
fail, MM refuses to write the cache.

**Root cause:** the "Continued" fork ships **only the 65 expansion experiments + a tagging
plugin** — it is an *add-on*, not a standalone mod. Every experiment cfg only **`@`-edits** a
root node it never defines:

```
@KERBALISM_GROUP_SETTINGS { @LAB_EXPERIMENTS { ADVASC { value = 40 ... } } }   // edit, not create
... %data_rate /= #$@KERBALISM_GROUP_SETTINGS/LAB_EXPERIMENTS/LabDataRateMultiplier$   // lookup
```

That root node + the `LabDataRateMultiplier` value + the **"Laboratory Experiments" `Configure`
host** on lab parts all come from **Kerbalism's ScienceRework framework**, distributed in
[`KerbalismScienceOnly`](https://github.com/Kerbalism/KerbalismScienceOnly) (and historically some
KerbalismConfig builds). Neither stock Kerbalism, **nor RP-1's KerbalismConfig** (verified: no
`KERBALISM_GROUP_SETTINGS` anywhere in `ksp_rp1_clean`), nor the fork provides it. ~132 errors ≈
2 failed lookups × 65 experiments — every experiment's value-lookups fail because the root node is
absent. The original RoadWarrior9 SpaceDock build had the same gap (it added the host only to SSPX
lab parts via `SSPX-Kerbalism-Labs.cfg`, which the fork also dropped in favour of stock-part tagging).

**Exact missing pieces** (all in `KerbalismScienceOnly/.../System/ScienceRework/`):
- `Internal.cfg` — creates the scaffold node `KERBALISM_GROUP_SETTINGS:NEEDS[FeatureScience] {}`
  (deleted again at `:FINAL` after patching).
- `Tweakables/StockGroups-Lab.cfg` — the `LAB_EXPERIMENTS` group: `LabDataRateMultiplier = 2`,
  `BaseSlots`/upgrade settings, and the **6 base lab experiments** (CHILLED, RELAX, JAMMED, TRAPPED,
  SALINE, BIRDIE + stock MatBay/Goo).
- The **"Laboratory Experiments" `Configure` host** added to lab parts (ScienceRework `NewScience.cfg`
  for stock; the original's `SSPX-Kerbalism-Labs.cfg` for SSPX). The fork's `InstrumentTagging.cfg`
  adds the DLL's `*LabExperimentPackage` part-tag modules but **never** creates the Configure host —
  so even with the root node, no part exposes the lab experiment slots until a host is provided.
- The ScienceRework processing/ordering (`Groups/LabExperiments.cfg`, `Patches-Experiments.cfg`).

**Fix recipe (for P3 integration — NOT done here):** vendor the **minimal lab subset** of
ScienceRework into AXE as authored config — the scaffold node + `LAB_EXPERIMENTS` settings + a
Configure host on AXE's curated lab parts (stock Mobile Lab + SSPX labs) + the lab processing
patches — coexisting with RP-1's RP0\* science. **Do not** install KerbalismScienceOnly wholesale:
it's a full alternative science system (its Orbital/Unmanned/Crew groups would duplicate/conflict
with the RP0\* backbone). This is config-authoring — AXE's deliberate value-add. See §4 decision.

---

## 1b. How a science number is computed (reference)

Science is per **subject** = (experiment × body × situation × biome). For RP-1's experiments
(`baseValue == scienceCap`) one clean run of a subject yields:

```
science = baseValue × bodyDataValue(situation) × biomeValue
```

- **6 situations**, a bitmask: 1 SrfLanded · 2 SrfSplashed · 4 FlyingLow · 8 FlyingHigh · 16 InSpaceLow
  · 32 InSpaceHigh. Each experiment's `situationMask` = where it runs; `biomeMask` = where it's *also*
  biome-split (else one global subject). E.g. `VisibleImaging` = mask 63 (all) / biomeMask 29 (biome-split
  only Landed+FlyLow+FlyHigh+SpaceLow).
- Situation **altitude thresholds** are per-body (`RP-1/Science/BodyScienceParams.cfg`). Earth:
  `flyingAltitudeThreshold = 40000` (FlyLow↔FlyHigh = **40 km**), `spaceAltitudeThreshold = 35,786 km`.
- **bodyDataValue** = per-body, per-situation multiplier (Earth low ≈ 1; Mars landed 7; Mercury landed 40;
  Pluto landed 50). **recoveryValue** is an extra multiplier for physically returning a sample (Moon ×4,
  Mars ×15) — why sample-return is lucrative.
- **biomeValue** sums the body's biome `value`s (Earth ≈ 12; Moon 17 biomes × 0.5 = 8.5; Mars 19; Pluto 20).
- **Earth sub-40 km is removed** by AXE — `design/Science/EarthScienceRemoval.cfg` zeroes Earth
  landed/splashed/flyingLow (→ 0.00001/0.00001/0.001), keeping ≥40 km / orbit / recovery. You can't grind
  science on the homeworld; it must come from real spaceflight and (mostly) other bodies. Costs ~nothing
  in total because other bodies are 2–50× Earth.

## 2. RP0\* suite — MIXED crewed/uncrewed (NOT "probe science")

`tools/science_budget.py`, 98 experiments (96 RP0\* + 2 surface samples). Fully ground-truthed:
body multipliers vs `BodyScienceParams.cfg` (Earth post-`EarthScienceRemoval`); **biome weights** from
the merged `ModuleManager.ConfigCache` (`tools/extract_biomes.py`); **body restrictions** from RP-1's
`BodyAllowed`/`BodyNotAllowed` (`manifest/experiment-bodies.tsv`); **crew requirement** from the Kerbalism
`Experiment` module's `crew_operate` + EVA-part detection (`manifest/experiment-crew.tsv` via
`tools/experiment_crew.py`). **The suite is 60 crewed / 38 uncrewed.** Theoretical max, crew-split:

| reachable by era | crewed | uncrewed | combined | crew% |
|---|---|---|---|---|
| first orbit ~1958 (Earth+Moon) | 26,327 | 22,248 | **48,575** | 54% |
| inner planets ~1961 | 31,372 | 102,044 | 133,415 | 24% |
| crewed + landing ~1964 | 40,012 | 217,835 | 257,846 | 16% |
| adv probes/stations ~1967 | 52,672 | 370,520 | 423,191 | 12% |
| Jupiter ~1970 | 75,182 | 737,098 | 812,279 | 9% |
| Saturn ~1972 | 114,804 | 1,360,946 | 1,475,750 | 8% |
| Uranus ~1986 | 141,464 | 1,822,009 | 1,963,473 | 7% |
| Pluto/modern ~2015 | **177,124** | **2,391,827** | **2,568,951** | 7% |

- **The crew split INVERTS with distance.** Crewed RP0\* experiments are almost all Earth/Moon-locked
  (`HomeBody`/`HomeBodyAndMoons`/`Moon`: life-sciences, habitats, EVA, crew/TV reports), so they DON'T
  scale to deep space. Uncrewed probe instruments (imaging, mag/mass-spec, RPWS, IR, telemetry) are
  universal and soak up the ×10–50 outer-body multipliers. So crewed is **54% at first orbit but only
  7% of the whole-system RP0\* total** — crewed front-loaded, uncrewed back-loaded.
- **Earth-only 21k, Earth+Moon 49k** — the early game is genuinely science-tight, and it's ~half crewed.
- **Big correction from reading body restrictions:** 49 experiments are **Earth-only** (`HomeBody`),
  5 Earth+Moon, 11 Moon-only; the rest universal. An earlier keyword heuristic wrongly spread several
  Earth-only experiments across all 32 bodies — worst case **`RP0photos4` (baseValue 10,000, uncrewed)**
  and the film-return photography family. Fixing that **cut the total 7.3M → 2.57M (−65%)**.
- Uncrewed is **back-loaded** (Jupiter→Pluto ≈ 1.8M of the 2.39M uncrewed). No one collects the
  theoretical max; realistic collection ~20–40%.
- Reference anchor: **RP-1's full pre-restart tree costs ~115,070 science.**
- *Known gaps (data integrity):* the 98-list predates the current RP-1 install — it MISSES 5 stock
  experiments present today (`crewReport`, `evaReport`, `surfaceSample` = crewed; `temperatureScan`,
  `barometerScan` = uncrewed) and CARRIES 2 stale ones absent now (`RP0ALFMED` crewed, `RP0BistaticRadar`
  uncrewed — classified from history in `science_budget.py`'s `CREW_FALLBACK`). The 5 omitted (universal)
  would add roughly +50–80k, mostly crewed; not yet folded in, to preserve the validated 2.57M anchor.
  A future refresh should re-derive the experiment set from the live install. "Theoretical max" = every
  experiment at every allowed body/biome; Charon biomesum reads 0 (cache artifact).

## 3. KerbalismLab (ALL crewed) — the crewed deep-space tail

`tools/lab_budget.py` (inventory: `tools/lab_inventory.py` → `manifest/lab-experiments.tsv`).
**71 experiments** (65 fork + 6 base), `value` 10–500, **all crewed** (they run in a crewed lab).
They scale with the body exactly like RP0\* (`value` is a Kerbalism `baseValue`: `science = value ×
bodyDataValue(situation) × biome`) — a value=50 `InSpaceLow` exp = 50 @Earth, 150 @Mars, 1,500 @Pluto.
And unlike the Earth/Moon-locked *crewed RP0\** experiments, the fork **gates ~30 of 65 OFF Earth**
(`BodyNotAllowed=HomeBody`, or `Gaseous`/`Suns`/`Moons`-only, e.g. `JUNO-*` gas giants) — so KerbalismLab
DOES scale to deep space. So the budget MUST count all allowed bodies:

**KerbalismLab theoretical max (all allowed bodies, same basis as §2) = 1,365,760.**
Dominated by `SrfLanded@Biomes` experiments deliberately gated off Earth → run on all 31 other bodies
with full body+biome multipliers (RELAX alone 164k; ChemCam/GV-SSPB/PPME-1 ~70k each).

- **Realizability caveat (the catch):** this is the *least* collectable third of the budget — those
  totals need **crewed surface bases on other bodies' biomes**, the hardest thing in the game. Uncrewed
  probe theoretical-max you approach with flybys; this you basically never reach. *Realistic* KerbalismLab
  is far lower — an Earth-orbit station runs only 27 of 65 (~3.6k); LEO + a Moon/Mars base ~10–15k.
- Not installable as-is (the §1 load blocker); P3 re-authors it (§4) as plain `Experiment` modules under
  AXE's control. Tier funding: UnlockTechs cluster early-mid; stock node names → remap to AXE nodes.

## 3b. T2 TOTAL BUDGET (the deliverable) — CREWED vs UNCREWED, per era

**Uncrewed** = RP0\* robotic instruments (§2). **Crewed** = RP0\* crewed experiments (§2) + all of
KerbalismLab (§3).

| era (cumulative) | **crewed** (RP0\*+lab) | **uncrewed** (RP0\* robotic) | combined | crew% |
|---|---|---|---|---|
| orbit ~1958 | 35,604 | 22,248 | **57,852** | 62% |
| inner planets ~1961 | 79,610 | 102,044 | **181,654** | 44% |
| crewed + landing ~1964 | 153,134 | 217,835 | **370,969** | 41% |
| adv probes ~1967 | 252,599 | 370,520 | **623,119** | 41% |
| Jupiter ~1970 | 483,634 | 737,098 | **1,220,732** | 40% |
| Saturn ~1972 | 884,581 | 1,360,946 | **2,245,527** | 39% |
| Uranus ~1986 | 1,182,856 | 1,822,009 | **3,004,865** | 39% |
| **Pluto / total** | **1,542,884** | **2,391,827** | **3,934,711** | **39%** |

**Total collectable science ≈ 3.93M; split ≈ 39% crewed / 61% uncrewed** (theoretical max). Crewed
**dominates early** (62% at first orbit — life-sciences + lunar + early lab) then settles to a steady
~39% as the universal uncrewed instruments reach the outer planets. **Realistic** collection is far
more uncrewed-weighted: the crewed 39% leans on the KerbalismLab deep-space tail (least realizable) plus
Earth/Moon-locked crewed RP0\*, whereas uncrewed probe science you approach with flybys. This is the
per-tier budget the tree is costed against (§4). Regenerate: `science_budget.py` (RP0\* crewed/uncrewed) +
`lab_budget.py` (KerbalismLab).

**✅ Resolved (the earlier "do they scale?" uncertainty):** they **do** scale by body — same Kerbalism
subject mechanism as probes. No cache read needed; it's visible in the experiment defs (stock situations
+ body-type gates). The consequence is a **re-author design lever** (§4): the as-shipped design has an
**overpowered deep-space tail** (value-500 telescope × gas-giant ×10) and assumes deployments players
rarely make (you build in LEO). RP-1's *own* crewed experiments dodge this by being `HomeBody`/`Moon`-
restricted (don't scale). **Re-author choice:** flatten most lab exp to home-system (matches reality,
no tail) vs. keep a deliberate handful as high-value deep-space targets (JUNO/solar) for ambition.

---

## 4. Tree-cost decision — LOCKED (2026-07-06): ~298k via a per-tier rate table

Total budget (§3b): **~3.93M theoretical (39% crewed / 61% uncrewed)**; realistic collection is lower and
uncrewed-weighted. Anchors considered: RP-1 = **115k** (≈3% of pool, completable); VISION-literal "tree cost ≈
total science" = ~3.93M (you'd unlock ~5% — absurd). **DECISION: total tree cost ≈ 298k** (≈ 2.6× RP-1,
≈ 8% of pool), implemented as a **monotonic per-tier rate table** in `tree/nodes.yaml` meta (`tier_cost`),
NOT a global scalar. `cost(node) = tier_cost[tier]`, per-node `cost:` overrides win.

- **Why ~300k:** AXE drops RP-1's *other* gates (reliability/run-data grind, time pressure), so science is
  the **sole** pacing axis and must do more work than RP-1's 115k. ~300k is finishable by a **broad-
  exploration** playthrough (banks ~300–500k realistically) but not a focused rush → matches VISION's
  "not expected to finish in one playthrough." Bracket: ~150k RP-1-comfortable … ~500k grand-tour-only.
  Total is a dial (rescale the table); final tune comes from the **P3 solvency play-session**.
- **The rate table (per node, by tier):**

  | T | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | rate | 1 | 4 | 15 | 40 | 80 | 160 | 300 | 450 | 700 | 1000 | 1450 | 2000 | 2650 | 3500 | 4500 | 5650 |

  **Monotonic non-decreasing, T1 = 1** (bootstrap ~free — can't gate *reaching* orbit behind orbital science).
- **Shape EMERGES from node count × a rising rate — NOT hand-forced (supersedes the earlier "front-load
  tiers 3–6" plan).** Node count already humps mid/late (T7 = 52, T9 = 54, T10 = 45, T11 = 41; then craters
  T13–16 = 11/4/2/2). A monotonic per-node rate over that count puts the cumulative bite in the **reachable
  T9–T13 outer-planet grind** (cumulative-cost peaks ~62% at T11), tapering at the top where node count dies
  and VISION hands the gate to *other* axes (power/heat/materials/money). Early (T1–6) is only ~3% of total —
  **capability-gated, not science-gated**, exactly as VISION wants.
- **RP-1 reference (ground-truth from `RP0TechTree.cfg`, ORPHANS 99999 sink excluded):** RP-1's real 115k is
  *far more back-loaded* — its **final era column alone is 60%** of the tree — but it gets there via **node
  count** (78 cheap nodes dumped in that column; per-node median **233**, max **1000**), an aspirational
  endgame wall most players never reach. AXE's node count **tapers** at the top instead, so AXE back-loads via
  **per-node rate** (up to 5650) and spreads the bite across the *reachable* mid-late game. Same philosophy
  (monotonic, back-loaded), different lever — and the smoother curve is the healthier pacing.

**For P3 (KerbalismLab integration) — DECIDED: re-author as plain `Experiment` modules.**
Reimplement the 65 experiments as plain Kerbalism `Experiment` + `EXPERIMENT_DEFINITION` configs wired
directly to AXE instrument parts and AXE tech nodes — the way RP-1 wires RP0\* — dropping Kerbalism's
ScienceRework `Configure`/group/slot layer entirely. Rationale: a clean, RP-1-consistent crewed-science
set **fully under AXE's control** (values, gating, scope, part assignment), no dependency on the
ScienceRework framework, and the two science streams then balance against each other identically.
(Rejected: *vendor the ScienceRework lab subsystem as-is* — least work but imports Kerbalism's
lab-slot machinery + its RP-1-coexistence risk, values stay author-defaults; *drop KerbalismLab* —
loses the 71-experiment breadth, falls back on RP0\*'s own ~25–30 crewed experiments.)

**Body-multiplier question — resolved.** Lab experiments scale like RP0\* (baseValue × situation × body ×
biome — the §2 model); confirmed from the experiment defs, no cache read needed. The fork's *as-shipped*
scope is wide (only ~10 are Earth-only; ~30 are gated *off* Earth to gas-giants/sun/"not-home") and the
deep-space tail is overpowered. Because we re-author, body-scope is **ours to set** — see step 4.

**P3 re-author plan (turnkey once P1 nodes exist):**
1. Generator: `lab-experiments.tsv` + the 65 cfgs → plain `Experiment`/`EXPERIMENT_DEFINITION` configs.
2. Map each experiment's instrument requirement (the `Module:*LabExperimentPackage` column) to a curated
   AXE part; decide whether to keep the DLL tags or hardcode `requirements = Part:<name>` (prefer the
   latter — no compiled dependency, precise control).
3. Remap the ~22 stock `UnlockTech` names → AXE nodes (blocked on P1; ship a remap table now).
4. **Set body scope + calibrate baseValues** so the budget lands where intended. Default lean: restrict
   most to home-system (`HomeBody`/`HomeBodyAndMoons`/`Moon`, like RP-1's own crewed exp) → matches the
   "stations live in LEO" reality and kills the runaway tail; keep a deliberate **handful** as high-value
   deep-space targets (JUNO=gas-giant, SOLAR=sun) so there's a reason to fly an ambitious lab out.

---

## 5. Part unlock (funds) cost — LOCKED (2026-07-06): tier × category, calibrated to RP-1

Science (§4) is the **primary** gate. Funds are the **secondary** axis — VISION's "abstract non-simulated
engineering tradeoffs": part `entryCost` = R&D, launch cost = ops. **Funds are TEXTURE, NOT A WALL** — you
prioritise, you don't go bankrupt. Generated to `GameData/RP-AXE/design/Tree/AxePartCost.cfg` by
`build_tree.py` (tables in `tree/nodes.yaml` meta), a `%entryCost` patch per part/upgrade.

**Model:**
- `entryCost(part) = part_cost_base[tier] × part_cost_weight[costcat(part)]`
- `entryCost(upgrade) = part_cost_base[tier] × upgrade_cost_scalar` (= 0.3; light, no category — RP-1 left
  upgrades ~free and engine variants are already paid via the base part's engine weight)
- `tier` = the AXE node the part/upgrade is placed on (T0 start-parts → 0, i.e. free). Result: 1774/1790
  parts priced, span **20–32,400 funds, median 1,440**.

**`part_cost_base`** (weight-1.0 part, monotonic): T1 100 · T4 600 · T7 1800 · T10 4200 · T13 9000 · T16 18000.
**`part_cost_weight`:** science 2.5 · crewpod 2.0 · gear 2.0 · engine 1.8 · power 1.5 · tank/avionics/misc 1.0 ·
antenna/rcs 0.8 · aero/separator 0.5 · structural 0.4 · chute 0.3 · ground 0.2.

**Why these numbers — calibrated to RP-1 (the reference you asked for).** Ground-truthed RP-1's real
`entryCost`s from the `ksp_rp1_expanded` ConfigCache, joined to `part-capabilities.tsv` (category/modules) +
AXE tier. Two findings drove the design:
- **RP-1 prices sharply BY CATEGORY.** The categories it hand-priced come out on RP-1's own medians:
  science ≈ 10.5k (RP-1 10k), crewpod ≈ 3.6k (RP-1 3.4k), gear ≈ 11k (10k), power ≈ 3.6k (5k),
  antenna ≈ 1.4k (1k). So the model **reproduces RP-1's economy** where RP-1 had one.
- **RP-1 left engines/tanks/structural/aero/rcs at ~0 at the part level** — because it gated their funds through
  the **tooling system** (per-size), which AXE **deleted with RP0.dll**, and engine-variant unlock through
  **RealFuels' dynamic config cost** (static `entryCost`s are ~0: 572/609 upgrades = 0). Those categories are
  currently **free-to-unlock in AXE** — so the tier×weight formula **rebuilds that gate** as a clean number
  (engines carry real cost via weight 1.8 on the base part; structural stays texture).

**No earliness premium.** The idea (pull a part in earlier than RP-1 → charge more) is already captured: the
**AXE tier** encodes "how advanced, when." A part placed early sits at a low tier and is naturally cheaper —
adding an RP-1-era-delta premium would reintroduce RP-1's tree as a second axis and fight the clean tier model.

**`costcat` classifier** (in `build_tree.py`): signal = PartModules + stock category + AXE discipline + source
mod, most-specific-first; stock-category clauses (Science/Coupling/Electrical/Thermal) + `ground`
(ModularLaunchPads / LaunchClamp) are fallbacks for parts whose modules dodge the module check; uncovered →
`misc` (weight 1.0, ~107 parts). **Magnitude is a P3 dial** — absolute funds calibrate against *income*
(contracts), which the P3 solvency play-session tunes; the category *ratios* are the RP-1-grounded part.
