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

## Remaining band-2 lanes (NOT yet authored)
Satellite science instruments · power/comms/DSN support · the charter nodes.
