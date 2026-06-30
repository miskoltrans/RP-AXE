# RP-AXE — Science Budget & KerbalismLab Audit (T2)

Pre-P1 science measurement (see [`RESTART.md`](RESTART.md) T2). The tree's total cost is
balanced against total collectable science, so we measure the budget **before** setting node
costs. Two science streams: uncrewed **probe science** (RP-1's RP0\* suite) and crewed
**lab/station science** (KerbalismLab).

Reproduce: `python tools/science_budget.py` (probe) and `python tools/lab_inventory.py` (lab).
Data artifacts: [`../manifest/lab-experiments.tsv`](../manifest/lab-experiments.tsv).

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

## 2. Probe science (RP0\*) — the dominant, back-loaded stream

`tools/science_budget.py`, 98 experiments (96 RP0\* + 2 surface samples). Fully ground-truthed:
body multipliers vs `BodyScienceParams.cfg` (Earth post-`EarthScienceRemoval`); **biome weights** from
the merged `ModuleManager.ConfigCache` (`tools/extract_biomes.py`); **per-experiment body restrictions**
from RP-1's actual `BodyAllowed`/`BodyNotAllowed` (`manifest/experiment-bodies.tsv` via
`tools/experiment_bodies.py`). **Theoretical max:**

| reachable by era | cumulative probe science |
|---|---|
| first orbit ~1958 (Earth+Moon) | **48,575** |
| inner planets ~1961 | 133,415 |
| crewed + landing ~1964 | 257,846 |
| adv probes/stations ~1967 | 423,191 |
| Jupiter ~1970 | 812,279 |
| Saturn ~1972 | 1,475,750 |
| Uranus ~1986 | 1,963,473 |
| Pluto/modern ~2015 | **2,568,951** |

- **Earth-only 21k, Earth+Moon 49k** — the early game is genuinely science-tight.
- **Big correction from reading body restrictions:** 49 experiments are **Earth-only** (`HomeBody`),
  5 Earth+Moon, 11 Moon-only; the rest universal. My earlier keyword heuristic had wrongly spread
  several Earth-only experiments across all 32 bodies — worst case **`RP0photos4` (baseValue 10,000)** and
  the rest of the film-return photography family ("photography" never matched the id "photos"). Fixing
  that **cut the total from 7.3M → 2.57M (−65%)**. Lesson logged: heuristics on the highest-value rows
  are where estimates go most wrong.
- Still **back-loaded** (Jupiter→Pluto ≈ 1.8M of 2.57M) but far less extreme. No one collects the
  theoretical max; realistic collection ~20–40% → **~0.5–1.0M**.
- Reference anchor: **RP-1's full tech tree costs ~115,070 science** (pre-restart tree). The tree is
  comfortably funded by **mid-game** (≥258k available by the early-crewed era), but completing a large
  AXE tree requires genuine **interplanetary** exploration — science is binding throughout, tightest early.
- *Still modeled (not read):* "theoretical max" = every experiment at every allowed body/biome (real
  collection is a fraction); Charon biomesum reads 0 (cache artifact). Body-assignment is now exact.

## 3. Crewed-lab science (KerbalismLab) — a mid-game station stream

`tools/lab_inventory.py` → `manifest/lab-experiments.tsv`. **71 experiments** (65 fork + 6 base),
science `value` **10–500, median 25, raw per-run sum 3,653**.

**Cross-body budget (fixed-value model — value taken as literal science, no body multiplier):**

| scenario | crewed-lab science |
|---|---|
| one fully-equipped station/base, 1 body, 1 biome | ~3,653 |
| realistic ~8 crewed bodies (Earth/Moon/Mars/Venus/4 moons) | **~51,000** |
| theoretical 32 bodies | ~204,576 |

- Magnitude check: realistic crewed-lab (~51k) **exceeds home-system probe science (~49k)** and is
  ~44% of a full tree (~115k) — a **meaningful mid-game stream that more than doubles home-system
  science** and specifically rewards the station/base era (where probe science is thin until you can
  reach other planets). It is **not** a primary funder globally (~2% of probe max).
- High-value items cluster in the `Space` telescopes / high-energy bucket (HaloSat 500, CALET 350,
  NICER/CXBN-2/ASTERIA 300). Biome experiments are individually small (10–15) but multiply.
- Tier funding: UnlockTechs cluster at `basicScience / scienceTech / spaceExploration /
  advExploration` — i.e. **early-mid tiers**, exactly the station era. All gates use **stock node
  names → must be remapped to AXE nodes** at integration.

**⚠️ Key uncertainty (why the cache-read still matters):** the above assumes Kerbalism treats
`value` as literal science. **If** Kerbalism applies celestial-body science multipliers to lab
experiments (as it does for probe science), the theoretical scales 3–30× toward **0.6–6M**, making
crewed-lab a *major* stream and likely **overpowered at outer planets**. Resolving this needs an
in-game **merged-cache read**, which is **blocked until the framework (§1) is restored**. For P1
tree *architecture* the fixed-value estimate is sufficient; for final *balance* (P3) we read the cache.

---

## 4. Tree-budget implications + decision needed

**For P1 (tree architecture):** two competing anchors to resolve —
- **RP-1 anchor (completable):** ~115k baseline → a 200–500 node AXE tree at **~150k–400k** total cost
  is fundable by realistic collection (~0.5–1.0M probe + ~50k lab) but requires genuine interplanetary
  exploration to finish; early game (Earth+Moon ≈ 49k probe + early lab) stays tight.
- **VISION anchor (not completable in one playthrough):** "tree cost ≈ total science" → ~2.5M, i.e. a
  much costlier tree you can't finish. These pull opposite directions — **a P1 call**, not settled here.
- Either way, per-tier budgeting must mirror availability: cheap early nodes (paid by thin home-system
  science), costlier late nodes (paid by interplanetary science). Crewed-lab fills the **mid-game
  station valley** between home-system probes and interplanetary probes.

**For P3 (KerbalismLab integration) — DECIDED: re-author as plain `Experiment` modules.**
Reimplement the 65 experiments as plain Kerbalism `Experiment` + `EXPERIMENT_DEFINITION` configs wired
directly to AXE instrument parts and AXE tech nodes — the way RP-1 wires RP0\* — dropping Kerbalism's
ScienceRework `Configure`/group/slot layer entirely. Rationale: a clean, RP-1-consistent crewed-science
set **fully under AXE's control** (values, gating, scope, part assignment), no dependency on the
ScienceRework framework, and the two science streams then balance against each other identically.
(Rejected: *vendor the ScienceRework lab subsystem as-is* — least work but imports Kerbalism's
lab-slot machinery + its RP-1-coexistence risk, values stay author-defaults; *drop KerbalismLab* —
loses the 71-experiment breadth, falls back on RP0\*'s own ~25–30 crewed experiments.)

**Body-multiplier question — resolved by construction.** Because we re-author (not run the fork as-is),
lab experiments scale like RP0\* (baseValue × situation × body × biome — the model behind §2). We *set*
the values and situations against that known model, so there is **no need for an in-game cache read**.
The §3 fixed-value crewed-lab budget (~51k realistic) is the **floor**; with body multipliers the real
figure is higher and is a **calibration dial** (set baseValues / restrict situations so an outer-planet
station isn't overpowered) rather than an unknown.

**P3 re-author plan (turnkey once P1 nodes exist):**
1. Generator: `lab-experiments.tsv` + the 65 cfgs → plain `Experiment`/`EXPERIMENT_DEFINITION` configs.
2. Map each experiment's instrument requirement (the `Module:*LabExperimentPackage` column) to a curated
   AXE part; decide whether to keep the DLL tags or hardcode `requirements = Part:<name>` (prefer the
   latter — no compiled dependency, precise control).
3. Remap the ~22 stock `UnlockTech` names → AXE nodes (blocked on P1; ship a remap table now).
4. Calibrate baseValues against the body-multiplier model so the crewed-lab budget lands where intended.
