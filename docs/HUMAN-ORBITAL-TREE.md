# Human Orbital Spaceflight — King-Part Design Notes (next phase after First Orbit)

Derived from `manifest/human-orbital-partlist.md` (21 RP-1 nodes, ~140 new parts once earlyAvionics +
scienceSatellite are set aside as already-resolved). Same rule as `EARLY-TREE.md`: node = one
**non-obvious enabling breakthrough** (zero `&`), carrying a **⭐king** part + ride-alongs; cost
abstracts the R&D for the unnamed rest. This is a first pass, revised once already — redline any of it.

**Revision note:** the first pass under-counted. It let low part-count per RP-1 category talk it into
default-ride-along too often, even though `fd_deepThrottleEarly` (1 part, XLR99) already proved a thin
category can hide a real breakthrough. Re-scanned the `orbitalRocketry1958–1961` block and the categories
originally left as "Open calls" with that corrected lens — see **13 king parts** below, up from 6.

## The framing that shapes it
First Orbit answered "can it fly." Human Orbital answers "can it fly *someone*, and get them back
alive." That's a small, sharp set of new irreducible requirements layered on top of the existing
`int_orbitalInsertion` booster: a sealed cabin (**Life Support** — new discipline, first use), a
heatshield that survives reentry (**Composite Materials** — new discipline, first use), and the
attitude control + parachute recovery the early tree *already built* for uncrewed probes. Two whole
RP-1 nodes (`earlyAvionics`, `scienceSatellite`) are re-listed in the partlist purely for
self-containedness — they were already placed in the first-orbit batch. **Skip them here.**

Beyond that milestone, the `orbitalRocketry1958–1961` block (41 parts) turned out to hide several real
scatter-breakthroughs of its own — this is the historical moment national programs' engine lines start
to diverge (peroxide chemistry, storable-propellant boosters, restart-in-vacuum, clustering) — alongside
the genuinely-ride-along bulk (more `fd_multiChamber`/`fd_baffledInjector` variants, more RCS blocks,
more solar panels, bigger landing gear).

---

## The milestone convergence

- **Crewed Reentry Capsule** `int_crewedCapsule` `[SystemsIntegration, T4]` — parents: `int_orbitalInsertion`,
  `gnc_rcs`, `aero_recovery`, `life_openLoopECLSS` (new), `cmp_ablativeTPS` (new). `anyToUnlock:false`.
  ⭐`ROC-MercuryCMBDB`. ride: `ROC-VostokCapsule`, `ROC-ZenitCapsule`, `mk1pod_v2`, `ROC-MercuryNoseCapBDB`,
  `ROC-MercuryAirbrakeBDB` (destabilizing flap — keeps the blunt end forward by design), `ROC-VostokService`,
  `RP0HumanRatedFlag`.
  *Same "relaxed convergence" test as `int_orbitalInsertion`: what's irreducible to fly a person to orbit
  and bring them home alive? An orbit-capable booster, attitude control to keep the heatshield forward,
  a heatshield, a way to decelerate, and air to breathe. Nothing else is physics — everything else
  (launch escape, a specific national capsule shape) is a practical-path nicety, kept off the gate per
  the same what-if principle that dropped staging/guidance from `int_orbitalInsertion`.*

- **Open-Loop Life Support** `life_openLoopECLSS` `[LifeSupport, T3]` — parents: `start`. ⭐`RO-LifeSupport-DummyEngine`
  (RP-1's life-support consumables module — lands, fittingly, in RP-1's own `crewSurvivability` node).
  *Bleed stored oxygen, scrub CO2 with lithium hydroxide, pack water and food for the mission's exact
  duration — the minimum a human needs to survive a sealed can for a day. First use of the LifeSupport
  lane (18-discipline set, previously untouched — the early tree never needed it).* Reuses the id/flavor
  seed already sketched in `tree/library.yaml`.

- **Ballistic Ablative Reentry** `cmp_ablativeTPS` `[CompositeMaterials, T3]` — parents: `start`.
  ⭐`RP0-SampleReturnCapsule` (deprecated but historically the right king — Corona/Discoverer-style
  film-return capsule). ride: `RP0-SampleReturnCommand`, `ROH-AdjustableHS`.
  *Proved uncrewed first: a spinning capsule with a phenolic char heatshield, snagged out of the air off
  a coastline, years before it ever carried a person. First use of the CompositeMaterials lane.* The
  Mercury/Vostok capsules' own integral heatshields (`ROC-MercuryHS`, etc.) ride inside
  `int_crewedCapsule` itself rather than duplicating a part here — same tech, already-integrated part.

## Refinement off the capsule (not a gate — see relaxed-convergence note above)

- **Pad/Ascent Abort Escape** `str_launchEscape` `[StructuresMechanisms, T4]` — parents: `int_crewedCapsule`.
  ⭐`ROC-MercuryLESBDB`. ride: `RO_mk1_LES`.
  *A solid tractor motor that yanks the capsule clear of a failing booster on explosive-bolt command — a
  distinct engineering problem (abort sensing + jettison logic + its own propulsion), not free with the
  capsule. Homed as a refinement, not a gate: a reckless program could fly without one, same reasoning
  that kept staging optional for orbit.*

- **Touchdown Energy Absorption** `str_landingLegs` `[StructuresMechanisms, T3]` — parents: `str_staging`.
  ⭐`landingLeg1`. ride: `miniLandingLeg`, `SXTAirbag`, `SXTAirbagSmall`.
  *Crushable/damped legs (or a cushioning airbag) that catch a touchdown without bouncing or tipping.
  Reuses the id/title/flavor already seeded in `library.yaml`. Resolves RP-1's `humanRatedEDL` category —
  the name is misleading (these are generic touchdown-recovery parts, not human-specific), but the
  breakthrough itself is real.*

## Scatter-ahas inside the existing engine/propellant lines (no new gate)

- **Throttleable Restart Combustion** `fd_deepThrottleEarly` `[FluidDynamics, T3]` — parents: `fd_turbopumpFeed`.
  ⭐`ROE-XLR99` (X-15). *The world's first large, deeply throttleable, restartable liquid engine — a real
  scatter-aha, and a taste of `library.yaml`'s much later `fd_deepThrottle` (T8).*

- **High-Test Peroxide Combustion** `pc_hydrogenPeroxide` `[PropellantChemistry, T2]` — parents: `start`.
  ⭐`ROE-Gamma2`. ride: `ROE-Gamma8`.
  *Concentrated peroxide decomposed over a catalyst into hot steam and oxygen — British rocketry's
  signature chemistry (Black Knight, Blue Streak's Gamma engines), and a genuinely different oxidizer
  path from kerolox or storable hypergolics. Reuses the id/flavor already seeded in `library.yaml`.*

- **Restart-in-Vacuum Hypergolic Ignition** `fd_restartableHypergolics` `[FluidDynamics, T3]` — parents:
  `pc_hypergolics`. ⭐`ROE-Agena` (XLR81). ride: `ROE-AgenaSPS`, `RO-KDU414`, `ROE-Agena_EquipmentRack`.
  *Reignite in vacuum on command, not just once at launch — the Agena upper stage, and the platform that
  became Corona's bus and Gemini's docking target. Absorbs the equipment rack (the Agena's own avionics)
  and the small satellite-attitude engines it spawned as the same breakthrough at different scales.*

- **Storable-Propellant Orbital-Class Boosters** `pc_storableBoosters` `[PropellantChemistry, T3]` —
  parents: `pc_hypergolics`. ⭐`ROE-RD215`. ride: `ROE-RD215_Single`, `ROE-RD219`, `ROE-RD855`, `ROE-RD856`
  (verified: UDMH/AK27 and UDMH/NTO respectively — vernier/trim engines for the same Yangel-bureau R-16/R-36
  storable ICBM-derived family, confirmed via `RealismOverhaul/Engine_Configs/RD855_Config.cfg`).
  *Corrosive, toxic storables scaled from a small hypergolic trim engine up to full first-stage thrust —
  the Yangel-bureau approach of repurposing an ICBM's always-ready propellants for a space launcher.*

- **Engine-Cluster Heavy Lift** `str_engineClustering` `[StructuresMechanisms, T4]` — parents:
  `fd_orbitalThrust`. ⭐`ROE-H1C`. ride: `ROE-H1D`, `ROE-RS27`.
  *Eight first-generation orbital-class engines on a common structure and manifold, synchronized to light
  together — Saturn I, the first heavy-lift booster.* **Settled: belongs in this batch** (see Settled §1
  below) — H-1 is literally the same Rocketdyne S-3D lineage already teaching `fd_baffledInjector`
  (Jupiter/Thor's engine), so its narrative doesn't borrow from the Moon at all: *"you already have a good
  single-chamber engine — Saturn I's answer to 'more thrust' was to multiply it, not reinvent it."* That's
  a clean echo of the very first engine fork (`fd_multiChamber` clustered small chambers ‖
  `fd_baffledInjector` scaled one big one) playing out a second time, one tier up, and Saturn I's actual
  flights (SA-1–SA-10, uncrewed/crewed Apollo CSM shakedowns, Pegasus micrometeoroid satellites) were
  Earth-orbit test missions — squarely "humans in orbit," not lunar. **F-1 is correctly the *other* fork
  arriving later**: it's `fd_baffledInjector`'s own lineage scaled to a single enormous chamber instead of
  clustering — the same "cluster vs scale" tension, resolved the other way, for the mission (translunar
  injection) that actually needs it. Two solutions to one problem, arriving at two different points in the
  tree for two different reasons — not a continuity gap.

- **Solid Retrofire** `pc_solidRetrofire` `[PropellantChemistry, T3]` — parents: `pc_solidGrains`.
  ⭐`ROC-MercuryRetroBDB`. ride: `ROC-MercuryPosigradeBDB`, `ROE-Agena_Retro_TypeIII`, `ROE-RangerRetro`.
  *A one-shot solid burn, precisely timed, to drop out of orbit or push a spent stage safely clear —
  deorbit and separation with no restart requirement.*

- **Helical Directional Arrays** `tel_helicalDirectional` `[Telecommunications, T2]` — parents: `tel_telemetry`.
  ⭐`antenna_cone_toggle` (`digitalComms`). *Axial-mode helix gives circularly-polarized gain that tolerates
  a tumbling spacecraft. Reuses the id/flavor already seeded in `library.yaml`.* Confirmed via
  `RP0TechTree.cfg`: `digitalComms`'s own `Parent{parentID}` IS `lunarRangeComms` (1957-58 vs 1959-60 in
  RP-1's node descriptions) — so `longAntenna`'s ride-along tier-bump on `tel_telemetry` must sit strictly
  *before* this node, not beside it.

## Ride-alongs only — extend an existing node, don't mint one

- **`highSpeedFlight`**, minus the turboprops (below): turbojets/ramjets, `GearLarge`/`GearMedium` → spread
  across `met_turbineAlloys` / `aero_areaRule` / `aero_afterburner` / `aero_ramjet` / `xplaneStart` by
  engine family (same capability-ladder judgment already used for the early tree's turbojets); landing
  gear rides `xplaneStart`.
- **`highSpeedFlight`**'s `SXTNK12M`/`SXTPWPT6` (turboprops) → **new node**, see below (Free-Turbine
  Propeller Drive — didn't fit cleanly under Scatter-ahas since it's Aerodynamics not propellant/engine,
  but it's a real king too): `aero_turboshaftProp` `[Aerodynamics, T3]`, parents: `met_turbineAlloys`.
  ⭐`SXTNK12M` (NK-12, the most powerful turboprop ever built — Tu-95's contra-rotating props at
  near-supersonic tip speed). ride: `SXTPWPT6`.
- **`hypersonicFlightRP0`** (5 parts) → `aero_rocketplane` already carries `Mark1Cockpit`/`Mark2Cockpit`;
  add `MK1Cargobay`, `SXTSmallFuselage`, `vernierEngine`.
- **`earlyFlightControl`**'s plain RCS blocks (`ROE-generic-full/half/quarter`, `ca_jib`, `microEngine`) →
  `gnc_rcs`. (Its `ROE-Agena_EquipmentRack` moved to `fd_restartableHypergolics` above.)
- **`solids1959`**'s Scout-family stages (`ROE-Algol1`, `ROE-Altair`, `ROE-Antares1` [+ Inline variants]) →
  `pc_solidGrains`.
- **`solids1959`**'s `ROE-Agena_Spinrocket` → rides `start`, alongside `ROSmallSpinMotor` (first-orbit
  batch) — same breakthrough (passive spin stabilization, already flavor-established at turn one), just a
  bigger later implementation. **Not** the retrofire node — corrected from an earlier draft that lumped it
  in with `pc_solidRetrofire` purely because both are small solid motors; spin-stabilization and
  deceleration are different functions. Confirmed: only 2 spin-motor parts exist in the whole 1820-part
  curated manifest, so this stays a minor ride-along, not its own node.
- **`orbitalRocketry1958/1959/1960/1961`** (remaining ~30 parts after the 5 kings pulled above) → spread
  across `fd_multiChamber` / `fd_baffledInjector` / `pc_hypergolics` by nation+family (per-engine judgment
  call, same tool-supported process as the early tree's engine pass).
- **`materialsScienceHuman`** (4 parts: bigger service bays/radial tanks/nosecone) → `met_weldedTank` /
  `aero_fairings` ride-alongs, same as the early tree's procedural structure.
- **`primitiveSolarPanels`** (1 part) → `elec_siliconPV`.
- **`lunarRangeComms`** (1 part, `longAntenna`) → `tel_telemetry`, strictly before `tel_helicalDirectional`
  (see Settled §1).
- **`electronicsHuman`** (0 parts, 2 upgrades only) → no node; `RFTech-Battery-II` is a tier-upgrade with
  no part to hang a king on here (batteries are stock, ungated — this is just a capacity bump wherever
  the battery-bearing node ends up).
- **`earlyAvionics`, `scienceSatellite`** → already placed in `first-orbit-partlist.md`. Skip.

**Ullage motors — checked, correctly absent from this batch.** Only one exists in the whole curated
manifest (`ROE-TX280`, S-IV Ullage Motor), and it's in `interplanetary-lunar-probes-partlist` (the next
batch), not here — consistent with Mercury/Vostok being direct-ascent, single-burn boosters with no
coast-then-restart upper stage needing propellant settled.

---

## Settled (do not re-litigate)

All four original open calls are now resolved — two against ground truth, two by user decision:

1. **`lunarRangeComms` → `digitalComms` ordering** — ground-truthed via `RP0TechTree.cfg`'s own
   `Parent{parentID}` chain. `longAntenna`'s ride-along sits before `tel_helicalDirectional`.
2. **`RD855`/`RD856` propellant** — ground-truthed via their engine configs: storable hypergolic verniers
   of the R-16/R-36 family. Confirmed on `pc_storableBoosters`.
3. **`str_engineClustering` (H-1/Saturn I) — IN this batch (user decision).** Test: does it have its own
   clear narrative path, independent of the Moon? Yes — H-1 is the same Rocketdyne S-3D lineage already
   teaching `fd_baffledInjector`; Saturn I's answer to "more thrust" was to cluster eight of an engine you
   already have rather than invent a bigger chamber, and its actual flights were Earth-orbit test missions.
   **F-1 is correctly deferred**: it's the *other* fork of the same "cluster vs scale" tension (from the
   very first engine split, `fd_multiChamber` ‖ `fd_baffledInjector`), resolved by scaling instead of
   clustering, for the mission (translunar injection) that needs it. Two solutions, two different points in
   the tree, each independently motivated — not a continuity gap.
4. **`str_launchEscape` — refinement, not a gate (user decision, "physics approach").** Consistent with
   `int_orbitalInsertion` already dropping staging/guidance as hard gates: the tree's convergence nodes gate
   on irreducible *physics* only, never on procedural/safety norms real programs happened to follow. A
   reckless program *could* physically fly crew without an abort system — the tree must not block that "for
   no reason," same principle as the orbit gate. `str_launchEscape` stays a T4 child of `int_crewedCapsule`,
   available but optional.

## Node count
13 new nodes: the milestone (`int_crewedCapsule`) + its 2 new-discipline inputs (`life_openLoopECLSS`,
`cmp_ablativeTPS`) + 2 refinements (`str_launchEscape`, `str_landingLegs`) + 7 scatter-ahas
(`fd_deepThrottleEarly`, `pc_hydrogenPeroxide`, `fd_restartableHypergolics`, `pc_storableBoosters`,
`str_engineClustering`, `pc_solidRetrofire`, `tel_helicalDirectional`) + `aero_turboshaftProp` (listed
under ride-alongs for narrative flow but counted here) — vs RP-1's 21 era-named nodes for the same ~140
parts. First new use of the LifeSupport and CompositeMaterials disciplines.
