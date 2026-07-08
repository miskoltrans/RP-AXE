# RP-AXE Avionics V2 Spec (design doc, iterating — nothing here is implemented yet)

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

**Mass/cost: own per-tier ladder, authored as real data — not a live multiplier. SCOPE CONFIRMED (2026-07-08):
its own ladder, full stop** — matching RP-1's real shape means ~10 *separate* tech-node placements in AXE's
tree (mirroring each Guided-tier unlock one-for-one, not a single gate riding whatever Guided tier happens to
be active). RP-1's actual Deep-Space ladder (ground-truthed this session) is `massFactor` = Near-Earth's ×
1.10, `costFactor` = × 1.50, `powerFactor` identical to NE, `powerConstant` 1.096 (vs NE's 1.035), at every
one of DS's 10 tiers (`techLevel0..9`, mapping to NE's tier names `basicAvionics` through `modernAvionics` —
DS skips NE's first three tiers, `start`/`avionicsPrototypes`/`earlyAvionics`, entirely). Plus the constants:
`massConstant` 0.96→1.043, `costConstant` 3.034→9.1. **TODO: compute these once and bake them into
`AxeAvionicsCore.cfg` as literal `shMassFactor`/`shCostFactor`/etc. per-tier fields**, same pattern as the
existing `scMassFactor` columns — not a runtime `×1.1`/`×1.5` multiplier applied to NE's live values. **TODO:
place ~10 tech-node gates in AXE's own tree**, one per Shielded tier, tracking wherever the corresponding
Guided-equivalent tiers unlock. This is real, substantial authoring work — flagged explicitly so it doesn't
get skipped or accidentally shortcut back into a multiplier during implementation.

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

**Radiation reliability — NUMBERS LOCKED (2026-07-08), verified against real mission profiles, not just
eyeballed.** Confirmed real and buildable via Kerbalism (not cosmetic — RP-1's own `shieldingMassFactor` was
checked and confirmed to connect to nothing; this is a different, verified-real mechanism instead): author a
new `Reliability` module on the avionics part (none exists there today), set `rated_radiation`/
`radiation_decay_rate` via runtime reflection (same duck-typed pattern as the existing RealFuels/kOS
bridges), keyed to the shielded/unshielded toggle. **Final numbers: unshielded `rated_radiation=1.0` rad/h,
`radiation_decay_rate=1.0`; shielded `rated_radiation=15` rad/h, `radiation_decay_rate=0.1`.** The mechanic is
a hard threshold (zero effect below `rated_radiation`, not gradual) — checked against 4 real mission shapes:
LEO and quick Mars/Venus transits show negligible effect either way (correct — real interplanetary cruises
don't linger in the belts); a belt-dwelling elliptical Earth orbit burns ~553 days off an unshielded core's
failure clock over a 5-year mission (immune if shielded); a Jupiter/Jool orbiter pushes unshielded to
near-guaranteed early failure vs. shielded surviving-if-lucky (~255 days, ~14× better). Real, meaningful
differentiation exactly where it should show up, near-zero noise where it shouldn't. Kerbalism's global MTBF
floor (~108 days) only clamps the base `mtbf` at config-load and doesn't fight this mechanic afterward —
confirmed no conflict.

**Open sub-decision this surfaced**: Kerbalism has a standard "quality" PAW toggle
(`Settings.QualityScale=4.0` in this profile) that, if exposed on the new `Reliability` module, would scale
`rated_radiation` up 4× for unshielded (clears Earth's outer belt entirely) and shielded up to 60× (clears
Jool too) — silently undercutting the calibration above. Decide: expose that toggle on the avionics part, or
hardcode it off?

---

## Capacity model

Box size determines capacity, not a typed number. Player resizes the part like any procedural part. Volume ×
density → hardware mass → inverse of the existing mass polynomial → a capacity number ("how much mass this
core can steer"). Box never auto-resizes to fit anything — capacity is purely derived, nothing forces
geometry to change (this also kills the pre-existing resize-jank risk). Capacity compares against **live
current total vessel mass** (same live number already computed today).

**Multiple cores: MAX, not SUM.** Carries forward RP-1's own 2021 anti-cheese change. Verified this still
lets a big disposable "ring" core protect a small permanent payload core from penalty during the ascent
overlap, before the ring stages off.

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
- Floors still needed on both ends, especially endurance — sized to guarantee a minimum *runtime*, not a
  fixed liters number (a fixed-liters floor is RP-1's actual mistake, `reservedRFTankVolume`, hardcoded to a
  negligible 1.5-3 L, the real mechanism behind RP-1#1295's zero-battery trap).

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
- **Shielding mass as a survival mechanic**, RP-1-style (`shieldingMassFactor`). Confirmed cosmetic in RP-1
  — connects to nothing. Replaced by the real Kerbalism reliability wiring above.

## Open / not yet decided

- Whether to expose Kerbalism's "quality" PAW toggle on the new `Reliability` module (see radiation section
  above — would quietly widen both radiation thresholds if left on).
- Bare stock/third-party probe cores — **checked (2026-07-08), not a real concern.** Most (OKTO, OKTO2,
  RC-001S, RC-L01) are either deleted outright by an inherited RP-1 `Deprecation.cfg` patch or fall into
  AXE's disconnected `parking` tech node (no `parentID`, unreachable in a real campaign) — orphaned leftovers,
  not curated content. Only 2-3 bare cores got deliberate placement (Sputnik PS-1, `ROT-ProbeCore`, both
  gated to a charter/flavor node `th_hermeticBus`, at or after the Avionics Core's own `start` availability)
  — intentional flavor/charter parts matching the established charter-redesign pattern, not a scalable
  escape hatch from the mechanics in this doc. No action needed.

## KNOWN LIVE BUG — separate from this redesign, found while reviewing the tier system (2026-07-08)

`AxeAvionicsCore.cfg`'s 14-tier ladder gates each tier on RP-1's original bare tech names (`postWarAvionics`,
`avionicsPrototypes`, etc.), but AXE's own from-scratch tree uses discipline-prefixed IDs — confirmed
`postWarAvionics` doesn't exist as a node ID anywhere in `AxeTechTree.cfg`, only `gnc_postWarAvionics` does.
`ModuleAxeAvionics.cs`'s `Researched()` calls stock `ResearchAndDevelopment.GetTechnologyState()` on the raw
bare string with zero prefix handling. If this pattern holds across all 13 tier names (being scoped now),
every avionics core in the game is likely permanently stuck at the tier-0 `start` floor regardless of
research — the whole tier progression this doc builds on may never actually engage in a real campaign. Full
scope (which tiers are affected, whether it's a clean prefix fix or needs real remapping, whether
`guidanceTech` has the same problem) is being checked separately — **this should probably be fixed before or
alongside this redesign, not after**, since it affects the ladder every other piece of this spec sits on top
of.
