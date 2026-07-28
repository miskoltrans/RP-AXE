# RP-AXE Funds Economy (P3)

SSOT for the funds side of the economy pass. Read with [`SCIENCE.md`](SCIENCE.md) (science is the
*primary* gate; funds are the secondary axis) and [`PROGRAMS.md`](PROGRAMS.md) (the invariants this
sits inside). **Status: SHIPPED — loads clean in-game (372/372 contract types, AutoTest pass).**

> **Gotcha — validating new contract configs takes TWO runs.** The first KSP launch after adding
> `CONTRACT_TYPE` configs loaded **338 of 372**, silently missing exactly the 34 new ones, and
> Contract Configurator never even logged their `CONTRACT_GROUP` — no error, and its own summary
> line still read "338 out of 338", so it looks like a clean pass. The second run, with no changes
> at all, loaded 372/372. Contract Configurator's pass evidently reads the pre-patch database on the
> run that regenerates the ModuleManager cache. **Always re-run before concluding a contract config
> is broken**, and cross-check `Loaded N out of M` against the cache's own node count
> (`grep -c '^\tCONTRACT_TYPE$' ModuleManager.ConfigCache`) rather than trusting the summary.

---

## 1. The diagnosis — income was exactly zero

Not "too low". Zero. Every one of the 305 vendored contract types paid `rewardFunds = 0`, verified
both in the configs and in a playtest save's own completion records (19 completed contracts, no
funds on any of them). RP-1 had two funds taps and AXE removed **both**, each for a good reason:

1. **Program funding drip** — `Program.ProcessFunding` pays a Hermite curve over
   `nominalDurationYears`, ticked from `MaintenanceHandler`. It is a pure function of the calendar,
   not of missions flown. AXE does not gate time (no KCT, no deadlines, no upkeep), so free
   timewarp turns any per-time payment into infinite money. Unportable by construction.
2. **Skopos `maintenance_*` contracts** — the only funds-paying contracts in the vendored set
   (275–400 each), deleted by `design/Contracts/DisableSkoposMaintenance.cfg` as the same
   warp-for-money exploit.

RP-1's third leg, a reputation-scaled yearly **subsidy**, also went out with `RP0.dll`. What
survived pays reputation — and reputation had no use, because the subsidy it fed no longer exists.

**Consequence found by playtest:** the launchpad starts at a 25 t limit and the first upgrade, to
75 t, has to be bought. A career starts with 15,000. Orbital flight was therefore unreachable — a
hard block, not a balance problem. *(This paragraph read "for 19,000 funds" until 2026-07-28; that
figure came from the never-charged array slot — see the indexing box in §2. The step really cost
**75,000**, so the block was four times worse than diagnosed. It is 40,000 after the §6 re-shape.)*

## 2. Measured sinks — the denominator

Everything below is measured from this install, not estimated.

> ⚠ **The first entry of every `upgrades` array is never charged.** KSP charges
> `upgradeLevels[currentLevel + 1].levelCost` (decompiled `UpgradeableFacility`) and CustomBarnKit
> assigns `levelCost = upgrades[k]`, so `upgrades[0]` is the *starting* level's own cost and no
> player ever pays it — CBK only demands the slot exist, because it validates `len(upgrades) ==
> levels`. **Every per-step price in this document was one slot to the left of the truth** until
> 2026-07-28. Totals were near enough to survive; the pacing claims built on them were not.
>
> | | as documented | actually charged |
> |---|--:|--:|
> | Pad, first step (25→75 t) | 19,000 | **75,000** → 40,000 after §6 |
> | R&D upgrade 1 (unlocks T6–T8) | 113,000 | **451,000** |
> | R&D upgrade 2 (unlocks T9+) | 451,000 | **1,690,000** |
> | Mission Control, first step | 25,000 | **60,000** |

| Sink | Purchasable total | Source |
|---|--:|---|
| Launchpad (7 levels, 6 purchases) | 7.29M | `AxeFacilities.cfg` — **re-shaped 2026-07-28, §6** (was 10.33M) |
| Tracking station (11 levels, 10 purchases) | 2.53M | `AxeTrackingStation.cfg` |
| R&D (3 levels, 2 purchases) | 2.14M | CustomBarnKit default |
| Administration (3 levels, 2 purchases) | 0.71M | CustomBarnKit default |
| Mission Control (5 levels, 4 purchases) | 0.68M | `AxeFacilities.cfg` |
| Part unlocks (1,830 parts + 87 upgrades) | 5.56M | `AxePartCost.cfg` |
| Engine-config unlocks (466) | 0.55M | `AxeEntryCostMods.cfg` |
| **Lump total** | **~19.46M** | |
| Vehicles | ~20M (assumed) | see §5 — **not yet measured** |

> **Part unlocks are a buy-everything figure — realized spend is ~3.2M, not 6.11M.** A playthrough that
> buys the two cheapest parts on every node it researches spends 2.71M on parts plus configs (SCIENCE.md
> §5c), i.e. **~8% of lifetime funds — the same share RP-1 spends on part unlocks**. The 6.11M belongs in
> this table as the ceiling; it is not what the income schedule has to cover. Re-measured 2026-07-28, when
> the part-cost calibration pass also corrected three silent misclassifications (+2.2%).

**The R&D ladder is the load-bearing gate.** Its 100-science cap covers tiers 0–5 *exactly*; every
tier-6 node costs 101+. So R&D L2 (**451,000 funds**) is required to research anything past tier 5,
and L3 (**1,690,000**) for tier 9+ (**243 nodes = ~90% of the tree's science**). This is deliberate — it is
what makes funds a real tradeoff rather than texture. **But it is not priced by AXE:** those are
CustomBarnKit's stock defaults, inherited, and they are ~4× what this section claimed while the
off-by-one stood — so "the income schedule is sized to make those two purchases bite without
blocking" was never actually true of the numbers being charged. AXE gates its entire tree on this
ladder and has never set its price; see §6.

> ⚠ **This gate lives in the tree's cost table, not in a settings file.** CustomBarnKit's
> `scienceCostLimit = 100, 500, -1` gates by node **cost**, so the tier at which each cap bites is an
> emergent property of `tier_cost × scalar` in `tree/nodes.yaml` — a few percent on the scalar moves a whole
> tier across a cap and silently rewrites this paragraph. `build_tree.py`'s **`science cap gate`** asserts the
> T5/T6 and T8/T9 boundaries on every build (binding floor: `scalar > 0.715`; it is **0.72** as of
> 2026-07-28). See SCIENCE.md §4.

Per-launch vehicle cost is measured at **171–8,314 funds** for 0.2–3.75 t craft
(`tools/analyze_craft_costs.py`), but no orbital-class vehicle has been priced yet, so the ~20M
figure is an assumption, not a measurement. Propellant is genuinely negligible at any scale
(0–3 funds/tonne), so vehicle cost is hardware, not fuel.

## 3. The model — two channels, 40M target

**Target: ~40,000,000 lifetime funds** for a player who does everything — the lumps (~19.5M after
§2's corrections and §6's pad re-shape) plus a vehicle allowance of roughly equal size. Split 60/40.
**Both channels reach their share** — Channel 2 was re-derived on 2026-07-28 (`tools/rep_budget.py`)
and tops out at **22.9M against its 16M target** on the Normal preset; the earlier "~8.4M measured"
came from an undercount, see the box under Channel 2.

### Channel 1 — contract funds (24M budgeted, **36.7M paid**), `tools/build_economy.py`

> ⚠ **The same multiplier chain that was missed on Channel 2 applies here, and it is bigger.**
> `Contract.SetFunds` scales `rewardFunds` by `GetContractPrestigeFactor(prestige) ×
> contractFundsCompletionFactor × Career.FundsGainMultiplier` exactly as `SetReputation` does
> (Assembly-CSharp, `FundsCompletion = Round(completion * GetContractFundsCompletionFactor(prestige)
> * destinationWeight)`). AXE's generated program-completion contracts declare `prestige =
> Significant` (×1.25) and the capstones are mostly `Exceptional` (×1.5), against
> `FundsGainMultiplier = 1.2` on Normal — so the **×1.529** the channel actually pays is
> **36,702,661**, not the 23,999,999 `build_economy.py` balances to. Measured 2026-07-28 from the
> merged cache. `build_economy.py` divides a target across programmes and never models the
> multipliers, so its printed totals are pre-multiplier throughout — including the early-game check
> below, where the two sounding-rocket programmes really pay ~33,000 each, not 22,000.
> **Not adjusted — that is §6 item 1's call**, and it moves the same dial.

Money is **launch-gated**: you earn it by flying missions, never by waiting. Each program gets a
budget of `RP-1 baseFunding × 0.10476`, which keeps RP-1's judgement about which programs are big
while re-deriving the magnitudes for AXE's far smaller sinks (RP-1 budgeted ~229M because it was
also paying salaries and maintenance; AXE has neither).

That budget splits two ways:

> **The "50%" is per-program, not per-channel.** Only 14 of 34 chartered programs have a capstone,
> and they turn out to be the small ones, so the realized split across Channel 1 is **capstones
> 2,426,013 (10%) / completions 21,573,986 (90%)** — measured from the merged cache, total
> 23,999,999 against the 24,000,000 target. Do not read the two headings below as half the channel each.

- **Capstones (50%).** RP-1 hand-marks 17 contracts `Type: <color=red>CAPSTONE</color>` in their
  *description text* — the crowning mission of a program. It is player-facing markup rendered in
  Mission Control, **not a config field**, so it is scraped from `seed/Contracts`. 15 belong to a
  chartered program and are paid; the other two sit on `RepeatMoonLandingCrew` and the deprecated
  `CrewedSpaceplaneDev`. → `design/Contracts/AxeCapstoneFunds.cfg`
- **Program completion (50%, or 100% where there is no capstone).** A generated contract per
  program, gated on every one of its `complete_contract` objectives plus `ProgramActive`,
  auto-accepting and completing instantly. This is the half that reaches *every* program — 20 of 34
  have no capstone at all, including `CrewedLunar` and `CrewedMarsExp`, so without it whole eras
  would earn nothing. → `design/Programs/AxeProgramCompletion.cfg`

**Not paid:** `OPTIONAL` contracts (129) and plain `REQUIRED` objectives (153) pay reputation only,
which then converts through Channel 2. Records pay reputation only. Nothing repeatable-without-a-
launch pays anything, ever — that is the invariant that killed the Skopos maintenance layer.

*Early-game check* (printed by `build_economy.py`): the two sounding-rocket programs pay 22,000 each
= **44,000**, against a 15,000 start and the 40,000 first pad step — clears, but only after the
§6 re-shape. At the old 75,000 it did **not**: a rocket-only career had 59,000 and could not buy the
pad at all, which is precisely the block this whole section exists to remove. R&D L2 (451,000) then
needs the next several programs.

### Channel 2 — Administration (target 16M, **reaches 22.9M**), `design/Settings/AxeStrategies.cfg`

Reputation is the currency AXE's contracts actually pay and it has no other sink, so the
Administration building is where it becomes spendable. `FundraisingCampaign` is rescaled from
stock's 1,002–1,253 funds/rep to **125–157**. The `strategyCommitRange` (0.25 / 0.6 / 1.0 by
Administration level) is the pacing knob: early careers can convert at most a quarter of incoming
reputation.

> ✅ **Reconciled 2026-07-28 — the channel is not short; the "measurement" that said so was wrong.**
> Re-derived from the merged cache by **`tools/rep_budget.py`**. The 65,595 hand sum is not
> reproducible by any filter: the raw config sum across all 284 paying contract types is **105,542**,
> which is what the original ~114k assumption had roughly right all along.
>
> **And the config value is not what the player receives.** Contract Configurator hands
> `rewardReputation` to stock's `Contract.SetReputation`, which multiplies it by the contract's
> **prestige factor** (1.0 / 1.25 / 1.5 — every paying AXE contract declares one: 135 Trivial, 133
> Significant, 16 Exceptional) and by the difficulty preset's **`RepGainMultiplier`** (1.2 on Normal).
> That is a **×1.385** uplift, so a career actually banks **146,163 reputation** on Normal.
>
> | preset | RepGainMultiplier | career reputation | Channel 2 ceiling |
> |---|--:|--:|--:|
> | Easy | 1.6 | 194,883 | 30.6M |
> | **Normal** | **1.2** | **146,163** | **22.9M** |
> | Moderate | 1.0 | 121,800 | 19.1M |
> | Hard | 0.8 | 97,442 | 15.3M |
>
> Ceiling = every contract completed once, Administration L3, full commitment. **Against the 16M
> target the channel is at 1.43× on Normal and still 0.96× on Hard** — so 40M lifetime stands and no
> re-target is needed. What the ceiling does *not* say is that the money arrives on time: the
> commit-range cap means Administration L1 converts the same career at **4.9M** and L2 at 12.6M, and
> the channel is *more* back-loaded than Channel 1 (`CrewedMarsExp` alone carries 18,700 raw). The
> early-game shortfall is §6 item 1's problem, not this channel's size.
>
> Two mechanics found while grounding this, both load-bearing:
> - **`useTargetBodyForReward = false`** (`seed/Contracts/Groups.cfg`, root RP0 group, no child
>   override) suppresses stock's destination weight. Flipping it would multiply every deep-space
>   contract's reputation by that body's `RecoveryValue` — inherited from RP-1, leave it alone.
> - **Crew-recovery reputation never becomes funds.** Stock pays `reputationKerbalRecovery` (25 ×
>   `RepGainMultiplier`) **per kerbal** on every crewed recovery, but under
>   `TransactionReasons.VesselRecovery`, which is absent from the strategy's
>   `AffectReasons = ContractReward, ScienceTransmission, Progression`. So it accrues as a reputation
>   *balance* only. That is what keeps the 750-reputation gate at Administration L3 reachable even at
>   100% commitment (where every converted point is deducted from the gain), and it means crewed
>   flight spam cannot be farmed for money.

Two stock strategies are **deleted**: `PatentsLicensing` (science → funds) and
`OpenSourceTechProgram` (science → reputation, which Fundraising then turns into funds). Science is
the primary gate and is deliberately ~10× more abundant than the tree costs, so either path is
unbounded income. Full reasoning in the file header.

The **rate is the only thing AXE changes** on the kept strategies. `requiredReputationMin`/`Max` are
now left at stock's `-500` → `750` — they are **not a "window"** (§5) but a lerp over the commitment
slider, setting how much reputation you must *possess* to commit that hard. At AXE scale stock's own
numbers already land correctly: the gate never binds at Administration L1, wants 250 reputation at
L2 and 750 at L3, so it bites only in the first era and is irrelevant long before 750,000 funds of
Administration upgrades are affordable. `strategyCommitRange` remains the real pacing knob.

## 4. Settled decisions

- **Contracts, not a drip.** Income is attached to missions, never to elapsed time.
- **Not every contract pays.** Capstones + program completion only.
- **Not every program pays a capstone** — 14 of 34 have one; the rest pay via completion.
- **Aviation is not special-cased.** X-planes pay reputation like everything else; the parked
  "X-plane contracts pay money" idea in RESTART.md is superseded — sounding-rocket capstones cover
  the pre-orbit gap, so a player who ignores aviation is not stranded.
- **Declining a contract never costs reputation.** `RepLossDeclined = 0` across all four difficulty
  presets, verified live in a playtest save. Already true; no change needed.
- **The R&D science-cap ladder stays** as a deliberate funds tradeoff (user call, 2026-07-28).
- **Everything pays on completion, never in advance** — `AllowNegativeCurrency` removes the
  cash-flow problem an advance would solve (§5).
- **The strategy reputation requirement is left at stock.** It is a commitment-scaled lerp, not the
  availability window it looks like, and stock's `-500 → 750` already lands correctly at AXE
  magnitudes — so AXE patches the *rate* and nothing else (§5).

## 5. Open & closed

> **One thing is actually open here: the end-to-end payout run.** The three questions this section
> carried since the economy shipped were resolved on 2026-07-28 and are struck below, kept for the
> reasoning trail. Two were false alarms; the third was a live bug in `AxeStrategies.cfg` that was
> halving Channel 2.

- **Vehicle cost above 3.75 t is a deliberate guesstimate** (user call, 2026-07-28) — *not* an
  outstanding task. The ~20M allowance is a round "about the same as everything else" figure, and
  measuring it precisely was judged not worth a build-and-price exercise. Two things to know if it
  ever needs revisiting: the cost formulas hint it may be far too generous (RealFuels tanks price at
  0.002–0.015 funds/litre, so a 100 t propellant load is ~390 funds; avionics grows only as
  `capacity^0.46`), and the retune is one constant — `TARGET_LIFETIME` in `tools/build_economy.py`
  — plus a regenerate. Playtest feel is the intended signal, not a measurement.
- **End-to-end payout is unproven.** The contracts *load* (372/372) and correctly do **not** fire in
  a fresh career, but no run has yet driven a program to completion, so the `autoAccept` +
  `CompleteContract` chain has not been observed actually paying out. Needs a save with a finished
  program — the playtest save has 3 of `SuborbRocketDev`'s 4 objectives done, so completing
  `Downrange` would exercise both halves at once (capstone 11,000 + completion 11,000).
- ~~**`requiredReputationMax` semantics**~~ — ✅ **CLOSED 2026-07-28, and the assumption was wrong.**
  It is **not** a window. Decompiled `Strategies.Strategy`: `RequiredReputation =>
  FactorLerp(RequiredReputationMin, RequiredReputationMax)`, then `CanBeActivated` refuses if
  `Ceil(CurrentRep) < Floor(RequiredReputation)`. The pair are the **endpoints of a lerp over the
  commitment slider** — how much reputation you must *hold* to commit that hard. Stock's
  `-500 → 750` means "commit 0% for free, commit 100% once you are famous"; more reputation makes a
  strategy **more** available, never less, so the ceiling §3 was written to escape never existed.
  Activation-time only — it never deactivates a running strategy.
  **Consequence: the old widening was a live bug, now fixed.** `-1000000 → 1000000` demanded
  `Lerp(-1e6, 1e6, factor)` reputation: 200,000 at 60% commitment, 1,000,000 at 100%, against a
  ~114k lifetime total. The slider was pinned near **50%** for the entire career and Administration
  L3 (750,000 funds) bought nothing. Because `CurrencyConverter.OnEffectQuery` lerps **both** the
  share diverted and the rate off that same factor
  (`input × Lerp(minShare,maxShare) × Lerp(minRate,maxRate)`), Channel 2 was paying ~70 funds/rep
  against the budgeted 157 — **roughly half its 16M**.
  **Resolution (user call): stop patching it — stock's `-500 → 750` is already correctly scaled.**
  Against `strategyCommitRange`, the requirement at each Administration level's slider cap is −188
  (L1, never binds) · 250 (L2) · 750 (L3). A band-1 playtest already reached 117 reputation and a
  career pays ~114k, so the gate bites only in the first era and is irrelevant long before 750,000
  funds of Administration upgrades are affordable — the stock mechanic ("commit as hard as your fame
  allows") working as designed, with no patch to maintain. The three strategies that carried *only*
  a reputation override are no longer patched at all. If a stronger fame axis is ever wanted,
  **rescale** the pair against early-career reputation (hundreds, not the 114k lifetime total) and
  re-derive §3's 16M — never widen it.
  *Still worth an in-game look:* confirm the slider reaches 100% at Administration L3.
- ~~**Failure reputation**~~ — ✅ **CLOSED 2026-07-28: a false alarm, no work needed.** The "78
  contracts lose 10–750 reputation on failure" claim does not survive ground-truthing. Every one of
  the 296 `failureReputation` fields in the merged `ModuleManager.ConfigCache` is **0**, as are all
  249 in the vendored `seed/Contracts` (RP-1 upstream is the same — its only non-zero is the Skopos
  maintenance set, which AXE already deletes). The remaining 76 of the 372 contract types simply
  omit the field, and Contract Configurator defaults it to 0; that 76 is almost certainly where the
  "78" came from. Confirmed against the games' own saves rather than configs: decoding the stock
  `Contract` `values` CSV (index 7 = reputation-on-failure) across all three career saves, **every
  `ConfiguredContract` reads 0**. The only contracts carrying a failure penalty were 3
  `TourismContract` + 2 `CrossBelt` — the leaked stock/Kerbalism types, already killed for new
  careers by `AxeDisableStockContracts.cfg` (`7e3b58f`). Nothing to zero.
- ~~**Advance vs reward**~~ — ✅ **CLOSED 2026-07-28: everything stays on completion.** The case for
  `advanceFunds` was that it funds the build instead of reimbursing it — but that is a cash-flow
  *timing* problem, and AXE structurally cannot have one. `AllowNegativeCurrency = True` in all four
  presets (verified live in the cache and in the playtest save), so no player is ever blocked from
  building or launching for want of cash up front; they go negative and the next completion clears
  it. There is also no carrying period to fund — AXE has no KCT, so build and launch are one action.
  And neither paying family could use an advance anyway: program-completion contracts `autoAccept`
  and complete in the same frame, so advance and reward are indistinguishable, and a capstone is the
  crowning mission of a program already under way. Revisit only if `AllowNegativeCurrency` is ever
  turned off.
- **Commercial contracts as a paying family** was considered and dropped in favour of the simpler
  capstone/completion split. The Skopos programs still earn through their completion bonuses.

---

## 6. Solvency pass — 2026-07-28: the ladders were read one slot off, and the pad is re-shaped

Triggered by the part-cost calibration (SCIENCE.md §5c), which flagged that income looked far more
back-loaded than the sinks it pays for. Modelling it properly turned up a bigger and simpler
problem first.

### What was wrong

**The off-by-one (§2).** `upgrades[0]` is never charged. Every per-step facility price in this doc
named the wrong array entry, so the two purchases the income schedule was explicitly sized around —
the first pad step and R&D L2 — really cost **75,000 and 451,000**, not 19,000 and 113,000. The
`build_economy.py` early-game check was comparing 44,000 of sounding-rocket income against a 19,000
pad that does not exist; at the true 75,000 a rocket-only career was still hard-blocked, which is
the exact failure §1 says this whole layer was built to remove.

**The shape.** A minimum-path solvency model — pad level from each era's real vehicle mass, R&D from
the tier its hardware sits on, DSN from the target's distance, parts at 1–2 per node researched —
put the margin **negative at six of nine milestones**, worst at a crewed lunar landing (**−4.3M**).
Two independent causes: the first 15 programmes pay only **6.4%** of Channel 1, and **2.7M of pad
upgrades** (the 1,200 t and 3,000 t steps) land in the single era that also has to fund Apollo.

*(Model caveats: which pad level each era needs is a judgement, and per-launch vehicle cost is not
in it at all. Both make the real picture tighter than modelled, not looser.)*

### What was done

- **Prices corrected** throughout this doc, `AxeFacilities.cfg` and `build_economy.py`. Facility
  configs now carry the indexing rule inline so the next author cannot repeat it. The lump total
  moves 22.62M → **19.46M** — the totals barely moved, because summing the whole array happened to
  approximate summing the purchasable part; only the per-step numbers were badly wrong.
- **Launchpad re-shaped**: `0, 40000, 150000, 400000, 900000, 1800000, 4000000` — 7.29M
  purchasable, down from 10.33M, with the Saturn-class step at 1.8M rather than 3M. It was 56% of
  every lump sink in the game. The curve keeps its shape (each step roughly doubles, mass stays the
  gate) and the unlimited top stays deliberately expensive, since nothing in a normal playthrough
  needs it. This is AXE's own ladder — RP-1 had none, KCT replaced it — so nothing upstream is
  being overridden.

Modelled effect at the milestones, parts at 1/node: first orbit −57k → **−22k**, applications
satellites −453k → **−318k**, crewed lunar −4,289k → **−2,254k**, space station −2,710k → **−675k**.
Better everywhere, and the Moon-landing cliff is halved — but still short, which is what item 1
below is for.

### What is still open — deliberately, these are design calls, not bugs

1. **Income shape.** ⚠ **Re-model before acting: the deficits below are computed against
   pre-multiplier income and are therefore overstated.** Every figure in this section came from
   `build_economy.py`, which never models the prestige × `FundsGainMultiplier` chain the game applies
   on top (§3, Channel 1) — real payouts are **×1.529**. Whether the early-to-mid gap survives that is
   an open question, not a known shortfall. The measured statement of the problem is now: **income
   totals ~36.7M (Channel 1) + up to 22.9M (Channel 2) against a 40M target of sinks**, so the
   economy is more likely over-funded in aggregate and mis-*shaped* in time.
   As modelled pre-multiplier, the pad re-shape alone did not close the gap: the early-to-mid game
   stayed ~300k short and the Moon ~2.3M short. The tested fix is flattening the programme payout curve —
   `budget ∝ baseFunding^0.65` instead of `^1`, same 24M total — which keeps RP-1's judgement about
   which programmes are big (Mars still pays 30× a sounding rocket, down from 190×) while moving the
   first 15 programmes from 6.4% to **14.4%** of Channel 1. With both levers the model is positive
   at every milestone. It is one constant in `build_economy.py`. **Not applied — user call.**
2. **The R&D ladder is stock's, not AXE's.** 451,000 and 1,690,000 are CustomBarnKit defaults AXE
   never touched, yet the science cap is the primary gate the whole tree is built on. Pricing it
   deliberately (250,000 / 900,000 was the modelled candidate) is an open decision.
3. ~~**Channel 2's 114k reputation figure does not reconcile**~~ — ✅ **CLOSED 2026-07-28: re-derived,
   and the channel was never short.** The 65,595 was an undercount that no filter reproduces; the raw
   config sum is **105,542**, and after the prestige factor and `RepGainMultiplier` the career banks
   **146,163** reputation on Normal — **22.9M against a 16M target**. Lifetime stays ~40M and nothing
   is re-targeted. Now measured by **`tools/rep_budget.py`** rather than asserted, so it can be
   re-run when contracts change. Full detail and the two mechanics it surfaced (`useTargetBodyForReward`,
   crew-recovery reputation being unconvertible) are in the §3 Channel 2 box.
   *Residual, deliberately not chased:* the ceiling assumes every contract completed once — no real
   career does that — and the 26 unlimited-repeat types add an unbounded 18,168/round on top. Both
   make the true figure a range, not a point, and playtest feel is the intended signal.
