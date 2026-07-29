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
- **Six families have a defensible scalar** and are checked for dominance: solar, battery, RTG,
  reaction wheel, radiator, antenna. Deliberately **excluded**, because the obvious proxy is *wrong*
  rather than merely noisy:
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
| **MG** magnetometer | 4, 5, 8 | clean -- the model the others should follow |
| **RPWS** plasma wave | **8, 8, 8** | all three generations on one node (caps 7 / 20 / 30) |

**RESOLVED 2026-07-29 (hard defects only; same-tier pairs deliberately left).**

- **`experimental` (T1, 1 science) was handing out the gen-4 camera.**
  `aquila_sensor_visible_light_telescope_s0_1` carried `RP0visibleImaging4` (cap 6) as a bare module,
  beating anything the optics lane delivers through T6 and killing VI01/VI02/VI03 outright. **Dropped
  from the manifest** -- `RO-AdvancedImager` already carries VI04 at its proper rung, so the part was a
  pure duplicate. Its sibling SAR part carries no experiment and stays. Note nothing strips science
  from parts homed on `experimental`, so a science-bearing part must never be placed there.
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

### C2. What the retraction did surface
- **`magScan3` (262,230 realised -- the largest payout in the game before T10) is reachable at T7 via
  `pioneer_6_7_8_9`** on the charter node `jpl_lunarPlanetaryRecon`, while its dedicated part
  `RO-FluxgateMagnet` sits at `mic_boomMagnetometryII` (T8). This is the mission-part leak noted under
  B and set aside as marginal. It is not marginal: it is the one thing that breaks the monotonic climb
  above, making T8 (149k) and T9 (211k) both pay *less* than the tier before them. Same shape for
  `RPWS2` (31,115) on the same part.
- **Film photography and imaging spectrometry pay ~1% of their peers.** Realised: `photos1` 96,
  `photos1a` 48, `photos2` 192, `photos3` 500, `photos4` 10,000; `imageSpec1/2/3` 2,234-2,979,
  `imageSpec4` 4,468 -- against 26k-862k for the TV-camera, mass-spec and magnetometer lines. So the
  original "OpticsPhotonics is nearly worthless" was also mis-aimed: `visibleImaging` (the TV cameras)
  is the most valuable line in the game. It is specifically the `RP0photos*` and `RP0imageSpec*`
  sub-lanes -- about 9 nodes -- that pay almost nothing.

### D. Level ladders: `commsTL` is the model, five others are compressed
| ladder | rungs → tiers | verdict |
|---|---|---|
| `commsTL` | 1→T5, 2→T6, 3→T7, 4→T8, 5→T9, 6→T10, 7→T11, 8→T12, 9→T13, 10→T14 | **exactly one rung per tier — the reference implementation** |
| `solarTL` | 0,1→T4 · 2,3→T6 · 4,5→T7 · 6→T9 · 7→T10 · 8→T11 · 9→T12 · 10→T13 | 11 rungs, but the first six arrive **two at a time** |
| `RFTech-rcs-tltech` | 1→T5 · 2,3→T8 · **6→T10** · 4,5,7→T11 | 3 rungs on one node; **level 6 unlocks before 4 and 5** |
| `RFTech-solids-tltech` | 1,2→T7 · 3→T8 · 4,6,7→T10 · **5→T11** | 3 rungs on one node; **level 5 arrives after 6 and 7** |
| `MLI.Upgrade` | 1→T3 · 2,3→T9 · 4,5→T11 | paired rungs **and** a 6-tier dead stretch T3→T9 |
| `PFTech-Fairing` | I,II→T4 · III,IV→T9 · V,VI→T12 | paired throughout |
| `HDD-Upgrade` | 1961→T3 · 1964→T4 · 1969→T10 · 1975→T11 · 1990→T13 · 1998→T14 · 2010,2020→T15 | 6-tier gap T4→T10 |
| `RFTech-ComSat` / `RFTech-NavSat` | 2→T5 · 3→T10 | 5-tier gap |
| `RFTech-Battery` | II→T6 · III→T7 · IV→T9 | **fixed during this audit** (was II,IV→T6 · III→T7, i.e. IV before III) |
| `RFTech-SM` | II→T5 · III→T7 · IV→T9 | clean |
| `airlaunchTL` | 1→T2 · 2→T3 · 3→T5 · 4→T6 | clean |

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
  *Flagged, not acted on:* the neighbouring `RD-277M-14D16M` (T10) / `RD-277-14D16` (T11) pair has the
  same shape. It survives the strict test on another axis, so it was left pending a look -- the two
  nodes may have been populated back-to-front as a pair.

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

**Left standing, deliberately:**
- `ca_landv_hga` (TL3/tracking, implies T6) stays on `int_surveyorLanderBus` (T8) -- it is a combined
  antenna-and-array integral to the Surveyor bus, and pulling it out would break that mission set.
- `sp_mariner_a` on `gnc_threeAxisStabilizedBus` (T7) measures TL6/tracking = 16.7 W/kg, implying T9
  -- **2 tiers early**, about 2.1x the procedural tracking array at its tier. Smaller than the NFS
  case but the same shape; not acted on.
- `nfs-panel-deploying-curved-375-1` on `elec_curvedExpandingArray` (T11) exposes **no solar output at
  all** in the cache, so it could not be fitted to the grid. Worth a look on its own -- a solar node
  whose only part may not generate power.

## 3. Tier shape

### Node census
```
        T0  T1  T2  T3  T4  T5  T6  T7  T8  T9  T10 T11 T12 T13 T14 T15 T16
nodes   2   19  24  25  37  24  33  55  42  59  56  51  40  23  11  8   4
parts   15  123 164 151 177 65  111 207 217 149 198 147 73  22  3   2   3
```
- **T5 is a trough** — 24 nodes and only **65 parts**, sandwiched between T4 (177) and T6 (111).
  It is also the tier immediately after first orbit (T4), so the tier you reach right after your
  first satellite is the emptiest in the first half of the tree.
- **T7 is a bulge** — 55 nodes / 207 parts, the largest tier in the tree.

### Lanes that barely exist, or exist only at one tier
- **Thermodynamics**: 5 nodes in the whole tree (T3, T7, T9×2, T11).
- **ResourceEngineering**: 3 nodes (T9, T10×2).
- **Robotics**: 12 nodes, **8 of them at T7**.
- **Computing**: contributes nothing before **T8** — the entire lane starts after lunar probes.
- **Cryogenics**: T1 (the empty `cryo_hydrogen` commitment gate), T2, then nothing at T3, T5 or T6
  before it ramps at T7+ — the hydrolox gamble has a three-tier hole in the middle of its own story.

### Engine frontier by propellant (best kN / best vac Isp reachable *by* that tier)
```
              T0    T1    T2    T3    T4    T5    T6    T7      T8      T9    T10   T11   T12
kerolox kN    -     -     -     999   1532  =     1948  =       7775    8815  9190  =     14920
kerolox Isp   -     -     -     315   =     326   330   =       339     342   =     =     362
hydrolox kN   -     -     70    =     =     =     667   =       890     5338  6672  8007  =
hydrolox Isp  -     -     410   =     422   =     427   466     =       =     =     =     483
hypergol kN   1.9   49    99    623   1765  3113  =     3358    =       =     6713  =     =
solid kN      147   =     218   =     =     =     =     17740   35390   =     =     =     =
nuclear Isp   -     -     -     -     -     -     -     -       -       831   850   1350  =
```
- **The solid lane has a five-tier dead zone then an 81× jump.** 218 kN at T2, nothing at all until
  **17,740 kN at T7**. Nothing between a sounding motor and a Titan/Shuttle-class SRB.
- **Kerolox jumps 4× at T8** (1,948 → 7,775 kN) with T5 and T7 contributing nothing to the class.
- Hypergolics are the smoothly-paced lane and are the best model in the engine set.

### Mission spine
First orbit is **T4** (`jpl_firstSats` / `okb_firstSputniks`); crewed capsules T6; lunar landers T7–T8;
stations T9–T11. Cumulative science to T4 is ~1k of a ~300k tree, so the run to orbit is cheap by
design. No capability family was found arriving *after* the mission that strictly requires it — the
closest call is `commsTL1` at T5 against first satellites at T4, which the base antenna tech level
covers.

---

## 4. Not flagged (checked, and intentional or inherited)

- `parking` (T0, cost 999, root) catches **490 uncurated parts** via `AxePartPlacement.cfg`'s
  wildcard. Known dev holding pen; the RDNode emits no `Unlocks`, though `TechRequired = parking`
  still gates the parts. Worth revisiting against the RESTART decision that uncurated parts belong
  on the `experimental` side-node, but not a tier-balance defect.
- The T0 `Crew Science` setups (scienceCap up to 200) — gated by T6–T11 host parts, not by tech.
- `RL10A-5` and other sea-level nozzle variants — real side-grades, filtered by the ispSL guard.
- Engine "families" that are really different engines sharing a name prefix (`RD-855`/`RD-856`,
  `PT6A-*`, `NK-33`/`NK-43`) — never treated as ladders.
