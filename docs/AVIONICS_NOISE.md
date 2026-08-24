# Control Noise — the live prototype, and what is still open

**Status: PROTOTYPE, flown, promising but unproven.** Successor to `docs/AVIONICS_AUTHORITY.md`,
which was built and rejected by test. Nothing here is a shipping decision.

Over capacity, the vessel's control inputs are corrupted by noise rising with overload, instead of
the core paying an EC penalty. Everything else — box-volume capacity, the MAX rule, the named-part
table, the Guided/Unguided/Shielded taxonomy — is unchanged.

> **2026-08-24 — §4e happened, and §3's own conclusion was right all along.** The additive
> `uncommanded`/`drift` cell is **removed**; the mechanic is now zero-in-zero-out. §3 below argued for
> on-input mode on signal-to-noise grounds and was overruled when `adversarial` shipped, which put the
> additive move back as the empty cell. On an assembled station (r = 2-10, where σ is pinned at ~1.0)
> that meant a full-deflection random command into a vessel that was merely holding attitude, and SAS
> fighting it kept it armed. **Read §3's "Mode: defaults to ON-INPUT" as the position that finally
> won.** §4e's resolution was a claim, not a verified fact — see its amendment. Details:
> `docs/AVIONICS_PLAN.md`, amendment of the same date.

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

## 3-bis. The numbers — five knobs reduced to two

The previous two designs died because a single free number could not be anchored to anything. Five
free numbers is not an improvement on one, so they were reduced rather than tuned.

| was | now |
|---|---|
| `k`, ceiling, Hz, RCS scale, mode | **`k = 2.3`** (from one sentence) and **`C = 2`** (from a scaling law) |

**Ceiling: deleted.** `sigma = 1 - e^(-k(r-1))` already asymptotes to 1, which is the natural
saturation — the command is fully swamped. A ceiling parameter was capping a curve that caps itself.
Default 1 (off), kept only as a debug knob.

**`k`: anchored to a statement, not tuned.** *"At 20% over its rated mass, a unit is hopeless"* means
`sigma(1.2) = 0.9`, which solves to **`k = 11.5`**:

| over capacity | sigma |
|---|---|
| 2% | 0.21 |
| 5% | 0.44 |
| 10% | 0.68 |
| 15% | 0.82 |
| **20%** | **0.90 — hopeless** |

A deliberately narrow tolerance band: a few percent of grace, then it goes away fast. That makes
rated capacity close to a hard constraint, which is how real vehicles treat control design margin —
nobody flies 20% over what the control system was characterised for. The number is a consequence of a
sentence that can be argued about in English, which is the property `k = 8` never had.

**Two knock-ons of the steeper curve:**

- The wet-mass "undersize and tough out the first minute" strategy (4b-bis item 1) largely dies. At
  20% over you cannot fly at all, so there is nothing to tough out; only a genuinely marginal craft
  (a few percent) has anything to ride out. The exploit shrinks to a rounding error.
- The VAB numbers matter *more*, not less. With clean and hopeless only 20% apart, the editor
  readout and the full-tanks line from 4b-ter carry most of the legibility load.

**Hz: scaled by vessel, which also dissolves 4f.** A fixed frequency cannot be right for both a 5 t
probe and a 300 t launcher, because each vehicle low-passes the noise according to its own rotational
response — the big stack filters 2 Hz heavily, the probe barely at all. That *is* the size-scaling
risk, restated.

    Hz = C / mass^(1/3)

Rigid-body attitude response time scales with linear dimension (`I ~ m*L^2`, torque roughly `~ m`, so
timescale `~ L`, frequency `~ 1/L ~ m^(-1/3)`). At `C = 2`, a 1 t probe gets 2 Hz and a 100 t stack
gets 0.43 Hz — each perturbed at its own response frequency, so the effect is comparable across sizes
instead of accidentally tuned to whatever was flown last. Toggleable to flat Hz for A/B comparison.

**RCS scale: deleted, because it was the wrong diagnosis.** RCS being unusable is not an inertia
problem, it is a SMALL-COMMAND problem — docking uses commands around 0.05, so additive noise of
+/-0.3 is six times the signal. RCS is merely where small commands live. On-input mode preserves the
ratio at any magnitude (0.05 becomes 0.035-0.065: degraded, not destroyed), so the separate scale is
unnecessary. Default back to 1.

**Mode: defaults to ON-INPUT.** This reverses the earlier lean toward uncommanded. The fiction
argument for uncommanded (real rockets fly themselves) is still true but weaker than the
signal-to-noise argument above, and largely moot in practice: MechJeb and SAS command continuously
during any active flight, so on-input noise still fires. The only time it does not is when nothing is
flying — exactly when nothing should be corrupted. It also makes 4a less load-bearing.

**The open risk this creates:** on-input mode has never been flown. It is better on every axis I can
reason about, but proportional noise may simply be too weak — during a nominal ascent MechJeb's
corrections are small, so the absolute perturbation is small too. **That is now the most important
untested question, ahead of any number.**

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
the total unchanged. Genuine continuous mass gain comes from ISRU/drills alone — worked through in
4b-ter, where it turns out to need no special machinery. Coupling events remain the trigger.

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

### 4b-ter. ISRU

The one genuine source of continuous mass gain with no coupling event, so worth working through
rather than waving at.

**It mostly covers itself.** Tank capacity is fixed at build time, and the KSP editor shows tanks
full, so the VAB figure is already the worst case. A miner launched full, landed, drained and
refilled cannot exceed the mass the VAB already displayed. Nothing new happens.

**The real gap is deliberate under-fuelling, and it is not really an ISRU problem.** Launch with tanks
set empty to save mass, fill them on site, and the VAB warning was computed against the light
configuration. The player is then over capacity in the field having been told they were clean. Same
hole applies to anything assembled in orbit or launched dry.

**Fix belongs in the editor, not in flight:** show the ratio at **full tanks** alongside the ratio as
configured. One extra line, it costs nothing, and it closes the case generally instead of
special-casing ISRU.

    Capacity        15.00 t
    As configured    9.20 t   (0.61x — clean)
    At full tanks   22.40 t   (1.49x — degraded)

**Do NOT auto-disengage on ISRU mass gain.** It is tempting for symmetry with docking, and it is
wrong: a miner needs guidance to fly off the surface, and standing the unit down would leave it
locked rather than wobbly. Wobbly beats locked when you still have to fly. Coupling events remain the
only auto-disengage trigger; the player can always disengage by hand if they prefer the lock.

**Drop-a-stage-then-refill is already covered.** A lander that sheds its descent stage (capacity
falls), mines and refills (mass rises) is the capacity-falls case from 4b-bis — a build-time decision,
so it stays engaged and wobbles. Correct outcome: you designed a vehicle whose avionics cannot handle
its own refuelled mass.

### 4c. Flight callout — REQUIRED, with the reason

Legibility in the VAB is considered solved (plus the full-tanks line from 4b-ter). What is missing is
flight. AXE already posts this kind of message on lock transitions in
`AxeAvionicsController.SetLevel`, so the mechanism exists; what it needs is a **reason**, because the
player's remedy differs depending on why the regime changed.

Every transition and what it says:

| trigger | message |
|---|---|
| Mass rose past capacity | `Avionics over capacity — 38.2 t vs 31.7 t rated. Guidance degraded.` |
| **Capacity fell** (staged away the primary unit) | `Primary avionics staged — remaining unit rated 2.0 t, vessel 8.4 t. Guidance degraded.` |
| Back under capacity | `Vessel within avionics rating. Guidance nominal.` |
| Auto-disengage on docking | `Docked mass 84 t exceeds 15 t rating. Guidance disengaged — attitude locked.` |
| Auto-engage after undock/staging | `Vessel within rating. Guidance engaged.` |
| Manual engage while over capacity | `Guidance engaged over capacity — control will be unreliable.` |
| Manual disengage | `Guidance disengaged — attitude control lost, staging and throttle retained.` |
| No/unguided avionics | existing `SetLevel` messages, unchanged |

**Rows 1 and 2 are the reason this needs reasons.** Both land the player in the degraded regime, but
one is fixed by dropping mass and the other by not staging away your good core — and the two are
indistinguishable from the cockpit without being told.

**Two residual gaps, neither fatal:**

- **Continuous degradation has no transition to announce.** Sliding from 1.05x to 1.4x produces no
  event, so the player feels it worsening with nothing said. Acceptable: the entry callout names the
  regime, the wobble conveys the severity, and the PAW carries the number.
- **Screen messages are missable.** A player in map view during staging sees nothing, and then has no
  persistent indicator short of right-clicking the part. Cheapest fix that needs no new UI: while
  degraded, **re-post a short reminder every ~30 s** rather than only on entry. Worth doing —
  a missed callout is the difference between "my avionics is undersized" and "this mod is broken".

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

~~Resolved by 4b as revised: auto-disengage on rising mass fires exactly here, so docking to something
heavy stands the unit down into a clean lock rather than starting a wobble against a station.~~

**That resolution was a claim, not a verified fact, and it was wrong in practice (2026-08-24.)** The
prediction — "wobble during proximity operations is considerably more dangerous" — was exactly right;
the mitigation had a race. Auto-disengage was armed by a one-shot `_coupledThisTick` bool consumed by
whichever throttled tick landed first after `onPartCouple`, and that event fires while KSP is still
merging the two vessels. A tick that read the **pre-dock** `vessel.totalMass` found `mass > capacity`
false, cleared the flag, and left that unit engaged permanently — while its neighbours, evaluating on
different phases, stood down correctly. Since the budget is a **MAX and not a sum**, a single straggler
sets the whole vessel's rating.

Confirmed in `saves/default3` on the **Mirmir** station: of four rated units, the 20 t, 25.09 t and 35 t
units are all `guidanceEngaged = false`, and the 51.68 t procedural core is still `true`. (Mirmir itself
is fine — the bracket falls out of auto-*re*-engage being ungated, so a disengaged unit re-engages within
a second of the vessel dropping under its rating: 35 t < Mirmir ≤ 51.68 t, i.e. r ≤ 1 and clean. The
station only bites when something docks and pushes it over the largest unit.)

Now a 3 s wall-clock **window** that expires by time rather than by consumption, plus an immediate
re-evaluation on the coupling frame, in both module types. Combined with the removal of the additive
cell, the docking case degrades to a clean stand-down instead of a wobble.

### 4f. Tuning must work out of the box across vehicle sizes — addressed by Hz scaling, needs confirming

`sigma` is a fraction of control range, but the *consequence* depends on inertia, TWR and aero. A
value that gently wallows a 300 t launcher may be lethal on a 5 t probe. If it turns out
size-dependent, sigma needs a term that is not just the overload ratio, and the design gets
materially uglier. **Test small probe vs large launcher before fixing any numbers.**

Downgraded from "could sink the design" by 4b: with noise opted into rather than stumbled into, a
player who never engages an overloaded unit never meets the tuning at all.
