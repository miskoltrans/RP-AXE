# Upgrade Ladders — engine config placement doctrine

Status: **COMPLETE 2026-07-27.** `ladder gate: 0 collapsed · 0 base-node · 0 descending` — and R1/R2/R5
now **fail the build** if they regress (`AXE_LADDER_SOFT=1` to downgrade mid-edit).
Live check: `python tools/build_tree.py`, read the `ladder gate:` line.
Worklist data: `manifest/upgrade-ladders.tsv`. Retargeting tool: `tools/retarget_upgrades.py`.

Started at **160 collapsed (part, node) pairs across 130 of 258 engine families**; the tree went
457 → 493 nodes, ~40 of them added to give an uprate an honest home.

---

## 1. The problem

`met_stainlessSteel` (T2, Metallurgy) carries **20 config upgrades across 6 engine families**, including
the entire RD-100 ladder — RD-101, RD-102, 5D60, RD-103, RD-103M. One purchase at tier 2 takes the engine
from 307 kN to 500 kN (**+63 % thrust, +11 s Isp**) and hands over four decisions at once. RP-1 gated those
same configs behind four separate nodes.

It is not a one-off. Two views of the scale, both true, measuring different things:

**Authoring view** — hand-written `upgrades:` lists in `tree/nodes.yaml`, i.e. what a designer edits:

| | count | share |
|---|---:|---:|
| nodes stacking ≥2 rungs of the same part | 58 | |
| upgrade refs that are stacked rungs | 339 / 549 | 62 % |
| engine families fully collapsed onto one node | 53 / 107 | 50 % |
| stacked rungs strictly dominated at unlock | 63 | |

**Resolved view** — after `merge_placement` + auto-placement, i.e. what the game actually sees. This is
the authoritative number and it is roughly 2.5× larger, because many parts share a config set (all six RCS
thrusters carry `microEngine`'s propellant menu; `ROE-LR87`, `ROE-LR87_11` and `ROE-LR87_Single` share the
LR87 configs):

| | count |
|---|---:|
| engine families with placed config upgrades | 258 |
| families with ≥1 collapsed node | **130** |
| (part, node) pairs granting >1 config | **160** |
| unique config tokens placed — *the actual edit surface* | 522 |

The edit surface is smaller than the damage: 93 config names are shared by more than one part, so fixing
one placement fixes it everywhere that name is used.

## 2. Root cause

The doctrine at `tree/nodes.yaml:388` is right:

> *uprates home NON-LINEARLY at what enabled them — a thrust-uprate homes at the ALLOY that let the engine
> run harder (Metallurgy); an Isp gain at the INJECTOR.*

The failure is **granularity**. It was applied per *engine family* (one family → one enabler) instead of per
*config* (one config → its own mechanism). Once a node is "the alloy node", every uprate that plausibly
needed better steel lands in it, and the enabler becomes a bucket.

The tell is that the node contradicts its own doctrine: RD-103 gains **+13 s ispVac**, which by the rule
above belongs at a combustion node, not at Metallurgy.

And the actual config data says the enabler was never the steel at all:

```
RD-100   Ethanol75+LqdOxygen   307 kN   ispV 237     <- base
RD-101   Ethanol90+LqdOxygen   404 kN   ispV 237     <- every uprate is 90 % alcohol
5D60     Ethanol90+LqdOxygen   466 kN   ispV 248
RD-103   Ethanol90+LqdOxygen   490 kN   ispV 248
RD-103M  Ethanol90+LqdOxygen   500 kN   ispV 248
```

The RD-100 ladder is a **propellant-chemistry story** (less water ballast in the alcohol → hotter chamber),
wearing a metallurgy node's name.

## 3. Taxonomy — four relationships, not one

The word "upgrade" was doing four jobs. Classified across all 448 placed engine configs:

| kind | count | share | what it is | where it belongs |
|---|---:|---:|---|---|
| **RUNG** | 264 | 59 % | next generation of the same engine on the same propellant | one per node, along its discipline's **spine**, increasing tiers |
| **PADDING** | 87 | 19 % | functionally identical to a sibling (±3 % on thrust/Isp/ignitions/burn) | **co-locate** with its twin — never its own tree event |
| **FORK-propellant** | 62 | 14 % | first config on a *new* chemistry | the node that unlocks **that chemistry** (cross-lane) |
| **BASE** | 17 | 4 % | base config listed as an upgrade | audit separately (doctrine #4 risk) |
| **FORK-nozzle** | 15 | 3 % | same generation, different expansion ratio / duty | the **nozzle or duty** node |
| **FORK-densified** | 3 | 1 % | `Cooled*` propellants — subcooled/densified | the **densification** node |

Only 59 % are ladder rungs. The remaining 41 % were never a progression, so "spread them across tiers" is
the wrong fix for them — they need *homing*, not *spacing*.

Two families that the collapse metric was misreading:

- **LR87 / LR91.** The `-Kero` suffix is a **propellant fork**, not a rung. `LR87-AJ-5` is `Aerozine50+NTO`;
  `LR87-AJ-5-Kero` is `RP-1+LqdOxygen` — same generation, different chemistry. `fd_titanStorableConversion`
  ("Storable-Propellant Booster Conversion") currently holds *both*, which makes its title a lie for half
  its contents. The storable side belongs there; the kerolox side belongs on the kerolox spine.
  `LR87-AJ-7` is `CooledAerozine50+CooledNTO` — a densification step, its own mechanism again.
- **`microEngine`.** Not a ladder in any sense — it is a **propellant menu**. 17 configs, one per chemistry
  (HTP, Hydrazine, MMH+NTO, MMH+MON3, CH4+O2, H2+O2, Syntin+O2, Cavea-B, ASCENT, cold gas…).
  `pc_storableRcsPropellants` grants 12 of them in a single T8 purchase. Every one of those should unlock
  when its chemistry unlocks elsewhere in the tree. Zero new nodes needed for most of them.

## 4. Rules

> **Standing direction (user, 2026-07-27): SCATTER is the default.** When a config has a real mechanism
> behind it, give it its own node — Materials, Metallurgy, chemistry, cycle, nozzle, whatever the mechanism
> actually is. New nodes are cheap; a fat node that hides four decisions is not. Merging and `catalog: true`
> are narrow exceptions for configs that genuinely are *one* decision, never a way to keep the node count
> down. When in doubt, add the node.
>
> This has already been applied twice against my own earlier instinct: a sea-level-Isp tolerance was tried
> and reverted because it merged classes, and R6 was rewritten from "merge before inventing" to the
> opposite. The Blok-D family went from one bucket to five nodes on that basis.

- **R1 — one decision per part per node.** A node may grant at most one *performance point* for a given
  engine part. Counted in equivalence classes (see R4), so cosmetic twins riding together are fine and two
  genuinely different configs are not. Machine-checkable; the invariant that would have caught this at
  authoring time.
- **R2 — rungs ascend.** Successive rungs of a family sit at strictly increasing tiers.
- **R3 — forks home at their own enabler.** A propellant fork homes at the chemistry node; a nozzle fork at
  the expansion/duty node; a densification fork at the densification node. Forks are cross-lane gates and
  are the most legible teaching moments in the whole system — they say *why* the engine got better.
- **R4 — padding co-locates, it never earns an event.** Configs at the same performance point (±3 % on
  every axis) are *one decision* however many names RealFuels gives it. They may share a node as cosmetic
  variants; what they must not do is occupy separate tree events. So R1 counts **equivalence classes**,
  not configs.

  > **Corrected 2026-07-27 during implementation.** The design first said "drop padding outright". That was
  > wrong on mechanism and on scope. `manifest/upgrades-curated.tsv` is read only by the partlist
  > extractors — `build_tree.py` never consumes its `disposition`, so a `DROP` there is a no-op. No
  > config-removal mechanism exists at all, and building one is undesirable: `emit_entry_cost_mods` chains
  > each config to the previous rung of its own ladder, so deleting configs breaks the ENTRYCOSTMODS graph,
  > and AXE's standing rule is to port RO content as-is rather than reinvent it. Co-location gets the whole
  > benefit — padding stops consuming tree events — at zero risk and with no content lost.
- **R5 — respect doctrine #4.** A config upgrade never lands on the node that holds its own base part.
  When walking a spine, skip that node.
- **R6 — a new node beats a near-enough home.** If a family has more distinct classes than its spine has
  honest steps, **add the node**. Materials, metallurgy, chemistry and cycle nodes are all fair game when a
  rung has a real mechanism and nowhere truthful to sit. Merging is for classes that genuinely *are* one
  decision; a `catalog: true` node is for a family that is genuinely unordered. Neither is an excuse to
  park a config on a node whose subject it has nothing to do with.

  > **Revised 2026-07-27 (user call).** R6 originally said "merge before inventing — do not invent spine
  > nodes to absorb rungs." That was too tight and it was already producing bad homes: `RL10A-3-3A`, a
  > burn-life and nozzle step, had been parked on `cryo_deepThrottleHydrolox` purely because the expander
  > lane had no T8 step. It now has one (`cryo_extendedBurnExpander`), and the placement is honest.

### Why dominance is not a separate problem

Of the 63 strictly-dominated stacked rungs, **30 become live choices again purely from spreading** — RD-101
is only dead because RD-103 arrives in the same instant. Only **33 are genuinely redundant** (dominated by a
same-or-earlier-era config) and those are exactly the R4 co-locations. Dominance is a *symptom*; fix placement and
most of it evaporates.

## 5. The spines already exist

This is a codification, not an invention — 54 of 107 families are already spread across multiple nodes.
`ROE-RD107` is the model: 9 configs across `met_nimonic` T3 → `fd_regenCooling` T4 → `fd_engineMaturation` T6.
`ROE-Agena` already forks correctly to `pc_fluorine` for its F2/H2 variant.

| spine | discipline | steps |
|---|---|---|
| **Kerolox gas-generator** | FluidDynamics | `fd_regenCooling` T4 → `fd_vacuumExpansion` T6 → `fd_engineMaturation` T6 → `fd_clusteredThrustGrowth` T7 → `fd_gasGeneratorCeiling` T8 → `fd_gasGeneratorApex` T9 → `fd_matureKeroloxClusterUprating` T9 → `fd_terminalGasGenKerolox` T11 → `fd_reusableGasGenKerolox` T12 → `fd_densifiedPropellantKerolox` T13 → `…II` T14 |
| **Storable upper** | FluidDynamics | `fd_restartableUpper` T4 → `fd_spacecraftPropulsion` T5 → `fd_restartableUpperMaturation` T9 → `fd_multiRestartStorableUpperII` T12 |
| **Hydrolox** | Cryogenics | `cryo_hydroloxPrototype` T2 → `cryo_expanderCycle` T4 → `cryo_refinedExpander` T7 → `cryo_gasGeneratorHydrolox` T8 → `cryo_largeHydrolox` T9 → `cryo_uprateRestartableHydrolox` T10 → `cryo_matureGasGeneratorHydrolox` T10 → `cryo_ssme` T11 → `cryo_deployableNozzleExpander` T11 → `cryo_operationalHydroloxUpperII` T12 → `cryo_combustionTapOff` T12 → `cryo_highThrustExpander` T12 → `cryo_reusableEngineUprating` T13 |
| **Staged combustion** | PropellantChemistry | `pc_orscDebut` T8 → `pc_protonStagedCombustion` T8 → `pc_n1ClosedCycle` T9 → `pc_refinedStorableORSC` T9 → `pc_stagedCombustionCeiling` T10 → `pc_zenitKerolox` T10 → `…ORSCII` T10 → `pc_multiChamberORSC` T11 → `pc_operationalStorableORSC` T11 → `pc_modularORSC` T12 → `…II` T13 |
| **Air-breathing** | Metallurgy → AirBreathing | `met_nimonic` T3 → `met_cooledTurbine` T4 → `av_refinedTurboprop` T5 → `av_advancedJetEngines` T8 → `av_advancedFighterTurbojets` T8 → `av_advancedHighSpeedTurbojets` T8 → `av_secondGenTurbofan` T9 → `av_fourthGenFighterTurbofan` T10 |
| **Electric** | ElectricalPower | `ep_operationalHall` T11 → `ep_highPowerHall` T12 → `ep_pulsedInductiveII` T13 → `ep_nasaHighPowerHall` T13 → `ep_nextGenGriddedIonII` T14 → `…HallII` T14 → `ep_variableSpecificImpulsePlasmaII` T15 |

Capacity is adequate: the worst family after padding removal (RL10, 13 rungs) fits the 13-step hydrolox
spine, and R6 absorbs any overflow.

## 6. Fork targets → nodes

Most forks already have a home. These exist and should simply be used:

`pc_htp` T2 · `pc_hypergolics` T2 (Visol+Salbei, amine blends) · `pc_ntoHypergolics` T4 (UDMH+NTO,
Aerozine50+NTO) · `pc_fluorine` T6 · `fd_blendedStorableFuel` T7 (UH25) · `pc_juno_ClF3` T7 ·
`pc_caveaB` T9 · `pc_n1ClosedCycle` T9 (subcooled) · `cryo_hydroloxPrototype` T2 (H2+O2) ·
`cryo_smallScaleMethalox` T12 (CH4+O2) · `fd_densifiedPropellantKerolox` T13

**Eight new nodes are required** — all in the chemistry lane, all earning their place as fork targets for
2+ families. Titles follow house style (one mechanism, named by the mechanism):

| id | title | disc | tier | serves |
|---|---|---|---|---|
| `pc_ethanol90` | High-Concentration Alcohol Fuel | PropellantChemistry | 2 | **RD-100 ladder** — the headline fix |
| `pc_hydyne` | Amine-Blend Booster Fuel | PropellantChemistry | 3 | Hydyne+O2 (Juno I), 2 families |
| `pc_rp1` | Narrow-Cut Refined Kerosene | PropellantChemistry | 4 | RP-1+O2, 4 families |
| `pc_hydrazineMonoprop` | Catalytic Hydrazine Decomposition | PropellantChemistry | 5 | monoprop RCS — a real gap today |
| `pc_rg1` | High-Density Kerosene Cut | PropellantChemistry | 8 | RG-1+O2, 2 families |
| `pc_mon` | Nitric-Oxide-Doped Oxidiser | PropellantChemistry | 9 | MMH+MON3, Hydrazine+MON3, 5 families |
| `pc_syntin` | Strained-Ring Synthetic Fuel | PropellantChemistry | 10 | Syntin+O2, 4 families |
| `ep_kryptonFeed` | Krypton Propellant Feed | ElectricalPower | 13 | 5 electric families |

`pc_ascent` (ionic-liquid green monopropellant, ~T14) is a ninth candidate serving one family — defer unless
the late-tree electric/RCS region wants it.

## 7. Worked dispositions — headline families

### `ROE-RD100` — the headline case (5 configs on one T2 node → 3 events)

| config | kind | disposition |
|---|---|---|
| RD-101 | FORK-propellant `Ethanol90+O2` | **→ `pc_ethanol90` T2 (new).** +32 % thrust, Isp flat — a pure chamber-pressure gain off the hotter alcohol |
| RD-102 | RUNG (thr −8 %, isp −13) | **co-locate with RD-101** at `pc_ethanol90`. Regressive and dominated — it is not a second decision |
| 5D60 | RUNG (thr +15 %, isp +11) | **→ `met_stainlessSteel` T2.** The Isp+thrust step the alloy actually bought |
| RD-103 | RUNG (thr +15 %, isp +13) | **merge into 5D60** (R6) — same performance point |
| RD-103M | RUNG (thr +2 %) | **→ `fd_engineMaturation` T6.** A burn-life/qualification uprate, which is what that node is for |

Result: 5 collapsed configs → **3 tree events across 3 nodes and 3 tiers**, one dropped, one merged. The
stainless node keeps a real thrust uprate (so its flavor stays true) and stops claiming credit for the alcohol.

### `microEngine` — 12 configs on `pc_storableRcsPropellants` T8 → scatter to chemistry

Every config is a propellant fork. Retarget each to its chemistry node — `HTP`→`pc_htp` T2,
`Hydrazine`→`pc_hydrazineMonoprop` T5 (new), `UDMH+NTO`/`Aerozine50+NTO`→`pc_ntoHypergolics` T4,
`MMH+MON3`/`MMH+MON10`→`pc_mon` T9 (new), `Cavea-B`→`pc_caveaB` T9, `CH4+O2`→`cryo_smallScaleMethalox` T12,
`H2+O2`→`cryo_hydroloxPrototype` T2, `Syntin+O2`→`pc_syntin` T10 (new), `RP-1+O2`→`pc_rp1` T4 (new),
`Ethanol+O2`→`pc_ethanol90` T2 (new), `ASCENT`→defer, cold gas stays on the base part.
`pc_storableRcsPropellants` then holds **nothing** and should be deleted — its job was always done by the
chemistry lane. This is the single highest-value change in the plan: one dead bucket node becomes eleven
cross-lane gates that teach the chemistry tree.

### `ROE-LR87_Single` / `ROE-LR91-4V` — 8 and 7 configs on `fd_titanStorableConversion` T7

Split the generation ladder from the propellant fork:
- `-Kero` variants (`RP-1+LqdOxygen`) → the **kerolox spine**, not the storable node.
- Storable variants (`Aerozine50+NTO`) → stay at `fd_titanStorableConversion` (correct home), one rung each
  along `fd_gasGeneratorCeiling` T8 → `fd_gasGeneratorApex` T9.
- `AJ-7` / `AJ-7-Kero` (`Cooled*`) → **densification** node.
- `AJ-5`/`AJ-9` are identical (1053.9 kN, 285.2 s) → **one class, one node**; `AJ-3` is identical to base →
  rides the base part's node.

### `ROE-RL10Fixed` — 9 at T7 + 9 at T11

Genuine 13-rung ladder; distribute along the hydrolox spine. Pull out the non-rungs first:
`RL10A-5` (ispSL 341 vs 182 — the sea-level DC-X nozzle) and `RL10A-3-9` are **nozzle forks**;
`CECE-Methane` is a **propellant fork** → `cryo_smallScaleMethalox`. `RL10A-3-7` is padding → rides with `RL10A-3-3`.

### `SXTPWPT6` (PT6 turboprop) — 8 on `av_refinedTurboprop` T5

Eleven Kerosene configs whose thrust wanders 8.4 → 13.0 kN with no progression. This is a fixed catalog, not
a ladder: it is **one class plus `PT6A-42`** — all eleven collapse to a single uprate event, the other nine
riding along on the same node as cosmetic variants.

### Air-breathing families (`aje_j79`, `RO-R11F`, `RO-RD9B`, `aje_j75`, `SXTPWPT6`) on `met_cooledTurbine` T4

29 upgrades on one node. These are mostly **padding** (WP-6 ≡ RD-9B, WP-7 ≡ R-11F-300, AL-7F-1 dominated by
AL-7F-2, J79-GE-5C dominated, PT6A-28 dominated). Drop the padding, then distribute the ~6 real J79 rungs
along the air-breathing spine, which has 8 steps and plenty of room.

Full per-config worklist for all 107 families: **`manifest/upgrade-ladders.tsv`**.

## 8. The invariant — **SHIPPED**

`check_ladder_collapse(ladders, by, p2n, u2n)` in `tools/build_tree.py`, running after `check_tech_gates`.
It consumes the already-resolved `engine_config_ladders()` output, so it polices what the game sees rather
than what the YAML says. Configs the gate emitter cannot address individually (`CFG_NAME_SAFE` sentinels
like `(single config)`) are excluded.

**R1 / R5 / R2 now FAIL THE BUILD** (reached 2026-07-27 — the pass that got there is §9). `AXE_LADDER_SOFT=1`
downgrades them to warnings while mid-edit. R4 stays advisory: a split performance class is usually a real
placement choice, and some are forced by the base-config pin guard.

Baseline at time of writing: **160 collapsed nodes · 0 base-node tokens · 6 non-ascending rungs ·
127 padding duplicates**. **Current: 0 · 0 · 0 (+35 benign same-tier) · 13** — the migration is complete
and the gate is the standing invariant.

**The invariant earned its keep, 2026-07-29 → 07-30.** R1 regressed to 1 for three commits. Cause: the
tier-balance pass (`docs/TIER-BALANCE.md` E) fixed a dominance inversion in `ROE-RD275` by **swapping two
configs between tiers** — but `RD-275` (1746 kN) is a padding class-mate of `RD-253-Mk3`/`Mk4` (1698/1748)
and `RD-275M` (1830) is its own class, so the exchange moved a second class onto T11 and split the first
across two nodes. **A tier swap must exchange CLASSES, not configs**; a pairwise dominance comparator cannot
see a class boundary being collapsed, which is exactly the gap this gate covers. Note the build emits
`AxeTechTree.cfg` *before* the gate runs, so a red gate still ships a cfg — read the gate line, don't infer
health from a written file.

Checks:

- **error** — two config upgrades for the same part on the same node (R1)
- **error** — a config upgrade on the node holding its own base part (R5)
- **error** — a rung gated EARLIER than the rung it supersedes (R2 descent). A rung landing at the *same*
  tier on a different node is counted separately and reported as benign — two lanes can legitimately reach
  the same depth, and burying the one real descent under 31 same-tier notes would hide it.
- **warn** — a placed config classified PADDING against an already-placed sibling (R4)

It needs `manifest/engine-stats.tsv` for the config→part and propellant mapping, which the build already has
available. Ship the checker **first** — it converts this from a one-off cleanup into a standing invariant,
and it will report the true remaining count as the migration proceeds.

### 8b. Electric propulsion — a different class (2026-07-28)

**R1 exempts electric configs** (`_is_electric`). The classifier's premise is chemical: a big Isp jump is a
generational step. For an electric thruster Isp is a **dial**, not a generation — at fixed input power
`P = ½·T·v_e`, so thrust and Isp trade continuously and one machine spans a wide Isp range purely on how it
is run (VASIMR is named for it). Two electric configs of one part on one node is a **choice** of working
fluid or operating point, not a collapsed ladder. The tree had already reached this conclusion by hand once,
via `catalog: true` on a DS4G node whose comment called its marks "operating points". Detected off the
propellant list — draws `ElectricCharge` **and** an electric working fluid, which excludes electric-*pump*-fed
chemical engines like Rutherford and the Agena ISPS.

### 8c. The EP power gate — **SHIPPED**, and why it is a separate rule

`check_ep_power_spread(u2n, by, hard=True)`. **R1 asks whether two configs of one PART are distinct
decisions; this asks whether one NODE spans power classes, across parts.** For electric propulsion the
enabling breakthrough is not the thruster, it is the power chain — array → PPU → radiator. A 0.2 kW SPT-50
and a 74 kW 457M are the same physics and completely different engineering.

**Doctrine: an EP config homes at the power class it needs. The thruster is the part, the power chain is the
tech.** Input power comes from the config's own numbers (`P_jet = ½·T·g₀·Isp`, input = jet ÷ 0.63), which
reproduces published figures well across the range — NEXT 7.8 kW computed vs 6.9 real, AEPS 13.4 vs 12.5.

**Invariant: no node may grant electric configs spanning more than 5× in input power.** Bands are the
natural clusters in the data, each ~3–5× wide. Baseline **6 violations → 0**; fails the build, `AXE_LADDER_SOFT=1`
downgrades. Scope: **upgrade-granted configs only** (base configs arrive with their parts, and parts are
placed by mechanism on purpose), and **charter nodes are exempt** — integrated probe craft (Dawn, DS1) are
homed chronologically by design.

The pass that got there built the **PPU lane** — `ep_kilowattPPU` T11 → `ep_multiKilowattPPU` T12 →
`ep_fiftyKilowattPPU` T13 → `ep_hundredKilowattPPU` T14 → `ep_megawattPPU` T15 — replacing five nodes that
carried **no parts at all** and existed only as generation pegs. Working fluid stays a separate axis
expressed in **parents**: `ep_kryptonFeed` (station-keeping scale) and `ep_kryptonHighPower` (parents =
krypton **and** the 100 kW power chain), because a config carries only one `techRequired`, so the AND has to
live on the node.

**Known gap, not closed:** R2 exempts propellant **forks** from rung ordering and never checks a fork's own
internal ordering. That is how `PITV-Hydrazine-1200` (737 kW) sat on a T5 propellant node — seven tiers below
its own host part — undetected. Ordering rungs *within* each propellant branch would catch that class
directly.

## 9. Order of work — ✅ ALL DONE (2026-07-27)

> Every step below is complete. The gate reads **0 collapsed · 0 base-node · 0 descending · 14 split
> padding**, and R1/R5/R2 are hard errors. The tree grew 457 → 493 nodes over the pass (499 today, the
> difference being later unrelated work), ~40 of them added to give an uprate an honest home.

1. ~~`check_ladder_collapse` in `build_tree.py`, warnings-only~~ — **DONE** (`b722907`, `d253a6d`).
3. ~~**`microEngine` scatter**~~ — **DONE** (`c948953`). `pc_storableRcsPropellants` was *kept*, not deleted:
   its five storables are one performance class, exactly what its title names. Seven other chemistries
   moved out. Added `pc_hydrazineMonoprop` T5, `pc_cryogenicRcsFeed` T10, `pc_ascent` T13.
4. ~~**RD-100 / `met_stainlessSteel`**~~ — **DONE** (`b7a9bd3`). Added `pc_ethanol90` T2. Five configs to
   five nodes across four tiers; none merged, because all five are distinct classes.
2. ~~**R4 co-locations**~~ — **DONE.** 34 padding classes split across nodes, now down to 14. Reordered after
   3–4: those steps moved configs wholesale, so doing this first would have churned.
5. ~~Remaining propellant + nozzle forks~~ — **DONE** (`5874909`, `908c3da`, `9e19cd6`, `3c4138e`, `af5a0bc`):
   NTR working fluids, Raptor generations, ion PPU power classes, the Agena chemistry chain, the late
   cryogenic chain, the RL10 hydrolox spine, jets/krypton/storable singles.
6. ~~Rung redistribution along spines, discipline by discipline~~ — **DONE** (`8b8ebbb` homes uprates in the
   discipline that enabled them; `98d88ea`, `21dc980`, `e12b548`, `b8d67c2` fan the Blok-D/N1, jet, turbofan
   and stainless-steel families onto real mechanisms).
7. ~~Flip the checker to error and re-run the full tree build~~ — **DONE** (`ba16422`, refined by `ce5352f`
   which made class assignment placement-independent and exempted pinned R4).

### `catalog: true` — the remaining uses

A node flagged `catalog: true` is exempt from R1 and may grant many classes for one part. Under
scatter-by-default this is a narrow exception. Three nodes carry it:

| node | family | why it holds |
|---|---|---|
| `av_refinedTurboprop` | PT6, 11 marks | thrust wanders 8.4–13.0 kN in **no order at all** — no progression exists to scatter |
| `ep_nextGenGriddedIonII` | DS4G 25 kW | grid-voltage **operating points** of one experimental thruster, split from the 50 kW class on the real hardware axis |
| `ep_kilowattClassPPU` | DS4G 50 kW | as above |

**`cryo_deployableNozzleExpander` was flagged and then CUT (2026-07-27).** Calling the eight RL10C/E marks
"one decision, eight names" was wrong, and reading only thrust is what hid it — they sit at 101–108 kN, so
on that axis they really do look identical. Two other axes run straight through them:

```
nozzle expansion   ispSL  148 -> 116 -> 45 -> 24
restart life       ign     20 ->  25 -> 50 -> 260 -> 500
```

Those are different mechanisms bought at different times, so they became two lanes off the node rather
than one bucket sitting on it — six new nodes, T11→T16:

`cryo_deployableNozzleExpander` T11 → `cryo_extendedBellExpander` T12 → `cryo_highExpansionNozzle` T13 →
`cryo_extendibleNozzleDeployment` T14 → `cryo_longLifeRestartExpander` T15 → `cryo_extremeRestartExpander` T16,
with `cryo_deepThrottleExpander` T12 branching off for CECE's 10:1 throttle and 50 starts.

The lesson generalises: **`catalog: true` is only honest when NO axis orders the family.** Before reaching
for it, check every axis — thrust, both Isp figures, ignitions, burn time — not just the obvious one.

### ~~Remaining worklist~~ — ✅ **CLOSED. Re-measured 2026-08-06: the worklist is empty.**

The gate now reads:

`ladder gate: 0 collapsed node(s), 0 base-node token(s), 0 DESCENDING rung(s) (+35 benign same-tier), 13 split padding class(es)`

The long tail below was worked through; nothing on it survives. Note the metric changed shape while it
was being cleared — "non-ascending" was split into genuinely **DESCENDING** rungs (a real defect, now 0)
and **same-tier** rungs (benign, 35 of them, a rung landing on a node in the same tier as its
predecessor). Split padding fell 31 → 13 and is intentional per §10 — padding co-locates rather than
being deleted, so those classes are not work. **The gate fails the build on regression**, so this stays
closed without anyone watching it.

Kept below as the historical record of what the tail actually was (measured 2026-07-27, after the
scatter pass: 54 nodes / 87 parts / 223 configs, down from 62 / 111 / 320):

| node | T | parts | configs | | node | T | parts | configs |
|---|--:|--:|--:|---|---|--:|--:|--:|
| `cryo_reusableEngineUprating` | 13 | 5 | 13 | | `pc_zenitKerolox` | 10 | 2 | 8 |
| `fd_regenCooling` | 4 | 5 | 13 | | `av_fourthGenFighterTurbofan` | 10 | 3 | 7 |
| `fd_vacuumExpansion` | 6 | 5 | 13 | | `fd_matureKeroloxClusterUprating` | 9 | 4 | 7 |
| `fd_restartableUpperMaturation` | 9 | 4 | 12 | | `pc_ntoHypergolics` | 4 | 5 | 6 |
| `fd_engineMaturation` | 6 | 4 | 10 | | `fd_gasGeneratorCeiling` | 8 | 4 | 6 |
| `cryo_matureGasGeneratorHydrolox` | 10 | 4 | 9 | | *(+44 more, mostly 2-4 configs each)* | | | |

Nodes added by the scatter pass so far (13): `pc_ethanol90` T2, `pc_hydyne` T3, `pc_hydrazineMonoprop` T5,
`cryo_extendedBurnExpander` T8, `pc_closedCycleUpper` T9, `pc_cryogenicRcsFeed` T10, `pc_rg1` T10,
`pc_throttledClosedCycle` T10, `pc_rg1Uprating` T11, `pc_refinedMixtureClosedCycle` T11,
`pc_extendedNozzleUpper` T12, `pc_syntin` T12, `pc_restartableClosedCycle` T12, `pc_ascent` T13.

## 10. Decisions taken

- Rungs distribute along **existing** spines; no new spine nodes (R6 absorbs overflow).
- Eight new chemistry-lane nodes, each justified by ≥2 fork families (`pc_ascent` deferred at 1).
- `pc_storableRcsPropellants` is **deleted**, not slimmed — it has no residue once its contents are homed.
- Padding **co-locates** rather than being deleted (revised during implementation — see R4). AXE is
  explicitly ahistorical, so RP-1's calendar-filler configs (`LR87-AJ-5`/`-7`/`-9`) have no claim on tree
  *events* — but they keep their place in the config list, which costs nothing and loses no RO content.
- Band 1 is **reopened** at T2–T3 for the stainless/alcohol fix. The tier fence from band-2 kickoff was
  about not disturbing settled work incidentally; this is a deliberate correction to it.
