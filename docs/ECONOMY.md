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

**Consequence found by playtest:** the launchpad starts at a 25 t limit and upgrades to 75 t for
19,000 funds. A career starts with 15,000. Orbital flight was therefore unreachable — a hard block,
not a balance problem.

## 2. Measured sinks — the denominator

Everything below is measured from this install, not estimated.

| Sink | Total | Source |
|---|--:|---|
| Launchpad (7 levels) | 10.34M | `AxeFacilities.cfg` |
| Tracking station (11 levels) | 2.58M | `AxeTrackingStation.cfg` |
| R&D (3 levels) | 2.25M | CustomBarnKit default |
| Administration | 0.75M | CustomBarnKit default |
| Mission Control (5 levels) | 0.71M | `AxeFacilities.cfg` |
| Part unlocks (1,830 parts + 87 upgrades) | 5.56M | `AxePartCost.cfg` |
| Engine-config unlocks (466) | 0.55M | `AxeEntryCostMods.cfg` |
| **Lump total** | **~22.62M** | |
| Vehicles | ~20M (assumed) | see §5 — **not yet measured** |

> **Part unlocks are a buy-everything figure — realized spend is ~3.2M, not 6.11M.** A playthrough that
> buys the two cheapest parts on every node it researches spends 2.71M on parts plus configs (SCIENCE.md
> §5c), i.e. **~8% of lifetime funds — the same share RP-1 spends on part unlocks**. The 6.11M belongs in
> this table as the ceiling; it is not what the income schedule has to cover. Re-measured 2026-07-28, when
> the part-cost calibration pass also corrected three silent misclassifications (+2.2%).

**The R&D ladder is the load-bearing gate.** Its 100-science cap covers tiers 0–5 *exactly*; every
tier-6 node costs 101+. So R&D L2 (**113,000 funds**) is required to research anything past tier 5,
and L3 (**451,000**) for tier 9+ (**243 nodes = ~90% of the tree's science**). This is deliberate — it is
what makes funds a real tradeoff rather than texture — and the income schedule is sized to make those two
purchases bite without blocking.

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

## 3. The model — two channels, 40M lifetime

**Target: ~40,000,000 lifetime funds** for a player who does everything — ~22M of lumps plus a
vehicle allowance of roughly equal size. Split 60/40:

### Channel 1 — contract funds (24M), `tools/build_economy.py`

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

*Early-game check:* the two sounding-rocket programs pay 22,000 each = **44,000**, against a 15,000
start and a 19,000 pad. The pad clears with room; R&D L2 then needs the next few programs, landing
it around first orbit.

### Channel 2 — Administration (16M), `design/Settings/AxeStrategies.cfg`

Reputation is the currency AXE's contracts actually pay (~114k over a career) and it has no other
sink, so the Administration building is where it becomes spendable. `FundraisingCampaign` is
rescaled from stock's 1,002–1,253 funds/rep to **125–157** — ~140 at full commitment × ~114k
reputation ≈ 16M. The `strategyCommitRange` (0.25 / 0.6 / 1.0 by Administration level) is the
pacing knob: early careers can convert at most a quarter of incoming reputation.

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
