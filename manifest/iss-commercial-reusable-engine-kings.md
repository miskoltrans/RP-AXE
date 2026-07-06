# ISS Completion -> Commercial/Reusable Era — Engine/Propulsion KING PARTS

**STATUS: PROPOSAL — not yet authored.** Derived from `iss-commercial-reusable-partlist.md` (RP-1
x=-1082..-402, real years ~2004-2028: the batch after `modular-stations-rovers`). This pass covers
**only the propulsion axis** — every new engine base part plus every upgrade-only `RFUpgrade_*` entry
whose tech node falls in this batch — ahead of authoring the non-engine parts (habitats, rovers, comms,
science, capsule structure) in a later pass, exactly as the two prior engine-only passes were staged.

This is the **first of the two remaining not-started partlists** (the second, `colonization-scaffold`,
is RP-1's almost-empty post-2051 scaffold — pure AXE gap-fill authoring, a separate later thread).

Method: same as the prior two passes — real thrust/Isp/propellant/cycle pulled from
`manifest/engine-stats.tsv`, doctrine-4 upgrade catches traced via `manifest/upgrades-curated.tsv`'s
`reason` field (which names the curated base part each `RFUpgrade_*` config belongs to) against each
base's *current* `tree/nodes.yaml` home. Grouped by **mechanism/lineage, not RP-1's calendar bucket**.

**Current propulsion frontier going in: Cryogenics/PropellantChemistry/ElectricalPower T12-T13,
NuclearEngineering T13, FluidDynamics/GuidanceControl T11.** This era is one full generation later
(matches how modular-stations-rovers landed one band past shuttle-station's T9-T11) — expect **T11-T15**.
**Tiers below are PROPOSALS** — the design value is the mechanism groupings + kings + lineage; tier
numbers are freely adjustable.

Legend: **KING** = the hero part. ⟳ = continues/widens an existing node (append only). 🆕 = new node.

---

## Already resolved — no new work
- `RAPIER` (stock CR-7 R.A.P.I.E.R.) — **"(no RealFuels config path)"** in `engine-stats.tsv`: RO never
  gives it a real engine config at all (unlike every other curated engine). Nothing to place; parked.
- `cryoengine-eagle-1` — same config family as `ROE-RaptorVac` (both "Raptor-Vacuum", identical
  thrust/Isp/propellant). Duplicate mod reference, not a second part; one Raptor-Vacuum king.
- `ROC-OrionESM`/`ROC-OrionLAS`/`ROC-OrionCover1/2/3` — RP-1 tags these `commercialCapsules` blank at the
  base-config level but `partTech=commercialCapsules` confirms the real node (ground-truthed the same way
  the AJ10-190 gap was, via `partTech` instead of a blank `techRequired`). Not a placement mystery.
- Two Tantares parts flagged by the same full-tree engine sweep (`aquarius_parachute_s0p5_1` LK-700
  parachute, `alnair_les_s0_2` TKS LES) are **out of scope here** — they're part of the entire
  Tantares Mir/LK-700/TKS value-add (48 curated parts, docs/PARTLIST.md keep-list) that has **no RP-1 tech
  placement at all** (RP-1 cuts all of Tantares) and so never appears in any x-position partlist extract.
  Separate known gap, not touched by this pass.

## Doctrine-4 catches routed to EXISTING nodes (no new node, just widen)
Traced via `upgrades-curated.tsv`'s `reason` field (names the curated base each config belongs to):

| Upgrade(s) | Base (current home) |
|---|---|
| `RFUpgrade_457M-V2` | `RO-457M` @ `ep_highPowerHall` (T12) |
| `RFUpgrade_SPT-100D`, `SPT-100M` | `RO-SPT100` @ `ep_operationalHall` (T11) |
| `RFUpgrade_SPT-140D` | `RO-SPT140` @ `ep_operationalHall` (T11) |
| `RFUpgrade_SPT-70M`, `SPT-70MK` | `RO-SPT70` @ `ep_higherPowerHallThruster` (T10) |
| `RFUpgrade_RS-18` | `ROE-LMAE`/`ROC-LEMLMAEBDB` @ `fd_deepThrottleLanding` (T9) |
| `RFUpgrade_LE-5B-2`, `LE-5B-3` | `ROE-LE5` @ `cryo_operationalHydroloxUpper` (T11) |
| `RFUpgrade_AJ26-58`, `AJ26-59`, `AJ26-62` | `ROE-NK33` @ `pc_n1ClosedCycle` (T9) |
| `RFUpgrade_AJ26-60` | `ROE-NK43` @ `pc_n1ClosedCycle` (T9) |
| `RFUpgrade_RD-0146D` | `ROE-RD0146` @ `cryo_deployableNozzleExpander` (T11) |
| `RFUpgrade_RD-171M` | `ROE-RD170` @ `pc_multiChamberORSC` (T11) |
| `RFUpgrade_RD-277M-14D16M` | `ROE-RD254` @ `pc_protonStagedCombustion` (T8) |
| `RFUpgrade_RD-275M` | `ROE-RD275` @ `pc_protonStagedCombustion` (T8) |
| `RFUpgrade_RD-58M-CCN` | `ROE-RD58` @ `pc_n1ClosedCycle` (T9) |
| `RFUpgrade_CECE-High`, `RL10C-2`, `RL10C-2-1` | `ROE-RL10B2` @ `cryo_deployableNozzleExpander` (T11) |
| `RFUpgrade_CECE-Base`, `CECE-Methane`, `RL10C-1`, `RL10C-1-1`, `RL10C-1A` | `ROE-RL10Fixed` (base @ `cryo_expanderCycle` T4) — routed to the *downstream* node continuing this lineage, `cryo_deployableNozzleExpander` (T11), same "idle-then-leap" precedent already accepted for the RL-10 chain |
| `RFUpgrade_RS-68A`, `RS-68B`, `RS-68K`, `RS-800` | `ROE-RS68` @ `cryo_boosterGasGenHydrolox` (T11) |
| `RFUpgrade_STAR-37FMV` | `ROE-Star37FM` @ `pc_apogeeKickCatalogII` (T9) |
| `RFUpgrade_CE-7.5` | `RO_KVD1` @ `cryo_deepThrottleHydrolox` (T9) |
| `RFUpgrade_YF-100K` | `YF100_Engine_S` @ `pc_multiChamberORSC` (T11) |
| `RFUpgrade_PITV-Ammonia-1200`, `PITV-Hydrazine-1200` | `pit-125` @ `ep_pulsedInductive` (T12) |
| `RFUpgrade_Aestus-II`, `AestusMod` | `restock-engine-125-pug` @ `fd_multiRestartStorableUpper` (T11) |

**Dormant, no host in our curated set (T3-audited `KEEP-engine-dormant`, no action):** `RFUpgrade_ATCRE-BlockII`,
`Aeon1-V`, `Engine-2Vac`, `Kestrel-2`, `Merlin1B`, `Merlin1BVac`, `RD-0126A`, `RD-0162A`, `RS-76A`,
`TR-312-100MN`, `TR-312-100YN`, `TRITON`, `Vikas-1+`, `Vikas-2`, `Vikas-2B`.

## Doctrine-4 catches routed to NEW nodes below
`ROE-Merlin1C`/`1CV`/`1D`/`1D+`/`1D++`/`1DV`/`1DV+` upgrade configs, `RFUpgrade_Vinci-180` (RL60/Vinci),
`RFUpgrade_AEPS`/`X3-HV`/`X3-HV-K`/`DS4G-25-hi`/`-25-mid`/`-50-hi`/`-50-low` (electric propulsion),
`RFUpgrade_VX-200SS-Kr`/`VF-200-Kr` (VASIMR), `RFUpgrade_NuPIT-7000` (NuPIT), `RFUpgrade_RD-181`/`RD-191`/
`RD-193` (RD-191) — each listed under its new king below.

---

## A. Cryogenics — hydrolox goes cheap-and-simple (the anti-staged-combustion generation)

| Breakthrough | KING(s) | tier (parent) | notes |
|---|---|---|---|
| 🆕 **Combustion Tap-Off Cycle** `cryo_combustionTapOff` | `ROE-BE3` (BE-3PM, 511 kN, Isp 360s) | **T12** (`cryo_boosterGasGenHydrolox` T11) | Blue Origin's real third hydrolox cycle — tap hot gas *off the main chamber wall* to spin the turbopump, then dump it overboard, skipping a separate gas-generator combustor entirely. Simpler and cheaper than gas-generator, sits beside it in the same "operational, not exotic" family as RS-68/Vulcain 2. |
| 🆕 **Expander-Bleed Cycle at Booster Scale** `cryo_expanderBoosterScale` | `cryoengine-fuji-1` (LE-9, **1471 kN** — real H3 core engine, Isp 425s) | **T13** (`cryo_deployableNozzleExpander` T11) | Expander cycles were always small-upper-stage-only (limited by cooling-jacket heat-exchange area) until the expander-*bleed* variant vented a little gas overboard for extra margin — breaking the thrust ceiling all the way up to core-stage scale. A real, recent (2020s) generational leap on the RL-10 family tree. |
| 🆕 **Higher-Thrust Closed Expander** `cryo_highThrustExpander` | `cryoengine-pavonis-1`/`cryoengine-tharsis-1` (RL60/Vinci, 180/360 kN, Isp 465s — two parallel American/European programs converging on the same idea) | **T12** (`cryo_deployableNozzleExpander` T11) | Direct next mark of the closed-expander RL-10 lineage at roughly triple its thrust class — still no bleed, still the cleanest cycle, just bigger turbopumps and a bigger chamber. |
| ⟳ **widen `cryo_methaloxStagedCombustion`** (T12) | += `ROE-BE4` (BE-4, 2647 kN, Isp 341s — New Glenn/Vulcan) | existing T12, no change | BE-4 *is* oxidiser-rich staged combustion on methane — the exact mechanism this node's title already names. Joins `rmm_arenysaurus` (LRBE) as the second methalox-ORSC king; the node's own flavor text ("the seed of a lane a later era will grow into") is now realized. |
| 🆕 **Full-Flow Staged-Combustion Methalox** `cryo_fullFlowMethalox` | `ROE-Raptor`/`ROE-RaptorVac` (2746/3001 kN, Isp 350/380s — Starship) | **T13** (`cryo_methaloxStagedCombustion` T12, widened above) | The thermodynamic endpoint: burn *both* turbopump drive-gas streams through combustion (fuel-rich preburner **and** oxidiser-rich preburner), nothing dumped overboard. No RP-1 tech gate exists for this (too recent for RP-1's own tree; ground-truthed via `partTech=stagedCombustion2019`, same technique as the AJ10-190/Orion-capsule gaps) — it's the real capstone one step past BE-4. |
| 🆕 **Small-Scale Methalox Upper Stage** `cryo_smallScaleMethalox` | `cryoengine-buzzard-1` (M10, 98 kN, Isp 362s — Rocket Lab Neutron upper stage) | **T12** (`pc_zenitKerolox` T10) | A simpler, non-staged-combustion methalox debut at small scale — sibling to the ORSC methalox lane rather than part of it (different, plainer cycle), the "small end" of the same new-fuel story `cryo_methaloxStagedCombustion` tells at booster scale. |

## B. FluidDynamics — gas-generator kerolox reborn for reusability (Merlin) + a genuinely new feed mechanism (Rutherford)

| Breakthrough | KING(s) | tier (parent) | notes |
|---|---|---|---|
| 🆕 **Reusable Gas-Generator Kerolox** `fd_reusableGasGenKerolox` | `ROE-Merlin1A` + `ROE-Merlin1C` (369/483 kN, Isp 288/305s) | **T12** (`fd_terminalGasGenKerolox` T11) | The gas-generator kerolox lineage's real modern twist: after the tree's own `fd_gasGeneratorApex`/`fd_terminalGasGenKerolox` narrative of "diminishing returns while staged combustion walks past," Merlin proves the *opposite* — plain gas-generator kerolox, kept deliberately simple, wins on cost and reusability instead of chasing Isp. `ROE-Merlin1CV` (vacuum-optimized 1C) rides along as a nozzle variant, not a new generation. |
| 🆕 **Densified-Propellant Kerolox Uprating** `fd_densifiedPropellantKerolox` | `ROE-Merlin1D`/`ROE-Merlin1DV` (914/934 kN, Isp 311/348s — `CooledRP-1+CooledLqdOxygen`) | **T13** (`fd_reusableGasGenKerolox` above) | Subcool ("densify") both propellants below their boiling points and pack more mass into the same tank/engine — a real, distinct refinement (not just a bigger chamber) that raised Merlin's thrust ~65% with the same basic cycle. |
| 🆕 **Electric-Pump-Fed Kerolox** `pc_electricPumpFeed` | `ROE-Rutherford`/`ROE-RutherfordVac` (25/26 kN, Isp 317/343s — `RP-1+LqdOxygen+ElectricCharge`) | **T12**, crossover parent = `fd_gasGeneratorApex` × `ep_hallEffectThruster` (both established propulsion/electric roots) | Genuinely new mechanism, not a refinement of anything: brushless battery-driven electric motors spin the propellant pumps instead of a gas-generator or preburner turbine. Trades a little thrust-to-weight for radical simplicity and cheap manufacturing (Rocket Lab Electron) — the tree's first crossover between chemical propulsion and battery/electric-power engineering. |
| 🆕 **American ORSC Kerolox Studies** `pc_americanORSCKerolox` | `nflv-engine-ar1-1`/`nflv-engine-ar1c-1` (AR-1, 2487/14922 kN) + `nflv-engine-rs84-1` (RS-84, 5026 kN, Isp 324s) | **T12** (`pc_multiChamberORSC` T11) | Two real, separately-funded 2000s Rocketdyne oxidiser-rich staged-combustion kerolox programs built to compete with/replace the imported RD-180 — both lost the contract and never flew. Same "drawn but never poured" flavor as RD-270/AJ-260/STBE, this time the story is American ORSC losing to Russian ORSC on price, not physics. |
| ⟳ **widen `pc_modularORSC`** (T12) | += `ROE-RD191` (2085 kN, Isp 337.5s) | existing T12, no change | RD-191 *is* the single-chamber, one-quarter-of-an-RD-170 engine this node's own flavor text already describes (Angara) — its base part was simply never added despite being narrated. Upgrades `RFUpgrade_RD-181`/`RD-191`/`RD-193` join here too. |
| ⟳ **widen `pc_gemStrapOnCatalog`** (T11) | += `ROE-GEM63` (1658 kN) | existing T11, no change | The fourth Delta/Vulcan graphite-epoxy strap-on length — same catalog as GEM-40/46/60 + AJ-60A. |
| ⟳ **widen `pc_filamentWoundSolid`** (T10) | += `ROE-Castor30`, `ROE-Castor30XL` (331/533 kN, HTPB) | existing T10, no change (reaches the 6-part cap) | Direct siblings of the already-placed `ROE-Castor120` — same real Castor-30-series commercial composite family (Antares stage 2 / Minotaur), not a separate lineage. |
| 🆕 **Five-Segment Solid Booster Scale-Up** `pc_fiveSegmentSolidScaleUp` | `MassiveBooster` (RSRMV, **15,800 kN** — SLS's 5-segment derivative of the Shuttle SRB) | **T11** (`pc_filamentWoundSolid` T10) | The Shuttle's own steel-segmented RSRM (`pc_shuttleSRB` T9) scaled up one more segment for SLS — largest solid in the curated set, a genuine "one more record" sibling to `pc_gemStrapOnCatalog` off the same composite-case parent. |
| ⟳ **widen `fd_continuousThrottleDescent`** (T7) | += `ROE-MR80B` (MR-80B "MLE", 3.6 kN monoprop hydrazine) | existing T7, no change | The same real MR-80 descent-engine family already hosting `ROE-MR80TDE` (Viking-derived terminal-descent engine) — MR-80B is its later Mars-rover mark (MER/MSL sky-crane), not a new mechanism. RP-1 tech-gates it by *when the KSP part's craft flew* (`largeRoverDesigns`, modern), not by engine debut — same pattern already accepted for other late-tagged-but-early-lineage marks in this project. |
| ⟳ **widen `gnc_deepSpaceApogeeEngine`** (T11) | += `ROE-LEROS4` (LEROS-4, 1.1 kN, Isp 323s) | existing T11, no change | Same real LEROS manufacturer lineage as the already-placed LEROS-1b — a bigger mark of the same apogee-engine family, not a new node. |

## C. GuidanceControl — commercial-crew abort engines learn to also land

| Breakthrough | KING(s) | tier (parent) | notes |
|---|---|---|---|
| 🆕 **Deep-Throttling Pressure-Fed Abort/Landing Engine** `gnc_deepThrottlingAbortLandingEngine` | `ROE-SuperDraco`/`ROE-SuperDracoDouble` (85/170 kN, MMH+NTO — Dragon 2) | **T12** (`gnc_deepSpaceApogeeEngine` T11) | SuperDraco is a real breakthrough beyond any prior abort motor: pressure-fed, hypergolic, *deep-throttleable*, and restartable enough to also fly a **propulsive landing** — one engine doing launch-abort and soft-touchdown duty. `ROC-CSTRS88` (CST-100's own launch-abort-only engine cluster, 774 kN) rides along as the parallel commercial-crew abort system without the landing capability. `ROC-OrionESM` (8×R-4D-11 service-module cluster) and `ROC-OrionLAS`+`ROC-OrionCover1/2/3` (the Orion launch-abort motor + its jettisoned fairings) ride along too — same commercial/modern-capsule propulsion generation, all `partTech=commercialCapsules`. |

## D. ElectricalPower — electric propulsion's second generation

| Breakthrough | KING(s) | tier (parent) | notes |
|---|---|---|---|
| 🆕 **Next-Generation Gridded Ion Thruster** `ep_nextGenGriddedIon` | `ionXenon-0625` (NEXT, Isp 4190s — **NASA's direct successor to NSTAR**, higher thrust) | **T13** (`ep_griddedIon` T12) | The real follow-on to Deep Space 1's NSTAR — same gridded-ion mechanism, refined for higher throughput. `ionXenon-0625-2` (HiPEP, Isp 9620s — even higher-Isp NASA test article), `RO-ID500` (Isp 7140s), `ionXenon-0625-3` (DS4G, Isp 8000s, dual-stage 4-grid) ride along as sibling refinements of the same electrostatic-grid family. |
| 🆕 **NASA High-Power Hall Thruster** `ep_nasaHighPowerHall` | `ionArgon-0625` (HERMeS, Isp 2820s — built for NASA's Gateway/PPE) | **T13** (`ep_highPowerHall` T12) | Direct next mark past the 457M — a purpose-built high-power Hall thruster for deep-space station-keeping. `ionArgon-0625-3` (X3, Isp 4370s — the highest-power nested-channel Hall thruster ever built) and `ionArgon-0625-2` (P5, Isp 2420s, a NASA mid-power test article) ride along. |
| 🆕 **Magnetoplasmadynamic Thruster** `ep_magnetoplasmadynamic` | `mpdt-125` (SX3 MPD, Isp 4665s) | **T13** (`ep_hallEffectThruster` T9) | A genuinely different acceleration mechanism from both Hall and gridded-ion: an electromagnetic pinch discharge accelerates a plasma arc directly, no grid or Hall channel at all. Real high-power-density concept, earns its own node rather than folding into either existing electric-propulsion lane. |
| 🆕 **Variable-Specific-Impulse Plasma Rocket** `ep_variableSpecificImpulsePlasma` | `vasimr-125`/`vasimr-0625` (VF-200/VX-200SS VASIMR, Isp 3210/3850s) | **T14** (`ep_magnetoplasmadynamic` above) | A third distinct mechanism: RF-heat a plasma, then a magnetic nozzle accelerates it — with thrust/Isp continuously tradeable in flight (unique among every electric thruster in the tree). The most exotic and least-flown of this batch's electric concepts, tiered one step past MPD. |

## E. NuclearEngineering — past NTR into fusion pulse and continuous-criticality concepts

| Breakthrough | KING(s) | tier (parent) | notes |
|---|---|---|---|
| 🆕 **Bimodal Nuclear Thermal + Power** `nuc_bimodalNTR` | `ROE-BNTR` (Bimodal NTR, 121 kN, Isp 512s) | **T14** (`nuc_advancedCoreNTR` T13) | The same reactor that heats propellant for thrust also runs continuously as a power source between burns — real NASA bimodal-NTR design studies, one generation past the pure-thrust advanced-core concepts. |
| 🆕 **Fission-Fragment Rocket** `nuc_fissionFragmentRocket` | `RO-fftdustyplasmaffre` (Dusty Plasma FFRE, Isp **527,000s**) | **T14** (`nuc_bimodalNTR` above) | The fission fragments themselves *are* the exhaust — no propellant to heat at all, the highest-Isp concept in the whole tree. `fft-ffre-plasma-1` ("Afterburning" variant, same absurd Isp, one tech tier later at `nuclearPropulsionNF2`) continues as the direct next mark — inject propellant into the fragment stream to trade some of that Isp for usable thrust. |
| 🆕 **Magnetically-Confined Fusion Pulse Drive** `nuc_magneticFusionPulsePropulsion` | `fft-fission-zpinch-1` (10m Mini-Mag Orion, 642 kN, Isp 9500s) + `RO-fft20mMMO` (20m, 1870 kN, Isp 16000s) | **T15** (`nuc_pulsePropulsion` T10, the classic fission-Orion node) | Real theoretical NASA/MSNW concept: magnetically compress a small fusion-fuel pellet and let the pulse itself do the pushing — mechanically a pulsed-drive sibling of the classic external-detonation Orion, but fusion instead of fission, one full generation past it. |
| 🆕 **Nuclear Salt Water Rocket** `nuc_nuclearSaltWaterRocket` | `fft-nswr-2` (20m NSWR, 8697 kN, Isp 8000s) | **T15** (`nuc_fissionFragmentRocket` above) | Zubrin's concept: dissolve fissile salts in water and let the mixture go critical continuously as it flows through the chamber — the reactor **is** the propellant stream, no separate core at all. The wildest, most engineering-fiction concept in the curated set; capstone of the exotic-nuclear cluster, deliberate what-if/fun curation per [[rp-axe-fun-over-history]]. |

---

## Proposed tier map (for authoring into `tree/nodes.yaml` on go-ahead)

| Tier | Discipline | Node (proposed id) | Parent(s) |
|---|---|---|---|
| T7 (existing, append) | FluidDynamics | `fd_continuousThrottleDescent` (+MR-80B) | — |
| T10 (existing, append) | PropellantChemistry | `pc_filamentWoundSolid` (+Castor 30/30XL) | — |
| T11 (existing, append) | PropellantChemistry | `pc_gemStrapOnCatalog` (+GEM-63) | — |
| T11 (existing, append) | GuidanceControl | `gnc_deepSpaceApogeeEngine` (+LEROS-4) | — |
| T11 | PropellantChemistry | 🆕 `pc_fiveSegmentSolidScaleUp` (RSRMV) | `pc_filamentWoundSolid` |
| T12 (existing, append) | PropellantChemistry | `pc_modularORSC` (+RD-191) | — |
| T12 (existing, append) | Cryogenics | `cryo_methaloxStagedCombustion` (+BE-4) | — |
| T12 | Cryogenics | 🆕 `cryo_combustionTapOff` (BE-3PM) | `cryo_boosterGasGenHydrolox` |
| T12 | Cryogenics | 🆕 `cryo_highThrustExpander` (RL60/Vinci) | `cryo_deployableNozzleExpander` |
| T12 | Cryogenics | 🆕 `cryo_smallScaleMethalox` (M10) | `pc_zenitKerolox` |
| T12 | FluidDynamics | 🆕 `fd_reusableGasGenKerolox` (Merlin 1A/1C) | `fd_terminalGasGenKerolox` |
| T12 | PropellantChemistry | 🆕 `pc_electricPumpFeed` (Rutherford) | `fd_gasGeneratorApex` × `ep_hallEffectThruster` |
| T12 | PropellantChemistry | 🆕 `pc_americanORSCKerolox` (AR-1, RS-84) | `pc_multiChamberORSC` |
| T12 | GuidanceControl | 🆕 `gnc_deepThrottlingAbortLandingEngine` (SuperDraco) | `gnc_deepSpaceApogeeEngine` |
| T13 | Cryogenics | 🆕 `cryo_expanderBoosterScale` (LE-9) | `cryo_deployableNozzleExpander` |
| T13 | Cryogenics | 🆕 `cryo_fullFlowMethalox` (Raptor/RaptorVac) | `cryo_methaloxStagedCombustion` |
| T13 | FluidDynamics | 🆕 `fd_densifiedPropellantKerolox` (Merlin 1D/1DV) | `fd_reusableGasGenKerolox` |
| T13 | ElectricalPower | 🆕 `ep_nextGenGriddedIon` (NEXT/HiPEP/ID-500/DS4G) | `ep_griddedIon` |
| T13 | ElectricalPower | 🆕 `ep_nasaHighPowerHall` (HERMeS/X3/P5) | `ep_highPowerHall` |
| T13 | ElectricalPower | 🆕 `ep_magnetoplasmadynamic` (SX3 MPD) | `ep_hallEffectThruster` |
| T14 | ElectricalPower | 🆕 `ep_variableSpecificImpulsePlasma` (VASIMR) | `ep_magnetoplasmadynamic` |
| T14 | NuclearEngineering | 🆕 `nuc_bimodalNTR` (BNTR) | `nuc_advancedCoreNTR` |
| T14 | NuclearEngineering | 🆕 `nuc_fissionFragmentRocket` (Dusty Plasma FFRE + Afterburning) | `nuc_bimodalNTR` |
| T15 | NuclearEngineering | 🆕 `nuc_magneticFusionPulsePropulsion` (Mini-Mag Orion 10m/20m) | `nuc_pulsePropulsion` |
| T15 | NuclearEngineering | 🆕 `nuc_nuclearSaltWaterRocket` (NSWR) | `nuc_fissionFragmentRocket` |

**19 new nodes** (1 at T11, 8 at T12, 5 at T13, 3 at T14, 2 at T15) + **7 existing nodes widened** with no
tier change (`fd_continuousThrottleDescent`, `pc_filamentWoundSolid`, `pc_gemStrapOnCatalog`,
`gnc_deepSpaceApogeeEngine`, `pc_modularORSC`, `cryo_methaloxStagedCombustion`) + **~23 upgrade-only
doctrine-4 catches** appended to already-existing nodes per the table above.

## Open questions for you
1. **Tier ceiling → T15?** Matches the "one generation deeper than the last era" pattern, but this batch
   spans real years 2004-2028+ *plus* pure-theoretical far-future concepts (fusion pulse, NSWR) — happy to
   compress the NuclearEngineering exotic cluster (T14-T15) into fewer tiers if you'd rather not stretch
   the ceiling that far this early.
2. **`pc_electricPumpFeed` discipline/crossover** — Rutherford is PropellantChemistry-flavored (still
   kerolox) but the actual breakthrough is electric, hence the crossover parent. Open to moving it to
   ElectricalPower outright if you'd rather the discipline follow the breakthrough, not the propellant.
3. **Raptor/Orion-capsule "no RP-1 tech gate" parts** — ground-truthed via `partTech` (same technique as
   the AJ10-190 fix), but flagging since it's now happened three times; fine to keep doing this, or say if
   you'd rather these wait for a dedicated AXE-authored pass instead of riding in with the RP-1-gated majority.
4. **Tantares Mir/LK-700/TKS (48 parts, entirely unplaced)** — not part of this pass (no RP-1 tech gate
   at all), but flagging it exists as a known gap since the sweep surfaced it. Separate thread, your call
   on when to tackle it.

**Ready to author into `tree/nodes.yaml` on your go-ahead.**
