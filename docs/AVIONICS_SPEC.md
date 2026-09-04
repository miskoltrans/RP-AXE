> **SUPERSEDED IN PART (2026-08-01).** The "Under-capacity penalty", "Multiplier ceiling" and the open
> `k` calibration item below describe an EC overload penalty that **no longer exists** — it was deleted
> in Phase C of `docs/AVIONICS_PLAN.md`. It was inert against a ~39-hour battery in a 6-10 minute
> ascent, both of its recorded justifications had collapsed, and named parts could never share a
> consequence measured in watts. Removing it is also RP-1 parity: RP-1 has no overload EC term either.
> Going over capacity is now **adversarial regime matching** (`AxeControlLockerUtils`), shared by
> procedural and named units alike: the craft keeps control and the command is corrupted by whichever of
> four moves beats what the pilot is currently doing. It never locks. The `k` open item closes by
> removal. Everything else in this document still stands.

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

## Axis 2 — Standard / Deep-Space Bus (RENAMED 2026-08-05), stands in for RP-1's Deep-Space, Guided-only

> **RENAMED 2026-08-05: "Unshielded / Radiation-Shielded" → "Standard / Deep-Space Bus".** The earlier
> "naming CONFIRMED" was wrong and this supersedes it. The mass premium was never a radiation claim:
> RP-1's own `AVIONICSCONFIG` description calls it *"added complexity (Thermal/Radiation Shielding, Star
> Trackers, etc.)"* — a whole-bus premium in which radiation is one line item and not the load-bearing
> one. The old AXE name narrowed that defensible bundle down to the single justification that does not
> survive scrutiny: Earth's Van Allen belts are a *harsher* radiation environment than deep space, so
> "you need shielding to leave Earth" reads backwards as physics. Judged as a deep-space **bus** premium
> — thermal mass, MLI, star trackers, redundancy, bigger antenna — the same numbers are directionally
> correct and physically honest. **No mass/cost/mechanic changed; only the name was wrong.**
>
> Scope of the rename: 10 `shd_*` node titles in `tree/nodes.yaml`, the two PAW strings in
> `ModuleAxeAvionics.cs` (`"Switch to Deep-Space Bus"` / `"Switch to Standard Bus"`), and this doc. The
> `shd_*` node **ids**, the `shTech`/`shMassFactor`/`shCostFactor` config keys, and the persistent
> `shieldedEnabled` field are all deliberately UNCHANGED — they are silent string bindings (and one is
> save-breaking), and per `docs/BUG-CLASSES.md` renaming them fails closed and quiet.
>
> **Also moved `shd_basicAvionics` T6 → T5** (re-parented `gnc_basicAvionics` → `gnc_earlyAvionics`,
> since `build_tree.py` requires forward edges and `gnc_basicAvionics` is itself T5). Rationale:
> `tel_dopplerRanging` (commsTL1, "Lunar Range Comms") is T4, so the gap between "can talk to the Moon"
> and "can build something that survives there" is now one tier instead of two. **That gap is the
> mechanic, not slack** — it is the flyby-and-impactor era. Do not close it to zero: ladder indices 0-3
> carry `shMassFactor` copied verbatim from their Unshielded values, so a T4 rung would grant the
> deep-space bus at *zero* premium, and index 3 has no `shTech` so it is not selectable at all.
>
> Known consequence of the re-parent, accepted not fixed: this rung no longer requires its paired
> Unshielded tier, so `gnc_earlyAvionics` (idx 3, massFactor 59.13) + this node yields the idx-4
> Deep-Space factors (55.168) — lighter than the player's own Unshielded tier, though dearer (85.26 vs
> 54.13). That is a cross-*generation* comparison; the invariant that matters (same-tier premium,
> 55.168 > 50.153 at idx 4) still holds. Fixing it would mean authoring idx-3 Deep-Space numbers RP-1
> never had.

Tech-gated second choice, only available once appropriate tech is researched (mirrors RP-1: Deep-Space wasn't
available from `start`, it unlocked around Near-Earth's `basicAvionics`-equivalent point). Unguided/
Science-Core never had a Deep-Space equivalent in RP-1 either — this axis doesn't apply to it.

### Attitude reference ("star tracker") — DECIDED 2026-08-05, ✅ **BUILT the same day** (`047ae1d`)

**As shipped:** `ModuleAxeAvionics.ProvidesAttitudeReference` (`!dead && guidanceEnabled && ShieldedActive`)
drives `targetSASServiceLevel` — a vessel with no Deep-Space Bus gets SAS level 0, i.e. no attitude hold.
`AxeAvionicsController.VesselHasAttitudeReference()` is the vessel-wide check. Same on
`ModuleAxeFixedAvionics` for the named parts.

**Why this exists.** Measured this session: the Deep-Space Bus bought *nothing* beyond hibernation, and
hibernation itself was worth 2.5 W (see `docs/AVIONICS_COMPARISON.md` differs-item 8 — the `idleFactor`
bug that made it worthless is now fixed, restoring it to 47.3 W). Even so, one job is thin for +10% mass
and +50% cost. Attitude reference is the second job, and it is the physically honest one: near Earth you
can navigate on horizon sensors and magnetometers; past Earth it's a sun sensor and a star tracker or
nothing.

**Bundled into the bus, no separate tech node.** Deliberate — RP-1's own config description bundles the
same way ("Thermal/Radiation Shielding, **Star Trackers**, etc."), and splitting it out would re-thin the
axis immediately after thickening it. Note `library.yaml` still holds unplaced `opt_starTracker` (T4) and
`gnc_opticalNav` (T6); if either is ever placed it should be framed as the *instrument/technique*, not the
capability, or the tree will appear to sell star trackers twice.

**Rule — PURE BUS TIE (user call 2026-08-05): "SAS 0 and controller off for Standard, everywhere."**

| | Standard bus | Deep-Space Bus | crewed |
|---|---|---|---|
| stock SAS | `targetSASServiceLevel` **0** (gyro attitude-hold only) | 3 (full) | 3, always |
| MechJeb `SmartASS` | disabled | on | on |
| MechJeb `NodeExecutor` | disabled | on | on |
| MechJeb **ascent guidance** | **ON — never gated, by anything** | on | on |
| everything else in MechJeb | untouched | untouched | untouched |

No SOI check, no distance check, no tech check beyond owning the bus. The scoped-to-outside-Earth-SOI
alternative was offered and **rejected** — a pure bus tie is the gameplay. Resolved across two rounds:

**Round 1 got the layer wrong.** The first plan disabled `MechJebModuleAttitudeController`. That is the
shared *service*, not a capability — `Core.Attitude` keeps a `Users` list, and `MechJebModuleNodeExecutor`,
`MechJebModuleAscentBaseAutopilot` and `MechJebModuleSmartASS` all register into it via
`Core.Attitude.Users.Add(this)`. Disabling the service therefore also killed **ascent guidance**, which is
near-Earth technology with nothing to do with star finding — a V-2 flies a pitch program on gyros and local
vertical and never sees a star. Gate the *clients*, leave the service running.

**The line is: does the capability need absolute attitude in an inertial frame?**

| capability | inertial frame? | verdict |
|---|---|---|
| ascent guidance | no — pitch program vs local vertical | never gated |
| docking / rendezvous | no — relative nav off the target | untouched |
| landing guidance | no — surface-relative, altimetry | untouched |
| SmartASS vector holds | **yes** — prograde/normal/target need an orbital frame | bus-tied |
| node executor | **yes** — same, plus precision | bus-tied |

That line matches the stock SAS ladder exactly: level 0 is gyro attitude-hold, levels 1-3 are the
frame-dependent holds. So both halves of the mechanic say the same thing.

**Ascent guidance is NOT tech-gated either (user, 2026-08-05).** A `unlockTechs` autonomy ladder was
proposed and declined — all 16 MechJeb modules stay at `unlockTechs = start`. Nothing in this design
touches `unlockTechs`.

**Accepted consequence, and the point of the whole thing:** on a Standard bus you cannot execute a maneuver
node anywhere, **including LEO**. You place stock KSP nodes and hand-fly them. That is the intended early-
game texture, not collateral damage.

**Crewed is free — but it needed a special case after all (2026-08-13).** The original claim here was
that vessel SAS resolves as a MAX across parts through `part.PartValues.AutopilotSkill`, so a crewed
pod's own `ModuleSAS` wins automatically. The MAX is real; the pod's `ModuleSAS` is not. Of the 72
crewed command parts in the live MM cache, **52 carry no `ModuleSAS` node at all**, 11 sit at level 1
and only 9 at level 3. Stock's other contributor is the crew's own `AutopilotSkill` experience effect,
whose value is `Parent.CrewMemberExperienceLevel()` — the kerbal's XP level, and only the Pilot trait
has the effect. So in practice a rookie pilot gave stability assist and nothing else, and an
engineer- or scientist-only crew gave **no SAS at all** (with no contributor the value stays at its
`-1` default, and `AvailableAtLevel` fails even for mode 0).

The rule AXE wants is the one the MechJeb half already enforces — a human aboard *is* the attitude
reference — and crew progression is cut forever, so XP is not a currency the player plans around.
Both halves now say it: `design/Settings/AxeCrewAutopilot.cfg` gives Engineer and Scientist the
`AutopilotSkill` effect (Tourist excluded), and `Avionics/AxeCrewSasSkill.cs` postfixes
`AutopilotSkill.GetValue` to a flat 3. The value, not `AvailableAtLevel`, so every consumer of
`VesselValues.AutopilotSkill` agrees. Config alone cannot do it: `GetValue` reads neither the EFFECT
node's `level` nor its `modifiers`.

**Implementation notes (all ground-truthed 2026-08-05):**
- Write **`targetSASServiceLevel`**, NOT `SASServiceLevel` — `ModuleSAS.FixedUpdate` recomputes the latter
  every frame from the former (`SASServiceLevel = ApplySASServiceLevelAdjustments(targetSASServiceLevel)`).
  Writing `SASServiceLevel` is clobbered within a frame. AXE already sets level 3 at
  `AxeAvionicsCore.cfg:473`, which works only because MM lands it before `OnStart` copies it across.
- MechJeb **ignores `SASServiceLevel` entirely** — no reference to it, `AvailableAtLevel`, `CanEngageSAS`,
  or `AutopilotSkill` anywhere in the binary. `MechJebModuleAttitudeController.Drive(FlightCtrlState)`
  either writes ctrl state directly or calls `vessel.Autopilot.SAS.SetTargetOrientation()`, and neither is
  gated by service level. It must be closed separately.
- Disable exactly two clients by name: **`MechJebModuleSmartASS`** and **`MechJebModuleNodeExecutor`**.
  Reach them via `MechJebCore.GetComputerModule(string)` (it has a string overload, so AXE's existing
  duck-typed reflection needs no new type references) and set `ComputerModule.Enabled = false`. Verified
  respected: `MechJebCore.Drive` gates on `if (computerModule.Enabled)` before calling each module's
  `Drive(s)`. Do **not** touch `MechJebModuleAttitudeController` — see round 1 above.
- Do not use the already-reflected `MechJebCore.DeactivateControl` for this. It kills *all* MJ control on
  the vessel, ascent guidance included. It stays for the existing dumb-craft case only.
- MechJeb is resolved per *vessel* via the master core, so the MechJeb half needs the vessel-MAX and the
  crewed exemption applied **explicitly** — unlike stock SAS, where `part.PartValues.AutopilotSkill` gives
  both for free.

**Vessel MAX (user, 2026-08-05).** If ANY core aboard provides attitude reference, the whole stack has it —
matching how stock SAS already resolves across parts. So a Deep-Space payload covers its own launch stack.

### Thermal control — BUILT 2026-08-05

**The mechanic is: you spend power to stay warm.** The inverse of everything KSP models. A craft radiates
continuously into a ~3 K sky and gets heat back only from absorbed sunlight and its own dissipation; far
from the Sun the income collapses and the loss doesn't. Real consequence, not flavour — batteries lose
capacity cold, and hydrazine freezes at ~2 °C, so every propellant line on a deep-space probe carries
heater tape. Nothing else in the modlist models this: stock has no "too cold" state at all, and
Kerbalism's temperature is habitat/crew comfort (`per_capita`).

```
Q = k · A · ( (T_min/T_set)⁴ − (1 − deficit) ),   clamped ≥ 0        [steady state]
deficit_vac = 1 − sunlit·(homeSMA/r)² − skyFrac·f_IR·(homeSMA/r_body)²,  clamped 0..1
deficit     = lerp( deficit_vac, 1 − (T_amb/T_set)⁴, coupling ),      clamped 0..1
coupling    = 1 − stock densityThermalLerp(ρ)      (0 in vacuum, →1 in dense air)
k = ε_eff · σ · T_set⁴     (σT⁴ = 418 W/m² at 293 K, so k = 418 × ε_eff)
A = 0.04 · m_dry^(2/3)     (VESSEL dry mass, kg)
```

**Two things in that formula are not what this section originally shipped, and the table below is the
first one to reflect either** (corrected 2026-08-18, found while auditing a craft whose heater bill looked
too big):

- **`A` is the vessel's, not the avionics box's** (changed 2026-08-05). It is the whole spacecraft that
  radiates. Box area was wrong by ~7×: measured across 74 cores in the dev save, real probe cores are
  0.017 m³ / 0.39 m², against the 0.30 m³ / 2.69 m² the original calibration assumed. Checked against real
  spacecraft — Luna 1 at 361 kg → 2.0 m² (actual sphere ~2 m²), Voyager at 825 kg → 3.5 m² (actual bus
  ~4 m²). **This makes the load scale with the craft**, so one table can no longer cover the game; the two
  below bracket the range.
- **The atmospheric term** (added 2026-08-31). The original model was a pure radiative balance with no
  convection at all, so it billed heaters by insolation even inside dense air. Measured before the fix: a
  rocket on the pad at night drew **58%** of a deep-space heater load in 288 K air, and a lander on the
  737 K night side of Venus drew **42%**. `T_amb` is `body.GetTemperature(altitude)` and `coupling` reuses
  stock's own `CalculateDensityThermalLerp` curve inverted, so AXE and `FlightIntegrator` grade an
  atmosphere the same way. Writing the ambient case as an equivalent *deficit* leaves `StepThermal`, the
  planner and background untouched, and `Q` passes through zero at exactly `T_amb == T_min` with no extra
  clamp — the two terms cancel. Stock's mach shock-compression factor is deliberately dropped: it would tie
  the heater budget to post-shock entry temperature, which the part thermal system already owns. Vacuum
  cases are bit-identical (coupling is 0 above `atmosphereDepth`); Titan barely moves (75.2% → 74.3%,
  correctly — it really is 95 K), while the pad, Venus surface and deep Saturn entry all go to 0%.

- **The 273 K deadband** (`ModuleAxeAvionics.StepThermal`). The heater does not hold the 293 K setpoint —
  it does nothing until the bus would fall through the 273 K battery floor and then holds exactly that.
  So the ceiling is the loss at 273 K, `(273/293)⁴ = 0.754` of `k·A`, not `k·A`. The original table
  charged the full `k·A·deficit`, i.e. ~33% high at every distance.

**It still asymptotes** — as `r` grows the solar term vanishes and demand tops out at that 0.754 ceiling.
That is why the outer system doesn't spiral. Cruise (deep space, sunlit, nothing nearby to radiate back):

| bus | ε_eff | k | Earth | Mars | Ceres | Jupiter | Saturn | Neptune |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **Voyager-class, 825 kg dry — A = 3.52 m²** ||||||||
| Standard, no thermal tech | 0.15 | 63 | 0 W | 72 W | 138 W | 159 W | 165 W | **167 W** |
| Standard + full MLI chain (capped) | 0.05 | 21 | 0 | 24 | 46 | 53 | 55 | 56 |
| Deep-Space, no MLI | 0.10 | 42 | 0 | 48 | 92 | 106 | 110 | 111 |
| + `th_hermeticBus` | 0.05 | 21 | 0 | 24 | 46 | 53 | 55 | 56 |
| + `th_extendedMLIWrapping` | 0.03 | 13 | 0 | 15 | 28 | 33 | 34 | 34 |
| + `th_advancedMLI` | 0.02 | 8 | 0 | 9 | 18 | 20 | 21 | 21 |
| **Svetovit-class, 3.22 t dry — A = 8.73 m²** ||||||||
| Standard, no thermal tech | 0.15 | 63 | 0 W | 178 W | 343 W | 394 W | 408 W | **414 W** |
| Deep-Space, no MLI | 0.10 | 42 | 0 | 118 | 228 | 263 | 272 | 276 |
| + `th_hermeticBus` | 0.05 | 21 | 0 | 59 | 114 | 131 | 136 | 138 |
| + `th_advancedMLI` | 0.02 | 8 | 0 | 23 | 43 | 50 | 52 | 53 |

*(Jupiter is already 95% of maximum. A LEO eclipse costs less than Ceres — 48 W and 119 W respectively at
k = 21 — because Earth fills 29% of the sky at 1.1 R and goes on radiating at a craft in its shadow.)*

**Mass scaling is sub-linear**, which is the right shape and worth stating because it is a design lever:
`A ∝ m^(2/3)`, so a 4× heavier craft pays only 2.5× the heaters. **Consequence: flying stacked probes as
one vessel is cheaper than flying them separately** — Svetovit 1's five-probe stack asks 138 W at Neptune
where five separated 640 kg probes would ask 47 W each, 235 W total. Nobody designed that in; it falls out
of surface-area-to-mass, same as it does in reality.

**The scissors.** Solar output falls as 1/r² while heater demand rises on the same curve. Where they cross
is where RTGs stop being optional — and that falls out of physics rather than a tuned threshold. A
Mariner-class 7 m² array gives ~310 W at Earth and ~11 W at Jupiter; a Standard bus there wants 159 W.

**ε_eff values are INSTALLED performance**, not datasheets — seams, penetrations and cable feedthroughs
cost 2–5× over lab figures. Standard sits at 0.15 because near-Earth thermal design is sized for
*rejecting* heat and performs poorly when the load reverses; it is not bare (0.8 → 334 W/m²), it is still
a spacecraft. **This is the tuning dial** — Mars at 72 W for a Voyager-class Standard bus is the number to
watch in play.

**Decisions taken:**
- **~~Box volume, not vessel~~ (user) — REVERSED 2026-08-05.** The original call was that the avionics is
  what must be kept warm, so the box was what should set the area. Ground-truthing the box sizes killed it:
  a real probe core is 0.39 m², so a Luna-class probe was billed 2 W at Jupiter. Vessel dry mass it is; see
  the two bullets under the formula. Nothing else about the mechanic changed.
- **Hibernation does NOT reduce it** (user): the heater doesn't care whether the computer is running, and
  it gives deep space an irreducible power floor. Added to the draw, never multiplied into it. (Strictly,
  hibernating means *less* waste heat and so *more* heater — modelling that would make hibernation a trap.)
- **Eclipse IS modelled (user, 2026-08-05 — reversing the deferral above).** Eclipse thermal cycling is the
  dominant LEO design driver and battery heaters are a real LEO power-budget line, so it earns its place.
  Shadow test is a dependency-free cylindrical occultation of the main body (`InShadow`), so it behaves
  identically loaded, in background, and with or without Kerbalism. In shadow the **solar term goes to
  zero**; the body term does not, which is what stops a LEO eclipse costing the same watts as Neptune —
  Earth keeps radiating IR and bouncing albedo at a craft in its shadow, and from low orbit it fills a
  third of the sky. Tunable via `bodyIrFraction` (0.35 = combined albedo + planetary IR as a fraction of
  the solar constant at that body).
- **Cold side only.** The inner system (Venus 1.9×, Mercury 6.7× flux) is a *cooling* problem costing mass
  in radiators and sunshades, not watts in heaters. Separate mechanic, phase 2.
- **NOT a part-temperature mechanic.** Purely an EC load, so it collides with nothing — not stock thermal,
  not FAR/RO reentry heating, not RealFuels boiloff. Flattening the battery is already fatal.

**`k` is resolved at BUILD time and persisted (`asBuiltThermalK`), frozen at launch** — new features are
built craft-sharing-first (user, 2026-08-05), so a shared `.craft` performs as its designer intended
rather than silently re-deriving from the recipient's research. Same idiom as `avionicsMass`/`avionicsCost`.
The avionics *tier* is still runtime-derived; that rework stays deferred.

**Background vessels re-evaluate live.** `BackgroundUpdate` reads `currentWatts` out of a frozen module
snapshot, which is right for the tier/mass term but wrong for heaters — an unloaded probe coasting outward
gets colder every day, and that is exactly the unattended cruise this exists for. So the background path
subtracts the stale thermal term and recomputes it from the vessel's current distance.

**Cross-lane gate.** `k` rides RealFuels' MLI `PARTUPGRADE`s, which AXE had already re-homed onto its own
Thermodynamics nodes (`th_hermeticBus` T3 → `th_extendedMLIWrapping` T9 → `th_advancedMLI` T11), where they
previously only affected propellant boiloff. So a deep-space bus's thermal performance depends on
*Thermal* research, not Guidance research — and Thermodynamics gains teeth. A Standard bus never benefits
from MLI research at all; that is the capability the Deep-Space Bus sells.

**VAB planning by target body — DONE, and it needed no new UI.** The selector already existed: it is
Kerbalism's own planner, whose body and sunlight/shadow pickers feed straight into
`PlannerUpdate(resources, CelestialBody body, environment)`. AXE was discarding **both** parameters and
reporting a flat number. It now reads `environment["sun_dist"]` and `environment["sunlight"]` (keys from
`KERBALISM.Planner.ResourceSimulator`) and reports the real heater load for the selected body and lighting
state. The static `Thermal at deep space` PAW readout stays as a quick asymptote reference.

**Live numbers as built** (0.30 m³ box, A = 2.69 m², Standard k=63 | best MLI k=8):

| situation | deficit | Standard | best MLI |
|---|--:|--:|--:|
| LEO 400 km, sunlit | 0.000 | 0 W | 0 W |
| LEO 400 km, **eclipse** | 0.884 | **150 W** | 19 W |
| GEO, eclipse | 0.998 | 169 W | 21 W |
| Lunar orbit, eclipse | 0.882 | 149 W | 19 W |
| Mars orbit, sunlit | 0.524 | 89 W | 11 W |
| Jupiter cruise | 0.963 | 163 W | 21 W |
| Neptune cruise | 0.999 | 169 W | 21 W |

**RESOLVED 2026-08-05 — Standard rides the ladder, capped.** The earlier "Standard never benefits from MLI
research" rule was *ahistorical*, and eclipse is what exposed it: keeping a bus alive through eclipse is a
1957 problem that was **solved in 1957**. Sputnik 1 was a pressurised nitrogen sphere with a polished skin,
a fan and a thermal switch — the satellite essentially *was* its thermal-control system. Explorer 1
balanced absorptivity against emissivity with nothing but stripes of paint. Neither carried a heater.
`th_hermeticBus` is literally that node, and it is already at T3.

So a Standard bus's floor is **passive thermal control**, not deep-space blanketing:

| researched | Standard k | Deep-Space k |
|---|--:|--:|
| nothing | 63 (ε .15) | 42 (ε .10) |
| `th_hermeticBus` | 33 (ε .08) | 21 (ε .05) |
| `th_extendedMLIWrapping` | 25 (ε .06) | 13 (ε .03) |
| `th_advancedMLI` | **21 (ε .05) — cap** | 8 (ε .02) |

Standard caps exactly where Deep-Space *starts* its MLI rungs, so Deep-Space stays 2.6× better at the top
and the axis still sells something real — but a LEO satellite now has counterplay. Resulting loads:

| | LEO eclipse | Mars | Jupiter |
|---|--:|--:|--:|
| Standard, no thermal tech | 150 W | 89 W | 163 W |
| Standard + `th_hermeticBus` | 78 W | 46 W | 85 W |
| Standard, capped | 50 W | 30 W | 54 W |
| Deep-Space, capped | 19 W | 11 W | 21 W |

**THERMAL MASS — MODELLED PROPERLY 2026-08-05, superseding the orbit-averaging version below.** Orbit
averaging worked but required a situation branch (averaged for orbiting craft, instantaneous for landed),
and two models with a discontinuity at touchdown was an artifact of having no temperature to remember.
With a real temperature state the branch is simply unnecessary — a craft on the Mun's night side and a
craft in a 35-minute LEO eclipse are the same physics at different timescales, and the only thing
separating them is how long the dark lasts against the craft's own τ.

```
T_env = T_set · (1 − deficit)^¼          equilibrium with NO heater
τ     = C / G,  C = vesselMass · c,  G = 4·ε·σ·A·T_set³
T    += (T_env − T) · (1 − e^(−dt/τ))    unconditionally stable at any dt
heater runs only once T would fall below T_min, then holds exactly that floor
```

**The deadband is what makes LEO free.** Heaters defend the *battery* — the tightest-toleranced thing
aboard and the real reason spacecraft carry heater tape — so `T_min` is 273 K, a floor, not the 293 K
setpoint. The bus drifts down to it for nothing and only pays watts below.

Simulated, five LEO orbits at 400 km then steady cruise:

| craft | τ | LEO avg heater | end T |
|---|--:|--:|--:|
| 500 kg, no thermal tech | 54 h | **0 W** | 287 K |
| 500 kg, + `th_hermeticBus` | 103 h | **0 W** | 290 K |
| 500 kg, capped | 162 h | **0 W** | 291 K |
| **50 kg**, + `th_hermeticBus` | 10 h | **4.7 W** | 273 K |

| cruise | deficit | heater |
|---|--:|--:|
| Mars, capped | 0.569 | 18 W |
| Jupiter, capped | 0.963 | 41 W |
| Jupiter, best MLI | 0.963 | 15 W |
| Neptune, capped | 0.999 | 43 W |

**Mass now matters, which was the point.** A 500 kg probe rides out every LEO eclipse on heat capacity
alone and never fires a heater — exactly as Explorer 1 did on paint stripes. A 50 kg one has τ ≈ 10 h
against a 1.5 h orbit, drops to the floor, and pays. Whole-*vessel* mass, because the bus is conductively
bolted to the craft and a probe strapped to a full tank really is buffered by it.

Background uses the identical `StepThermal` and writes `busTemperature` back into the module snapshot, so
an unloaded craft keeps evolving and cannot diverge from a loaded one.

*Aliasing at extreme warp is self-limiting:* sampling all-sunlit or all-shadow only matters when τ is short
relative to the orbit, and a short-τ craft is a light one whose absolute watts are small. Where the error
could be large in watts, τ is long and T barely moves.

---

*(Superseded, kept for the reasoning:)* **THERMAL MASS — via orbit averaging.** A spacecraft does not cool the instant it enters
shadow; it coasts through a ~35-minute eclipse on stored heat and reheats in sunlight. That is precisely
why passive-only designs worked — Explorer 1 rode out every eclipse of its life on paint stripes and heat
capacity, with no heater aboard. Charging a full steady-state load for the shadow half of every orbit
overstated LEO by ~3×.

So the solar term is now scaled by the **orbit-averaged sunlit fraction**, which is also how real thermal
engineers size heaters. Standard closed form for a circular orbit, **beta-angle aware** — no eclipse at all
once `|sin β| ≥ R/r`, else `shadowFraction = acos( √(r²−R²) / (r·cos β) ) / π`.

Beta-awareness is not decoration. It makes orbit choice a real thermal decision instead of a flat tax on
being in LEO, and it reproduces actual spaceflight behaviour:

| orbit | sunlit | deficit | no tech | + `th_hermeticBus` | capped |
|---|--:|--:|--:|--:|--:|
| LEO 400 km, β 0 (worst) | 0.610 | 0.274 | 46 W | 24 W | 15 W |
| LEO 400 km, β 45 | 0.659 | 0.225 | 38 W | 20 W | 13 W |
| LEO 400 km, **dawn-dusk β 75** | **1.000** | 0.000 | 0 W | 0 W | 0 W |
| GEO, β 0 (equinox) | 0.952 | 0.046 | 8 W | 4 W | 3 W |
| GEO, β 23 (solstice) | **1.000** | 0.000 | 0 W | 0 W | 0 W |

A dawn-dusk sun-synchronous orbit never eclipses — which is exactly why real missions fly them. And GEO
eclipses only near the equinoxes, because `asin(R/r) = 8.7°` there and β exceeds that for most of the year:
the model reproduces the real GEO eclipse season without being told about it.

*Approximation, stated plainly:* orbit averaging assumes the thermal time constant is long relative to the
orbital period. True for a dense, insulated avionics box; less true for a large deployed structure. Landed
and prelaunch craft have no orbit to average over, so they fall back to the instantaneous shadow test.

*Planner note:* Kerbalism's sunlight/shadow toggle is a **worst-case switch** (that is what it means for
solar panels), so the planner honours it as a hard 0/1 — "what if I sat in the dark". Flight uses the
orbit-averaged figure and therefore reads *between* the planner's two extremes.

**Named parts carry thermal too — CLOSED 2026-08-05.** `ModuleAxeFixedAvionics` had
`ProvidesAttitudeReference` but no heater load, so flying a named bus (Sputnik, a Voyager bus, an Agena,
an Apollo CM) dodged thermal entirely — the same class of hole the star tracker was careful to close. It
now resolves its own `k` through the *shared* `ModuleAxeAvionics.ResolveThermalK`, so the two model
families walk one MLI ladder and cannot drift.

`ModuleAxeThermal` is attached by a single blanket rule at the bottom of `AxeAvionicsCore.cfg`
(`@PART[*]:HAS[@MODULE[ModuleAxeFixedAvionics],!MODULE[ModuleAxeThermal]]:FINAL`) rather than emitted 38
times into `design/Parts/AxeFixedAvionics.cfg`, which is generated — one rule stays correct as parts come
and go. `:FINAL` so it lands after that file's own `:LAST[RP-AXE]` assignments *and* its `:FINAL` blanket
fallback, otherwise the parts caught by the fallback would be missed.

No double-billing: only the insulation coefficient comes from the avionics unit. Area is derived from
vessel dry mass, and `ModuleAxeThermal` enforces one heater owner per vessel, so a stack carrying both a
named unit and a procedural core is charged once.

**…on all three paths, as of 2026-08-18.** That claim was true of flight (`IsThermalOwner`) and background
(the lowest-`flightID` test) but NOT of the planner, which had no owner check at all. Kerbalism calls
`PlannerUpdate` on every enabled module on every part (`Planner.ResourceSimulator.Analyze` →
`Process_apiModule`), and once area became the whole vessel's, each core aboard reported the same
vessel-wide load — so the VAB "heaters" line read **N× what the craft actually flies**. Found on
Svetovit 1: five Deep-Space cores, 690 W shown against 138 W flown. `IsPlannerOwner` is the editor twin of
`IsThermalOwner`, resolving by position in `EditorLogic.fetch.ship.Parts` because there are no flight IDs
in the editor, and skipping parts the player has switched off via Kerbalism's `PlannerController` so that
excluding one core hands the load to the next rather than zeroing the line.

Third of its family, and the tell is the same each time: **a "heaters" figure that moves when it shouldn't,
or fails to match between the VAB and the flight scene.** The other two were the stale-thermal blocks
deleted from `ModuleAxeAvionics.PlannerUpdate` and `.BackgroundUpdate` on 2026-08-12 — that pass closed
avionics-vs-heaters and missed heaters-vs-heaters, because the owner check it assumed was doing the work
only ever existed on the flight paths. All three date to heaters moving into their own module on
2026-08-05 and are worth remembering as one shape: **when a per-vessel quantity is computed by a per-part
module, every code path that reports it needs its own ownership test — including the ones that only draw
UI.**

**Mass/cost: own per-tier ladder, authored as real data — not a live multiplier. SHIPPED.** Matching RP-1's
real shape meant ~10 *separate* tech-node placements in AXE's tree (mirroring each Guided-tier unlock
one-for-one, not a single gate riding whatever Guided tier happens to be active). RP-1's actual Deep-Space
ladder (ground-truthed against `RP-1/GameData/RP-1/Tree/ProceduralAvionics.cfg`) is its own literal per-tier
`massFactor`/`costFactor` table (**CORRECTED 2026-08-05: it IS exactly ×1.10 mass and ×1.50 cost on
Near-Earth's values, at every one of the ten rungs — 55.168/50.153 = 1.100, 85.26/56.84 = 1.500, and so on
to the last digit, in RP-1's own source numbers as well as AXE's copy. This sentence used to say it was
"NOT a clean ×1.10/×1.50 multiplier — that was an early approximation, corrected once the real numbers were
pulled"; the early approximation was right and the correction was the error. Authoring it as a literal
per-tier table is still the correct implementation — it survives RP-1 ever breaking the pattern — but
nobody should plan on the belief that the pattern isn't there**), `powerFactor` identical to NE at every
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

**Auto-hibernate on warp — SHIPPED** *(was "CONFIRMED, port RP-1's mechanism directly"; built since, this
paragraph described the pre-build state until 2026-08-05).* RP-1's base `ModuleAvionics.cs` hooks
`GameEvents.onVesselGoOnRails`/`onVesselGoOffRails`, calling `UpdateRate(onRails: true)`: while a vessel is
on rails (unloaded/timewarping), draw automatically drops to the reduced/idle rate — independent of the
player's manual Hibernate toggle state — and reverts to whatever the vessel's actual current state is the
moment it goes back off rails (loads/becomes active). **AXE now hooks the same two events**:
`GoOnRails`/`GoOffRails` → `RailChange` → `UpdateRate` in `ModuleAxeAvionics.cs`, with `_onRails` feeding
both `Asleep` and `ComputeWatts(onRails)` so the drop happens regardless of the manual toggle and reverts
off rails. `_onRails` deliberately does NOT feed `EffectiveCapacityTons` (RP-1's on-rails path also zeroes
`CurrentMassLimit`; capacity is a VAB-facing number and blinking it to zero on entering warp is noise —
nothing steers while unloaded). Stock probe hibernation stays disabled (`%hasHibernation = False`) so it
can't shadow the module's own toggle, except on radiation-hardened named parts (see `ApplyHibernation`).

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

**Multiplier ceiling — ADDED 2026-07-29.** The multiplier is clamped to `2981` (`penaltyMultiplierCap`, a
`KSPField`), which is `e^8` — *exactly* the `r=2` point. The curve therefore runs its full natural course out
to twice capacity and only stops climbing past that; everything below 2× over is untouched (1.1× → 2.2,
1.25× → 7.4, 1.5× → 54.6). The ceiling exists because the raw curve reaches `e^80 ≈ 5.5e34 W` by `r=11`,
which flattens any battery inside a single physics tick — that drops `ModuleCommand` and takes staging and
throttle with it, which is both harsher than the attitude lock this penalty was chosen over and
unrecoverable, since the battery is dead long before the overloading stage separates and `r` falls back under
1. At `e^8` the worst measured case (a 3 L battery) still lasts ~3 s: fatal, but commandable long enough to
stage. (The pre-existing clamp was on the *exponent*, at 80, which only fixed a literal `Infinity` readout
and left behaviour untouched.)

**The k=8 calibration above does not survive contact with the shipped EC economy — OPEN.** The ceiling was
first set to `54.6` on the strength of this section's own "50% over ≈ 89% of the original vessel's entire mass
just in battery" reference, then measured against real saved craft and found to be nowhere near it. RealFuels'
`ElectricCharge` tank holds **500 EC/L** (measured: a 41 L battery reports 20496 EC) and draw is
`watts/1000` EC/s, so a representative guided core — `Aether B`: 31.7 t capacity, 146 W, 41 L battery —
carries **~39 hours** of normal operation. An ascent is 6-10 minutes. At a 54.6 ceiling that core survives 43
minutes of maximum overload, i.e. sails through ascent with 4× margin and never notices. Killing it inside a
6-minute window needs >390; inside 10 minutes, >234. The reference burn this section was calibrated against is
out by orders of magnitude against real battery sizing, which means **the whole curve is plausibly
under-tuned, not just its ceiling** — `k` itself wants re-deriving against measured craft. Not done here; the
ceiling was raised to `e^8` to make gross overload actually fatal in the ascent window, and `k` left alone.

Note `r` is whole-vessel **wet** mass while `ec_draw_normal` is built from **dry** mass — deliberate, but
worth remembering when reading the two numbers side by side.

**UI**: show the penalty portion distinctly, not just a combined total — as a percentage over normal draw
(`(e^(8(r−1))−1) × 100%`), so a player can see at a glance how much of their current draw is "penalty" versus
baseline.

## Shutdown parity with RP-1 — ADDED 2026-07-29

The toggle AXE shipped as **Hibernate** is RP-1's **Shutdown Avionics** (`ModuleAvionics.systemEnabled`), not
stock probe hibernation — RP-1 blanket-disables that on every `ModuleCommand` (`Avionics.cfg:1`) and so does
AXE. The tier gate was ported faithfully (`GetToggleable() => disabledPowerFactor > 0`: Unshielded from index
9 only at `0.1`, Shielded every tier at `0.05`, Science-Core never), but three things did not come across, and
together they made the feature unusable for the case it exists to serve.

**The disabled draw carried the overload penalty.** RP-1's `GetDisabledkW()` is `GetEnabledkW() ×
disabledPowerFactor`, and RP-1's enabled kW has no overload term at all — RP-1 locks attitude instead of
taxing power. AXE built the sleeping rate from `ComputeBaseWatts()`, which folds the penalty in. Combined with
the (correct, RP-1-matching) rule that a shut-down core leaves `EffectiveCapacityTons`, a vessel whose *only*
guided core went to sleep saw capacity fall to 0 → `r → +∞` → the advertised "5% depth" was 5% of `e^80`. So
shutting an overloaded core down never saved it, and shutdown could not function as an escape from overload —
which is precisely what a staged vehicle needs it for. Sleeping draw is now built from `TierWatts()`, and
`PenaltyMultiplier()` returns 1 outright while asleep.

**It was flight-only.** RP-1 sets `guiActive` and `guiActiveEditor` alike from `GetToggleable()`. An upper
stage's avionics can now be *built* shut down rather than only switched off after launch.

**Only one action existed.** RP-1 pairs the toggle with one-way Shutdown and Activate actions so a state
change can be dropped into a staging sequence without depending on the current state. All three now exist.

**Also ported: `OnSave` writes the on-rails draw** ("too many ways to exit a scene" — RP-1
`ModuleAvionics.cs:260`). Kerbalism's `BackgroundUpdate` reads `currentWatts` straight out of the module
snapshot for an unloaded vessel, so persisting the live active figure billed a parked craft the penalised rate
for the entire time it sat unloaded.

**Deliberately not ported:** the crew veto on *Shutdown* ("Cannot shut down avionics while crewed") — the
procedural core is never crewed.

**`dead` / "Disable Avionics permanently" — PORTED 2026-08-05** (was listed here as "no current need").
A separate one-way action on both avionics modules, with RP-1's antenna-kill cascade
(`KillAntennasIfLastAvionicsDead`) intact: shared implementation in `Source/AXE/Avionics/AxeAvionicsKill.cs`,
`KillEvent`/`KillAction`/`dead`/`canPermaDisable` on `ModuleAxeAvionics` and `ModuleAxeFixedAvionics`.
A killed unit draws 0 W, disables its `ModuleCommand`, leaves the steerable-mass MAX, loses its Hibernate
and Engage controls, and re-applies all of that on load (`dead` is persistent). If it was the vessel's last
live avionics, every RealAntennas antenna on board is permanently shut down with it — without that clause
Kerbalism-side comms leave the "dead" probe still controllable, which is RP-1's own stated reason for it.
RealAntennas is reached by reflection (not an AXE assembly reference) and logs at error level if either
bound member ever stops resolving, so the clause can never silently become a no-op.

**One deliberate deviation:** the kill is blocked while the part is crewed. RP-1 guards the *reversible*
Shutdown against crew but leaves the irreversible kill unguarded, so an action group can brick a crewed
capsule's command with no way back. That matters for `ModuleAxeFixedAvionics`, which rides real crewed
capsules.

**Player-facing naming follows RP-1** — the PAW reads *Shutdown Avionics* / *Activate Avionics*, because the
unit leaving the steerable-mass budget is the point and "hibernate" does not convey it. Internal names
(`hibernating`, `CanHibernate`, `ToggleHibernation`) are unchanged for save compatibility.

**What this does not fix.** Shutdown is gated at index 9, so it is not available to an early-career craft —
matching RP-1, which does not need it there because RP-1 locks rather than penalises. An overloaded early-tier
core still pays the (now capped) penalty with no way to switch itself off.

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

---

## PAW mass readouts (2026-07-29)

The PAW's `Avionics Mass` only ever reported the **hardware segment** (`hwVolume × density`, i.e. this
module's own `IPartMassModifier` contribution) — reading it as "what the box weighs" understates a
battery-heavy core by more than the hardware itself weighs. Renamed to **Hardware Mass** and joined by two
more fields in the same group:

- **Battery Mass** — RealFuels' own `ModuleFuelTanks.mass`, read by reflection off the existing RF bridge.
  For the `Battery-I` tank type that's `0.00007 t/L` tankage base + `0.0045 t/L` of cells, over the battery
  volume this module pushes into RF. Pure readout: RF reports this mass to KSP itself, **non-additively**
  (`GetModuleMass` returns `mass - defaultMass`, replacing the part's 1 t prefab mass rather than adding to
  it), so folding it into this module's `IPartMassModifier` would double-count it.
- **Total Mass** — measured through KSP's own path (`part.mass + part.GetModuleMass(part.mass) +
  part.GetResourceMass()`), *not* summed from the two above. Hardware + battery don't quite reach it:
  Kerbalism's `HardDrive` (data/sample capacity mass) and any `ProceduralPart` hollow-volume mass ride
  along too. Measuring is what keeps the readout equal to the mass KSP actually flies.

All three refresh from `UpdateRate()`, which every editor path already reaches *after*
`PushBatteryToTank()` has re-run RF's `CalculateMass()` — so the battery figure tracks the drag live rather
than lagging a frame.

The allocation bar's label was **trimmed** at the same time, to the volume split alone
(`X L batt | Y L hw | Z L empty`). It had been carrying capacity and the overload penalty, and briefly the
mass split too — all of which are their own PAW fields a few rows above the bar. The label is one line in a
narrow window; anything already displayed as a field costs more in wrapping than it buys in convenience.
