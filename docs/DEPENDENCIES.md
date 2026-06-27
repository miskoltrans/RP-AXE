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
| CustomBarnKit | facility levels/costs | keep. **We do NOT supply our own CBK config** — building/recovery use CBK defaults; starting funds (100k) are granted in code (`Source/AXE/GenerousStart.cs`), since CBK has no `startingFunds` field. |
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

## CKAN metadata

> ✅ **AUTHORED — the source of truth is now [`../RP-AXE.netkan`](../RP-AXE.netkan)** (M7). The
> per-mod tables above remain the *rationale* (why each mod is in the set); the netkan/metapackage are
> the *mechanical* list and win on any disagreement.

**Dependency model — REVISED 2026-06-27: `depends` = the exact installed set of the perfect
environment.** Rather than hand-curate roots and lean on CKAN to resolve transitive deps, the netkan
now lists **every module installed in the test instance** — derived directly from
`Instance/CKAN/registry.json` (`installed_modules`). This makes a rebuild reproduce the curated stack
verbatim, independent of CKAN's recommend-resolution.

- **`depends` (81 modules)** = 57 user-requested roots + 24 CKAN-resolved transitive deps, **including
  the two DLC** (`MakingHistory-DLC`, `BreakingGround-DLC`). The transitive layer (Kopernicus, RealHeat,
  FAR, AJE, B9PartSwitch, CRP, KSPBurst, ROLib, ROUtils, ModuleManager, KSPCommunityFixes, ClickThroughBlocker,
  ToolbarController, …) is now **named explicitly** instead of being left to resolution. Tantares CKAN ids
  are `NewTantares`/`NewTantaresLV`/`TantaresSP`.
- **No `recommends`/`suggests`.** Anything not installed in the perfect environment is not part of the
  set — so QoL mods that *are* installed (MechJeb2, KerbalAlarmClock, EditorExtensionsRedux,
  TransferWindowPlannerFork, Waterfall, TextureReplacer, Skopos, TestFlight, …) are now hard `depends`,
  and ones that were merely suggested but never installed (e.g. `kOS`) are simply absent.
- **`conflicts`:** `RP-1` (invariant 2 — RP-AXE replaces the RP-1 career plugin).
- Regenerate with the PowerShell snippet in [`WORKFLOW.md`](WORKFLOW.md) ("Rebuilding a clean
  instance") whenever the instance's mod set changes — it rewrites both the netkan `depends` and the
  `RP-AXE-deps.ckan` metapackage from the live registry.

## Reconstituting the instance

`../RP-AXE-deps.ckan` (a CKAN metapackage, `kind=metapackage`, 81 `depends`, `conflicts: RP-1`) is the
one-shot installer. Import via CKAN → *File → Install from .ckan file* (CLI: `ckan install -c
RP-AXE-deps.ckan`), then deploy RP-AXE itself via `tools/deploy.ps1`. See WORKFLOW.md for the full
nuke-&-restore procedure. *(The legacy `Instance/CKAN/installed-RP-AXE.ckan` auto-export is CKAN's own
snapshot and is not used for installs.)*
