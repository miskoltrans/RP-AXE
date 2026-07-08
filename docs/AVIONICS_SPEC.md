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

## Axis 2 — Unshielded / Radiation-Shielded (stands in for RP-1's Deep-Space), Guided-only

Tech-gated second choice, only available once appropriate tech is researched (mirrors RP-1: Deep-Space wasn't
available from `start`, it unlocked around Near-Earth's `basicAvionics`-equivalent point). Unguided/
Science-Core never had a Deep-Space equivalent in RP-1 either — this axis doesn't apply to it.

**Mass/cost: own per-tier ladder, authored as real data — not a live multiplier.** RP-1's actual Deep-Space
ladder (ground-truthed this session) is `massFactor` = Near-Earth's × 1.10, `costFactor` = × 1.50,
`powerFactor` identical to NE, `powerConstant` 1.096 (vs NE's 1.035), at every one of DS's 10 tiers
(`techLevel0..9`, mapping to NE's tier names `basicAvionics` through `modernAvionics` — DS skips NE's first
three tiers, `start`/`avionicsPrototypes`/`earlyAvionics`, entirely). Plus the constants: `massConstant`
0.96→1.043, `costConstant` 3.034→9.1. **TODO: compute these once and bake them into `AxeAvionicsCore.cfg` as
literal `shMassFactor`/`shCostFactor`/etc. per-tier fields**, same pattern as the existing `scMassFactor`
columns — not a runtime `×1.1`/`×1.5` multiplier applied to NE's live values. This is real authoring work,
not a formula shortcut — flagged explicitly so it doesn't get skipped.

**Hibernation/idle: matches RP-1 exactly, replaces AXE's current ungated behavior.** Unshielded: no hibernate
at all until `advancedAvionics` tech (RP-1's NE has no `disabledPowerFactor` field on its first 8 tiers),
then only reaches `0.1`. Shielded: deep `0.05`, available from tier 0, no gate. AXE's *current* Hibernate
gives every Guided core the deep `0.05` unconditionally regardless of shielding — that was an accidental
side effect of porting the number without the gate, and gets axed in favor of the real RP-1 split.

**Radiation reliability — the actual differentiator we're trying to make Unshielded genuinely worse at,
still being worked out.** Confirmed real and buildable via Kerbalism (not cosmetic — RP-1's own
`shieldingMassFactor` was checked and confirmed to connect to nothing; this is a different, verified-real
mechanism instead): author a new `Reliability` module on the avionics part (none exists there today), set
`rated_radiation`/`radiation_decay_rate` via runtime reflection (same duck-typed pattern as the existing
RealFuels/kOS bridges), keyed to the shielded/unshielded toggle. Starting numbers to tune from: unshielded
`rated_radiation≈1.0` rad/h (fails inside Kerbin's own belts — both inner 10.4 and outer 2.2 rad/h exceed
it), shielded `≈15` rad/h (shrugs off Kerbin entirely, only Jool-class fields at 300/50 rad/h bite),
`radiation_decay_rate` unshielded=1.0 (default), shielded=0.1. Caveat: Kerbalism's global MTBF floor (~108
days) applies regardless, so this is a long-run reliability difference, not a fast/dramatic failure. Still
exploratory — "we will try to work out how to make radiation affect the unshielded one," not locked.

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
- If the player **hasn't** explicitly set anything, use a standard default proportion on resize (exact ratio
  TBD).
- Floors still needed on both ends, especially endurance — sized to guarantee a minimum *runtime*, not a
  fixed liters number (a fixed-liters floor is RP-1's actual mistake, `reservedRFTankVolume`, hardcoded to a
  negligible 1.5-3 L, the real mechanism behind RP-1#1295's zero-battery trap).

## Under-capacity penalty

**Additive, not multiplicative**: `ec_draw = ec_draw_normal + ec_draw_penalty`. `ec_draw_penalty = 0` at or
under capacity — **must be continuous at the boundary, no sudden jump right at the capacity threshold** —
but ramp up **very steeply** once over: a plausible mission profile (e.g. a 10-minute burn) should become
essentially impossible fairly quickly as overage increases, not a gentle slope. Exact formula still TBD/to
iterate — the requirement is shape (continuous, steep), not a specific exponent yet. (Earlier session work
had explored a multiplicative `×(liveMass/capacity)^p` form with `p≈0.5` — superseded by this additive
framing; keep the earlier economic-dominance analysis in mind when picking the real formula, since `p=0` was
proven to make capacity meaningless entirely.)

**UI**: show the penalty portion distinctly, not just a combined total — likely as a percentage over normal
draw, so a player can see at a glance how much of their current draw is "penalty" versus baseline.

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

- Standard default battery/hardware proportion when the player hasn't set explicit values.
- Exact under-capacity penalty formula (shape requirements set above, specific function TBD).
- Whether the mass↔capacity curve gives sane numbers at realistic box sizes — formula has a hard
  minimum-size-for-any-capacity floor (~169 L at `postWarAvionics`) that's *bigger* than AXE's current
  default part dimensions (~98 L) — a fresh, unresized part would sit at zero capacity today. Needs either
  the default size bumped or confirmation this is intentional.
- Auto-hibernate-on-warp — separately parked, doesn't block any of this.
