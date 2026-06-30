# RP-AXE — Restart Backlog

Landing pad for the tree-first rebuild (see [`../VISION.md`](../VISION.md)) until the full
roadmap is written.

**Keep & refine:** contracts (port-and-strip); avionics (rename → RP-1 names + rebalance);
deploy/rebuild tooling (improve).
**Rebuild from scratch:** tech tree; part baseline + placement; economy.

## Decisions settled (this session)
- **Mod parts** — curate a canonical part **manifest** (single source of truth); uncurated /
  3rd-party parts fall to a **standalone Experimental side-node** (visible, low science, *off*
  the main tree, excluded from balance). Player flexibility via a later `allowUncurated` toggle.
- **Part boundary** — **RO-config floor + author our own configs** to fill sparse late-tree paths
  (Nertea/Orion/probes). Strict-RO is the start state; config-authoring is the deliberate value-add.
- **Probe/capsule cross-branch "prerequisite-tech checklist"** — **post-MVP** plugin layer.
- **Parts mix** — procedural is the workhorse; layer in **curated iconic historical/stockish** parts
  where they teach a design or carry an aha-moment (key probes, iconic capsules/engines), cut filler
  variants. Education pillar earns its place without bloat. Sets the manifest's composition.
- **Tooling — REMOVED (not husked).** RP-1's in-game build-time **tooling** system is cut entirely
  from AXE. Consequence for vendored RP-1 parts: strip `ModuleTooling*` (`ModuleToolingPTank`,
  `ModuleToolingProcAvionics`, …) and don't vendor `ToolingDefinitions.cfg` / `Tooling/`.
- **Avionics — REWRITTEN by AXE (we author our own).** AXE ships its own avionics
  (`design/Tree/AxeAvionicsCore.cfg`, `Source/AXE/Avionics/`); RP-1's `ModuleAvionics` /
  `ModuleProceduralAvionics` on vendored parts are dropped/replaced by AXE's modules in a design-pass
  patch (this is the P4 axis). In the meantime vendored parts still load — KSP strips unknown modules.
- **RP-0 flag — KEEP registered.** Vendored RP-1 parts carry `:FOR[RP-0]`, which makes ModuleManager
  treat RP-1 as installed, so the ~60 dormant `:NEEDS[RP-0]` patches across RO / RealAntennas /
  KerbalismConfig / ROSolar / ROHeatshields / ROCapsules / MechJeb / Coatl apply → AXE **inherits
  RP-1's RO-stack realism tuning** and matches `ksp_rp1_clean` (the manifest's curation source).
  Validated by `-axe-autotest`: career loads, R&D + Mission Control open, 0 hard part errors, no NRE
  traced to it. Reversible — override an individual misbehaving RP-0 patch if one surfaces (they
  assume the full RP-1 incl. the axed `RP0.dll`). NOT installing RP-1 (still absent + `conflict`-ed).

## Roadmap (critical path)
Each phase gates the next; avionics + contracts ride alongside, off the critical path.

- **P0 — Part list** ✅ **DONE** (= T1). Manifest locked: **`manifest/curated-parts.tsv` (1,820 parts)**,
  built reproducibly by `tools/build_manifest.py`; full curation log in `docs/PARTLIST.md`.
  **→ P1 is now unblocked.**
- **P1 — Tree architecture.** Branch taxonomy (engineering disciplines, real names); node schema
  (id / tier / deps / `anyToUnlock` / flavor text); editor + build pipeline (lean on ETT).
  **Prove:** a documented branch map + schema; tooling renders a stub tree.
- **P2 — Tree skeleton (parity).** Place the whole manifest so every part has a home (~200 nodes),
  tiered node costs; convergence gates + multi-entry paths; Experimental side-node catches the rest;
  **remap the engine-progression + capability `PARTUPGRADE` `techRequired`s → AXE nodes (see T3)**.
  **Prove:** 0 orphans (bar Experimental); loads + renders; AutoTest passes.
- **P3 — Economy rework.** Science = primary gate; part entryCost = R&D; launch cost = ops; no time
  pressure; **drop RP-1 reliability/run-data grind.** **Prove:** play session / solvency audit shows
  the gates bite as intended.
- **P4 — Avionics** *(parallel)*. Rename to RP-1 terms; rebalance. **Prove:** flyable early control.
- **P5 — Special parts** *(post-MVP)*. Probe subtree (hire-JPL / hire-OKB) + capsule capability-split
  + cross-branch prerequisite-tech checklist plugin. **Prove:** a probe gated by multi-branch prereqs.
- **P6 — Expansion + ship.** Author gap-fill configs (Nertea/Orion/probes); finalize mod set
  ("RP-1 Express minus RP-1" baseline); the two test workflows (add-a-part-mod loop;
  clean+recommended install test); RAM-trim submod; packaging. **Prove:** clean-room install runs.

## Tasks

### T1 — Lock the canonical part list ✅ DONE
Every part-mod curated (per-mod rationale + exact keep-lists in `docs/PARTLIST.md`); consolidated into
**`manifest/curated-parts.tsv` (1,820 parts)** via the reproducible `tools/build_manifest.py`.
- **Curation rule:** RO's `HardRemoveNonRO` flag (RP-1-Express-shipped) = the plausibility floor — it
  *deletes* un-physical parts, so the RO-config floor ≈ "plausible". Our job is cutting **redundant /
  low-value**, not judging plausibility.
- **Science model (big finding):** RP-1's **RP0\* suite (96 tiered real-instrument experiments)** is the
  backbone, ported like contracts; mods contribute **hardware, not science** (DMagic/Coatl probe
  instruments are redundant with RP-1's own 32). **Dropped:** DMagic, NearFutureSpacecraft, TantaresLV.
- **KerbalismLab** (user added `KerbalismLabExperimentsExpandedContinued` = 66 crewed-station experiments)
  is a station-science value-add → integrate at **P3** (regen cache + load-test; **remap its 66
  `UnlockTech` gates to AXE nodes**; rebalance values). It gates on base-experiment carriers + crew, NOT
  probe instruments.
- **Modpack** `../expansion modpack.ckan` trimmed to **28 mods** (dropped NF-Spacecraft, DMagic, TantaresLV).
- **Flag for P2:** `ModularLaunchPads` = 233 parts (biggest inherited block) — a tree-placement trim target.
- **Part upgrades (added post-T1, preliminary — separate agent owns):** `manifest/upgrades-live.tsv` (71
  live PartUpgrades: `name/techRequired/mod/title`) + `manifest/upgrades-absent.tsv` (626 RP-1-defined,
  not live here, `disposition=REVIEW-capability`, from `Tree/*.cfg`). **Upgrades also need tree homes** and
  are the *mechanism* for discipline-scatter: one part, breakthrough-gated config improvements (RP-1's ~81
  yearly engine-increment *nodes* collapse into *upgrades* unlocked across the enabling-discipline nodes;
  a pure-process node like "Vacuum Induction Melting" can pay off purely in upgrades). **Schema impact:** a
  node's payload = `unlocks:{parts:[…], upgrades:[…]}`. → P1 schema + P2 placement input.

### T2 — Science-budget audit (with KerbalismLab) ✅ AUDIT DONE → full writeup in [`SCIENCE.md`](SCIENCE.md)
Budget measured before setting node costs. Tools: `tools/science_budget.py` (probe),
`tools/lab_inventory.py` → `manifest/lab-experiments.tsv` (lab). Headline numbers:
- **Probe science (RP0\*, 98 exp):** ~2.57M theoretical max across RSS (fully ground-truthed: cache
  biome weights + RP-1's real `BodyAllowed` body restrictions — 49 exp Earth-only incl. `photos4`@10k).
  Back-loaded — Earth+Moon only **49k**, outer planets ~1.8M. Realistic ~0.5–1.0M. (RP-1 full tree ≈ **115k**.)
- **Crewed-lab science (KerbalismLab, 71 exp, `tools/lab_budget.py`):** values 10–500; they **scale by
  body like probes** and the fork gates ~30 off-Earth → **~1.37M theoretical** across all allowed bodies.
  BUT it's the least-realizable third (needs crewed surface bases on other bodies' biomes); realistic is
  ~4k (LEO) … ~10–15k (LEO+Moon/Mars). UnlockTechs cluster early-mid (stock names → remap to AXE).
- **T2 TOTAL BUDGET = ~3.93M** (probe 2.57M + crewed-lab 1.37M; **65% / 35%**), per-era table in SCIENCE.md
  §3b. **Tree-cost PROVISIONAL = ~300k** (≈2.6× RP-1's 115k, ≈8% of pool) — science is AXE's *sole* gate so
  it bites harder than RP-1; finishable by broad exploration, not a rush. **Shape = front-load the bite**
  (cheap bootstrap → peak in tiers 3–6 orbit→inner-planets → taper late where other axes gate). It's a global
  scalar dial, final tune from the P3 solvency play-session. (Bracket: ~150k comfortable … ~500k grand-tour.)
- **⚠️ Blocker DIAGNOSED (fix deferred to P3):** the "Continued" fork is an *add-on*; it omits the
  **Kerbalism ScienceRework lab framework** (`KERBALISM_GROUP_SETTINGS`/`LAB_EXPERIMENTS` root node +
  `LabDataRateMultiplier` + the "Laboratory Experiments" `Configure` host) that lives in
  **`KerbalismScienceOnly`** (NOT in stock Kerbalism, NOT in RP-1's config). 132 errors ≈ 2 lookups × 65 exp.
  Fix recipe (vendor the minimal lab subset) + exact missing files in SCIENCE.md §1.
- **DECIDED (P3 integration): re-author** the 65 as plain Kerbalism `Experiment`/`EXPERIMENT_DEFINITION`
  configs wired directly to AXE parts + nodes (like RP0\*), dropping the ScienceRework Configure/slot layer.
  Body-multiplier uncertainty is then **resolved by construction** (we set values/situations against the
  RP0\* model; no cache-read needed; ~51k is the floor, calibration is a dial). Turnkey re-author plan in
  SCIENCE.md §4 — blocked on P1 nodes existing (needs the `UnlockTech`→AXE-node remap).
- **Reference clones (siblings, outside repo):** `../KerbalismLabExperimentsExpandedContinued` (fork),
  `../KerbalismScienceOnly` (base framework source). *(KerbalismLab stays out of `ksp_rp1_expanded` so its
  cache stays clean for the manifest/audit.)*
- **→ P1 unblocked:** tree architecture, designed against these numbers.

### T3 — Upgrade realization (engine progression) — P2/P3 ✅ AUDIT DONE
The part diff only compares `PART` nodes, so RP-1-authored `PARTUPGRADE`s are invisible to it. `tools/upgrade_audit.py`
(→ `manifest/upgrades-absent.tsv` + `manifest/upgrades-live.tsv`) audits them against the live cache:
- **626 RP-1-authored PARTUPGRADEs, ALL absent** under AXE (no RP-1). The 71 live are mod-authored (Coatl `ca-upgrade-*`,
  RealAntennas `commsTL1-10`), present via their mods.
- **532 = engine config-unlock progression** (`Tree/TREE-Engines.cfg` 517 + `RFTechLevels.cfg` 15). Each unlocks a better
  RO engine `CONFIG` at a tech node (e.g. `RFUpgrade_11D23` → the RD0216's 11D23 config at `stagedCombustion1967`, via a
  `:AFTER[RealismOverhaulEngines]` `%CONFIG[..]{ &specLevel = operational }` patch). **This is RP-1's entire engine-progression
  layer and AXE currently has none of it.** NOT the legacy RealFuels `techLevel` system (RO dropped it — 0 engine refs).
- **Sandbox is unaffected** (auto-unlocks all upgrades — engines + configs fully usable); the gap is **career progression only**.
- Other dispositions: **35 avionics = SUPERSEDED** (AXE `ModuleAxeAvionics` `TIER` ladder, design/Tree/AxeAvionicsCore.cfg);
  **32 KCT/facility = DROP** (axed career); **27 capability unlocks** (Payload/Fairing/Airlaunch/Cockpit/HardDrive) = **REVIEW**.
- **The work:** vendor RP-1's engine config-unlock system (`Tree/TREE-Engines.cfg` + its CONFIG patches) and **remap each
  `techRequired` → AXE node** (same job as the science `UnlockTech` remap, ×532) — OR re-author engine progression AXE's way.
  Tree-coupled → **blocked on P1 nodes existing**; do it in P2 alongside placement. Drives off `manifest/upgrades-absent.tsv`.

## Reference instances (outside the repo — never nuke)
- `../ksp_instance_clean` — pristine rebuild base; copy it to spin up a fresh test instance.
- `../ksp_rp1_clean`, `../ksp_ro_clean` (+ `_expanded`) — clean RP-1 / RO references (used for the part diff).
- Other `../ksp_*` folders hold various mod combos. **Some may be in a messed-up state — validate the
  actual installed mods (`ls GameData` / `CKAN/registry.json`) before trusting any non-`*_clean` folder.**

## Parked ideas (later threads)
- **Relocatable / selectable KSC** — let the player choose or move the launch site ("united
  Kerbalkind → launch from anywhere"), where it's valid gameplay. Mechanically grounded:
  `KerbalKonstructs` + RSS launch sites (already in the RO_clean loadout); RP-1 has a launch-site
  system to study and strip of its career coupling.
