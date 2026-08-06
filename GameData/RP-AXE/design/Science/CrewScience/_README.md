# design/Science/CrewScience — RP-1 crewed-science, tech-remapped to AXE nodes

These 8 files are RP-1's `GameData/RP-1/Science/Experiments/CrewScience/*.cfg` (the crewed
capsule / cockpit / station / lunar-surface science suite), **localized to RP-AXE**: every RP-1
tech-node reference has been substituted for the equivalent AXE tree node.

## Why these live in `design/`, not `seed/`

RP-AXE's tree is a from-scratch rebuild with different node IDs. These files reference tech nodes
in **two** ways, and both must point at real AXE nodes or the experiment silently never becomes
available (`ResearchAndDevelopment.GetTechnologyState()` returns `Unavailable` with no error/log):

1. `techRequired = <node>` inside each `EXPERIMENT_DEFINITION` — the R&D gate.
2. `@PART[*]:HAS[#TechRequired[<node>]]:BEFORE[zzzKerbalism]` — *filter directives* that tag the
   crewed craft unlocked at that node so the station/lunar experiments attach to them.

A `design/` overlay can rewrite (1) but **cannot** rewrite (2) — you can't `@`-patch a patch's
`:HAS[]` clause. So the whole set is authored here with the node names substituted inline. The
files keep their original `:FOR[RP-0]` / `:*[RP-0-Kerbalism]` / `:BEFORE[zzzKerbalism]` pass tags
(those order the Kerbalism conversion — not a location concern), so they are NOT retagged
`:FOR[RP-AXE]`.

## Remap table (RP-1 node → AXE node)

| RP-1 node | AXE node | | RP-1 node | AXE node |
|---|---|---|---|---|
| `start` | `start` (unchanged) | | `earlySpaceStations` | `life_convertedStageStation` |
| `basicCapsules` | *(no gate — see below)* | | `spaceStationPrototypes` | `life_stationHabitation` |
| `earlyFlightControl` | `gnc_rcs` | | `spaceStationDev` | `life_convertedStageStation` |
| `improvedComms` | `tel_pcmTelemetry` | | `modularSpaceStations` | `life_modularHabitat` |
| `electronicsHuman` | `int_geminiCapsule` | | `largeScaleOrbitalCon` | `str_stationHubs` |
| `materialsScienceHuman` | `int_geminiCapsule` | | `improvedOrbitalConstruction` | `str_modularTrussSystem` |
| `lunarRangeComms` | `tel_deployableHighGainDish` | | `lunarRatedHeatshields` | `cmp_lunarReturnAblator` |
| `advancedUncrewedLanding` | `int_surveyorLanderBus` | | `lunarLanding` | `fd_deepThrottleLanding` |
| `surfaceScience` | `fd_deepThrottleLanding` | | `deepSpaceScience` | `fd_lunarSurfaceMobility` |

Targets are era-matched (not 1:1 — RP-1's crewed-lunar/station gating is finer-grained than AXE's
and several RP-1 nodes are `//Placeholder`). Every target was verified to exist in
`design/Tree/AxeTechTree.cfg` before use. `CockpitExperiments.cfg`'s four supersonic experiments
carry no tech gate in RP-1 and were left as-is.

## A capsule-generation node cannot be remapped 1:1 (fixed for basic, OPEN for second-gen)

RP-1's `basicCapsules` / `secondGenCapsules` are **single** nodes covering every capsule of a
generation. AXE deliberately scatters capsules across per-vehicle nodes, so there is no AXE node
that means "early capsule": the only common ancestors of the five basic-tier carriers
(`int_mercuryCapsule`, `int_vostokCapsule`, `life_pressurisedCabin`, `life_spaceplaneCockpit`,
`life_crewedExperimentBay`) are `start`, `life_highAltCompartment` and `met_weldedTank` — and the
nine second-gen carriers share exactly the same three.

Remapping such a node to one arbitrary capsule **orphans every other path**: a player who
researched `int_vostokCapsule` got a Vostok with a 2-slot Crew Science Configure whose only
selectable entry was "None", hard-blocking the `CollectCrewedScienceBasic` capstone. Nothing logs.

Rule: **when the RP-1 gate was a capsule-generation node, drop the gate** — the `gets*Experiments`
tag on the carrier part already restricts the setup to that tier, so buying the part *is* the gate.
Only keep a gate when it names a genuinely different technology (a dish, mapping optics, RCS).

Applied to `getsBasicCapsuleExperiments`. **Still open for the other three tiers**, where the same
remap over-gated — including five second-gen and two mature setups that RP-1 left at `start`:

| Setup | RP-1 gate | current AXE gate | note |
|---|---|---|---|
| Orbital Maneuvering | `secondGenCapsules` | `gnc_spacecraftRCS` | plausible — OMS is a real capability |
| Visual Acuity | `start` | `int_geminiCapsule` | over-gated |
| Star Occultation Navigation | `earlyFlightControl` | `gnc_spacecraftRCS` | should follow `gnc_rcs` |
| Power Tool Evaluation | `materialsScienceHuman` | `int_geminiCapsule` | wrong lane (EVA tooling) |
| Simple Organism Egg Growth | `materialsScienceHuman` | `int_geminiCapsule` | wrong lane — `bio_cultures`? |
| White Blood Cells / Sleep / Food / Work Tolerance | `start` | `int_geminiCapsule` | over-gated (4 setups) |
| Simple Navigation, Zodiacal Light Photography | `secondGenCapsules` | `int_geminiCapsule` | orphans Voskhod/Apollo |
| Ion Sensing Attitude Control | `electronicsHuman` | `int_geminiCapsule` | wrong lane — `elec_integratedCircuit`? |
| Night Image Intensification | `electronicsHuman` | `int_geminiCapsule` | wrong lane |
| Synoptic Terrain / Weather Photography | `start` | `opt_orbitalMapping` | over-gated (2 setups) |

`UHF/VHF Polarization` → `tel_deployableHighGainDish` and `Space Television Broadcast` →
`tel_pcmTelemetry` are correct: those name real, different technologies.

## sync-seed handling (resolved)

`seed/Science` is a wholesale verbatim vendor of RP-1's `Science/` folder EXCEPT this remapped
CrewScience (and the HardDrive files). `tools/sync-seed.ps1` now handles that automatically: after
copying `Science/`+`Tree/`, it **strips** the design-owned paths (`Experiments/CrewScience`,
`HardDriveConfigs.cfg`, `Tree/HardDriveUpgrades.cfg`) so a re-run can't re-introduce RP-1's originals
and duplicate these `EXPERIMENT_DEFINITION` ids. If you add another design-owned science file, add its
path to sync-seed's `$designOwned` strip-list too.
