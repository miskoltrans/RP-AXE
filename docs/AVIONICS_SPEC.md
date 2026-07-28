# RP-AXE Avionics V2 Spec (SHIPPED 2026-07-10 — this is the as-built record; design reasoning below is historical)

**Goal**: feature parity with RP-1's avionics, with better UX. Not a simplification pass — everything RP-1's
system actually *does* mechanically should still be possible to do here, just without RP-1's specific failure
modes (silent hard-lock cliff, unguarded utilization-to-zero trap, a typed number nobody can predict the
consequence of). Where AXE previously dropped something because it seemed non-essential (Deep-Space's
premium, real hibernation gating), the working assumption is now: put it back, just built better.

Full session trace (topology investigation, economic analysis, research citations) lives in the
`rp-axe-steerable-mass-design` and `rp-axe-avionics-core` memories — this doc is the current spec, not the
history.

---

## Axis 1 — Guided / Unguided

Already shipped, unaffected by this redesign. Guided = Near-Earth shape (vessel-scaled, full control).
Unguided = Science-Core shape (flat per-tier, axial-only from `improvedAvionics`). Range is not gated here —
handled entirely by comms (RealAntennas).

## Axis 2 — Unshielded / Radiation-Shielded (naming CONFIRMED), stands in for RP-1's Deep-Space, Guided-only

Tech-gated second choice, only available once appropriate tech is researched (mirrors RP-1: Deep-Space wasn't
available from `start`, it unlocked around Near-Earth's `basicAvionics`-equivalent point). Unguided/
Science-Core never had a Deep-Space equivalent in RP-1 either — this axis doesn't apply to it.

**Mass/cost: own per-tier ladder, authored as real data — not a live multiplier. SHIPPED.** Matching RP-1's
real shape meant ~10 *separate* tech-node placements in AXE's tree (mirroring each Guided-tier unlock
one-for-one, not a single gate riding whatever Guided tier happens to be active). RP-1's actual Deep-Space
ladder (ground-truthed against `RP-1/GameData/RP-1/Tree/ProceduralAvionics.cfg`) is its own literal per-tier
`massFactor`/`costFactor` table (NOT a clean ×1.10/×1.50 multiplier on Near-Earth's values — that was an
early approximation, corrected once the real numbers were pulled), `powerFactor` identical to NE at every
corresponding tier, `powerConstant` 1.096 (vs NE's 1.035), across DS's 10 real tiers (`techLevel0..9`, mapping
to NE's tier names `basicAvionics` through `modernAvionics` — DS skips NE's first three tiers, `start`/
`avionicsPrototypes`/`earlyAvionics`, entirely, RP-1 has no Deep-Space data there). Constants: `massConstant`
0.96→1.043, `costConstant` 3.034→9.1. Baked into `AxeAvionicsCore.cfg` as literal `shMassFactor`/`shCostFactor`
per-tier fields (mirrors the existing `scMassFactor` columns), `ModuleAxeAvionics.cs`'s hardcoded fallback
ladder kept in sync. 10 `shd_*` tech nodes placed in `tree/nodes.yaml` (serial chain, each requiring both the
previous Shielded rung and its paired Guided/Computing tier) for the 10 real tiers.

RP-1 also applies a surface-area-scaled shielding-mass ADD-ON on top of the per-tier curve
(`avionicsMass^(2/3) * shieldingMassFactor`, `shieldingMassFactor=0.1` tier-invariant) — missed in the first
implementation pass (the per-tier table alone was verified byte-exact against RP-1 and mistakenly taken as
the whole story), found and fixed 2026-07-10 (see POST-SHIP FIXES below).

**1:1 ladder fill-in (2026-07-10):** the 4 early tiers RP-1 has no Deep-Space data for (`start`/
`gnc_postWarAvionics`/`gnc_avionicsPrototypes`/`gnc_earlyAvionics`) now carry `shMassFactor`/`shCostFactor`
too, reused verbatim from their own Unshielded values — no new tech nodes needed (they key off the SAME
tech field as the paired Guided tier already does), and the Shielded **toggle** stays gated behind
`ShieldedUnlocked` (hardcoded to `gnc_basicAvionics`) regardless, unchanged from before the fill-in. Decided
this way because the toggle being locked makes the early-tier numbers moot either way.

**Hibernation/idle: matches RP-1 exactly, replaces AXE's current ungated behavior.** Unshielded: no hibernate
at all until `advancedAvionics` tech (RP-1's NE has no `disabledPowerFactor` field on its first 8 tiers),
then only reaches `0.1`. Shielded: deep `0.05`, available from tier 0, no gate. AXE's *current* Hibernate
gives every Guided core the deep `0.05` unconditionally regardless of shielding — that was an accidental
side effect of porting the number without the gate, and gets axed in favor of the real RP-1 split.

**Auto-hibernate on warp — CONFIRMED, port RP-1's mechanism directly, not a separate open question.** RP-1's
base `ModuleAvionics.cs` hooks `GameEvents.onVesselGoOnRails`/`onVesselGoOffRails`, calling
`UpdateRate(onRails: true)`: while a vessel is on rails (unloaded/timewarping), draw automatically drops to
the reduced/idle rate — independent of the player's manual Hibernate toggle state — and reverts to whatever
the vessel's actual current state is the moment it goes back off rails (loads/becomes active). AXE currently
has zero `onRails`/`offRails` hooks anywhere in `ModuleAxeAvionics.cs`, and also disables stock KSP's own
probe-hibernation fallback (`%hasHibernation = False`), so today draw just freezes at its last live value and
keeps applying for the whole warp unless the player manually hits Hibernate first. Port RP-1's hook pattern
directly: same events, same "auto-drop during warp regardless of manual state, auto-restore on load" behavior.

**Radiation reliability — DEFERRED, NOT SHIPPED IN THIS PASS (2026-07-08 decision, still holds).** Everything
below was designed and numbers-locked before implementation started, then explicitly scoped OUT at the start
of the build: Kerbalism's `Reliability` feature is off instance-wide, and wiring this up is a separate,
later, game-wide balance task, not something to bundle into the avionics V2 build. No `MODULE{name=Reliability}`
block, `rated_radiation`/`radiation_decay_rate` field, or reflection bridge exists anywhere in
`ModuleAxeAvionics.cs` today. The design below remains valid for whenever that later task happens — it was
not abandoned, just not part of this build. Important
correction to how this is described: RP-1 has zero real radiation-*reliability* mechanic for avionics — no
failure/decay connection anywhere — so this whole mechanic is new AXE design, not a port. (Correction to an
earlier claim in this doc: `shieldingMassFactor` is NOT purely cosmetic — it's a real mass add-on,
`avionicsMass^(2/3) * shieldingMassFactor`, that genuinely increases Deep-Space's total mass; it just has no
connection to *reliability/radiation-damage*, which is the only thing meant by "connects to nothing" below.) First-pass numbers (unshielded `1.0/1.0`, shielded `15/0.1`)
were invented from reasoning about Kerbalism's body radiation data with no anchor — checked properly and
found to have **no precedent anywhere in the ecosystem**: not in this instance, not in RP-1/RO's actual
Kerbalism fork (`ROKerbalism`, confirmed to predate this feature entirely, zero references), not even
documented by Kerbalism's own upstream maintainers beyond a formula comment. The one real precedent that
exists anywhere — base Kerbalism's default profile, applied only to solar panels/reaction wheels/data
transmitters, never avionics — sits at `rated_radiation 0.11-0.26` rad/h, `decay_rate 1-3`, and even those
real values needed 10-20× downward retuning after being found too punishing in practice.

**Final design, simpler than the first pass:**
- **Shielded: leave the `Reliability` module's `rated_radiation` unset (defaults to 0).** Kerbalism's own
  code short-circuits to zero decay whenever `rated_radiation <= 0` — so "shielded behaves normal, no
  radiation damage" requires no special-casing, it's just the default, identical to how literally every
  other avionics/probe part in the game already behaves today.
- **Unshielded: `rated_radiation = 0.10` rad/h, `radiation_decay_rate = 30`.** Threshold sits just below the
  real solar-panel precedent floor (grounded, not invented from nothing); the decay rate is deliberately far
  above the real 1-3 range because threshold barely matters once it's anywhere near that low relative to
  Earth's belts (2.2-10.4 rad/h) — decay rate is the actual lever for "how much does a brief pass hurt."
  Tuned so a single ordinary departure crossing (~3h outer belt + ~30min inner belt) burns **~14 days off the
  ~135-day failure buffer — about 10% of an unshielded core's reliability window, gone in one pass**,
  genuinely felt without being instant death. Sustained belt-dwelling (e.g. a long-duration Earth radiation-
  belt science orbit) is correspondingly much more severe — appropriately so. Kerbalism's global MTBF floor
  (~108 days) only clamps the base `mtbf` at config-load and doesn't fight this mechanic afterward — confirmed
  no conflict. Still recommend confirming this feels right in actual play once built, same as any new mechanic
  with no prior playtesting anywhere in the ecosystem to lean on.

**Quality toggle — DECIDED (2026-07-08): do not expose it.** Kerbalism has a standard "quality" PAW toggle
(`Settings.QualityScale=4.0` in this profile) that would scale `rated_radiation` up 4× for unshielded (clears
Earth's outer belt entirely) and shielded up to 60× (clears Jool too) if exposed on the new `Reliability`
module — silently undercutting the calibration above. Not shown on this part; hardcode it off.

---

## Capacity model

Box size determines capacity, not a typed number. Player resizes the part like any procedural part. Volume ×
density → hardware mass → inverse of the existing mass polynomial → a capacity number ("how much mass this
core can steer"). Box never auto-resizes to fit anything — capacity is purely derived, nothing forces
geometry to change (this also kills the pre-existing resize-jank risk). Capacity compares against **live
current total vessel mass** (same live number already computed today).

**Multiple cores: MAX, not SUM.** Carries forward RP-1's own 2021 anti-cheese change. Verified this still
lets a big disposable "ring" core protect a small permanent payload core from penalty during the ascent
overlap, before the ring stages off. Fixed-capacity named parts (below) join the same MAX.

## Fixed-capacity named parts (ADDED 2026-07-28)

The procedural core is the *design it yourself* path. Named parts — Sputnik, Voyager, an Apollo CM, an
Agena bus, a Titan guidance ring — are the *buy it off the shelf* path, and they work differently on
purpose. `ModuleAxeFixedAvionics` carries one authored number, the vessel mass the unit can steer. No
allocation bar, no shielding toggle: the part's model is a fixed size, so there is no box to split, and
the author already made that decision.

**Why not derive it.** Capacity cannot be computed from part data — a part's mass is mostly structure,
tankage and instruments, so running the inverse mass polynomial on it yields nonsense (a 150 t launch
stand "derives" ~10 million tonnes). The values are RP-1's own hand-authored `ModuleAvionics.massLimit`
table, ported as-is; it encodes per-spacecraft judgement no field contains. The two models do agree at the
bottom of the range: the curve needs 84.5 kg of hardware (a 169 L box) before capacity goes positive at
tier 0, and Sputnik 1's entire 83 kg falls under it — independently reproducing RP-1's authored 0.

**Why they LOCK instead of taking the penalty.** The penalty exists to soften a *sizing mistake* — a
player who built their own box slightly small should degrade, not brick. A fixed part has no sizing
decision to get wrong, so going over its rating locks attitude (RP-1's original rule) while command,
staging and throttle keep working. Routing them through the penalty curve instead would mean a capacity-0
part draws e^80 watts, flattens the battery and drops `ModuleCommand` entirely — harsher than RP-1 and
far less legible in the VAB.

**Shielding is baked, not chosen.** Voyager was radiation-hardened; Sputnik was not. The flag is ported
from RP-1's `interplanetary` (which marked exactly the units rated beyond near-Earth) and still gated on
researching `shd_basicAvionics`, so the shd_* lane keeps its value without duplicating a per-tier ladder
onto every named part. Its effect here is hibernation only.

**The blanket fallback is the important half.** Any uncrewed command part with no authored capacity gets
capacity 0. Without it a bare stock `ModuleCommand` is an unconditional full-control bypass in
`AxeControlLockerUtils` — which is what let every named probe core, and every ModularLaunchPads launch
stand, silently grant unlimited guided control. RP-1 never hit this because its own blanket rule
(`Avionics.cfg:11`) covered everything its table missed; AXE dropped `ModuleAvionics` globally and never
replaced that rule. Generated by `tools/build_fixed_avionics.py` into
`design/Parts/AxeFixedAvionics.cfg`.

**Not ported: `techRequired`.** RP-1's optional per-unit tech gate names RP-1 tech IDs, none of which
exist in AXE's from-scratch tree, and `GetTechnologyState()` returns `Unavailable` rather than erroring on
an unknown ID — so porting it would silently zero those parts' capacity forever (the same failure mode as
the 2026-07-08 tier bug below). In AXE the part's own tree node is the gate.

## Capacity / battery / empty-space allocation

**UI: a 3-segment bar**, `|--battery--|--hardware--|--empty space--|`, representing how the box's total
volume is currently split. Not required to use the full box — empty space is a legitimate, allowed state
(no forced 100% utilization).

**Resize behavior — needs custom logic, not a stock control:**
- If the player has **explicitly set** specific battery/hardware values (adjusted the bar manually), those
  values are **remembered** as intent.
- On a shape resize (box gets bigger or smaller), re-fit using the remembered values: **battery gets
  priority — fit it first**, then hardware gets whatever room is left. (This resolves the earlier open
  "proportional shrink vs. priority order" question — priority order, battery first.)
- If the player **hasn't** explicitly set anything, use a standard default proportion on resize —
  **CONFIRMED (2026-07-08): 25% battery / 75% hardware / 0% empty space.** Most of a default, untouched box
  goes to hardware; battery is the smaller share until the player deliberately asks for more.
- **Floor — REVERSED from this doc's original call, SHIPPED as RP-1's real mechanism (2026-07-09).** This
  section originally called RP-1's `reservedRFTankVolume` approach "RP-1's actual mistake" and specified a
  runtime-guaranteed-minimum-endurance floor instead (computed from live draw ÷ battery chemistry). That
  runtime floor was built first, then explicitly rejected in live testing ("there is no floor when using
  this sliders... look at what rp1 is doing") — it was also the direct cause of a real runaway-feedback bug
  (an undersized core's penalty multiplier going to +Infinity inflated the floor to consume the whole box).
  Ground-truthed RP-1's actual mechanism (`ModuleProceduralAvionics.cs`/`ProceduralAvionics.cfg`) at the
  user's request: it's a tiny FIXED constant, identical at every tier — 3 L for Guided (Near-Earth/Deep-Space
  both use 0.003), 1.5 L for Unguided (Science-Core, 0.0015) — added as a minimum on the battery side only.
  **Hardware has NO floor at all in RP-1** — hardware volume is purely `GetAvionicsMass()/avionicsDensity`,
  forward-derived from whatever the player rates it at, with nothing enforced as a minimum. AXE now matches
  both facts exactly: `EnduranceFloorVolume()` returns a flat 3 L/1.5 L constant (no runtime/draw math at
  all), and `hwVolume` has no floor anywhere in `RecomputeSplit()`/`LiveUpdateSplit()`. The "doc was wrong"
  call was explicit: this design decision predated enough live testing to know better, and simple/
  ground-truthed won over the original (reasonable-sounding, but ultimately unvalidated) invented mechanic.

**Default part dimensions — CONFIRMED (2026-07-08): match RP-1's own default, not AXE's current override.**
RP-1's real default procedural-avionics shape is a 1.25 m diameter × 0.2 m length cylinder ≈ 245 L — safely
above the ~169 L minimum-for-any-positive-capacity floor at `postWarAvionics`, so a freshly-placed, unresized
core is functional out of the box (resolves the earlier concern about AXE's current 0.5×0.5m default, ~98 L,
sitting below that floor). AXE's `AxeAvionicsCore.cfg` currently overrides `ProceduralShapeCylinder` to
0.5m/0.5m — **needs reverting to RP-1's 1.25m/0.2m default** as part of this build.

## Under-capacity penalty — FORMULA LOCKED (2026-07-08)

`r = liveMass / effectiveCapacity` (effectiveCapacity = MAX across active cores, per the multi-core rule).
`r ≤ 1` → zero penalty.

`ec_draw_penalty = ec_draw_normal × (e^(k×(r−1)) − 1)`, `k = 8`.

`ec_draw = ec_draw_normal + ec_draw_penalty` (= `ec_draw_normal × e^(8×(r−1))` — additive framing preserved
for the UI split below, mathematically the same curve). `ec_draw_normal` is the existing, unchanged
`ComputeBaseWatts()` formula (live dry mass, tier `powerFactor`).

Continuous at `r=1` (no jump), gentle at small overages, genuinely prohibitive past ~25-50% over — verified
against a 20-ton/600-second reference burn: 10% over ≈ 3% of vessel mass in battery (tolerable), 25% over ≈
12% (a real tax, discouraged but not physically absurd), 50% over ≈ 89% of the *original vessel's entire
mass* just in battery (a hard practical wall — you will not reach orbit built this way), 100% over is beyond
absurd. `k` is the one tuning dial if this needs adjusting after real play-testing — pushing it up hardens
both thresholds simultaneously since it's one curve, not two independently-set breakpoints.

**UI**: show the penalty portion distinctly, not just a combined total — as a percentage over normal draw
(`(e^(8(r−1))−1) × 100%`), so a player can see at a glance how much of their current draw is "penalty" versus
baseline.

---

## Also in scope — verified, small, self-contained

**"Set to Debris: Never / On Stage" — confirmed real RP-1 feature, port it.** Lives in RP-1's
`ModuleAvionics.cs` (not stock KSP — confirmed via decompiled `Assembly-CSharp.dll`, zero hits there). A
per-part, editor-only `UI_Toggle` (disabled="Never"/enabled="On Stage", default Never), grouped under the
Avionics PAW fold-out. Mechanism: subscribes to `GameEvents.onStageActivate`; on staging, waits 1s, checks if
this vessel is no longer the active one (i.e. it's the piece just left behind); if so, scans it for any
command-capable part with avionics explicitly set to "Never" (any one vetoes the whole vessel) — otherwise
force-sets `vesselType = VesselType.Debris`. Pure tracking-station hygiene (no funds/recovery/science effect)
— lets a spent stage that happened to carry avionics (needed for its own burn) not clutter the tracking
station as a permanent "Ship" after separating. Self-contained: toggle + event hook + one `vesselType` write,
no interaction with anything else in this doc. No RP-1 config presets it to true anywhere — pure opt-in.

---

## Explicitly rejected — don't re-propose

- **Topology/decoupler-graph auto-scoping** (deriving a core's "responsible mass" from the vessel's
  attachment graph). Confirmed technically buildable, killed for semantic reasons: a bottom-stage core needs
  more than its local segment (everything still attached above it), and topology alone can't distinguish
  independent parallel payloads from serial stages — the distinction is about intent the graph doesn't
  encode. See `rp-axe-steerable-mass-design` memory for the two counterexamples that killed it.
- **Splitting core + battery into separate parts.** Floated mid-session, dropped in favor of one integrated
  part with a real allocation floor instead.
- **A manual typed `controllableMass` slider.** The entire point of this redesign was removing it.
- **Shielding mass as a survival/reliability mechanic**, RP-1-style (`shieldingMassFactor`). Confirmed it
  connects to no failure/reliability system in RP-1 — replaced by the real Kerbalism reliability wiring above
  (itself deferred, not shipped). Note this is narrower than "the field does nothing": `shieldingMassFactor`
  IS a real mass add-on in RP-1 (see the Axis 2 section above) and AXE now applies it too — what's rejected
  here is specifically using it as a stand-in for a radiation-survival mechanic, not the mass effect itself.

## Open / not yet decided

- Whether to expose Kerbalism's "quality" PAW toggle on a future `Reliability` module (see radiation section
  above — would quietly widen both radiation thresholds if left on). Moot until the radiation-reliability
  work actually ships, since no `Reliability` module exists yet.
- Bare stock/third-party probe cores — **checked (2026-07-08), not a real concern.** Most (OKTO, OKTO2,
  RC-001S, RC-L01) are either deleted outright by an inherited RP-1 `Deprecation.cfg` patch or fall into
  AXE's disconnected `parking` tech node (no `parentID`, unreachable in a real campaign) — orphaned leftovers,
  not curated content. Only 2-3 bare cores got deliberate placement (Sputnik PS-1, `ROT-ProbeCore`, both
  gated to a charter/flavor node `th_hermeticBus`, at or after the Avionics Core's own `start` availability)
  — intentional flavor/charter parts matching the established charter-redesign pattern, not a scalable
  escape hatch from the mechanics in this doc. No action needed.

## FIXED LIVE BUG (2026-07-08) — was blocking all avionics tier progression AND guidance activation

Root cause confirmed via decompiled `Assembly-CSharp.dll`: `ResearchAndDevelopment.GetTechnologyState()` on
an unrecognized tech ID silently returns `RDTech.State.Unavailable` — no crash, no log, just a false. Every
bare RP-1-style tech name in `AxeAvionicsCore.cfg` fails this lookup against AXE's own prefixed/renamed tree.

**Bug #1 — tier ladder frozen at floor.** Confirmed for all 13 non-`start` tiers: `ApplyTier()`'s loop never
finds a `Researched()==true` tier past index 0, so mass/power/cost/kOS/science-container gating are all
permanently stuck at `start`'s numbers regardless of research. The fix is NOT uniform:

| Tier | Correct target (found via a leftover `Science-Core-<name>` PARTUPGRADE breadcrumb, itself dead code) | Fix |
|---|---|---|
| `postWarAvionics` | `gnc_postWarAvionics` | clean: add `gnc_` prefix |
| `avionicsPrototypes` | `gnc_avionicsPrototypes` | clean: add `gnc_` prefix |
| `earlyAvionics` | `gnc_earlyAvionics` | clean: add `gnc_` prefix |
| `basicAvionics` | `gnc_basicAvionics` | clean: add `gnc_` prefix |
| `interplanetaryProbes` | `gnc_interplanetaryAvionics` | remap (renamed) |
| `improvedAvionics` | `comp_digitalGuidanceComputer` | remap (fully renamed) |
| `matureAvionics` | `comp_realTimeFlightComputer` | remap (fully renamed) |
| `largeScaleAvionics` | `comp_networkedAvionics` | remap (fully renamed) |
| `advancedAvionics` | `comp_multiplyRedundantFlightComputer` | remap (fully renamed) |
| `nextGenAvionics` | `comp_distributedAvionicsBus` | remap (fully renamed) |
| `longTermAvionics` | `comp_softwareDefinedFlightControl` | remap (fully renamed) |
| `internationalAvionics` | `comp_interoperableAvionicsStandard` | remap (fully renamed) |
| `modernAvionics` | `comp_commercialOffTheShelfAvionics` | remap (fully renamed) |

Only tiers 1-4 (through Basic Avionics) are a clean prefix add. Tiers 5-13 (everything past that) landed on
tree nodes with no lexical relation to their RP-1 name at all during the tree rebuild — the only reason
they're recoverable now is a dead `Science-Core-*` PARTUPGRADE comment left behind as a naming fossil.

**Bug #2 — `guidanceTech = postWarAvionics`, same bug, worse consequence.** This is a SEPARATE field (not
part of the tier loop) gating whether guidance can ever activate at all: `GuidanceUnlocked =>
Researched(guidanceTech)`. Since it has the identical bare-string bug, `GuidanceUnlocked` is **permanently
false** — `GuidanceActive` can never become true, so the entire "Guided" model can never achieve real 3-axis
control **no matter how much tech is researched**, in any non-sandbox campaign. Every player flying "Guided"
today sees `guidanceStatus` permanently stuck at "guidance not yet researched (dumb)." This is a full
capability lockout, not a frozen-economy-numbers bug — arguably the most severe thing found this whole
session, and it's in currently-shipped code, not something this redesign introduced.

**FIXED (2026-07-08).** Applied as a standalone, surgical patch, independent of the rest of this V2 redesign:
corrected all 14 `tech =` values + `guidanceTech` in `AxeAvionicsCore.cfg` to the confirmed correct IDs above
(traceability comments added, `// RP-1: <original name>`, so the mapping isn't lost again). Also found and
fixed the identical bug in `ModuleAxeAvionics.cs`'s hardcoded fallback ladder (`_ladTech` array + the
`guidanceTech` KSPField default) — the cfg-driven ladder was the only thing checked initially, but the
in-code fallback used the same bare RP-1 names and would have reintroduced the exact same lockout if the cfg
ever failed to parse. Reference-string corrections only, no logic changes. Build verified clean (0 errors).

## POST-SHIP FIXES (2026-07-10) — found and fixed during live in-game testing after the V2 build landed

- **Overload penalty overflowing to literal `Infinity`.** `PenaltyMultiplier()`'s `Mathf.Exp(8*(r-1))` was
  uncapped; an undersized core (capacity near/at 0 while vessel mass > 0) pushed the exponent argument past
  ~89, overflowing float's ~3.4e38 ceiling to the literal string "Infinity" in the PAW. This wasn't a rare
  edge case — the stock default part + default 25/75 split produces only ~5 kg of capacity at tier `start`,
  so essentially every fresh Guided core hit it before any deliberate resizing. Fixed by clamping the
  exponent argument (not the multiplier) to 80 — still enormous (~5.5e34×) and still prohibitive, just no
  longer a literal overflow. The "severe penalty for an undersized core" behavior itself is unchanged.
- **`EffectiveCapacityTons()` required `GuidanceUnlocked` for a core to count at all — the real cause of
  "penalty is severe no matter how I size it."** Ground-truthed against RP-1's real
  `ControlLockerUtils.ShouldLock()`: it aggregates every avionics core's rated mass unconditionally (gated
  only on having EC connected, or being in the editor) — there is no "is guidance tech researched" gate
  anywhere in the real mechanism. A core's tier data is always valid (`ApplyTier()`'s tier-0 floor guarantees
  it), so "dumb" avionics still needs to not overload for its own rated mass; `GuidanceUnlocked` should only
  gate whether the vessel can actively *steer*, a separate concern. As shipped, every Guided core showed
  maximum overload penalty from the moment it was placed until `guidanceTech` was researched, regardless of
  sizing — not RP-1 parity, a genuine bug. Removed the `!axe.GuidanceUnlocked` condition.
- **Resizing the box bigger didn't grow hardware, only "empty."** `RecomputeSplit()` capped `hwVolume` at
  `desiredHwVolume` (the last explicitly-dragged absolute liters value) with no upper adjustment for a
  bigger box — any growth past the last committed split just inflated unclaimed empty space, so the player
  had to re-drag the handle after every resize for it to do anything. Added `desiredTotalVolume` (the box
  size at the moment the split was last committed): volume gained since then flows to the player-adjustable
  segment (hardware for Guided, battery for Unguided) by default, while a deliberately-left empty gap (a
  handle dragged short of the box's far edge) is preserved — only *new* room past the remembered total counts
  as growth.
- **Fresh part instantiation could compute a near-zero capacity that "fixed itself" on the first resize.**
  `OnStartFinished`'s editor branch read `ProceduralPart`'s volume synchronously on the same frame the part
  started — `ProceduralPart`'s own shape/volume isn't necessarily settled that same frame (its shape
  application can run across a frame boundary), so the read could catch it before that, producing a
  near-zero cached volume that then stuck (near-zero capacity → tripped overload penalty) until the next
  `onEditorShipModified` event, i.e. the player's first resize. Delayed the initial read one frame via a
  coroutine (`EditorFirstFrameSetup()`) — same idiom `AxeAllocationBarHook` already uses waiting for the
  PAW's field list to finish building.
- **Missing RP-1's real Deep-Space shielding-mass add-on** and the **Shielded ladder's 4-tier gap** — see the
  Axis 2 section above, both fixed the same session.
- **"Endurance" PAW readout removed (sacked, not fixed).** It only ever estimated this one part's own local
  battery against this one module's own draw — redundant with Kerbalism's own vessel-wide EC-balance
  estimate, which accounts for every producer/consumer on the ship and answers the actual question players
  care about. `guidanceEndurance`, `UpdateEndurance()`, and the now-unused `FormatDuration()` helper were
  deleted outright rather than reconciled with Kerbalism's number.

All of the above verified live in-game (KSP 1.12.5, this instance) after each fix, not just build-clean.
