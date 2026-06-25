# RP-AXE Dependencies

Principle (from the brief): **start from exactly RP-1's dependency set, then trim/extend.**
RP-AXE = RP-1's deps **minus the RP-1 plugin/career configs**, plus (post-MVP) promoted
near/far-future part packs.

The test `Instance/` already has all of these installed via CKAN from the RP-1 Express install.
This file is the **record of intent** so the instance can be rebuilt and so a future RP-AXE CKAN
metapackage can be authored.

## Hard dependencies (mirror RP-1.netkan `depends`, minus RP-1)

| Module | Role | RP-AXE |
|---|---|---|
| ModuleManager | config engine | keep |
| RealismOverhaul (≥ v16) | the realism layer | keep |
| RealSolarSystem | real planets | keep |
| ContractConfigurator | contract engine — **our contracts run on this** | keep (core) |
| Kerbalism-Config-RO | life support / science (RO-tuned) | keep |
| KSPCommunityFixes | bug fixes | keep |
| ROUtils | shared RO utility lib | keep |
| ClickThroughBlocker, ToolbarController | UI plumbing (our plugin UI may use these) | keep |
| SXTContinued, VenStockRevamp-NewParts | parts referenced by RO/tree | keep |
| KerbalChangelog | changelog display | keep (optional) |
| CustomBarnKit | facility levels/costs config | keep (we supply our own CBK config) |
| Skopos | RP-1's commercial-comms contract sim plugin | **drop for MVP** (its contracts are advanced; revisit) |

> Note: RealismOverhaul transitively pulls Real Fuels, Real Heat, FAR, AJE, RealChute, RealPlume,
> SolverEngines, ModularFlightIntegrator, etc. — all kept automatically.

## Effectively-required part/tooling packs (RP-1 `recommends`)

Kept because the tech tree and contracts assume them. MVP-required unless noted:

ReStock + ReStockPlus, ROEngines, ROTanks, ROCapsules, ROSolar, ROHeatshields, ProceduralParts,
ProceduralFairings, B9-PWings-Fork, RealAntennas, ModularLaunchPads, KSPWheel.

Tooling/QoL (recommended, not load-bearing): RCSBuildAid, MechJeb2, Waterfall, KerbalAlarmClock,
TransferWindowPlannerFork, LunarTransferPlanner, EditorExtensionsRedux, kOS, ConformalDecals,
DockingPortSoundFX, KerbalRenamer, TextureReplacer, AtmosphereAutopilot, KSPBurst, Shabby.

## Dropped vs RP-1

- **RP-1 itself** (`RP0.dll`, `CC_RP0.dll`, `RP0InstallChecker.dll`, and all of
  `GameData/RP-1/**` career configs). This is the whole point.
- **Skopos** (MVP) — see above.
- **TestFlight / TestLite** — part failures. *Decision pending* (realism vs. lightweight). Default:
  keep TestFlight (it's installed) but treat its configs as out-of-scope for MVP.

## Part-mod set (the RP-AXE parts)

Decision basis: a mod is *turnkey* for us when it is **RO-scaled** (realism) **and** already placed in
RP-1's tree (which we ship). "Endorsed" = in `RP-1.netkan` (recommends/suggests). "Configed" = has
`TREE-Parts.cfg` placements (a larger, partly-legacy superset — see the RP-1 wiki "Which Mods Have
RP1 Configurations?"). CKAN identifiers in `code`. CKAN auto-resolves transitive deps
(CryoTanks, CommunityResourcePack, DynamicBatteryStorage, B9PartSwitch, etc.).

### Baseline — LOCKED IN (RO-scaled + RP-1-endorsed + tree-placed → ~zero work)
Core part packs (RP-1 `recommends`):
- `ReStock`, `ReStockPlus` · `ROEngines` `ROTanks` `ROCapsules` `ROSolar` `ROHeatshields`
- `ProceduralParts`, `ProceduralFairings` · `B9-PWings-Fork` · `KSPWheel`
- `RealAntennas` · `ModularLaunchPads` · `ConformalDecals`
- (already bedrock deps, parts included: `SXTContinued`, `VenStockRevamp-NewParts`)

Near-future + cryo/nuclear (RP-1 `suggests`):
- `CryoEngines` · `KerbalAtomics` · `InternalRCS`
- `NearFutureLaunchVehicles` `NearFutureConstruction` `NearFutureElectrical`
  `NearFutureExploration` `NearFutureSolar`

### Near-future propulsion — INCLUDED
- [x] `NearFuturePropulsion` — ion/plasma/VASIMR; 28 configs + RO support.
- [x] `NearFutureAeronautics`, `NearFutureSpacecraft` — optional, minimal configs (user installed them).

### Far-future — DEFERRED (skip for now, per decision; revisit later)
- [ ] `FarFutureTechnologies` — fusion/exotic; 21 tree configs + RO support.
- [ ] `HeatControl` — radiators/thermal; 19 configs + RO support.

### Exploration / utility additions — INCLUDED
Turnkey (RP-1 tree-placed → ~zero work, just verify orphans):
- `SCANsat` (15) — orbital scanning (has a seed contract type).
- `KAS` (20) · `KIS` (36) — construction/connectors.
- `TantaresLV` (24), `TantaresSP` — Soviet-styled launch vehicles + spaceplanes.

Needs placement work (RO-scaled but NOT in RP-1's tree → Pass F authoring, not just orphan-fix):
- `Tantares` (Soviet spacecraft + station parts) — RO-supported (`RO_SuggestedMods/Tantares`) but
  unplaced; we author `%TechRequired` for these (LRTR `tree/parts/Tantares.cfg` is a head start; remap nodes).

Dropped from the set:
- `ProbesPlus`, `DMagicOrbitalScience`, `SurfaceExperimentPackage` — **not available** in the user's
  CKAN (compat-filtered/unlisted); skipped for now.
- `UniversalStorage2` — skipped (per decision).

American stockalike: **none** — `ROCapsules`/`ROEngines` (baseline) already cover US real-scale capsules/engines.

### Excluded (legacy "configed but newer support lacking", or no RO support)
- `Bluedog_DB` — dropped from `RP-1.netkan` (legacy `RP-0` only); RO support is beta/community; 110
  *legacy* tree configs risk part-name drift vs current BDB v1.14. **Skip.**
- `RealScaleBoosters`, `CoatlAerospace`/`ProbesPlus`, `FASA`, the `RN_` Soviet/US packs,
  `NearFutureAeronautics`, `NearFutureSpacecraft`, `StationPartsExpansionRedux` — configed but not
  endorsed; revisit individually only if wanted (version-drift checking required).
- `KSPIE` (KSP Interstellar Extended) — **no RO support**; would need DIY scaling. Skip.

## CKAN metadata (target `RP-AXE.netkan`)

Strategy: **seed `depends` from RP-1's own CKAN depends (`ckan show RP-1`), minus RP-1, then trim by
experiment.** Verify exact CKAN identifiers (Kerbalism / its RO config and ROLibrary have provider
quirks).

- **`depends` — bedrock (never trim):** ModuleManager, RealSolarSystem, RealismOverhaul, RealFuels,
  Kerbalism, ContractConfigurator.
- **`depends` — examine-later:** RealAntennas, ROLibrary/ROUtils, CustomBarnKit.
- **`depends` — part set:** the **Baseline (LOCKED IN)** + **Far-future — INCLUDED**
  (`FarFutureTechnologies`, `HeatControl`, `NearFuturePropulsion`) + **Exploration/utility additions**
  (`ProbesPlus`, `DMagicOrbitalScience`, `SurfaceExperimentPackage`, `SCANsat`, `KAS`, `KIS`,
  `UniversalStorage2`, `Tantares`, `TantaresLV`) under "Part-mod set" above.
- **`conflicts`:** RP-1 (invariant 2 — vendored configs must not double-patch a real RP-1).
- **`suggests`:** tools only (SCANsat, SurfaceExperimentPackage, kOS).

## Reconstituting the instance

The current snapshot is `Instance/CKAN/installed-RP-AXE.ckan` (a metapackage). It currently still
lists `RP-1` — that's a stale snapshot. The intended metapackage drops `RP-1` and keeps the rows
above. Authoring a clean `RP-AXE.netkan`/metapackage is a backlog task.
