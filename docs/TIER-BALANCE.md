# RP-AXE Tier-Balance Audit (2026-07-29)

Tier-by-tier check of whether each tier actually *advances* the tree, and whether ladders
(instrument generations, tank/battery levels, engine configs) are spread across tiers or
collapsed onto one node.

**Snapshot:** `tree/nodes.yaml` @ 512 nodes, live `Instance/GameData/ModuleManager.ConfigCache`
of 15:20. The tree was being edited during the audit (509 → 512 nodes) — re-run the tools rather
than trusting the numbers below verbatim.

---

## 0. How "part capability" is estimated

The hard problem: ranking parts without a human eye. The model:

> **Capability is only comparable within a functional family, and within a family the thing that
> encodes TECH GENERATION is the INTENSIVE (specific) metric — W/kg, EC/kg, Isp, kN·m/kg, kW/kg —
> never the EXTENSIVE one (total EC, total thrust, panel area).**

A bigger battery is not a better battery. A 2 MN engine is not a more advanced engine than a
400 kN one — [`rp-axe-milestone-tiers`](../..) already says "tier follows generation, not thrust
magnitude"; this is the measurable form of that rule. Extensive size is a **mission-class** axis,
intensive performance is the **tier** axis. So each family declares both, and only the intensive
set drives any "A is worse than B" claim; the extensive set is used solely to check that two parts
are in the same size class before comparing them at all.

Consequences baked into `tools/tier_balance.py`:

- **Integrated buses are excluded from equipment leagues.** Vanguard 1 carries solar cells, but you
  do not pick it for its W/kg. Anything with `ModuleCommand`/crew is classified as a pod/core first.
- **Five families have a defensible scalar** and are checked for dominance: solar, battery, reaction
  wheel, radiator, antenna. For **solar the axis is the TL RUNG, not W/kg** -- ROSolar's grid charges a
  folded panel 1.05-1.75x and a sun-tracking panel 1.2-2.0x the mass for the *same* cell technology,
  so raw W/kg conflates geometry with generation (a folded TL5 reads 9.3 against a static TL5's 14.0).
  Every catalog panel fits the grid to within 5%, so the rung is the honest axis and deployment is an
  orthogonal choice. Deliberately **excluded**, because the obvious proxy is *wrong* rather than
  merely noisy:
  - *RTG* (dropped 2026-07-29 after it produced 23 findings, all artefacts) -- W/kg penalises exactly
    the right hardware. MMRTG (2.52 W/kg) really is less efficient than GPHS-RTG (5.37) because it
    trades efficiency for the ability to run in an **atmosphere**, which is why Curiosity carries one;
    and the Universal Storage wedge, quad-rack and `[Shielded]` variants are heavier by construction.
    Output class, atmosphere capability and form factor are the real axes, and none is a scalar;
  - *parachute* — `deployedDiameter`/kg conflates drogues with mains; RealChute doesn't store the
    number that matters (canopy area at deployment pressure);
  - *heatshield* — PART `maxTemp` is the structure's limit, not the ablator's capability;
  - *crewpod* — seat count is mission class, not tech;
  - *engines* — role/propellant/geometry dominate. Engines get their own instrument (below).
- **Engines are judged on their CONFIG ladder**, from `manifest/engine-stats.tsv` (real RO
  thrust/Isp/propellant per config) joined to the `RFUpgrade_<config>` node placement — so engine
  *upgrades* count, which is how this tree is meant to stretch a family across tiers. A config is
  only "beaten" by another config **of the same engine on the same propellant** that is ≥ on
  thrust, vacuum Isp **and sea-level Isp** (that last guard is what keeps sea-level nozzle variants
  like `RL10A-5` out of the report — 368 s vac looks terrible until you notice it's an SL engine).
- **A group is only a LADDER once the data says so.** Name prefixes lie: `RD-855`/`RD-856` are
  different engines, `PT6A-21`/`PT6A-42` are power ratings. Ladders are recognised from the
  upgrade's own text ("Level N"), a TL-numbering scheme, or a roman-numeral suffix — never from a
  bare trailing digit.

### The gate is not always where you think
Two mechanisms were mis-read at first and are worth recording:

1. **Science instruments are gated by Kerbalism `Configure` SETUPs**, not by parts. Every probe bus
   carries every `Experiment` module; the `tech = <AXE node>` on the SETUP is the real gate. Reading
   part placement alone says "`proceduralAvionics` at `start` has Mass Spectrometer 4" — false.
2. **The `Crew Science` Configure slot is gated by its HOST PART, not by tech** — all 14 of its
   setups read `tech = start` and are hosted on T6–T11 crewed modules. Only the `Experiments` slot
   (probe instruments) is genuinely tech-gated. Mixing the two makes the science ladder look
   catastrophically front-loaded when it isn't.

### Non-shipping scaffold -- three nodes the tools must ignore
Corrected by the author 2026-07-29, after this audit mis-read `experimental` as "where uncurated parts
land". The real pipeline is **`parking` -> `experimental` -> tree**, and *none of the three ships today*
-- they exist so the parts are reachable **in game while being evaluated**:

| node | what it is |
|---|---|
| `parking` | the build fall-through. `AxePartPlacement.cfg` wildcards every part here, then overrides the placed ones onto their real nodes, so this is "whatever the tree did not place". Held for P2 reconsideration; most of it is expected to be sacked. |
| `experimental` | the **shortlist promoted out of `parking`** -- parts under consideration for a real home. |
| `us2_serviceSandbox` | the same idea for the Universal Storage set, organised together pending an axe-or-place decision. |

So a tier, a cost or a science payload on any of them means nothing yet, and **a part promoted to the
shortlist must not start generating findings**. `tools/tier_balance.py` defines `SCAFFOLD` and the
detectors honour it. This had been applied to the part-dominance check but *not* to
`instrument_reachability`, which is exactly why finding B1 fired on a shortlist part.

**Also note:** the emitted `AxePartPlacement.cfg` (and therefore the live cache) can lag
`tree/nodes.yaml`. All tools prefer `nodes.yaml` for placement and fall back to the cache only for
upgrades the tree does not place. When cache and source disagree, source wins.

---

## 1. Tools

| tool | what it does |
|---|---|
| `tools/tier_balance.py` | parses the live cache → per-part family + intensive/extensive metrics → `manifest/part-capability-full.tsv` |
| `tools/tier_defects.py` | the detectors; `--section science-instrument\|level-ladder\|engine-config\|part`, `--json` |
| `tools/tier_report.py` | the tier-by-tier tables: capability frontier, engine frontier by propellant, internal spread, mission spine |

Detector vocabulary: **SUPERSEDED** (a strictly better rung unlocks earlier — the worse rung is dead
on arrival) · **COLLAPSE** (2+ rungs of one ladder on one node — a generation is skipped) ·
**FLAT** (rungs on the same tier via different nodes) · **GAP** (≥4 tiers with no progress) ·
**COMPRESSED** (fewer tiers spanned than rungs to spend) · **DOMINATED** / **DEADONARR** (part-level).

Census at time of writing: **112 findings** — 26 SUPERSEDED, 38 DOMINATED, 26 DEADONARR,
17 COLLAPSE, 4 GAP, 1 FLAT.

---

## 2. Findings, ranked

### A. `reactionWheelMode` is a ~1,000x lever, and `gnc_largeReactionWheels` is really a CMG node
**Corrected 2026-07-29** — the first draft of this finding claimed these parts were never
RO-rebalanced. That was wrong. RO ships a global solver, `RO_ReactionWheels.cfg`, that derives
torque from a declared power budget and deletes any `ModuleReactionWheel` it did not configure:

```
Torque[kN.m] = 0.0001 * 10^(log_base(reactionWheelPowerDraw / reactionWheelPowerBase))
    wheel mode: log_base 4.0, powerBase 0.150 (150 W)
    CMG   mode: log_base 2.5, powerBase 0.010 (10 W)
```

The formula reproduces every measured value in the tree exactly, so all eight wheels are
RO-configured:

| part | mode | power | torque kN.m | node | tier |
|---|---|---|---|---|---|
| `ca_rw_xsmall` | wheel | 48 W | 1.00e-4 | `gnc_reactionWheelAttitude` | T8 |
| `ca_rw_small` | wheel | 60 W | 1.00e-4 | `gnc_reactionWheelAttitude` | T8 |
| `sasModule` | wheel | 100 W | 1.00e-4 | `gnc_reactionWheelAttitude` | T8 |
| `ca_rw_medium` | wheel | 120 W | 1.00e-4 | `gnc_reactionWheelAttitude` | T8 |
| `ca_rw_large` | **wheel** | **180 W** | **1.35e-4** | `gnc_largeReactionWheels` | T9 |
| `restock-reactionwheel-radial-1` | **CMG** | **180 W** | **0.143** | `gnc_largeReactionWheels` | T9 |
| `advSasModule` | CMG | 500 W | 1.86 | `gnc_largeReactionWheels` | T9 |
| `asasmodule1-2` | CMG | 1 kW | 10.6 | `gnc_largeReactionWheels` | T9 |

The real defect is the **mode tag**, not the mod of origin. `ca_rw_large` and the ReStock radial
draw *identical* 180 W; one is tagged `wheel` and the other `CMG`, and RO's two curves return
1.35e-4 vs 0.143 -- a 1,054x difference for the same power budget. Consequences for the tree:

1. `ca_rw_large` is stranded: it is the only `wheel`-mode part on a node otherwise made of CMGs,
   so it can never be the sensible pick there.
2. **T9 is a 78,000x single-tier step** in attitude authority (1.35e-4 -> 10.6 kN.m), gated only on
   affording 1 kW -- about 33 kg of T9-era solar.
3. `asasmodule1-2` at 10.6 kN.m from a 200 kg unit is roughly 40x beyond a real ISS CMG. That is
   RO's CMG curve extrapolating badly at kilowatt scale, inherited rather than AXE-authored.

There is a third population the formula does not explain at all: RaiderNick/Coatl probe buses with a
hardcoded `PitchTorque` (0.0015 - 0.07 kN.m, T6-T12). And the `wheel` curve is **flat in the range
AXE actually uses** -- `ca_rw_xsmall` (48 W), `ca_rw_small` (60 W), `sasModule` (100 W) and
`ca_rw_medium` (120 W) all return exactly 1.00010e-4, because RO's `LOG_SOLVER` converges to ~0 for
any power draw below its 150 W reference. So all four T8 wheels are mechanically identical, and
`ca_rw_xsmall` (1.6 kg, 48 W) strictly dominates `sasModule` (50 kg, 100 W). **Noted, deferred**
(user call, 2026-07-29) -- it is an RO solver defect, not an AXE placement one.

**RESOLVED 2026-07-29** -- re-tiered, not patched (these are already at RO scale). The node had no
dependents, so the change was ripple-free; `build_tree.py` reports the same 6 pre-existing warnings
before and after.

| | before | after |
|---|---|---|
| T9 `gnc_largeReactionWheels` | "Large-Class Reaction Wheels" - `ca_rw_large`, `restock…radial-1`, `advSasModule`, `asasmodule1-2` | **"Gimballed Momentum Exchange"** - `ca_rw_large`, `restock…radial-1` |
| T11 `gnc_kilowattCMG` | — | **"Kilowatt-Class Momentum Exchange"** (new) - `advSasModule`, `asasmodule1-2` |

The gimbal, not the size class, is what the T9 node is really about -- so it now *introduces* the
smallest CMG, and T11 scales it to kilowatts. The new node takes a second parent,
`elec_matureSolarArrays` (T10): a plain physical dependency rather than a celebrated crossover, since
RO derives CMG torque straight from power draw and "gated only on affording 1 kW" was the whole
balance problem. It also keeps the edge to a single tier.

Resulting attitude ladder -- no bolt-on out-torques a station core of its own tier:

```
T9   0.143  bolt-on  restock-reactionwheel-radial-1   180 W
T10  2.94   core     sspx-core-1875-1 (3.38 m)        600 W
T11  1.86   bolt-on  advSasModule                     500 W
T11  10.6   bolt-on  asasmodule1-2                    1 kW
T11  29.4   core     sspx-core-375-1 / -5-1           1.5 kW
T11  60.6   core     acamar_crew_s2_1 (Kvant-1)       2 kW
```

### B. Instrument generations collapse -- and there are THREE gates, not one
An instrument generation is reachable by any of three routes, and checking only one hides leaks:

1. a Kerbalism `Configure` SETUP with `tech = <node>` (the multi-slot hosts);
2. a **bare `Experiment` module** on a dedicated instrument part -- then the PART's node is the
   gate and the tech ladder has no say at all;
3. the same SETUP list is **duplicated in `design/Science/Configure.cfg` and `US2.cfg`**, so editing
   one leaves the other live on every Universal Storage wedge.

`USFluidSpectroWedge` sits at T4 carrying all four mass-spectrometer experiments and is *correct*,
because route 1 gates each slot. `RO-AdvancedImager` carries one bare experiment and so leaks its
generation onto whatever node the part happens to live on.

The dedicated `RO-*` parts form clean numbered ladders (VI01-05, IR01-04, IS01-04, MS01-04, MG01-03,
RPWS01-03) but were placed by *what each node is about* rather than *by generation*:

| family | gen -> tier (before) | defect |
|---|---|---|
| **VI** visible imaging | 4, 5, 6, **6**, 10 | VI04 shares VI03's node; VI04 **also on `experimental` at T1** |
| **IR** radiometer | 5, 6, **6**, 10 | IR02/IR03 on the same tier |
| **IS** imaging spectrometer | **7**, 6, 6, 10 | IS01 arrives *after* IS02/IS03; IS02+IS03 share a node |
| **MS** mass spec | 4, **7, 7**, 9 | MS02+MS03 share `mic_ionMassSpec` |
| **MG** magnetometer | 4, 5, 8 | tiers clean -- but see the naming correction below |
| **RPWS** plasma wave | **8, 8, 8** | all three generations on one node (caps 7 / 20 / 30) |

**RESOLVED 2026-07-29 (hard defects only; same-tier pairs deliberately left).**

- **`aquila_sensor_visible_light_telescope_s0_1` dropped -- as a DUPLICATE, not as a leak.**
  It carried `RP0visibleImaging4` (cap 6) as a bare module while sitting on `experimental`.
  **Correction (author, 2026-07-29):** the original write-up called this a gate leak "handing out the
  gen-4 camera at T1 for 1 science". That reasoning does not hold -- `experimental` is non-shipping
  scaffold (see below), so nothing it contains is player-facing and no balance claim about it is
  meaningful. The argument that stands is the other one in the same commit: `RO-AdvancedImager`
  already carries `RP0visibleImaging4` at its proper rung, so this part was a pure duplicate. Its
  sibling SAR part carries no experiment and stays.
- **`RO-NIMS` re-homed** `opt_uvSpectrometry` (T6) -> `opt_multiSpectralImaging` (T7). Three defects in
  one placement: a **near-infrared mapping** spectrometer was sitting on the **ultraviolet** node
  (id-vs-title); it shared that node with `RO-UVSpectrometer`, making IS02 obsolete on arrival; and at
  T6 it made IS01 (T7) unbuildable. Mapping is the new node's own mechanism, and it gated no instrument
  before. **Both gates moved together** -- the part in `nodes.yaml` AND the slot in `Configure.cfg`
  *and* `US2.cfg`.
- **RPWS split into a three-rung ladder:**
  `mic_plasmaWave` T8 (RPWS01) -> **`mic_solarWindSpectrometry` T9** "Solar-Wind Ion Spectrometry"
  (RPWS02) -> **`mic_dipoleWaveSpectrometry` T10** "Electric-Dipole Wave Spectrometry" (RPWS03).

`tools/tier_defects.py` now reads slot gates from the **authored cfgs rather than the live cache**
(which is only as fresh as the last KSP run) and reports a **SPLITGATE** finding whenever the two
copies of the slot list disagree. They were in sync before this change; the detector exists so the
next edit cannot silently desync them.

**Naming correction 2026-08-19 (MG family).** The table above judged this family on *tiers only* and
called it clean. It was not: the T4 root `mic_magnetometer` was titled **"Fluxgate Magnetometry"** and
its flavor described the fluxgate saturation cycle read **"on a boom"** -- while the fluxgate part is
MG03 (`RO-FluxgateMagnet`, `mic_boomMagnetometryII`, T8) and the boom is the T5 breakthrough
(`mic_boomMagnetometry`). The node holds only MG01, a surface-attach early magnetometer whose RP-1
provenance note cites **Explorer VI**, a search-coil instrument read off the spacecraft's own spin.
Retitled **"Search-Coil Magnetometry"** with a search-coil flavor; the lunar-surface payoff sentences
from `bc420b1` are kept verbatim. The **id is unchanged** -- `mic_magnetometer` is a fine generic root
and renaming it would break string refs silently (`Configure.cfg`, `US2.cfg`, `AxePartPlacement.cfg`,
saves). Same id-vs-title shape as the `RO-NIMS`-on-the-UV-node defect above; the cause was age, not
judgement -- the title was correct when MG01 was the tree's only magnetometer (`321ea81`, band 1) and
never came back down as the ladder grew above it in bands 2 and 4.

**Left standing, by decision:** VI03+VI04 on `opt_refinedTV`; IR02+IR03 on tier T6; MS02+MS03 on
`mic_ionMassSpec`; bioScan1+2 on `bio_cultures`; IS01/IS03 now sharing tier T7 via different nodes.
Also noted, not fixed: `pioneer_6_7_8_9` (T7) carries RPWS02 and MG03 as bare modules, so those
generations are reachable a tier early *if you fly that specific historic bus* -- arguably a feature,
since the instrument comes welded to the spacecraft rather than available for your own designs.

### C. ~~`gnc_orbitalGravimetry` is worth more than the rest of the ladder~~ -- RETRACTED
**Withdrawn 2026-07-29 (user challenge).** The claim rested on comparing raw `scienceCap` across
instruments, and on summing those caps. Both are invalid: `scienceCap` is only half the payout, which
is `scienceCap x situationMultiplier` summed over the situations and biomes the experiment's masks
actually allow, so caps with different masks are not commensurable and their sum means nothing.

Run through the project's own ground-truthed model (`tools/science_budget.py`: real biome weights,
per-experiment `BodyAllowed`, RP-1's situation masks), `RP0orbitalPurturbation1` is **rank 4 of 98 at
148,950 realised** -- below `magScan3` (262,230), `massSpec4` (210,881) and `visibleImaging5`
(862,148). Its cap of 200 is buying back a `situationMask` of 48: SpaceLow + SpaceHigh only, two
situations against imaging's six, and no biome multiplier. **In band, not an outlier.**

And T8 is the right tier. Realised value against the tier that unlocks it climbs cleanly, with
orbital perturbation slotting exactly between its neighbours:

```
T4   56,235  massSpec1          T7  140,587  massSpec3
T5   78,669  magScan2           T8  148,950  orbitalPerturbation
T6  103,458  visibleImaging4    T9  210,881  massSpec4    T10  862,148  visibleImaging5
```

**No action.** Standing lesson, and the second time this audit has been caught by it: read the payout
model, not the headline field ([[kerbalism-pays-on-sciencecap]] says exactly this).

### C2. What the retraction surfaced -- one half real, one half the same mistake again
**C2b RETRACTED.** The claim was "film photography and imaging spectrometry pay ~1% of their peers".
That repeated finding C's error one finding later: the `RP0photos*` line is **Earth-only**
(`BodyAllowed = HomeBody`, `bodies = 1`), so comparing its all-body total against instruments that
fly to 32 bodies is meaningless. Measured on its own ground:

| experiment | Earth-only yield |
|---|---|
| `RP0photos4` | **10,000** |
| `RP0visibleImaging5` | 1,023 |
| `RP0orbitalPurturbation1` | 450 |
| `RP0magScan3` | 90 |
| `RP0massSpec4` | 86 |

Film photography is not the underpaying lane -- it is **the single largest Earth-science payout in the
game**, which is exactly right for a film-return reconnaissance programme, and it is what makes the
early Earth-bound game solvent. (`RP0imageSpec1-4` really are low -- caps 3-6, `sitMask 48`,
`biomeMask 0` -> 2.2k-4.5k -- but that is RP-1's own valuation of a niche instrument, and it shares a
lane with the photos earners, so OpticsPhotonics as a whole is healthy.)

**C2a -- real, and narrower than first stated.** `pioneer_6_7_8_9` carries `RP0magScan3` and
`RP0RPWS2` as **bare, ungated `Experiment` modules** alongside its own 21 properly Configure-gated
slots, so those two ride the charter node `jpl_lunarPlanetaryRecon` (T7) rather than their dedicated
parts (T8 / T9).

But this is **RP-1's deliberate convention, not a leak**: **18 of 29 historic buses** carry bare
`RP0RPWS*` / `RP0magScan3` modules -- these are the boom magnetometers and plasma-wave antennas that
were physically integral to those spacecraft, so RP-1 welds them on instead of making them swappable.
Every other bus in the convention sits at or after the dedicated parts (`torekka` T9, `rn_voyager` T9,
`galileo_mb` T10, `rn_cassini` T11); **`pioneer_6_7_8_9` at T7 is the only one that lands early.**
Nothing is dead -- the instrument is usable only by flying that specific bus, so the dedicated part
keeps its job.

**DECISION 2026-07-29: leave it, document only.** `tools/tier_defects.py` now tags this route
`welded` and reports it as an informational **WELDED** finding rather than SUPERSEDED, so it is not
re-flagged. *Noted:* the RPWS2 gap is 2 tiers rather than 1 because the finding-B RPWS ladder split
moved `RO-SWPlasmaAnalyzer` from T8 to T9 -- this audit widened it.

### D. Level ladders -- `solarTL` fixed to match `commsTL`; the rest are not defects
A levelled ladder should spend one rung per tier where it has the tiers to do it. Ground-truthing what
each rung actually *delivers* turned most of this list into non-findings.

**RESOLVED 2026-07-29 -- `solarTL`.** The decisive fact: `ModuleROSolar` consumes **solarTL1-solarTL10
only**. `solarTL0` is declared by ROSolar but never referenced -- an inert baseline marker. So the real
ladder is **10 rungs, and it spans exactly 10 tiers (T4-T13)**: one rung per tier is achievable, which
is the shape `commsTL` already has. It was doubled at T6 (TL2+TL3) and T7 (TL4+TL5) with T5 and T8
holding no rung at all.

Two new cell-chemistry nodes take the displaced rungs, continuing the lane's own
one-cell-breakthrough-per-rung pattern rather than parking them on deployment or simulation nodes:

| tier | node | rung | W/kg |
|---|---|---|---|
| T4 | `elec_arCoatings` | TL1 | 5.6 |
| **T5** | **`elec_griddedContacts`** "Gridded Contact Metallisation" *(new)* | TL2 | 8.0 |
| T6 | `elec_nOnPCell` | TL3 | 9.4 |
| T7 | `elec_dopedCoverglass` | TL4 | 11.0 |
| **T8** | **`elec_violetCell`** "Violet-Cell Shallow Junction" *(new)* | TL5 | 14.0 |
| T9 | `elec_backSurfaceField` | TL6 | 30.0 |
| T10-T13 | thinSilicon / GaAs / tripleJunction / metamorphic | TL7-TL10 | 58.6 - 376 |

Both inserts re-parent the chain (`elec_nOnPCell` onto `elec_griddedContacts`, `elec_backSurfaceField`
onto `elec_violetCell`) so no transitively-redundant edge appears. Historically the 1972 COMSAT violet
cell really is the step immediately before the back-surface-field cell. `tier_defects.py` now also
drops **inert rungs** -- a PARTUPGRADE no module consumes -- but only when siblings in the same family
*are* consumed, so a ladder with a different mechanism is never silently lost.

*Accepted consequence:* this shifts the TL->tier map that finding F used to home the fixed catalog
panels (T7 is now TL4 rather than TL5). Every panel stays within the +/-1 tier band F already treated
as tolerance, so nothing needs re-homing (user call).

**NOT defects -- checked and dismissed:**
- **`PFTech-Fairing` I-VI.** The pairs group *material generations*: T4 metal stringer (Al 0.135 ->
  Mg 0.124), T9 fibreglass -> isogrid (0.074 -> 0.068), T12 composite -> advanced (0.042 -> 0.040).
  Each node is one materials family with its own refinement, and the big steps (-40%, -38%) land on
  the node boundaries. Deliberate.
- **`MLI.Upgrade` 2-5.** The upgrades' own text reads *"this is not a part you can use, it just
  symbolizes"* additional insulation layers. Pairing them makes a bigger single step; low impact.
- **`RFTech-ComSat` / `RFTech-NavSat`.** Only two rungs exist (II, III). A 2-rung ladder spanning five
  tiers is a short ladder, not a gap.
- **`HDD-Upgrade` 2010+2020** (T15) and the `RFTech-solids-tltech` same-tier pairs -- endgame and
  side-lane respectively; noted, not chased.

### E. Engine configs that unlock out of order -- 28 claimed, 4 real
The first pass compared configs on thrust and vacuum Isp alone and reported 28. That is the wrong
test: a config with less thrust or Isp is still the right pick if it burns longer, restarts more,
throttles deeper or weighs less. Requiring dominance on **every axis a builder actually chooses
between** -- thrust, vac Isp, SL Isp, rated burn time, ignition count, throttle depth and massMult --
drops it to **4**. Two further false positives died on a subtler point: a **blank `massMult` means
1.0, not "unknown"**, and skipping the test when one side was blank let `SPT-100M` (28% heavier than
`SPT-100B`) and `DS4G-50-hi` (2.25x heavier than `DS4G-25-mid`) read as free upgrades.

So 24 of the 28 were side-grades. `tools/tier_defects.py` now carries the strict comparator.

**RESOLVED 2026-07-29 -- the two genuine inversions, wrong against performance AND RP-1's own era
ordering (`engine-stats.tsv` `node_title`).**

- **Merlin 1D.** The part `ROE-Merlin1D` is at T13, but `Merlin1D++` (914 kN) sat at **T11, two tiers
  below its own part**, while the weaker `Merlin1D+` (825 kN) was gated at T14. In play: at T13 you
  received base *and* `++` together, and `+` was dead on arrival. Both cost 56 and share RP-1's
  2014-2018 era node; history puts `+` (full-thrust, 2015) before `++` (Block 5, 2018).
  **Swapped** between `fd_keroloxClusterApex` (T11) and `fd_densifiedPropellantKeroloxII` (T14). The
  vacuum line (`Merlin1DVac` T13 -> `Merlin1DVac+` T14) was already ascending and is untouched.
- **RD-275.** `RD-275M` (1830 kN, RP-1 era 2004-2008) was gated at T10 while the earlier, weaker
  `RD-275` (1746 kN, era 1992-1997) sat at T11. **Swapped** between `pc_stagedCombustionCeiling`
  (T10) and `pc_operationalStorableORSC` (T11).

  *The swap broke the ladder gate -- re-fixed 2026-07-30.* Swapping the two configs was not a
  like-for-like exchange: `RD-275` (1746 kN) is in the **same padding class** as `RD-253-Mk3` (1698)
  and `RD-253-Mk4` (1748) -- within 3% on every axis `_ladder_near` reads -- and `RD-275M` is in its
  own. So moving `RD-275M` up onto T11 put *two* classes on `pc_operationalStorableORSC` (R1
  `1 collapsed node`, red build since `03d73d3`) and split the Mk3 class across T10/T11 (an R4).
  Fixed by unifying the class instead of trading places: `RD-253-Mk3`, `RD-253-Mk4` **and** `RD-275`
  all now sit on `pc_refinedStorableORSCII` (T10) -- the lane's "Mk2->Mk3 next rung" collector, where
  the RD-253 line previously had no rung at all -- leaving `RD-275M` alone at T11 as the family's only
  real step past that point. Ladder reads T8 1545 -> T9 1635 -> T10 {1698/1746/1748} -> T11 1830, and
  `pc_stagedCombustionCeiling` is back to hosting only `RD-277M-14D16M` (below).
  **Lesson: a tier swap must exchange padding CLASSES, not configs** -- both gates are needed, since
  `tier_defects` only compares configs pairwise and cannot see that a move collapses a class boundary.
  *`RD-277M` / `RD-277` -- CHECKED 2026-07-29, NOT the same defect.* The pair looks back-to-front by
  date (RD-277M is 2009-2013, RD-277 is 1998-2003) but `RD-277M` trades **burn time**: 129 s against
  RD-277's 225 s, 43% less, for +88 kN (+4.8%) and +2 s sea-level Isp. A genuine choice, not a free
  upgrade -- which is precisely why the strict comparator flagged RD-275 and refused to flag this one.
  Both configs stay viable, so there is no gameplay defect, and the placement is thematically right:
  `pc_stagedCombustionCeiling` (T10) is about the thrust CEILING of storable staged combustion -- its
  king is RD-270 at 6,713 kN -- so the family's highest-thrust variant belongs on it. **No action.**

  *Consequence of the RD-275 swap, fixed:* `pc_operationalStorableORSC`'s flavor named "the RD-275
  first stage", and the swap moved that config down to T10. Re-pointed at **RD-275M**, which is what
  the node now holds and is itself the line's final operational mark -- so the flavor reads truer than
  before rather than merely being patched.

**Left standing, by decision -- 2 dead configs.** Not power creep, just clutter nobody picks; both are
inherited from RP-1, which ships them the same way:
- `RL10A-3-3B` (T9) vs `RL10A-3-3A` (T8) -- 66.7 kN/440 s against 73.4/444.4 at identical burn and
  mass. Here RP-1's history *agrees* with the tree's order (3A 1972-75, 3B 1981-85): the later variant
  really was lower-thrust. History and performance genuinely disagree, so there is no ordering that
  satisfies both.
- `RL10A-4N` vs `RL10A-4-1N`, both on `cryo_refinedExpander` (T7), same RP-1 era: 92.5 kN/448.9 s/burn
  402 against 99.2/450.5/burn 740, and the better one is also *lighter*. RP-1 co-locates them too.

### F. Solar: the catalog is frozen, the procedural panel is not
The structural fact that makes this whole family legible, and it validates design rule 7
("procedural is the DEFAULT; fixed-catalog variants -> opt-in dead-ends") with numbers:

- **`ROS-StaticSolarPanel`** (ROSolar's procedural panel) carries `ModuleROSolar` *and* the
  `solarTL1-10` UPGRADES. It tracks the ladder: **5.0 W/kg at TL0 (1956) -> 376 W/kg at TL10
  (Modern)**, a 75x climb across T4-T13.
- **Every fixed catalog panel** has **no UPGRADES at all** -- `ModuleDeployableSolarPanel` plus
  `ModuleROSolarPanel`, and the latter is *only a VAB planning UI* (decompiled: it reads `chargeRate`
  to predict output at a chosen body's Pe/Ap and modifies nothing). They are frozen forever at their
  authored W/kg.

So each catalog panel is implicitly authored to ONE **(solarTL rung x deployment type)** grid point,
and `TechLimits.cfg` gives the grid: TL0 5.0 · TL1 5.6 · TL2 8.0 · TL3 9.4 · TL4 11.0 · TL5 14.0 ·
TL6 30.0 · TL7 58.6 · TL8 122.6 · TL9 265 · TL10 376 W/kg, with mass multipliers 1.05-1.75 for
folded and 1.2-2.0 for tracking. Fitting all 34 placed panels to that grid lands them at **0-5%
error** -- this is not a heuristic, the parts really were built to these numbers.

That turns the question from "which parts dominate which" into one mechanical check: **is each frozen
panel homed where its own era unlocks?** Mostly yes, within +/-1 tier. The spread inside
`elec_deployablePanelII` that the first draft called a 2.6x same-node gap is mostly *static vs folded
vs tracking on the same TL5 rung* -- legitimate geometry variety, not a generation gap.

**RESOLVED 2026-07-29.**

- **Power creep -- 5 NearFutureSolar arrays, 2 tiers early.** They measure 376-418 W/kg = TL10
  (Modern), which unlocks at `elec_metamorphicMultijunction` (T13); at T11 the ladder only reaches
  TL8 (122.6), so they were **3.4x better than anything else at their tier** -- the same defect class
  as the `experimental` T1 camera in finding B. `elec_deployableBlanketArray`,
  `elec_concentratingPhotovoltaic` and `elec_advancedRigidArray` **re-tiered T11 -> T13**, with
  `elec_tripleJunctionCell` (T12) added as a second parent: the plain physical prerequisite (the cells
  the arrays are built from), which also keeps the edge to a single tier.
- **Dead content -- 4 Coatl bus arrays 2-5 tiers late on a main-lane node.** `ca_vor_sp2` at
  **2.8 W/kg is below the TL0 1956 floor of 5.0** -- worse than the panel you start with, offered at
  T9. Moved off `elec_probeBusSolarWings` into a new dead-end, **`elec_busArrayCatalog` (T8),
  "Prefabricated Spacecraft-Bus Arrays"** (nothing depends on it), per rule 7. The two parts left on
  the main-lane node measure TL6 static/folded = exactly its tier.

### F2. Panels judged against the PROCEDURAL default (2026-07-29)
Re-measuring on the axis that actually matters in play -- **is a fixed panel better or worse than the
procedural panel you already own at that tier, for the same deployment class?** -- reversed one of F's
conclusions and sharpened the rest. (User steer: *"it's ok to be earlier than historical, it has to
make sense from gameplay"*.)

- **The TL5 panels on `elec_deployablePanelII` (T7) read 1.27x procedural -- a modest reward for
  buying the node. LEFT IN PLACE.** An earlier draft proposed moving them to T8 "to match their era";
  that would have turned a reward into parity and made the node pointless. Being ahead of history is
  doing real work here.
- **Six panels sat BELOW the procedural default -- dead content -- and were moved to where they reach
  parity:** `solarPanels2`, `solarPanels4`, `solarPanels5`, `1x3SPanels` (all TL2, 0.73-0.77x) from
  `elec_deployablePanelII` (T7) to **`elec_deployableArrays` (T5)**, whose procedural rung IS TL2; and
  `ROC-ApolloSolarBlockV` + `ROC-OrionSolar` (TL6, 0.47-0.48x) from `elec_matureSolarArrays` (T10) to
  **`elec_stationClassSolarArrays` (T9)**, which is now entirely TL6 -- a clean single-generation node.
- **Left by decision:** `sp_mariner_a` (2.65x at T7) and `ca_landv_sp` (2.40x at T8) are the largest
  remaining rewards, well above the 1.27x band -- but both are integrated into a specific spacecraft
  on a mission node, so they are only usable by building that vehicle. Same argument that settled the
  welded instruments in C2. `rn_surveyor_solar` and `ca_landv_hga` are weak for the same reason and
  stay too.
- **Detector:** solar comparisons now require the **same deployment class**. A tracking panel pays
  1.2-2.0x the mass of a static one built from identical cells and buys continuous sun-pointing; a
  folded one pays 1.05-1.75x and buys stowed volume. Comparing a folded TL4 with a static TL5 compares
  two products, not a dead part.
- **Follow-up, DONE:** `RO_EarlyMediumSolarPanel` (TL1) briefly became the weakest part on
  `elec_deployableArrays` beside the TL2 panels moved in, so it went to **`elec_siliconPV` (T3)**
  alongside `RO_EarlyTinySolarPanel` -- the other TL1 static panel. The two early-era panels now share
  a node and differ only in size, and `elec_deployableArrays` is a clean all-TL2 node.

**Solar lane closed.** The only same-deployment-class generation gaps left on any single node are
`elec_busArrayCatalog` (the rule-7 dead-end, where era-frozen hardware is the point) and
`elec_deployablePanelII` folded TL4+TL5 -- where the TL4 is at parity with procedural and the TL5 is
the 1.27x reward, so neither is dead.

**Left standing, deliberately:**
- `ca_landv_hga` (TL3/tracking, implies T6) stays on `int_surveyorLanderBus` (T8) -- it is a combined
  antenna-and-array integral to the Surveyor bus, and pulling it out would break that mission set.
- `sp_mariner_a` on `gnc_threeAxisStabilizedBus` (T7) measures TL6/tracking = 16.7 W/kg, implying T9
  -- **2 tiers early**, about 2.1x the procedural tracking array at its tier. Smaller than the NFS
  case but the same shape; not acted on.
- `nfs-panel-deploying-curved-375-1` on `elec_curvedExpandingArray` (T11) exposes **no solar output at
  all** in the cache, so it could not be fitted to the grid. Worth a look on its own -- a solar node
  whose only part may not generate power.

### G. Tanks -- the material ladder (2026-07-29)
Tanks were one of five families the capability model punted on ("no defensible scalar"), which meant
*unmeasured*, not *balanced*. RealFuels does expose the right number: each `TANK_DEFINITION` carries
`basemass = <x> * volume`, so **dry mass per unit volume IS the capability**, and the types form
explicit material ladders -- `Tank-Sep-` Steel -> Al -> Al2 -> AlCu -> AlLi -> Stir -> Starship, plus
`Tank-Iso-` and `Tank-Balloon-` families. They are gated by `RFTech-Tank-*` PARTUPGRADEs wired through
`ModuleFuelTanks` `UPGRADES { typeAvailable = ... }`.

This matters more than any other family: tank dry-mass fraction drives every staging decision.

**RESOLVED.** Two defects, both in the separated-tank line:

- **`Tank-Sep-Al` and `Tank-Sep-Al2` shared `met_weldedTank` (T1).** Al2 is 32% lighter (27.0 vs
  39.55) with better utilisation (92 vs 87) for 10% more cost, so Al was obsolete on arrival -- and
  against the `Tank-Sep-Steel` start baseline of 70.0, one T1 purchase dropped tank dry mass **70 ->
  27, 2.6x, in a single node**. Al2 moved to a new **`met_stringerTankage` (T3)**, "Stringer-Stiffened
  Tankage". T1 -> T3 is a deliberate two-tier jump, taken to spread the gain.
- **`Tank-Sep-AlCu` was homed on `int_geminiCapsule` (T7)** -- the only rung of the material ladder
  outside Metallurgy, which gated the tank ladder on building a capsule. Moved to a new
  **`met_aluminiumCopperTankage` (T7)**, keeping the pacing identical and changing only the lane;
  `met_aluminiumCopperBalloonTank` (T9) now hangs off it so the chain is explicit. `RFTech-SM-III`
  stays on the Gemini node -- a SERVICE-MODULE tank level genuinely is a capsule-programme
  breakthrough.

The separated-tank ladder now reads as one Metallurgy chain, one rung per step:

```
start  Tank-Sep-Steel      70.0     T7   met_aluminiumCopperTankage  AlCu      20.0
T1     met_weldedTank      Al 39.5  T11  met_aluminiumLithiumTankage AlLi      15.5
T3     met_stringerTankage Al2 27.0 T13  met_stirWeldedTankage       Stir      14.5
                                    T15  met_stainlessSteelTankage   Starship  18.0
```

**Checked and dismissed:** `Tank-Sep-Starship` (T15) is *heavier* than `Tank-Sep-Stir` (T13) -- 18.0
against 14.5 -- which looks like an inversion. It is not: Starship is **35% cheaper** at identical
97% utilisation, a real cost/mass trade and the actual design philosophy of the vehicle it is named
for. Same sidegrade class as the engine configs dismissed in E.

### H. Heatshields -- audited, ladder sound (2026-07-29)
The second of the five punted families. The first draft's proxy was PART `maxTemp`, which is the
STRUCTURE's limit rather than the ablator's capability -- it classified `ROC-D2Parachute` as a
heatshield (that part does carry 12 units of Ablator, so the misread was earned).

There is no single scalar for NAMED shields, and this time the reason is properly established rather
than assumed: ablator **amount** is extensive (it scales with capsule diameter -- `ROC-GeminiHSLunarBDB`
45 kg/169 units against `ROC-OrionHS` 300 kg/720 units, both lunar-rated), and ablator **per kg** comes
out noisy at 2.2-3.8 because material and geometry vary independently of rating.

But the capability axis does exist, stated in prose by RO and gated properly:
`ROHeatshields/Heatshield-Presets.cfg` defines `ROHS_PRESET`s by **rated reentry regime**, and each is
unlocked by its own PARTUPGRADE named after the preset -- consumed by the ROHeatshields plugin, not by
a module `UPGRADES` block. All six are placed in `nodes.yaml`, and they ascend:

| preset | rated for | gate | tier |
|---|---|---|---|
| `Heatsink` | LEO with a deeply negative perigee | `cmp_ablativeTPS` | T5 |
| `MercuryHS` | non-lifting LEO | `cmp_ablativeRefinement` | T6 |
| `GeminiHS` | lifting LEO | `cmp_ablativeRefinement` | T6 |
| `EarlyLunarHS` | lunar | `cmp_lunarReturnAblator` | T8 |
| `LunarHS` | lunar and interplanetary | `cmp_lunarLandingAblator` | T9 |
| `Inflatable` | Mars or very gentle Earth (sidegrade) | `cmp_inflatableDecelerator` | T11 |

**No defect.** A false alarm en route is worth recording: `ROH-AdjustableHS` sits at T5 and advertises
`presets = Heatsink, MercuryHS, GeminiHS, EarlyLunarHS, LunarHS` with `UPGRADES: NONE`, which reads as
"interplanetary reentry available at T5". It is not -- that field lists the presets the part SUPPORTS,
and each one is gated separately. Fourth time in this audit a frightening-looking field turned out to
be fine once the gating mechanism was found rather than inferred.

**Worth considering, not acted on:** `MercuryHS` and `GeminiHS` share `cmp_ablativeRefinement` (T6).
Non-lifting and lifting LEO reentry are two distinct capability rungs arriving on one node -- the same
COLLAPSE class as the `solarTL` pairing fixed in D. Smaller stakes, since both are LEO-class.

**Also dismissed:** `ROC-BigGeminiHS` (152 kg / 380 ablator) beside `ROC-BigGeminiHSLunar`
(190 kg / 456) on `cmp_lunarLandingAblator` (T9) looks like a dead LEO variant next to its lunar
sibling. It is a mass trade -- the LEO shield is 20% lighter -- so both have a role.

### I. Crew pods -- audited; volume-per-seat is the ladder (2026-07-29)
Third of the punted families. The original dismissal ("seat count is a mission-class axis, not a tech
axis") was right, but for a stronger reason than stated, and it missed the axis that IS real.

**`kg/seat` is role-dominated, not a tech axis.** It spans 250 - 10,000 across the family, and the
spread tracks *function*, not generation: cockpits 325-1081, reentry capsules 395-1215, station
habitats 620-8358, greenhouses and observation domes 7000-9358. A greenhouse is not a worse capsule.

**`m3/seat` (Kerbalism `Habitat.volume`) IS the ladder, and it ascends correctly.** Habitable volume
per crew is what drives Kerbalism comfort/stress and therefore mission duration:

```
T3-T7  cockpits and capsules   1.10 - 4.50      T10  3.36 - 22.05
T8     first station modules   3.85 -  8.07     T11  6.63 - 95.40
T9                             7.06 - 33.75     T12 13.37 - 95.50
```

**A test that looked role-neutral and was not.** "Within one node, does a sibling have both more
m3/seat and less kg/seat?" produced 51 pairs -- and most compare across the family's ~10 functional
roles: an **airlock** out-scoring a reentry capsule, a **cockpit** (which flies the aircraft) against a
passenger cabin, a **station core** (docking ports, avionics, controls) against a bare habitation
module, a **lab** against anything at all. Recorded because the lesson keeps recurring in this audit:
an intensive metric is only comparable inside a single role, and "crew pod" is not one role.

**One same-role outlier**, all three on `life_inflatableHabitat` (T11):

| part | mod | total | crew | kg/seat | m3/seat |
|---|---|---|---|---|---|
| `InflatableHAB` | VenStockRevamp | 25.0 t / 66 m3 | 10 | **2500** | **6.63** |
| `sspx-inflatable-hab-125-3` | StationPartsExpansionRedux | 1.4 t / 25.7 m3 | 3 | 467 | 8.57 |
| `sspx-inflatable-hab-25-1` | StationPartsExpansionRedux | 31.6 t / 635 m3 | 18 | 1756 | 35.28 |

Both mods are RO-patched (`RO_VNP_Command.cfg` covers `InflatableHAB`), so this is **not** an
unpatched-part leak like the reaction wheels or the curved solar panel -- it is a cross-mod scaling
disagreement about what an inflatable weighs. Against the real reference, Bigelow B330 at 20 t / 330 m3
/ 6 crew = 3333 kg/seat and 55 m3/seat, `InflatableHAB`'s MASS is realistic and its VOLUME is roughly
8x too low: priced like an inflatable, sized like a rigid module. The sspx parts are light on mass but
sane on volume. **Open call, not yet acted on.**

### J. RCS -- audited, clean (2026-07-29)
Last of the punted families (parachutes skipped, user call). RCS has **two** gates and both are sound.

**1. The RealFuels tech-level ladder** `RFTech-rcs-tltech1-7` -- one rung per tier, ascending:
T2 `gnc_rcs` -> T3 `gnc_standardRCS` -> T5 `gnc_spacecraftRCS` -> T8 `pc_storableRcsPropellants` ->
T9 `gnc_bipropAttitudeThrust` -> T10 `pc_cryogenicRcsFeed` -> T11 `gnc_longLifeRCS`. (This ladder had
two descending rungs when the audit began; the author fixed them in `bb57599`/`ae26672`, and the
build's own tech-level gate now reports clean.)

**2. Per-propellant `CONFIG`s**, each gated by its own chemistry node, ascending in Isp multiplier:
```
Helium  (start) 0.453     MMH/UDMH+NTO etc  T8  0.943-0.955
HTP     T2      0.465     Cavea-B           T9  0.939
N2O     T4      0.525     H2+O2             T9  1.329
Nitrogen T5     0.195     RP-1/Syntin+O2    T11 0.951-1.016
Hydrazine T5    0.720     CH4+O2            T12 1.047
```

**`Nitrogen` (0.195) looks like dead content at T5 -- it is not.** It is a density/Isp trade:

| | Isp mult | density | impulse per tank VOLUME | tank mass |
|---|---|---|---|---|
| Helium | 0.453 | 1.786e-7 | 8.1e-8 | 0.000115 |
| Nitrogen | 0.195 | 1.251e-6 (7x denser) | **2.4e-7 (3x better)** | 0.000095 (lighter) |

Helium wins impulse per propellant MASS; nitrogen wins 3x on impulse per VOLUME and carries a lighter
tank. The same trade the tree deliberately celebrates for kerolox vs hydrolox.

**3. Zero dominated parts** among the 123 dedicated thrusters -- but only after two exclusions, both of
which are lessons this audit has now hit three times each:
- **fixed-catalog nodes.** Including `gnc_standardRCS` ("Interchangeable-Part Manufacture", 42
  interchangeable blocks) produced *42 KB* of mutual-dominance pairs. Mutual dominance is what a
  catalogue IS.
- **integrated parts.** `thrusterPower / part mass` only means anything for a part whose JOB is RCS.
  Comparing whole spacecraft on it -- Cassini 2,025 kg against Mars Observer 892 kg, Juno against
  LCROSS, Galileo against Magellan -- measures the spacecraft, not the thruster. Identical to the
  integrated-bus error corrected for solar in F.

**Noted, not acted on:** `RO-2kN-Thruster` sits on `gnc_rcs` (T2) with default
`configuration = Nitrogen`, but the Nitrogen config is gated at T5 -- so for three tiers the part
cannot use the propellant it is named for and falls back to Helium. Harmless (Helium is free from
start) but the node comment does describe it as "Nitrogen cold-gas thruster".

## 3. Tier shape -- three claims made, three retracted

Every tier-shape finding in the first draft turned out to be an artefact of measuring the wrong
quantity. Recorded in full because the *way* each was wrong is the reusable part.

### 3a. "T5 is a trough" -- RETRACTED
Measured **part count** (65, against T4's 177) and called it thin. Part count is not what a tier
delivers. T5 carries 24 nodes with payload in **12 of 21 disciplines**, including six FluidDynamics
nodes (restartable/throttleable upper stages, storable clustering), ablative TPS, deployable solar,
pressurised cabin, launch escape, first lunar probes and application satellites -- a coherent "now do
things in orbit" generation.

Measured against the doctrine's own sizing rule (~3 parts/node ideal, HARD MAX 6), **T5 is the
best-proportioned tier in the tree**:

```
tier   T0   T1   T2   T3   T4   T5   T6   T7   T8   T9  T10  T11  T12  T13
p/node 7.5  6.4  6.8  5.8  4.8  2.7  3.3  3.9  5.1  2.4  3.5  2.9  1.8  1.0
```
The bloat is at the FRONT (T0-T2 above the hard max), not at T5.

### 3b. "The solid lane has a five-tier dead zone then an 81x jump" -- RETRACTED
Measured **peak thrust per tier** off the engine frontier -- the one axis
[[rp-axe-milestone-tiers]] explicitly forbids tiering on ("tier follows generation/milestone-role,
NOT thrust magnitude"). The lane actually advances at every tier: `pc_doubleBaseSolid` T1 (6p) ->
`pc_doubleBaseBooster` T2 (3p) -> **`pc_compositeSolid` T3** (ammonium-perchlorate composite grains,
4p) -> four nodes at T4 (`pc_scoutSolids`, `pc_strapOnSolids`, `pc_retroKick`,
`pc_pioneerVernierTrim`) -> `int_launchEscape` T5 -> `int_crewedRetroPack` T6 -> six nodes at T7 ->
two at T8. The T7 thrust step is where segmented casting and composite binders arrive: a real
generation that happens to unlock big boosters. Correct as designed.

### 3c. "Computing contributes nothing before T8" -- RETRACTED
A discipline-LABEL artefact. The avionics capability ladder is one continuous 14-rung `grants:` chain
running `gnc_postWarAvionics` T1 -> `gnc_avionicsPrototypes` T2 -> `gnc_earlyAvionics` T4 ->
`gnc_basicAvionics` T5 -> `shd_basicAvionics` T6 -> `comp_digitalGuidanceComputer` T8 -> ... -> T16.
The early rungs are simply filed under GuidanceControl. Counting nodes per discipline made a
continuous ladder look like a lane that starts late.

### 3d. What actually stands: node sizing -- and rule 8 was being measured wrong
Counting **part INSTANCES** flags 67 nodes and is mostly noise. Rule 8 is about how many distinct
things a node asks the player to understand, so the honest count is **part FAMILIES** -- titles
normalised by stripping sizes, dimensions and length qualifiers. `str_adjustableGear` holds 8 parts
that are *one* undercarriage in eight sizes; `life_stationLogistics` holds 17 that are *three*
storage modules in every length. Neither is a rule-8 violation.

`tools/check_node_sizing.py` implements that, plus two exemption classes beyond the ids the rubric
already lists: the GroundSupport line and catalog dead-ends (documented), and **mission-charter nodes
(`jpl_*`, `okb_*`), which hold COMPLETE SPACECRAFT by design** -- Huygens alone is a lander, a
parachute, two heatshield halves and a heatshield parachute.

```
nodes over 6 parts: 67
  exempt by class ............ 26
  <= 6 FAMILIES (rule 8 met) . 19
  genuinely over ............. 22
```

The 22 are a **curation backlog against design rule 8, not a balance defect** -- nearly all are
commodity families (tanks, lights, chutes, docking mechanisms, airframes, trusses) that want either a
split or a place on the exemption list, node by node. Two stand out as real crowding rather than
commodity: **`fd_restartableUpper`** (T4) puts 8 distinct engine families on one breakthrough node,
and **`opt_vidicon`** (T4) mixes its real king, the VI01 Early Television Camera, with 9 utility
hull-cameras that belong in a catalog dead-end.

The T12-T16 tail (1.8 -> 0.2 parts/node) is the known, deliberately deferred colonization scaffold
(RESTART P6) -- 46 nodes with no real hardware yet.

## 4. Not flagged (checked, and intentional or inherited)

- `parking` (T0, cost 999, root) catches **490 uncurated parts** via `AxePartPlacement.cfg`'s
  wildcard. Known dev holding pen; the RDNode emits no `Unlocks`, though `TechRequired = parking`
  still gates the parts. Worth revisiting against the RESTART decision that uncurated parts belong
  on the `experimental` side-node, but not a tier-balance defect.
- The T0 `Crew Science` setups (scienceCap up to 200) — gated by T6–T11 host parts, not by tech.
- `RL10A-5` and other sea-level nozzle variants — real side-grades, filtered by the ispSL guard.
- Engine "families" that are really different engines sharing a name prefix (`RD-855`/`RD-856`,
  `PT6A-*`, `NK-33`/`NK-43`) — never treated as ladders.
