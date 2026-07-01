# Interplanetary-Flyby + Moon-Landing Probes — KING PARTS (for review)

Derived from `interplanetary-lunar-probes-partlist.md` (33 RP-1 nodes, 216 curated parts). Each **breakthrough**
carries **1–few KING parts** (the heroes that earn the node) + a ride-along tail the node cost abstracts. Homed
**scatter-by-difficulty** (part lives at its signature breakthrough/discipline, not its function). ⟳ = the
breakthrough already exists in `tree/nodes.yaml`; the batch only adds successors/ride-alongs there.

Legend: **KING** = the hero. `disc` = proposed RP-AXE discipline home. ‖ = two-solutions multi-entry pair.

---

## A. Systems Integration — the milestone vehicles (probes)

**⚠ SPECIAL RULE — the named US/Soviet probes are NOT main-tree kings.** `RN_US_Probes`→`hire_JPL`,
`RN_Soviet_Probes`→`hire_OKB` (auto-routed by `route_probe_mods`). The milestones live in the **charter
subtree**, *gated by* the breakthroughs in B–I (the probe-requirements model), not crowned on the discipline
lanes. Charter-subtree parts this batch: **hire_JPL** = Mariner `rn_mariner1_2`, Surveyor `rn_surveyor3` +
`rn_surveyor_engines`/`_retro`/`_s_engine`/`_solar`, Pioneer `pioneer_6_7_8_9`/`pioneer1_booster`/`p1_decoupler`;
**hire_OKB** = Luna 9 `luna9_als`/`luna9_airbag_cvr`/`luna_ktdu`, `luna_radio`, `l11_radio`.

Main-tree SystemsIntegration convergence nodes (the *generic* bus/lander, Coatl `ca_*` — these DO home here):

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Interplanetary Cruise Bus** | `ca_argo-mk2` (Coatl Mariner bus) | — (subsystems scatter to B–I) | convergence node: deep-space dish + articulated solar + star-tracker cruise attitude + midcourse burn. The RN Mariner sits in hire_JPL and requires this. |
| **Robotic Lunar Soft-Lander** | `ca_landv_core` (Coatl Surveyor core) | ca_landv_orbiter_core | convergence: terminal-descent propulsion + landing legs + radar. **Two-solutions lives at the descent breakthrough** (throttled vernier ‖ solid-retro+airbag), not here — see B/F. |

> **⚠ TODO (user, 2026-07-01): Coatl `ca_*` cores = generic buses, KEPT on main tree — but VERIFY avionics
> support in-game.** Do these integrated cores carry a command module + accept RP-AXE core probe avionics
> (`ModuleAxeAvionics` / the procedural `ROT-ProbeCore` path)? The 3 to check: `ca_argo-mk2` (Mariner bus),
> `ca_landv_core` (Surveyor lander core), `ca_landv_orbiter_core` (Surveyor orbiter core). If unsupported →
> reconsider (patch avionics onto them, or cut in favor of the procedural probe core + charter probes).
| **Two-Crew Maneuvering Capsule** (crewed) | `ROC-GeminiCMBDB` (Gemini) | Gemini equipment/OAMS/retro/parachute/RCS/nose sections (16) | ⚠ belongs to the **crewed-orbit** milestone, not these two — home it but flag scope. |
| **Multi-Crew Capsule + Airlock** (crewed) | `ROC-VoskhodCapsule` + `ROC-VoskhodAirlock` (first EVA) | Voskhod retro/decoupler; `ROAdvCapsule` | ⚠ crewed-orbit scope. |

## B. Propulsion (scatter-by-difficulty by cycle)

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Oxidizer-Rich Staged Combustion** | `ROE-RD58` (RD-58/Block D, first ORSC) | RD-0203/0212/0213/0214 (RD-0210 Proton family), `ROE-E1` | `disc: Metallurgy` (ox-rich preburner superalloys = the bottleneck). The Soviet closed-cycle hero. |
| **Pressure-Fed Service/Kick Engine** | `ROE-AJ10-137` (Apollo SPS) | AJ10-118/-118D/-Adv, KTDU-5A/35, S5.23 | `disc: PropellantChemistry` (storable hypergolics). SPS = into/out of lunar orbit. Successor to spine `pc_hypergolics`. |
| **Throttleable Terminal-Descent Engine** | `ROE-TD339` (Surveyor vernier, throttleable+restart) | — | `disc: FluidDynamics` (deep throttle). The moon-landing enabler; **one arm of the soft-lander two-solutions** (throttled-descent ‖ solid-retro+airbag → the airbag/retro side is `ROE-Star37` + the charter-subtree Luna 9 airbag). |
| **Operational Hydrolox** ⟳ | *(RL-10 already king in `fd_expanderCycle`)* | `ROE-RZ20` (RZ.20), `ROE-LR87_LH2` (AJ23-65) | extends the spine hydrolox line; no new king. |
| **Segmented Large Solid Boosters** | `ROE-UA1205` (Titan III solid) + `ROE-AJ260SLF` (AJ-260, largest solid ever) | UA1204, SR19, SR73, M55 (Minuteman), 1204/1205 sepmotors | `disc: Structures` (segmented case) or PropChem. The big-thrust solids. |
| **Apogee-Kick Solid Motors** ⟳ | `ROE-Star37` (STAR 37 — Surveyor retro + ubiquitous kick) | STAR 13/13A/13D/37E, Altair II/III, Antares II, Algol II, Castor 2, Alcyone | extends spine `pc_solidGrains`; STAR-37 earns its own successor node (the workhorse kick). |
| *(utility solids — NOT kings)* ⟳ | — | **ullage** `ROE-TX280` (S-IV settling); **sep** `ROE-1204/1205sepMotor`; **retro** Gemini/Voskhod (Star-13E); **vernier** `PioneerVernier` | ride-alongs on the STAGING concept (spine `str_staging`), defined by FUNCTION not chemistry. **No spin-up motor in this batch** (those were in first-orbit). |
| **Mach-3 Turbojet** (aviation) | `turboFanEngine` (J58, SR-71) | Olympus 593, R-13, R-15, RB.162 | ⚠ **aviation** track, not probes. `disc: Aerodynamics`/Metallurgy. Home but flag scope. |

## C. Electrical Power

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Alkaline Fuel Cells** | `FuelCell` | FuelCellArray, USFuelCell M/S, kerbalism-fuelcell | `disc: ElectricalPower`. The Gemini/Apollo power breakthrough (library `elec_fuelCell`). |
| **Deployable Articulated Solar Array** | `ca_argo-mk2-solar` (Mariner SAW) | ROS-Folding/Hinged, solarPanels4/5, 1x3SPanels, sp_mariner | `disc: ElectricalPower`. First deployable+tracking array (vs body-mounted). Successor to spine `elec_siliconPV`. |
| **RTG** ⟳ | *(SNAP-3/9 already in spine `nuc_rtg`)* | rtgMini (SNAP-3B Pu238) | no new king. |

## D. Guidance & Control

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Stellar Attitude Determination** | `ca_startrack` (StarTrack ACS) | — | `disc: GuidanceControl`/Optics (library `opt_starTracker`). Mariner's Canopus tracker = deep-space 3-axis pointing. |
| **Momentum-Exchange Attitude Control** | `sasModule` / `ca_rw_small` (reaction wheels) | ca_rw_xsmall | `disc: GuidanceControl` (library `gnc_reactionWheels`). |
| *(RCS thrust-class variants)* ⟳ | — | 275/413/550/890 N RCS blocks (improvedFlightControl + earlyDocking, ~20) | NOT kings — ride-along thrust classes of spine `gnc_rcs`; the breakthrough is the storable hypergolic propellant (see B). |

## E. Telecommunications

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Parabolic High-Gain Reflector** | `ca_argo-mk2-hga` (Mariner HGA) | 23 antennas: HighGainAntenna, RelayAntenna*, dish_deploy_*, nfex dishes, restock, Gemini/Surveyor/Luna antennas | `disc: Telecommunications` (library `tel_cassegrainHGA`). Steerable dish that closes the interplanetary link. Spine only had omni telemetry. |
| ~~Electronically-Steered Phased Array~~ **DROPPED** | — | nfex-antenna-phased-array-1/2/3, phased-single-3 | **NOT a breakthrough** — all 4 are mod `NearFutureExploration`, anachronistic for 1966. → REFERENCE ride-along on the HGA node (or cut). |

## F. Structures & Mechanisms

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Orbital Docking Mechanism** | `ROC-AgenaPort` + `ROC-GeminiNoseconeBDB` | ROC-AgenaFairing, dockingPort3 | `disc: Structures` (library `str_dockingProbeDrogue`). Gemini-Agena first docking. |
| **Electric Servo Actuators** | `rotoServo_03` / `hinge_03` | 20 Breaking-Ground robotic parts (hinges/pistons/rotors/servos) | `disc: Robotics` (library `rob_servoActuators`). One king abstracts the whole robotic-parts pile. |
| **Touchdown Energy Absorption** | `landerCabinSmall` (Mk1 Lander Can) | ShieldCapLarge; airbag = the Luna-9 alt (see A) | `disc: Structures` (library `str_landingLegs`). |
| **Rover Wheels / Chassis** | `roverWheel1` (RoveMax) | roverWheel2, KF-WheelSmall/Tiny | `disc: Robotics`. Minor; Lunokhod/rover lineage. |
| *(misc)* | — | ROE-120XDecoupler, controller1000 (KAL), fuelLine | plain ride-alongs. |

## G. Composite Materials — Thermal Protection

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Lunar-Return Ablative Heatshield** | `ROC-ApolloHSBDB` (Apollo CM AVCOAT) | ROC-GeminiHSBDB, ROC-GeminiHSLunarBDB (+ GeminiHS/EarlyLunarHS upgrades) | `disc: CompositeMaterials` (library `cmp_ablativeTPS`/`cmp_pica`). Reentry from lunar velocity. |

## H. Life Support

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **EVA Mobility** | `evaJetpack` | evaCylinder; kerbalism ECLSS/lifesupport modules | `disc: LifeSupport` (library `life_suitEVA`). ⚠ crewed scope. |

## I. Science instruments (the interplanetary-era science — education heroes)

| Breakthrough | KING(s) | ride-along tail | notes |
|---|---|---|---|
| **Imaging Spectrometry** | `RO-IRIS` (IR Interferometer Spectrometer) | — | `disc: OpticsPhotonics` (library `opt_spectrometry`). Composition-at-a-distance; Nimbus/Voyager IRIS. |
| **Infrared Radiometry** | `RO-IRRadiometer` (IR01) | `RO-HRIRRadiometer` (IR02) | `disc: OpticsPhotonics`/Thermo. |
| **Helium Magnetometry** ⟳ | `RO-HeliumMagnet` (MG02) | — | successor to spine magnetometer on `str_booms`; the vector field instrument. |
| **Scintillation Cosmic-Ray Telescope** ⟳ | `RO-ScintillationCounter` (CR02) | `RP0Cherenkov` (CD01) | successor to spine `nuc_geiger`. |
| **In-Situ Surface Sampler** | `RO-SurfaceSampleScoop` (Surveyor soil scoop) | — | `disc: Robotics`/science. First surface-mechanics experiment. |
| *(imaging/spec successors)* ⟳ | — | `RO-BasicTVCamera` (VI02→spine `opt_vidicon`), `RO-ImprovedFilmCamera` (PH03→`opt_filmReturn`), `RO-MIMS` (MS02→`mic_massSpec`), gravimeters | extend existing spine science lanes. |

---

## Tally
~**23 breakthroughs**, ~**28 king parts** (main tree). The 14 named US/Soviet probes route to the
**charter subtree** (hire_JPL/hire_OKB), NOT counted here. Of the main-tree kings: **~14 new**; **~9 extend
existing spine nodes** (⟳ hydrolox, kick-solids, RTG, RCS, magnetometer, cosmic-ray, TV/film/mass-spec).
**Scope flags:** Gemini/Voskhod capsules, EVA, J58 jet are in the x-band but belong to the **crewed-orbit /
aviation** milestones — home or defer.

## Resolved (2026-07-01)
- **US/Soviet probes** → charter subtree (special rule); main tree = the enabling breakthroughs only.
- **Phased-array antennas** → DROPPED (NearFuture, anachronistic) → REFERENCE on the HGA node.
- **ORSC home** → **Metallurgy** (ox-rich preburner superalloys).

## Open review questions
1. **Soft-lander two-solutions** now framed at the *descent breakthrough*: `ROE-TD339` throttled vernier ‖
   `ROE-Star37` solid-retro (+ charter Luna-9 airbag). OK, or model it at the mission level instead?
2. **Crewed capsules + EVA + J58 jet** — home now (they're in the x-band) or hold for their own milestones?
3. **Coatl `ca_*` bus/lander cores** vs the RN charter probes — do we even keep the Coatl integrated cores on
   the main tree (as generic buses), or are they redundant with the charter subtree and better cut/parked?
