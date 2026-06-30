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

## Roadmap (critical path)
Each phase gates the next; avionics + contracts ride alongside, off the critical path.

- **P0 — Part list** ✅ **DONE** (= T1). Manifest locked: **`manifest/curated-parts.tsv` (1,820 parts)**,
  built reproducibly by `tools/build_manifest.py`; full curation log in `docs/PARTLIST.md`.
  **→ P1 is now unblocked.**
- **P1 — Tree architecture.** Branch taxonomy (engineering disciplines, real names); node schema
  (id / tier / deps / `anyToUnlock` / flavor text); editor + build pipeline (lean on ETT).
  **Prove:** a documented branch map + schema; tooling renders a stub tree.
- **P2 — Tree skeleton (parity).** Place the whole manifest so every part has a home (~200 nodes),
  tiered node costs; convergence gates + multi-entry paths; Experimental side-node catches the rest.
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

### T2 — Science-budget audit (with KerbalismLab) ✅ AUDIT DONE → full writeup in [`SCIENCE.md`](SCIENCE.md)
Budget measured before setting node costs. Tools: `tools/science_budget.py` (probe),
`tools/lab_inventory.py` → `manifest/lab-experiments.tsv` (lab). Headline numbers:
- **Probe science (RP0\*, 98 exp):** ~2.57M theoretical max across RSS (fully ground-truthed: cache
  biome weights + RP-1's real `BodyAllowed` body restrictions — 49 exp Earth-only incl. `photos4`@10k).
  Back-loaded — Earth+Moon only **49k**, outer planets ~1.8M. Realistic ~0.5–1.0M. (RP-1 full tree ≈ **115k**.)
- **Crewed-lab science (KerbalismLab, 71 exp):** values 10–500 (median 25); **~51k** realistic (~8 crewed
  bodies), ~205k theoretical-max — a mid-game **station stream** ~= home-system probe science, funding the
  early-mid "station valley". UnlockTechs cluster early-mid (stock names → remap to AXE).
- **Tree-budget target → ~150k–400k total node cost** (anchored on RP-1's 115k); per-tier must mirror the
  back-loaded availability (cheap early, expensive late). Drives P1.
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
