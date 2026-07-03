# RP-AXE Band 2 — Tech Tree Design

Band 2 = **appsats → humans ‖ lunar probes**, the ~1958–61 era. Tier band **T4→T6** (a 3-generation
arc ending at the crewed climax). Fence: T1/T2 off-limits, T3 read-only (parent onto, don't edit),
new nodes land T4–T6. Partlist = `manifest/human-orbital-partlist.tsv` (RP-1 buckets = reference only;
taxonomy re-derived from parts). Decisions: crewed lane = **parallel Mercury ‖ Vostok**; appsats/probes
= **charter nodes** (empty start → first-sats T4 → rest in last node); crossovers **sparingly**.

## Engine spine (DONE — 15 nodes, T4→T6)

The 1958–61 propulsion cohort. **Homed by propellant, not the RealFuels disc tag.** Two transitions
drive it — storable hypergolics (UDMH+NTO) scaled to booster size, and kerolox uprating toward Saturn-I —
plus the peroxide (Larch) and liquid-fluorine side-stories. **Upgrades are parts:** the ~50 `RFUpgrade_*`
configs home on the ENABLER breakthrough that allowed each uprate (thrust↑→cooling/alloy, Isp↑→nozzle,
propellant swap→chemistry), gated (enabler AND base) — never on the base engine's own node.

### Enablers (hold the uprate configs; some gate the chambers)
| Node | Tier | Parent | Role |
|---|---|---|---|
| `pc_ntoHypergolics` Dinitrogen-Tetroxide Oxidiser | 4 | `pc_hypergolics` | UDMH+NTO chemistry; holds AK27→NTO swaps (YF-1B, YF-3A, RD-214); gates both storable boosters |
| `fd_regenCooling` Regenerative Chamber Cooling | 4 | `met_nimonic` | higher chamber pressure; holds ~21 thrust uprates (LR89-NA-5, RZ.2, LR79, R-7 configs, Viking-4/5) |
| `fd_vacuumExpansion` Optimised Vacuum Expansion | 6 | `fd_matureOrbital` | extended bells; holds Isp uprates (RD-119 +28s, RD-0109, X-405H) |
| `fd_restartableUpper` Restartable Vacuum Ignition | 4 | `pc_hypergolics` | king Agena; coast+relight; holds XLR81-BA-x, AJ10 configs |
| `pc_htpSustainer` Multi-Chamber Peroxide Sustainers | 4 | `pc_stentor` | king Gamma 8; holds Larch-2/4/8 |
| `pc_fluorine` Liquid-Fluorine Oxidiser *(gamble)* | 6 | `pc_hypergolics` | king G-1 (hydrazine+F₂, Isp 357, exotic dead-end) |

### Hardware chambers (gated by lineage [+ enabler])
| Node | Tier | Parents | King / parts |
|---|---|---|---|
| `fd_storableSustainer` Storable Hypergolic Sustainers | 4 | `fd_singleChamber` | Viking 2/4/5, YF-3 |
| `fd_titanTandem` Altitude-Start Tandem Staging | 5 | `fd_largeChamber` | LR87 ×3, LR91 ×2 |
| `fd_longMarchStorable` Clustered Storable First Stage | 5 | `fd_orbitalMultiChamber` + `pc_ntoHypergolics` | YF-21 (CZ-2), YF-20/22/23/25 |
| `fd_sovietStorable` Tandem Storable Booster | 5 | `fd_orbitalMultiChamber` + `pc_ntoHypergolics` | RD-215/219, RD-855/856 |
| `fd_saturnKerolox` Mass-Produced Kerolox Booster | 6 | `fd_largeChamber` | H-1/RS-27, RD-111 → hands to Saturn ref |
| `fd_spacecraftPropulsion` Restartable Course-Correction | 5 | `fd_restartableUpper` | Agena-SPS, KDU-414, Ranger-retro |

### Solids (PropellantChemistry)
| Node | Tier | Parent | King / parts |
|---|---|---|---|
| `pc_scoutSolids` Cast Composite Upper Stages | 4 | `pc_compositeSolid` | Algol (Scout), Antares, Altair |
| `pc_strapOnSolids` Strap-On Thrust Augmentation | 4 | `pc_compositeSolid` | Castor (Thor→Delta strap-on) |
| `pc_retroKick` Vacuum-Start Solid Motors | 4 | `pc_compositeSolid` | Mercury retro (deorbit = coming home); posigrade, Agena retro/spin |

**Already-placed band-2 engines** (band 1 pulled forward — not duplicated): RD-0105/0110/0109, XLR99,
RZ, X-405H. **Parked:** YF-21 CZ-2/2C/2D boattail shells (cosmetic dupes).

All nodes ≤6 base parts (ideal 3). Homing by breakthrough, not chronology. Base configs by propellant &
thrust are in `manifest/engine-stats.tsv`.

## Remaining band-2 lanes (NOT yet authored)
Crewed spine (Mercury ‖ Vostok capsules, ablative TPS, ECLSS, LES, recovery) · satellite science
instruments · power/comms/DSN support · the charter nodes · the aviation tail (jets + jet uprates).
