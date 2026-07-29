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

### C. `gnc_orbitalGravimetry` (T8) is worth more than the entire rest of the probe ladder
Orbital Perturbation carries `scienceCap = 200`. Every other probe instrument is 1.5–30, and they
sum to ~177. It is RP-1's own number, vendored verbatim (the file carries RP-1's "strongly
recommended not to change anything in this section" comment), and its `situationMask = 48` (two
situations) partly offsets the headline — payout is `scienceCap × situationMultiplier`, so this is
not a 133× advantage in realised science. It is still the single largest probe payout in the tree,
and it sits on a GNC node rather than anywhere in the OpticsPhotonics or Microelectronics lanes
that the rest of the instrument ladder runs through.

Related: the **OpticsPhotonics lane is nearly worthless in science terms** — 8 instrument-bearing
nodes yielding caps of 2, 2, 3, 2, 3, 4, 3, 4 (~24 total) against 3 NuclearEngineering nodes
yielding 7+10+20+30 = 67.

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

### E. Engine configs that unlock out of order (28 findings; representative)
| engine | dead config | beaten by |
|---|---|---|
| `ROE-RD108` | `RD-108-8D77` T4 `fd_regenCooling` 803 kN | `RD-108-8D75-1958/59/K` T3 `met_nimonic` 941–945 kN |
| `ROE-RL10Fixed` | `RL10A-3-3B` T9 `cryo_largeHydrolox` 67 kN/440 s | `RL10A-3-3A` T8 73 kN/444 s |
| `ROE-RL10Fixed` | `RL10A-3-7` T10 67 kN/442 s | `RL10A-3-3A` T8 73 kN/444 s |
| `ROE-M1` | `M-1SL` T12, `M-1U-SL` T13 | `M-1U` T11 8007 kN/430 s |
| `ROE-RD275` | `RD-253-Mk3/Mk4`, `RD-275` T11 | `RD-275M` T10 1830 kN |
| `ROE-RD254` | `RD-254-11D44-Mk3/Mk4`, `RD-277-14D16` T11 | `RD-277M-14D16M` T10 1922 kN |
| `ROE-LE5` | `LE-5` T11 103 kN/450 s | `LE-5A` T7 122 kN/452 s |
| `ROE-Merlin1D` | `Merlin1D+` T14 825 kN | `Merlin1D++` T11 914 kN |
| `ROE-NK33` | `AJ26-59` T13 | `AJ26-62` T12 |
| `RO-SPT100` | `SPT-100B` 1600 s | `SPT-100D` 1740 s — **same node** `ep_kilowattPPU` T11 |

The `ROE-RD275`/`ROE-RD254` pattern is one mistake repeated: `pc_stagedCombustionCeiling` (T10)
hands out the best config in the family, and `pc_operationalStorableORSC` (T11) then hands out three
weaker ones.

### F. Same-node capability gaps (38 DOMINATED)
Nodes holding a clear upgrade next to its own predecessor:

| node | tier | family | spread | worst → best |
|---|---|---|---|---|
| `gnc_largeReactionWheels` | T9 | reaction wheel | see **A** | |
| `gnc_reactionWheelAttitude` | T8 | reaction wheel | 31× | `sasModule` → `ca_rw_xsmall` |
| `elec_deployablePanelII` | T7 | solar | 2.6× over **10 panels** | `1x3SPanels` 0.0054 → `solarPanels5HiTech` 0.014 |
| `elec_probeBusSolarWings` | T9 | solar | 10.9× | `ca_vor_sp2` → `SXTsolarPanelhex` |
| `elec_matureSolarArrays` | T10 | solar | 2.1× | Apollo Block V → `largeSolarPanel` |
| `nuc_isotopePowerII` | T8 | RTG | 3.4× over 7 RTGs | `rtgMini` → SNAP-27 |
| `elec_gphsRTGGeneration` | T10 | RTG | 2.1× over 8 RTGs | MMRTG → GPHS-RTG |
| `okb_lunaLanders` | T7 | battery | 2.8× | `luna_radio` → `l11_astro` |
| `th_activeLouvers` | T7 | radiator | 1.25× | `ca_louver_s2` → `ca_louver_m` |

`solarPanels5` ("ST1 Solar Panel") and `solarPanels5HiTech` ("ST2 Solar Panel") on one node is the
purest instance — a named upgrade pair sharing a home.

---

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
