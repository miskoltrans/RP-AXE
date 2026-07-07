# RP-AXE vs RP-1 — Avionics Comparison & Grounding (2026-06-27, updated 2026-07-08)

Grounds RP-AXE's avionics core against RP-1's procedural avionics. **RP-AXE adopts RP-1's formulas directly**,
so the old divergences (flat un-scaling mass; the tier freeze at ~1960) are resolved. A VAB-only toggle picks
the **model**: **guided = Near-Earth** (RP-1's vessel-scaled, full-control curve) or **unguided = Science-Core**
(RP-1's light flat-mass sequencer). Deep-Space is intentionally dropped (range is handled by comms, not
avionics). Script: `tools/avionics_compare.py` (parses the shipped `TIER` ladder from `AxeAvionicsCore.cfg`;
re-run after editing it to refresh the tables below).

**2026-07-07 update**: closed the three gaps item 7 (below) used to call "planned" — **hardware cost**
(`GetModuleCost`, RP-1's hump-shaped curve), **science-container tier gating** (on from `basicAvionics`,
matching RP-1), and a **kOS per-tier scaling bridge** (reflected onto a `kOSProcessor` module if present —
inert today since kOS isn't an AXE dependency, but no longer silently frozen at a flat value the way the old
RP-1 kOS patch would leave it once `ModuleProceduralAvionics` is stripped). See sections H/I and the
"what still differs" list below.

**2026-07-08 update**: closed a fourth gap the 07-07 pass had only documented — AXE's Science-Core ladder
now has RP-1's real `start` floor rung (48 kg/100 W/density 3.35), one step below `postWarAvionics`. See
the note under §G.

## Headline — two RP-1 models on one toggle, draw keyed off live dry mass

RP-AXE's `ModuleAxeAvionics` evaluates RP-1's polynomials with the per-tier factors taken straight from RP-1's
ladders. The guided/unguided toggle selects the as-built model (frozen at launch). Avionics mass = a hardware
curve + the battery you size.

| | **RP-1 proc avionics** | **RP-AXE core** |
|---|---|---|
| Models | Near-Earth / Deep-Space / Science-Core (separate configs) | **Near-Earth (guided) / Science-Core (unguided)**, one VAB toggle |
| Mass input (NE) | **rated** `controllableMass` (slider, ≥ vessel) | **live vessel load** (auto, ≈ vessel mass), frozen at launch |
| Hardware mass (NE) | `(M^0.46172 + 0.96)·massFactor/1000` | **same formula** |
| Draw input | rated `controllableMass`, **static** | **live DRY mass** — steady on burn, steps down on staging |
| Control cliff | hard — vessel > massLimit ⇒ **no control** | **none** — bigger just costs more |
| Low-power | Deep-Space hibernation only | **Hibernate toggle on every core** (draw → 5%) |
| Battery | leftover part volume after hardware | **same** — hardware reserves vol, rest is EC |
| Cost | `(M^0.46172+3.034)·costFactor`, hump-shaped | **same formula**, frozen at launch like mass (§H) |
| Science container | on from `basicAvionics` (both models) | **same** — checked off at flight start if tier lacks it |
| kOS | per-tier `kosDiskSpace`/etc via `ModuleProceduralAvionics` | reflected onto `kOSProcessor` if present (§I) — inert, kOS isn't an AXE dep |
| Tiers | 13 tech-gated (powerFactor 56.4 → 7.8) | **same 13**, 1:1 by tech node, + a `start` floor rung below them |
| SAS | level 3 from TL0 | level 3 once guidance is active |

The result lands on RP-1's numbers at every craft size, and what differs is all **easier**: AXE keys hardware
off the *actual* load (RP-1 players rate `controllableMass` with margin), the draw is *live* off **dry mass**
vs RP-1's static, mass *freezes at launch* (RP-1-like), guidance is gated at `postWarAvionics` (vs RP-1's
`start`), and SAS is a flat 3.

## The formulas (exact)

RP-1 `GetPolynomial(v,e,c,f) = (v^e + c)·f` — from `ModuleProceduralAvionics.cs`:
- hardware **mass** (t) = `(M^0.46172 + 0.96)·massFactor / 1000`  (M = `controllableMass`)
- hardware **cost** (funds) = `(M^0.46172 + 3.034)·costFactor`  — same `M`, **no** `/1000` (§H)
- **EC draw** (kW) = `(M^0.57853 + 1.035)·powerFactor / 1000`
- Science-Core: `controllableMass = 0` ⇒ flat **mass** = `scMassFactor/1000` t, flat **draw** = `scPowerFactor/1000`
  kW, flat **cost** = `costFactor` funds (default zero exponent/constant collapse the polynomial to the factor)
- hardware **volume** = mass / `avionicsDensity`; leftover part volume → EC battery
- `hasScienceContainer` gates `ModuleScienceContainer` on from `basicAvionics` (both configs)
- `kosDiskSpace`/`kosSpaceCostFactor`/`kosSpaceMassFactor`/`kosECPerInstruction` per tier scale a `kOSProcessor`
  module's disk space / EC-per-instruction / cost / mass, read off `CurrentProceduralAvionicsTechNode`

RP-AXE — from `ModuleAxeAvionics.cs` (the guided/unguided toggle picks the model, frozen at launch):
- **Near-Earth (guided)**: mass (t) = `(load^0.46172 + 0.96)·massFactor / 1000`, cost (funds) =
  `(load^0.46172 + 3.034)·costFactor` (same `load`, no `/1000`), `load` ≈ vessel mass; full control
- **Science-Core (unguided)**: mass (t) = `scMassFactor / 1000`, cost (funds) = `scCostFactor` flat — **size-
  independent**; no steering (axial-thrust only from `improvedAvionics` up)
- **EC draw** (W) = `(dryMass^0.57853 + 1.035)·powerFactor` for NE (live), or flat `scPowerFactor` for SC;
  ×0.1 when a NE core is dumb, ×0.05 when **hibernating** (either model)
- hardware **volume** = mass / density (NE 0.5; SC per-tier); the part auto-grows to fit, leftover → **RealFuels
  EC battery** you size
- guidance gated at `postWarAvionics`; runs **dumb** if the battery goes flat in flight or the core is hibernated
- `ModuleScienceContainer` (seed-added, static) is stripped at flight start if the as-built tier's
  `hasScienceContainer` is false — same node/gate as RP-1, checked once like RP-1's own `Start()` logic
- a `kOSProcessor` module, if present, is kept in sync with the tier's `kos*` ladder via reflection (duck-typed,
  same pattern as the RealFuels bridge) — currently a no-op since kOS isn't an AXE dependency

## A) Tier ladder — AXE tech node → (massFactor, powerFactor), matched 1:1 to RP-1 Near-Earth

| AXE tech (`TIER` node) | massFactor | powerFactor | RP-1 Near-Earth tier (era) |
|---|--:|--:|---|
| start (unconditional floor) | 87.99 | 56.415 | start/postWar (1945-51) |
| postWarAvionics | 87.99 | 56.415 | start/postWar (1945-51) |
| avionicsPrototypes | 69.712 | 47.851 | avionicsPrototypes (1952-55) |
| earlyAvionics | 59.13 | 40.587 | earlyAvionics (1956-58) |
| basicAvionics | 50.153 | 34.426 | basicAvionics (1959-60) |
| interplanetaryProbes | 42.54 | 29.2 | interplanetaryProbes (1961) |
| improvedAvionics | 36.082 | 24.767 | improvedAvionics (1962-63) |
| matureAvionics | 30.605 | 21.007 | matureAvionics (1964-66) |
| largeScaleAvionics | 25.959 | 17.818 | largeScaleAvionics (1967-71) |
| advancedAvionics | 22.018 | 15.113 | advancedAvionics (1972-80) |
| nextGenAvionics | 18.675 | 12.819 | nextGenAvionics (1981-87) |
| longTermAvionics | 15.84 | 10.873 | longTermAvionics (1988-93) |
| internationalAvionics | 13.436 | 9.222 | internationalAvionics (1994-99) |
| modernAvionics | 11.396 | 7.822 | modernAvionics (2000s) |

`start` and `postWarAvionics` tie on Near-Earth numbers (RP-1 has no NE rung below `start`) — the split only
matters for Science-Core (§G), where `start` carries RP-1's own heavier starting values.

The ladder lives in `AxeAvionicsCore.cfg` as `TIER` nodes — the single source of truth this script parses.

## B) Hardware MASS (kg) vs per-craft load — AXE == RP-1 at equal load

| tier | 1 t | 3 t | 10 t | 30 t | 100 t | 300 t | 1000 t |
|---|--:|--:|--:|--:|--:|--:|--:|
| postWarAvionics | 172 | 231 | 339 | 508 | 822 | 1310 | 2220 |
| basicAvionics | 98 | 131 | 193 | 289 | 469 | 746 | 1266 |
| advancedAvionics | 43 | 58 | 85 | 127 | 206 | 328 | 556 |
| modernAvionics | 22 | 30 | 44 | 66 | 106 | 170 | 288 |

AXE is fed the **actual** vessel load and freezes it; RP-1 uses rated `controllableMass ≥ load` (with
margin), and AXE's live draw drops as stages separate ⇒ AXE ≤ RP-1 in play.

## C) EC DRAW (W) vs DRY mass — AXE == RP-1 per tier, live (steady on burn, steps on staging)

| tier | 1 t | 3 t | 10 t | 30 t | 100 t | 300 t | 1000 t |
|---|--:|--:|--:|--:|--:|--:|--:|
| postWarAvionics | 115 | 165 | 272 | 462 | 868 | 1588 | 3127 |
| basicAvionics | 70 | 101 | 166 | 282 | 530 | 969 | 1908 |
| advancedAvionics | 31 | 44 | 73 | 124 | 233 | 425 | 838 |
| modernAvionics | 16 | 23 | 38 | 64 | 120 | 220 | 434 |

## D) Grounded — V-2 (RP-1 craft: Near-Earth, `controllableMass = 15 t`, start)

| | RP-1 (rated 15 t) | RP-AXE (live load ~12.5 t) |
|---|---|---|
| hardware mass | **392 kg** | **367 kg** |
| EC draw | 329 W | 302 W (live, falls further as it burns) |
| hardware footprint | 783 L | 734 L (+ the battery you size) |
| + battery, 5 min powered | bundled | 0.41 kg (90 EC, Battery-I) |
| + battery, 3 h continuous | bundled | 14.7 kg (3257 EC) |

The ~390 kg is almost all **hardware** — the battery is negligible for a short flight, which is why the
mass has to be a hardware curve, not an endurance battery. AXE lands ~25 kg under RP-1 (actual vs rated load).

## E) VOLUME — hardware reserves (mass / 0.5) m³ of the part; the rest is EC battery (liters)

| tier | 1 t | 3 t | 10 t | 30 t | 100 t | 300 t | 1000 t |
|---|--:|--:|--:|--:|--:|--:|--:|
| postWarAvionics | 345 | 461 | 678 | 1015 | 1644 | 2619 | 4441 |
| basicAvionics | 197 | 263 | 387 | 579 | 937 | 1493 | 2531 |
| advancedAvionics | 86 | 115 | 170 | 254 | 411 | 655 | 1111 |
| modernAvionics | 45 | 60 | 88 | 131 | 213 | 339 | 575 |

The part auto-grows to at least this footprint (RP-1-style); the player sizes it up further for battery EC.

## F) Battery = the RP-AXE marginal cost. Chemistries (RO `electronics` line)

EC per kg: **Battery-I 222 · II 346 · III 556 · IV 694**.

| chemistry | kg/1000 EC | funds/1000 EC | maxUtil | unlock |
|---|--:|--:|--:|---|
| Battery-I | 4.5 | 12 | 0.50 | start |
| Battery-II | 2.89 | 8 | 0.50 | electronicsHuman ~1961 |
| Battery-III | 1.8 | 5 | 0.60 | electronicsAdvCapsules ~1964 |
| Battery-IV | 1.44 | 4 | 0.75 | electronicsLunar ~1967 |

## G) Science-Core (unguided model) — flat per tier, size-independent (RP-1 Science-Core)

The unguided half of the VAB toggle. Mass and draw are **flat per tech tier** (no vessel scaling); no steering,
but axial-thrust spin-stabilization is allowed from `improvedAvionics` up. For sounding rockets and kick stages.

| AXE tech (`TIER` node) | mass (kg) | draw (W) | density | axial |
|---|--:|--:|--:|:--:|
| start (unconditional floor) | 48 | 100 | 3.35 | no |
| postWarAvionics | 33 | 50 | 2.4 | no |
| avionicsPrototypes | 17 | 25 | 1.4 | no |
| earlyAvionics | 4 | 0.15 | 0.5 | no |
| basicAvionics | 1.5 | 0.10 | 0.5 | no |
| interplanetaryProbes | 1 | 0.09 | 0.5 | no |
| improvedAvionics | 0.81 | 0.081 | 0.5 | **yes** |
| matureAvionics | 0.73 | 0.073 | 0.5 | yes |
| largeScaleAvionics | 0.66 | 0.066 | 0.5 | yes |
| advancedAvionics | 0.59 | 0.059 | 0.5 | yes |
| nextGenAvionics | 0.53 | 0.053 | 0.5 | yes |
| longTermAvionics | 0.48 | 0.048 | 0.5 | yes |
| internationalAvionics | 0.43 | 0.043 | 0.5 | yes |
| modernAvionics | 0.39 | 0.039 | 0.5 | yes |

vs Near-Earth at the same node (e.g. `basicAvionics`): **1.5 kg / 0.1 W** unguided vs **193 kg / 166 W** for 10 t
of guided control — a featherweight, near-zero-power sequencer that simply can't steer.

**Closed 2026-07-08.** RP-1's own Science-Core ladder had one rung AXE was missing: a `start` tech level
(48 kg / 100 W / density 3.35) *below* `postWarAvionics`. AXE now carries a matching `start` `TIER` node —
the unconditional floor (no research gate, `ApplyTier` always begins there) — with RP-1's real starting
Science-Core numbers; `postWarAvionics` only takes over once that tech is actually researched. Near-Earth is
unaffected (RP-1 has no NE rung below `start`, so `start`'s NE numbers are identical to `postWarAvionics`'s —
`ApplyTier`'s tie-break was changed from `<` to `<=` so research can still step off an NE-tied floor). Before
this fix AXE's earliest Science-Core was lighter/lower-draw than RP-1's actual starting one, from turn 0 of
career — see `tools/avionics_compare.py` §G for the corrected ladder.

## H) Hardware COST (funds) — RP-1's hump, not monotonic; peaks `matureAvionics`

`GetModuleCost`/`IPartCostModifier`, same load basis + freeze-at-launch as mass. Distinct signal from the
monotonic mass/power curves: early sophistication costs *more* before mass production brings it back down.

| AXE tech (`TIER` node) | NE @10t | NE @100t | SC (flat) |
|---|--:|--:|--:|
| start (unconditional floor) | 285 | 549 | 3.0 |
| postWarAvionics | 285 | 549 | 6.0 |
| avionicsPrototypes | 306 | 589 | 8.0 |
| earlyAvionics | 321 | 618 | 10.0 |
| basicAvionics | 337 | 649 | 12.0 |
| interplanetaryProbes | 354 | 681 | 12.0 |
| improvedAvionics | 372 | 716 | 12.0 |
| matureAvionics | **390** | **751** | 12.0 (peak) |
| largeScaleAvionics | 349 | 672 | 10.0 |
| advancedAvionics | 279 | 538 | 9.0 |
| nextGenAvionics | 223 | 430 | 8.1 |
| longTermAvionics | 179 | 344 | 7.3 |
| internationalAvionics | 143 | 275 | 6.6 |
| modernAvionics | 114 | 220 | 5.9 |

## I) Science container gating + kOS per-tier scaling

`ModuleScienceContainer` is checked off at flight start if the as-built tier's `hasScienceContainer` is false
(same node RP-1 gates it at, `basicAvionics`, both models) — matches RP-1's own `Start()`-only gating (the
editor always shows the module present; only flight strips it). A `kOSProcessor` module, if present on the
part, has its `diskSpace`/`baseDiskSpace`/`diskSpaceCostFactor`/`diskSpaceMassFactor`/`ECPerInstruction`
fields kept in sync with the tier via reflection (duck-typed, same pattern as the RealFuels bridge) — **inert
today**, since kOS isn't an AXE dependency, but no longer the flat non-scaling disk space the seed's old
`:NEEDS[kOS]` patch would silently leave once `ModuleProceduralAvionics` (which drove RP-1's own kOS scaling)
is stripped.

| AXE tech (`TIER` node) | science container | kOS disk space |
|---|:--:|--:|
| start (unconditional floor) | no | 500 B |
| postWarAvionics | no | 500 B |
| avionicsPrototypes | no | 500 B |
| earlyAvionics | no | 500 B |
| basicAvionics | **yes** | 500 B |
| interplanetaryProbes | yes | 5,120 B |
| improvedAvionics | yes | 10,240 B |
| matureAvionics | yes | 20,480 B |
| largeScaleAvionics | yes | 51,200 B |
| advancedAvionics | yes | 102,400 B |
| nextGenAvionics | yes | 204,800 B |
| longTermAvionics | yes | 307,200 B |
| internationalAvionics | yes | 409,600 B |
| modernAvionics | yes | 512,000 B |

## What still differs (all intended, all easier)

1. **Two models on the guided/unguided toggle.** Guided = Near-Earth, unguided = Science-Core (RP-1's third
   config, Deep-Space, is dropped — range is comms, not avionics). Chosen in the VAB, frozen at launch.
2. **Hardware keys off actual load, not rated mass** (NE). RP-1 players set `controllableMass ≥ vessel` (margin);
   AXE uses the real load ⇒ a touch lighter.
3. **Draw is live off DRY mass.** Steady as fuel burns, steps down as stages drop; RP-1's is static at the rated
   value. (Mass itself still freezes at launch — RP-1-like.)
4. **Hibernation on every core** (flight Hibernate toggle, draw → 5%, control suspended) — RP-1 gates hibernation
   to Deep-Space only.
5. **Guidance gate** at `postWarAvionics` vs RP-1's `start` — so the very start flies Science-Core only.
6. **SAS** is a flat level 3 (config), suppressed while dumb/axial by `AxeAvionicsController`.
7. **Funds, science storage, kOS — closed 2026-07-07.** Cost now has a real hardware-efficiency curve
   (§H, `GetModuleCost`), science storage is tier-gated like RP-1 (§I), and a kOS reflection bridge exists
   (§I, inert until kOS is an AXE dependency). See `docs/UPGRADES.md` §C1.
8. **No manual "disable for power" toggle.** RP-1 lets the player switch Near-Earth avionics fully off from
   `advancedAvionics` on (`disabledPowerFactor`, a deliberate power/control trade). AXE's idle multiplier
   (`idleFactor`, 0.1×) is automatic — it applies whenever guidance isn't active (unresearched/unpowered), at
   every tier, not a player-chosen toggle. Different mechanic, not a gap: AXE's Hibernate (§ above) already
   covers the "trade control for power" use case, uniformly, from the start.

## Planned — not yet built

**Decouple battery volume from box volume.** Today `ApplyVolumeReservation` sends *all* leftover volume
(box volume − hardware volume) to RealFuels as tank capacity, unconditionally — a bigger box always means
proportionally more EC, with no way to build a bigger box without also getting more battery than you want
(e.g. to match a stack diameter, or to leave headroom to grow EC later without a rebuild). Neither RP-1 nor
current AXE support this — RP-1's `SendRemainingVolume()`/`GetAvailableVolume()` has the identical
unconditional-leftover behavior. Shape sketched 2026-07-08: a second AXE-owned fraction (how much of `avail`
actually gets sent onward to RealFuels; the rest stays dead volume in the box) — needs design first, not
started.

## Where the numbers live
- RP-1 coeffs: `RP-1/GameData/RP-1/Tree/ProceduralAvionics.cfg` (`AVIONICSCONFIGS`: Near-Earth …)
- RP-1 formulas: `RP-1/Source/RP0/Avionics/ModuleProceduralAvionics.cs` (`GetPolynomial`, `GetAvionicsMass`,
  `GetAvionicsCost`, `SetScienceContainer`)
- RP-AXE model: `Source/AXE/Avionics/ModuleAxeAvionics.cs`
- RP-AXE ladder (source of truth): `GameData/RP-AXE/design/Tree/AxeAvionicsCore.cfg` (`TIER` nodes)
- Battery tanks: `Instance/GameData/RealismOverhaul/RO_RealFuels.cfg` (`Battery-I..IV`)
- kOS field reference (not vendored — kOS isn't an AXE dependency): `kOSProcessor` fields `diskSpace` /
  `baseDiskSpace` (int) / `diskSpaceCostFactor` / `diskSpaceMassFactor` / `ECPerInstruction` (float), per
  https://ksp-kos.github.io/KOS/general/kospartmodule.html

Related: [[rp-axe-avionics-core]] memory.
