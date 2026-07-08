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
| `basicCapsules` | `int_mercuryCapsule` | | `spaceStationPrototypes` | `life_stationHabitation` |
| `earlyFlightControl` | `gnc_spacecraftRCS` | | `spaceStationDev` | `life_convertedStageStation` |
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

## ⚠️ sync-seed caveat

`tools/sync-seed.ps1` vendors RP-1's whole `Science/` folder into `seed/Science/`. Because RP-AXE
now ships a **curated** science subset (see the Phase-2 commit) and this **remapped** CrewScience
copy, a blind `sync-seed.ps1` run would (a) clobber the curated `seed/Science` and (b) re-introduce
RP-1's CrewScience under `seed/Science/Experiments/CrewScience/` with RP-1 node names — producing
**duplicate `EXPERIMENT_DEFINITION` ids** against this folder. Before re-running sync-seed, drop
`Science` from its `$folders` list (or re-apply the curation + delete the re-vendored CrewScience).
