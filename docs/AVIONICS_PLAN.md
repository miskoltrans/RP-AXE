# Avionics overload — complete build plan

Companion to `docs/AVIONICS_NOISE.md` (the design) and `docs/AVIONICS_AUTHORITY.md` (the rejected
predecessor). This is the whole of the work, planned before building.

**The rule this plan was built around: the exact mechanic stayed OPEN.** Everything except Phase D was
independent of which perturbation won, and improves the shipped lock system on its own.

> **DECIDED (2026-08-14): `adversarial` ships, and it is the only mechanic left in the code.** The other
> ten consequences are deleted — files, knobs and branches — rather than parked behind a chooser. Over
> capacity NEVER locks: `LocksInstead`, the hard cutoff and `RatioCut` went with them, so discrete
> "unguided" now survives only as a property of the part (Unguided/Science-Core, capacity 0, or no
> avionics at all). Roll is degraded like pitch and yaw; the `noise roll` switch is gone.
>
> **AMENDED same day, from flying it.** Two escapes the policy on its own could not close:
>
> - **RCS translation was never corrupted at all.** The post-autopilot hook is rotation-only (deliberate:
>   translation noise on a launcher burns RCS unfelt), so `X/Y/Z` reached the thrusters clean at any
>   overload. Docking and station-keeping were the one place an autopilot absorbed the whole mechanic.
>   Translation now gets its own path inside the existing `ModuleRCS` prefix/postfix window.
> - **Three of the four cells are PROPORTIONAL** to the command (`overgain`, `washout`, `lag`), so small
>   inputs buy small errors — "ask for less" is a partial escape, and autopilots are good at it.
>
> Both are closed by bringing **`misdirect` back as an always-on BASE LAYER** under the policy rather than
> as a competing mode: it rotates instead of scaling, so the wrong-axis fraction is `cos θ` at any
> magnitude, and it is stateless, which is the only kind of corruption safe to run per-thruster on Unity's
> Update phase. Same rotation for gimbals and for RCS in a given frame — one drifting IMU, one wrong frame.
> `misdirect deg = 0` turns the layer off, which is the A/B against the bare policy.
>
> **`arm on` now defaults to `any input incl throttle`** (was `always`). It was `always` only because a
> mode that fires intermittently is harder to A/B; with the mechanic settled the design claim wins, and a
> base layer that runs under every cell needs a safe harbour — this makes it "stop asking for anything"
> rather than "ask quietly".
>

> **AMENDED 2026-08-24, from an assembled station — the `drift` cell is REMOVED and the mechanic is now
> ZERO IN, ZERO OUT.** Reported as "uncommanded input on big stations, RCS and engines go crazy", and it
> was not a tuning problem:
>
> - σ has **no dynamic range above r ≈ 1.5**. `k = 11.5` was anchored on a launch-vehicle sentence
>   ("20% over is hopeless" → σ(1.2) = 0.9), which gives σ(1.5) = 0.997 and σ(2) = 0.99999. A launch
>   vehicle lives at r ∈ [1.0, 1.3]; an **assembled station lives at r ∈ [2, 10]**, entirely off the end
>   of the curve, so every station sat at maximum severity regardless of how far over it was.
> - `drift` was the one **additive** move, by design — it is selected when there is no command to be
>   proportional to. At σ ≈ 1 that is a **full-deflection random command on all three axes**, at
>   `2/m^(1/3)` Hz, into a vessel that was only holding attitude.
> - It **self-armed**. `arm on = any input incl throttle` reads the *post-autopilot* command, and SAS
>   holding a station emits well over the 0.01 deadband. drift → SAS fights it → the fight arms drift.
>
> **RE-AMENDED 2026-08-25 — the third bullet was the only real cause, and the cell is restored.**
> Reported as "I executed a scheduled burn no problem at 2× over capacity". Removing `drift` fixed the
> station, but it also removed the mechanic's teeth everywhere, because **every other move is
> proportional to `|command|`** — so the rule that actually shipped was *small in → small out*, and an
> autopilot holding a vector commands almost nothing. Worse, on any MechJeb-driven attitude the
> corruption **never reached the actuators at all**: AXE wrote at `OnPostAutopilotUpdate`, MechJeb
> writes at `OnFlyByWire` (after us) and assigns the axes outright. See `AVIONICS_NOISE.md`, amendment
> of 2026-08-25, for both.
>
> The rule is now stated the way it was always meant: **the input is a SWITCH, not a volume knob.**
> Zero in → zero out; *any* input → chaos at full σ. `ApplyChaos` is the old `drift` cell verbatim in
> amplitude, promoted from a policy cell to a **base layer gated by arming alone**. The station fault
> stays fixed by attacking its actual cause — **arming now reads intent** (raw stick sampled pre-
> autopilot, commanded throttle, a held autopilot target), never the post-autopilot command, so nothing
> downstream of our own corruption can re-arm us.
>   A penalty that cannot be stopped by stopping is not a cost, it is a fault.
>
> The empty cell is now a **no-op** (`idle` in the PAW, renamed from `drift`). Every remaining move is
> proportional to the command, a pure time shift of it, or a rotation of it, so **all four are exactly
> zero at zero input, at any σ**. `NoiseSample`, `PerlinGain`, the `NoiseWhite` field and the
> `DEBUG: white noise` knob go with it — nothing else called them.
>
> **What this knowingly gives back: "fly gently and you are safe" during a coast.** That was the whole
> point of the cell and the reason `adversarial` beat `effort gain` (below). The trade is accepted: the
> escape only exists when the pilot is commanding *nothing*, everything from "hold it" onward is
> unchanged, and an undersized unit still cannot fly its vehicle. It just no longer attacks a vessel
> nobody is flying. The dominant-escape argument below should be read as **historical from this date**.
>
> **Also fixed in the same pass — the auto-disengage-on-dock race.** `_coupledThisTick` was a one-shot
> bool consumed by whichever throttled tick landed first after `onPartCouple`; that event fires while KSP
> is still merging the vessels, so a tick reading the **pre-dock** `vessel.totalMass` cleared the flag and
> the unit stayed engaged for good. Because the vessel budget is a **MAX across units, not a sum**, one
> straggler pins the entire vessel at saturated σ. Seen on **Mirmir**: three of four rated units
> disengaged, the fourth (51.68 t) did not, and it alone set the station's budget. Replaced with a 3 s
> wall-clock **window** that expires by time instead of by consumption, plus an immediate re-evaluation on
> the coupling frame. Both module types.

> ~~**The `DEBUG:` knobs deliberately STAY** — this is where D4 is knowingly incomplete. Every one drives
> something: the strength curve, the regime split, one of the four moves, or the base layer. Two constants
> were PROMOTED to knobs in the same pass — regime dwell and regime margin — because they are the two
> numbers that decide legibility, and legibility is what the mechanic still has to be tuned for. Stripping
> the rig is the last commit before ship, not part of this cleanup.~~
>
> **DONE 2026-08-24 — the rig is stripped and the numbers are LOCKED IN. D4 is closed.** All 17 `DEBUG:`
> PAW entries are gone, along with `PushDebugKnobs()`, the `ModifierTicks`/`LastNoise` hook diagnostics,
> the `dc`/`ac` tuning readouts and the `SetupModeChooser`/`PopulateChooser` pair that existed only to fill
> the arm-mode dropdown. Every tunable is now a `const` in `AxeControlLockerUtils`:
>
> | const | value | why this number |
> |---|---|---|
> | `NoiseK` | 11.5 | anchored: σ(1.2) = 0.9 — "at 20% over its rated mass a unit is hopeless" |
> | `OvergainSlope` | 10 | anchored: G(1.2) = 3, since typical loop gain margin is 2–4× |
> | `NoiseHz` | 2 | C in `C/m^(1/3)`, so each vehicle is perturbed at its own attitude-response frequency |
> | `RegimeTauCycles` | 3 | EMA window in response cycles — must be slower than the vehicle itself |
> | `AdversarialAcGain` | 3 | the balance knob; tuned for a *spread* across the four cells, not a value |
> | `AdversarialDwellSec` / `AdversarialMargin` | 2 s / 0.15 | the two legibility numbers: long enough to read, sticky enough not to flap |
> | `DelayTicksMax` | 10 | 200 ms at 50 Hz — already past what destabilises most controllers |
> | `MisdirectMaxDeg` / `MisdirectRateHz` | 90° / 0.6 Hz | 90 = the intended axis gets nothing; 0.6 Hz = too fast to adapt to, too slow to be filtered |
> | `ArmDeadband` | 0.01 | reads post-autopilot, so a strict `> 0` would arm always |
>
> **Three A/B switches are gone rather than frozen**, because each one's comparison is settled and each
> shipped in its OFF position: `NoiseMax` (a ceiling on a curve that already asymptotes to 1), `NoiseDrift`
> + `DriftHz` (non-stationary overgain slope, never shipped on), and `NoiseHzAutoScale` (flat-Hz mode, only
> ever there to A/B against mass scaling). `NoiseOverrideEnabled`/`Value` — the σ pin that let one craft fly
> the same profile at several values — goes with them, including its early-return in `ShouldLock`.
> `ArmMode` is locked to `any input incl throttle`; the other two modes and `ArmNames` are deleted.
>
> The removed `KSPField`s were `isPersistant`, so existing saves carry values for fields that no longer
> exist. KSP ignores unmatched save values, so this is a silent no-op — no save migration needed.
> `EffectiveNoiseHz` is the only mutable static left in the file, and it is per-vessel live state written
> by the controller, not a knob.

| phase | what | gate | status |
|---|---|---|---|
| **0** | penalty abstraction layer | — | **DONE** (`a5c9845`), then **DELETED** — its job was to let the losers be removed by removing files, and that is what happened |
| **A** | player-facing behaviour | — | **DONE** (A1–A5) |
| **B** | RP-1 parity audit + fixes | — | B1/B2 decided; B3 to build |
| **C** | sack the EC penalty | — | **DONE** |
| **D** | fly the modes, pick one, clean up | needs A+B+C | **DONE 2026-08-24** — mechanic chosen, losers deleted, D4 closed: rig stripped and every tunable frozen as a `const` |

---

## Phase 0 — penalty abstraction (DONE, then removed)

`AxeControlPenalty` + `AxeControlPenalties` held eleven selectable consequences behind one interface,
chosen at runtime from the core's DEBUG mode knob. It existed so the surrounding work could be built and
flown while the mechanic stayed open, and so the losers could be deleted by deleting files. Both happened:

| # | id | family | outcome |
|---|---|---|---|
| 0 | `none` | experimental control | deleted |
| 1 | `lock (RP-1)` | RP-1's rule — the A/B baseline and the fallback | deleted |
| 2 | `uncommanded` | disturbance | survived as the `drift` move; **removed 2026-08-24** — see the amendment above |
| 3 | `on input` | disturbance | deleted |
| 4 | `overgain` | margin attack — gain margin | **survives as the `overgain` move** |
| 5 | `coupling` | margin attack — decoupling | deleted |
| 6 | `delay` | margin attack — phase margin | **survives as the `lag` move** |
| 7 | `dropouts` | availability | deleted |
| 8 | `misdirect` | margin attack — reference frame | **restored as the always-on base layer** |
| 9 | `effort gain` | closed loop — by depth | deleted |
| 10 | `adversarial` | closed loop — by choice | **SHIPPED — it is the mechanic** |

The families were the argument, not the list. Disturbances get **rejected** (that is what a loop is for);
margin attacks are not rejectable but are **open-loop and therefore learnable**. The last three escape
both: `dropouts` randomises whether the command lands at all, and 9/10 make the corruption a function of
the loop's own output, so there is no fixed point for an adaptive controller to converge on.

Four of the eleven survive, but **not as modes** — as the move set 10 plays from. `washout` is the
fourth, and it was never a mode: it was rejected as one (below) and only works as a move.

### The test that separates 9 from 10 — a dominant escape

`effort gain` is **monotone in effort**, so *minimise effort* beats it: fly gently and the penalty
withdraws itself. A mechanic with a dominant escape strategy is a tax you can route around, not an
adversary, and the fix is not a deeper penalty — it is to make **every escape the entrance to another
attack.**

`adversarial` therefore adds no corruption of its own. It splits the recent command into a sustained
part and a transient part, and plays the move whose own effect is largest in that cell:

| | **not moving it** | **moving it** |
|---|---|---|
| **holding little** | `uncommanded` → `idle` (no-op) since 2026-08-24; **the additive move returned 2026-08-25 as an always-on base layer, not a cell** | `overgain` |
| **holding a lot** | `washout` | `delay` |

- ~~**Fly gently → `uncommanded`.** The counter to minimal input is the one mechanic that does not read
  input. That cell is the whole answer to the dominant-escape problem.~~ **Removed 2026-08-24.** The cell
  is a no-op; the dominant-escape problem is reopened for a coasting vessel and closed for a flying one.
  **Superseded 2026-08-25:** the move is back as a base layer under *every* cell, so the dominant escape
  is closed for anyone commanding anything — and still open, deliberately, for a vessel commanding
  nothing. The cell stays a no-op; what changed is that the corruption no longer lives in a cell.
- **`overgain` where commands are small** — amplification needs headroom below the clamp; ×3 on 0.3 is an
  event, ×3 on 0.9 merely saturates.
- **`washout` where the command is mostly DC.** Its standalone weakness (the loop just commands
  `1/(1−σ)` harder, which is the authority scalar `AVIONICS_AUTHORITY.md` killed) is what makes it work
  *here*: commanding harder moves you into another cell. Rejected as a mode, correct as a move.
- **`delay` where the command is changing** — pure lag does nothing to a constant command.

**No absorbing state** was the property being bought: do nothing → drift forces a correction → you are
holding or twitching; hold → it decays → you re-command → lag; fight → it destabilises → you back off →
drift. **Since 2026-08-24 there is exactly one absorbing state — commanding nothing.** The rest of the
cycle is intact, so the remedy for anyone actually flying is still a unit rated for the vehicle, which is
the constraint the whole design exists to make binding.

Not in the policy, deliberately: `dropouts`, `misdirect` and `coupling` are strong in *every* regime, so
no cell is theirs. That makes them standalone candidates rather than moves.

The fiction is not a malicious computer — it is a **gain schedule characterised for a different
vehicle**. Real control laws are scheduled per flight regime; an under-rated unit's table is wrong in
every cell, and wrong in a different way in each.

### Arming — a third axis, orthogonal to all of the above

*When* the penalty is live is a separate question from *what* it does, so it is a gate on every mode
(`DEBUG: arm on`) rather than three near-copies of mode 10. The axis it varies is **how much safe
harbour the player gets** — how much of the envelope they can retreat into and be certain nothing is
being done to them:

| setting | safe harbour | consequence |
|---|---|---|
| `always` | none | a craft over capacity is corrupted even sitting still doing nothing |
| `any input incl throttle` | **fully idle** — not burning, not steering | **LOCKED IN, and since 2026-08-25 it is the whole gate:** it decides both base layers (`chaos` and `misdirect`), so it is what buys back the null-stick safe harbour. Measured from **intent** — raw stick sampled pre-autopilot, commanded throttle, a held autopilot target — never the post-autopilot command, which is what made `drift` self-arming |
| `steering only` | **not steering** — burning is free | as above; the difference between the two modes is now whether a hands-off *burn* is interfered with |

The middle setting is the real design claim: **a flight computer that is not being asked for anything
should not fail.** It is also the cheapest answer to the §4a objection that noise is active sabotage
against a capsule riding a stage it is not flying — under `always` that needs the Engage/Disengage
toggle to answer it; under either gate it largely answers itself.

**Deadband, not `> 0`.** The hook runs post-autopilot, so what it reads is the vehicle's program, not a
human stick, and MechJeb and SAS emit small nonzero commands continuously. A strict zero test would read
armed essentially always and collapse the three variants into one — which would look exactly like the
gate not working.

Disarmed passes σ = 0 rather than skipping the penalty, so every stateful move keeps advancing and
re-arming cannot read a stale delay buffer or a cold EMA and jump.

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

### A3 Regime callouts — **DONE**
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

### A4 VAB legibility — **DONE**
On both module types:

    Capacity        15.00 t
    As configured    9.20 t   (0.61x — clean)
    At full tanks   22.40 t   (1.49x — degraded)

Full-tank mass = current mass + `sum over resources of (maxAmount - amount) * density`. Closes the
under-fuelling hole in one line: launch with tanks emptied to save mass, fill on site, and a
configured-mass-only warning was computed against a craft that never flies. Covers ISRU, orbital
assembly and launched-dry with no ISRU-specific machinery.

### A5 `useThrottle` bypass — **DONE**
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

### D1 Mode comparison — **FLOWN, DECIDED**

One craft, `pin noise` on, the modes at sigma = **0.44** (~5% over) and **0.68** (~10% over), flown as
controlled A/Bs: **4 `overgain` → 9 `effort gain` → 10 `adversarial`** (same slope throughout, so
each step changes exactly one thing — fixed gain, then gain scheduled on the loop's own effort, then
the move itself chosen to match the regime), and **2 `uncommanded` vs 3 `on input`**.

The prediction on record was *"coupling wins, overgain second, delay too sharp, both noise modes
absorbed"*, plus a second one: **10 is the strongest and the least legible.** The second is what the
decision rests on. `adversarial` ships, and the ten losers are deleted rather than kept selectable — a
chooser with one live option is a branch that has to be reasoned about at every call site for no benefit,
and `LocksInstead` / `Stateful` were exactly that kind of branch.

The question 10 had to answer, and still has to under tuning: watch the regime readout and check whether
it **tracks what you are doing** or **thrashes**. A thrashing readout means the AC gain is wrong and the
mechanic is being judged on a tuning artefact; a readout that sits in one cell for a whole ascent means
the policy never engaged and only one move is really being tested. `DEBUG: injected` now prints `dc`/`ac`
next to the regime name for exactly this — the name alone cannot tell "correct" from "stuck", and dc/ac
say which way it is wrong (dc pinned high → window too long; ac pinned high → AC gain too high).

### D1-bis Arming comparison — still open, knob retained

`arm on` at each of its three settings, same craft, same sigma. These bracket the space rather than
sampling it, so one of the three is the answer:

- **`always`** — the current default. Is being corrupted while doing nothing *broken*, or *a vehicle
  that will not sit still*?
- **`any input incl throttle`** — the one to beat. Keeps the no-escape property while removing the
  "corrupted while idle" complaint, so if it feels as strong as `always` it wins on both axes.
- **`steering only`** — the permissive end, with a known structural cost: it makes coasting safe, so the
  `drift` cell becomes nearly unreachable. Worth flying anyway — if it feels *no weaker*, that is
  evidence the drift cell was never carrying its weight and this is really a three-cell design.

### D2 Scaling check — outstanding
Small probe vs large launcher, same sigma, `Hz scaling` on then off. Comparable effect across sizes = the
design survives. It now touches two things rather than one: `noise Hz (C)` sets the drift cell's frequency
**and**, through `EffectiveNoiseHz`, the regime window's real length in seconds — so a scaling error
shows up as the wrong *cell mix* on heavy craft, not merely as the wrong feel.

### D3 Legibility check — needs A3
Fly overloaded without being told what to look for. Reads as *undersized avionics* or as *a broken mod*?
**This gates the ship, and it is what `regime dwell s` and `regime margin` exist to tune.**

### D4 Cleanup — **PARTIAL, deliberately**
Done: the losing penalty classes and `AxeControlPenalty.cs` deleted; the mode chooser and every knob
belonging to a dead mode removed (`noise roll`, `hard cutoff`, `mode`, `dropout ms`, `RCS noise scale`,
`noise on RCS`; `misdirect deg` and `precess Hz` came back with the base layer); the RCS re-application path removed with them (a
stateful mechanic must be applied exactly once, and the post-autopilot hook already mutates the ctrlState
ModuleRCS reads); the lock/cutoff branches removed from `ShouldLock`; docs rewritten to describe what
shipped.

Not done, on purpose: **the `DEBUG:` rig stays** until the numbers are nailed down. Stripping it is the
last commit before ship, and at that point the surviving values get frozen into the code.

### D5 Failure exit — spent
There is no `PenaltyLock` to fall back to any more. If the mechanic fails D3 the fallback is a new
decision rather than a knob — the cost of deleting the losers, accepted knowingly.

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
