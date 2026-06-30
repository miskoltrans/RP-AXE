# RP-AXE vs RP-1 — Avionics Comparison & Grounding (2026-06-27)

Grounds RP-AXE's avionics core against RP-1's procedural avionics. **RP-AXE adopts RP-1's formulas directly**,
so the old divergences (flat un-scaling mass; the tier freeze at ~1960) are resolved. A VAB-only toggle picks
the **model**: **guided = Near-Earth** (RP-1's vessel-scaled, full-control curve) or **unguided = Science-Core**
(RP-1's light flat-mass sequencer). Deep-Space is intentionally dropped (range is handled by comms, not
avionics). Script: `tools/avionics_compare.py` (parses the shipped `TIER` ladder from `AxeAvionicsCore.cfg`;
re-run after editing it to refresh the tables below).

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
| Tiers | 13 (powerFactor 56.4 → 7.8) | **same 13**, 1:1 by tech node |
| SAS | level 3 from TL0 | level 3 once guidance is active |

The result lands on RP-1's numbers at every craft size, and what differs is all **easier**: AXE keys hardware
off the *actual* load (RP-1 players rate `controllableMass` with margin), the draw is *live* off **dry mass**
vs RP-1's static, mass *freezes at launch* (RP-1-like), guidance is gated at `postWarAvionics` (vs RP-1's
`start`), and SAS is a flat 3.

## The formulas (exact)

RP-1 `GetPolynomial(v,e,c,f) = (v^e + c)·f` — from `ModuleProceduralAvionics.cs`:
- hardware **mass** (t) = `(M^0.46172 + 0.96)·massFactor / 1000`  (M = `controllableMass`)
- **EC draw** (kW) = `(M^0.57853 + 1.035)·powerFactor / 1000`
- Science-Core: `controllableMass = 0` ⇒ flat **mass** = `scMassFactor/1000` t, flat **draw** = `scPowerFactor/1000` kW
- hardware **volume** = mass / `avionicsDensity`; leftover part volume → EC battery

RP-AXE — from `ModuleAxeAvionics.cs` (the guided/unguided toggle picks the model, frozen at launch):
- **Near-Earth (guided)**: mass (t) = `(load^0.46172 + 0.96)·massFactor / 1000`, `load` ≈ vessel mass; full control
- **Science-Core (unguided)**: mass (t) = `scMassFactor / 1000`, **flat per tier** (size-independent); no steering
  (axial-thrust only from `improvedAvionics` up)
- **EC draw** (W) = `(dryMass^0.57853 + 1.035)·powerFactor` for NE (live), or flat `scPowerFactor` for SC;
  ×0.1 when a NE core is dumb, ×0.05 when **hibernating** (either model)
- hardware **volume** = mass / density (NE 0.5; SC per-tier); the part auto-grows to fit, leftover → **RealFuels
  EC battery** you size
- guidance gated at `postWarAvionics`; runs **dumb** if the battery goes flat in flight or the core is hibernated

## A) Tier ladder — AXE tech node → (massFactor, powerFactor), matched 1:1 to RP-1 Near-Earth

| AXE tech (`TIER` node) | massFactor | powerFactor | RP-1 Near-Earth tier (era) |
|---|--:|--:|---|
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
7. **Funds**: control is currently free (only the battery costs) — but a **hardware-cost /
   efficiency-optimization dimension is planned** (revises the old "out of scope" stance). RP-1's
   avionics cost curve is the reference: `cost = (load^0.46172 + 3.034)·costFactor`, a *hump*
   (`costFactor` 48→66 peak ~1964-66→19 modern) so cost captures hardware-efficiency optimization
   across the tree, distinct from the monotonic mass/power gains. To build: add
   `costExponent`/`costConstant`/`costFactor` to the `TIER` nodes + `GetModuleCost` in
   `ModuleAxeAvionics`. See `docs/UPGRADES.md` §C1.

## Where the numbers live
- RP-1 coeffs: `RP-1/GameData/RP-1/Tree/ProceduralAvionics.cfg` (`AVIONICSCONFIGS`: Near-Earth …)
- RP-1 formulas: `RP-1/Source/RP0/Avionics/ModuleProceduralAvionics.cs` (`GetPolynomial`, `GetAvionicsMass`)
- RP-AXE model: `Source/AXE/Avionics/ModuleAxeAvionics.cs`
- RP-AXE ladder (source of truth): `GameData/RP-AXE/design/Tree/AxeAvionicsCore.cfg` (`TIER` nodes)
- Battery tanks: `Instance/GameData/RealismOverhaul/RO_RealFuels.cfg` (`Battery-I..IV`)

Related: [[rp-axe-avionics-core]] memory.
