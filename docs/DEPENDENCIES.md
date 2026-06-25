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

## Promoted (post-MVP): near & far future as expected content

RP-1 lists these under `suggests`; the AXE vision makes them expected. They need RO scaling
configs to be realistic under RSS — that's a research task, **not MVP**:

- Near-future: NearFutureLaunchVehicles, NearFutureConstruction, NearFutureElectrical,
  NearFutureSolar, NearFutureExploration, CryoEngines, KerbalAtomics.
- Far-future: candidates to evaluate — Far Future Technologies, KSP Interstellar Extended.
  (Tracked in TASKS.md as research, since RSS/RO compatibility is non-trivial.)

## CKAN metadata (target `RP-AXE.netkan`)

Strategy: **seed `depends` from RP-1's own CKAN depends (`ckan show RP-1`), minus RP-1, then trim by
experiment.** Verify exact CKAN identifiers (Kerbalism / its RO config and ROLibrary have provider
quirks).

- **`depends` — bedrock (never trim):** ModuleManager, RealSolarSystem, RealismOverhaul, RealFuels,
  Kerbalism, ContractConfigurator.
- **`depends` — examine-later (likely required, confirm by experiment):** RealAntennas (the
  `AddToGroundSegment`/`AchieveConnectionAvailability` contracts need it), ROLibrary/ROUtils,
  CustomBarnKit, plus the RO part packs the tree places (ReStock(+Plus), ROEngines, ROTanks,
  ROCapsules, ROSolar, ROHeatshields, ProceduralParts/Fairings).
- **`conflicts`:** RP-1 (invariant 2 — vendored configs must not double-patch a real RP-1).
- **`suggests` (optional content gates):** SCANsat, SurfaceExperimentPackage, kOS, SXT.

## Reconstituting the instance

The current snapshot is `Instance/CKAN/installed-RP-AXE.ckan` (a metapackage). It currently still
lists `RP-1` — that's a stale snapshot. The intended metapackage drops `RP-1` and keeps the rows
above. Authoring a clean `RP-AXE.netkan`/metapackage is a backlog task.
