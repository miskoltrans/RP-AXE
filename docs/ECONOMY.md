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
| Part unlocks (1,826 parts; upgrades are free — SCIENCE.md §5d) | 5.46M | `AxePartCost.cfg` |
| Engine-config unlocks (449) | 0.53M | `AxeEntryCostMods.cfg` |
| **Lump total** | **~19.82M** | |
| Vehicles | ~20M (assumed) | see §5 — **not yet measured** |

> **Part unlocks are a buy-everything figure — realized spend is ~3.2M, not 5.99M.** A playthrough that
> buys the two cheapest parts on every node it researches spends 2.71M on parts plus configs (SCIENCE.md
> §5c), i.e. **~8% of lifetime funds — the same share RP-1 spends on part unlocks**. The 5.99M belongs in
> this table as the ceiling; it is not what the income schedule has to cover. Re-measured 2026-07-28, when
> the part-cost calibration pass also corrected three silent misclassifications (+2.2%); re-measured again
> 2026-07-30, when upgrades stopped being sold (−125k measured, SCIENCE.md §5d).

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

> **Reversed by [§13](#13-programs-end--2026-07-30-conclusion-is-earned-not-chosen).** The playtester
> was right and this section was wrong: programs now do end, and this contract is the ending. Retitled
> again to *"Conclude Program: X"*. The "no deactivate path" statement above is history, not current
> behaviour.

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

Channel 1 still totals **exactly 24,000,000**, now split 15 capstones (3,065,619) / **137** staged
objectives (15,972,343) / 35 bonuses (4,962,038). *(Read 138 / 15,976,779 / 4,957,603 as first
written; the dedupe pass below dropped one staged objective, since a name that exists twice in `seed/`
is one contract at runtime. The 24,000,000 is unaffected — it is normalised, not summed.)* Three
invariants are asserted by the generator and would previously have failed silently:

- **The two patch files must key disjoint contract sets.** `%rewardFunds` is set-or-create and
  therefore *overwrites*; two patches on one contract would silently keep the last, not the sum.
  Capstone-labelled objectives are excluded from the spread, which makes the sets disjoint by
  construction (15 + 137, zero overlap) — and it is asserted, not assumed.
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

- ~~**Nothing tells the player Fundraising exists.**~~ **CLOSED 2026-07-29 — see §12.**
- ~~**Not verified in game.**~~ ✅ **CONFIRMED LIVE 2026-07-30, from a career rather than the UI.**
  The cold load merged `strategyCommitRange = 0.5, 0.75, 1` with **no CustomBarnKit `wrong size`
  warning**, and Contract Configurator loaded **373 of 373** against the cache's own 373 node count
  (so the two-run under-load did not bite). The staged patches are on the contracts —
  `AtmoSat` / `FirstPolarSat` / `FirstSolarSat` all read `rewardFunds = 25862`, `maxCompletions = 1`
  — and the merged cache carried **188 paying types totalling 23,999,994 raw**, i.e. Channel 1
  reconciling to target *after* ModuleManager, not just in the generator's own arithmetic. (Measured
  on the 2026-07-29 cold load, hence 188 = 15 + 138 + 35; the dedupe pass has since made it 187. The
  figure to re-measure against is whatever `build_economy.py` last printed, never a number pasted
  here.)
  **The runtime proof is stronger than a screenshot:** `saves/default3` holds an active
  `FundraisingCampaignCfg` at **`factor = 0.49`** with `SpaceCenter/Administration` at **`lvl = 0`**.
  A 0.49 commitment at building level 1 is unreachable under CustomBarnKit's 0.25 cap, so the block
  is live at runtime and not merely in the cache. (0.49 rather than 0.50 because
  `factorSliderSteps = 20` quantises the slider.) Effective yield **108.4 funds/reputation** against
  the old **33.2**, matching the 109.3 this section predicts for a clean 0.5.
  The same save shows the pass working end to end: funds **−348 → 208,712**, reputation 596 → 431 as
  the converter diverts incoming gains, and the launchpad at `lvl = 0.333` — the **200 t rung §10 cut
  to 90,000**, bought at 130,000 cumulative.
- **Era-scaling of old contract rewards** (§7) is untouched, and still the lever for repeatable
  contracts paying 1950s reputation in 1975.

## 12. Fundraising was invisible — 2026-07-29, and it is load-bearing, not flavour

§11 left this as the last open item on the list and called it a discoverability problem. It is, but
the sizing was understated: **Channel 2 is not a bonus the player can decline. The early tree is
balanced on it.**

`tools/gate_feasibility.py`, at the first-orbit gate:

| | funds |
|---|--:|
| Channel 1 alone, banked before the gate | 572,852 |
| gates demanded there (pad L4 + R&D L1) | 590,000 |
| **margin on Channel 1 alone** | **−17,148 — BLOCKED** |
| Channel 2 at Administration L1 | +56,386 |
| **both channels** | **629,237 — clears by 39,237** |

So the entire first-orbit margin *is* Channel 2, and Channel 2 pays nothing until the player walks
into a building the game never mentions. A player who does not is hard-blocked at first orbit, and —
per §11c — a negative balance blocks launching and upgrading alike, so there is no way to trade out
of it and nothing in game names the cause. That is precisely the state the playtest save reached:
**596 reputation across 38 completed contracts, Administration never opened, −348 funds.**

### The conversion is flow-only, and that is correct

Decompiled `Strategies.Effects.CurrencyConverter`: `OnEffectQuery` reads `qry.GetInput(input)` — the
amount moving in *this* transaction — and is registered only between `OnRegister`/`OnUnregister`, so
it sees nothing while the strategy is inactive. Reputation banked beforehand is unreachable for the
rest of the career.

**Back-paying that balance on activation would be the wrong fix.** The rate rises with Administration
level *and* with the commitment slider, so converting a hoard at activation time would reward
*delaying* activation — a worse incentive than the one being fixed, and a direct inversion of §11a,
which exists to stop Administration level gating the rate twice. Flow-only is right. Only the silence
is the bug.

### "Start small, raise it later" is real — via a stock bug AXE deliberately keeps

The nudge tells the player to activate at whatever commitment they can afford and raise it later.
That advice is only honest if the commitment can actually be changed, so it was decompiled rather
than assumed. `Strategies.Strategy`:

```csharp
public double LeastDuration   => FactorLerp(minLeastDuration, maxLeastDuration);
public double LongestDuration => FactorLerp(minLeastDuration, maxLeastDuration);   // <-- least, not longest
```

Both properties lerp the **least**-duration *fields*, and those fields are never assigned for a
config-defined strategy — `StrategySystem.LoadStrategies` calls
`GetStrategyType("FundraisingCampaignCfg")`, no class of that name exists, so it falls back to the
base `Strategy` and nothing but a subclass could set them. Both therefore evaluate to **0**, which
means:

- the expiry branch (`if (LongestDuration != 0.0) … Deactivate()`) never runs — the campaign runs for
  the whole career rather than the 1200–1600 days its config asks for;
- `CanBeDeactivated`'s `dateActivated + LeastDuration < now` is satisfied immediately — the player can
  stop and restart at a higher commitment whenever they like, for the `initialCostReputation` of 4–70
  (lerped, ~7 at the stock 0.05 slider default), which is nothing at AXE's 146k career scale.

This is the exact stock bug **KSPCommunityFixes' `StrategyDuration` repairs**, and
`AxeCommunityFixes.cfg` deliberately does not take it (the one KSPCF patch of five that AXE refuses).
That refusal was already recorded as "it would put an expiry clock on Channel 2" — it also, less
obviously, is what makes re-committing free of a waiting period. **If `StrategyDuration` is ever
taken, this section's advice and §3's ceiling both stop being true.**

### The fix

`Source/AXE/AxeFundraisingTip.cs` — a one-time Space-Center popup, reusing the `AxeTipState`
per-career store `AxeAirlaunchTip` introduced for exactly this. It fires once, when reputation first
reaches **10** (the point where activation is affordable, so the advice is actionable rather than
premature; the reputation forgone below that threshold is worth about a thousand funds), and only if
no reputation→funds conversion is already running.

That last check is **structural, not by name** — it walks the active strategies for a
`CurrencyConverter` whose `input`/`output` are Reputation/Funds, read via `Traverse` as
`AxeEconomySelfTest` already does on the same class. Matching `"FundraisingCampaignCfg"` by string
would be BUG-CLASSES family 1: a renamed or replaced strategy would leave the check passing while the
player earned nothing. On any exception it reports "conversion is live" and stays quiet — an
unreadable strategy system must not produce a false alarm telling a player to switch on something
they already run.

### It shipped broken, and the playtest caught it the same day

Confirmed in game 2026-07-30 — by firing at `saves/default3`, **a career that had been running
Fundraising at 0.49 commitment for years.** A false positive, and the cause is worth keeping:

`StrategySystem.OnLoad` does `StartCoroutine(OnLoadRoutine(node))`, and that routine opens with
`yield return null`. So for at least one frame the scene has a live `StrategySystem.Instance` whose
`Strategies` is a **non-null empty list**. The check guarded against `null` only, so it read empty as
"nothing is converting", and — worse — it had already latched `_evaluated`, so the wrong answer was
final for that scene visit.

**Empty is not absent.** It is the state a lazily-populated collection is in before its coroutine
runs, and a null guard does not distinguish them — BUG-CLASSES.md family 3, a check that looks
thorough and answers a question its data cannot yet support.

Fixed two ways, because either alone still misbehaves:
- an explicit readiness test (`Strategies.Count > 0`) before the verdict is formed. Sound because
  `LoadStrategies` creates every *defined* strategy and applies the saved nodes — `Strategy.Load` ends
  `isActive = true; Register();` — in **one synchronous pass**, so the count is either 0 or complete,
  and activation state is final the moment it is non-zero;
- **nothing load-order sensitive latches any more.** Only `Game.Modes != CAREER` does, since the mode
  is known immediately and never changes. Reputation not yet loaded, rep below threshold, strategies
  not yet populated are all *not-yet* conditions, and the addon respawns on every return to the Space
  Center, so leaving them retryable is what lets the nudge arrive on a later visit instead of being
  silently spent on a frame where nothing was readable.

The negative case is now the one that is verified; the positive case (a career that genuinely has not
activated Fundraising) has not been seen fire yet.

## 13. Programs end — 2026-07-30: conclusion is earned, not chosen

`Begin Program: X` had no counterpart. A chartered program stayed active for the rest of the career,
so its member contracts — including the 66 repeatable ones — kept being offered forever, and §7's
`Program Bonus: X` was explicitly worded to say so.

Programs now have a third state and an ending. **Inactive → Active → Concluded**, mirroring RP-1
(`Program.IsActive => !IsComplete && acceptedUT != 0`, and `CompleteProgram` does
`ActivePrograms.Remove(p)`). Only **Active** satisfies `ProgramActive`, so concluding a program is
what stops its contracts being offered — one rule, and the 250 program-gated seed contracts follow
from it.

### The abandon path was designed, then cut on the data

The ask was closure for *obsolete* programs, which implies abandoning one you cannot or will not
finish. So: can every chartered program actually be finished? **34 of 35 can.** The single exception
was `TargetedSats`, whose objective `FirstGEOSat` is gated `Any{CommercialApplications2,
GEOCommNetwork}` — both deliberately un-chartered because RP-1 ships them `isDisabled`. One upstream
config artefact does not justify a player-facing abandon door, a forfeit rule, an undo, and a second
contract per program. It justifies a build gate. **Cut:** abandoning a started program, revoking a
charter, re-chartering after conclusion, any guard against over-chartering, and a programs UI.

(`NeptuneMoonLandings` looked like a second case — its only objective `landingTriton` appeared to be
gated by `OuterGasGiantSurvey`. It is not: see the dedupe fix below.)

### Shipped

- **`AxeProgramHandler.Conclude()`** + a `concludedProgram` save key. Additive, so pre-existing saves
  load as "nothing concluded" with no migration.
- **`ConcludeProgram`** behaviour (`Source/AXE/Contracts/ConcludeProgram.cs`), on every
  `AXE_Complete_*` contract. Fires on **`OnCompleted`, not `OnAccepted`** like its mirror
  `ActivateProgram`: the contract sits Active for one frame while `AxeInstantComplete` waits for
  `Root.ContractState == Active`, and pulling its own `ProgramActive` requirement inside that window
  is precisely the state CC answers by failing the contract.
- **`ProgramActiveRequirement` now defaults `checkOnActiveContract = false`** — a deliberate
  divergence from RP-1, and load-bearing rather than cosmetic. With `true`, CC re-checks requirements
  on contracts that are already Active, and `ContractRequirement.RequirementsMet` responds to one
  going unmet by calling `Contract.Fail()`, which in stock runs `PenalizeFailure()` and posts a red
  failure message (both verified by decompile). Collecting a program's completion bonus while any of
  its repeatable missions was in flight would therefore have **fined the player for finishing the
  program**. With `false`, conclusion stops the *offering* only: an offered contract that stops
  meeting requirements is `Withdrawn`, which has no penalty path, and anything already accepted stays
  flyable.

### A build gate, and two bugs it found

`tools/build_economy.py` now proves every objective can actually be offered, and **fails the build**
if pruning leaves a program with none. This is BUG-CLASSES family 1 by construction:
`CompleteContractRequirement` resolves its target by name against a dictionary of finished contracts,
so an unreachable or misspelled objective never matches and **logs nothing** — it would just strand
the program active for the whole career, invisibly.

Writing the gate needed a contract→gating-program map, which turned up a second silent defect. Two
contract names exist twice in `seed/` (`FirstTundraSat`, `landingTriton`) because RP-1 deduped at
runtime in its own plugin; AXE deletes the redundant copy with MM in
`design/Contracts/DedupeContracts.cfg`. The generator was scanning `seed/` naively, so **whichever
copy the directory walk happened to hit last won** — deciding this tool's answers about a contract's
title, `CAPSTONE` label, and gating program from a file that does not survive to runtime. For
`landingTriton` the two copies are gated by *different* programs, which is where the phantom
`NeptuneMoonLandings → OuterGasGiantSurvey` dependency came from. `scan_seed` now skips what the
dedupe patch deletes.

The two fixes, both visible in the regenerated config:

- `FirstGEOSat` was carrying **11,089 funds no player could ever collect**. Pruned; `TargetedSats`
  now stages over 5 objectives instead of 6, so its own slices rise 11,089 → 13,307.
- `landingTriton` is read from the surviving copy (title *Triton Landing (Uncrewed)*, gate
  `NeptuneMoonLandings`), so the program is concludable on its own.

**No funds moved.** Channel 1 still totals exactly 24,000,000; the only redistribution is inside
`TargetedSats`, which was previously paying part of its budget into an unreachable contract.

### Player-facing

`Program Bonus: X` → **`Conclude Program: X`**. The description has three jobs, all of which the
earlier wording would have got wrong once closure existed: name the consequence *before* the click
(missions vanishing from *Available* with no warning reads as the mod breaking), promise there is no
deadline (AXE gates nothing by time, so nothing expires — unsaid, players feel rushed into concluding
before they have farmed the repeatables), and note that the repeatable missions go too. The
completion message says what happened: *"X is closed. Its missions are no longer offered."*

The charter notes in `AxeProgramValue.cfg` said *"Chartering is permanent: the program stays active
for the rest of the career and its contracts remain available to fly."* That was the one line a player
read while choosing, and conclusion made it false. It now states both halves: concluding is one-way,
and nothing forces or expires it.

**Not yet confirmed in game.** Needs a career that concludes a program, to see the contracts leave
*Available* and an accepted member contract survive. Contract Configurator under-loads new contract
configs on the first run and its own "N out of N" summary lies, so run twice before believing it.

## 14. The launch bill — 2026-07-30: AXE had no per-unit part cost at all

A part has **two** prices in KSP. `entryCost` is what R&D charges once to unlock it; `cost` is what the
VAB charges *every time you fly it*. AXE authored the first (`AxePartCost.cfg`, calibrated in §5c) and
never authored the second.

RP-1's lived in `Tree/TREE-Parts.cfg` — `%cost` on 3,612 parts. AXE replaced that file wholesale for its
tree placement and module tagging, and the pricing half went with it. Same shape as the
`ModuleNonReentryRated` dormancy and the `CrewSettings.cfg` G-limits: **a file dropped for what its name
said it was, when half of it was something else.** Third instance of that lesson.

### The symptom was incoherence, not cheapness

Named parts fell back to whatever their own mod happened to ship — unnormalised across three orders of
magnitude. Measured against RP-1:

| part | AXE was | RP-1 | |
|---|--:|--:|---|
| `ROE-SmallLC` — Small Launch Clamp | 150 | 1 | 150x |
| `launchClamp1` — TT18-A | 200 | 1 | 200x |
| `RO-BasicFilmCamera` | 7,500 | 500 | 15x |
| `ROE-RD100` (engine) | 1 | 320 | 0.003x |
| `ROE-RZ20` (engine) | 1 | 301 | 0.003x |

You paid more for a launch clamp than for the engine above it. `TREE-Parts.cfg` was never an *added*
cost layer — it was RP-1 **normalising** every part onto one scale, pushing clamps and fairings down to
~1 and pulling engines up to 80–11,596.

### What shipped

`tools/build_fly_costs.py` → `manifest/part-fly-costs.tsv` recovers RP-1's own numbers for **1,542**
parts and fills **317** AXE-only parts from RP-1's median funds/tonne in the same `costcat`.
`build_tree.py` emits `AxePartFlyCost.cfg` = baseline × **`launch_cost_scalar`**.

Two things the data corrected during the build:

- **Procedural parts need no special case.** RP-1 prices them **0**, because their own modules compute
  cost from dimensions (`ProceduralPart.costPerkL`, RealFuels `TANK_DEFINITION.baseCost = k * volume`)
  via `seed/ProcCosts.cfg`, which AXE inherited intact. Restoring the zero is correct; a static cost
  would charge for the same hardware twice.
- **The fallback must key on `costcat`, not the KSP `category` field.** ModularLaunchPads structures
  report category `none`, which priced a 2,500 t launch base at **4,009,358**. `costcat` calls them
  `ground` (10 funds/tonne) and it becomes 25,000. Using the same taxonomy as `entryCost` means the two
  prices can never disagree about what a part *is*.

### The scalar is what ops and tooling became

RP-1 charged two things per launch that AXE cannot port, both stripped with `ModuleTooling*`:

- **Tooling** — `GetModuleCost` adds `d·l·costMultiplierDL` every launch, plus a 2% untooled penalty,
  against a one-off unlock of ~21,198 for a 1.65 m × 5 m tank. **AXE assumes optimal tooling** (user
  call), so only the per-launch dimension term is in scope: ~1.85x on tank hardware.
- **Ops** — `MaintenanceHandler.ComputeDailyMaintenanceCost` is `0.0002 × capital` per day, ×2 for
  launch complexes: **7.3%/year of facility capital, 14.6%/year for LCs**, offset by a `subsidyCurve`
  paying 25,000/yr in 1951 rising to 600,000/yr from 1967 and doubled at high reputation. It is a
  **clock**, and AXE deliberately has none, so there is no per-launch quantity to extract.

Neither converts cleanly, so both are folded into the scalar rather than modelled. Per-part cost already
scales with vehicle size, so a separate ops fee would double-count that.

### Calibration — 1.2, from a real career

Not from a target ratio. `saves/default3` reconstructed: 52 completed contracts paid 420,756 funds and
1,463 reputation; facilities cost exactly 190,000 (pad L3 + MC L2) and part unlocks 7,525, leaving
**~188,846 of launch spend** as the residual — cross-checked as ~62 launches at that career's 3,031
average craft cost.

**That save predates the §10/§11 payout work, and contract rewards are baked at generation.** Re-pricing
its 9 stale contracts to current values adds **244,692**, so income should read ~825,558 and launch spend
is **23.3% of income**, not the 33.4% the save shows. The restore alone lifts it to ~28%; the 1.2 scalar
lands it at **30.2%**, measured across the same 28 craft (1.32x).

### Two things this does not do

- **It does not move the procedural half.** `ProcCosts` prices from dimensions through expressions
  (`baseCost = 0.004 * volume`), so one ModuleManager multiplier cannot scale it. Procedural is ~51% of
  measured vehicle cost, so the knob currently has roughly half the authority its name implies. Its own
  pass.
- **Eight Far-Future fission tanks carry RP-1's own prices up to 39.3M** — 86% of the "one of each"
  total sits in five parts. Harmless while the colonization tier is deferred scaffold; unaffordable in a
  40M economy if it ever ships.

### §10's table was blind to all of this

`gate_feasibility.py` compared banked income against facility **gates** and never modelled the money
spent flying the missions that earn it — the largest recurring expense in the game. A launch-spend term
is now in both tables (`flown`), as
`objectives(era) × LAUNCHES_PER_OBJECTIVE × glow × DRY_FRACTION × FUNDS_PER_TONNE_DRY`.

**Read the two tables as a bracket, never separately.** The reference table assumes every launch in an
era flies that era's milestone-defining launcher and blocks from era B onward (era B alone: 28 objectives
× 4 launches × an R-7 = 1.8M). The floor table assumes the lightest vehicle that can do the job and
clears everywhere. Real play sits between, and nearer the floor — the 28 craft in `default3` are ~12 t
dry against an R-7's ~27 t. The weakest input is not any constant but that vehicle assumption.

`FUNDS_PER_TONNE_DRY = 597` is measured; **`massT` in `craft-prices.csv` is DRY** (`p.mass +
GetModuleMass`, no resources), so it must never be applied to a GLOW figure — hence `DRY_FRACTION`.
