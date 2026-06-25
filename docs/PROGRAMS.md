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
- `CrewedSpaceplaneDev` (7) — early/mid; ~1.2M (≈ CrewedOrbitEarly).
- `SaturnMoonLandings` (9), `JupiterMoonLandings` (5), `UranusMoonLandings` (5),
  `NeptuneMoonLandings` (1) — outer-moon landings, late; scale ~5–15M with OuterGasGiantSurvey /
  PlutoLandings. Tune later.

(35 programs funded in `Programs.cfg`; 40 distinct programs referenced by contracts. RP-1 also has 4
`RP0_PROGRAM_MODIFIER` variant-funding blocks we ignore.)

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

## M4 — program switcher (design)

Replaces RP-1's `ProgramHandler`. Pure-config + the `ProgramActive` requirement already stubbed in
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
