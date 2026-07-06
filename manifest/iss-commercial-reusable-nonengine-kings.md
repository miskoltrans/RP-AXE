# ISS-Completion → Commercial/Reusable Era — NON-ENGINE KING PARTS

**STATUS: AUTHORED (2026-07-06, commit `5064aac`) — build clean, 356 nodes.** The non-engine axis of
batch 7 (`iss-commercial-reusable`, RP-1 x=-1082..-402), the modern reusable/commercial era (2004–2028+).

## Scope
109 unplaced non-engine parts − **11 owned by the engine pass** = **98 hand-placed** (no RN auto-routes
this batch). Engine-owned exclusions (in `iss-commercial-reusable-engine-kings.md`): `ROE-SuperDraco`/
`SuperDracoDouble` → `gnc_deepThrottlingAbortLandingEngine`; `ROE-MR80B` → `fd_continuousThrottleDescent`;
`ROE-LEROS4` → `gnc_deepSpaceApogeeEngine`; `ROC-OrionESM`/`OrionLAS`/`OrionCover1/2/3`/`CSTRS88` ride the
SuperDraco node; `RAPIER` (SABRE-class spaceplane engine) → engine lane. **12 new nodes + 17 appends.**

Decisions carried from batch 6 (no re-litigation): RN-only charter (non-RN `ca_hera` Juno bus → main-tree
`gnc_flagshipProbeBus`); catalogs sliced fine; science = its own nodes.

---

## New nodes
| Node | tier (parent) | king + folds in |
|---|---|---|
| `life_inflatableHabitat` | T11 (`life_modularHabitat`) | BEAM/Bigelow expandable habs (`sspx-inflatable-hab-*`, `InflatableHAB`, `SXTDLK83EHabitat`, extendable tube) |
| `life_centrifugeHabitat` | T12 (`life_inflatableHabitat`) | **artificial gravity** — inflatable/expandable centrifuges (`sspx-*-centrifuge-*`) |
| `life_largeStationModule` | T11 (`life_modularHabitat`) | 9m/6.75m cores, habs, labs (`sspx-core-5-1` king) |
| `life_aquacultureModule` | T12 (`life_bioregenerativeECLSS`) | aquaculture + 6.75/9m greenhouses — fuller closed food chain |
| `str_annularTruss` | T11 (`str_modularTrussSystem`) | NFC annular/ring truss segments (`truss-circular-*`) |
| `str_strongbackTruss` | T11 (`str_modularTrussSystem`) | SXT Strongback girders (`SXTMTVGirder*`) |
| `str_reusableLandingLeg` | T11 (`str_fixedLanderLegs`) | `largeLandingLeg` — propulsive-recovery booster leg |
| `gnc_nasaDockingSystem` | T11 (`gnc_androgynousDocking`) | NASA Docking System / IDSS (`ROC-CSTNDS*`, `dockingPort1/2/lateral`, `sspx-docking-125-1`) |
| `int_commercialCrewCapsule` | T11 (`int_apolloBlockIII`) | **Orion + CST-100 command/service modules** (king `ROC-OrionCM`) |
| `cmp_inflatableDecelerator` | T11 (`cmp_extremeAtmosphericEntry`) | `ROH-AdjustableHIAD` — inflatable Mars-entry aeroshell |
| `nuc_modernFissionReactor` | T11 (`nuc_thermionicReactor`) | Kilopower/SAFE-400/Prometheus/RAPID-L compact fission power |
| `nuc_fissilePropellantMagazine` | T12 (`nuc_modernFissionReactor`) | FFT fissile-fuel tanks (`fft-fueltank-fission-*`) for advanced nuclear drives |

## Appends (capsule scatter + catalog growth)
- **Commercial-crew scatter** (per scatter-spacecraft doctrine): heat shields `ROC-OrionHS`/`OrionForwardHS`/
  `CSTHS` → `cmp_lunarReturnAblator`; parachutes `OrionParachute`/`CSTParachute` → `edl_crewedRecovery`;
  nose cone `CSTNoseCone` → `cmp_compositeFairingShells`; decoupler `OrionEUSDecoupler` →
  `str_standardDecouplers`; RCS `OrionRCS` → `gnc_bipropAttitudeThrust`; solar `OrionSolar` →
  `elec_matureSolarArrays`.
- **Stations** → `life_pressurizedCrewTubes` (+3 tubes), `life_stationLogistics` (+7 cargo/logistics),
  `life_observationCupola` (+3), `str_stationMountingBases` (+2 adapters).
- **Probe/comms** → `gnc_flagshipProbeBus` (+`ca_hera` Juno bus), `tel_deepSpaceParabolic` (+Juno/MAVEN dishes).
- **Power** → `elec_gphsRTGGeneration` (+MMRTG/ASRG ×4), `nuc_pulsePropulsion` (+Mini-Mag Orion magazines ×2).
- **Science** → `opt_hyperspectralImaging` (+ABI/MSI/MISE), `opt_syntheticApertureRadar` (+PAZ SAR).
- **Reuse** → `rob_heavyWheelDrive` (+`roverWheel3`, `wheelMed`).

## Flags (for veto)
1. **Centrifuge = artificial-gravity node** (`life_centrifugeHabitat`) — new mechanism; kept separate from plain habs.
2. **Commercial capsule scatter** — Orion/CST-100 split across mechanism nodes (capsule body in
   `int_commercialCrewCapsule`, TPS/chutes/decoupler/RCS/solar to their lanes) per scatter-spacecraft doctrine.
3. **FFT fissile tanks** given their own `nuc_fissilePropellantMagazine` (feed future fission/gas-core drives);
   Mini-Mag Orion magazines went to the existing `nuc_pulsePropulsion` (Orion) node.
4. **Engine/non-engine boundary** — 11 parts deferred to the engine pass (SuperDraco etc.); verify that pass authors them so nothing is dropped.
