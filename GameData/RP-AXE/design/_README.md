# design/ — RP-AXE transformations & new content

Everything RP-AXE *does* to the seed lives here, as ModuleManager patches and new config. Every
patch applies **after** the vendored seed and after RO/RealFuels — use `:AFTER[...]` (e.g.
`:AFTER[RealismOverhaul]`) or `:FINAL`, and tag our own files `:FOR[RP-AXE]` so other patches can
order against us. Never edit `../seed/`; change behaviour here.

Folders map to the transformation passes (see `docs/ARCHITECTURE.md` and `docs/TASKS.md`):

| folder | pass | what it does |
|---|---|---|
| `Contracts/` | A | **fixups only** — dedupe + Uranus/Neptune moon-group plumbing. The 14 custom CC types are implemented in `AXE.dll` under their registered names (D6, `Source/AXE/Contracts/`), so contracts load verbatim — no broad config type-swap |
| `Programs/` | B | "Activate [X] Program" contracts + `AcceptContract`-gating that replaces `ProgramActive` (opt-in, any order) |
| `Rewards/` | C | per-contract `rewardFunds` (`ProgramRewards.cfg`) + the ×1.25 funds trim (`FundsTrim.cfg`) |
| `EntryCosts/` | D | **parts unlock FREE** (D8) — `ZeroEntryCost.cfg` (`@PART[*] %entryCost=0`) + `Source/AXE/FreePartUnlock.cs`. The entryCost funds-sink was abandoned; launch cost is the only sink |
| `Tree/` | F | future/ahistorical placements (`AxePlace_*`), orphan browser, marking, **and the M6 `StartParts.cfg`** (repoint RP-1's `unlockParts` "Starting Parts" → `start`) (mind `OrphanNode`) |
| `Science/` | E | RP-1 ×1.0 pace (×0.8 trim reverted, D9) + `EarthScienceRemoval.cfg` (no sub-40 km home-planet science) |
| `Settings/` | G | (no `Avionics/` folder — Pass-G shipped as `Tree/StartParts.cfg`.) Avionics axed; stock `ModuleCommand` control; inert proc-avionics parts **kept** as probe cores |

For custom CC types that can't be cleanly swapped to stock (e.g. `HorizontalLanding`,
`DownrangeDistance`, `ReachMach`), the triage decides per-type: tweak-in-cfg, strip, or implement
in `Source/AXE` (`AXE.dll`). See the Pass-A research task in `docs/TASKS.md`.
