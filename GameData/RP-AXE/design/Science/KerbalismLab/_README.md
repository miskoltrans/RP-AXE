# design/Science/KerbalismLab — crewed-station lab science, integrated into AXE

**Path A (see [`docs/KERBALISMLAB.md`](../../../../../docs/KERBALISMLAB.md)):** vendor `KerbalismLabExperimentsExpandedContinued`
as its creator authored it (values, situations, bodies, crew, slots) and change only what AXE's
from-scratch tree + RO part set force. **Do not re-author the experiments.**

## Files

| file | source | notes |
|---|---|---|
| `Framework-1-Scaffold.cfg` | KerbalismScienceOnly `Internal.cfg` (trimmed) | creates `KERBALISM_GROUP_SETTINGS`, deletes `:FINAL`. **Not** `KERBALISM_HDD_SIZES` — AXE owns that. |
| `Framework-2-LabGroup.cfg` | KerbalismScienceOnly `StockGroups-Lab.cfg` | **generated** — the lab group + 6 base exps; techs remapped. |
| `Framework-3-LabProcessing.cfg` | KerbalismScienceOnly `Groups/LabExperiments.cfg` | verbatim; reads all techs from Framework-2. |
| `Framework-4-Host.cfg` | authored | adds the `Configure` "Laboratory Experiments" host to AXE crewed labs at `:FIRST`. |
| `Framework-5-BaseExperimentDefs.cfg` | KerbalismScienceOnly `ScienceDefs-Kerbalism.cfg` | **generated** — the 6 base lab `EXPERIMENT_DEFINITION`s, verbatim. Only those 6: the rest of that file is the Crew/Orbital/Unmanned alt-science system. |
| `Framework-6-ScienceCap.cfg` | authored | makes the authored `value` the actual payout (`@scienceCap = #$baseValue$`). See "Payout" below. |
| `InstrumentTagging.cfg` | fork, re-pointed | `*LabExperimentPackage` tags moved onto AXE/RO parts; ScienceBox clone deleted. |
| `Experiments/*.cfg` (65) | fork, **generated** | verbatim except `UnlockTech` remapped (+ marquee Mir/Kvant gates, + the single-body value scale). |

**Generated files come from `tools/build_kerbalismlab.py`** — do not hand-edit `Framework-2` or `Experiments/*`;
edit the script's `REMAP` / `MARQUEE` tables and re-run. This folder is design-owned (tech-remapped), so
`sync-seed` never touches it.

## Payout — why `scienceCap` matters more than `value` looks like it should

Kerbalism pays out on **`scienceCap`**, not `baseValue`:

```
ExperimentInfo:  DataSize        = baseValue  * dataScale        (applyScienceScale = true)
                 ScienceCap      = scienceCap * ScienceGainMultiplier
SubjectData:     ScienceMaxValue = ScienceCap * Situation.SituationMultiplier
                 SciencePerMB    = ScienceMaxValue / DataSize
```

A completed run collects `DataSize` MB, so it banks exactly `scienceCap × situationMultiplier`.
`baseValue` only sizes the data stream — and since Framework-3 sets `dataScale = size / baseValue`,
it cancels out of the data size too.

Framework-3 writes the group `value` to **`baseValue` only**, so every fork definition kept its
template literal `scienceCap = 180` and the whole catalogue paid a flat 180 × multiplier regardless of
what its creator priced it at. **`Framework-6-ScienceCap.cfg` is what makes `value` real.** Upstream
does this globally in `Patches-Global.cfg`, which AXE does not vendor; ours is scoped to `kerbalism_*`.

Without it the theoretical max is 13.07M instead of 1.49M. `tools/lab_budget.py --model both` contrasts
the two; it also fails loudly if any experiment's `scienceCap` drifts away from its `value` again.

## Balance — the near-Earth floor (2026-07-28)

An experiment gated to **one body** never earns a body multiplier, while everything beside it scales
from Earth ×1 up to Pluto ×30, times a biome sum of up to 20. The mod was priced on stock Kerbin scales
where home orbit *is* the game; under RSS home orbit is the starting line. A LEO station therefore
banked ~4.0k against a ~300k tree.

So `build_kerbalismlab.py` scales `value` ×10 for exactly the single-body-locked set (`+HomeBody`,
`+Oceanic`, `+Suns` — 17 experiments). Because they run nowhere else, the deep-space tail does not move:

| | before | after |
|---|---|---|
| LEO station | 4,023 | **28,224** |
| Earth + Moon base | 10,026 | 34,227 |
| theoretical max (all 32 bodies) | 1,468,583 | 1,494,179 (+1.7%) |

Uniform ×10 preserves the creator's *relative* pricing (the marquee astrophysics payloads are already
priced 25–50× the Earth-observation cubesats precisely because they are single-subject) and changes only
the global scale RSS broke. No situation, body, crew, duration, slot or data size is re-authored.

**Known dead content, left alone deliberately:** `EGOMDOAF`, `MEGCO`, `SWE-NEMO` (and the base `SALINE`)
run only `SrfSplashed`, which `design/Science/EarthScienceRemoval.cfg` zeroes on purpose so the home
planet cannot be grinded. Pricing them would be a false signal; the generator reports them instead.

## §4 tech remap — stock/CTT `UnlockTech` → AXE node

Philosophy: for crewed-**station** experiments, menu availability tracks **station capability** → the
Life-Support / station ladder, era-stepped, preserving the creator's early→late stagger. Runnability is
carried separately by the instrument requirement (§3 re-point). Lab unlocks at `int_orbitalLab` (T9):
techs ≤ T9 are "available with your first lab"; techs > T9 stagger as the station program grows.

| stock tech | AXE node | T | | stock tech | AXE node | T |
|---|---|---|---|---|---|---|
| `highAltitudeFlight` | `life_highAltCompartment` | 3 | | `advExploration` | `life_convertedStageStation` | 9 |
| `engineering101` | `life_openLoopECLSS` | 5 | | `advScienceTech` | `life_convertedStageStation` | 9 |
| `survivability` | `life_openLoopECLSS` | 5 | | `advConstruction` | `life_habitatModuleCatalog` | 9 |
| `basicScience` | `life_pressurisedCabin` | 5 | | `experimentalElectrics` | `life_habitatModuleCatalog` | 9 |
| `electrics` | `life_pressurisedCabin` | 5 | | `miniaturization` | `life_mirCore` | 10 |
| `generalConstruction` | `life_crewedExperimentBay` | 7 | | `advUnmanned` | `life_mirCore` | 10 |
| `spaceExploration` | `life_crewedExperimentBay` | 7 | | `heavyLanding` | `life_isru` | 10 |
| `scienceTech` | `life_crewedExperimentBay` | 7 | | `specializedScienceTech` | `life_largeObservationDome` | 11 |
| `electronics` | `life_crewedExperimentBay` | 7 | | `hydroponics` | `life_bioregenerativeECLSS` | 11 |
| `unmannedTech` | `life_crewedExperimentBay` | 7 | | `experimentalScience` | `life_largeStationModule` | 11 |
| `fieldScience` | `life_stationHabitation` | 8 | | `longTermScienceTech` | `life_largeScaleHabitat` | 12 |
| `precisionEngineering` | `life_stationHabitation` | 8 | | `aerodynamicSystems` | `life_stationHabitation` | 8 |

Slot-upgrade techs (in Framework-2): `advScienceTech` (+1 slot) → `life_convertedStageStation`;
`fieldScience` (field-reconfigure) → `life_stationHabitation`.

## Marquee Mir/Kvant gates (per-experiment override of the table above)

Ten iconic experiments gate on their thematic Mir module (T11) instead of their base tech — you fly an
ambitious station to earn them:

| module (T11) | experiments |
|---|---|
| `int_kvant1Module` (Astrophysics) | HaloSat, NICER, CALET |
| `int_kristallModule` (Materials-Processing) | SODI-Colloid, Platan, TPSMMO |
| `int_prirodaModule` (Earth-Observation) | ECOSTRESS, GEDI, BeaverCube |
| `int_kvant2Module` (EVA & Biology) | Tanpopo |

## §3 instrument re-point (which part carries each package)

6 packages had no AXE host (RO strips the stock donor) → re-pointed onto the equivalent RO/RP0* instrument;
the rest kept on their surviving donor. See `InstrumentTagging.cfg` for the full table. Two review-flagged:
Radar (kept on `SurveyScanner` pending a confirmed RO radar-altimeter part) and the crewed-star gating
(experiments require `Scientist:N` — confirm AXE kerbal leveling reaches those tiers).
