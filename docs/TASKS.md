# RP-AXE Task Backlog

Canonical, durable backlog, organised as milestones **M0–M7** (each with a "prove it" gate). Read
[`ARCHITECTURE.md`](ARCHITECTURE.md) and [`WORKFLOW.md`](WORKFLOW.md) first. The live task tracker
mirrors these milestones.

**MVP definition of done:** a clean CKAN-style install (vendored config, **no `RP0.dll`/`CC_RP0.dll`**,
`conflicts: RP-1`) loads; the tech tree renders with parts in the right nodes and unlocks via
science; an early contract chain is **offered and completable**; activating a program opens its
bundle (config-only switcher); **funds are a real, non-trivial budget with no time pressure**.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · ⛏ depends on

---

## M0 — Project skeleton ✅ (this session)
- [x] Map RP-1/instance layout; identify plugin coupling; choose architecture.
- [x] Repo scaffold + `seed/`+`design/` split; docs (README, ARCHITECTURE, WORKFLOW, DEPENDENCIES,
      DECISIONS, TASKS); `tools/deploy.ps1`, `tools/sync-seed.ps1`; boilerplate `Source/AXE`.
- [ ] `LICENSE.md` (CC-BY-NC-SA-4.0) + attribution (RP-1 Group, pehvbot/LRTR).
- [ ] First commit of the scaffold.

## M1 — Vendor seed & pluginless load ⛏ M0
- [ ] `tools/sync-seed.ps1` → vendor `Tree/`, `Contracts/`, `Science/` into `seed/`.
- [ ] `tools/deploy.ps1` → junction `GameData/RP-AXE` into `Instance/`, toggle `RP-1` ⇄ `RP-1.disabled`.
- [ ] **Prove:** game loads to menu + a new career; tree renders with parts in correct nodes; check
      whether `.truecolor` icons render (ROLibrary) or fall back. Capture `KSP.log` (no RP0/CC_RP0).

## M2 — Contract CC types in AXE.dll ⛏ M1  —  ✅ VALIDATED (356/356 contracts, AXE AutoTest 2026-06-26)
Approach (DECISIONS D6): wrote our OWN CC types in `AXE.dll` (`Source/AXE/Contracts/`) so RP-1's
contracts load verbatim. Per-type decisions + status: `Source/AXE/_CCTYPES.md`.
- [x] CC-type triage — researched each type's behaviour & dependency (most are self-contained stock logic).
- [x] Implement all 14 names (real / no-op). `ProgramActive` is now **real** (M4), not the stub. **Builds clean.**
- [x] Dedupe `FirstTundraSat` & `landingTriton` → `design/Contracts/DedupeContracts.cfg`.
- [x] Stub `RP1CommsPayload`/`RP1WeatherPayload` → `Source/AXE/Contracts/ExpressionFunctions.cs`.
- [ ] Deferred (polish): promote no-ops (`ImpactCB`, `RP1Rendezvous`, `HorizontalLanding`, Kerbalism
      sample/experiment) to real checks.

### ✅ COMBINED VALIDATION (M2 + M3 + M4) — PASSED via AXE AutoTest (2026-06-26)
Hands-free smoke test (`-axe-autotest`, see `Source/AXE/AutoTest/`): CAREER → R&D → Mission Control → self-quit.
- [x] **Load (M2):** **356/356** CONTRACT_TYPE loaded; 0 ModuleManager errors; no `Unknown` types; no no-op-factory errors.
- [x] **Switcher (M4):** Mission Control opens; earlier manual run: accept charter → `[AXE] Program activated: X` → gated contracts offered.
- [x] **Screens:** R&D + Mission Control open/exit cleanly (autotest SUCCESS, visited 2).
- [x] No exceptions from our code (only benign KSPCommunityFixes drag-cube NREs).
- [ ] Still untested — needs a real play session, not a smoke test: **fly** an early contract to see
      `DownrangeDistance`/`ReachMach`/`RP1ReturnHome`/`RP1CollectScience` complete; **economy balance**. → under M3.

## M3 — Pass C + D: rewards & parts funds sink ⛏ M2  —  v1 IMPLEMENTED, ⚠️ pending combined validation
> Backbone data: **`docs/PROGRAMS.md`** (Pass C) and **`docs/ENTRYCOSTS.md`** (Pass D).
> v1 shipped: Pass C **flat** per-program `rewardFunds` (`design/Rewards/ProgramRewards.cfg`);
> Pass D **conservative category-default** entryCost (`design/EntryCosts/Defaults.cfg`).
> Follow-ups: capstone weighting + `rewardScience`; per-part LRTR entryCost porting; balance vs vehicle cost.
- [ ] Pass C: redistribute each program's `baseFunding` (from `seed` `Programs.cfg` reference) into
      per-contract `rewardFunds`; add modest `rewardScience`. (`design/Rewards/`)
- [ ] Pass D: rebuild part `entryCost` — LRTR values for add-on/futuristic mods; RO core hand-priced
      from `EntryCostModifiers.cfg`. (`design/EntryCosts/`)
- [ ] Document global Funds/Science multipliers as the final trim knob.
- [ ] **Prove:** funds are a real, non-trivial budget; each early era's income covers its vehicle costs.

## M4 — Pass B: program switcher ⛏ M2  —  v1 IMPLEMENTED, ⚠️ pending combined validation
> Design + program list/membership: **`docs/PROGRAMS.md`** (§ "M4 — program switcher").
> v1 shipped: `AxeProgramHandler` (ScenarioModule) + `ActivateProgram` behaviour + real `ProgramActive`;
> 12 early "Begin Program" charters with a guided chain (`design/Programs/ActivatePrograms.cfg`).
> Follow-ups: charters for the remaining ~28 programs; surfacing (offered-contract limit / `weight`);
> optional toolbar UI.
- [ ] Author "Activate [X] Program" contracts (always available) for the program list (DEPENDENCIES/
      ARCHITECTURE §6). (`design/Programs/`)
- [ ] Re-point member contracts to gate on `AcceptContract{ contractType = Activate_X }`.
- [ ] **Prove:** activating a program opens its bundle; ignoring it hides them; any order works.

## M5 — Pass E + F: science tune & future tree ⛏ M1, M3  —  ✅ Pass E + F DONE (AutoTest 2026-06-26)
- [x] Pass E — **science pace + economy** ("Gentle trim", `design/Science/`, `design/Rewards/`):
  - [x] Science pace: **RP-1 original ×1.0** (trialled a ×0.8 `SciencePace.cfg` trim, then reverted —
        the solvency audit showed ~57× headroom, so easing an already-trivial gate wasn't worth it).
  - [x] `EarthScienceRemoval.cfg`: near-zero Earth sub-40km science (landed/splashed 0.00001, flyingLow
        0.001) — no home-planet biome farming; science comes from ≥40km/orbit/recovery + other bodies
        (whose multipliers are 2–50× Earth's, so completability is safe). Matches LRTR.
  - [x] Funds ×1.25 both channels: `FundsTrim.cfg` (CONTRACT_GROUP[RP0] DATA globalHardContractMultiplier
        1.0→1.25) + `ProgramRewards.cfg` re-baked baseFunding/N×1.25.
  - [ ] *Follow-up:* true per-tier solvency (income vs vehicle+entryCost per era) — needs a play session.
- [x] Pass F — **orphan browser + part placement** (`design/Tree/AxePlace_*.cfg`, `OrphanBrowser.cfg`,
      `zzzAxeTags.cfg`):
  - [x] Installed part set: Tantares(+LV+SP), full NearFuture suite, Cryo, KerbalAtomics (CKAN, RP-AXE
        instance). (ProbesPlus/DMagic/SurfaceExperiment/UniversalStorage/FarFuture deferred by user.)
  - [x] **Orphan browser**: surface RP-1's hidden `orphanParts` pool as 12 visible categorised RDNodes
        (right of the tree) so the orphan set is browsable. Everything RP-AXE touches is marked:
        `ModuleAxeMarker` (FE "RP-AXE" filter) + `rp-axe` tag + `[RP-AXE]` description note.
  - [x] **Placed 828 parts** (Tantares/NF/Cryo/Atomics) onto RP-1 era nodes by porting LRTR's
        `tree/parts/*.cfg` tier judgement: strip `:NEEDS[LRTRTechTree]`, run `:LAST[RP-AXE]` (override
        OrphanNode), remap 58 stock/CTT node ids → RP-1 nodes (93 shared lift verbatim), keep LRTR
        cost/entryCost. 0 placement failures; browser drained 1248 → 568 (genuine remainder).
- [x] **Prove (AutoTest):** career→R&D→Mission Control SUCCESS; future nodes render; orphanParts 0;
      placed parts on real nodes; 0 new errors. *Remaining:* per-part **entryCost balance** review
      (LRTR values are a head start, not RP-AXE-tuned) → folds into M3 Pass D.

## M6 — Pass G: avionics/control & start node ⛏ M1  —  ✅ CONFIG-COMPLETE (AutoTest 2026-06-26)
- [x] **Real root cause: 506 "Starting Parts" stranded.** RP-1 keeps the basic 1940s-50s set (sounding
      engines, early guidance, cockpits, procedural parts) on the `unlockParts` node (cost 999), which
      its ConfigurableStart/FirstStart plugin auto-unlocked. Plugin axed → stranded behind 999 science
      at turn 1. Fixed: `design/Tree/StartParts.cfg` repoints `unlockParts → start` + hides the empty
      node. start 43 → **549 parts**; first-rocket essentials confirmed on start.
- [x] Basic command part at `start`: kv1Pod, SXT-TMA1new, GuidanceStart1m — stock `ModuleCommand`
      control (RP-1's mass-based avionics system is gone with the plugin, but control works stock-like).
- [x] Early antennas + science at start: **26 RealAntenna** parts + **37 science instruments** on start.
- [~] Inert procedural-avionics parts (proceduralAvionics, ROT-ProbeCore): **kept** — both have
      `ModuleCommand`, still work as probe cores; only the avionics PAW is cosmetically dead. Not removed.
- [ ] **Prove (needs a play session):** actually build + launch a sounding rocket from `start`.
      Config-complete (engine+guidance+control+tank+comms+science all at start, free, 100k funds).

## M7 — Packaging & release ⛏ all  —  AUTHORED (awaiting GitHub owner + publish)
- [x] `GameData/RP-AXE/RP-AXE.version` (KSP-AVC): v0.1.0, KSP 1.12.0–1.12.5, URL/DOWNLOAD filled (with
      `__GITHUB_OWNER__` placeholder). Renamed from AXE.version.
- [x] `RP-AXE.netkan`: depends = the test instance's real CKAN set (proven to resolve+run) minus RP-1/
      Skopos/TestFlight/tooling; `conflicts: RP-1`; `recommends` DLCs/MechJeb/KAC; `suggests` tools.
      Valid JSON. Tantares ids are `NewTantares`/`NewTantaresLV`.
- [x] README: status → MVP config-complete, economy summary, Install + "Playing the MVP" notes.
- [x] `docs/RELEASE.md`: build-payload + publish + **clean-room install test** procedure.
- [x] Owner/author/URLs filled → `miskoltrans` / `miskoltrans/RP-AXE`. AutoTest ships disabled
      (`enabled = false`; `-axe-autotest` flag force-enables for dev).
- [ ] Create the GitHub repo + remote, tag v0.1.0, GitHub release with the `GameData/RP-AXE` zip.
      *(user will set up the remote later; release zip prebuilt at `dist/RP-AXE-v0.1.0.zip`.)*
- [ ] Run the clean-room install test (fresh KSP 1.12.5 + CKAN, zero manual steps). *(blocked on publish.)*

---

## Cross-cutting / parked
- [ ] Keep `Source/AXE` boilerplate building & loading (a `[AXE]` line in `KSP.log`) so the fallback
      is ready the moment the CC triage (M2) needs it.
- [ ] Optional future: tiny Harmony plugin re-implementing avionics-by-mass control (out of v0 scope).
- [ ] Far-future part-pack selection + RO/RSS scaling research (feeds Pass F).
- [ ] Remaining program bundles / advanced contracts (lunar, planetary, stations, records, Skopos).
- [ ] Educational mission briefings that explain the engineering.

## Open decisions (track in DECISIONS.md)
- OD1 **resolved** → funds ON, rebuilt light (invariant 3).
- OD2 avionics replacement (validate in-game first). · OD3 TestFlight failures. · OD5 far-future packs.
