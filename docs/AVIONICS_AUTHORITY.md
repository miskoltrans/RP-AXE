# Control Authority — proposed replacement for the overload penalty

**Status: PROPOSAL, not built.** Amends `docs/AVIONICS_SPEC.md`. Nothing here is shipped; the
overload power penalty described in AVIONICS_SPEC "Under-capacity penalty" is still what runs today.

The one-line change: **going over capacity degrades how well the craft steers, instead of taxing its
electric charge.** Everything else in the avionics design — the box-volume capacity model, the MAX
rule, the named-part table, the Guided/Unguided/Shielded taxonomy — is untouched.

---

## 1. Why replace the penalty

Four reasons, in descending order of how much they matter.

**It does not work during the phase it exists to police.** Measured, not estimated: RealFuels
`ElectricCharge` holds 500 EC/L and draw is watts/1000 EC/s, so a representative guided core
(`Aether B`: 31.7 t capacity, 146 W, 41 L battery) carries **~39 hours** of normal operation. An
ascent is 6-10 minutes. The multiplier needed to kill that core inside the ascent window is >390;
`k = 8` reaches 54.6 at 1.5x over. The curve is either invisible or, past the cap, lethal — there is
no band where it does the job it was designed for. `AVIONICS_SPEC.md:232` records this as open.

**Both recorded justifications for the lock/penalty split are dead.**
- *"A capacity-0 part on the penalty path would draw e^80 watts and drop ModuleCommand"* — true when
  written (`cd5a0fa`, 00:00 on 2026-07-29), false 19 hours later when `penaltyMultiplierCap` capped
  the multiplier at e^8 (`19b7c1b`, 19:27). Still stated as a live reason in `AVIONICS_SPEC.md:144`,
  `AxeControlLockerUtils.cs:22` and `ModuleAxeFixedAvionics.cs:27`.
- *"A fixed part has no sizing decision to get wrong"* — false. `r = vesselMass / capacity` has two
  terms and the player controls both. Choosing a 0.875 t Voyager bus for a 2 t spacecraft is a
  sizing decision made in the VAB and correctable there.

**Named parts cannot use it.** They have no power model — 33 of 90 draw no EC at all, and
`ModuleAxeFixedAvionics` has no draw field until the `enabledkW` adoption in `a9cde23`, which is
adopt-only. A consequence expressed in watts can never be shared by both classes. A consequence
expressed in control authority can.

**The penalty is the less recoverable failure.** A lock resolves the instant the overweight stage
separates. A flattened battery does not come back. The e^8 ceiling exists specifically so a craft
"stays commandable long enough to stage" — i.e. the failure being managed is the penalty destroying
the vessel.

**What the lock gets wrong instead:** it is a cliff at exactly `r = 1`. One kilogram over and
attitude authority is gone. `AVIONICS_SPEC.md:3` names the *"silent hard-lock cliff"* as a failure
mode to avoid; this proposal keeps the "not silent" half and removes the cliff rather than pricing
it in watts.

---

## 2. The model

`r = vesselMass / effectiveCapacity`, unchanged from today: whole-vessel **wet** mass, capacity is
the **MAX** across contributing units (never the sum), fixed and procedural units in the same MAX.

Authority factor `q`:

| r | q | state |
|---|---|---|
| `r <= 1` | `1.0` | full control |
| `1 < r < R_cut` | `1 / r` | **degraded** — control authority scaled |
| `r >= R_cut` | — | **unguided** (Axial if any unit allows it, else Locked) |

**`q = 1/r` is derived, not tuned.** The unit was built to control `capacity` tonnes; asked to
control `r` times that, the authority available per tonne is `1/r`. This is the whole point of
preferring it to `k`: there is no invented constant in the curve. `R_cut` is the single dial, and it
sets the floor implicitly (`q_floor = 1/R_cut`).

Starting value: **`R_cut = 3`**, floor `q = 0.33`. Rationale: it leaves a wide, genuinely flyable
degraded band (a craft 50% over keeps 67% authority — sluggish, obviously wrong, still recoverable),
and cuts out before `q` gets low enough for closed-loop instability to dominate (see §6).

| over capacity | q | reads as |
|---|---|---|
| 10% | 0.91 | barely noticeable |
| 25% | 0.80 | soft, obviously heavier than it should be |
| 50% | 0.67 | wallowing |
| 100% | 0.50 | half authority, hard to fly |
| 200%+ | — | unguided |

**Unguided is still a real state, not `q -> 0`.** "Axial thrust only" is a discrete capability
(spin-stabilized kick stage), not a weak version of full control — it cannot be reached by scaling.
`R_cut` is where the scalar hands over to the existing three-level ladder.

---

## 3. Enforcement — four points, not one

KSP has no single input choke point. AXE already has all four of RP-1's; this is what each does
under a scalar `q`. **Getting this list wrong is the most likely way to ship a hole.**

| # | Point | Today | Under this proposal |
|---|---|---|---|
| 1 | `InputLockManager.SetControlLock(LockMask)` (`AxeAvionicsController:136`) | binary, mask = `YAW\|PITCH\|ROLL\|SAS` | **unchanged, floor only.** An input lock cannot be scaled. Engages at `r >= R_cut`. In the degraded band input flows and is scaled downstream. |
| 2 | `FlightInputModifier` via `OnPostAutopilotUpdate` (`AxeAvionicsController:82`) | `st.yaw = st.pitch = st.roll = 0`, `st.X = st.Y = 0`, `st.Z = 0` at Locked | `*= q` on yaw/pitch/roll/X/Y. Z untouched in the degraded band; at the floor, existing Locked/Axial behaviour. Covers **reaction wheels, engine gimbal, aero surfaces**. |
| 3 | `AxeRcsControlLock` Harmony prefix/postfix on `ModuleRCS.Update` | zeroes, then restores | `*= q` inside the same save/restore window. Needed because `ModuleRCS.Update` reads `ctrlState` on its own Unity pass, before the post-autopilot hook re-zeroes it. |
| 4 | MechJeb `DeactivateControl` by reflection (`AxeAvionicsController:157`) | binary | **unchanged, floor only.** MechJeb has no authority-scaling input; in the degraded band it flies with scaled output like any other autopilot. |

### 3a. The `useThrottle` trap — a live bug today, independent of this proposal

Stock `ModuleRCS` contains, in effect:

```
if (Z ~= 0 && useThrottle) num2 -= mainThrottle;
```

so with no translation input, **the throttle becomes the axial RCS command.** RP-1 patched this as an
exploit on 2023-10-05 (`816d8656`, *"Patch ModuleRCS to not allow throttling to get around control
locker"*), zeroing `mainThrottle` at Locked and snapping it to full at Axial inside the same
prefix/postfix window.

**AXE never ported it.** `AxeRcsControlLock` zeroes X/Y/Z and the rotation axes but never touches
`mainThrottle`, so an avionics-locked vessel can still translate axially on RCS via the throttle.
Fix this regardless of which direction the design goes; scaling Z without handling `mainThrottle`
would leave the same hole open in the degraded band.

---

## 4. Readouts

The penalty's invisibility in the editor is the actual complaint behind "silent cliff". This must be
legible before launch, not discovered in flight.

- **Core PAW:** `Overload Penalty` (percent over normal draw) is replaced by **`Control Authority`**,
  shown as a percentage, plus the state word (`full` / `degraded` / `unguided`).
- **Named parts:** gain the same field — the first readout both classes genuinely share.
- **`GetInfo`:** state the band, e.g. *"Guided up to 0.88 t. Beyond that, control authority falls
  with load; past 3x it becomes unguided."*
- The existing `Capacity` / `Steerable Mass` fields are unchanged.

---

## 5. What deletes, what stays

**Deletes:**
- `PenaltyMultiplier()`, the hardcoded `8f`, `penaltyMultiplierCap` (a `KSPField`), `penaltyPercent`
- the penalty multiplication in `ComputeBaseWatts()` — EC draw becomes `TierWatts()` alone
- the open `k` item at `AVIONICS_SPEC.md:232`, closed by removal rather than by tuning
- the three stale `e^80` justifications listed in §1

**Stays, untouched:**
- box-volume capacity model, allocation bar, tier ladder, Shielded axis, shutdown semantics
- `EffectiveCapacityTons()` and the MAX rule
- the named-part authored table and the `:FINAL` blanket fallback
- `allowAxial` semantics, including RP-1's vessel-wide OR with no capacity condition (any qualifying
  unit upgrades the whole craft from Locked to Axial)
- Unguided/Science-Core: no capacity, no `q`, unchanged

---

## 6. Open questions — all need play, not analysis

1. **Does scaling actually feel different, or does SAS mask it?** The key one. SAS is a closed loop:
   it will push its output toward 1.0 to compensate, so the net effect is *maximum authority reduced
   by q* — the craft turns slower. Expected to read as sluggishness. Must be confirmed in flight,
   with and without MechJeb.
2. **Oscillation at low `q`.** Stock SAS's PID is tuned for unscaled authority; at low `q` the
   integral term may wind up and overshoot. This is the reason for a floor rather than `q -> 0`, and
   the reason `R_cut = 3` rather than 10. If oscillation appears above `q = 0.33`, raise the floor.
3. **`R_cut` itself.** 3 is a starting guess. It is the only tunable in the design.
4. **Should `q` apply to translation (X/Y) as well as rotation?** Proposed yes, for consistency, but
   translation authority arguably belongs to RCS sizing rather than avionics.
5. **Rover wheels.** AXE's `LockMask` omits `WHEEL_STEER`/`WHEEL_THROTTLE` (RP-1 includes them), and
   `FlightInputModifier` does not touch `wheelSteer`/`wheelThrottle`. So a locked rover still drives
   today. Decide whether that is deliberate before adding a scalar to the mix.

---

## 7. Divergences from RP-1 to record while we are here

Not caused by this proposal; worth writing down because they are easy to mistake for bugs.

- **No interplanetary gate.** RP-1's `IsLockedByInterplanetary` zeroes `CurrentMassLimit` when a
  non-interplanetary unit leaves near-Earth (threshold = home `spaceAltitudeThreshold * 2`). AXE's
  `shielded` flag affects hibernation only. A near-Earth-rated unit works everywhere here.
- **Throttle is never locked.** RP-1's mask includes `THROTTLE`, though that lock has been broken
  since ~KSP 1.9 — KSP carved X and Z out of `ControlTypes.THROTTLE` into `THROTTLE_CUT_MAX` and
  RP-1's 2015-era mask was never updated, so it blocks Shift/Ctrl but not X or Z. AXE deliberately
  leaves throttle and staging free at every level, which is a design choice rather than the same rot.
- **`dead` / "Disable Avionics permanently"** is not ported (`AVIONICS_SPEC.md:280`), so neither is
  its antenna-kill cascade.
