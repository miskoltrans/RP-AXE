# RP-AXE Band 2 — Tech Tree Design

Band 2 = **appsats → humans ‖ lunar probes**, the ~1958–61 era. Tier band **T4→T6** (a 3-generation
arc ending at the crewed climax). Fence: T1/T2 off-limits, T3 read-only (parent onto, don't edit),
new nodes land T4–T6. Partlist = `manifest/human-orbital-partlist.tsv` (RP-1 buckets = reference only;
taxonomy re-derived from parts). Decisions: crewed lane = **parallel Mercury ‖ Vostok**; appsats/probes
= **charter nodes** (empty start → first-sats T4 → rest in last node); crossovers **sparingly**.

## Sign-off status
Convention: everything in the tree **before commit `e912eeb`** (the 88 band-1 nodes) is **SIGNED OFF** —
do not re-litigate. New band-2 nodes are **PENDING** until the user signs them off; tracked here.

**Pending review — engine spine (16 nodes, authored `e912eeb`, revised in the naming/upgrade pass):**
- [ ] `pc_ntoHypergolics` `pc_htpSustainer` `pc_larchPeroxide` `pc_fluorine` `pc_scoutSolids` `pc_strapOnSolids` `pc_retroKick`
- [ ] `fd_regenCooling` `fd_vacuumExpansion` `fd_restartableUpper` `fd_spacecraftPropulsion` `fd_storableSustainer` `fd_titanTandem` `fd_longMarchStorable` `fd_sovietStorable` `fd_saturnKerolox`

**Pending review — aviation tail (7 nodes):**
- [ ] `met_cooledTurbine` (enabler, 15 jet uprates) · `av_turboprop` · `av_hydrogenJet` (× `cryo_hydrogen`) · `av_highTempTurbojet` · `av_ramjetAdvanced` · `aero_variableIntake` · `str_heavyGear`

**Pending review — crewed spine (9 nodes):**
- [ ] T5 subsystems: `cmp_ablativeTPS` · `life_openLoopECLSS` · `gnc_spacecraftRCS` · `life_pressurisedCabin` · `int_launchEscape`
- [ ] T6 vehicles: `int_mercuryCapsule` · `int_vostokCapsule` · `int_zenitRecon` · `edl_crewedRecovery` — OPEN: keep "Capsule" in the 3 vehicle names, or drop to pure "…Reentry"?

**Pending review — science (1 seed + 3 progression gates):**
- [ ] `opt_orbitalMapping` (SCANsat MapTraq seed)
- [ ] `opt_irRadiometry` (IR02) · `opt_twoChannelIR` (IR03, heavier req: +thermal) · `opt_uvSpectrometry` (IS02) · `opt_refinedTV` (VI03) — numbered-family gates at T6

**Pending review — charter (era-tiered, 3 pack nodes):**
- [ ] `hire_JPL`/`hire_OKB` (T1 entries) → `charter_usEarly` (T4) → `charter_usApp` (T5) · `charter_sovietEarly` (T4)

**Pending review — support (5 nodes):**
- [ ] `elec_deployableArrays` (solar) · `gnc_basicAvionics` (grants Science-Core-basic) · `tel_dopplerRanging` (DSN L2) · `tel_pcmTelemetry` (DSN L3 + helical) · `str_equipmentBays` (service bays + US tank + Mk18)

## Engine spine (DONE — 16 nodes, T4→T6)

The 1958–61 propulsion cohort. **Homed by propellant, not the RealFuels disc tag.** Two transitions
drive it — storable hypergolics (UDMH+NTO) scaled to booster size, and kerolox uprating toward Saturn-I —
plus the peroxide (Larch) and liquid-fluorine side-stories. **Upgrades are parts:** the ~50 `RFUpgrade_*`
configs home on the ENABLER breakthrough that allowed each uprate — and **never on the base part's own
node** (doctrine #4; verified by `scratchpad/check_upg.py` = 0 violations).

### Enabler nodes (upgrades only)
| Node | Title | Tier | Parent |
|---|---|---|---|
| `pc_ntoHypergolics` | Dinitrogen-Tetroxide Oxidiser | 4 | `pc_hypergolics` |
| `pc_larchPeroxide` | Refined Peroxide Combustion | 6 | `pc_htpSustainer` |
| `fd_regenCooling` | Regenerative Chamber Cooling | 4 | `met_nimonic` |
| `fd_vacuumExpansion` | Extended Vacuum Expansion | 6 | `fd_matureOrbital` |

### Part nodes (base engines; may carry non-conflicting uprates)
| Node | Title | Tier | Parents | King / parts |
|---|---|---|---|---|
| `fd_restartableUpper` | Restartable Vacuum Ignition | 4 | `pc_hypergolics` | Agena (+ AJ10-Mid, Juno 45K/6K) |
| `fd_spacecraftPropulsion` | Restartable Deep-Throttling | 5 | `fd_restartableUpper` | Agena-SPS, KDU-414, Ranger-retro |
| `pc_htpSustainer` | Multi-Chamber Peroxide Combustion | 4 | `pc_stentor` | Gamma 2/8 |
| `pc_fluorine` | Liquid-Fluorine Oxidiser *(gamble)* | 6 | `pc_hypergolics` | G-1 (hydrazine+F₂, Isp 357) |
| `fd_storableSustainer` | Storable Single-Chamber Combustion | 4 | `fd_singleChamber` | Viking 2/4/5, YF-3 |
| `fd_titanTandem` | Altitude-Start Tandem Staging | 5 | `fd_largeChamber` | LR87 ×3, LR91 ×2 |
| `fd_longMarchStorable` | Storable Chamber Clustering | 5 | `fd_orbitalMultiChamber` + `pc_ntoHypergolics` | YF-21 (CZ-2), YF-20/22/23/25 |
| `fd_sovietStorable` | Storable Tandem Staging | 5 | `fd_orbitalMultiChamber` + `pc_ntoHypergolics` | RD-215/219, RD-855/856 |
| `fd_saturnKerolox` | High-Pressure Kerolox Combustion | 6 | `fd_largeChamber` | H-1/RS-27, RD-111 → Saturn ref |
| `pc_scoutSolids` | Staged Solid Boost | 4 | `pc_compositeSolid` | Algol, Antares, Altair (+Castor uprates) |
| `pc_strapOnSolids` | Strap-On Thrust Augmentation | 4 | `pc_compositeSolid` | Castor (Thor→Delta) |
| `pc_retroKick` | Vacuum-Start Solid Impulse | 4 | `pc_compositeSolid` | Mercury retro (deorbit = coming home) |

**Upgrade re-homing (naming/rule pass, after `e912eeb`):** Larch uprates → new `pc_larchPeroxide`
(off Gamma parts); Castor SL/Vac → `pc_scoutSolids` (off the Castor part); Agena `XLR81-BA-5/7`
(UDMH) → `pc_ntoHypergolics`, `BA-1/3` (restart-life) → `fd_spacecraftPropulsion` (off the Agena part).

**Already-placed band-2 engines** (band 1 pulled forward — not duplicated): RD-0105/0110/0109, XLR99,
RZ, X-405H. **Parked:** YF-21 CZ-2/2C/2D boattail shells. All nodes ≤6 base parts (ideal 3).

## Aviation tail (DONE — 7 nodes, T4→T6)
Extends band-1's AirBreathing/Aerodynamics lanes (most jets already placed there). `met_cooledTurbine`
(Metallurgy, T4, off `met_nimonic`) is the enabler holding the ~15 jet uprates — mirrors how `met_nimonic`
already feeds T4 jets, so an enabler below its base engines is fine (config needs enabler AND base).
New engines: `av_turboprop` (NK-12/PT6), `av_highTempTurbojet` (Atar-09/R-11/J85, T5), `av_hydrogenJet`
(Model 304, gated on `cryo_hydrogen`), `av_ramjetAdvanced` (RD-012 + RJ43 uprates, T6). Plus
`aero_variableIntake` (adjustable ramp) and `str_heavyGear` (LY-60/99, continues the gear lane).

## Crewed spine (DONE — 9 nodes, T5→T6)
Subsystems @ T5 feed parallel Mercury ‖ Vostok vehicles @ T6. `cmp_ablativeTPS` (CompositeMaterials —
first node in that discipline), `life_openLoopECLSS`, `gnc_spacecraftRCS`, `life_pressurisedCabin` (X-15),
`int_launchEscape` (tractor motor, off `pc_scoutSolids`). Vehicles: `int_mercuryCapsule` (blunt-body) ‖
`int_vostokCapsule` (spherical), both gated on **TPS × ECLSS**; `int_zenitRecon` is a *sibling* (uncrewed
recon) gated on **TPS × opt_recon** (stays in-band at T6); `edl_crewedRecovery`. Tech-level capability
upgrades (Heatsink, MercuryHS) deferred to a tech-level pass (like solarTL/commsTL).

## Science (DONE — instruments already in band 1 + 1 SCANsat seed)
All five satellite instruments (PH02 film / MG01 magnetometer / VI01 TV / CR01 geiger / MM01
micrometeorite) were already placed in band 1 — no new instrument nodes. Band-2 adds one seed node:
`opt_orbitalMapping` "Synoptic Orbital Scanning" (SCANsat MapTraq, T6, off `opt_remoteSensing`).
`SCANsat_Scanner32` skipped (DEPRECATED); `dmUS2MagBoom`/`dmUS2Scope` deferred (uncurated US2 wedges).
The mapping-lane bulk is in the interplanetary partlist (band 3).

**Numbered-instrument progression (design rule):** every family (PH/VI/IR/IS/MS/MG/CR/WS, `XX##` codes)
is a *tiered gated progression* — `XX01` cheap/early, higher numbers gate above. Bulk in T1–T4; refinements
at T5–T6. IR01 `opt_remoteSensing` (T5) → IR02 `opt_irRadiometry` (T6) ‖ IR03 `opt_twoChannelIR` (T6,
**heavier req** — also `th_hermeticBus` for a thermally-stable detector: the *same-tier-heavier-requirement*
gate for a later instrument when the tier ceiling blocks a clean T7); IS02 → `opt_uvSpectrometry` (T6);
VI02 `opt_tvRecon` (T5) → VI03 `opt_refinedTV` (T6). Band 3 continues each family (IR04, IS01/03/04,
MS02–04, VI04/05, PH05, WS01–03, MG02/03).

**Ullage — open opportunity:** companion to `fd_restartableUpper` (coast-then-relight needs settling). Hardware
already folded into the sep/posigrade solids (`pc_retroKick`, band-1 sep motors), so it'd be a *capability gate*.
Thin in band 2 (short coasts); becomes a real breakthrough in band 3 (lunar/planetary injection). Not yet placed.

## Charter (DONE — era-tiered, 3 pack nodes)
`hire_JPL` (US) and `hire_OKB` (Soviet) are **T1 / cost 300** charter gates (no parts). Spacecraft arrive by
ERA off them — this fixes the mission-feasibility leapfrog (integrated appsats were unlocking at T1, years
before their own instrument lanes):
- `hire_JPL` (T1) → `charter_usEarly` (**T4**: Vanguard 1, Pioneer 0-4, Explorer 6, Vanguard 2/3) →
  `charter_usApp` (**T5**: Tiros-1, Transit-2A, GRAB, Pioneer 5 — now alongside `opt_tvRecon`/`opt_remoteSensing`).
- `hire_OKB` (T1) → `charter_sovietEarly` (**T4**: Sputnik 2/3).
Avionics grants (Science-Core/HDD) belong to the avionics ladder in Support, not here.

## Engine performance audit (role-aware) — PASSED
Every engine hand-tagged by role (`manifest/engine-roles.tsv`, 441 engines, from a second agent). Re-ran the
tier-inversion audit joined on roles: **zero broken inversions**. The one flagged booster-vs-booster case —
US kerolox (H-1 T6, LR87 T5) dominated by the Soviet R-7 (RD-108 T4) — is **ACCEPTED as flavor** (the R-7
genuinely out-performed; `fd_saturnKerolox` is carried by the non-dominated RD-111; H-1's real edge was
cheap mass-production/clustering, which the tree doesn't model). All other hits were flavor (double-base
solids < TinyTim) or non-comparable (kick motors ranked by Isp). `engine-roles.tsv` is a reusable audit input.

## Support (DONE — 5 nodes, T5–T6)
`elec_deployableArrays` (ST1 panel, off `elec_arCoatings`) · `gnc_basicAvionics` (grants Science-Core-basic,
off `gnc_earlyAvionics`) · `tel_dopplerRanging` (DSN L2) → `tel_pcmTelemetry` (DSN L3 + helical antenna) ·
`str_equipmentBays` (service bays 3m/4m, US radial tank, Mk18 nose). Tech-levels placed (solarTL1, commsTL1/2,
HDD-Basic, SM-II); `PFTech-Fairing-II` + `RFTech-Battery-II` deferred (fairing/battery ladders).

## US2 wedges — REVIEW QUEUE (config from RP-1)
5 DMagic Universal Storage 2 science wedges, all were `curated=no` (unconfigured). **Approach: take the
config straight from RP-1** — the rebuild pulls RP-1's `.cfg`; nothing to hand-author.
- **BAND 2 — `curated=yes` + PLACED**: `dmUS2MagBoom` → new `mic_boomMagnetometry` (T5, MG-boom gate off
  `mic_magnetometer`); `dmUS2Scope` → new `opt_precisionOptics` (T5 off `opt_recon`). Resolved from RP-1's
  config (`RP-1/Parts/Science/US2.cfg` + `USScope.cfg`): the "Orbital Telescope" is a long-focal-length
  **surface** imager (scopeScan/KerbNet-Terrain, `hirise` tag), NOT astronomy → recon/optics lane.
- **BAND 3 — still `curated=no`**: `dmUS2RPWS` (RPWS plasma-wave, WS03) · `dmUS2GoreSat` (IR Radiometer,
  IR-family) · `dmUS2ImagingPlatform` (Multi-Spectral Imaging). Mark + place when band 3 is built.

## BAND 2 COMPLETE — 41 new nodes, tree at 129 / 19 disciplines
Engines 16 · aviation 7 · crewed 9 · science 4 · charter (into existing roots) · support 5. All PENDING
sign-off (see checklist above). Deferred within band 2: US2 wedges (uncurated), IR03 finer gate (band 3),
ullage capability gate (band 3), the tech-level `TODO` tuning pass, the cost pass.
