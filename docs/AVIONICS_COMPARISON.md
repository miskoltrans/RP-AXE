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

**2026-07-08 update (2), user direction — hibernation restricted, custom power-brownout removed.**
Hibernate is now **Guided (Near-Earth) only** — Unguided (Science-Core) can never hibernate, matching RP-1's
own behavior more closely (RP-1 never gives Science-Core a toggle at any tier; AXE just doesn't additionally
tier-gate Near-Earth's the way RP-1 does from `advancedAvionics` on). And AXE's custom `_powered`/reserve-
seconds hysteresis check (`UpdatePowered`, `poweredCutoffSeconds`/`poweredRecoverSeconds`) is **gone
entirely** — the live draw is now fed straight into stock `ModuleCommand`'s own EC input resource every
update, so an empty battery loses control via KSP's own control-source logic, exactly like RP-1 (confirmed
by reading `RP-1/Source/RP0/Avionics/ModuleAvionics.cs`: it has no dedicated brownout check either, it just
writes its wattage into `ModuleCommand`'s resource rate and lets stock handle the rest). See the updated
"what still differs" list, items 4 and 8.

## Headline — two RP-1 models on one toggle, draw keyed off live dry mass

RP-AXE's `ModuleAxeAvionics` evaluates RP-1's polynomials with the per-tier factors taken straight from RP-1's
ladders. The guided/unguided toggle selects the as-built model (frozen at launch). Avionics mass = a hardware
curve + the battery you size.

| | **RP-1 proc avionics** | **RP-AXE core** |
|---|---|---|
| Models | Near-Earth / Deep-Space / Science-Core (one 3-way dropdown) | **all three, on TWO orthogonal VAB toggles**: Guided/Unguided (= NE / Science-Core) × Standard/Deep-Space Bus (Guided-only) |
| Mass input (NE) | **rated** `controllableMass` (slider, ≥ vessel) | **live vessel load** (auto, ≈ vessel mass), frozen at launch |
| Hardware mass (NE) | `(M^0.46172 + 0.96)·massFactor/1000` | **same formula** |
| Draw input | rated `controllableMass`, **static** | **live DRY mass** — steady on burn, steps down on staging |
| Control cliff | hard — vessel > massLimit ⇒ **no control** | **none** — bigger just costs more |
| Out of power | no custom check — feeds `ModuleCommand`'s EC rate, stock handles it | **same** — no custom check either (see below) |
| Low-power | Deep-Space always; Near-Earth from `advancedAvionics`; Science-Core never | **same** — Deep-Space Bus 0.05 from its first rung, Standard can't until idx 9 then 0.1, Unguided never |
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
  ×0.1 when a NE core is dumb, ×0.05 when **hibernating** (**Guided/Near-Earth only** — Unguided can never
  hibernate; `ToggleHibernation` no-ops and the PAW event/action are hidden when `!guidanceEnabled`)
- hardware **volume** = mass / density (NE 0.5; SC per-tier); the part auto-grows to fit, leftover → **RealFuels
  EC battery** you size
- guidance gated at `postWarAvionics`; runs **dumb** if the tech isn't researched or the core is hibernated.
  Running the battery flat is **not tracked by AXE at all** — the live draw is fed straight into stock
  `ModuleCommand`'s own EC input resource every update (zeroed instead if Kerbalism is present, to avoid
  double-counting), so an empty battery loses control via KSP's own control-source logic, same as RP-1
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

1. **RP-1's 3-way dropdown becomes two orthogonal toggles.** Guided = Near-Earth, Unguided = Science-Core;
   a second Guided-only toggle picks Standard vs **Deep-Space Bus** (RP-1's third config). Both chosen in
   the VAB, frozen at launch. What AXE actually dropped is not the model but RP-1's `interplanetary`
   *range lock* — range is comms (RealAntennas), not avionics. (Updated 2026-08-05: this item used to say
   "Deep-Space is dropped", which stopped being true when the axis shipped 2026-07-10 and was renamed
   Deep-Space Bus 2026-08-05.)
2. **Hardware keys off actual load, not rated mass** (NE). RP-1 players set `controllableMass ≥ vessel` (margin);
   AXE uses the real load ⇒ a touch lighter.
3. **Draw is live off DRY mass.** Steady as fuel burns, steps down as stages drop; RP-1's is static at the rated
   value. (Mass itself still freezes at launch — RP-1-like.)
4. **~~Hibernation is Guided-only, not tier-gated.~~ CLOSED 2026-07-10 — AXE now matches RP-1 exactly.**
   Deep-Space Bus hibernates to 0.05 from its first rung; Standard cannot hibernate at all until ladder
   index 9 (`advancedAvionics`-equivalent) and then only reaches 0.1; Unguided never can, at any tier.
   See `_ladUnshHibernate` / `hibernationFactor` / `CanHibernate` in `ModuleAxeAvionics.cs`. This is no
   longer a divergence and is kept only so the item numbering below stays stable.
5. **Guidance gate** at `postWarAvionics` vs RP-1's `start` — so the very start flies Science-Core only.
6. **SAS** is a flat level 3 (config), suppressed while dumb/axial by `AxeAvionicsController`.
7. **Funds, science storage, kOS — closed 2026-07-07.** Cost now has a real hardware-efficiency curve
   (§H, `GetModuleCost`), science storage is tier-gated like RP-1 (§I), and a kOS reflection bridge exists
   (§I, inert until kOS is an AXE dependency). See `docs/UPGRADES.md` §C1.
8. **~~No manual "disable for power" toggle distinct from Hibernate.~~ CLOSED 2026-08-05 — AXE now has
   RP-1's single mechanic.** RP-1's `advancedAvionics`+ toggle (`disabledPowerFactor`) and its Hibernate
   mechanic are the *same* underlying `systemEnabled` flag; "hibernation" is just what that toggle is called
   for Deep-Space. AXE used to carry a second, automatic `idleFactor` (0.1×) on top — and because
   `GuidanceActive` includes `guidanceEngaged`, merely **disengaging** guidance bought the full 10× power
   saving, contradicting `guidanceEngaged`'s own documented "no effect on EC draw" contract and leaving
   hibernation with nothing to sell (Standard's hibernate depth is *also* 0.1, so the tier-9 gate gated a
   number every core already had for free). Measured: the entire Deep-Space-vs-Standard cruise advantage on
   a 500 kg probe was **2.5 W**; with idle removed it is **47.3 W**. `idleFactor` is **deleted** — hibernation
   and on-rails are the only things that reduce draw.

## Unintended divergence — the TIER is not persisted (LOGGED 2026-08-05, undecided)

Unlike every item in the list above, this one is **not a design decision**. It has no record anywhere, and
it diverges from RP-1 *and* from the wider RO/RealFuels house pattern. Logged so a future avionics rework
starts from a known gap instead of rediscovering it.

**The RO/RF pattern is: tech gates what you may SELECT; the selection persists in the craft.** RealFuels
stores `_numberOfAddedMLILayers` on the part and clamps it to `maxMLILayers` on load. RP-1's
`ModuleProceduralAvionics` stores *both* axes explicitly:

```csharp
[KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Configuration", ...UI_ChooseOption)]
public string avionicsConfigName;   // Near-Earth / Deep-Space / Science-Core
[KSPField(isPersistant = true)]
public string avionicsTechLevel;    // the TIER, stored as the tech node name
```

plus a `SetFallbackConfigForLegacyCraft()` path for a craft referencing a config that no longer exists.

**AXE stores the axes but derives the tier.** `guidanceEnabled`, `shieldedEnabled`, `hwVolume`, `battVolume`
and the split all persist. There is no persisted tier field — `ApplyTier()` recomputes it at runtime from
whatever is currently researched, and `ApplyShieldedTier()` does the same through `_bestShieldedIdx`.

**The consequence is not subtle.** `massFactor` runs 87.99 (tier 0) → 11.396 (tier 13), a **7.7× span**. The
same `.craft` opened in a save with more tech gets ~7.7× lighter avionics hardware and correspondingly more
steerable capacity from an identical box — a different spacecraft, not a different readout. In a sandbox
(everything researched) every shared craft silently maxes. An RP-1 craft carries its designed tier and
behaves the same anywhere, up to the recipient's own ceiling.

**Both patterns have real virtues** — this is logged as *undecided*, not as a bug to fix on sight:

- *Tech-derived (AXE today)*: saved designs improve as you research, so there's no graveyard of obsolete
  `.craft` files, and it needs zero extra UI. Cost: not portable; a sandbox silently grants max.
- *Explicit-persisted (RP-1, RF)*: reproducible, self-documenting, survives sharing. Cost: needs a
  clamp-or-fallback path for recipients lacking the tech, and old designs go stale rather than improving.

Note that explicit-persisted buys only *partial* portability anyway:
`Mathf.Clamp(_numberOfAddedMLILayers, 0, maxMLILayers)` means a shared craft gives the designer's intent
only up to the recipient's own ceiling. Still strictly better than silently maxing, because the designed
value survives as data and degrades **visibly** instead of inflating **invisibly**.

## Design record — what was proposed here, and what shipped since

*Status audit 2026-08-05: everything below except "Decouple battery volume from box volume" has since
been built. The per-item status lines are current; the surrounding design prose is kept as the record of
how each decision was reached, and still describes the pre-build state where it says "currently".*

**Steerable-mass redesign (2026-07-08 design session) — SHIPPED 2026-07-10.** Box size → hardware mass →
inverse mass polynomial → `capacityTons`; one vessel-wide MAX (`EffectiveCapacityTons`, never SUM); over
capacity answered by control degradation (adversarial regime matching) rather than RP-1's hard lock. What follows is the
design pass as written on 07-08, when AXE still had no "controllable mass" concept at all — every core
auto-sized off whatever the vessel weighed when the ship was last modified in the editor, frozen at launch
(`UpdateHardwareMass()`, `load = VesselMassTons() - avionicsMass`). It records the route to reintroducing RP-1's real
tradeoff (cheap payload core + separate disposable ascent core, which is RP-1's own documented recommended
strategy — see `Procedural-Avionics-Basics` wiki) without RP-1's `controllableMass` slider or its hard
control-lock cliff (confirmed via research to be RP-1's #1 player complaint — silent failure misdiagnosed as
unrelated bugs for hours, even RP-1's own FAQ misfiles the symptom).

*Rejected direction*: auto-derive each core's "responsible mass" from vehicle topology (walk `Part.parent`/
`children`, treat `ModuleDecouplerBase`/`ModuleDockingNode`/`LaunchClamp` as graph cuts, sum the reachable
segment). Confirmed technically buildable (stock API sufficient, ~100-150 LOC, no MechJeb dependency needed —
see the `rp-axe-steerable-mass-design` memory for the full feasibility trace) but **semantically broken**:
(1) a bottom-stage core needs the mass of *every* stage above it, not just its own segment between the two
nearest decouplers — the algorithm undersizes exactly the core that needs to be biggest; (2) topology alone
cannot distinguish "10 independent payload satellites" from "10 serial stages" from "5 two-stage satellites" —
the intent isn't encoded in the graph, so no algorithm on `Part.parent`/`children` can resolve it. Killed,
not patched.

*Current direction ("flip it")*: box size determines capacity, not the other way around. Player resizes the
avionics part like any other procedural part (no typed number); volume × density → hardware mass → run
through the *inverse* of the existing mass polynomial → a "controllable mass" capacity number. Compare that
capacity against **live current total vessel mass** (same live number AXE already computes, same thing RP-1's
real control check — `ControlLockerUtils.ShouldLock` — actually does every frame). This needs zero topology:
a bottom-stage core just needs to be built big enough, a fact the player can see and fix directly in the
part's own PAW, not something the game has to infer from vehicle structure. Confirmed this also incidentally
kills the resize-jank risk from the topology direction — capacity is purely *derived from* size, nothing ever
forces the box to resize itself.

Sub-decisions made so far:
- **Multiple cores: MAX, not SUM.** Matches RP-1's own (deliberately changed-to-in 2021) behavior — summing
  lets you cheese capacity by stacking cheap small units, which RP-1 explicitly moved away from. Tradeoff:
  goes against naive player intuition (RP-1's own playerbase got blindsided by this exact change), needs
  clear in-game communication.
- **Under capacity → power penalty, not a lock.** Live draw already scales off current mass regardless of
  the core's own rating; the "penalty" is that formula doing what it already does once capacity stops being
  forced to always cover current mass. Visible on the existing Power/Endurance PAW readouts, no new UI
  needed. Deliberately not RP-1's hard binary lock (Locked/Axial/Unlocked, throttle included) — see the
  research citation above for why that's the wrong call to copy.

Open risk flagged but not resolved: a secondary "utilization" knob (trade capacity vs. battery within a
fixed box size, mirroring RP-1's own utilization concept) risks recreating a specific, real RP-1 pain point
— maxing utilization can silently starve battery volume to zero, unrecoverable without rebuilding the part
(`RP-1#1295`). If utilization gets built, it needs guardrails RP-1's own version didn't have.

Also flagged, not yet checked: whether the mass↔capacity curve produces sane numbers at realistic box sizes
(the formula has a hard minimum-size-for-any-positive-capacity threshold, same as RP-1's own
`GetControllableMass` clamp-to-zero) — needs real numbers run once this is implemented, not just formula
inspection.

See `rp-axe-steerable-mass-design` memory for the full session trace (this was a long back-and-forth; the
memory has more blow-by-blow than this doc needs).

**Near-Earth + Deep-Space → Guided merge gap — INVESTIGATED AND CLOSED (2026-07-08).** Original concern:
Guided uses pure Near-Earth numbers, and Deep-Space's premium (heavier `massConstant`, pricier `costConstant`,
`shieldingMassFactor=0.1` extra mass) doesn't exist anywhere in AXE — range enforcement legitimately moved to
comms (RealAntennas), but it looked like the *hardware cost of surviving far from Earth* got dropped along
with it. Traced all the way through and it didn't: `shieldingMassFactor` in RP-1 is read in exactly one place
(`GetShieldingMass()`), feeds only the mass/cost display, and connects to no failure/reliability/radiation
check anywhere — confirmed cosmetic. Kerbalism does ship a real radiation-accelerated hardware-failure
mechanic (`Reliability` module, `rated_radiation`/`radiation_decay_rate`, applies to probes) but it's fully
dormant — those fields are unset by every mod in this instance, not an avionics-specific gap. The bigger
finding: RP-1's actual "deep space is dangerous" enforcement was never a survival simulation — it was the
`interplanetary=True/False` field, a hard range-eligibility gate (Near-Earth literally can't operate past
some distance; Deep-Space could operate anywhere). Shielding mass was flavor bolted onto the same config
that flipped that flag. Since AXE already relocated range enforcement to comms as the *first* decision of
the whole Guided-merge redesign, there was nothing functionally real left behind to port — RP-1 never had a
working survival mechanic, just a range gate wearing a radiation costume. The `rp-axe-gate-ideas` memory's
"RADIATION HARDENING (Microelectronics)" idea is updated to reflect this and redirect toward the one real
difference found instead (see next entry). See `rp-axe-steerable-mass-design` memory for the full trace.

**What replaces it: gate Deep-Space's real remaining premium — hibernation depth/availability — behind a
paid tech+toggle (proposed 2026-07-08, not yet built).** RP-1 ground truth: Near-Earth avionics can't
hibernate/toggle to reduced power AT ALL until `advancedAvionics` tech (its first 8 tiers have no
`disabledPowerFactor` field), and even then only reaches `disabledPowerFactor=0.1`. Deep-Space gets a deeper
`0.05` reduction, available from tier 0, no tech gate. AXE's current Hibernate already (unintentionally)
gives every Guided core the DS-depth `hibernationFactor=0.05` for free, from any tier — the code comment
literally says "RP-1 deep-space depth," it just was never gated behind anything. Proposed fix: without a
paid deep-space tech+toggle, hibernation is either unavailable or only reaches the shallow `0.1` floor (and
only once `advancedAvionics` is researched, matching NE's real gating); with it, unlock the deep `0.05`
version from tier 0. Price TBD — leaning toward a smaller premium than RP-1's full DS `massConstant`/
`costConstant`/cost-×1.5 numbers, since "better hibernation" alone is a narrower benefit than "fully hardened
for deep space" was in RP-1. Open loose end: does hibernation depth stay uniform across all Guided cores
regardless of hardening once this exists, or does an unhardened core get bumped down to the shallow `0.1`
it should have had all along?

**Decouple battery volume from box volume.** Today `ApplyVolumeReservation` sends *all* leftover volume
(box volume − hardware volume) to RealFuels as tank capacity, unconditionally — a bigger box always means
proportionally more EC, with no way to build a bigger box without also getting more battery than you want
(e.g. to match a stack diameter, or to leave headroom to grow EC later without a rebuild). Neither RP-1 nor
current AXE support this — RP-1's `SendRemainingVolume()`/`GetAvailableVolume()` has the identical
unconditional-leftover behavior. Shape sketched 2026-07-08: a second AXE-owned fraction (how much of `avail`
actually gets sent onward to RealFuels; the rest stays dead volume in the box) — needs design first, not
started.

**Auto-hibernate on timewarp (on-rails) — DONE.** *(Was the last open item in this section; noted
2026-07-08, shipped since, and this entry described it as unbuilt until 2026-08-05.)* RP-1's base
`ModuleAvionics.cs` hooks `GameEvents.onVesselGoOnRails`/`onVesselGoOffRails` and calls
`UpdateRate(onRails: true)` on rails — which, for any config/tier that's toggleable
(`disabledPowerFactor > 0`: Deep-Space always, Near-Earth from `advancedAvionics` on), automatically drops
to the reduced draw rate for the whole warp, independent of the player's manual `systemEnabled` state, and
restores automatically on load. **AXE ports this directly**: `GoOnRails`/`GoOffRails` →
`RailChange(v, onRails)` → `UpdateRate()` (`ModuleAxeAvionics.cs`, hooks registered in `OnStartFinished`),
with `Asleep => guidanceEnabled && CanHibernate && (hibernating || _onRails)` and
`ComputeWatts(onRails)` returning `TierWatts() * CurrentHibernateFactor` — same "drop regardless of the
manual toggle, restore off rails" behaviour, Guided-only per the 07-08 hibernation restriction.

One deliberate difference from RP-1 on the automatic path: `_onRails` feeds the POWER calc only, not
`EffectiveCapacityTons`. RP-1's `currentlyEnabled = systemEnabled && !(toggleable && onRails)` also zeroes
`CurrentMassLimit` during warp, so a warping vessel's steerable-mass budget momentarily reads 0. Capacity is
a build-time property the player reads in the VAB, and blinking it to zero on entering timewarp is noise;
nothing steers while unloaded, so the distinction is inert. The manual `hibernating` toggle DOES leave the
budget, matching RP-1.

AXE also disables stock KSP's built-in probe hibernation (`%hasHibernation = False` in
`AxeAvionicsCore.cfg`) so it can't shadow the avionics' own toggle — except on named parts, where
`ModuleAxeFixedAvionics.ApplyHibernation()` re-enables it for a radiation-hardened unit whose
`shieldedTech` is researched, giving the `shd_*` lane something to sell there.

## Where the numbers live
- RP-1 coeffs: `RP-1/GameData/RP-1/Tree/ProceduralAvionics.cfg` (`AVIONICSCONFIGS`: Near-Earth …)
- RP-1 formulas: `RP-1/Source/RP0/Avionics/ModuleProceduralAvionics.cs` (`GetPolynomial`, `GetAvionicsMass`,
  `GetAvionicsCost`, `SetScienceContainer`)
- RP-1 base class (power draw → stock `ModuleCommand`, no custom brownout, the toggle/hibernate mechanic):
  `RP-1/Source/RP0/Avionics/ModuleAvionics.cs` (`UpdateRate`, `GetToggleable`, `ToggleEvent`)
- RP-AXE model: `Source/AXE/Avionics/ModuleAxeAvionics.cs`
- RP-AXE ladder (source of truth): `GameData/RP-AXE/design/Tree/AxeAvionicsCore.cfg` (`TIER` nodes)
- Battery tanks: `Instance/GameData/RealismOverhaul/RO_RealFuels.cfg` (`Battery-I..IV`)
- kOS field reference (not vendored — kOS isn't an AXE dependency): `kOSProcessor` fields `diskSpace` /
  `baseDiskSpace` (int) / `diskSpaceCostFactor` / `diskSpaceMassFactor` / `ECPerInstruction` (float), per
  https://ksp-kos.github.io/KOS/general/kospartmodule.html

Related: [[rp-axe-avionics-core]] memory.
