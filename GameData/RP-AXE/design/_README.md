# design/ — RP-AXE transformations & new content

Everything RP-AXE *does* to the seed lives here, as ModuleManager patches and new config. Every
patch applies **after** the vendored seed and after RO/RealFuels — use `:AFTER[...]` (e.g.
`:AFTER[RealismOverhaul]`) or `:FINAL`, and tag our own files `:FOR[RP-AXE]` so other patches can
order against us. Never edit `../seed/`; change behaviour here.

Folders map to the transformation passes (see `docs/ARCHITECTURE.md` and `docs/TASKS.md`):

| folder | pass | what it does |
|---|---|---|
| `Contracts/` | A | de-rail (strip `ProgramActive`), swap custom CC types to stock where possible (`RP1ReturnHome`→`ReturnHome`, `RP1CollectScience`→`CollectScience`), delete guard riders (`AvionicsCheck`, `VesselBuiltAt`), strip dead reward lines |
| `Programs/` | B | "Activate [X] Program" contracts + `AcceptContract`-gating that replaces `ProgramActive` (opt-in, any order) |
| `Rewards/` | C | rebuild per-contract `rewardFunds`/`rewardScience` (program `baseFunding` redistributed) |
| `EntryCosts/` | D | rebuild part `entryCost` funds sink (LRTR values + RO core hand-priced) |
| `Tree/` | F | future/ahistorical nodes + placements for near/far-future part mods (mind `OrphanNode`) |
| `Science/` | E | science pacing tune (global multiplier; frontier nodes kept expensive) |
| `Avionics/` | G | command part guaranteed at `start`, remove inert proc-avionics parts, early antenna/instrument placement |

For custom CC types that can't be cleanly swapped to stock (e.g. `HorizontalLanding`,
`DownrangeDistance`, `ReachMach`), the triage decides per-type: tweak-in-cfg, strip, or implement
in `Source/AXE` (`AXE.dll`). See the Pass-A research task in `docs/TASKS.md`.
