# Avionics overload — complete build plan

Companion to `docs/AVIONICS_NOISE.md` (the design) and `docs/AVIONICS_AUTHORITY.md` (the rejected
predecessor). This is the whole of the work, planned before building.

**The rule this plan is built around: the exact mechanic stays OPEN.** Everything except Phase D is
independent of which perturbation wins, and improves the currently-shipped lock system too. If every
mode fails the flight test, all of it still ships and the fallback (`PenaltyLock`) is a one-knob
change with no code edit.

| phase | what | gate | status |
|---|---|---|---|
| **0** | penalty abstraction layer | — | **DONE** (`a5c9845`) |
| **A** | player-facing behaviour | — | A1/A2 done; A3–A5 to build |
| **B** | RP-1 parity audit + fixes | — | to build |
| **C** | sack the EC penalty | — | to build |
| **D** | fly the modes, pick one, clean up | needs A+B+C | tomorrow |

---

## Phase 0 — penalty abstraction (DONE)

`AxeControlPenalty` + `AxeControlPenalties` registry. Eleven selectable consequences behind one
interface, chosen at runtime from the core's DEBUG mode knob:

| # | id | family |
|---|---|---|
| 0 | `none` | experimental control |
| 1 | `lock (RP-1)` | RP-1's rule — the A/B baseline and the fallback |
| 2 | `uncommanded` | disturbance |
| 3 | `on input` | disturbance |
| 4 | `overgain` | margin attack — gain margin |
| 5 | `coupling` | margin attack — decoupling |
| 6 | `delay` | margin attack — phase margin |
| 7 | `dropouts` | availability |
| 8 | `misdirect` | margin attack — reference frame |
| 9 | `effort gain` | closed loop — by depth |
| 10 | `adversarial` | closed loop — by choice |

The families are the argument, not the list. Disturbances get **rejected** (that is what a loop is for);
margin attacks are not rejectable but are **open-loop and therefore learnable**, which drift and
precession exist to blunt. The last three escape both: `dropouts` randomises whether the command lands
at all, and 9/10 make the corruption a function of the loop's own output, so there is no fixed point for
an adaptive controller to converge on.

### The test that separates 9 from 10 — a dominant escape

`effort gain` is **monotone in effort**, so *minimise effort* beats it: fly gently and the penalty
withdraws itself. A mechanic with a dominant escape strategy is a tax you can route around, not an
adversary, and the fix is not a deeper penalty — it is to make **every escape the entrance to another
attack.**

`adversarial` therefore adds no corruption of its own. It splits the recent command into a sustained
part and a transient part, and plays the move whose own effect is largest in that cell:

| | **not moving it** | **moving it** |
|---|---|---|
| **holding little** | `uncommanded` | `overgain` |
| **holding a lot** | `washout` | `delay` |

- **Fly gently → `uncommanded`.** The counter to minimal input is the one mechanic that does not read
  input. That cell is the whole answer to the dominant-escape problem.
- **`overgain` where commands are small** — amplification needs headroom below the clamp; ×3 on 0.3 is an
  event, ×3 on 0.9 merely saturates.
- **`washout` where the command is mostly DC.** Its standalone weakness (the loop just commands
  `1/(1−σ)` harder, which is the authority scalar `AVIONICS_AUTHORITY.md` killed) is what makes it work
  *here*: commanding harder moves you into another cell. Rejected as a mode, correct as a move.
- **`delay` where the command is changing** — pure lag does nothing to a constant command.

**No absorbing state**, which is the property being bought: do nothing → drift forces a correction → you
are holding or twitching; hold → it decays → you re-command → lag; fight → it destabilises → you back
off → drift. The only remedy left is a unit rated for the vehicle, which is the constraint the whole
design exists to make binding.

Not in the policy, deliberately: `dropouts`, `misdirect` and `coupling` are strong in *every* regime, so
no cell is theirs. That makes them standalone candidates rather than moves.

The fiction is not a malicious computer — it is a **gain schedule characterised for a different
vehicle**. Real control laws are scheduled per flight regime; an under-rated unit's table is wrong in
every cell, and wrong in a different way in each.

`LocksInstead` is honoured inside `ShouldLock`, `Stateful` tells the RCS patch to skip
double-application, `Reset(vessel)` drops per-vessel state, `Describe()` gives each mode its own PAW
wording. Choosing the ship mechanic later is one index; deleting the losers is deleting files.

---

## Phase A — player-facing behaviour

### A1 Engage / Disengage Guidance — **DONE**
Capacity-only, no tier gate, no power effect, both module types, with actions. Distinct from Shutdown
Avionics (RP-1's power feature, gated at tier index 9 — useless for the era where this matters).

### A2 Auto-engage / auto-disengage — **DONE**
Engage when `vesselMass <= thisUnit.capacityTons` (never the vessel MAX — a disengaged sole unit makes
the MAX 0 and `r` infinite, so a MAX test could never become true again). Disengage on coupling events
only (`r` also rises when *capacity* falls; ISRU raises mass continuously).

### A3 Regime callouts — TO BUILD
Screen message on every transition, **with the reason**, driven from a small state machine in
`AxeAvionicsController` that remembers the previous `(level, sigma>0, maxCapacity)`.

| trigger | message |
|---|---|
| Mass rose past capacity | `Avionics over capacity — 38.2 t vs 31.7 t rated. Guidance degraded.` |
| **Capacity fell** (staged the primary) | `Primary avionics staged — remaining unit rated 2.0 t, vessel 8.4 t. Guidance degraded.` |
| Back under capacity | `Vessel within avionics rating. Guidance nominal.` |
| Engage/disengage | done in A1 |

Rows 1 and 2 both land in the degraded regime but have different remedies, and are indistinguishable
from the cockpit — that is why the reason, not just the state, is required. Distinguished by comparing
this tick's `maxCapacity` against last tick's: if capacity fell, it is row 2.

**Plus a ~30 s re-post while degraded.** A player in map view during staging misses the entry message
and then has no persistent indicator. A missed callout is the difference between "my avionics is
undersized" and "this mod is broken".

### A4 VAB legibility — TO BUILD
On both module types:

    Capacity        15.00 t
    As configured    9.20 t   (0.61x — clean)
    At full tanks   22.40 t   (1.49x — degraded)

Full-tank mass = current mass + `sum over resources of (maxAmount - amount) * density`. Closes the
under-fuelling hole in one line: launch with tanks emptied to save mass, fill on site, and a
configured-mass-only warning was computed against a craft that never flies. Covers ISRU, orbital
assembly and launched-dry with no ISRU-specific machinery.

### A5 `useThrottle` bypass — TO BUILD
Stock `ModuleRCS` uses `mainThrottle` as the axial command when `Z` is idle and `useThrottle` is set,
so **an avionics-locked vessel can translate axially on RCS via the throttle today**. RP-1 patched it
as an exploit in 2023 (`816d8656`); AXE never ported it. Zero `mainThrottle` at Locked and snap it to
full at Axial, inside the existing prefix/postfix window.

---

## Phase B — RP-1 parity audit

Ground-truthed against `C:\git\ksp\RP-1`. Every row gets a disposition; nothing is left implicit.

| RP-1 behaviour | AXE | disposition |
|---|---|---|
| `maxMass` = MAX across parts, sum within a part | same | ✅ parity |
| Vessel mass = wet (`p.mass + p.resourceMass`) | same | ✅ parity |
| `forceUnlock` from any command part with no avionics | same | ✅ parity |
| Blanket `massLimit = 0` on uncrewed command parts (`Avionics.cfg:11`) | same | ✅ parity |
| Blanket hibernation strip (`Avionics.cfg:2`) | same | ✅ parity |
| `allowAxial` OR'd vessel-wide, no capacity condition | same | ✅ parity |
| Launch clamps zeroed pre-flight, never grant control | same | ✅ parity |
| `isEVA` / `InfiniteElectricity` unlock | same | ✅ parity |
| 124-entry `massLimit` table | ported (90 installed) | ✅ parity |
| `setToDebrisOnStage` | ported | ✅ parity |
| Four enforcement points | all four present | ✅ parity |
| **`useThrottle` RCS bypass patch** | **missing** | 🔧 **A5 — fix** |
| **Avionics counts only with EC connected** | no EC gate | 🔧 **B1 — decide** |
| **`interplanetary` range gate** | not ported | 🔧 **B2 — decide** |
| **`enabledkW` delivery** (RP-1 zeroes ModuleCommand and delivers itself) | adopt-only | 🔧 **B3 — build** |
| `techRequired` per-unit gate | not ported | ⛔ deliberate — RP-1 tech IDs do not exist in AXE's tree and `GetTechnologyState()` returns `Unavailable` on a miss, silently zeroing those parts forever |
| `dead` / permanent disable + antenna cascade | ported (both modules) | ✅ parity — shipped 2026-08-05, `AxeAvionicsKill.cs`. Adds a crew guard RP-1 lacks (see below) |
| Throttle + wheel locks in the mask | not ported | ⛔ deliberate — AXE leaves throttle/staging free at every level. (RP-1's throttle lock has also been broken since KSP 1.9: `THROTTLE` no longer covers X/Z, which moved to `THROTTLE_CUT_MAX`, and its 2015 mask was never updated) |
| Typed `controllableMass` slider | replaced by box volume | ⛔ deliberate — the point of the V2 redesign |
| Utilization launch block | replaced by A4 readouts | ⛔ deliberate — RP-1 validates the wrong variable; it never checks mass against capacity, which is why an overweight craft launches clean there |

### B1. EC-connected gate — **DECIDED: do not port**
RP-1 only counts a unit toward `maxMass` if it has EC connected. AXE has no such check. Porting it
would be wrong here: 33 of 90 named parts draw no EC at all and would silently contribute nothing,
and stock `ModuleCommand` brownout already removes control when the battery dies. Record as a
deliberate divergence in the class docs.

### B2. Interplanetary range gate — **DECIDED: do not port**
`IsLockedByInterplanetary` zeroes capacity when a non-interplanetary unit leaves near-Earth
(threshold = home `spaceAltitudeThreshold * 2`). AXE's `shielded` affects hibernation only. Not
porting: AXE deliberately moved range to comms (RealAntennas), stated in `AxeAvionicsCore.cfg`.
Record as deliberate.

### B3. `enabledkW` delivery — **BUILD**
This is the last thing making named parts second-class. RP-1 adopts the part's `ModuleCommand` rate,
**zeroes it**, and delivers the draw itself so it can be modulated. AXE's fixed module currently only
adopts, because zeroing without a Kerbalism bridge would make every named part free to run.

Port the bridge from `ModuleAxeAvionics` to `ModuleAxeFixedAvionics`: `PlannerUpdate`,
`ResourceUpdate`, static `BackgroundUpdate`, the `KerbalismPresent` branch, and `OnSave` writing the
on-rails figure. Then zero the `ModuleCommand` resource and drive it from `enabledkW`. Acceptance:
total vessel EC draw unchanged for a named part before and after.

---

## Phase C — sack the EC overload penalty

The penalty is proven inert (a representative core carries ~39 h of EC against a 6–10 minute ascent),
both of its recorded justifications are dead, and named parts can never share a consequence measured
in watts. It goes regardless of which perturbation wins — RP-1 has no overload EC term either, so
removing it is *also* parity.

**Delete:**
- `PenaltyMultiplier()` including the hardcoded `8f` and the `#pragma`-guarded stood-down block
- `penaltyMultiplierCap` (`KSPField`) and `penaltyPercent`
- the multiplication in `ComputeBaseWatts()` → becomes `TierWatts()` alone

**Keep:** the whole tier × dry-mass EC draw model, the Kerbalism bridge, hibernation depths,
on-rails reduction. Only the *overload multiplier* goes.

**Docs to correct in the same pass:**
- `AVIONICS_SPEC.md` — the "Under-capacity penalty", "Multiplier ceiling" and "k=8 calibration ... OPEN"
  sections describe current behaviour that will no longer exist; line 232's open item closes by removal
- the three stale `e^80` justifications (`AVIONICS_SPEC.md:144`, `AxeControlLockerUtils.cs:22`,
  `ModuleAxeFixedAvionics.cs:27`) — they state a hazard `19b7c1b` removed 19 hours after it was written
- `AxeAvionicsCore.cfg` header, which advertises the power penalty as the mechanic

---

## Phase D — fly it, decide, clean up (tomorrow)

### D1 Mode comparison
One craft, `pin noise` on, all eleven modes at σ = **0.44** (≈5% over) and **0.68** (≈10% over).

Prediction on record so it can be wrong — it has been three times already (authority scaling, the
frequency direction, white-vs-correlated): **coupling wins, overgain second, delay too sharp, both
noise modes absorbed.**

Watch for MechJeb's adaptive gain partially retuning against `overgain` where SAS will not. A split
between autopilot and hand-flying is itself a result.

**These are controlled A/Bs, not a free-for-all, and should be flown back to back:**

- **4 `overgain` → 9 `effort gain` → 10 `adversarial`**, in that order. Same slope throughout by
  construction, so each step changes exactly one thing: fixed gain, then gain scheduled on the loop's
  own effort, then the move itself chosen to match the regime. Flying 10 without 9 cannot tell you
  whether the *policy* is doing the work or the *scheduling* is.
- **2 `uncommanded` vs 3 `on input`** — the mode question from `AVIONICS_NOISE.md` §3-bis, still open
  because on-input has never actually been flown.

Predictions, on record:

- **9 hunts rather than diverges, and reads as a vehicle that is fine until you ask it for something.**
  Known defect, already argued rather than measured: dodgeable by flying gently.
- **10 is the strongest and the least legible.** Specifically: it will beat 9 on *feel* and be at risk
  on **D3**, because a failure that changes character is harder to attribute than one that is always
  present. The dwell time and the regime name in the PAW exist to buy that back.

**The D1 question 10 actually has to answer, and it is not "is it hard":** watch the regime readout and
check whether it *tracks what you are doing* or *thrashes*. A thrashing readout means the AC gain is
wrong and the mode is being judged on a tuning artefact. A readout that sits in one cell for a whole
ascent means the policy never engaged and you are really only testing that one move.

### D2 Scaling check — winner only
Small probe vs large launcher, same σ, `Hz scaling` on then off (modes 2/3 only; 4/5/6 have no
frequency term). Comparable effect across sizes = the design survives.

### D3 Legibility check — needs A3/A4
Fly overloaded without being told what to look for. Reads as *undersized avionics* or as *a broken
mod*? **This gates the commit, not just the mode choice.**

### D4 Cleanup, after the decision
Fix the mode and numbers, delete the losing penalty classes, strip every `DEBUG:` knob and the pin,
rewrite the design docs to describe what shipped.

### D5 Failure exit
No mode survives → set the registry to `PenaltyLock` and ship Phases A+B+C. That is a materially
better system than today, needs no code change to select, and Phase A was built to be worth having on
its own.

---

## Loose ends — recorded, not scheduled

- **Editor and flight gate capacity differently.** `ShouldLock` counts a core only if `GuidanceActive`
  (which includes `GuidanceUnlocked`); `EffectiveCapacityTons` deliberately does not gate on
  `GuidanceUnlocked` (the `17009ce` fix, correct for the EC curve). Before guidance tech is researched
  the VAB can read "clean" while flight would be unguided — under-warning. Settle before ship.
- **Gimbal authority looks over-provisioned** — cutting it *improves* ascents. A balance observation
  about gimbal ranges or MechJeb tuning, nothing to do with avionics.
- **`ModuleRangeSafety` survives its `!MODULE` strip** on both procedural parts, so something re-adds
  it after `:LAST[RP-AXE]`. Pre-existing, not a regression.
