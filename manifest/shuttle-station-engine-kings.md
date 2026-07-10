# Space Shuttle & Station Era — Engine/Propulsion KING PARTS

**STATUS: AUTHORED (2026-07-06) — all 18 new nodes + 7 widened nodes are live in `tree/nodes.yaml`,
`python tools/build_tree.py` reports `design checks: clean`, 258 nodes / 20 disciplines.** This doc is now
the design record for that pass, not a pending proposal.

Two gaps found during authoring that this doc's original pass missed:
- `RFUpgrade_M-1` (hydrolox1972) is a genuine upgrade (base config is `M-1-Spec`, already the king of
  `cryo_largeHydrolox`) — NOT a duplicate like KTDU-425A/NK-33/NK-43. Added to `cryo_uprateRestartableHydrolox`
  alongside `RFUpgrade_M-1SL`.
- `RFUpgrade_RD-107-11D512`/`RD-108-11D511` (1972) and their `-P` marks (1981) were missed entirely in the
  original pass. They're later rungs of the same R-7-family production-refinement chain `fd_engineMaturation`
  (T6) already hosts (`RD-107-8D728`/`RD-108-8D727`) — appended there, no new node, no tier change.

Two build_tree.py redundant-edge warnings were also fixed by dropping transitively-implied parents:
`cryo_deepThrottleHydrolox` (dropped `cryo_expanderCycle`, already reachable via `cryo_gasGeneratorHydrolox`)
and `gnc_bipropAttitudeThrust` (dropped `gnc_smallRcsCatalog`, already reachable via `pc_storableRcsPropellants`).

---

Derived from `space-stations-shuttle-partlist.md` (the batch after `crewed-lunar-landing-partlist.md`;
RP-1 x=-1932..-1592). This pass covers **only the propulsion axis** of that partlist — every new engine
part plus every upgrade-only `RFUpgrade_*`/`RFTech-*` entry in the batch — ahead of authoring the
non-engine parts (capsules, stations, comms, science) in a later pass.

Method: real thrust/Isp/propellant/cycle pulled from `manifest/engine-stats.tsv`
(`tools/extract_engine_stats.py`), sorted by **mechanism/lineage, not RP-1's calendar bucket** (rule 1
in `docs/TREE-REVIEW.md`). For every upgrade-only entry, its host base part was traced to its *current*
`tree/nodes.yaml` home so doctrine-4 (an upgrade never shares a node with its own base part) is respected.
**Tiers below are PROPOSALS** — current tree frontier is T9-T10 (e.g. `fd_lunarSurfaceMobility` T10,
`comp_networkedAvionics` T10); this batch should land T9-T11. Nothing here is authored yet.

Legend: **KING** = the hero part. ⟳ = continues an existing node (no new node needed, just append).
🆕 = genuinely new node proposed. `disc` = discipline.

---

## Already resolved — no new work
- `RFUpgrade_KTDU-425A` — same config as the KTDU-425 **base** part (`ROE-KTDU425A`), already placed as
  the king of `fd_advancedSpacecraftPropulsion` (T8) in the band-3 tail. Duplicate reference, not a gap.
- `RFUpgrade_NK-33` / `RFUpgrade_NK-43` — same configs as the NK-33/NK-43 **base** parts, already placed
  as kings of `pc_n1ClosedCycle` (T9). Duplicate reference.
- `RFUpgrade_30x_NK-33` / `RFUpgrade_8x_NK-43` — already dispositioned `DROP-no-curated-host` (N1
  cluster configs, no curated cluster part hosts them). Nothing to place.

---

## A. Cryogenics — the reusable-hydrolox lineage (LR129 → HG-3 → SSME)

Real throughline: J-2/HM-7/M-1/YF-75 (already kinged in `cryo_gasGeneratorHydrolox` T8 /
`cryo_largeHydrolox` T9) are single-start, expendable, gas-generator engines. This batch's new parts are
the **deliberate push toward a restartable, deep-throttling, reusable hydrolox engine** — a real
three-step lineage (LR129 was a genuine 1960s NASA study for a reusable-shuttle engine; Rocketdyne's own
HG-3 uprated-J2 study fed directly into the actual SSME design; RD-57/KVD-1 are the Soviet parallel
attempts at restart-capable hydrolox for their own reusability ambitions).

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Deep-Throttle Restartable Hydrolox** | `ROE-LR129` (1049 kN, Isp 435s), `ROE-RD57` (392 kN, Isp 457s), `RO_KVD1` (RD-56 base, 70 kN, Isp 448s) | — | **T9** (`cryo_gasGeneratorHydrolox` × `cryo_expanderCycle`) | Crossover: scales gas-generator thrust + borrows expander-cycle restart know-how. Real SSME ancestor study (LR129, 1966 USAF/NASA). **RESEARCHED:** KVD-1/RD-56 confirmed **fuel-rich staged combustion**, not expander (that's RD-0146, a different Kosberg engine, decades later) — RP-1's own bucketing was right; it belongs here with LR129/RD-57, not with the RL-10 chain. |
| 🆕 **Uprated Restartable Hydrolox (HG-3)** | `ROE-HG3` (1401 kN, Isp 451s) | `RFUpgrade_HM-7B`, `RFUpgrade_J-2S`, `RFUpgrade_YF-75D`, `RFUpgrade_M-1SL` (bases in `cryo_gasGeneratorHydrolox`/`cryo_largeHydrolox`), `RFUpgrade_HG-3-SL`/`RFUpgrade_KVD-1`/`RFUpgrade_LR129-P-1` (bases = above node) | **T10** (parent = Deep-Throttle Restartable Hydrolox) | HG-3 = Rocketdyne's real J-2-derived SSME precursor study. Catches the 1972-76 gas-generator engines "maturing in the shadow of the reusable program." |
| 🆕 **Reusable Staged-Combustion Hydrolox (SSME)** | `ROE-RS25` — **the headline part of the whole era** (2090 kN, Isp 455s, 0 rated ignition limit i.e. designed for reuse) | `RFUpgrade_HG-3A`, `RFUpgrade_HG-3A-SL`, `RFUpgrade_LR129-P-2` | **T11** (parent = Uprated Restartable Hydrolox) | The Shuttle main engine. Deepest tier of this whole pass — the culmination of a real 3-step program. |
| ⟳ **append directly to `cryo_refinedExpander`** | — | `RFUpgrade_RL10A-3-3A`, `RFUpgrade_RL10A-3-9` | **T7** (existing node, no change) | This node's own comment says it's a "thin stub... fills out as the long RL-10 chain arrives in later batches" — this IS that batch. Just append to its upgrades list. No new node. |

## B. PropellantChemistry — storable ORSC thrust ceiling (RD-270)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Storable Staged-Combustion Thrust Ceiling** | `ROE-RD270` (6713 kN — **the largest hypergolic engine ever built/tested**, real UR-700 engine) | — | **T10** (parent = `pc_refinedStorableORSC` T9) | Sibling of `fd_gasGeneratorApex`/`cryo_largeHydrolox`: every propellant family gets its "pushed past sane thrust for one more chemistry-ceiling record" dead-end. RD-270 never flew — same "drawn but never poured" flavor as AJ-260. |
| 🆕 **Re-Fuelled Ceiling Variants** (thin, upgrades-only) | *(none — doctrine-4 forces RD-270's own later configs off its own node)* | `RFUpgrade_RD-270M-8D420M` (exotic PB-1+HTP config), `RFUpgrade_RD-116-8D420K` (RG-1+LOX re-fuel config) | **T11**, parent = Storable Staged-Combustion Thrust Ceiling | Both are what-if re-fuelings of the same RD-270 hardware, not separate engines — a thin single-purpose node next to the SSME/NERVA-I capstones. |

## C. PropellantChemistry — kerolox ORSC matures (Zenit)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Operational Oxidiser-Rich Kerolox** | `ROE-RD120` (834 kN, Isp 350s) | `ROE-RD8` (20 kN, steering verniers) ride-along | **T10** (parent = `pc_n1ClosedCycle` T9) | RD-120/RD-8 = the real Zenit upper stage. Where NK-33/43 (N1) never flew, this is oxidiser-rich staged combustion **finally operational** — nice narrative contrast at the next tier. |

## D. PropellantChemistry — storable ORSC refinement (no new king, pure catch)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Further-Refined Storable Staged Combustion** | *(none — pure doctrine-4 collector, same shape as `pc_refinedStorableORSC` itself)* | `RFUpgrade_RD-0210-Mk2`, `RFUpgrade_RD-0212-Mk2`, `RFUpgrade_RD-0213-Mk2`, `RFUpgrade_RD-253-Mk3` | **T10** (parent = `pc_refinedStorableORSC` T9) | Mk1→Mk2 already lives at T9; this is the Mk2→Mk3/Mk2 next rung. Straightforward same-shape continuation. |

## E. PropellantChemistry — solids (four separate, real lineages — do not merge)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| ⟳ **Castor4 → append directly** | `ROE-Castor4` (460 kN) | — | append to existing `pc_strapOnMarkII` (**T7**, only 2/6 parts used) | Direct next mark of Castor1→Castor2, same strap-on lineage. No new node needed. |
| 🆕 **Third-Generation Scout Solid** | `ROE-Algol3`/`ROE-Algol3_Inline` (530 kN) | — | **T8**, thin node, parent = `pc_scoutMarkII` (T7, at 6/6 cap already) | Direct next mark of Algol I→II; needs its own node only because the parent is at the part-count cap, not because it's a different mechanism. |
| 🆕 **Human-Rated Segmented Solid Booster** | `RO-RSRM`/`restock-srb-anvil-1` (14,819 kN — **the largest solid ever flown**) | — | **T9** (parent = `pc_largeSegmentedBooster` T8) | The Shuttle SRB. Deliberate contrast to `pc_largeSegmentedBooster`'s AJ-260 ("drawn but never poured") — this one is flight-proven and crew-rated. **Tier held at T9, not pushed deeper**, even though it's dramatic: mechanically it's a one-step scale-up-and-human-rate of already-mastered segmented casting, not a multi-generation program like SSME/NERVA-I — the tier reflects real lineage-depth, not drama. Flag if you'd rather weight it to match SSME/NERVA-I's T11. |
| 🆕 **Extended-Range Solid Kick Motors II** | `ROE-Star48B` (78 kN, Isp 292s — still flown today, e.g. real-world upper-stage kicks) | `ROE-Star37FM`, `ROE-Antares3`/`_Inline` (Star-31) ride along | **T9** (parent = `pc_apogeeKickCatalog` T8) | Same shape as the existing `pc_apogeeKickStage`→`pc_apogeeKickCatalog` size-extension pattern, one generation later. |
| 🆕 **Solid-Fuel Upper Stage** ✅ (confirmed) | `ius_bottom` (Orbus-21, 268 kN) + `ius_top` (Orbus-6E, 114 kN) — **paired 2-stage king** | — | **T9** (crossover parent = `pc_apogeeKickCatalog` × `pc_largeSegmentedBooster`, both T8) | Real IUS: a genuinely bigger breakthrough than a kick motor — a complete solid stage that replaces a liquid upper stage for GTO/escape work from the Shuttle's bay (Magellan/Galileo/Ulysses real payloads). Confirmed as its own breakthrough, not folded into the kick-motor chain. |

## F. FluidDynamics — mature kerolox clusters + restartable storables (no new kings, pure catches)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| ⟳ **append to `fd_gasGeneratorApex`** (revised — no new node) | — | `RFUpgrade_E-1-575k`, `RFUpgrade_E-1-Upgrade2`, `RFUpgrade_E-1A_KS`, `RFUpgrade_H-1-205K`, `RFUpgrade_H-1-250K`, `RFUpgrade_H-2-300K`, `RFUpgrade_RS-27`, plus `RFUpgrade_F-1A` | existing **T9** trap node (no tier change) | Better fit than a new node: `fd_gasGeneratorApex`'s whole point is "marginal gas-generator-kerolox uprates going nowhere while ORSC/hydrolox walk past" — E-1/H-1/RS-27's late marks are exactly that, same family as F-1's own trap. Just widen this node's existing upgrade list; F-1A joins the same list. |
| 🆕 **Restartable Storable Upper Maturation** | *(none — catch node)* | `RFUpgrade_AJ10-118F`, `RFUpgrade_Model8096-39`, `RFUpgrade_Model8096A`, `RFUpgrade_Model8096L`, `RFUpgrade_Model8096B`, `RFUpgrade_AJ10-138A` | **T9** (parent = `fd_advancedSpacecraftPropulsion` T8) | Bases (Agena/AJ10Adv) live in `fd_restartableUpper` (T4); parenting one tier above the *more recent* descendant (`fd_advancedSpacecraftPropulsion`, T8, KTDU-425) keeps it consistent with "next tier after this lineage's last batch," matching every other lane in this pass. |

## G. NuclearEngineering — split NTR from Nuclear Pulse (Orion)

RP-1 buckets NRX/Phoebus-1B/NERVA-XE **together with the Orion pulse-unit drives** in its own
`earlyNuclearPropulsion` node purely by calendar year — but these are mechanically unrelated (reactor
heats propellant vs. external nuclear detonations push a pusher plate). Per the standing TODO
([[rp-axe-stockish-project-orion]]), **split them**:

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Full-Scale Nuclear Thermal Testing** | `NERVA_NRX` (243 kN, Isp 848s), `Phoebus1N50` (299 kN, Isp 828s), `ROE-NERVAXE` (239 kN, Isp 850s) | — | **T10** (parent = `nuc_nuclearThermalRocket` T9, KIWI) | Real lineage: KIWI (already kinged) → NRX → Phoebus-1 → NERVA-XE, the actual NASA/AEC ground-test progression toward a flight engine. |
| 🆕 **Flight-Rated Nuclear Thermal Engine** | `ROE-NERVA` (NERVA I, 334 kN, Isp 900s) | `PEWEE100` (111 kN, Isp 901s — highest-Isp test article), `Phoebus2N100` (913 kN, Isp 813s — most powerful test), `RO-KA-PrincetonLNTR` (39 kN, Isp 1350s — LEU/what-if compact design) ride along | **T11** (parent = Full-Scale Nuclear Thermal Testing) | NERVA I = the design NASA actually intended to fly (cancelled 1972 — thematically fitting for this exact era). Pewee/Phoebus-2A = the biggest/most efficient ground tests informing it. Princeton LNTR later continues into the already-existing `improvedNuclearPropulsion` node (out of this batch's scope, x=-1422). Ties SSME for the deepest tier in this pass — both are real flight-design capstones of multi-step programs. |
| 🆕 **Ablative Pusher Plate & Shock Absorption** ✅ (new, per your go-ahead) | *(no part — pure structural/mechanical enabler)* | — | **T9**, discipline **StructuresMechanisms**, parent = `str_stationStructures` (T8) | The real enabling mechanism Orion needs and nothing else in the tree provides: a thick ablative steel plate plus a two-stage shock-absorber system (plate-mounted primary + vehicle-mounted secondary) that turns a survivable-to-the-plate nuclear detonation into a survivable-to-the-crew acceleration pulse. No curated part represents it directly — it's a pure enabler node (like `cryo_hydrogen`'s empty commitment gate), there to be a real prerequisite rather than asserted flavor text. |
| 🆕 **Nuclear Pulse Propulsion (Project Orion)** | `RO-fftorion8`/`RO-fftorion12`/`fft-fission-orion-5-1` (external pulse units, staged 8/10/12m drives) | — | **T10** (crossover parents = `nuc_fissionReactor` (T8) × **Ablative Pusher Plate & Shock Absorption** (T9, above)) | **Per standing TODO:** Orion gets its own node, explicitly NOT folded into the NTR ladder — completely different physics (external detonation + pusher plate vs internal reactor heating). Propellant-tank ride-along: `fft-fueltank-pulseunits-5-1/2/3` (pulse-unit magazines, from `materialsScienceSpaceStation` non-engine group) belongs with this king once authored. What-if/fun curation per [[rp-axe-fun-over-history]] — Orion never flew, this is deliberate sim-not-documentary curation. |

## H. ElectricalPower — brand-new lane: electric propulsion

**Nothing in the tree today uses ion/Hall-effect thrusters** — this batch is the FIRST placement of the
entire electric-propulsion family. Prefix **`ep_`** confirmed (avoids collision with the existing `elec_`
prefix used for both ElectricalPower diodes/PV *and* Microelectronics transistors/ICs).

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Hall-Effect Ion Acceleration** (`ep_hallEffectThruster`) | `RO-SPT50` (14 mN, Isp 860s), `RO-SPT60`/`RO-ionSPT60` (30 mN, Isp 1185s) | — | **T9** (parent = `elec_siliconPV` × `nuc_isotopePowerII` — needs continuous kW-class power, crossover) | Genuinely tiny thrust, huge Isp — a real different-axis breakthrough (station-keeping/deep-throttle-free cruise, not launch thrust). Rewires "electrical power" into "propulsion" for the first time; a good discipline-crossing moment worth flavor emphasis. |
| 🆕 **Higher-Power Hall Thrusters** (`ep_higherPowerHallThruster`) | `RO-SPT70` (39 mN, Isp 1470s) | — | **T10** (parent = above) | Direct next mark, same mechanism, scaled up. |

## I. GuidanceControl — bipropellant attitude/apogee thrusters (new tier above monoprop RCS)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Bipropellant Attitude & Apogee Thrust** | `ROE-HiPAT` (R-4D, 0.5 kN, Isp 322s), `ROE-R40B`/`ca_lahar` (R-40, 3.9-4.0 kN, Isp 281-293s) | `ca_trident` (Bi-Propellant Apogee Engine, 1.3 kN, Isp 321s) ride-along | **T9** (parent = `gnc_smallRcsCatalog` × `pc_storableRcsPropellants` T8, crossover) | Real step up from monoprop/cold-gas RCS: MMH+MON3/NTO bipropellant combustion in a thruster-class engine — genuinely higher Isp (~320s vs ~280s) than the existing RCS catalog nodes. R-4D is the real, still-flying OMS/RCS workhorse (Apollo, many modern spacecraft). Decided: fold the finer configs (R-4D-15/-15DM, R-40A-NTO/R-40B/-NTO) directly onto this same node rather than spinning up a T10 continuation — the performance deltas between them are thin enough not to earn a separate tier. |

## J. AirBreathing — second-generation turbofans

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Second-Generation Bypass Turbofans** | `SXTKe90TurboJet` (D-18T, 230 kN), `aje_al31` (AL-31F, 122 kN) | `RFUpgrade_CF6-50E2`, `RFUpgrade_CF6-80A`, `RFUpgrade_CF34-1A` (bases in `av_highBypassTurbofan` T7), `RFUpgrade_GE4-J6H`, `RFUpgrade_J79-IAI-J1E`, `RFUpgrade_WP-13` (bases in `av_variableStator`/`av_afterburner` T4) | **T9** (parent = `av_advancedJetEngines` T8) | D-18T/AL-31F are new base-part kings, a genuine next generation past the CF6/JetEngine/F100 family already homed at T7-T8. |
| ⟳ **append to `av_refinedTurboprop`** | — | `RFUpgrade_PT6A-21` | existing T5 node | Same PT6 lineage as the 5 marks already there (11AG/15AG/20A/34/42/135) — just a config that RP-1 slotted at a later calendar year; no real generation gap. |
| ⟳ **append to `av_advancedJetEngines`** | — | `RFUpgrade_WP-7BM` | existing T8 node | Same WP-7 base as `RFUpgrade_WP-7B` already there. |

---

## Resolved (2026-07-06)
1. **KVD-1's cycle** — researched: fuel-rich staged combustion, confirmed. Stays grouped with LR129/RD-57.
2. **Orion's pusher-plate parent** — new enabler node created: `Ablative Pusher Plate & Shock Absorption`
   (StructuresMechanisms, T9, no part). Orion's propulsion node crosses it with `nuc_fissionReactor`.
3. **IUS naming** — confirmed as its own "Solid-Fuel Upper Stage" breakthrough, not folded into the kick-motor chain.
4. **`ep_` prefix** — confirmed for the new electric-propulsion lane.
5. **Tier pass** — done below; every node re-checked against its real parent(s) and against every other
   node proposed in this same pass, so parallel single-step lanes land together and multi-step lineages
   (hydrolox reusability, NTR) spread out to reflect real generational depth.

## Final tier map (for authoring into `tree/nodes.yaml`)

| Tier | Discipline | Node (proposed id) | Parent(s) |
|---|---|---|---|
| T7 (existing, append only) | Cryogenics | `cryo_refinedExpander` | — |
| T7 (existing, append only) | PropellantChemistry | `pc_strapOnMarkII` | — |
| T8 (existing, append only) | FluidDynamics | `av_refinedTurboprop`, `av_advancedJetEngines` | — |
| T8 | PropellantChemistry | 🆕 `pc_scoutMarkIII` (Algol III) | `pc_scoutMarkII` |
| T9 (existing, append only) | FluidDynamics | `fd_gasGeneratorApex` (widened) | — |
| T9 | Cryogenics | 🆕 `cryo_deepThrottleHydrolox` (LR129/RD-57/KVD-1) | `cryo_gasGeneratorHydrolox` × `cryo_expanderCycle` |
| T9 | PropellantChemistry | 🆕 `pc_shuttleSRB` (RSRM) | `pc_largeSegmentedBooster` |
| T9 | PropellantChemistry | 🆕 `pc_apogeeKickCatalogII` (Star-48B/37FM/Antares-3) | `pc_apogeeKickCatalog` |
| T9 | PropellantChemistry | 🆕 `pc_solidUpperStage` (IUS) | `pc_apogeeKickCatalog` × `pc_largeSegmentedBooster` |
| T9 | FluidDynamics | 🆕 `fd_restartableUpperMaturation` (AJ10/Agena catch) | `fd_advancedSpacecraftPropulsion` |
| T9 | StructuresMechanisms | 🆕 `str_pusherPlate` (Orion enabler, no part) | `str_stationStructures` |
| T9 | ElectricalPower | 🆕 `ep_hallEffectThruster` (SPT-50/60) | `elec_siliconPV` × `nuc_isotopePowerII` |
| T9 | GuidanceControl | 🆕 `gnc_bipropAttitudeThrust` (R-4D/R-40/trident) | `gnc_smallRcsCatalog` × `pc_storableRcsPropellants` |
| T9 | AirBreathing | 🆕 `av_secondGenTurbofan` (D-18T/AL-31F) | `av_advancedJetEngines` |
| T10 | Cryogenics | 🆕 `cryo_uprateRestartableHydrolox` (HG-3) | `cryo_deepThrottleHydrolox` |
| T10 | PropellantChemistry | 🆕 `pc_stagedCombustionCeiling` (RD-270) | `pc_refinedStorableORSC` |
| T10 | PropellantChemistry | 🆕 `pc_zenitKerolox` (RD-120/RD-8) | `pc_n1ClosedCycle` |
| T10 | PropellantChemistry | 🆕 `pc_refinedStorableORSCII` (Mk2/Mk3 catch) | `pc_refinedStorableORSC` |
| T10 | NuclearEngineering | 🆕 `nuc_fullScaleNTRTesting` (NRX/Phoebus-1B/NERVA-XE) | `nuc_nuclearThermalRocket` |
| T10 | NuclearEngineering | 🆕 `nuc_pulsePropulsion` (Orion) | `nuc_fissionReactor` × `str_pusherPlate` |
| T10 | ElectricalPower | 🆕 `ep_higherPowerHallThruster` (SPT-70) | `ep_hallEffectThruster` |
| T11 | Cryogenics | 🆕 `cryo_ssme` (RS-25 — **the era's title engine**) | `cryo_uprateRestartableHydrolox` |
| T11 | PropellantChemistry | 🆕 `pc_rd270Variants` (thin, upgrades-only) | `pc_stagedCombustionCeiling` |
| T11 | NuclearEngineering | 🆕 `nuc_flightRatedNTR` (NERVA-I — **ties SSME for deepest tier**) | `nuc_fullScaleNTRTesting` |

**18 new nodes total** (12 at T9, 6 split across T10-T11) + 7 existing nodes widened with no tier change
(`cryo_refinedExpander`, `pc_strapOnMarkII`, `av_refinedTurboprop`, `av_advancedJetEngines`,
`fd_gasGeneratorApex`, plus the two duplicate-reference upgrades needing no action at all).

Ready to author into `tree/nodes.yaml` on your go-ahead.
