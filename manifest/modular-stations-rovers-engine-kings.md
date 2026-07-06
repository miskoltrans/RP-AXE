# Modular Stations, Rovers & ISS-Assembly Era — Engine/Propulsion KING PARTS

**STATUS: PROPOSAL (2026-07-06) — nothing authored into `tree/nodes.yaml` yet.** This is the
engine-axis design for the batch *after* `space-stations-shuttle`, to be authored ahead of the
non-engine parts (stations, rovers, probes, comms, science) exactly as the shuttle pass was.

Derived from `modular-stations-rovers-partlist.md` (RP-1 x=-1507..-1167 — the operational-launch-fleet
era: 1986/1992/1998 engine columns + International Cooperation). This pass covers **only the propulsion
axis** of that batch — every new engine base part plus every upgrade-only `RFUpgrade_*`/`RFTech-*` entry.

Method: real thrust/Isp/propellant/cycle pulled from `manifest/engine-stats.tsv`
(`tools/extract_engine_stats.py`), grouped by **mechanism/lineage, not RP-1's calendar bucket**
(rule 1, `docs/HANDOVER.md`). For every upgrade-only entry, its host base part was traced to its
*current* `tree/nodes.yaml` home so doctrine-4 (an upgrade never shares a node with its own base part)
is respected.

**Current engine frontier = T11** (`cryo_ssme` RS-25, `nuc_flightRatedNTR` NERVA-I, `pc_rd270Variants`,
`ep_higherPowerHallThruster` SPT-70). This batch is a full generation later and internally spans three
RP-1 sub-eras (1986 / 1992 / 1998), so it should land **T11–T13**. **Tiers below are PROPOSALS** — the
design value is the mechanism groupings + kings + lineage parents; adjust tier numbers freely.

Legend: **KING** = the hero part. ⟳ = continues an existing node (append only). 🆕 = new node proposed.
`disc` = discipline. (`build_tree.py` uses `tc.get(tier,0)` so new T12/T13 nodes build at cost 0 until
the deferred cost pass extends `meta.tier_cost` — no blocker.)

---

## The era in one line
The Shuttle proved reusable staged-combustion hydrolox (RS-25, T11). This era is what the **operational
world fleet actually did next**: (1) it went *back* to gas-generator hydrolox for cost (RS-68, Vulcain);
(2) the SSME cycle went **international** (RD-0120 Energia, LE-7 H-II) and spawned exotic-fuel variants
(tripropellant MAKS, methalox); (3) oxidiser-rich kerolox hit its **all-time thrust ceiling** (RD-170)
then **modularised** for the commercial market (RD-180); (4) **electric propulsion finally flew as
primary propulsion** (NSTAR/Deep Space 1, operational Hall); (5) solids switched to **filament-wound
composite cases**; and (6) the nuclear lane matured past NERVA into flight-design (RD-0410), particle-bed
(Timberwind) and liquid/gas-core concepts.

---

## Already resolved — no new work / duplicate references
- `restock-engine-cherenkov` — same config as `RD0410MID` (both "RD-0410"). Ride-along/dup of the RD-0410
  king (G1), not a second part.
- `rmm_turiasaurus` — same config as `nflv-engine-stbe-kero-1` (both "STBE (Pratt & Whitney)", 3275 kN).
  Duplicate reference; one STBE king (D3).
- `YF77_Engine-double-withShell` / `YF100_Engine-double-withShell2` — the same YF-77 / YF-100 with a
  CZ-5 boattail shell. Cosmetic-variant ride-alongs of their bare kings (A3 / C1).
- `miniIonEngine` (IX-631 "Dawn") — **uncurated (✗)** in the partlist; nothing to place.
- `RFTech-Tank-*`, `MLI.Upgrade5`, `PFTech-Fairing-V`, `RFTech-MLI-UpgradeBalloon`, `solarTL8/9`,
  `commsTL8/9`, `RP0Level9/10TrackingStation`, `HDD-Upgrade-*`, `*-longTermAvionics`,
  `rp0*Upgrade*` — **non-engine** (tanks / MLI / fairings / solar / comms / avionics / axed-career).
  Out of scope for this pass.

---

## A. Cryogenics — the operational hydrolox fleet (expander maturity + the anti-SSME booster)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Deployable-Nozzle Expander Cycle** `cryo_deployableNozzleExpander` | `ROE-RL10B2` (RL-10B/C, 110 kN, **Isp 465.5s — the highest of any flown engine**, 84" carbon-carbon extendable nozzle), `ROE-RL10A4N` (RL-10A-4N, 92.5 kN, Isp 449s, 46" extendable), `ROE-RD0146` (98 kN, Isp 463s — Russian closed-expander, Angara upper) | `RFUpgrade_RL10A-4`, `RL10A-4-1N`, `RL10A-4N`, `RL10A-5`, `RL10A-4-1-2`, `RL10A-4-2N`, `RL10B-2`, plus the expander-bleed `RFUpgrade_LE-5A`/`LE-5B` (their base LE-5 is gas-gen, homed at A2) | **T11** (parent = `cryo_refinedExpander` T7) | The RL-10 lane's real next step: the **deployable radiative nozzle** that trades stowed length for record vacuum Isp. **Accepted (your call):** T7→T11 is a 4-tier lineage edge (the intermediate RL10A-3 marks were appended to `cryo_refinedExpander` in the shuttle pass) — an idle-then-leap lane, kept as-is with no intermediate rung. |
| 🆕 **Operational Restartable Hydrolox Upper** `cryo_operationalHydroloxUpper` | `ROE-LE5` (LE-5, 102.9 kN, Isp 450s, **10 restarts** — the H-I/H-II multi-burn upper) | — (its own expander-bleed marks LE-5A/B home at A1; `RFUpgrade_HM-7B++`, `M-1U`, `M-1U-SL` → append `cryo_matureGasGeneratorHydrolox` T10) | **T11** (parent = `cryo_gasGeneratorHydrolox` T8) | The gas-generator hydrolox *upper* (J-2 → LE-5 lineage) matures into an operational, many-restart stage. Thin king node; its interesting descendants (expander-bleed LE-5A/B) deliberately split off to A1 per doctrine-4. |
| 🆕 **Booster-Class Gas-Generator Hydrolox** `cryo_boosterGasGenHydrolox` | `ROE-RS68` (**3380 kN — the most powerful hydrolox engine ever flown**, gas-gen + ablative nozzle, deliberately cheap), `cryoengine-vesuvius-1` (Vulcain 2, 1350 kN — Ariane 5 core), `YF77_Engine` (YF-77, 700 kN — Long March 5 core), `rmm_rainier` (STME, 2891 kN — NLS study) | — | **T11** (parent = `cryo_largeHydrolox` T9 × `cryo_gasGeneratorHydrolox` T8) | The **deliberate anti-SSME**: after staged combustion was proven, the operational fleet went *back* to gas-generator hydrolox scaled to core-stage thrust, trading Isp for cost/manufacturability (RS-68 the textbook case). **Tiered T11 as a *sibling* of `cryo_ssme` (your call)** — later by calendar but not more advanced; it trades Isp for cost, so it sits beside the SSME, not beyond it. |

## B. Cryogenics — the SSME cycle goes international & exotic (fuel-rich staged combustion)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Operational Fuel-Rich Staged-Combustion Hydrolox** `cryo_operationalFRSC` | `ROE-RD0120` (RD-0120, 1961 kN, Isp 454.5s — **Energia core, the Soviet SSME**), `ROE-LE7` (LE-7, 1096 kN, Isp 446.5s — H-II core, Japan) | `rmm_ishtar` (RS-25-50X uprated-SSME study) rides along | **T12** (parent = `cryo_ssme` T11) | The RS-25's fuel-rich staged-combustion cycle proven by **two more space programs** — the theme is "the hardest cycle in rocketry becomes something three nations can build." |
| 🆕 **Reusable-Engine Production Uprating** `cryo_reusableEngineUprating` | *(none — pure doctrine-4 collector)* | `RFUpgrade_RS-25A`, `RS-25C`, `RS-25D-50X`, `RS-25D-E` (base RS-25 @ `cryo_ssme`), `RD-0120M` (@ B1), `LE-7A`, `LE-7A-2` (@ B1), `RD-0122`, `HG-3B`/`-2`/`-SL`/`-SL-2` (base HG-3 @ `cryo_uprateRestartableHydrolox` T10), `LR129-P-3`, `RD-57M`, `RD-57A-1` (bases @ `cryo_deepThrottleHydrolox` T9) | **T13** (parent = B1) | One catch node for every *production mark* of the reusable/staged-hydrolox engines whose bases are already placed — the SSME Block-I/II, RD-0120M, LE-7A, HG-3B chain "maturing in service." |
| 🆕 **Tripropellant Staged Combustion** `cryo_tripropellant` | `nflv-engine-rd701-1` (RD-701, 4004 kN — MAKS spaceplane, RG-1+LH2+LOX), `nflv-engine-rd704-1` (RD-704, 2002 kN), `rmm_dugong` (SSBE, 2265 kN — RP-1+LOX+LH2) | `RFUpgrade_SSBE-BlockII` | **T12** (crossover parent = `cryo_ssme` T11 × `pc_zenitKerolox` T10) | A genuinely different mechanism: **one engine burning kerosene+LOX at liftoff and switching to hydrogen+LOX at altitude** — needs both staged-combustion-hydrolox *and* oxidiser-rich-kerolox mastery, so a real justified crossover. What-if flavor (MAKS never flew). **Disc → Cryogenics (resolved):** the bottleneck is the hydrolox staged-combustion cycle (a Cryogenics concern); the kerolox side is carried by the `pc_zenitKerolox` crossover edge, so it needn't *live* in PropChem. |
| 🆕 **Methalox Staged Combustion** `cryo_methaloxStagedCombustion` | `rmm_arenysaurus` (LRBE, 2429 kN — **the tree's first methane engine**, LqdMethane+LqdOxygen) | `RFUpgrade_LRBE-BlockII` | **T12** (parent = `pc_zenitKerolox` T10) | Methane sits between kerosene and hydrogen; the first methalox part is the **seed of a future methalox lane** (Raptor-era). Thin king. **Disc → Cryogenics (resolved):** matches the `cryo_hydrogen` precedent — the tree files *cryogenic-fuel introduction* under Cryogenics, not PropChem; methane is a cryogenic fuel with the same handling concern (the `pc_zenitKerolox` parent gives the ORSC-cycle flavor via the edge). |

## C. PropellantChemistry — the oxidiser-rich kerolox dynasty (RD-170 → RD-180)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **High-Thrust Multi-Chamber ORSC** `pc_multiChamberORSC` | `ROE-RD170` (**7904 kN — the most powerful liquid-propellant engine ever built**, 4-chamber oxidiser-rich kerolox, Energia strap-on / Zenit stage-1), `YF100_Engine_S` (YF-100, 1340 kN — China's operational ORSC) | `YF100_..withShell2` cosmetic ride-along | **T11** (parent = `pc_zenitKerolox` T10) | The ORSC kerolox thrust ceiling — where NK-33 (N1) never flew and Zenit's RD-120 was an *upper*, RD-170 is the **operational monster**. Sibling to `cryo_largeHydrolox`/`pc_stagedCombustionCeiling`: the "biggest of its chemistry" record node. |
| 🆕 **Modular Oxidiser-Rich Kerolox** `pc_modularORSC` | `ROE-RD180` (RD-180, 4152 kN — **literally half an RD-170**, 2-chamber, Atlas V) | `RFUpgrade_RD-171` (RD-170 mark), `RD-172-173`, `RD-120F`, `RD-120K` | **T12** (parent = C1) | The real story: the RD-170 is **subdivided** into modular commercial engines — RD-180 (2-chamber, Atlas V), RD-191 (1-chamber, Angara). Same core hardware, packaged for the export/commercial market. |
| 🆕 **Operational Storable Staged Combustion** `pc_operationalStorableORSC` | *(none — pure catch; the Proton engines' bases are already placed)* | `RFUpgrade_RD-275`, `RD-253-Mk4`, `RD-254-11D44-Mk4`, `RD-277-14D16`, `RD-0210-Mk3`, `RD-0212-Mk3`, `RD-0213-Mk3`, `RD-58S` | **T11** (parent = `pc_refinedStorableORSCII` T10) | The Proton first/second-stage ORSC (RD-253/275 + Kosberg RD-021x) reaching its final operational marks — same-shape continuation of the Mk1→Mk2→Mk3 storable-ORSC chain. No new king. |

## D. FluidDynamics — mature storable uppers + the last gas-generator kerolox marks

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Multi-Restart Storable Upper Stage** `fd_multiRestartStorableUpper` | `ROE-S592` (S5.92, **Fregat main engine**, 50 restarts — the interplanetary workhorse), `restock-engine-125-pug` (Aestus — Ariane 5 upper, 20 restarts), `ROE-AJ10-transtar` (AJ23 Transtar, **500 restarts**), `ROE-S598M` (S5.98M — Briz-M) | `ROE-AJ10AdvLong` (final AJ10 long-nozzle) rides; `RFUpgrade_AJ10-118K`, `AJ10-153`, `AJ10-154`, `AJ10-156`, `Agena-2000` | **T11** (parent = `fd_restartableUpperMaturation` T9) | The deep-space **many-restart storable propulsion module** — the breakthrough is coast-and-reignite duty across dozens/hundreds of burns (Fregat/Briz/Cassini-class multi-target missions), a real step past the single-restart Agena/AJ10 lineage. |
| 🆕 **Terminal Gas-Generator Kerolox Uprating** `fd_terminalGasGenKerolox` | *(none — catch)* | `RFUpgrade_RS-27A`, `RS-56-OBA`, `RS-56-OSA`, `LR87-AJ-11A`, `LR87-AJ-11A-Kero`, `LR91-AJ-11A`, `LR91-AJ-11A-Kero`, `LR101-NA-15`, `Model8096C` | **T11** (parent = `fd_gasGeneratorApex` T9) | The **final production marks** of the Delta (RS-27/RS-56), Titan (LR87/LR91) and vernier (LR101) gas-generator kerolox engines before retirement. Same "diminishing-return uprate" spirit as `fd_gasGeneratorApex`, one generation on. (`RFUpgrade_RD-107A-14D22`/`RD-108A-14D21` → append `fd_engineMaturation` T6, the R-7 production chain, no tier change.) |
| 🆕 **Advanced Gas-Generator Kerolox Booster** `fd_advancedGasGenKerolox` | `nflv-engine-stbe-kero-1` (STBE, 3275 kN — Pratt & Whitney NLS booster), `cryoengine-allosaur-1` (STBE-3) | — (`rmm_turiasaurus` = STBE dup) | **T11** (parent = `fd_gasGeneratorApex` T9) | The **American gas-generator answer to the RD-180** — a big, simple kerolox booster engine for the NLS/EELV studies that lost to the imported ORSC RD-180. What-if flavor; thin king node. |

## E. PropellantChemistry — solids switch to filament-wound composite cases

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Filament-Wound Composite-Case Solids** `pc_filamentWoundSolid` | `ROE-SRMU` (**8234 kN — the composite-case Titan IV motor**, the largest here), `ROE-Castor120` (1875 kN — commercial composite standalone, Athena/Taurus stage-1), `ROE-UA1208` (7450 kN — Titan) + `ROE-1208sepMotor` | `RFUpgrade_FWC-SRM` (the filament-wound Shuttle SRB), `RSRM-1986`, `RFTech-solids-tltech6`, `RFTech-solids-tltech7` | **T10** (parent = `pc_shuttleSRB` T9) | A real **material breakthrough**: the filament-wound graphite/epoxy composite case replaces heavy steel segments → higher mass fraction. Next casing generation after the human-rated *steel* segmented RSRM. |
| 🆕 **Graphite-Epoxy Strap-On Catalog** `pc_gemStrapOnCatalog` | `ROE-GEM60` (GEM-60, 1236 kN — Delta IV) | `ROE-GEM40`, `ROE-GEM46` (Delta II/III), `ROE-AJ60` (AJ-60A, Atlas V) — the modern composite EELV strap-on family | **T10** (parent = E1) | **Split (your call):** the Delta/Atlas graphite-epoxy composite strap-on **catalog dead-end** off the composite-case king. |
| ⟳ **append to `pc_strapOnMarkII`** (T7) | — | `ROE-Castor4A`, `ROE-Castor4AXL` | existing **T7**, no change | **Split (your call):** Castor-4's own later marks continue the existing Castor strap-on lineage (`pc_strapOnMarkII` already hosts Castor 1/2/4) — GEM gets a new node, Castor stays on its family line. |
| ⟳ **append to `pc_apogeeKickCatalogII`** (T9) | — | `ROE-Star5D` (STAR 5D), `ROE-Star8` (STAR 8 RAD) | existing **T9**, no change | Two more small STAR kick motors — same catalog, next marks. No new node. |

## F. ElectricalPower — electric propulsion comes of age (Hall operational + gridded ion flies)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Operational Hall-Effect Thruster** `ep_operationalHall` | `RO-SPT100` (SPT-100, Isp 1600s — **the operational workhorse**), `RO-SPT140` (Isp 1680s), `RO-PPS1350` (SMART-1's engine) | `RFUpgrade_SPT-100B`, `SPT-50M` | **T11** (parent = `ep_higherPowerHallThruster` T10) | The Hall thruster crosses from lab article (SPT-70) to **flight-qualified primary/station-keeping propulsion** — the workhorse of the whole electric-propulsion era. |
| 🆕 **High-Power Nested Hall Thruster** `ep_highPowerHall` | `RO-457M` (457M, **72 kW**, Isp 2929s) | `RFUpgrade_457M-V1-K` | **T12** (parent = F1) | Scaling Hall thrusters into the tens-of-kW class — the path toward cargo-tug-scale electric propulsion. |
| 🆕 **Gridded Ion Electrostatic Thruster** `ep_griddedIon` | `ionEngine` (NSTAR, Isp 3100s — **Deep Space 1, the first ion engine to propel an interplanetary probe**) | — | **T12** (parent = `ep_hallEffectThruster` T9) | A **distinct electrostatic mechanism** from Hall (gridded acceleration, higher Isp) and a genuine headline — the first primary-propulsion ion flight. Parallel branch off the electric-propulsion foundation, not a Hall descendant. |
| 🆕 **Pulsed Inductive Thruster** `ep_pulsedInductive` | `pit-125` (PIT Mk Va, **Isp 7000s**, ammonia, electrodeless pulsed-inductive) | `RFUpgrade_PITV-Hydrazine-40` | **T12** (parent = `ep_higherPowerHallThruster` T10) | A high-Isp, electrodeless, high-power *pulsed* concept — experimental/what-if (PIT never flew operationally), a fun deep-space cruise option. Thin king. |

## G. NuclearEngineering — NTR matures past NERVA (flight-design → particle-bed → advanced cores)

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Flight-Design Solid-Core NTR** `nuc_flightDesignNTR` | `RD0410MID` (RD-0410, 35 kN, Isp 910s — **the real Soviet NTR that was actually built and ground-tested**), `ROE-NERVAII` (NERVA II, 867 kN — the largest solid-core design) | `restock-engine-cherenkov` = RD-0410 dup | **T12** (parent = `nuc_flightRatedNTR` T11) | The solid-core NTR reaches a **built, tested** flight design (RD-0410) and its biggest US paper design (NERVA II) — the operational endpoint of the solid-core lineage. |
| 🆕 **Particle-Bed NTR** `nuc_particleBedNTR` | `ROE-SNTPPFE100` (SNTP-PFE100, 206 kN, Isp 940s — **Timberwind particle-bed**) | — | **T12** (parent = G1) | A different fuel geometry — packed fuel particles instead of solid rods → higher power density and Isp. Real (Timberwind/SDI) program; distinct enough for its own node. |
| 🆕 **Advanced-Core NTR Concepts** `nuc_advancedCoreNTR` | `RO-KA-LRCNTR` (Lewis LNTR, 145 kN, **Isp 1400s — liquid core**), `ntr-gc-25-1` (Low-Pressure NTR, Isp 1037s — gas-core start) | `RFUpgrade_PrincetonLNTR-WCH` | **T13** (parent = G2) | The **fuel-state leap** — solid → liquid → gas core — trading engineering realism for huge Isp. What-if capstone that seeds the future gas-core lane. |

## H. AirBreathing — VTOL vectored thrust + fourth-generation fighter turbofans

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Vectored-Thrust VTOL Turbofan** `av_vtolVectoredTurbofan` | `RO-SXT-R79` (R-79, 147 kN — **Yak-141, vectored-thrust supersonic VTOL**), `RO-nfa-RD41` (2× RD-41 — Yak-38 lift jets) | — | **T10** (parent = `av_secondGenTurbofan` T9) | A distinct capability: **thrust vectoring for vertical/short takeoff** in a supersonic airframe. Real, separate mechanism from a plain fighter turbofan. |
| 🆕 **Fourth-Generation Fighter Turbofan** `av_fourthGenFighterTurbofan` | `SXTVTOLturboFan` (F135 — **F-35, the most powerful fighter engine ever**), `RO-WS10` (WS-10 — China's operational 4th-gen) | `RFUpgrade_F100-PW-229`, `F100-PW-229PYBBN`, `F404-GE-402`, `CF34-3B`, `J58-P-4A`, `J58-P-4B`, `RM12`, `R-79M-300`, `R-79V-300`, `WP-13A-II`, `WP-13F`, `WP-13FI`, `AL-31FM`, `AL-41F-1S`, `F135-PW-600`, `WS-10B`, `PT6A-34AG` | **T10** (parent = `av_secondGenTurbofan` T9) | The generation of high-thrust, high-pressure-ratio fighter turbofans (F135/WS-10/AL-31 family). Catches the long tail of fighter-engine production marks. (`SXTMiniJet` FJ44-2A small biz-jet turbofan → append `av_highBypassTurbofan` T7.) |

## I. GuidanceControl — deep-space bipropellant apogee engines

| Breakthrough | KING(s) | doctrine-4 catches | tier (parent) | notes |
|---|---|---|---|---|
| 🆕 **Deep-Space Bipropellant Apogee Engine** `gnc_deepSpaceApogeeEngine` | `ROE-LEROS1B` (LEROS-1b, 635 N, Isp 317s — **the real interplanetary apogee/orbit-insertion engine**: NEAR, MESSENGER, Juno), `ROE-R42` (R-42, 890 N) | `ca_mer_ft` (Cassini Propulsion Module) rides along; `RFUpgrade_LEROS-1c`, `LEROS-2b` | **T11** (parent = `gnc_bipropAttitudeThrust` T9) | The mature, flight-proven descendant of the R-4D bipropellant thruster (T9) — a long-coast, restartable, high-reliability apogee engine sized for probe orbit insertion. The exotic RCS-propellant configs (`RFUpgrade_Ethanol+O2`, `RP-1+O2`, `Syntin+O2`, `RFTech-rcs-tltech6`, `RFTech-AddOxygenGas`) → append `pc_storableRcsPropellants` T8 (propellant type-levels, not this engine). |

---

## Proposed tier map (for authoring into `tree/nodes.yaml` on go-ahead)

| Tier | Discipline | Node (proposed id) | Parent(s) |
|---|---|---|---|
| T10 | AirBreathing | 🆕 `av_vtolVectoredTurbofan` (R-79/RD-41) | `av_secondGenTurbofan` |
| T10 | AirBreathing | 🆕 `av_fourthGenFighterTurbofan` (F135/WS-10) | `av_secondGenTurbofan` |
| T10 | PropellantChemistry | 🆕 `pc_filamentWoundSolid` (SRMU/Castor 120/UA1208) | `pc_shuttleSRB` |
| T10 | PropellantChemistry | 🆕 `pc_gemStrapOnCatalog` (GEM-40/46/60 + AJ-60A) | `pc_filamentWoundSolid` |
| T9 (existing, append) | PropellantChemistry | `pc_apogeeKickCatalogII` (+Star-5D/Star-8) | — |
| T11 | Cryogenics | 🆕 `cryo_deployableNozzleExpander` (RL-10B-2/A-4N/RD-0146) | `cryo_refinedExpander` |
| T11 | Cryogenics | 🆕 `cryo_operationalHydroloxUpper` (LE-5) | `cryo_gasGeneratorHydrolox` |
| T11 | PropellantChemistry | 🆕 `pc_multiChamberORSC` (RD-170/YF-100) | `pc_zenitKerolox` |
| T11 | PropellantChemistry | 🆕 `pc_operationalStorableORSC` (Proton marks catch) | `pc_refinedStorableORSCII` |
| T11 | FluidDynamics | 🆕 `fd_multiRestartStorableUpper` (Fregat/Aestus/AJ23) | `fd_restartableUpperMaturation` |
| T11 | FluidDynamics | 🆕 `fd_terminalGasGenKerolox` (RS-27A/RS-56/LR87/91 catch) | `fd_gasGeneratorApex` |
| T11 | FluidDynamics | 🆕 `fd_advancedGasGenKerolox` (STBE) | `fd_gasGeneratorApex` |
| T11 | ElectricalPower | 🆕 `ep_operationalHall` (SPT-100/140/PPS-1350) | `ep_higherPowerHallThruster` |
| T11 | GuidanceControl | 🆕 `gnc_deepSpaceApogeeEngine` (LEROS-1b/R-42/Cassini) | `gnc_bipropAttitudeThrust` |
| T11 | Cryogenics | 🆕 `cryo_boosterGasGenHydrolox` (RS-68/Vulcain 2/YF-77/STME) | `cryo_largeHydrolox` × `cryo_gasGeneratorHydrolox` |
| T6 (existing, append) | FluidDynamics | `fd_engineMaturation` (+RD-107A/108A marks) | — |
| T7 (existing, append) | AirBreathing | `av_highBypassTurbofan` (+FJ44-2A) | — |
| T7 (existing, append) | PropellantChemistry | `pc_strapOnMarkII` (+Castor 4A/4AXL) | — |
| T8 (existing, append) | PropellantChemistry | `pc_storableRcsPropellants` (+exotic RCS propellant type-levels) | — |
| T10 (existing, append) | Cryogenics | `cryo_matureGasGeneratorHydrolox` (+HM-7B++/M-1U marks) | — |
| T12 | Cryogenics | 🆕 `cryo_operationalFRSC` (RD-0120/LE-7) | `cryo_ssme` |
| T12 | Cryogenics | 🆕 `cryo_tripropellant` (RD-701/704/SSBE) | `cryo_ssme` × `pc_zenitKerolox` |
| T12 | Cryogenics | 🆕 `cryo_methaloxStagedCombustion` (LRBE) | `pc_zenitKerolox` |
| T12 | PropellantChemistry | 🆕 `pc_modularORSC` (RD-180) | `pc_multiChamberORSC` |
| T12 | ElectricalPower | 🆕 `ep_highPowerHall` (457M 72 kW) | `ep_operationalHall` |
| T12 | ElectricalPower | 🆕 `ep_griddedIon` (NSTAR / Deep Space 1) | `ep_hallEffectThruster` |
| T12 | ElectricalPower | 🆕 `ep_pulsedInductive` (PIT Mk Va) | `ep_higherPowerHallThruster` |
| T12 | NuclearEngineering | 🆕 `nuc_flightDesignNTR` (RD-0410/NERVA II) | `nuc_flightRatedNTR` |
| T12 | NuclearEngineering | 🆕 `nuc_particleBedNTR` (SNTP/Timberwind) | `nuc_flightDesignNTR` |
| T13 | Cryogenics | 🆕 `cryo_reusableEngineUprating` (RS-25/RD-0120/LE-7 marks catch) | `cryo_operationalFRSC` |
| T13 | NuclearEngineering | 🆕 `nuc_advancedCoreNTR` (liquid/gas-core LNTR) | `nuc_particleBedNTR` |

**~25 new nodes** (2 at T10, 9 at T11, 12 at T12, 2 at T13) + **6 existing nodes appended** with no tier
change (`pc_apogeeKickCatalogII`, `pc_strapOnMarkII`, `fd_engineMaturation`, `av_highBypassTurbofan`,
`pc_storableRcsPropellants`, `cryo_matureGasGeneratorHydrolox`).

## Resolved (2026-07-06 — user decisions)
1. **Tier ceiling → T13.** Kept as proposed (extend past T11; cost defaults to 0 until the deferred cost pass).
2. **Exotic-fuel discipline → both Cryogenics.** `cryo_tripropellant` (bottleneck = the hydrolox
   staged-combustion cycle) and `cryo_methaloxStagedCombustion` (a cryogenic fuel, per the `cryo_hydrogen`
   precedent) both stay in Cryogenics; their kerolox side is carried by the `pc_zenitKerolox` crossover
   edge, not by the discipline.
3. **RL-10 tier gap → accepted.** `cryo_deployableNozzleExpander` keeps the T7→T11 lineage edge; no
   intermediate rung.
4. **Solid catalog → split.** GEM gets its own `pc_gemStrapOnCatalog` (GEM-40/46/60 + AJ-60A, off the
   composite-case king); Castor 4A/4AXL append to their existing lineage node `pc_strapOnMarkII` (T7).
5. **RS-68 → T11.** `cryo_boosterGasGenHydrolox` tiered as a *sibling* of `cryo_ssme` (later by calendar,
   not more advanced), not a descendant.

**Ready to author into `tree/nodes.yaml` on your go-ahead.**
