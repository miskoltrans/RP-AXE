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

## 1. The KerbalismLab load blocker — diagnosed → ✅ FIXED 2026-07-15

> **RESOLVED.** Fixed by **Path A — vendor the minimal Kerbalism ScienceRework lab framework**, so the fork
> loads exactly as its creator authored it. Shipped + in-game verified (`02b840a`, `bc7e6cb`): 65 experiments
> under `design/Science/KerbalismLab/` via `tools/build_kerbalismlab.py`, techs remapped to AXE nodes,
> `-axe-autotest` clean with a 36.6 MB ConfigCache. Full plan: [`KERBALISMLAB.md`](KERBALISMLAB.md).
> **This also supersedes the "re-author the 65 as plain Experiments" default** that §4 of this doc and
> RESTART.md T2 had settled on. The diagnosis below is kept as the reasoning trail.

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

> **⚠ RE-MEASURED 2026-07-28 (balance pass, `docs/KERBALISMLAB.md` §7).** The figures below were computed
> from the upstream fork under the assumption that the authored `value` is the science payout. **It is
> not** — Kerbalism pays on `scienceCap` (`ScienceMaxValue = ScienceCap × SituationMultiplier`), and
> nothing was setting it, so the shipped build paid a flat **180 × multiplier** for every experiment:
> a real theoretical max of **13.07M**, not 1.37M. The 6 base experiments were also missing their
> definitions entirely. Both fixed. `tools/lab_budget.py` now reads the **shipped** configs and models
> the real payout field. **Current total = 1,494,179** (1.47M after the fixes, +1.7% from raising the
> near-Earth floor). The per-body/era shape below still holds; the totals are superseded by §3b.

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
| orbit ~1958 | 60,554 | 22,248 | **82,802** | 73% |
| inner planets ~1961 | 108,417 | 102,044 | **210,461** | 52% |
| crewed + landing ~1964 | 185,073 | 217,835 | **402,908** | 46% |
| adv probes ~1967 | 288,094 | 370,520 | **658,614** | 44% |
| Jupiter ~1970 | 532,659 | 737,098 | **1,269,757** | 42% |
| Saturn ~1972 | 958,750 | 1,360,946 | **2,319,696** | 41% |
| Uranus ~1986 | 1,281,199 | 1,822,009 | **3,103,208** | 41% |
| **Pluto / total** | **1,671,303** | **2,391,827** | **4,063,130** | **41%** |

> **Re-measured 2026-07-28** after the KerbalismLab balance pass ([`KERBALISMLAB.md`](KERBALISMLAB.md) §7).
> Was 3.93M / 39% crewed, on a lab figure of 1.37M that no build ever ran — the shipped build actually paid
> a flat 180 × multiplier per experiment. Lab is now 1,494,179.

**Total collectable science ≈ 4.06M; split ≈ 41% crewed / 59% uncrewed** (theoretical max). Crewed
**dominates early** (73% at first orbit — life-sciences + lunar + early lab) then settles to a steady
~41% as the universal uncrewed instruments reach the outer planets. **Realistic** collection is far
more uncrewed-weighted: the crewed 41% leans on the KerbalismLab deep-space tail (least realizable) plus
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

## 4. Tree-cost decision — LOCKED (2026-07-06) · RE-BLESSED (2026-07-28): ~300k via a per-tier rate table

> **RE-BLESSING, 2026-07-28 (commit `a8a3f49`) — read this first; the lock rationale below is intact but
> its central premise expired.** The tree grew **423 → 499 nodes** and the growth landed almost entirely at
> the expensive end (T12–16 = **84%** of the increase; T13–16 alone **19 → 46 nodes**), so **+18% nodes bought
> +49% cost**: the emitted total drifted **298,214 → 442,966** and the late tail went **21% → 36%** of the
> tree — the RP-1 endgame wall this section set out to avoid. The lock justified rates rising to 5,650/node
> on the premise that *node count craters at the top*; with 46 nodes up there it does not. **Both levers moved:**
>
> | | before | after | effect |
> |---|---|---|---|
> | **Shape** — `tier_cost` T14/15/16 | 3500 / 4500 / 5650 | **2900 / 3200 / 3500** | tail 36% → **32%** |
> | **Magnitude** — `meta.scalar` | 1.0 | **0.72** | total → **300,376** |
>
> **Why the tail stops at 32%, not 21%:** with 46 nodes at T13–16 and T12 = 2000, monotonicity floors the tail
> near **25%** — going lower means re-tuning the whole curve, not the top. The right moment for that is when
> the endgame region is actually *designed*: those 46 nodes are the undesigned colonization scaffold
> (RESTART.md P6). **Node costs are now `round(tier_cost[tier] × 0.72)`** — 115 at T6, 504 at T9, 1440 at T12.
>
> ⚠ **Scalar window — keep `scalar` in `0.625 … 0.828`, enforced by `build_tree.py`'s `science cap gate`.**
> The R&D building gates research by node **cost**, not tier, so *which tier needs which R&D level* is
> economy design (ECONOMY.md §8) hiding inside this table. **Widened 2026-07-29** when AXE replaced the
> inherited 3-level CustomBarnKit ladder with its own 8-level one: the caps now sit at the geometric
> midpoint of each tier gap, so all seven boundaries tolerate 15–40% of drift and both bounds are set by
> the T12|T13 cap of 1655. Under the old `100, 500, -1` the floor was 0.715 against a scalar of 0.72 —
> 0.7% of headroom, and the obvious scalar for an exact 298k restore (**0.673**) would have put T9 at 471,
> silently dropping 57 nodes out from behind the top gate. The gate asserts every boundary on each build
> and prints the range.

> **⚠️ DRIFT — measured 2026-07-28, RESOLVED the same day by the re-blessing above.** The measurement is
> kept because it is the evidence the re-blessing acted on; the "now (live build)" column is the *pre-fix*
> state, not current. Current = **300,376** total, T13–16 = 31.8%.
>
> The decision deliberately makes total cost *emergent* (`node count × a rising per-tier rate`). The tree
> then grew **~217 → 499 nodes**, so:
>
> | | as decided | now (live build) |
> |---|--:|--:|
> | total tree cost | ~298k | **422,666** |
> | cumulative cost by end of T11 | ~62% | **49.2%** |
> | T13–16 node count | 11 / 4 / 2 / 2 (19) | **22 / 12 / 8 / 4 (46)** |
>
> Total is still inside the stated bracket (~150k … ~500k), so *magnitude* is defensible as-is. **The shape
> claim is the part that no longer holds:** the bullet below argues the bite lands in T9–T13 and then tapers
> "at the top where node count dies and VISION hands the gate to *other* axes." The top no longer dies —
> **T12–16 now carry 50.8% of the entire tree's cost**, because the late tail grew from 19 nodes to 46 as the
> outer-planet / station / reusable milestones were placed. Half the science gate now sits above T11.
>
> Per-tier node counts at the time of measuring (T0–T16): 2 · 20 · 23 · 25 · 37 · 25 · 30 · 53 · 41 · 57 ·
> 53 · 49 · 38 · 22 · 12 · 8 · 4. Re-measure with `python tools/build_tree.py` (per-tier cost table,
> `total:`, and the `science cap gate` line are printed). **Both levers were moved rather than waiting for
> the play-session** — the shape claim was broken, not merely off-target, and leaving a broken premise in
> place would have let every later node compound it. Magnitude remains the play-session's dial.

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
- **The rate table (per node, by tier)** — `tier_cost` in `tree/nodes.yaml` meta; **T14–16 flattened
  2026-07-28** (was 3500 / 4500 / 5650), and every entry is multiplied by `scalar` **0.72** on emit:

  | T | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | rate | 1 | 4 | 15 | 40 | 80 | 160 | 300 | 450 | 700 | 1000 | 1450 | 2000 | 2650 | **2900** | **3200** | **3500** |
  | emitted (×0.72) | 1 | 3 | 11 | 29 | 58 | 115 | 216 | 324 | 504 | 720 | 1044 | 1440 | 1908 | 2088 | 2304 | 2520 |

  **Monotonic non-decreasing, T1 = 1** (bootstrap ~free — can't gate *reaching* orbit behind orbital science).
- **Shape EMERGES from node count × a rising rate — NOT hand-forced (supersedes the earlier "front-load
  tiers 3–6" plan).** *(The mechanism stands; the node counts below are the 2026-07-06 snapshot and the
  "craters at the top" reading of them expired — see the re-blessing at the top of this section.)* Node count
  already humps mid/late (T7 = 52, T9 = 54, T10 = 45, T11 = 41; then craters
  T13–16 = 11/4/2/2). A monotonic per-node rate over that count puts the cumulative bite in the **reachable
  T9–T13 outer-planet grind** (cumulative-cost peaks ~62% at T11), tapering at the top where node count dies
  and VISION hands the gate to *other* axes (power/heat/materials/money). Early (T1–6) is only ~3% of total —
  **capability-gated, not science-gated**, exactly as VISION wants.
- **Where the cost actually sits (499 nodes, scalar 0.72):** T1–5 **2,887** (1.0%) · T6–8 **28,182** (9.4%) ·
  T9–12 **172,764** (57.5%) · T13–16 **95,544** (31.8%). These bands used to be the R&D-building bands too,
  with **90% of the tree's science behind a single 1,690,000 purchase**. AXE authored its own 8-level ladder
  on 2026-07-29 to break that up — no step now opens more than 18.8% of the tree bar the far-future top,
  and each band above splits across two or three R&D levels. See ECONOMY.md §8.
- **RP-1 reference (ground-truth from `RP0TechTree.cfg`, ORPHANS 99999 sink excluded):** RP-1's real 115k is
  *far more back-loaded* — its **final era column alone is 60%** of the tree — but it gets there via **node
  count** (78 cheap nodes dumped in that column; per-node median **233**, max **1000**), an aspirational
  endgame wall most players never reach. AXE back-loads via **per-node rate** instead and spreads the bite
  across the *reachable* mid-late game. Same philosophy (monotonic, back-loaded), different lever — and the
  smoother curve is the healthier pacing. **Caveat as of 2026-07-28:** AXE's node count no longer *tapers* at
  the top (T13–16 is 46 nodes, not 19), so AXE is now leaning on **both** levers up there — which is exactly
  what the flattened T14–16 rates pull back against, and why the tail is worth re-checking whenever the
  endgame region gains or loses nodes.

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
  upgrades ~free). **`RFUpgrade_*` are the exception, forced to 0** — see §5b, they are tree icons and
  RealFuels charges for an engine variant somewhere else entirely.
- `tier` = the AXE node the part/upgrade is placed on (T0 start-parts → 0, i.e. free). Result (2026-07-28,
  full tree): **1,830 parts priced, span 20–32,400 funds**, total **5,455,475**; plus 87 upgrades (102,150)
  and 466 engine configs (551,685, §5b) = **6,109,310 to buy literally everything**.

**`part_cost_base`** (weight-1.0 part, monotonic): T1 100 · T4 600 · T7 1800 · T10 4200 · T13 9000 · T16 18000.
**`part_cost_weight`:** science 2.5 · crewpod 2.0 · gear 2.0 · engine 1.8 · power 1.5 · tank/avionics/misc 1.0 ·
antenna/rcs 0.8 · aero/separator 0.5 · structural 0.4 · chute 0.3 · ground 0.2.

**Why these numbers — calibrated to RP-1 (the reference you asked for).** Ground-truthed RP-1's real
`entryCost`s from the `ksp_rp1_expanded` ConfigCache, joined to `part-capabilities.tsv` (category/modules) +
AXE tier. Two findings drove the design:
- **RP-1 prices sharply BY CATEGORY**, and the model reproduces those categories' medians. *(Re-measured
  on the finished tree 2026-07-28 — see §5c; the original figures here were taken on a partial tree and two
  of them were wrong. Current: science 4,500 vs RP-1's 4,500 — exact; antenna 1,440 vs 1,000; crewpod 4,800
  vs 5,600; gear 3,600 vs 1,600. The claim holds where it matters — science and antenna are the categories
  RP-1 genuinely hand-priced — but it only holds **after** the §5c classifier fixes.)*
- **RP-1 left engines/tanks/structural/aero/rcs at ~0 at the part level** — because it gated their funds through
  the **tooling system** (per-size), which AXE **deleted with RP0.dll**, and engine-variant unlock through
  **RealFuels' dynamic config cost** (static `entryCost`s are ~0: 572/609 upgrades = 0). Those categories are
  currently **free-to-unlock in AXE** — so the tier×weight formula **rebuilds that gate** as a clean number
  (engines carry real cost via weight 1.8 on the base part; structural stays texture).

### 5b. Engine-variant unlock cost — added 2026-07-27: `ENTRYCOSTMODS`, chained per ladder

§5 originally assumed engine variants were "already paid via the base part's engine weight." Ground-truthing
the installed RealFuels 15.14.0 (decompiled) showed they were **not paid at all**, in two places:

- **RealFuels gates a CONFIG on two things**, `CanConfig()` (its `techRequired`) *and* `UnlockedConfig()` →
  `EntryCostDatabase.IsUnlocked()`, priced from **`ENTRYCOSTMODS`** nodes. AXE shipped **zero** of them, so
  every config's price was 0 — and `EngineConfigGUI` silently auto-purchases a 0-cost config the instant its
  row renders (`if (num <= 0.0 && !flag2 && flag) PurchaseConfig(...)`). Free, with no button to press.
- **The `RFUpgrade_*` `PARTUPGRADE`s were being priced instead, and they are not the lever.** RealFuels never
  consults `PartUpgradeManager` for config availability, and `OnPartUpgradePurchased` marks `RFUpgrade-<cfg>`
  unlocked rather than `<cfg>` — so buying one charged funds and unlocked nothing. RP-1 defines them at
  `entryCost = 0` deliberately: `EntryCostDatabase.UpdateEntryCosts()` auto-unlocks any upgrade under 1.1
  whose tech is researched, so the icon never presents as a purchase. AXE now matches that.

**Model** — `GameData/RP-AXE/design/Tree/AxeEntryCostMods.cfg`, generated by `build_tree.py`:

- `cost(config) = part_cost_base[tier of the config's node] × engine_config_cost_scalar` (= 0.3, its own
  meta knob so it can be dialled off `upgrade_cost_scalar` later).
- **Chained per ladder.** Each variant names the previous rung of its own part's ladder as an ECM child;
  `GetCost` sums `own + Σ children` with an already-unlocked name counting **0**. So the first variant you
  buy in a family carries the lineage and every sibling after it costs only its own step — RP-1's
  self-discounting shape (`RL10A-3-1 = 15000, RL10A-1`), with AXE's tier numbers instead of RP-1's
  hand-tuned figures and shared-technology tokens (`HydroloxPumps`, `PumpReignition`, …).
- **Priced set == tech-gated set.** A config is charged for exactly when the ladder moved it past its part's
  own node. Anything reachable the moment you buy the part — its base config, propellant variants like the
  NTRs' Ammonia/Methane or the RCS Helium (104 occurrences) — is included in the part's `entryCost` and stays
  free. Pricing those would be a funds-only toll with no tech story, which is not what "texture, not a wall"
  means.
- **Configs only, no `PART` entries.** RP-1's `ECM-Parts.cfg` lists parts pointing at their base config,
  which is how buying the part unlocks that config. Omitting both gets the same result without a second
  pricing system — and critically, an ECM holder for a part would **override** §5's `entryCost`
  (`UpdateEntryCost(AvailablePart)` calls `ap.SetEntryCost(holder)`), so `AxePartCost.cfg` stays the sole
  owner of part pricing.

**Result: 443 configs priced, 441 chained**, span 30–4,350 per step. Worked example, the RL-10 (`ROE-RL10Fixed`):
`RL10A-1` free with the part → `RL10A-3-1` 390 → `RL10A-3-3` 540 → … → the CECE/RL10C family 1,650 each.
Buying out of order costs the chain: `RL10A-3-3` first is 930, `CECE-Base` cold is 6,900.

ECM keys are **global**, and 134 config names are shared by more than one part (`ASCENT` rides six), so each
name is priced once from its earliest home; chains only point strictly backwards in that order, which makes
the graph acyclic by construction. Engines absent from `manifest/engine-stats.tsv` get no entry and stay
free — the same coverage gap as the gate emitter's layer-2 catch-all.

**No earliness premium.** The idea (pull a part in earlier than RP-1 → charge more) is already captured: the
**AXE tier** encodes "how advanced, when." A part placed early sits at a low tier and is naturally cheaper —
adding an RP-1-era-delta premium would reintroduce RP-1's tree as a second axis and fight the clean tier model.

**`costcat` classifier** (in `build_tree.py`): signal = PartModules + stock category + AXE discipline + source
mod, most-specific-first; stock-category clauses (Science / Coupling / Electrical / Thermal / Ground) are
fallbacks for parts whose modules dodge the module check, and **each one belongs to the last rule that could
want it** — a category clause placed early silently outranks every module rule below it (§5c). Uncovered →
`misc` (weight 1.0, ~109 parts), and so is any part with **no row in `part-capabilities.tsv`**: it arrives as
four empty strings and classifies as `misc` with nothing to flag it. Run `tools/backfill_capabilities.py`
after placing parts RP-1 never had.

---

### 5c. Calibration pass — 2026-07-28: the defects were classification, not magnitude

Run once the tree was complete (the pass RESTART.md deferred). Four measurements, then the verdict.

**1. Magnitude is right — against income, and against RP-1 itself.** Buy-everything is 6.11M against a
40M lifetime (ECONOMY.md §3), but nobody buys everything: at the *k cheapest parts on every node you
research*, a full playthrough spends **1.55M (1/node) — 2.71M (2/node)**, and with engine configs ≈ **3.2M**.
That is **8% of lifetime funds — the same share RP-1 spends on part unlocks** (its own `entryCost`s over the
shared part set total 17.9M against 229M of programme funding = 7.8%). Buy-everything runs at 2× RP-1's
share, which is the intended difference: AXE prices the categories RP-1 gated through tooling.

**2. The early window is the tight one, and it is tight by design.** Through T5 — everything before R&D L2
is needed — realized part spend is **72k (1/node) / 128k (2/node)** against ~334k of income earned by then,
competing with R&D L2 (113k) and pad L2–L3 (94k). Selective buying clears it with room; buying two of
everything does not. That is "you prioritise, you don't go bankrupt" working, but it is the window a play
session should watch first.

**3. Three classification defects, all silent, all now fixed.** These moved 129 parts and +122,590 funds
(+2.2%); none of them was a dial:
- **`ground` was stealing every landing leg, wheel, track and aircraft gear** — 54 parts. `cat == "Ground"`
  is KSP's part category for legs and wheels, not for launch infrastructure, and it sat in the *first*
  clause, so they all priced at the launch-clamp weight **0.2** instead of `gear` **2.0** — a 10× underprice
  (17,900 → 179,000) that also left `gear` matching **zero parts**, which is why the original bullet above
  could claim a gear median that no part had. `ground` is now launch infrastructure only (ModularLaunchPads
  / LaunchClamp / ModuleGroundPart); `cat == "Ground"` fell through to `gear`, where it belongs.
- **41 crew cabins and habitats priced as scientific instruments** — `mk2CrewCabin`, `MK1CrewCabin`, the
  SSPX hab / greenhouse / centrifuge line, the Tantares crew modules. Station modules ship
  `ModuleScienceExperiment` by convention, so they hit the science clause and took the **2.5** instrument
  weight. Now `crewpod` (2.0), scoped *inside* the science clause on purpose: `Habitat` is added to any
  pressurisable volume including crew-capacity-0 adapters, so as a standalone rule it also swallows the SSPX
  connectors. Parts with a real `ModuleScienceLab` stay science — the lab is the thing being paid for.
- **52 placed parts had no `part-capabilities.tsv` row at all**, so they classified from empty strings into
  `misc`. Nine SCANsat instruments, `RO-MagellanRadar` and `SCANsat_Tracker` were being priced as generic
  hardware instead of instruments. `tools/backfill_capabilities.py` mines the missing rows from the live
  ModuleManager cache (discipline taken from the AXE node the part sits on — not a guess, the part is in the
  tree); 46 were added. The remaining 6 are **placed but not installed**: `ca_GRS` (RO deletes it) and the
  five `dmUS2*` wedges (DMagic is not in the mod set — these are the US2 wedges P6 still owes).
- Minor, same pass: fission reactors (`ModuleSystemHeatFissionReactor`) → `power`, and the backfilled US2
  shrouds/cores → `structural` / `separator`.

**4. What did NOT change: `part_cost_base`, `part_cost_weight`, and both scalars.** After the fixes the
category medians land on RP-1's for the categories RP-1 actually priced (science exactly, antenna 1.4×) and
realized spend lands on RP-1's own share of lifetime funds. There was no evidence for moving a dial, and
magnitude remains what it always was: the play-session's call, not a spreadsheet's.

**Open — not part pricing, but the thing part pricing is calibrated against.** Contract income is far more
back-loaded than the sinks it pays for: the first 15 programmes pay **6.4%** of channel 1 (1.54M of 24M),
while the pad upgrades a Moon landing needs cost more than that on their own and `CrewedLunar` is the 16th
programme. Part unlocks are a minor term in it (~1.3M by the Moon landing) and are not what would break it.
**→ Chased down and partly fixed the same day: [`ECONOMY.md`](ECONOMY.md) §6.** The root cause turned out to
be an off-by-one in how every facility `upgrades` array was read (the first entry is never charged), the
launchpad has been re-shaped 10.33M → 7.29M, and the remaining income-shape fix is an open user call. Nothing
there moves `part_cost_base`.
