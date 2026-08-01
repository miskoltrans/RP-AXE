# Avionics overload — build plan

Companion to `docs/AVIONICS_NOISE.md` (the design) and `docs/AVIONICS_AUTHORITY.md` (the rejected
predecessor). This is the execution order.

**The one rule this plan is built around: the exact mechanic stays OPEN.** Phase A contains nothing
that depends on which perturbation wins, and every item in it improves the currently-shipped lock
system too. If all five modes fail the flight test, Phase A still ships and the day was not wasted.

| phase | what | gate |
|---|---|---|
| **A** | mode-agnostic build | none — start now |
| **B** | fly the five modes, decide | needs A3/A4 for the legibility half |
| **C** | commit the winner, delete the rest | needs B |

---

## Phase A — mode-agnostic, buildable now

### A1. Engage / Disengage Guidance

New persistent field on **both** `ModuleAxeAvionics` and `ModuleAxeFixedAvionics`.

- Effect is **capacity only**: disengaged, the unit contributes 0 to the MAX and provides no guidance.
- **No tier gate.** (Today's Shutdown Avionics is gated at tier index 9 — useless for the era where
  this matters most.)
- **No power effect.** Distinct from Shutdown/hibernation, which keeps RP-1's semantics.
- Editor + flight, persistent, plus Engage / Disengage / Toggle actions for staging sequences.
- Naming: **Engage / Disengage Guidance**. "Shutdown Avionics" is taken.

*Why it is required, not optional:* a lock is passive, a perturbation is active sabotage. A capsule
over capacity riding a big unguided stage must be able to stand down rather than corrupt the controls
of whatever is actually flying.

**Acceptance:** a disengaged core on an otherwise-guided vessel drops out of `EffectiveCapacityTons`
and `ShouldLock`'s MAX; the vessel falls to Axial/Locked if nothing else covers it.

### A2. Auto-engage / auto-disengage

- **Auto-engage** when `vesselMass <= thisUnit.capacityTons`.
  **Not** against the vessel MAX — a disengaged unit contributes 0, so if it is the only avionics
  aboard the MAX is 0, `r` is infinite, and a MAX-based condition can never become true again. The
  unit would be stuck off forever.
- **Auto-disengage on coupling events only** (docking), never on a mass watch. `r` also rises when
  *capacity* falls (staging away the good core), which a mass watch misses entirely; and ISRU raises
  mass continuously, which a mass watch would trip on.
- Per-unit "auto" toggle, default on.

**The principle:** build-time state is the player's decision and carries its consequences; only
run-time surprises are protected. So launching over capacity stays engaged and is punished, staging
away your own core stays engaged and is punished, docking to something heavy stands down.

**Acceptance:** capsule on a dumb stage launches locked, auto-engages on staging; a tug docking to a
heavy station auto-disengages and does not corrupt station attitude.

### A3. Regime callouts

Screen messages on transition, **with the reason** — `AxeAvionicsController.SetLevel` already posts
this kind of message, so it is one more branch.

| trigger | message |
|---|---|
| Mass rose past capacity | `Avionics over capacity — 38.2 t vs 31.7 t rated. Guidance degraded.` |
| Capacity fell (staged the primary) | `Primary avionics staged — remaining unit rated 2.0 t, vessel 8.4 t. Guidance degraded.` |
| Back under capacity | `Vessel within avionics rating. Guidance nominal.` |
| Auto-disengage on docking | `Docked mass 84 t exceeds 15 t rating. Guidance disengaged — attitude locked.` |
| Auto-engage | `Vessel within rating. Guidance engaged.` |
| Manual engage while over | `Guidance engaged over capacity — control will be unreliable.` |
| Manual disengage | `Guidance disengaged — attitude control lost, staging and throttle retained.` |

Rows 1 and 2 are why the reason is needed: both land in the degraded regime, but one is fixed by
dropping mass and the other by not staging away your core, and they are indistinguishable from the
cockpit.

**Plus: re-post a short reminder every ~30 s while degraded.** A player in map view during staging
misses the entry message and then has no persistent indicator short of right-clicking the part. A
missed callout is the whole difference between "my avionics is undersized" and "this mod is broken".

### A4. VAB legibility

On both module types:

    Capacity        15.00 t
    As configured    9.20 t   (0.61x — clean)
    At full tanks   22.40 t   (1.49x — degraded)

The full-tanks line closes the under-fuelling hole: launch with tanks emptied to save mass, fill on
site, and a configured-mass-only warning was computed against a craft that never flies. Covers ISRU,
orbital assembly and launched-dry in one line, with no ISRU-specific machinery.

### A5. Fix the `useThrottle` bypass — unrelated live bug, same files

Stock `ModuleRCS` uses `mainThrottle` as the axial command when `Z` is idle and `useThrottle` is set,
so **an avionics-locked vessel can still translate axially on RCS via the throttle today.** RP-1
patched this as an exploit in 2023 (`816d8656`); AXE never ported it. Fix regardless of which
direction the design goes.

---

## Phase B — decide the mechanic

The rig is already built and committed: five modes, a pin, and live knobs (`2faad24`).

### B1. Mode comparison

One craft, `pin noise` on, through all five modes at two amplitudes:

- σ = **0.44** (≈5% over at `k = 11.5`)
- σ = **0.68** (≈10% over)

| mode | is it a disturbance? | prediction |
|---|---|---|
| 0 uncommanded | yes | absorbed |
| 1 on input | yes | absorbed, possibly toothless |
| 2 overgain | no — gain margin | 2nd |
| 3 coupling | no — decoupling | **predicted winner** |
| 4 delay | no — phase margin | too sharp |

Recorded so it can be wrong. It has been wrong three times already in this work: authority scaling,
the frequency direction, and white-vs-correlated.

**Watch for:** MechJeb has some adaptive gain, so it may partially retune against mode 2 where SAS
will not. A split result between autopilot and hand-flying is itself a finding.

### B2. Scaling check — on the winner only

Small probe vs large launcher, same σ. With `Hz scaling` on then off (modes 0/1 only; 2/3/4 have no
frequency term by construction). If the effect is comparable across sizes, the design survives; if
not, σ needs a term that is not just the overload ratio.

### B3. Legibility check — needs A3/A4 first

Fly overloaded without being told what to look for. Does it read as *undersized avionics* or as *a
broken mod*? This is the question the whole design exists to answer and it cannot be tested until the
callouts exist. **B3 gates the commit, not just B1.**

### B4. Failure exit

If no mode survives B1, fall back to **lock + everything in Phase A**. That is still a materially
better system than what ships today, and Phase A was built to be worth having on its own.

---

## Phase C — commit and clean up (only after B)

Deliberately deferred: this is the irreversible half.

1. Pick the mode, fix the numbers, delete the losing modes.
2. **Delete the EC penalty path** — `PenaltyMultiplier()`, the hardcoded `8f`, `penaltyMultiplierCap`,
   `penaltyPercent`, and the `#pragma`-guarded stood-down block.
3. Strip every `DEBUG:` knob and the pin.
4. **Rewrite `AVIONICS_SPEC.md`** — it still documents the penalty as current behaviour, including
   the open `k` item at line 232, which closes by removal.
5. **Fix the three stale `e^80` justifications** (`AVIONICS_SPEC.md:144`,
   `AxeControlLockerUtils.cs:22`, `ModuleAxeFixedAvionics.cs:27`). They state a hazard that
   `19b7c1b` removed 19 hours after it was written, and they are still the recorded reason for the
   lock/penalty split.

---

## Loose ends found along the way — not part of this work

- **Editor and flight gate capacity differently.** `ShouldLock` counts a core only if `GuidanceActive`
  (which includes `GuidanceUnlocked`); `EffectiveCapacityTons` deliberately does not gate on
  `GuidanceUnlocked` (the `17009ce` fix, correct for the EC curve). So before guidance tech is
  researched the VAB can read "clean" while flight would be unguided — under-warning. Settle before ship.
- **Gimbal authority looks over-provisioned**, enough that reducing it *improves* ascents. That is a
  balance observation about gimbal ranges or MechJeb tuning, nothing to do with avionics, and it
  should not be lost with this document.
- **`ModuleRangeSafety` survives its `!MODULE` strip** on both procedural parts, so something re-adds
  it after `:LAST[RP-AXE]`. Pre-existing, not a regression.
