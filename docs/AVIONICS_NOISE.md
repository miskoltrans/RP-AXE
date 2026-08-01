# Control Noise — the live prototype, and what is still open

**Status: PROTOTYPE, flown, promising but unproven.** Successor to `docs/AVIONICS_AUTHORITY.md`,
which was built and rejected by test. Nothing here is a shipping decision.

Over capacity, the vessel's control inputs are corrupted by noise rising with overload, instead of
the core paying an EC penalty. Everything else — box-volume capacity, the MAX rule, the named-part
table, the Guided/Unguided/Shielded taxonomy — is unchanged.

---

## 1. Why this and not the two before it

| attempt | outcome |
|---|---|
| EC overload penalty (shipped) | Unfelt. A representative core carries ~39 h of EC against a 6-10 minute ascent. |
| Authority scaling (`AVIONICS_AUTHORITY.md`) | Dead. At `q = 0.05` a medium craft ascended normally, and flew *better* — cutting loop gain raises stability margin. |
| **Control noise (this)** | Felt. Frequency has real travel. |

The general lesson: **anything a control loop sits in front of gets compensated until saturation, and
anything measured in a resource with hours of buffer is invisible.** Noise survives because an
autopilot can correct a disturbance's average but cannot anticipate it.

## 2. The model

`sigma = 1 - e^(-k(r-1))`, `r = vesselMass / maxCapacity`, capped at a ceiling.

Applied at both `ctrlState` hooks (`FlightInputModifier` for wheels/gimbal/aero, the RCS Harmony
prefix for thrusters). **No hard cutoff** — a threshold flip to unguided was tried and dropped as the
same arbitrary cliff relocated; the curve already asymptotes to unflyable, so the limit enforces
itself. Discrete "unguided" survives only as a property of a *part* (Science-Core, capacity-0 named
part, no avionics), never as a threshold crossing.

## 3. Test findings so far

- **Low frequency is much harder to fly than high.** Inverts the original prediction. A slow wander
  is not a bias the integrator can learn — it keeps changing sign, so it produces sustained attitude
  excursions the vehicle has time to follow. Fast noise is averaged away by rotational inertia.
  **The design should live in the low band.** It also reads correctly: wallowing, not buzzing.
- **White appeared harder than correlated**, but Unity's Perlin is bell-shaped and was running ~2-3x
  quieter at equal nominal amplitude. RMS-matched since; the comparison needs re-running.
- **RCS is unusable at any meaningful sigma.** Thrusters respond instantly with no inertia to filter
  anything. Now scaled separately, default 0.25.

## 4. Open items

### 4a. Engage / Disengage Guidance — REQUIRED, not optional

**The defect it fixes:** a lock is passive, noise is active sabotage. In RP-1 a capsule that is over
capacity riding a big unguided stage simply contributes no control; the stage flies itself and
nothing is harmed. Under noise, that same capsule *corrupts the controls of whatever is flying*.
"Small guidance unit riding a big dumb stage" is an extremely common configuration, so this is not an
edge case.

A player-facing toggle whose ONLY effect is whether the unit contributes capacity and steers:

- **No tier gate.** The existing Shutdown Avionics is gated on `CanHibernate` (Unshielded: tier index
  9), so an early-career player cannot do this at all today — exactly when they are most likely to
  fly a capsule on a dumb stage.
- **No power effect.** Distinct from Shutdown/hibernation, which is the RP-1 power feature and keeps
  its own semantics.
- Editor + flight, persistent, with an action group so it can be bound into a staging sequence.
- Naming: **Engage / Disengage Guidance** — "Shutdown Avionics" is taken and means something else.
- Disengaged, the unit contributes zero capacity, so a vessel with nothing else falls through to the
  existing Axial/Locked ladder. That is the desired outcome: the passive lock, not noise.

### 4b. Auto-engage — probably the default, with one refinement

Engage automatically once vessel mass drops to where this unit can control it, so staging restores
guidance without the player remembering.

**It must latch upward only — never auto-disengage.** If it also disengaged whenever the craft went
over capacity, the unit would always drop out rather than take the noise, and the entire noise
mechanic would collapse back into RP-1's lock. Once engaged, an overloaded unit stays engaged and
pays for it.

Fits the fiction (see 4d): a programmed probe brings its guidance online when it can use it.

### 4c. Flight callout — REQUIRED

Legibility in the VAB is considered solved by any of these designs. What is missing is a screen
message on **regime transition** in flight: entering over-capacity, and returning to clean. AXE
already posts exactly this kind of message on lock transitions in `AxeAvionicsController.SetLevel`,
so it is one more branch on an existing mechanism.

With the callout plus visibly shaking inputs on the control gauges, an experienced player diagnoses
it instantly. Without it, a wallowing rocket reads as a broken mod.

### 4d. Framing: in reality, rockets fly themselves

KSP has the player flying the rocket; real launch vehicles execute their own program. That framing is
why things like "burn while out of comms range" feel acceptable — the vehicle was *programmed* to do
it.

Two consequences worth holding onto:

- The player's stick is a **proxy for the vehicle's program**, not the fiction itself. So corrupting
  it models "the vehicle mis-executes its own guidance", which is the right layer, and argues for the
  uncommanded mode over the on-input mode.
- But uncommanded noise is exactly what makes 4a necessary, since a unit that is not flying anything
  should not be corrupting anything. The two modes are not interchangeable and the choice interacts
  with 4a: **on-input mode partially self-solves the staging case** (nothing commanding, nothing
  corrupted), while uncommanded mode needs the toggle to do it.

### 4e. Docking raises vessel mass — inherited risk, worse under noise

Docking merges vessels, so `vesselMass` becomes the sum while `maxCapacity` stays the MAX across
parts. A small tug docking to a heavy station can therefore go over capacity and lose control. This
is **not new** — RP-1 has identical behaviour, and station cores carry large authored capacities
(35-160 t) which usually cover it.

What *is* new: under noise the failure is wobble rather than a lock, and wobble during proximity
operations is considerably more dangerous than simply having no attitude authority. Needs testing
before this ships, and may be an argument for auto-disengage on docking specifically.

### 4f. Tuning must work out of the box across vehicle sizes — THE open risk

`sigma` is a fraction of control range, but the *consequence* depends on inertia, TWR and aero. A
value that gently wallows a 300 t launcher may be lethal on a 5 t probe. If it turns out
size-dependent, sigma needs a term that is not just the overload ratio, and the design gets
materially uglier. **Test small probe vs large launcher before fixing any numbers.**
