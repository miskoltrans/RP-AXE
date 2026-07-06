# Modular Stations, Rovers & ISS-Assembly Era — NON-ENGINE KING PARTS

**STATUS: PROPOSAL (2026-07-06) — nothing authored yet.** The non-engine axis of batch 6
(`modular-stations-rovers`), the pass after its engine kings (authored, `0f232cd`). Design record for
the stations, probes, science, comms, ISRU, power, thermal, docking and spaceplane parts.

## Scope — ground-truthed by pack, not guessed
Of the 140 unplaced curated non-engine parts:
- **26 auto-route to the charter subtree** and are NOT hand-placed. `build_tree.py:route_probe_mods`
  routes every part whose `curated-parts.tsv` pack column is `RN_US_Probes`/`RN_Soviet_Probes` into
  `hire_JPL`/`hire_OKB`. That covers the integrated RN deep-space probes + EOS sats: Cassini/Galileo/
  Magellan/NEAR/Ulysses/Stardust/Dawn/Deep Impact/DS1/MESSENGER/New Horizons, EOS Aqua/Aura/Terra/TDRS,
  the Galileo dishes and the `rn_huygen_hs_*` heat shields. **Nothing to do — already contained.**
- **≈114 hand-placed**, and the batch is dominated by **catalogs** (57 station parts) + a small tail of
  fine-curation science instruments (12) + a few genuinely new nodes.

Method as ever: real function from the part **title** (rule 0), grouped by mechanism, ≤6 parts/node with
one king *except* utility catalogs (stations/trusses), **science = finest curation**. Tiers are PROPOSALS;
this era is contemporaneous with the engine batch (≈1986–2010) so non-engine parts land **T9–T12**,
continuing existing T7–T9 frontiers.

---

## A. Station habitation & logistics — SSPX modules (34 parts) → **LifeSupport**
Continues `life_stationHabitation` (T8) → `life_habitatModuleCatalog` (T9). The SSPX set is a utility
catalog (cap-exempt), split by **function**, not size:

| Node (proposed) | tier (parent) | king + folds in |
|---|---|---|
| 🆕 `life_modularHabitat` | T10 (`life_habitatModuleCatalog`) | **king `sspx-core-1875-1` (3.38m Station Core)** + habitation modules (`sspx-habitation-25-1/-375-2`), pressurised crew tubes (`sspx-tube-*`, `sspx-extendable-tube-25-1`), science module (`sspx-science-1875-1`). The modern rigid pressurised station module. |
| 🆕 `life_stationLogistics` | T10 (`life_modularHabitat`) | **king `sspx-cargo-25-1` (Storage Module)** + all `sspx-cargo-*`/`sspx-cargo-container-*`/radial cargo + `sspx-lab-pallet-1/2` (external stowage). Pressurised + unpressurised resupply/logistics catalog. |
| 🆕 `life_bioregenerativeECLSS` | T11 (`life_openLoopECLSS` × `life_modularHabitat`) | **king `sspx-greenhouse-25-1` (Greenhouse Module)** + `sspx-cupola-greenhouse-125-1`. Real closed-loop step: growing food/recycling air is a genuine ECLSS breakthrough, not just a module. |
| 🆕 `life_observationCupola` | T10 (`life_modularHabitat`) | **king `sspx-cupola-1875-1` (Observation Module)** + `sspx-cupola-125-1`, `sspx-airlock-25-1` (service airlock w/ NASA docking). Crew observation + EVA egress. (`sspx-cupola-telescope-125-1` telescope dome → **OpticsPhotonics**, region I.) |

## B. Station structure — trusses, hubs, adapters (NFC 23 + Squad/Ven hubs) → **StructuresMechanisms**
Continues `str_stationStructures` (T8) → `str_externalTrussStructure` (T9). Utility catalog (cap-exempt):

| Node (proposed) | tier (parent) | king + folds in |
|---|---|---|
| 🆕 `str_modularTrussSystem` | T10 (`str_externalTrussStructure`) | **king `truss-octo-01` (Octo-Girder Modular Truss XL)** + the whole Octo-Girder family (`truss-octo-*`: sizes, angled, hubs, adapters, docking, pressurised crew trusses) + Spinal trusses (`truss-spinal-*`). The bolt-together ISS-assembly truss kit. |
| 🆕 `str_stationHubsAndBases` | T10 (`str_modularTrussSystem`) | **king `stationHubLarge` (XL HubMax)** + `stationHub`, SSPX hubs (`sspx-hub-125/1875/25-1`), radial attach (`sspx-attach-25/375-1`, `truss-octo-attach-01`), adjustable base frames/cradles (`sspx-adjusting-base-*`). Multi-point connectors + mounting. |

## C. Station docking & berthing (APAS/CADS/CBM + linear connectors) → **GuidanceControl**
Continues `gnc_rendezvousDocking` (T8) → `gnc_stationBerthing` (T9):

| Node (proposed) | tier (parent) | king + folds in |
|---|---|---|
| 🆕 `gnc_androgynousDocking` | T10 (`gnc_stationBerthing`) | **king `APAS89-95` (APAS-89/95)** — the real androgynous port that mated Shuttle–Mir–ISS — + `ROC-APAS8995Av2/Pv2` (active/passive), `ROC-ApolloCADSActive/Passive`, `dockingPortLarge` (Common Berthing Mechanism), `docking-linear-1/2` (linear connectors). The androgynous/berthing breakthrough past gendered probe-drogue docking. |

## D. Station attitude — large reaction wheels → append `gnc_largeReactionWheels` (T9)
`asasmodule1-2` (Advanced Reaction Wheel Module, Large) + `restock-reactionwheel-radial-1` (Radial
Reaction Wheel Large) — same large-class-CMG breakthrough already there. **No new node.**

## E. Station thermal — EATCS radiators → append `th_pumpedLoopRadiators` (T9)
`foldingRadLarge/Med/Small` (EATCS Retractable Radiators) — the ISS active-thermal-control radiators,
exactly this node's pumped-loop-radiator mechanism. **No new node.**

## F. ISRU & propellant production (Kerbalism 5) → **LifeSupport** (new lane)
No ISRU node exists yet. This is the first:

| Node (proposed) | tier (parent) | king + folds in |
|---|---|---|
| 🆕 `life_isru` | T10 (`life_openLoopECLSS`) | **king `kerbalism-ISRU` (ISRU)** + `kerbalism-miniISRU`, `LiquefactionArray`, `Liquifier`, `kerbalism-chemicalplant`. In-situ resource extraction + cryogenic liquefaction + chemical processing — the propellant/consumables-from-the-ground breakthrough that underwrites long-duration and surface missions. |

## G. Space fission reactor power (TOPAZ ×2) → **NuclearEngineering / ElectricalPower**
Continues `nuc_fissionReactor` (T8, the SNAP reactors):

| Node (proposed) | tier (parent) | king + folds in |
|---|---|---|
| 🆕 `nuc_thermionicReactor` | T9 (`nuc_fissionReactor`) | **king `RO-reactor-TOPAZII` (TOPAZ-II)** + `RO-reactor-TOPAZI`. Thermionic direct-conversion space fission reactors — the kilowatt-class step past SNAP thermoelectric, real Soviet flight hardware (TOPAZ-I flew on Cosmos). |

## H. Solar & Apollo-block upgrades (ROCapsules 8) → scatter
- `ROC-ApolloSolarBlockV` (Apollo Block V Solar Array) → append `elec_probeBusSolarWings`/`elec_matureSolarArrays` (T9/T10) — a deployable array mark.
- `ROC-ApolloMissionModule4` (Block IV Mission Module), `ROC-ApolloSMDBDBlockIV` (Block IV Service Module) → append `int_apolloBlockIII` (T9) — the Apollo block-upgrade continuation. (`STXCANIOT` PPD-H Crew Cabin → same node or `life_modularHabitat`.)
- `ROC-ApolloHGABlockV` (Block V High-Gain Antenna) → **Telecommunications** (region J).
- APAS/CADS docking parts → region C.

## I. Deep-space science instruments (SCANsat 4 + RP-1 4) → **OpticsPhotonics + Microelectronics** (finest curation)
The one region that earns fine, per-instrument curation:

| Instrument | → node |
|---|---|
| `RO-MagellanRadar` (RDRS radar antenna) | append `opt_radarAltimetry` (T7) — Magellan Venus SAR, the radar-mapping king |
| `scansat-multi-modis-1` (MODIS), `scansat-resources-crism-1` (CRISM), `scansat-resources-hyperion-1` (Hyperion) | 🆕 `opt_hyperspectralImaging` (T10, parent `opt_multiSpectralImaging` T7) — hundreds-of-band hyperspectral scanning, a real step past multi-spectral |
| `RO-VIMS` (IR mapping spectrometer), `RO-PMIRR` (pressure-modulated IR radiometer) | append `opt_infraredInterferometry`/`opt_irRadiometry` (T7/T6) — Cassini/Mars IR spectro-mapping |
| `RO-HIRES` (high-res imaging) | append `opt_digitalImaging` (T9) — solid-state high-resolution imager |
| `OrbitalScanner` (M4435 narrow-band), `SurfaceScanner` | append `opt_orbitalMapping`/`opt_remoteSensing` (T6/T5) — SCANsat resource/terrain scanning |
| `RO-RPWS` (radio & plasma-wave science) | append `mic_plasmaWave` (T8, Microelectronics) — Cassini RPWS, exactly this node |

## J. Deep-space comms dishes (Coatl 3) → **Telecommunications**
`dish_S` (Ulysses), `mer_dish` (Cassini), `dish_xihe` (STEREO) → append/continue `tel_largeApertureReflectors`
(T9) or a thin 🆕 `tel_deepSpaceParabolic` (T10) — the big steerable deep-space HGA dishes.

## K. Heavy transport airframe (SXT An-124 6 + Squad MK1) → **StructuresMechanisms / AirBreathing**
| Node (proposed) | tier (parent) | king + folds in |
|---|---|---|
| 🆕 `str_heavyTransportAirframe` | T8 (`str_aircraftAirframe` T6) | **king `SXTOsualHullLarge` (An-124 Hull)** + An-124 cockpit/tail/radial hull parts (`SXTOsaul*`), `MK1IntakeFuselage`. The strategic-airlift airframe class (An-124/C-5) — big-fuselage catalog, dead-end off the monocoque airframe. |

## L. Integrated probe/appsat buses + Huygens components (Coatl 9 + Squad 1) → **CHARTER SUBTREE** ⚠ decision
Not covered by `route_probe_mods` (they're `CoatlAerospace`/`Squad` pack, not `RN_*`). These are integrated
spacecraft, so per the batch-3 doctrine (buses → charter, not main-tree kings) I propose **new era-tiered
charter packs off `hire_JPL`**, mirroring `charter_usEarly`→`charter_usApp`:
- 🆕 `charter_earthObservation` (T10, parent `charter_usApp`) — `RO_boeing702` (Boeing 702 comsat bus),
  `ca_ESM2` (LM900 bus), `xihe` (STEREO bus), `tatsujin` (LM-DS bus). The operational GEO-comsat / earth-obs
  bus generation.
- 🆕 `charter_flagshipProbes` (T11, parent `charter_earthObservation`) — `meridiani` (Cassini bus),
  `ca_mer_leu` (Cassini LEU), and the **Huygens descent probe** components (`ca_draco` lander, `ca_draco_as`
  aeroshell, `ca_draco_hs` heat shield, `ca_draco_drogue`/`ca_draco_parachute` chutes, `mer_ringDecoupler`
  adapter). The flagship-class interplanetary probe programme.

**Alternative (flag):** instead of hand-authored charter packs, add `CoatlAerospace` to `route_probe_mods`'s
`PROBE_SUBTREE` map — one line, auto-contains them flat on `hire_JPL` like the RN packs (loses era-tiering).

---

## New-node tally (proposal): ~13 new nodes + ~7 appends + 2 charter packs
New: `life_modularHabitat`, `life_stationLogistics`, `life_bioregenerativeECLSS`, `life_observationCupola`,
`str_modularTrussSystem`, `str_stationHubsAndBases`, `gnc_androgynousDocking`, `life_isru`,
`nuc_thermionicReactor`, `opt_hyperspectralImaging`, `tel_deepSpaceParabolic`, `str_heavyTransportAirframe`
(+ the 2 charter packs).
Appends: `gnc_largeReactionWheels`, `th_pumpedLoopRadiators`, `int_apolloBlockIII`, `elec_matureSolarArrays`,
`opt_radarAltimetry`, `opt_infraredInterferometry`, `opt_digitalImaging`, `opt_orbitalMapping`, `mic_plasmaWave`.

## Open questions (before authoring)
1. **Probe routing (region L)** — hand-authored era-tiered charter packs (recommended, matches batch-3), or
   the one-line `route_probe_mods` extension (simpler, flat, no era-gate)?
2. **Station catalog granularity** — 4 LifeSupport + 2 Structures nodes for the 57 station parts as proposed,
   or coarser (e.g. fold logistics into habitat)? Cap-exempt either way.
3. **Huygens components** — bundled into the flagship-probe charter pack (proposed), or scattered into
   mechanism nodes (heat shield → TPS, chutes → recovery)? The rest of Huygens (`rn_huygen_hs_*`) already
   auto-routes, so bundling keeps the probe together.
4. **`tel_deepSpaceParabolic`** as its own T10 node vs just appending the 3 dishes to `tel_largeApertureReflectors` (T9)?
