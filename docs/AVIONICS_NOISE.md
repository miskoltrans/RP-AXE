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

### 4b. Auto-engage AND auto-disengage — noise becomes opt-in

Revised. The unit engages automatically when vessel mass drops to where it can control the vehicle,
and **disengages automatically on docking** — see 4b-bis, which narrows this from the "any mass
increase" rule it started as, because `r` also rises when capacity falls (staging away the good core)
and because refuelling raises mass continuously rather than as an event.

I previously argued auto-disengage must never happen, on the grounds that a unit which always drops
out rather than take the noise collapses the mechanic back into RP-1's lock. That objection is wrong,
because it assumed noise had to be the *default* consequence. It does not. Noise becomes an **opt-in
gamble** instead, and that is a better design than a mandatory one:

- **Default (auto):** you are always either guided-and-clean, or unguided-and-locked. Never a
  surprise, never sabotage, and it matches RP-1's behaviour for a player who never touches the
  toggle.
- **Override (manual engage while over capacity):** you accept a faulty flight computer and fly with
  the wobble.

**The choice is real because both options cost.** It is not "penalty vs no penalty" — it is *no
guidance* versus *unreliable guidance*, and unreliable is often better than none. A player 10% over
who needs to finish a burn has a genuine decision to make, and the wobble is simultaneously the
punishment and the information that tells them what they chose.

This also substantially de-risks 4f: if the noise regime is opted into rather than stumbled into,
imperfect tuning across vehicle sizes is far less damaging.

Fits the fiction (see 4d): a programmed probe brings its guidance online when it can use it, and
stands down when it cannot.

**Needs hysteresis.** `r` will cross 1.0 back and forth as propellant burns and mass shifts, and a
naive threshold would chatter between engaged and disengaged — spamming the 4c callout and flipping
control state mid-flight. Either use a deadband (engage at `r <= 0.95`, disengage at `r >= 1.05`) or
evaluate only on discrete events (docking, undocking, staging) rather than continuously. Decide
before building.

### 4b-bis. Wet mass, and the edge cases it brings

`r` uses **wet** mass today — `p.mass + p.resourceMass`, propellant included — matching RP-1. Dry
mass is used only for the EC draw curve, never for capacity. Wet is the physically right call: a full
rocket genuinely is harder to slew. Keeping it, but it is not free.

**The framing choice underneath it:** wet mass makes overload a *transient*; dry mass would make it a
*binary design constraint*. Worth stating plainly because everything below follows from it.

**1. Overload heals itself as propellant burns — ACCEPTED.** A craft 20% over at liftoff may be at
capacity by the time the tanks are half empty, so "undersize the core, tough out the first minute,
save the mass" becomes a viable strategy. Decided we are fine with this even though it eases
progression: it is exactly the margin-shaving RO players enjoy, and the cost is real, since a wobbly
max-Q can break the vehicle under FAR.

**2. Chatter — NOT A REAL CONCERN, retracted.** I claimed `r` would cross 1.0 repeatedly and flap the
auto behaviour. It will not: mass falls monotonically through a burn and rises only at coupling
events, so `r` crosses once, downward. The worry belonged to the continuous mass-watch design that
4b-bis already replaced with docking events, and does not survive it.

**2-bis. The real trap in its place: auto-engage must test THIS UNIT'S capacity, not the vessel MAX.**
A disengaged unit contributes zero, so if it is the only avionics aboard, `maxCapacity` is 0 and `r`
is infinite — and an auto-engage condition written against vessel `r` can never become true again.
The unit would be permanently stuck off. Condition must be `vesselMass <= thisUnit.capacityTons`.

**3. Only ISRU raises mass continuously — refuelling does not.** Corrected: once docked it is a
single vessel, so transferring propellant between its tanks moves mass around internally and leaves
the total unchanged. Genuine continuous mass gain comes from ISRU/drills alone, which is rare enough
to ignore for now. Coupling events remain the trigger regardless.

**4. THE ONE THAT BREAKS THE MASS-INCREASE RULE: `r` also rises when CAPACITY falls.** Staging away
the stage carrying the big core drops `maxCapacity` while mass also drops — so `r` jumps without any
mass increase at all. A rule that watches mass would miss it entirely.

**Therefore the trigger is docking/coupling events, not a mass watch.** That is discrete, cheap,
immune to refuelling creep and chatter, and it draws the line where it belongs:

| event | auto behaviour | why |
|---|---|---|
| Launch over capacity | **stay engaged**, wobble | You built it that way and the VAB told you. Your decision. |
| Stage away the good core | **stay engaged**, wobble | Also a build-time decision, made in the editor. |
| Dock to something heavy | **auto-disengage** → clean lock | A mission-time surprise you did not design. Also where wobble is most dangerous. |
| Undock / stage down | **auto-engage** if now under capacity | Guidance returns without the player remembering. |

The principle: **build-time state is the player's decision and carries its consequences; only
run-time surprises are protected.** This also answers the clamp-release worry — the mechanic stays
live at launch, where it is the actual balance lever, and stands down at docking, where it would
merely be dangerous.

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
operations is considerably more dangerous than simply having no attitude authority.

Resolved by 4b as revised: auto-disengage on rising mass fires exactly here, so docking to something
heavy stands the unit down into a clean lock rather than starting a wobble against a station.

### 4f. Tuning must work out of the box across vehicle sizes — the open risk, now smaller

`sigma` is a fraction of control range, but the *consequence* depends on inertia, TWR and aero. A
value that gently wallows a 300 t launcher may be lethal on a 5 t probe. If it turns out
size-dependent, sigma needs a term that is not just the overload ratio, and the design gets
materially uglier. **Test small probe vs large launcher before fixing any numbers.**

Downgraded from "could sink the design" by 4b: with noise opted into rather than stumbled into, a
player who never engages an overloaded unit never meets the tuning at all.
