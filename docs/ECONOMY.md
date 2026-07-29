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
>
> The two R&D rows are history twice over: that 3-level ladder was replaced by an authored 8-level
> one on 2026-07-29 (§8). The indexing rule itself still governs the new array.
> | Mission Control, first step | 25,000 | **60,000** |

| Sink | Purchasable total | Source |
|---|--:|---|
| Launchpad (7 levels, 6 purchases) | 7.23M | `AxeFacilities.cfg` — re-shaped 2026-07-28 §6 (was 10.33M); **200 t step 150k → 90k, 2026-07-29 §10** |
| Tracking station (11 levels, 10 purchases) | 2.53M | `AxeTrackingStation.cfg` |
| R&D (8 levels, 7 purchases) | 2.68M | `AxeFacilities.cfg` — **authored 2026-07-29, §8** (was 2.14M CBK default) |
| Administration (3 levels, 2 purchases) | 0.71M | CustomBarnKit default |
| Mission Control (5 levels, 4 purchases) | 0.68M | `AxeFacilities.cfg` |
| Part unlocks (1,830 parts + 87 upgrades) | 5.56M | `AxePartCost.cfg` |
| Engine-config unlocks (466) | 0.55M | `AxeEntryCostMods.cfg` |
| **Lump total** | **~19.94M** | |
| Vehicles | ~20M (assumed) | see §5 — **not yet measured** |

> **Part unlocks are a buy-everything figure — realized spend is ~3.2M, not 6.11M.** A playthrough that
> buys the two cheapest parts on every node it researches spends 2.71M on parts plus configs (SCIENCE.md
> §5c), i.e. **~8% of lifetime funds — the same share RP-1 spends on part unlocks**. The 6.11M belongs in
> this table as the ceiling; it is not what the income schedule has to cover. Re-measured 2026-07-28, when
> the part-cost calibration pass also corrected three silent misclassifications (+2.2%).

**The R&D ladder is the load-bearing gate** — it is the primary *funds* gate laid across science, AXE's
primary *progression* gate, and that makes funds a real tradeoff rather than texture. **It is now priced
by AXE** (§8, 2026-07-29). It was not until then: the inherited CustomBarnKit default put **89.7% of the
tree's science behind a single 1,690,000 purchase**, with the first wall (451,000) standing at the
applications-satellite era — the tightest point on the income curve. The authored ladder is 8 levels /
7 purchases, no step opening more than 18.8% of the tree bar the deliberately-expensive far-future top.

> ⚠ **This gate lives in the tree's cost table as much as in the settings file.** `scienceCostLimit`
> gates by node **cost**, so the tier at which each cap bites is an emergent property of
> `tier_cost × scalar` in `tree/nodes.yaml` — a few percent on the scalar moves a whole tier across a cap
> and silently rewrites this paragraph. `build_tree.py`'s **`science cap gate`** asserts all seven
> boundaries on every build. The caps sit at the geometric midpoint of each tier gap, which brackets
> `scalar` at **0.625 … 0.828** (it is **0.72**); the old 500 cap sat 0.8% under T9 = 504, i.e. one
> nudge from silently un-gating a third of the tree. See SCIENCE.md §4 and §8 below.

Per-launch vehicle cost is measured at **171–8,314 funds** for 0.2–3.75 t craft
(`tools/analyze_craft_costs.py`), but no orbital-class vehicle has been priced yet, so the ~20M
figure is an assumption, not a measurement. Propellant is genuinely negligible at any scale
(0–3 funds/tonne), so vehicle cost is hardware, not fuel.

## 3. The model — two channels, 40M target

**Target: ~40,000,000 lifetime funds** for a player who does everything — the lumps (~20.0M after
§2's corrections, §6's pad re-shape and §8's R&D ladder) plus a vehicle allowance of roughly equal
size. Split 60/40.
**Both channels reach their share** — Channel 2 was re-derived on 2026-07-28 (`tools/rep_budget.py`)
and tops out at **22.9M against its 16M target** on the Normal preset; the earlier "~8.4M measured"
came from an undercount, see the box under Channel 2.

### Channel 1 — contract funds (24M budgeted, **36.9M paid**), `tools/build_economy.py`

> ⚠ **The same multiplier chain that was missed on Channel 2 applies here, and it is bigger.**
> `Contract.SetFunds` scales `rewardFunds` by `GetContractPrestigeFactor(prestige) ×
> contractFundsCompletionFactor × Career.FundsGainMultiplier` exactly as `SetReputation` does
> (Assembly-CSharp, `FundsCompletion = Round(completion * GetContractFundsCompletionFactor(prestige)
> * destinationWeight)`). AXE's generated program-completion contracts declare `prestige =
> Significant` (×1.25) and the capstones are mostly `Exceptional` (×1.5), against
> `FundsGainMultiplier = 1.2` on Normal — so the **×1.536** the channel actually pays is
> **36,859,004**, not the 24,000,004 `build_economy.py` balances to. *(Was ×1.516 / 36,386,760 until
> the §10 payout re-shape moved raw funds toward the mostly-Exceptional capstones; the raw total is
> unchanged, so the whole difference is mix.)* Measured 2026-07-28 from the
> merged cache; recomputed from the generated configs after the AsteroidExploration recovery
> (§7) re-spread the scalar. `build_economy.py` divides a target across programmes and never models
> the multipliers, so its printed totals are pre-multiplier throughout — including the early-game
> check below, where the two sounding-rocket programmes really pay ~31,800 each, not 21,222.
> **Not adjusted — that is §6 item 1's call**, and it moves the same dial.

Money is **launch-gated**: you earn it by flying missions, never by waiting. Each program gets a
budget of `RP-1 baseFunding × 0.10106`, which keeps RP-1's judgement about which programs are big
while re-deriving the magnitudes for AXE's far smaller sinks (RP-1 budgeted ~229M because it was
also paying salaries and maintenance; AXE has neither).

That budget splits two ways:

> **The "50%" is per-program, not per-channel.** Only 14 of 35 chartered programs have a capstone,
> and they turn out to be the small ones, so the realized split across Channel 1 is **capstones
> 2,340,203 (10%) / completions 21,659,793 (90%)** — total 23,999,996 against the 24,000,000 target.
> Do not read the two headings below as half the channel each.

- **Capstones (50%).** RP-1 hand-marks 17 contracts `Type: <color=red>CAPSTONE</color>` in their
  *description text* — the crowning mission of a program. It is player-facing markup rendered in
  Mission Control, **not a config field**, so it is scraped from `seed/Contracts`. 15 belong to a
  chartered program and are paid; the other two sit on `RepeatMoonLandingCrew` and the deprecated
  `CrewedSpaceplaneDev`. → `design/Contracts/AxeCapstoneFunds.cfg`
- **Program completion (50%, or 100% where there is no capstone).** A generated contract per
  program, gated on every one of its `complete_contract` objectives plus `ProgramActive`. It appears
  in Mission Control as an offer once the last objective lands; accepting it completes it on the spot
  (§9). This is the half that reaches *every* program — 21 of 35
  have no capstone at all, including `CrewedLunar` and `CrewedMarsExp`, so without it whole eras
  would earn nothing. → `design/Programs/AxeProgramCompletion.cfg`

**Not paid:** `OPTIONAL` contracts (129) and plain `REQUIRED` objectives (153) pay reputation only,
which then converts through Channel 2. Records pay reputation only. Nothing repeatable-without-a-
launch pays anything, ever — that is the invariant that killed the Skopos maintenance layer.

*Early-game check* (printed by `build_economy.py`): the two sounding-rocket programs pay **84,804
each = 169,608**, against a 15,000 start and the 40,000 first pad step. *(They paid 22,000 each until
the §10 payout re-shape; that cleared the first pad step too, but nothing beyond it — see §10 for why
the first pad step was never the gate that mattered.)* At the pre-§6 price of 75,000 it did **not**
clear: a rocket-only career had 59,000 and could not buy the pad at all, which is precisely the block
this whole section exists to remove.

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
- ~~**Advance vs reward**~~ — ✅ **CLOSED 2026-07-28: everything stays on completion.** ⚠ **Partly
  wrong — see §10.** The `AllowNegativeCurrency` argument below holds for building and launching a
  vessel and does **not** hold for facility upgrades, which refuse on a hard `cost <= Funding.Funds`
  check. The conclusion (no advances) still stands; the reason given for it does not cover the gate
  that actually blocks a career. The case for
  `advanceFunds` was that it funds the build instead of reimbursing it — but that is a cash-flow
  *timing* problem, and AXE structurally cannot have one. `AllowNegativeCurrency = True` in all four
  presets (verified live in the cache and in the playtest save), so no player is ever blocked from
  building or launching for want of cash up front; they go negative and the next completion clears
  it. There is also no carrying period to fund — AXE has no KCT, so build and launch are one action.
  And neither paying family could use an advance anyway: a program-completion contract completes in
  the frame it is accepted, so advance and reward are indistinguishable, and a capstone is the
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

1. ~~**Income shape.**~~ — ✅ **CLOSED 2026-07-29: re-modelled with the multipliers, the gap survived,
   and the flattening shipped. See §10.** The open question below was whether the deficits were an
   artefact of `build_economy.py`'s pre-multiplier arithmetic. They were not: with the ×1.5 chain
   included, and with income counted only from eras *before* each milestone (which is the correct
   ordering — a pad has to be bought before the missions that pay for it can be flown), first orbit
   was 450,066 short and the Moon 1,702,225 short. `FUNDING_EXPONENT = 0.65` is now applied.
   Kept as written for the reasoning trail:
   ⚠ **Re-model before acting: the deficits below are computed against
   pre-multiplier income and are therefore overstated.** Every figure in this section came from
   `build_economy.py`, which never models the prestige × `FundsGainMultiplier` chain the game applies
   on top (§3, Channel 1) — real payouts are **×1.516**. Whether the early-to-mid gap survives that is
   an open question, not a known shortfall. The measured statement of the problem is now: **income
   totals ~36.4M (Channel 1) + up to 22.9M (Channel 2) against a 40M target of sinks**, so the
   economy is more likely over-funded in aggregate and mis-*shaped* in time.
   As modelled pre-multiplier, the pad re-shape alone did not close the gap: the early-to-mid game
   stayed ~300k short and the Moon ~2.3M short. The tested fix is flattening the programme payout curve —
   `budget ∝ baseFunding^0.65` instead of `^1`, same 24M total — which keeps RP-1's judgement about
   which programmes are big (Mars still pays 30× a sounding rocket, down from 190×) while moving the
   first 15 programmes from 6.4% to **14.4%** of Channel 1. With both levers the model is positive
   at every milestone. It is one constant in `build_economy.py`. **Not applied — user call.**
2. ~~**The R&D ladder is stock's, not AXE's.**~~ — ✅ **CLOSED 2026-07-29: authored, and re-levelled
   rather than just re-priced.** The modelled candidate here (250,000 / 900,000 on stock's 3 levels)
   was not taken: the defect was the ladder's *shape*, not only its magnitude. See §8.
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

## 7. Program bonuses — 2026-07-28: reframed as a payout, and AsteroidExploration recovered

**First live payout observed**, closing §5's last genuinely open item: a career drove
`SuborbRocketDev` to completion and banked **16,500** (`11,000 × 1.25 Significant × 1.2 Normal`).
The `autoAccept` + `CompleteContract` + `AXEInstant` chain works end to end.

It also surfaced the wording problem. The contract was titled *"Programme Complete: X"* and said the
programme *"is discharged"* — which reads as a state change that **does not exist**.
`AxeProgramHandler` has no deactivate path (`AllActive` only ever reads a set that is inserted
into), so a program stays active for the rest of the career and its member contracts keep being
offered. That is deliberate — §"Repeatable is fine; idle income is not" in
[`PROGRAMS.md`](PROGRAMS.md) — but nothing said so, and a playtester reasonably read the payout as an
ending. Retitled **"Program Bonus: X"** (matching the hand-authored `Begin Program: X` charters, so
the pair reads as one series) and the description now states outright that the program stays active.
The `AXEInstant` parameter reads *"Collect the bonus"*, not *"Discharge the programme"*.

**Defect fixed in the same pass — `AsteroidExploration` was paying nothing.** RP-1 funds it at
`baseFunding = 8,400,000` (4th richest of 35) but ships it with an **empty `OBJECTIVES` block**.
`load_programs` dropped any programme with no objectives, so it got no completion contract, no
capstone, and its whole share was silently redistributed to the other programmes — while remaining
chartered and fully playable with 6 gated contracts. `derive_objectives` now falls back to the same
source the capstone scrape already trusts (the `CAPSTONE`/`REQUIRED` label in the description
markup), gating it on `orbitCeres` + `orbitVesta`. Never silent: every derivation and every drop
prints a note, and a funded programme that *has* members but no usable ones now prints a WARNING.

Consequences, all intended:
- **Scalar 0.10476 → 0.10106.** The denominator grew by AsteroidExploration's 8.4M, so every other
  programme's payout falls ~3.5%. `SuborbRocketDev` completion 11,000 → 10,611. Channel 1 still
  balances to 24M config / **36,386,760 paid**.
- **35 completion contracts, up from 34.** AsteroidExploration pays 848,871 config (1,273,307 paid).
- **`(WIP)` stripped from 5 player-facing titles** (Asteroid Exploration + the four outer-moon
  landing programmes). It is an upstream RP-1 dev note; the charters already dropped it, so the two
  halves of the same programme disagreed in the contract list.
- **`CrewedVenusExp` / `CrewedExploration` remain skipped, correctly** — RP-1 funds them but AXE
  vendors no contracts for them and charters neither, so they are not AXE programmes. Now reported
  as notes rather than vanishing.

**Open, found here, not chased:** the anti-grind on repeatable contracts is a **clock**
(`rewardFactor = Log(Max(elapsedDays / expectedDays * 3 - 0.05, 1), 2) / 1.5607`, 0% immediately
after a completion → 100% after `expectedDays`, e.g. 135 for the sounding rockets). AXE does not
gate time, so free timewarp does not break the launch-gate invariant — each repeat still costs a
launch — but it does erase the pacing intent, reducing it to "warp 135 days between flights". The
payout does not scale with era either, so 1950s sounding rockets still pay ~40 reputation (~7,500
funds through Fundraising) in 1975. Era-scaling of old contract rewards is the lever, not programme
finality.

## 8. The R&D ladder — 2026-07-29: authored, and re-levelled rather than re-priced

Closes §6 item 2. The ladder AXE gates its entire tree on was CustomBarnKit's stock default, never
set by anyone. `design/Settings/AxeFacilities.cfg` `@RESEARCH` now owns it.

### What the mechanic actually is

Decompiled rather than assumed. `RDNode` picks `RESEARCHABLE` vs `FADED` on
`effectiveCost < RDController.ScienceCap`, where `ScienceCap` is
`GameVariables.GetScienceCostLimit(<R&D facility level>)` — a **hard refusal on node cost**, not a
hint or a discount. CustomBarnKit overrides that method with `NormLevelToArrayValue`, which indexes
`scienceCostLimit` by `RoundToInt(normLevel × (len-1))` — exact at any level count, so the array
generalises past stock's 3 entries the same way `@TRACKING` already does at 11. Two things worth
recording because they are not obvious from the config:

- **`-1` means unlimited, not literal −1.** CBK's `LoadValue(ref float[])` maps any negative to
  `float.MaxValue`. Without it, `cost < -1` would fade *every* node at max level.
- **Every per-level array must be exactly `levels` long.** CBK logs `scienceCostLimit wrong size` /
  `dataToScienceRatio wrong size` / `Wrong numbers of upgrade price for …` and silently falls back to
  **stock** for that one field — which would restore the 100/500 wall with no error visible in game.

### What was wrong

| | nodes | science | share |
|---|--:|--:|--:|
| L1 — free, cap 100 | 132 | 2,887 | **0.9%** |
| L2 — 451,000, cap 500 | 126 | 28,513 | 9.3% |
| L3 — 1,690,000, uncapped | 249 | 274,320 | **89.7%** |

One purchase opened 90% of the tree. The level you start with covered under 1%. And the *first*
wall — 451,000 to research anything past tier 5 — landed at the applications-satellite milestone,
which the §6 solvency pass put at −318k. That is the one that could stall a career: `scienceCostLimit`
refuses by cost, and a player at L1 has already researched every cheap node, so banked science has
nowhere to go. Progress stops until the funds appear.

### RP-1 is not the precedent — it deleted this mechanic

`RP-1/GameData/RP-1/CustomBarnKit.cfg` sets `scienceCostLimit = -1, -1, -1`, `upgrades = 1, 1, 1`,
`dataToScienceRatio = 1, 1, 1`; there is no `RESEARCH` entry in `KCTBUILDINGTECHS`, and RP0.dll's only
CBK patch just triggers a maintenance recalc. `scienceCostLimit` appears nowhere else in the repo.
It is deliberate — changelog **v3.0.0.0**: *"Remove RnD upgrades and researcher caps. Instead,
researchers cost a bit more per year in salary, and base research rate is a bit slower."* RP-1 had
this mechanic, judged it bad, and cut it; still cut at v4.4.0.0.

**AXE does not follow it, for a reason.** RP-1 could zero the cap because KCT still paced research by
*time* — salaried researchers producing research points per day, nodes taking real days. AXE cut KCT,
so it has no time gate at all. Zeroing this too would leave science pure bank-and-spend. AXE keeps the
mechanic (§4) and owns the numbers instead of inheriting them.

### The ladder

Eight levels, seven purchases. Caps sit at the **geometric midpoint** of the gap between adjacent tier
rates, so each boundary tolerates 15–40% of scalar drift either way.

| lvl | cap | opens | nodes | science | share | price |
|---|--:|---|--:|--:|--:|--:|
| L1 | 82 | T0–5 · sounding rockets → appsats | 131 | 2,887 | 0.9% | start |
| L2 | 265 | T6–7 · first crewed capsules | 85 | 15,229 | 5.0% | 25,000 |
| L3 | 404 | T8 · Apollo/Surveyor, lunar | 41 | 13,284 | 4.3% | 50,000 |
| L4 | 600 | T9 · stations, shuttle, Grand Tour | 58 | 29,232 | 9.5% | 100,000 |
| L5 | 865 | T10 · shuttle-era flagships | 54 | 38,880 | 12.7% | 200,000 |
| L6 | 1225 | T11 · Mir-class, Cassini | 52 | 54,243 | 17.7% | 400,000 |
| L7 | 1655 | T12 · modern robotic | 40 | 57,600 | 18.8% | 700,000 |
| L8 | −1 | T13+ · far future | 46 | 95,364 | 31.1% | 1,200,000 |

**Purchasable total 2,675,000, of which a career stopping at T12 — every node with real hardware short
of the deferred far-future band — pays 1,475,000 across six purchases**, against 2,141,000 across two
before. So the nominal total rises 25% while *realized* mid-game spend falls 31% and spreads out. All
of the increase sits in the top step, which is the endgame catch-all and deliberately expensive for the
same reason the launchpad's unlimited tier is: nothing in a normal playthrough needs it.

`dataToScienceRatio` is flattened to 1 at every level, matching RP-1. It is stock's transmission ratio
and Kerbalism owns transmission here, so it is very likely inert — RP-1 flattened it rather than rely
on that, and so do we. `unlockedFuelTransfer = 1` (turn-1 on-orbit refuelling) is unaffected by the
level count: CBK tests `normLevel > (unlockedFuelTransfer - 1.1)/(levels-1)`, true at level 0 for any
`levels`.

### The gate

`build_tree.py`'s `SCIENCE_CAPS` now asserts all seven boundaries and reports the range `scalar` may
take before one breaks: **0.625 … 0.828**, currently 0.72, both bounds set by the T12|T13 cap of 1655.
The old ladder's binding floor was 0.715 against a scalar of 0.72 — **0.7% of headroom**, on a
boundary that silently un-gates a third of the tree if it slips. That is what the midpoint placement
buys.

Two non-obvious nodes checked against the new caps: `parking` (the unsorted-parts catch-all) carries an
explicit cost of 999 rather than a tier rate, so it needs L6 — it is a detached root that gates nothing
and it needed the *top* level before, so this is a loosening. `start` is free and `experimental` /
`hire_JPL` / `hire_OKB` cost 1, all reachable at L1 as intended.

**Not yet verified in game.** Cold-load confirmation that CBK accepts an 8-entry `@RESEARCH` (the
`wrong size` fallback is silent) belongs with the next instance rebuild.

## 9. Program bonuses — 2026-07-29: made visible, because nobody had ever seen one

The payout chain from §7 was never broken. It was **invisible**, and that is a different bug.

`AXE_Complete_*` carried `autoAccept = true` and its only parameter, `AXEInstant`, self-completes on
the first `OnUpdate` after the contract turns Active. So the contract was offered, accepted and
completed inside one frame. It never sat in Mission Control's *Available* or *Active* list. All the
player ever saw was funds appearing.

Ground truth, from the playtest save (`saves/default3`, 4 programs chartered):

| contract | state | `viewed` | funds slot |
|---|---|---|---|
| `AXE_Complete_SuborbRocketDev` | Completed | **Unseen** | 16,500 |
| `AXE_Complete_SuborbRocketResearch` | Completed | **Unseen** | 16,500 |

Both paid, exactly as §7 measured. Both finished `viewed = Unseen` — the save records that the
player never opened either one. `EarlyXPlanes` and `EarlySatellites` correctly had not fired
(4 and 6 objectives outstanding), so there was nothing else to look at either.

**Fix: drop `autoAccept`.** The bonus now waits in Mission Control until claimed. One click, and it
buys two things a silent transfer cannot:

- the payout is *legible* — it lands attached to a named program, with a completion popup;
- a finished-but-uncollected program **advertises what it is worth**, which is the only in-game
  readout of the completion half of the budget. Previously nothing in the game showed a program's
  value at any point, before or after.

`declinable = false` / `cancellable = false` stay: `maxCompletions = 1` means a declined bonus is
gone for the career, and there is no reason to throw one away. `minExpiry = maxExpiry = 0` still
holds, so an unclaimed offer never withdraws — same rule as the Begin Program charters, which have
sat in Mission Control non-declinable and non-expiring all along (7 of them at once in the playtest
save) without clogging anything. Only programs whose every objective is already met are ever
offered, so the list stays short.

No funds changed. The generator emits the same `rewardFunds`; §3's split and totals are untouched.

`AxeEconomySelfTest`'s well-formedness check ran the *other* way — it asserted every completion
contract `autoAccept`s, on the reasoning that otherwise "it sits Offered forever and the AXEInstant
parameter never fires". That premise was half right: `AxeInstantComplete` does gate on
`ContractState == Active`, which is exactly why an offer waits instead of self-firing, and why
accepting it pays immediately. The assert is now inverted — an auto-accepted bonus is the defect.

### 9a. What a program is worth, stated on its charter

§9 fixed the payout being invisible *after* the work. The complementary gap was **before** it: both
funds contracts are unreadable until you have already earned them. The completion bonus is not
offered until every objective is met, and a capstone is not marked as anything special in the
mission list — RP-1's `CAPSTONE` label is scraped from description markup that AXE does not
re-render. So accepting a **Begin Program** charter — the one moment the player actually chooses
between programs — said nothing about the stakes.

`tools/build_economy.py` now emits a third file, `design/Programs/AxeProgramValue.cfg`, patching a
`notes` line onto each of the 35 charters:

> Worth at least 21,222 funds: 10,611 on its capstone mission, Downrange Milestone (5000 km), and
> 10,611 as a bonus once every objective is met. Your difficulty settings scale rewards on top of
> that, so the funds that land run higher. Chartering is permanent: the program stays active for the
> rest of the career and its contracts remain available to fly.

**`notes`, not `description`.** The flavour text is hand-authored in `ActivatePrograms.cfg` and this
file is regenerated, so appending to `description` would need either fragile MM regex surgery or a
`%description =` that silently reverts an edited line to whatever the generator last saw. `notes` is
a separate field, and the whole chain is decompiler-verified rather than assumed:
`ContractType.notes` is parsed from config → `ConfiguredContract.notes = contractType.notes` at
generation → `GetNotes()` → stock `Contract.MissionNotes()`, called from
**`MissionControlTextRich()`** — the Mission Control briefing pane, which is what you read before
clicking Accept. It renders under the `Objectives:` header, above the objective list.

**"At least"** is doing real work: the figures are base `rewardFunds`, and what lands is scaled by
contract prestige × `FundsGainMultiplier` (1.5× on Normal for the Significant-prestige bonus). The
lowest that product goes is Hard's `1.25 × 0.8 = 1.0`, so the stated number is never an overstatement
on any preset.

**Two gates, because this is a string-matched overlay** (BUG-CLASSES.md family 1). The generator
reports `35/35 charters priced` and warns on either half of a mismatch — a charter whose program is
not funded, or a funded program no charter can start. That only proves the *files* agree.
`AxeEconomySelfTest` adds the other half: it reads Contract Configurator's parsed model and fails on
any `AXE_Begin_*` with empty `notes`, which proves the patch actually *applied*. Charter → program
comes from each charter's own `ActivateProgram` behaviour, never from its name —
`AXE_Begin_EarlySatellitesHeavy` charters `EarlySatellites-Heavy`.

## 10. Cross-gate pass — 2026-07-29: the ladders were each sane and did not line up

Closes §6 item 1. Triggered by a playtest report that reads, in full: *"T3 is orbital tech, but I
still don't have enough money to upgrade the pad for an R-7 sized rocket — I manage because I have a
hydrolox engine."* That is not a balance complaint about one number; it is the economy and the tree
disagreeing about what era the player is in.

### The method — order by cash flow, not by lifetime totals

New tool: **`tools/gate_feasibility.py`**. Everything §3 does is a lifetime sum, and a lifetime sum
cannot see this class of defect. **A gate has to be bought before the missions that pay for it can be
flown**, so the tool counts income only from eras *strictly before* each milestone, and it derives
what pad level an era needs from the actual hardware the tree hands you there — joining
`manifest/engine-stats.tsv` to AXE nodes through `AxeEngineConfigGates.cfg` (the `CONFIG` gate is
what really unlocks a variant in career) and rocket-equationing the lightest 2-stage LEO launcher
available at each tier.

It audits all eight gates. Five came back clean and are recorded here so nobody re-checks them:

- **DSN tracking station** — every one of the 10 tech gates sits a tier *ahead* of the mission that
  needs its range (Jupiter precursors T8 ← step 3 gated at T7; Grand Tour T9 ← step 4 gated at T8).
  No block. Step 7 costs 1,000,000 (RP-1 verbatim) and buys range nothing in the solar system needs.
- **R&D `scienceCostLimit`** — the §8 re-levelling holds; it never binds before income at any milestone.
- **Science supply** — comfortable. 377 science to reach T3, against SCIENCE.md §3b's 82,802
  collectable by first orbit.
- **`craftSizeLimit`** — never binds before `craftMassLimit` at any level. Tightest point in the game
  is Saturn V's 110.6 m against pad L6's 120 m height: 8% margin.
- **Mission Control** — `ContractLimitOverrider` is correct. Contract Configurator's per-prestige cap
  counts **Active** contracts (`ContractState == 5`), not offered ones, so the permanently-parked
  `Begin Program` charters do not squat slots, and flattening all three tiers to `maxActive` can never
  be tighter than stock's own global cap.

### What was actually wrong

The **launchpad** ladder, and it was wrong in *time*, not in magnitude.

| milestone | tree hands you | pad | all gates | banked before | margin |
|---|---|---|--:|--:|--:|
| first orbit | R-7 8K71PS, 270 t | L4 | 650,000 | 199,934 | **−450,066** |
| appsats + first crew | Vostok 8K72, 305 t | L4 | 895,000 | 696,675 | **−198,325** |
| crewed lunar landing | Saturn V, 2,950 t | L6 | 3,820,000 | 2,117,775 | **−1,702,225** |

**This is the answer to §6 item 1's caveat: the multipliers do not rescue it.** The ×1.5 prestige ×
`FundsGainMultiplier` chain is already inside those `banked` figures. Nor does Channel 2 — measured
from the merged cache, the entire pre-orbit game banks **516 reputation, 0.4% of the career's
146,163**, worth 17,157 funds at Administration L1. The early economy is Channel 1 and nothing else.

The consequence is a **route filter**, not a difficulty curve. Against 217,090 banked at first orbit:

| route | node | GLOW | pad | cumulative | |
|---|---|--:|---|--:|---|
| R-7 8K71PS | `fd_orbitalSoviet` | 270 t | L4 | 590,000 | out of reach |
| Atlas B | `fd_largeChamber` | 118 t | L3 | 190,000 | only if you flew X-planes |
| Juno I | `pc_scoutSolids` | 29 t | L2 | 40,000 | fine |
| min-max kerolox | `fd_singleChamber` | 41 t | L2 | 40,000 | fine |
| min-max hydrolox upper | `cryo_hydroloxPrototype` | 17 t | L1 | **0** | free |

So the tree's own orbital spines were the *unaffordable* options and the cheapest path to orbit was
whatever minimised GLOW. That is what the playtester found. **The hydrolox route is left exactly as
it is (user call, 2026-07-29)** — for the record, `cryo_hydrogen` (T1, 1 science) →
`cryo_hydroloxPrototype` (T2, 3 science) buys 410 s of vacuum Isp when the best alternative is 277 s,
and none of the three costs the design intends it to carry survive in AXE: program time does not
exist (KCT is cut), reliability is off instance-wide, and LH2 tankage is not gated anywhere (all 38
`TANK_DEFINITION`s carry `LqdHydrogen` at `techRequired = NONE`). It is a real shortcut, deliberately kept.

### What was done — two dials, both already identified in §6

1. **`build_economy.py` `FUNDING_EXPONENT = 0.65`.** Programme budget is now `baseFunding^0.65`
   normalised to the same 24M, instead of `baseFunding^1`. RP-1's judgement about which programmes
   are big survives — Mars still pays **30×** a sounding rocket, down from 190× — while the first 15
   programmes move from **6.4% to ~14%** of the channel. Purely a redistribution in time; the
   lifetime total does not move. `SuborbRocketDev` 21,222 → **84,804**.
2. **Launchpad 200 t step 150,000 → 90,000** (`AxeFacilities.cfg`). This is the rung the tree's own
   spines need — Atlas B at 118 t, Titan II at 154 t. Purchasable total 7.29M → **7.23M**; the shape
   above the 200 t rung is untouched.

| milestone | before | after |
|---|--:|--:|
| first orbit (R-7) | −450,066 | −17,148 |
| appsats + first crew | −198,325 | **+1,140,276** |
| crewed lunar landing | −1,702,225 | **+1,130,020** |
| stations, shuttle, Grand Tour | +205,676 | +2,757,628 |

Channel 1 paid moves 36,386,760 → **36,859,004** (×1.536). The raw 24M is unchanged; the whole
difference is mix — the re-shape moved raw funds toward the capstones, 14 of whose 15 are
`Exceptional` (×1.5) against the completion bonuses' `Significant` (×1.25).

### Still open

- **The R-7 is a mass-*rung* problem, not a price one.** It is the only milestone still negative, and
  only by 17,148 (≈ break-even once Channel 2's 17,157 is counted). The rungs jump 200 → 500 t, and
  the R-7 (270 t), Vostok 8K72 (287 t) and Soyuz (308 t) all sit just above the 200 t rung — so the
  most iconic first-orbit vehicle in the game needs the 500 t pad. The fix is to re-rung
  (200 → 300 t), not to discount further: cutting the 500 t step would also cheapen Saturn I and
  Titan III, which are correctly priced there. Left as a design call.
- **§5's `AllowNegativeCurrency` reasoning has a hole, and it is exactly the load-bearing case.**
  "Advance vs reward" was closed on the grounds that `AllowNegativeCurrency = True` means no player is
  ever blocked for want of cash up front. That is **false for facility upgrades** — and, corrected in
  §11c, false for **launching** too, which is the half this bullet originally got wrong.
  Decompiled: `SpaceCenterBuilding.UpgradeFacility` refuses unless
  `CurrencyModifierQuery.RunQuery(StructureConstruction, −cost, 0, 0).CanAfford()`, and
  `CurrencyModifierQuery.CanAfford(Currency.Funds)` is `cost <= Funding.Instance.Funds` — a hard
  on-hand check that never consults `AllowNegativeCurrency`. `PreFlightTests.CanAffordLaunchTest` is
  the same story with no override button (§11c), so once negative you can neither launch nor upgrade —
  the flag lets a purchase *put* you there and then strands you. The escape hatch covers neither gate
  that blocks progression, which is why this whole section exists.
- **Era boundaries are a judgement.** `gate_feasibility.py`'s `MILESTONES` table hard-codes which
  programme pays in which era and which real vehicle defines each milestone. The direction of every
  finding above is robust to re-bucketing; the exact margins are not.
- **The launcher model is optimistic by construction** — perfect staging, no fairing/interstage/avionics
  margin, procedural-tank structure fractions. Real first orbital rockets come out 1.5–2.5× heavier
  than its floor, so it is a lower bound on the pad level an era needs, never a build target.

## 11. Channel 2's shape, and the payout cadence — 2026-07-29

§10 fixed how *much* the early game earns. This fixes *when* it arrives — twice, on two independent
mechanisms. Triggered by a playtest save (`saves/default3`) sitting at **−348 funds with 596
reputation banked and no strategy active**, unable to launch anything: 38 contracts completed, of
which exactly **four** had paid a single fund (two capstones, two program bonuses — 72,600 together
against 87,949 spent).

### 11a. Channel 2 was gated twice, and the second gate was quadratic

`Strategies.Effects.CurrencyConverter.OnEffectQuery`, decompiled, lerps **both** terms off the same
commitment factor `f`:

```
taken = qry.GetInput(Reputation) * ParentLerp(minShare, maxShare)
qry.AddDelta(Funds, ParentLerp(minRate, maxRate) * taken)
```

so the yield is `Lerp(minShare,maxShare,f) × Lerp(minRate,maxRate,f)` — **quadratic in `f`** — and
`strategyCommitRange` caps `f` by Administration level. At CustomBarnKit's default `0.25 / 0.6 / 1`
with stock's `minShare = 0`, Administration L1 paid **33.2 funds/reputation against L3's 157: 21% of
the rate.** That multiplied an input which §10 had already measured as back-loaded to **0.4% of
career reputation before first orbit**, so the pre-orbit game saw **0.09%** of the channel.

The doc called `strategyCommitRange` "the pacing knob". It was a *second* pacing knob, stacked on a
channel whose input is already paced by mission difficulty — reputation scales with how hard the
mission was, which is precisely why it is back-loaded. Nothing chose that; it was inherited.

**Two dials, both ceiling-neutral:**

1. **`@ADMINISTRATION strategyCommitRange = 0.5, 0.75, 1`** (`AxeFacilities.cfg`). AXE now owns this
   block — it was the last CustomBarnKit default doing load-bearing economy work, exactly as
   `@RESEARCH` was before §8. `upgrades` and `activeStrategyLimit` are deliberately left at CBK's
   values; the prices are sane at AXE scale and the slot ladder was not what was wrong.
2. **`minShare = 0.55`** (`AxeStrategies.cfg`). Lifts the floor of the share lerp so Administration
   level decides how *much* converts, not also how *well*.

| Administration | before | after | share of L3 |
|---|--:|--:|--:|
| L1 (start) | 33.2 | **109.3** | 21% → 70% |
| L2 (150,000) | 86.5 | **132.2** | 55% → 84% |
| L3 (563,000) | 157.0 | 157.0 | 100% |

> **The lifetime ceiling does not move.** It is measured at full commitment — L3, `f = 1` — where
> `Lerp(0.55, 1, 1) = 1.0`, identical to stock. Every figure in §3's Channel 2 table (22.9M on
> Normal, 15.3M on Hard) stands unchanged. This is a redistribution in **time**, the same kind of
> change `FUNDING_EXPONENT` made to Channel 1 and for the same reason.

Measured effect at the gate §10 could not clear: pre-orbit Channel 2 goes **17,157 → 56,386**, and
the first-orbit milestone banks **629,237 against a 590,000 gate — it now clears by 39,237**, where
Channel 1 alone was 17,148 short.

> ⚠ **`minShare` must never go to 1.0.** At full share the player banks no *contract* reputation at
> all, and the reputation **balance** is what stock's `requiredReputation` lerp checks at activation.
> Only crew-recovery reputation would accrue (`TransactionReasons.VesselRecovery`, absent from
> `AffectReasons`), which cannot reach 750 — so a 100% share would lock the player out of the very
> commitment level it was meant to serve.

**The reputation requirement now binds in the first era, and that is intended.** Against the new caps
the lerp asks 125 reputation at L1 (was −188, never bound), 438 at L2, 750 at L3. A fresh career at 0
reputation commits at whatever it can afford — `f = 0.2` needs −250, i.e. free — and raises the
slider as it earns fame. That is stock's "commit as hard as your fame allows" working as designed;
reaching 125 is one or two contracts. Do not patch it back.

### 11b. The payout cadence cliff — 21 of 35 programmes paid nothing until the very end

The completion bonus is all-or-nothing: not offered until **every** objective is met. For the 14
programmes with a capstone that is fine, because the capstone pays mid-programme. For the other 21 it
meant zero income for the whole programme — and three of them are **consecutive**, right where
vehicle costs step up:

| programme | budget | objectives | mid-programme payment (before) |
|---|--:|--:|---|
| SuborbRocketDev | 84,804 | 4 | ✓ capstone |
| SuborbRocketResearch | 84,804 | 4 | ✓ capstone |
| EarlyXPlanes | 101,147 | 6 | ✓ capstone |
| **EarlySatellites** | 155,173 | 5 | ✗ **none** |
| **EarthObservationScience1** | 160,434 | 6 | ✗ **none** |
| **CommNetwork** | 102,241 | 3 | ✗ **none** |

A player paid at the midpoint of two programmes in a row then hit **fourteen launches with no
income**. That is a shape defect, not a magnitude one.

**Fix: `build_economy.py` stages the completion half across the programme's own objectives.** The pot
splits into `non-capstone objectives + 1` equal slices — one paid on each objective as it is flown,
one retained as the Program Bonus so the collectable payout §9 made visible still exists. New
generated file `design/Programs/AxeProgramObjectiveFunds.cfg`, using the same `%rewardFunds` overlay
`AxeCapstoneFunds.cfg` already uses. `EarlySatellites` now pays 38,793 six times instead of 232,758
once.

Channel 1 still totals **exactly 24,000,000**, now split 15 capstones (3,065,619) / 138 staged
objectives (15,976,779) / 35 bonuses (4,957,603). Three invariants are asserted by the generator and
would previously have failed silently:

- **The two patch files must key disjoint contract sets.** `%rewardFunds` is set-or-create and
  therefore *overwrites*; two patches on one contract would silently keep the last, not the sum.
  Capstone-labelled objectives are excluded from the spread, which makes the sets disjoint by
  construction (15 + 138, zero overlap) — and it is asserted, not assumed.
- **No funds are created or lost by shared objectives.** Three contracts are objectives of two
  programmes each (`KarmanLine`, `first_OrbitRecover`, `FirstComSat`). Each is paid once from the
  richer claim, and the loser **keeps that slice on its own bonus** rather than leaking it — which is
  why `EarthObservationScience1` carries a double-size bonus. Channel 1 is asserted to reconcile.
- **Nothing repeatable carries funds.** Every funds-paying type in the merged cache is
  `maxCompletions = 1`; there are **0** repeatable funds-paying contract types. That is §3's
  launch-gate invariant, and staging is the change most likely to break it.

`AxeEconomySelfTest` gains a fourth check, because a count cannot see the failure that matters: if
one of the two patch files stopped applying, the combined count would still look healthy and the
budget would still sit inside tolerance. It now asserts the **design property** — every
`AXE_Complete_*` must have at least one `CompleteContract` objective that itself pays — and reads
`strategyCommitRange` live from `GameVariables.GetStrategyCommitRange`, which also catches
CustomBarnKit's silent per-field "wrong size" fallback reverting `@ADMINISTRATION` to stock.

### 11c. Correction to §10 — a negative balance blocks launching too

§10's open-questions list states that `AllowNegativeCurrency = True` is *"true for building and
launching a vessel and false for facility upgrades"*. **The first half is wrong**, and it is what the
playtest save actually hit. Decompiled:

```
PreFlightTests.CanAffordLaunchTest.Test()              =>  (double)launchCost <= fundsAvailable
PreFlightTests.CanAffordLaunchTest.GetProceedOption()  =>  null
```

There is no `AllowNegativeCurrency` term, and `PreFlightCheck.runNextTest` builds an **Abort-only**
dialog when `GetProceedOption()` returns null (`OnDismiss = Abort` as well), so a failed
affordability check has no override. `EditorLogic` adds the test unconditionally in career.
`AllowNegativeCurrency` only suppresses the clamp inside `Funding.AddFunds`/`SetFunds` — it lets a
part purchase or a rollout push the balance negative, and then **strands the player there**, unable
to launch or to upgrade.

So the escape hatch §5 leaned on to close "advance vs reward" covers *neither* gate that blocks
progression. Both halves of that premise are now falsified. **Not reopened here** — 11a and 11b move
income earlier, which is the same relief an advance would buy, and reopening it is a design call.
But the reasoning that closed it no longer stands, and the failure mode is a hard stop with no
in-game explanation rather than a slow squeeze.

### What is still open

- **Nothing tells the player Fundraising exists.** Reputation is the currency AXE's contracts pay, it
  converts only on the way *in* (`OnCurrencyModifierQuery` intercepts transactions, never the
  balance), and a player who banks reputation before activating the strategy loses that conversion
  **permanently**. The playtest save reached 596 reputation across 38 completed contracts having
  never opened Administration. Silent and irreversible, and no amount of rate tuning addresses it —
  this is a discoverability problem, and the natural fix is the one §9a used for programme value: say
  it where the player is already looking.
- **Not verified in game.** The `@ADMINISTRATION` block needs the same cold-load confirmation §8's
  8-entry `@RESEARCH` does, and for the same reason: CustomBarnKit's size check is silent.
- **Era-scaling of old contract rewards** (§7) is untouched, and still the lever for repeatable
  contracts paying 1950s reputation in 1975.
