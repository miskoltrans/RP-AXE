# RP-AXE vs RP-1 — the changelist

What RP-AXE 0.9 changes relative to RP-1 **v4.4.0.0** (the version its vendored config was synced
from, 2026-06-28). AXE runs on the same realism stack (RO / RSS / RealFuels / Kerbalism / RealAntennas
/ TestFlight / FAR …) and **replaces** RP-1's career plugin; it conflicts with RP-1 and never
depends on it. Everything not listed here is RP-1 as-is: the vendored contracts and science configs
load byte-identical from `GameData/RP-AXE/seed/`, and the RO stack's `:NEEDS[RP-0]` tuning still
applies because AXE keeps the `RP-0` ModuleManager flag registered.

Tags: **REMOVED** (RP-1 mechanic, gone) · **REPLACED** (AXE's own design in its place) · **PORTED**
(RP-1 behaviour re-provided without RP0.dll, same rules) · **CHANGED** (ported with a deliberate
difference) · **NEW** (exists in neither RP-1 nor the stack) · **KEPT** (unchanged, listed because
people ask).

Design rationale lives in the docs each section links to; this file is the inventory.

## At a glance

| Area | Status | One line |
|---|---|---|
| Build times (KCT), tooling, maintenance, leaders, crew training, reliability data grind | REMOVED | Timewarp is free; the launch is the only gate |
| Tech tree | REPLACED | 534 discipline-based breakthrough nodes, science-gated, ~300k science total |
| Avionics | REPLACED | Box-sized steerable-mass capacity; overload corrupts control instead of locking |
| Funds economy | REPLACED | 40M lifetime, paid by missions (capstones + program completion) and Administration |
| Programs | REPLACED | Charter contracts, an onboarding DAG, earned conclusion; no funding curves |
| Contracts | PORTED | RP-1's ~370 contract types on AXE's own ContractConfigurator types |
| Science | PORTED + NEW | RP-1's instrument suite + crewed science; KerbalismLab (65) integrated; Orbital Geochemistry added |
| Facilities | CHANGED | Launchpad mass ladder, 11-level DSN, 8-level R&D science cap; VAB/SPH uncapped |
| Simulator, airlaunch, launch-site switching | REPLACED / PORTED / KEPT | Free sim; airlaunch re-authored; KSCSwitcher free |
| Dependencies | CHANGED | RP-1 Express's part set minus RP-1, plus 21 curated part mods; graphics are a Low/High preset choice |

---

## 1. Install and dependencies

- **REMOVED — `RP0.dll`, `CC_RP0.dll`, `RP-1/`, `RP-1-ExpressInstall`.** `AXE.dll` provides what the
  contracts, tree and economy need. The netkan lists `RP-1` under `conflicts`.
- **CHANGED — dependency set.** RP-1 Express's part and realism set minus RP-1, **minus
  LunarTransferPlanner** (TargetInterceptPlanner instead), **plus** the curated expansion: Near Future
  Aeronautics / Construction / Electrical / Exploration / Launch Vehicles / Propulsion / Solar, Far
  Future Technologies, Kerbal Atomics, CryoEngines, Station Parts Expansion Redux, Tantares, Coatl
  Aerospace, RN US + Soviet probe packs, Universal Storage 2, Rocket Motor Menagerie, Kerwis Chinese
  Aerospace Pack, SCANsat, Hullcam VDS. 54 entries in `depends` (one of them the RSS texture-pack
  choice). Tools and graphics ride on the `RP-AXE-Express-RSS-{Low,High}` presets the way they ride on
  RP-1 Express: Low is textures only, High adds Parallax, Scatterer and RSSVE-HR. Unlike RP-1 Express,
  the texture pack is a pre-ticked recommendation (4K on Low, 16K on High), so the player can pick
  another size.
  Both DLCs are suggestions; Breaking Ground is strongly recommended (the Robotics discipline places
  its parts).
- **Evaluated and not added:** DMagic Orbital Science (its instruments duplicate RP-1's), Near Future
  Spacecraft, TantaresLV.
- **KEPT — RO's `HardRemoveNonRO` plausibility floor** (RP-1 Express ships the same flag; ~825
  non-RO parts deleted). **Not used:** `HardRemoveNonRP0` (it would delete nearly everything without
  RP-1's part configs).
- **KEPT — the `:FOR[RP-0]` flag.** Vendored parts carry it, so the ~60 `:NEEDS[RP-0]` patches in
  RO, RealAntennas, KerbalismConfig, ROSolar, ROHeatshields, ROCapsules, MechJeb and Coatl still
  apply. AXE inherits RP-1's RO-stack tuning rather than re-deriving it.
- **CHANGED — RO career enable.** RO forces sandbox unless RP-1 is detected; AXE flips RO's override
  flag by reflection (`Source/AXE/EnableCareer.cs`) instead of impersonating an `RP-0` assembly.
- **PORTED — KSPCommunityFixes toggles.** 4 of RP-1's 8 taken (`AxeCommunityFixes.cfg`);
  `StrategyDuration` refused because it would put an expiry clock on the funds economy.

## 2. The career layer that is gone

All of these lived in RP0.dll / KCT and are **REMOVED** with it (`docs/RESTART.md`, `docs/PROGRAMS.md`):

- **Kerbal Construction Time**: build points, build times, launch complexes and their human-rating /
  propellant provisioning, pad construction and tonnage growth, rollout, reconditioning,
  warp-to-complete, engineer/researcher personnel and their efficiency upgrades, unlock credit.
- **Tooling**: `ModuleTooling*` stripped from every vendored part at `:FINAL`; `ToolingDefinitions`
  not shipped. Its per-build cost is folded into the launch bill (§7).
- **Maintenance and upkeep**: facility maintenance, salaries, the program funding drip (a Hermite
  curve over calendar years), the reputation-scaled yearly subsidy, and **daily reputation decay**
  (~15 %/yr). Every one of these is calendar-driven and would be farmable under free timewarp.
- **Leaders / Strategia**: RP-1 repurposed the Administration building for leaders; AXE gives it
  back to the stock strategies (rescaled, §7). Program confidence is gone with it.
- **Crew**: training courses, proficiency, retirement, training times, Astronaut Complex gating.
  **Cut for good.** Kerbal XP still accumulates in stock fashion and still gates Kerbalism
  experiments that ask for a Scientist level (36 of the 71 KerbalismLab experiments do).
- **TestFlight data grind — CHANGED, not removed.** `AxeAlwaysMaxData` forces "parts always have
  maximum flight data", so reliability sits at each config's rated ceiling from unlock. Failures,
  rated burn time, rated ignitions and per-config ceilings are untouched; reliability improves by
  unlocking better engines, never by static-firing one. RP-1's `TestFlightRnD.cfg` is not vendored.
- **RP-1's Engineer's Report additions** (human-rating gate, GSE resources callout, untooled-parts
  warning) — all three read the KCT launch complex. Stock's report stays; AXE additionally enables
  three stock design-concern tests KSP ships disabled (no control source, parachute on an engine
  stage, seat collision) — `AxeDesignConcerns.cs`.
- **Milestones newspaper, RP-1 localization, agencies, flags, stock craft files** — not ported. The
  Records "First X" contracts still fire.
- **Time pressure in general.** No deadlines, no upkeep, no research time; timewarp is free and
  unlimited. The one calendar term left is Contract Configurator's own `rewardFactor` ramp on
  repeatable contracts, which under free warp degrades to "wait N days between flights".

## 3. Tech tree — REPLACED (`docs/TREE.md`, `tree/nodes.yaml`)

- **534 nodes in 21 lanes** (20 engineering disciplines + a Systems Integration convergence lane),
  tiers 0–16, compiled from `tree/nodes.yaml` by `tools/build_tree.py`. RP-1's era/function nodes
  and `RP0TechTree.cfg` are not shipped.
- **Nodes are breakthroughs, not eras**: research-paper names ("Stellar Attitude Determination",
  "Vacuum Induction Melting"), flavour text on every node, parts homed at the breakthrough that made
  them hard (F-1 under combustion instability, RD-170 under ox-rich superalloys, J-2 under
  cryogenics). A lander is assembled from nodes across the tree.
- **Convergence and multi-entry gates**: `anyToUnlock = False` nodes need every parent; `True` nodes
  take any one. The in-game render draws OR edges dashed.
- **Single rocketry root.** Aviation is an opt-in lane, paid in reputation like everything else, not
  a second start. The RN probe packs hang off two **off-start charter chains** (`hire_JPL` /
  `hire_OKB`, chronological by real flight date); ModularLaunchPads is an off-start Ground Support
  chain.
- **Science is the only progression gate, and it costs ~300k** (RP-1's whole tree ≈ 115k). The
  solar system holds ~3.9M theoretical, so the tree is finished by exploring broadly. Per-tier rate
  table in `docs/SCIENCE.md` §4; the `scalar` dial is 0.72.
- **PORTED — engine progression.** RP-1's `TREE-Engines.cfg` is vendored whole: 462 live
  `RFUpgrade_*` config unlocks + 53 dormant (wake if a mod adds the engine), 15 RealFuels per-type
  tech levels, every `techRequired` remapped to an AXE node. Engine CONFIGs are the backbone of the
  ladder (`docs/UPGRADES.md`, `docs/ENGINE-STATS.md`).
- **CHANGED — upgrades are granted, never sold.** Every `PARTUPGRADE` is `entryCost 0` and is marked
  unlocked the moment its node is researched (`AxeGrantUpgradeUnlock`). RP-1 prices them. Engine
  CONFIGs still cost funds, chained per rung so the first variant carries the lineage
  (`AxeEntryCostMods.cfg`, 449 configs).
- **NEW — the VAB enforces config ownership.** RealFuels' "Switch" button ignored tech and purchase
  state; AXE gates it (`AxeEngineConfigPurchaseGate.cs`). RP-1's engine-stats tooltip on
  `RFUpgrade_*` icons is **PORTED**.
- **PORTED — RP-1's capability keepers**: ProceduralFairings size caps (6), ComSat/NavSat bus levels
  (6), X-2 cockpit ceiling, Kerbalism HDD ladder (10), tank type levels (21), heatshield (6), MLI (5).
  **CHANGED:** the MLI rungs are re-valued to a constant-ratio curve (`AxeMliLadder.cfg`).
- **REPLACED — avionics tier icons.** RP-1's 35 `ProceduralAvionics.cfg` upgrades are superseded by
  AXE's TIER ladder (§4); 23 visible tier tokens + 11 DSN tokens are emitted as `grants` instead.
- **PORTED — procedural sizing**: every ProceduralParts shape from `start` and the PF base diameter
  ungated (RP-1's `ProcSizes.cfg`). **CHANGED:** autostruts unlock when the strut part's node is
  researched (stock/RO point at a tech id that does not exist in AXE's tree).
- **NEW — tech-id remaps for third parties.** Stock/CTT ids that part mods hard-code, Kerbalism's
  life-support / power `Configure` gates (543 refs) and nested MODULE-level gates are all re-homed on
  AXE nodes; `tools/check_tech_refs.py` fails the build on a dangling reference.
- **Parts — CHANGED curation.** 1,826 curated parts on the RO floor (`manifest/curated-parts.tsv`,
  `docs/PARTLIST.md`). RP-1's 215 removals are mostly inherited (187 stock parts); reversed: Kerbal
  Foundries mobility, `proceduralTankOre`, the Saturn IUs. AXE's own cuts (US2 wedges that duplicate
  procedural parts, attitude-control decouplers, …) in `AxeCutParts.cfg`. RP-1's post-2051
  colonisation scaffold (~60 empty tech-gate nodes) is deliberately **not** recreated.
- **PORTED — part-origin tag** ("From X mod") in every description; a Filter Extensions "RP-AXE"
  category marks every part AXE re-homed.
- **NEW — in-game R&D render** (`Source/AXE/RnD`, `RenderSettings.cfg`): discipline colours and
  legend, hover/click lineage highlight, OR edges dashed, a node tooltip that lists its parts **and**
  the experiments it unlocks (Kerbalism `Configure` and crewed science show nowhere in stock R&D).
  Icons resolve from the stock atlas; no Squad assets ship.

## 4. Avionics — REPLACED (`docs/AVIONICS_SPEC.md`, `docs/AVIONICS_COMPARISON.md`)

- **One procedural core + authored named parts.** `ModuleAxeAvionics` on the procedural core;
  `ModuleAxeFixedAvionics` gives capsules, probe buses and guidance rings RP-1's own hand-authored
  `massLimit` table as a fixed steerable mass. RP-1's `ModuleAvionics` / `ModuleProceduralAvionics`
  are stripped.
- **Same formulas, run backwards.** The player sizes the box (a draggable battery / hardware / empty
  split in the PAW); hardware volume × density gives mass, and the inverse of RP-1's Near-Earth
  polynomial gives **capacity**. RP-1 has the player type a `controllableMass` rating and derives the
  box from it. MAX across active cores (RP-1's anti-stacking rule) is kept.
- **Same 13 tech tiers**, 1:1 by node, plus RP-1's `start` floor rung. Two orthogonal VAB toggles:
  Guided / Unguided (RP-1's Near-Earth / Science-Core) and Standard / **Deep-Space Bus** (RP-1's
  Deep-Space, now a whole-bus premium with its own 10-rung ladder on the `shd_*` lane). The
  separate Deep-Space range model is gone; range is comms' job.
- **CHANGED — over capacity never locks the procedural core.** RP-1 hard-locks attitude **and
  throttle** in three states. AXE corrupts control instead: zero stick in → zero out, any input →
  adversarial noise scaled by the overload ratio, on gimbal and RCS alike; throttle and staging are
  never touched (`docs/AVIONICS_NOISE.md`). Fixed-capacity named parts keep RP-1's attitude lock.
  Crewed pods and bare probe cores bypass the mechanic, as in RP-1.
- **CHANGED — live draw.** EC draw runs off the vessel's live **dry** mass (RP-1: the static rating),
  drops to the hibernate rate on rails, and is fed into stock `ModuleCommand` (or Kerbalism when
  present), so an empty battery loses control exactly as in RP-1. Mass and cost freeze at launch.
  Hibernation is Guided-only; radiation-hardened cores may hibernate from their first rung.
- **NEW — heaters as their own Kerbalism line** (`ModuleAxeThermal`), so the planner shows where
  deep-space watts go.
- **PORTED**: RCS honours the attitude lock (RP-1's `ModuleRCS` patch), F7 clears stuck input locks,
  Kerbalism EC shown in SI watts (the live half of RP-1's KerbalismPatcher), science container on from
  `basicAvionics`, kOS tier bridge (inert, kOS is not a dependency).
- **NEW — an astronaut aboard always gives full SAS**, whatever their trait or level
  (`AxeCrewAutopilot.cfg`, `AxeCrewSasSkill.cs`). Stock ties SAS to the pilot's XP level, and an
  engineer or scientist alone gets none; AXE cut crew progression, so a human aboard is the guidance
  computer.
- **NEW — pre-flight verdict** in the editor (`N.NNx — degraded`), and an avionics check as a
  contract requirement (`AvionicsCheck`).

## 5. Science — PORTED, with additions (`docs/SCIENCE.md`, `docs/KERBALISMLAB.md`)

- **PORTED verbatim — RP-1's RP0\* instrument suite**: 96 of 98 budgeted experiments (the two absent
  ones never existed in RP-1 either), 16 experiment files, `GlobalExperimentPatches`, the
  DMagic-module clean-slate. Instruments are part-gated so no remap was needed.
- **PORTED, remapped — crewed science** (capsule / cockpit / station / lunar-surface, 17 tech gates
  → AXE nodes) and the Kerbalism `Configure` SETUP gates (probe cores, capsules, lunar bases, US2
  wedges), each gated where its content unlocks.
- **KEPT — telemetry free from mission 1**, stapled to every command part.
- **NEW to the stack — KerbalismLab**: 65 crewed-station experiments (the "Continued" fork) plus the
  minimal Kerbalism ScienceRework lab framework it needs, techs remapped. Balance pass: payouts
  actually read `scienceCap` (so the author's 10–500 curve is live, 13.07M → 1.47M theoretical), the
  6 base lab experiments defined, single-body experiments ×10 so a LEO station banks ~28k, not ~4k.
- **CHANGED — home-planet science below 40 km is near-zero** (`EarthScienceRemoval.cfg`, follows
  LRTR). RP-1 leaves landed / splashed / flying-low Earth at 1×. Above 40 km, orbit and recovery keep
  RP-1's values; the ocean-only lab experiments are therefore dead by policy.
- **NEW — Orbital Geochemistry**: three AXE-authored instruments reading surface elemental
  composition from orbit, biome-resolved **only** from low orbit, so a mapping campaign pays per
  region and a lazy high orbit banks one reading. Neither RP-1 nor RO has this category.
- **PORTED, re-homed — Kerbalism HDD data storage.** RP-1's 10-rung ladder, moved from the avionics
  nodes onto the data-handling spine (tape recorder → diodes → transistors → flight computers), so a
  fresh career has storage from 4 science instead of 44.
- **NEW — Kerbalism group upgrades defined** (lab slot, in-flight lab reconfigure, US2 wedge slots,
  permanent habitation / sickbay) so they stop rendering as "Unknown Upgrade" and are reachable.
- **CHANGED — contract science.** RP-1 zeroes `rewardScience` everywhere; AXE keeps that except
  First Launch (6, before any instrument exists) and the lunar impactor (~60, the mission *is* the
  experiment).
- **PORTED — stock ΔV app forced off** (wrong under RealFuels; read MechJeb).

## 6. Contracts and programs — PORTED contracts, REPLACED programs (`docs/PROGRAMS.md`, `docs/ECONOMY.md`)

- **PORTED — RP-1's contracts**, 312 config files / ~370 contract types, byte-identical under
  `seed/Contracts/`. The CC_RP0 parameter and requirement types they use are reimplemented in
  `AXE.dll` (`Source/AXE/Contracts/`: CollectScience, HasExperiment, HasSamples, ReachMach,
  DownrangeDistance, HorizontalLanding, ReturnHome, Rendezvous, ImpactCB, AvionicsCheck, …).
- **Fixups the plugin used to do at runtime**: duplicate contract names deduped (RP-1's
  ContractClobberer), the Uranus/Neptune moon-landing groups declared, First EVA's RP-1-only
  requirements rewritten, the First Docking `NewVessel` latch, titles for untitled science
  parameters, every `TechResearched` requirement remapped to an AXE node.
- **CHANGED — stock, expansion and Kerbalism contracts are off** (27 types via config + preset; RP-1
  disabled 32 from its plugin). **Skopos's perpetual `maintenance_*` contracts are deleted**: monthly
  reputation from hardware already in orbit is infinite money under free warp. The one-shot
  "establish the network" masters stay.
- **REPLACED — programs.** RP-1's `Programs.cfg` funding system (funding curves, nominal durations,
  slots, confidence, leaders, program UI) is not run. Instead every RP-1 program has a **"Begin
  Program: X" charter contract** (35; the 5 RP-1 ships disabled stay dormant). Charters never expire.
  The first three are open; each later program requires a predecessor to be **concluded**, forming an
  onboarding DAG. A program ends only through its **"Conclude Program: X"** contract, offered once
  every objective is flown; concluding stops its missions being offered and opens the next tier.
  There is no abandon path.
- **PORTED — Mission Control active-contract limit** (3 / 5 / 7 / 10 / ∞ by facility level, RP-1's
  curve); Contract Configurator's per-prestige caps are flattened to it.
- **CHANGED — what a contract pays.** Reputation at RP-1's values (× stock's prestige and difficulty
  multipliers, which RP-1 also paid). Funds only on **capstones** (RP-1's own `CAPSTONE`-marked
  missions, 14 programs) and on **program objectives + the completion bonus**, each program's pot
  sized from RP-1's `baseFunding` × 0.101 and spread across its objectives so no program goes 14
  launches without income. The charter states what the program pays. Total 24M budgeted, ~36.9M paid
  after stock multipliers. Nothing repeatable carries funds.

## 7. Economy and facilities — REPLACED (`docs/ECONOMY.md`)

- **Two channels, 40M lifetime target.** Channel 1 (above) is launch-gated. Channel 2 is the stock
  Administration **Fundraising Campaign**, rescaled from stock's 1,002–1,253 to **125–157 funds per
  reputation** (reputation is otherwise unspendable once RP-1's subsidy is gone). **Deleted**: Patents
  Licensing and Open Source Tech Program (science → funds is unbounded when science is 10× the tree).
  Commit range 0.5 / 0.75 / 1 by Administration level, `minShare` 0.55. A one-time Space Center popup
  at 10 reputation points at Fundraising, because a player who never opens Administration is
  hard-blocked at first orbit.
- **NEW — reputation arithmetic is linear.** Stock damps every award one point at a time while the
  strategy takes a flat share of the raw value, so a 1,350-rep capstone banked 403 and was charged
  1,046. `AxeReputationScale.cs` flattens both curves. RP-1 never hit this because it did not convert
  reputation.
- **Part unlock cost**: tier × category table calibrated so realised spend is ~8 % of lifetime funds,
  RP-1's own share (`AxePartCost.cfg`; `BypassEntryPurchaseAfterResearch` stays off). Engine configs
  0.3× their node's part price.
- **PORTED ×1.2 — the launch bill.** Per-unit part costs are RP-1's own hand-normalised values
  (`AxePartFlyCost.cfg`, `AxeProcCostScale.cfg`), scaled 1.2× to absorb the two RP-1 costs AXE cannot
  port: tooling and daily ops. Propellant is negligible at any size.
- **CHANGED — facilities (CustomBarnKit)**, all authored by AXE because RP-1 owned these numbers
  through its plugin and KCT:
  - **Launchpad**: a 7-level mass ladder, 25 / 75 / 200 / 500 / 1,200 / 3,000 / ∞ t (RP-1's pad was
    inert in CBK; KCT grew it by construction), 7.23M total.
  - **Tracking station**: RP-1's 11-level DSN ladder verbatim (RealAntennas ground gain), 2.53M, each
    level tech-gated by a `tel_*` node and enforced in `AXE.dll` (RP-1 did this in RP0.dll).
  - **R&D**: an 8-level **science-cost-cap** ladder, 2.68M. RP-1 deleted this mechanic in v3.0 because
    KCT already paced research by time; AXE has no time gate, so it keeps the cap and prices it (no
    step opens more than ~19 % of the tree). The caps sit at the geometric midpoints of the tier
    rates and `build_tree.py` asserts them on every build.
  - **Mission Control**: RP-1's 5-level contract-limit curve. **VAB / SPH**: no part-count cap and all
    action groups from turn 1 (RP-1 parity). **Runway**: free upgrades (RP-1 parity).
    **Administration**: 3 levels, owned for the commit range. **On-orbit fuel transfer** from turn 1
    (RP-1 parity; stock gates it on R&D L2).
  - **EVA**: free in Earth's SOI from turn 1 and the EVA chute from the start (`homebodyAtmoEVA`,
    `unlockedEVAChute`); the Astronaut Complex gates nothing.
- **PORTED — difficulty presets.** RP-1's `GAMEPARAMETERS` defaults on all four presets, applied by
  AXE's own preset changer (`AxeDifficultyPresets.cs`, since the node is an RP-1 convention stock
  never reads): no re-entry comms blackout, negative funds allowed, action groups always on, KSC
  buildings 10× sturdier, reverts and quickload on, no signal needed for control; pressure / G /
  re-entry realism kept. Note `AllowNegativeCurrency` still does **not** let you launch while negative.
- **PORTED — kerbal G tolerance** (RP-1's `PHYSICSGLOBALS` and trait tables from `CrewSettings.cfg`,
  the half of that file that was never about crew training).
- **PORTED — dev parts.** RP-1's experimental-parts toggle in the VAB/SPH; AXE bills the entry cost
  at launch (no KCT to bill it) and simulations stay free. RealFuels configs keep their own buy flow.

## 8. Editor and flight features

- **REPLACED — simulator** (`docs/SIMULATION.md`). A **Simulate** button in the VAB/SPH spawns the
  craft into any orbit around a chosen body, nothing persists, **free**. The home world is always
  available; every other body and time-of-launch unlock with the Digital Guidance Computer node.
  RP-1's KCT simulation (costed, orbit-only, feeding reliability data) is gone with KCT.
- **PORTED, standalone — airlaunch.** Build a rocketplane, pick **Airlaunch** at the SPH launch
  button, set the release point, spawn airborne after a 10 s countdown. RP-1's four envelopes
  (B-29→X-1, B-50→X-2, B-52→X-15 / X-15A-2) gated on the rocketplane lane. **Added**: a per-launch
  funds fee scaled by tier, and Revert to Launch repeats the airlaunch.
- **KEPT, decoupled — launch-site switching.** KSCSwitcher relocates the KSC to any RSS site, any
  time, **free**, from the Tracking Station. RP-1's per-site space centers, DSN gating and lockable
  switching lived in the removed layer. RealAntennas' fixed ~56-station ground network already has a
  station at every site, so comms need nothing.
- **PORTED — part behaviour modules**, same class names, tagging re-authored since AXE does not ship
  RP-1's `TREE-Parts.cfg`:
  - `ModuleNonReentryRated` — RP-1's rule (atmospheric cockpits + off-world landers burn up on a
    full re-entry; capsules and station modules are not tagged), 24 parts.
  - `ModuleRangeSafety` — **CHANGED key**: on every uncrewed command part (142) rather than on
    RP-1's `ModuleAvionics` carriers, stripped from crewed parts as in RP-1.
  - `ModuleNoEVA` — RP-1's 43-part list, **minus the Voskhod airlock** (the whole point of the part).
  - `ModuleUnpressurizedCockpit` — per-cockpit hypoxia ceilings and the X-1 → X-2 ceiling upgrade.
  - `ModuleNonRecharge` — primary batteries on battery-only early satellites (Sputnik 1/2 class);
    solar-powered contemporaries stay rechargeable.
  - `ModuleTagList`, `ModuleShowInfo`, `ModuleStationPart` — stripped or inert; every consumer left
    with RP0.dll.
- **PORTED — small plugin behaviours**: first-EVA flight-log fix (a ground step-out is not the first
  spacewalk), the "landed while actually flying" tip (the only RP-1 gameplay tip with no sacked
  dependency), F7 clear-locks.
- **NEW — compatibility fixes AXE carries because it runs the RO stack without RP-1**: ROHeatshields
  PAW re-collapsing and unit labels, RO's editor resource units, AJE propeller zero-RPM thrust spike,
  the bimodal-engine toggle silently doing nothing, nine upstream part defects
  (`AxeUpstreamPartFixes.cfg`), and RSS gas giants over-radiating orbiters (`AxeGasGiantEmissiveFix`).
  AXE does **not** patch other mods' cosmetic bugs (the DynamicBatteryStorage toolbar NRE is left
  alone and documented).
- **KEPT — Kerbalism**: radiation, comfort, storms, habitat, the RO life-support profile and
  reliability-off are the RP-1 config unchanged. The only AXE touch is stock hibernation re-enabled
  for radiation-hardened avionics cores.

## 9. Not ported, parked, or still open

- RP-1's post-2051 colonisation scaffold; a real endgame (fusion, O'Neill habitats) is a future design
  pass, not a port.
- Deep-Space interplanetary avionics as a separate model (folded into the Shielded axis).
- Fuel as a usability gate and the probe prerequisite-tech checklist (`VISION.md`) — parked, post-MVP.
- Kerbal Konstructs multi-pad launch complexes — not a dependency; KSCSwitcher relocates one KSC.
- TestFlight's RP-1 config (`TestFlightRnD.cfg`) and optional `zTweakScale.cfg` — not vendored.
- A Space-Center-scene launch-site switcher (KSCSwitcher's UI is Tracking-Station only).
- Everything in `docs/BUG-CLASSES.md` is the taxonomy of *unintended* divergence found so far; the
  parity gate `tools/check_settings_parity.py` reports 0 open items as of 0.9.0.
