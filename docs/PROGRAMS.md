# Programs & economy backbone (M3 + M4 reference)

This is the data both M3 (Pass C reward distribution) and M4 (program switcher) consume. It is
*derived analysis*, not shipped config: program funding comes from RP-1's `Programs.cfg` (reference
only — we do **not** run RP-1's program system), and the "gated contracts" counts come from
`program = X` references in our vendored `seed/Contracts/`.

Regenerate with the two extraction commands in this file's git history (awk over `Programs.cfg` +
`grep -roE "program = …"` over the seed).

## Program funding × membership

Sorted by `baseFunding` (≈ progression order, early/cheap → late/expensive).
`~funds/contract = baseFunding ÷ nGated` — the flat starting point for Pass C before capstone weighting.

| Program | baseFunding | curve | nGated | ~funds/contract |
|---|--:|---|--:|--:|
| SuborbRocketDev | 210,000 | SlowRampup | 7 | 30,000 |
| SuborbRocketResearch | 210,000 | SlowRampup | 10 | 21,000 |
| CommNetwork | 280,000 | – | 5 | 56,000 |
| TargetedSats | 420,000 | – | 7 | 60,000 |
| EarlySatellites | 532,000 | MildBackloaded | 8 | 66,500 |
| CommercialApplications1 | 560,000 | MildRampup | 10 | 56,000 |
| EarthObservationScience1 | 560,000 | MildRampup | 10 | 56,000 |
| SkoposCommercialApplications0 | 610,000 | MildRampup | 16 | 38,125 |
| GEOCommNetwork | 700,000 | MildBackloaded | 4 | 175,000 |
| CommercialApplications2 | 800,000 | MildBackloaded | 12 | 66,666 |
| EarlyLunarProbes | 800,000 | – | 5 | 160,000 |
| EarlyXPlanes | 800,000 | BimodalBackloaded | 14 | 57,142 |
| SkoposCommercialApplications1 | 800,000 | MildBackloaded | 15 | 53,333 |
| EarlySatellites-Heavy | 875,000 | – | 6 | 145,833 |
| SkoposCommercialApplications2 | 900,000 | MildBackloaded | 24 | 37,500 |
| CrewedOrbitEarly | 1,200,000 | MildBackloaded | 9 | 133,333 |
| UncrewedLunarSurface | 1,375,000 | MildBackloaded | 8 | 171,875 |
| SkoposCommercialApplications3 | 1,500,000 | MildBackloaded | 41 | 36,585 |
| EarlyInnerPlanetProbes | 2,100,000 | Frontloaded | 6 | 350,000 |
| CrewedOrbitAdv | 2,200,000 | MildBackloaded | 5 | 440,000 |
| JupiterObservation | 4,000,000 | – | 7 | 571,428 |
| SmallBodiesFlyby | 4,000,000 | – | 3 | 1,333,333 |
| MarsSurfaceExp | 4,800,000 | – | 11 | 436,363 |
| MercuryExploration | 4,800,000 | – | 5 | 960,000 |
| VenusSurfaceExp | 4,800,000 | – | 5 | 960,000 |
| CrewedOrbit | 5,200,000 | Backloaded | 14 | 371,428 |
| OuterPlanetFlyby | 5,400,000 | – | 6 | 900,000 |
| SaturnObservation | 5,500,000 | – | 11 | 500,000 |
| AsteroidExploration | 8,400,000 | – | 6 | 1,400,000 |
| EarlyLunarHabitation | 9,600,000 | Flat | 10 | 960,000 |
| OuterGasGiantSurvey | 10,800,000 | – | 13 | 830,769 |
| EarlyEarthSpaceStation | 14,300,000 | Mid | 7 | 2,042,857 |
| CrewedLunar | 15,720,000 | StrongFrontloaded | 7 | 2,245,714 |
| PlutoLandings | 25,200,000 | – | 7 | 3,600,000 |
| CrewedMarsExp | 40,000,000 | Mid | 10 | 4,000,000 |

### Referenced by contracts but NOT funded in Programs.cfg (assign funding in M3)
These appear as `program = X` gates but have no `RP0_PROGRAM` baseFunding — pick values from
sibling tiers:
- `CrewedSpaceplaneDev` (7) — **deprecated** in RP-1 (`isDisabled`); we leave it un-chartered (M4),
  so no funding needed unless re-enabled.
- `SaturnMoonLandings` (9), `JupiterMoonLandings` (5), `UranusMoonLandings` (5),
  `NeptuneMoonLandings` (1) — outer-moon landings, late; **chartered in M4** (so they can be offered)
  but still unfunded; scale ~5–15M with OuterGasGiantSurvey / PlutoLandings. Tune later.

(35 programs funded in `Programs.cfg`; 40 distinct programs referenced by contracts. RP-1 also has 4
`RP0_PROGRAM_MODIFIER` variant-funding blocks we ignore.)

## Economy model — the ground rules M3 sits inside

**Time is not gated (by design):** no KCT / build time, no program deadlines, no upkeep. Timewarp is
free and unlimited. Consequence: **money can never be a time-driven scarcity engine** — any per-time
income is farmable by warping. So the economy rests on two invariants:

1. **The launch is the gate.** A fund reward is legitimate iff earning it — and earning it *again* —
   requires flying hardware. Effort = building and launching a vehicle is the real cost; money tracks
   missions actually flown, and timewarp buys you nothing.
2. **Repeatable is fine; idle income is not.** A contract may repeat freely ("spinning content") —
   each completion consumes a new launch. A one-shot "operate / maintain X for N days" reward is also
   fine: a durability achievement, still gated by a launch. The *only* forbidden shape is **income you
   can re-collect from already-deployed assets without launching anything** — because under free
   timewarp "wait" is free, so any no-launch repeat is infinite money. (This, not repetition, is why
   Skopos's perpetual `maintenance_*` contracts had to go: monthly reputation from a network already in
   orbit, collected by warping.)

Income is therefore **effort-gated, not finite** — you can always earn more by flying more, never by
waiting. Money is a solvency/efficiency layer (it punishes overbuilding and failed missions), not the
point — the tech tree + contract objectives are the progression spine.

**Currencies are fungible via the stock Administration building.** RP-AXE keeps the stock strategies
(Fundraising Campaign rep→funds, Patents Licensing science→funds, Outsourced R&D / Unpaid Research
funds→science) — we simply don't re-suppress them (`RP0.dll`, which repurposed Admin for Programs /
Leaders, is gone). Reputation and science both cash out to funds at the player's discretion, so M3
need not agonise over *which* currency a contract pays — total value per era is what matters.

**Already actioned — Skopos recurring disabled.** Because rep→funds conversion is live, Skopos's
perpetual `maintenance_*` contracts (auto-accept, monthly reputation) were the one time-farmable
currency source = a warp-for-money exploit. Deleted in
`design/Contracts/DisableSkoposMaintenance.cfg`; the one-shot "establish the network" masters stay.

### ⚠ TODO (balance) — rescale stock strategies to RP-AXE magnitudes
The stock strategies are tuned for **stock-KSP** currency magnitudes (thousands of funds, single-digit
science). At RP-AXE / RSS scale (millions of funds, RP-1 science values) the default conversion rates
and per-Admin-level commitment caps will be near-useless or absurd. Rebalance them — conversion
percentages, min/max commitment, and the per-Admin-level active-strategy limits — against real per-era
income and launch costs. Hook already present: `GameData/Squad/Strategies/StrategiesCustom._cfg`
(disabled template; enable/patch via `:FOR[RP-AXE]`). Do this **after** M3 sets per-era income, so the
conversion rates can be sanity-checked against actual numbers.

## M3 — Pass C reward distribution (plan)

For each program, spread `baseFunding` across its gated contracts as per-contract `rewardFunds`:
- Start flat at `~funds/contract`.
- **Weight the capstone heavier** than stepping-stones — the capstone(s) are the program's
  `OBJECTIVES { complete_contract = … }` in `Programs.cfg`. Suggested split: capstone ×2–3, the
  rest share the remainder.
- `rewardScience` = a modest supplement only (Kerbalism experiments remain the main science source).
- Global Funds/Science multipliers (difficulty settings) are the final trim knob.
- Sanity rule (invariant): each era's total income must comfortably cover that era's **per-launch
  vehicle costs** (the dominant RSS drain), not just part entry costs.

## M4 — program switcher ✅ DONE (config + code)

**Status:** implemented and (charters-side) complete. `AxeProgramHandler` ScenarioModule + the
`ActivateProgram` behaviour + a real `ProgramActive` requirement all live in `AXE.dll`
(`Source/AXE/`). Charters are authored in `design/Programs/ActivatePrograms.cfg` — **all 35 live
programs** referenced by seed contracts now have a "Begin Program: …" charter, wired into an
onboarding DAG (theme + funding order). The 5 programs RP-1 marks `isDisabled = true`
(CommercialApplications1/2, GEOCommNetwork, CrewedOrbit, CrewedSpaceplaneDev) are **deliberately
left un-chartered** so their contracts stay dormant, matching RP-1. The 4 outer-moon-landing
programs are chartered but still need M3 funding.

Design (as built):

Replaces RP-1's `ProgramHandler`. Pure-config + the `ProgramActive` requirement implemented in
`AXE.dll`:

1. For each program `P`, author an **"Activate [P] Program"** contract (`design/Programs/`),
   always offered once basic prerequisites (tech/era) are met, trivial to accept.
2. Member contracts keep their existing `REQUIREMENT { type = ProgramActive; program = P }`.
3. Make `ProgramActive` real (the M2 stub returns true): a small `AxeProgramHandler` ScenarioModule
   holds the set of started programs; accepting/completing "Activate [P]" adds `P`;
   `ProgramActive.RequirementMet` returns whether all listed programs are in that set.
   *(Pure-CC alternative: `ProgramActive` checks whether the `Activate_P` contract is accepted/
   completed via CC's own contract state — avoids a ScenarioModule but is clumsier for many programs
   and gives no UI. Prefer the ScenarioModule; it's the hook for a future "set your own goals" UI.)*
4. Result: opt-in themed bundles, **any order** (ahistorical), no funding/clock/confidence economy.
   Early programs gate on this for onboarding; late/exotic ones can be left fully open.

Depends on M2 validating (contracts must actually load before gating them is meaningful).
