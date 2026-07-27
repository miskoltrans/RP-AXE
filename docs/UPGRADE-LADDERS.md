# Upgrade Ladders — engine config placement doctrine

Status: design settled 2026-07-27. **Step 1 (the build gate) shipped; steps 2-7 outstanding.**
Live baseline: run `python tools/build_tree.py` and read the `ladder gate:` line.
Worklist data: `manifest/upgrade-ladders.tsv` (448 classified rows, regenerate with the classifier in `tools/`)

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
- **R6 — merge before inventing.** If a family has more rungs than its spine has steps, merge the
  smallest-delta adjacent pairs until it fits. Do not invent spine nodes to absorb rungs.

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
like `(single config)`) are excluded. Warnings-only today; `AXE_TREE_STRICT=1` makes R1 fatal.

Baseline at time of writing: **160 collapsed nodes · 0 base-node tokens · 6 non-ascending rungs ·
127 padding duplicates**. Drive these to zero, then flip R1 to error.

Checks:

- **error** — two config upgrades for the same part on the same node (R1)
- **error** — a config upgrade on the node holding its own base part (R5)
- **warn** — rungs of a family not at strictly increasing tiers (R2)
- **warn** — a placed config classified PADDING against an already-placed sibling (R4)

It needs `manifest/engine-stats.tsv` for the config→part and propellant mapping, which the build already has
available. Ship the checker **first** — it converts this from a one-off cleanup into a standing invariant,
and it will report the true remaining count as the migration proceeds.

## 9. Order of work

1. ~~`check_ladder_collapse` in `build_tree.py`, warnings-only~~ — **DONE** (`b722907`, `d253a6d`).
3. ~~**`microEngine` scatter**~~ — **DONE** (`c948953`). `pc_storableRcsPropellants` was *kept*, not deleted:
   its five storables are one performance class, exactly what its title names. Seven other chemistries
   moved out. Added `pc_hydrazineMonoprop` T5, `pc_cryogenicRcsFeed` T10, `pc_ascent` T13.
4. ~~**RD-100 / `met_stainlessSteel`**~~ — **DONE** (`b7a9bd3`). Added `pc_ethanol90` T2. Five configs to
   five nodes across four tiers; none merged, because all five are distinct classes.
2. **R4 co-locations** — 34 padding classes split across nodes. Reordered after 3–4: those steps moved
   configs wholesale, so doing this first would have churned. *(outstanding)*
5. Remaining propellant + nozzle forks — mechanical once the fork targets exist. *(outstanding)*
6. Rung redistribution along spines, discipline by discipline. *(outstanding)*
7. Flip the checker to error and re-run the full tree build. *(outstanding)*

### Remaining worklist (measured 2026-07-27, after step 4)

`ladder gate: 137 collapsed · 0 base-node · 6 non-ascending · 34 split padding`

That is **62 distinct nodes** across 111 parts and 320 configs — the 137 counts (part, node) pairs, and
many parts share a config set. The work is concentrated: the top 20 nodes carry 210 of the 320 configs.

| node | T | parts | configs | | node | T | parts | configs |
|---|--:|--:|--:|---|---|--:|--:|--:|
| `met_cooledTurbine` | 4 | 8 | 24 | | `cryo_refinedExpander` | 7 | 2 | 11 |
| `fd_regenCooling` | 4 | 6 | 17 | | `fd_engineMaturation` | 6 | 4 | 10 |
| `fd_titanStorableConversion` | 7 | 5 | 15 | | `cryo_matureGasGeneratorHydrolox` | 10 | 4 | 9 |
| `pc_n1ClosedCycle` | 9 | 4 | 14 | | `cryo_deployableNozzleExpander` | 11 | 1 | 9 |
| `met_stainlessSteel` | 2 | 5 | 13 | | `av_refinedTurboprop` | 5 | 1 | 8 |
| `cryo_reusableEngineUprating` | 13 | 5 | 13 | | `av_fourthGenFighterTurbofan` | 10 | 3 | 7 |
| `fd_vacuumExpansion` | 6 | 5 | 13 | | `fd_matureKeroloxClusterUprating` | 9 | 4 | 7 |
| `fd_restartableUpperMaturation` | 9 | 4 | 12 | | `pc_ntoHypergolics` | 4 | 5 | 6 |

`met_stainlessSteel` still appears: its RD-100 family is resolved, but the five *other* families parked on
it (Aerobee, A-7, XLR11, ORM-65, Meteo) are step-5/6 work.

## 10. Decisions taken

- Rungs distribute along **existing** spines; no new spine nodes (R6 absorbs overflow).
- Eight new chemistry-lane nodes, each justified by ≥2 fork families (`pc_ascent` deferred at 1).
- `pc_storableRcsPropellants` is **deleted**, not slimmed — it has no residue once its contents are homed.
- Padding **co-locates** rather than being deleted (revised during implementation — see R4). AXE is
  explicitly ahistorical, so RP-1's calendar-filler configs (`LR87-AJ-5`/`-7`/`-9`) have no claim on tree
  *events* — but they keep their place in the config list, which costs nothing and loses no RO content.
- Band 1 is **reopened** at T2–T3 for the stainless/alcohol fix. The tier fence from band-2 kickoff was
  about not disturbing settled work incidentally; this is a deliberate correction to it.
