# RP-AXE Band-1 Tech Tree — Handover (2026-07-03)

Paste this (or point me to it) to resume. Full detail lives in the auto-loaded memory files
(`rp-axe-band1-status`, `rp-axe-milestone-tiers`, `rp-axe-tree-*`, `rp-axe-placeholder-parts`).

## State
- **80 nodes, 19 disciplines, build clean, all committed** (latest `5679ce5`).
- **SSOT = `tree/nodes.yaml`**, compiled by `tools/build_tree.py`; disciplines in `tree/disciplines.yaml`.
- Band 1 = "to first orbit" + early satellites. **First partlist fully placed** (only intentional defers remain).

## Build / commit loop
1. Edit `tree/nodes.yaml` — a node is `{id, title, discipline, tier, parents, flavor, parts | upgrades | grants, anyToUnlock?}`.
2. `python tools/build_tree.py` — must print `design checks: clean`. It regenerates the game cfg + `tree/render/axe-tree.png`.
3. Commit granularly (one logical change per commit).
- Big/precise edits: a `python3 << 'PYEOF'` string-surgery heredoc with `assert`-guarded replaces is the reliable pattern (avoid matching em-dash `—` flavor text; anchor on titles/ASCII).

## The tree (lanes)
- **Roots:** `start` (1950 baseline — de Laval nozzle, procedural airframe/tank/avionics, first instruments, sounding motors ORM-65/TinyTim), `parking`, `hire_JPL`/`hire_OKB` (probe-pack charters, hide_empty).
- **Engine spine** (PropChem→FluidDynamics): storables/solids → **turbopump (V-2, `anyToUnlock`: feed OR combustion route)** → single-chamber → **Combustion-Instability Damping (West)** ‖ **Parallel Engine Clustering (Soviet R-7)** ‖ multi-chamber storable → High-Expansion Vacuum Nozzles. Verniers branch for TVC.
- **Hydrolox gamble** (Cryogenics): `cryo_hydrogen` **empty T1 commitment gate (INTENTIONAL — costs program time; do NOT dissolve)** → weak prototype T2 → RL-10 expander T4.
- **Materials** (Metallurgy): welded → austenitic stainless → Nimonic; feeds tanks (Structures) + engines + jet turbines (crossover). Tank mass-fraction: welded → isogrid ‖ balloon monocoque.
- **Structures:** `str_structuralHardware` "Riveted Airframe Structure" = load-bearing foundation → staging/gear/adapters. Fixed catalogs (`Prefabricated Nose Cones/Decouplers`, `Stamped Aerofoil Panels`, `Interchangeable-Part Manufacture` RCS) are **opt-in DEAD-ENDS** (procedural is default).
- **Aero:** `aero_subsonicWing` "Subsonic Aerodynamics" (the wing IS the foundation) → refinements T2 (fairings, recovery, boattail, prefab cones) → **Swept-Wing Planform** supersonic T3.
- **AirBreathing:** piston → centrifugal → axial → afterburner ‖ variable-stator → ramjet (supersonic jets depend on aero swept-wing/shock-cone).
- **Science:** basic 1950 instruments T1 (geiger, film, thermo/baro, biology) → **electronic instruments gated behind the transistor `elec_semiconductorDiode` → T3** (vidicon, mass-spec, magnetometer, cosmic-ray) → recon/IR remote-sensing T4. Deep-space instruments PARKED for band 2.
- **Avionics** (GuidanceControl grants-ladder, Science-Core tiers): gyro autopilot → analog inertial → **transistorized stable-platform (× electronics crossover)**.
- **LifeSupport:** biology exposure; `life_pilotedCockpits` (crew accommodation → the front of cockpit→cabin→capsule).
- **Ground Support** (own discipline): the complete MLP inventory as **one straight line T1 Sounding-Rocket Stands → T7 Shuttle** (Saturn T6 + Shuttle T7 = reference/future). Functional launch clamps live separately in Structures.

## Design rules (FOLLOW THESE — hard-won)
1. **TIER = tech generation** (not thrust or RP-1 calendar). `start` → T1 only; multi-tier jumps flagged.
2. **One start-child per discipline** (PropChem excepted). **T1 = the first improvement *beyond* the `start` baseline**, never the baseline itself (start already embodies basic engines/propellant/injector/nozzle — so a "nitration chemistry" foundation node would be backwards).
3. **Scatter-by-difficulty:** a part homes at its *bottleneck* breakthrough, not its fuel/role.
4. **Upgrades home on a SEPARATE enabler node** (thrust→alloy, Isp→injector), never the base part's node; the enabler can be a different discipline and a lower tier; gated `(enabler AND base)`.
5. **Naming = the breakthrough a landmark PAPER would be titled** — mechanism/effect, never artifact ("cockpit") or capability ("orbital-class thrust"). No "X & Y" compound names (unless the field is really named that: GN&C).
6. **Lineage** (every parent→child edge) must read as real **"X led to Y" OR "same family."** Naming exposes bad lineage — fix or re-home.
7. **Procedural is the DEFAULT;** fixed-catalog variants → opt-in DEAD-END nodes (nothing depends on them).
8. **≤6 parts/node, one clear king;** utility catch-alls (structural/MLP/ground-support) exempt; **science ≠ utility** (finest curation).
9. **`anyToUnlock` for fun** (a milestone reachable via multiple routes); **crossovers** (a breakthrough needing two lanes — turbopump=feed×combustion, Nimonic=rockets+jets, science×electronics, guidance×electronics) are prized — the user wants MORE.
10. **No do-nothing convergence gates** — the vehicle is what you BUILD. Exception: deliberate *commitment* gates that cost program time (cryo_hydrogen).
11. **Propose before big placements; names always veto-able; commit granularly.** The user writes C# too — small purposeful `AXE.dll` modules are fine.

## Open threads / next
- **⏰ FIRST: add ScanSat parts** (orbital-scanner remote-sensing → `opt_remoteSensing` T4 lane; may need pulling into `manifest/curated-parts.tsv` first).
- **Balance / propulsion deep-look** (T2 was de-bulged 26→23; propulsion "balanced but look deeper" per user).
- **HTP T2/T3** confirm (Gamma-T2 / Stentor-T3 split).
- **Avionics 8↔13 tier map + DSN nodes** (`grants:` currently a STUB emitting partUpgrade — real plugin/facility hookup TODO).
- **Cost pass** (tier_cost weights; the hydrolox-overtakes-kerolox lever).
- **Band 2** — appsats → humans ‖ lunar probes. **Strays re-home here:** ladders ×8, decals ×5 (park), probes ×5 (Sputnik/Vanguard/Pioneer → charter), X2CockpitUpgrade, crew-access/Saturn/Shuttle MLP (best-guess placed, refine).

## Intentional defers (NOT bugs)
Ladders, decals, deep-space science instruments (Galileo/Magellan/IRIS/NIMS/PMIRR/plasma-wave/scanners), the parked partlist tail — all band-2. `cryo_hydrogen` empty gate — intentional.
