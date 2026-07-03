# RP-AXE Band-1 Tech Tree — Handover (2026-07-03)

Paste this (or point me to it) to resume. Full detail lives in the auto-loaded memory files
(`rp-axe-band1-status`, `rp-axe-milestone-tiers`, `rp-axe-tree-*`, `rp-axe-placeholder-parts`).

## State
- **88 nodes, 19 disciplines, build clean, all committed** (latest `148e43c`).
- **SSOT = `tree/nodes.yaml`**, compiled by `tools/build_tree.py`; disciplines in `tree/disciplines.yaml`.
- Band 1 = "to first orbit" + early satellites. **First partlist fully placed** (only intentional defers remain).
- **NEXT = agentic tree review** — rubric in `docs/TREE-REVIEW.md` (failure modes, method, the INTENTIONAL "don't-flag" list, fan-out shape). **Cost pass is DEFERRED until the tree is complete** (user).
- **This pass (2026-07-03) — dependency-hub review + lineage cleanup** (memory `rp-axe-dependency-flags`, `rp-axe-tree-lessons`): split `elec_semiconductorDiode` 7→2 (new `elec_transistor` gate); split prefab structures catalogs (decouplers/adapters/gear); unravelled launch clamps into a 3-tier chain; re-chained aero streamlining off boattail (+ buried stamped-wings behind it as a stock tax); split imaging into film vs TV recon; re-rooted the rocketplane lane onto `fd_injectors` (X-1→X-2→X-15). Accepted hubs: transistor ~5, wing ~5, structural 4.

## Build / commit loop
1. Edit `tree/nodes.yaml` — a node is `{id, title, discipline, tier, parents, flavor, parts | upgrades | grants, anyToUnlock?}`.
2. `python tools/build_tree.py` — must print `design checks: clean`. It regenerates the game cfg + `tree/render/axe-tree.png`.
3. Commit granularly (one logical change per commit).
- Big/precise edits: a `python3 << 'PYEOF'` string-surgery heredoc with `assert`-guarded replaces is the reliable pattern (avoid matching em-dash `—` flavor text; anchor on titles/ASCII).

## The tree (lanes)
- **Roots:** `start` (1950 baseline — de Laval nozzle, procedural airframe **+ early B9 wing (fly turn 1)**, tank/avionics, first instruments, sounding motors ORM-65/TinyTim), `parking`, `hire_JPL`/`hire_OKB` (probe-pack charters, hide_empty).
- **Engine spine** (PropChem→FluidDynamics): storables/solids → **turbopump (V-2, `anyToUnlock`: feed OR combustion route)** → single-chamber → **Combustion-Instability Damping (West)** ‖ **Parallel Engine Clustering (Soviet R-7)** ‖ multi-chamber storable → High-Expansion Vacuum Nozzles. Verniers branch for TVC.
- **Hydrolox gamble** (Cryogenics): `cryo_hydrogen` **empty T1 commitment gate (INTENTIONAL — costs program time; do NOT dissolve)** → weak prototype T2 → RL-10 expander T4.
- **Materials** (Metallurgy): welded → austenitic stainless → Nimonic; feeds tanks (Structures) + engines + jet turbines (crossover). Tank mass-fraction: welded → isogrid ‖ balloon monocoque.
- **Structures:** `str_structuralHardware` "Riveted Airframe Structure" = load-bearing foundation → staging, gear, adapters, launch clamps. Procedural is default; fixed catalogs are **opt-in DEAD-ENDS** off their king: decouplers (staging → radial T3 → stack T4), adapters (procedural king T2 → `Prefabricated Adapters` T3), gear (`Oleo-Strut` stock T2 → `Adjustable Heavy` KF T3), + `Interchangeable-Part Manufacture` RCS. Functional **launch clamps unravel T2→T4**: `Launch Hold-Down Clamps` → `Radial Hold-Down Clamps` → `Swing-Arm Hold-Downs` (+ umbilical). `ReleaseValve` drain valve → welded-tank; nose cones → aero streamlining chain.
- **Aero:** bare procedural wing at `start`; control surfaces + all-moving tail at `aero_subsonicWing` "Subsonic Aerodynamics" = the aero lane root (intakes + control) → recovery T2, **Swept-Wing Planform** supersonic T3, and the streamlining chain **boattail T2 → payload fairing T3 → {composite fairings ‖ prefab nose cones} T4**. `Stamped Aerofoil Panels` (stock-wing catalog) is buried at T3 **behind boattail as a deliberate stock-parts tax** (gating, not lineage).
- **AirBreathing:** piston → centrifugal → axial → afterburner ‖ variable-stator → ramjet (supersonic jets depend on aero swept-wing/shock-cone).
- **Rocketplanes** (FluidDynamics branch, off `fd_injectors` — a rocket needs injectors, NOT the wing): `Chamber-Staged Aircraft Rocket` X-1 T2 → `Throttle-Valve Aircraft Rocket` X-2 T3 → `Throttleable Restartable Rocket` X-15 T5. Clean family line, no crossover (the Stentor edge was false — different propellant/mechanism).
- **Science:** basic 1950 instruments T1 (geiger, film, thermo/baro, biology). Solid-state split: `elec_semiconductorDiode` T2 (junction/power — lights, silicon PV) → **`elec_transistor` "Transistor Amplification" T3 gates the signal instruments at T4** (vidicon, mass-spec, magnetometer, stable-platform guidance, rotor actuation). **Imaging** runs film-first-then-electronic: `film-return` T1 (PH01+PH02) → `film-recon` T3 (PH03+PH04, **pure optics, no transistor**) → `vidicon` T4 (×transistor) → {`TV-recon`, `IR remote-sensing`} T5. `cosmic-ray` T3 off Geiger (vacuum-tube coincidence, **not** transistor-gated). Deep-space instruments PARKED for band 2.
- **Avionics** (GuidanceControl grants-ladder, Science-Core tiers): gyro autopilot → analog inertial → **transistorized stable-platform T4 (× `elec_transistor` crossover)**.
- **LifeSupport:** biology exposure; `life_pilotedCockpits` "Pressurized Cockpit" T2 off `met_weldedTank` (pressure-vessel lineage) — crew accommodation, the front of cockpit→cabin→capsule.
- **Ground Support** (own discipline): the complete MLP inventory as **one straight line T1 Sounding-Rocket Stands → T7 Shuttle** (Saturn T6 + Shuttle T7 = reference/future). Functional launch clamps live separately in Structures.

## Design rules (FOLLOW THESE — hard-won)
0. **GROUND-TRUTH FIRST — the id lies, the title tells the truth.** Read the real part title/config in `manifest/curated-parts.tsv` before you place or judge a part; never infer function from the id. (Caught `science_module` = "PH01 Early Film Camera" mis-homed in atmo-sounding.)
1. **TIER = tech generation** (not thrust or RP-1 calendar). `start` → T1 only; multi-tier jumps flagged.
2. **One start-child per discipline** (PropChem excepted). **T1 = the first improvement *beyond* the `start` baseline**, never the baseline itself (start already embodies basic engines/propellant/injector/nozzle — so a "nitration chemistry" foundation node would be backwards).
3. **Scatter-by-difficulty:** a part homes at its *bottleneck* breakthrough, not its fuel/role.
4. **Upgrades home on a SEPARATE enabler node** (thrust→alloy, Isp→injector), never the base part's node; the enabler can be a different discipline and a lower tier; gated `(enabler AND base)`.
5. **Naming = the breakthrough a landmark PAPER would be titled** — mechanism/effect, never artifact ("cockpit") or capability ("orbital-class thrust"). No "X & Y" compound names (unless the field is really named that: GN&C).
6. **Lineage** (every parent→child edge) must read as real **"X led to Y" OR "same family."** TEST: say the edge aloud as that sentence — if it's false, fix or re-home (caught piston→rocketplane, peroxide-Stentor→LOX-XLR25, monocoque→1950s-cockpit). **But distinguish lineage from GATING:** a semantically-weak edge can be an intentional economic tax (bury stock/catalog parts deep) — label which lever you pull.
7. **Procedural is the DEFAULT;** fixed-catalog variants → opt-in DEAD-END nodes (nothing depends on them).
8. **≤6 parts/node, one clear king;** utility catch-alls (structural/MLP/ground-support) exempt; **science ≠ utility** (finest curation).
9. **`anyToUnlock` for fun** (a milestone reachable via multiple routes); **crossovers** (a breakthrough needing two lanes — turbopump=feed×combustion, Nimonic=rockets+jets, science×electronics, guidance×electronics) are prized — the user wants MORE.
10. **No do-nothing convergence gates** — the vehicle is what you BUILD. Exception: deliberate *commitment* gates that cost program time (cryo_hydrogen).
11. **Propose before big placements; names always veto-able; commit granularly.** The user writes C# too — small purposeful `AXE.dll` modules are fine.

## Open threads / next
- **Add ScanSat parts** (orbital-scanner remote-sensing → `opt_remoteSensing` T5 lane; may need pulling into `manifest/curated-parts.tsv` first).
- **Balance / propulsion deep-look** (T2 was de-bulged 26→23; propulsion "balanced but look deeper" per user).
- **Avionics 8↔13 tier map + DSN nodes** (`grants:` currently a STUB emitting partUpgrade — real plugin/facility hookup TODO).
- **Cost pass** — DEFERRED until the tree is complete (user). tier_cost weights + the hydrolox-overtakes-kerolox lever; NB the diode→transistor split pushed signal instruments to T4 and recon/IR to T5 (cost ~doubled).
- **Band 2** — appsats → humans ‖ lunar probes. **Strays re-home here:** ladders ×8, decals ×5 (park), probes ×5 (Sputnik/Vanguard/Pioneer → charter), X2CockpitUpgrade, crew-access/Saturn/Shuttle MLP (best-guess placed, refine).

## Intentional defers (NOT bugs)
Ladders, decals, deep-space science instruments (Galileo/Magellan/IRIS/NIMS/PMIRR/plasma-wave/scanners), the parked partlist tail — all band-2. `cryo_hydrogen` empty gate — intentional.
