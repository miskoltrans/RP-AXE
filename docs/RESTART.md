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

### T3 — Upgrade realization (engine progression) — P2/P3 ✅ AUDIT + CURATION DONE → [`UPGRADES.md`](UPGRADES.md)
The part diff only compares `PART` nodes, so RP-1-authored `PARTUPGRADE`s are invisible to it. `tools/upgrade_audit.py`
(→ `manifest/upgrades-absent.tsv` + `manifest/upgrades-live.tsv`) enumerates them; `tools/curate_upgrades.py`
(→ **`manifest/upgrades-curated.tsv`**) orphan-filters + dispositions them. The 71 live are mod-authored (Coatl,
RealAntennas, ROSolar…), present via their mods.
- **626 RP-1-authored PARTUPGRADEs, ALL absent** under AXE. Curated to **553 KEEP · 45 REFERENCE · 28 DROP**
  (user decisions folded in: HDD keep, avionics→reference, orphans keep, axed-career examined, N1 clusters sacked):
  - **462 KEEP-engine** + **53 KEEP-engine-dormant** + **2 DROP-no-curated-host** (of 517 `Tree/TREE-Engines.cfg` RFUpgrade_*).
    Each unlocks engine `CONFIG X`; **orphan filter = reproduce RP-1's own `deleteme`/`Tree/UpgradeCleanup.cfg` offline**
    (parse live cache `Module*EngineConfigs`→`CONFIG`→host PART vs 1820 curated). 53 configs absent from our RO
    (e.g. `Merlin1B`,`NK-32`,`11D23`) → **KEPT as dormant** (vendor TREE-Engines.cfg whole; inert via deleteme, wakes if
    a mod adds the engine; **31/34 of their nodes already in the keeper remap** → forward-compat for ~3 extra lines).
    2 (`30x_NK-33`,`8x_NK-43`) = N1 Block A/B cluster configs whose only host is the uncurated SXT N1 stages → **sacked**
    (standalone ROE-NK33/NK-43 engines ARE curated; no curated cluster part).
  - **15 KEEP-engine-typelevel** (`Tree/RFTechLevels.cfg`, per engine-TYPE); **23 KEEP-capability** — PFTech-Fairing (6),
    X2Cockpit (1), ComSat/NavSat bus (6), **HDD data-storage (10, KEPT** — Kerbalism `KERBALISM_HDD_SIZES` subsystem,
    `Science/HardDriveConfigs.cfg`). Each pairs with a `%UPGRADES`/companion patch to vendor.
  - **35 REFERENCE-avionics** (`Tree/ProceduralAvionics.cfg`) — AXE's `ModuleAxeAvionics` TIER ladder already supersedes
    them (and `AxeAvionicsCore.cfg:115-118` deletes the icons); **keep `AVIONICSCONFIGS` as the impl reference.** Gap AXE
    hasn't built = per-tier **kOS** integration (`kosDiskSpace`/`kosECPerInstruction`/…) + `hasScienceContainer` gating;
    `costFactor` + Deep-Space/`interplanetary` deliberately dropped. See [[rp-axe-avionics-core]], UPGRADES.md §C1.
  - **10 REFERENCE-comms-dsn** (`Tree/TechFacilityUpgrades.cfg`) — DSN tracking-station tech gated by comms nodes; ref for
    AXE comms/ground-station axis, pairs with live RealAntennas `commsTL1-10`.
  - **26 DROP-axed-career** — `rp0Engineer/ResearcherUpgrade*` (22, KCT personnel efficiency, `description=unset`, dead) +
    `airlaunchTL*` (4, RP-0/KCT airlaunch plugin).
- **Sandbox unaffected** (auto-unlocks all upgrades); the gap is **career progression only**.
- **The work (P2):** vendor TREE-Engines.cfg whole + UpgradeCleanup.cfg + RFTechLevels.cfg + capability companions + the
  HDD subsystem, then **remap each kept `techRequired` → AXE node** — **115 distinct RP-1 nodes** (+3 orphan-only). Tree-coupled →
  **blocked on P1 nodes existing**; do it in P2 alongside placement. Drives off `manifest/upgrades-curated.tsv`.

## Reference instances (outside the repo — never nuke)
- `../ksp_instance_clean` — pristine rebuild base; copy it to spin up a fresh test instance.
- `../ksp_rp1_clean`, `../ksp_ro_clean` (+ `_expanded`) — clean RP-1 / RO references (used for the part diff).
- Other `../ksp_*` folders hold various mod combos. **Some may be in a messed-up state — validate the
  actual installed mods (`ls GameData` / `CKAN/registry.json`) before trusting any non-`*_clean` folder.**

## Parked ideas (later threads)
- **X-plane program contracts** (decided direction, 2026-07-01, early-tree review) — the aviation track is
  deliberately roleplay/side-content and is NOT expected to recoup science (it flies the SCIENCE.md-zeroed
  sub-40 km regime). Its reward loop is a set of **special x-plane-program contracts** paying MONEY (the
  VISION "money abstracts non-simulated tradeoffs" lever) — sound-barrier / altitude / speed-record milestones,
  X-plane research flights, etc. This is why the tree does NOT try to make the aviation ladder science-solvent.
  Contract authoring rides the contracts thread (port-and-strip from RP-1). See [`TREE.md`](TREE.md) §3B/§8.
- **Procedural-part mass/cost tax audit** (economy design, 2026-07-01) — ground-truthed whether AXE's
  workhorse procedural parts (`Parts mix` decision above) are penalized vs. named/stock counterparts for
  the flexibility of not picking a fixed real hardware analog. Audited all curated procedural part types
  against RO's actual configs + the mod's own source comments. **Mixed picture, not a blanket tax** — 3 of
  8 categories are genuinely taxed, one looks like an RO patch-ordering bug, and two already favor custom
  design:
  - **`proceduralStackDecoupler` — REVISED: not a magnitude tax, but has no upgrade path.** Initial
    read (below) called this TAXED off the "arbitrary coefficients" comment alone; computing the actual
    formula against matched diameters overturns that. Real formula (`KSP-RO/ProceduralParts`
    `Source/DecouplerTweaker.cs`, `usePFStyleMass` branch): `mass = (x·d³ + y·d² + z·d + w) ×
    decouplerMassMult` with RO's `(x,y,z,w) = (0.0002, 0.0075, 0.005, 0)`, `decouplerMassMult = 4`.
    Evaluated at the named decouplers' own diameters: TD-06 0.625m 20kg vs proc 24.4kg (+22%); TD-12
    1.25m 80kg vs proc 73.4kg (**−8%**); TD-25 2.5m 350kg vs proc 250kg (**−29%**); TD-37 3.75m 500kg vs
    proc 539kg (+8%). That's noise around parity, not a systematic tax — procedural is sometimes lighter.
    (TD-18 1.875m 12kg vs proc 148kg looks catastrophic but is TD-18 itself being an outlier-light real
    part, not procedural being punitive.) **Real standing issue: no tech-tier improvement curve** — the
    formula is permanently flat regardless of era, unlike real isogrid tanks which get lighter with
    research (below). RO also deletes the stock size-tier `UPGRADE` blocks entirely (full size range
    unlocked from tech `start`), so there's no path to improve it over a career at all. **DECISION
    (2026-07-01): no action.** Mass is already roughly at parity with real parts (not taxed), so a
    tech-tier improvement curve would be solving a problem that isn't actually costing anything
    competitively — documented for reference only, not queued as work.
  - **`proceduralStructural` — REVISED AGAIN: comparing against RO's cited "isogrid" ideal was
    misleading; against real competing parts, procedural wins.** Resolved `dryDensity = 0.03` (30 kg/m³)
    is still accurate, but the isogrid ladder (16→6.5 kg/m³) it was checked against turns out to be a
    red herring: **no actual named part in this modlist uses the isogrid RF type** — it's not something
    you'd really be choosing between. Checking what stock/named cylindrical hulls actually use instead
    (`mk2Fuselage`, `mk2FuselageShortLiquid`, `rocketNoseCone`, and even `Mk1FuselageStructural` — which
    RO silently renames to "Fuselage (Pressurized)" and reassigns `type=Fuselage`, since RO never leaves
    a stock cylindrical hull as dead structure) all resolve to RF's `Structural`/`Fuselage` types, both
    `basemass = 0.000039/L` = **39 kg/m³** (`RealFuels/Resources/RealTankTypes.cfg`). Procedural
    structural (30 kg/m³) is **23% lighter** than this real, currently-active reference — the opposite
    of taxed. Zero upgrade path still stands (`RO_ProceduralParts.cfg` line 1:
    `!PARTUPGRADE[ProceduralParts*]:BEFORE[RealismOverhaul] {}`, blanket-deletes every ProceduralParts
    upgrade), but that's now a moot/neutral point rather than a fix target — there's no real-part
    tech-ladder it's failing to keep pace with. **No action needed.**
  - **`proceduralCrewTube` — density is roughly at PARITY against real competition (not taxed, not
    rewarded); the cost premium is separate and still real.**
    1. **Density:** checked against 3 sizes of `StationPartsExpansionRedux` `sspx-tube-*` ("Pressurized
       Crew Tube," explicitly bare/fixture-less, a fair match), correcting for RO's 1.8x rescale:
       2.25m → 68.9 kg/m³, 4.5m → 46.7 kg/m³, 6.75m → 47.4 kg/m³. Procedural's 50 kg/m³ beats the
       smallest but is **5-7% heavier** than the two larger, more representative sizes — call it parity.
       The internal inconsistency vs. its own sibling Structural (0.05 vs. 0.03, from being cloned in a
       `:BEFORE[RealismOverhaul]` pass before the later density-reduction patch, which never lists
       CrewTube) is a real, cheap (one-line), zero-risk fix if ever revisited — but **DECISION
       (2026-07-01): no action**, documented for reference only.
    2. **Cost (still a deliberate RP-1 design choice, unaffected by the density finding):** resolved
       `costPerkL = 24.5` vs. Structural's `0.5` (49x) traces to `RP-1/GameData/RP-1/ProcCosts.cfg`,
       vendored verbatim into `RP-AXE/seed/ProcCosts.cfg` — pricing crew tubes far above plain structural
       (pressure-vessel/life-support-grade construction cost). Its `ModuleToolingPTank` (further 3x)
       is already correctly stripped per the Tooling-REMOVED decision. **DECISION (2026-07-01): no
       action** — keep RP-1's pricing as-is, documented for reference only.
  - **Standing lesson, reinforced twice now:** when RO's own comment cites a comparison ("equivalent to
    isogrid tanks"), verify that comparison is to something a real part actually uses — not an idealized
    RF type nobody is assigned to. Two separate "TAXED" verdicts in this audit turned out to rest on
    exactly that mistake.
  - **`proceduralNoseCone` — REWARDED, no fix needed.** 30 kg/m³ vs. the named nose cone's own
    RealFuels-assigned 39 kg/m³ density — ~23% *lighter* than picking the stock part.
  - **Procedural tanks (curated `RO-RFTank-Integral/Separate/BalloonNew/SM/Spaceplane`) —
    PARITY-to-REWARDED, no fix needed.** Share the exact same tech-progressive RO tank-type system
    (`RO_RealFuels_PartConfigs.cfg`) that RO's own dedicated named-tank mod (ROTanks) uses — procedural
    tank builders have strictly *more* options than stock-tank users frozen on legacy tank types.
  - **`proceduralHeatshield` — N/A for AXE, and confirmed why.** ProceduralParts' native heatshield part
    does carry a ~6.4x tax (never wired into RO's shared heatshield mass formula), but it **isn't in the
    curated manifest** — AXE already uses `ROH-AdjustableHS` (ROHeatshields), which achieves full parity
    with named heatshields by design. Root-caused (2026-07-01): RO itself sets `%RSSROConfig = False` on
    it (`RO_ProceduralParts.cfg:112-122` — every *other* procedural part gets `= True`), which RO's
    `HardRemoveNonRO` mechanism then hard-deletes. Confirmed live in the current instance: zero
    `proceduralHeatshield` entries in `ModuleManager.ConfigCache`, delete logged in `MMPatch.log`. Not an
    AXE curation call and not RP-1's doing either (RP-1's own redundant delete in
    `Tree/StartNodeRemoval.cfg` never even applies — no RP-1/RP-0 folder in this instance) — it's RO's
    own upstream plausibility judgment, already covered by the T1 curation rule that treats RO's
    plausibility floor as inherited. No action needed.
  - **`proceduralTankOre` — divergence flag.** That same RP-1 `StartNodeRemoval.cfg` also deletes
    `proceduralTankOre` and `proceduralTankTAC`. TankTAC is independently gone anyway (its own RO
    plausibility flag). But **TankOre is alive in the current instance and sits in the curated manifest**
    — confirmed via `ModuleManager.ConfigCache` — purely because AXE doesn't install RP-1 and so never
    inherits that specific deletion. Concrete instance of the general "re-cut RP-1's cuts" risk from
    [[axe-replaces-not-depends-rp1]]. **DECISION (2026-07-01): no action** — keep it curated as-is,
    documented for reference only.
  - **`proceduralBattery`** — deleted outright by RO (`-PART[proceduralBattery]`); moot, not curated.
  - **Bottom line (2026-07-01): no action taken on any of the above.** The audit's real value was
    correcting the verdicts, not generating a work list — decoupler/structural/nose cone/tanks came back
    fine-to-favorable once checked against real competing parts instead of RO's own cited (and
    misleading) comparisons; the two remaining loose ends (crew-tube density bug, crew-tube cost premium,
    TankOre divergence) were reviewed and deliberately left as-is. Kept here as reference in case any of
    it becomes relevant again, not as queued P2/P3 work.
- **Airlaunch** — RP-1's airlaunch is an interesting feature we **sacked** with the KCT/RP0.dll
  career layer (T3, 2026-07-01). It is not a part: you build a vessel, KCT "mounts" it on a notional
  carrier aircraft (time + funds), and it **spawns already airborne** inside an unlocked envelope.
  Envelopes (`SCMData/AirlaunchLevels.cfg`, `KCTAIRLAUNCHTECHS`) are tech-gated and modeled on real
  carriers — B-29→X-1 (7.6 km, 7.5 t), B-50→X-2 (9.1 km, 11.3 t), B-52→X-15/X-15A-2 (13.75 km,
  15→25 t). The mass/size check is `AirlaunchTechLevel.CanLaunchVessel`. Reimplementing it for AXE
  would be a **plugin** (spawn a vessel airborne within an envelope, gated by tech node), reusing
  `AirlaunchLevels.cfg` + `Source/RP0/SpaceCenter/AirlaunchTechLevel.cs` / `UI/KCT/GUI_Airlaunch.cs`
  as the reference — not a config port. (The dropped `airlaunchTL1-4` PARTUPGRADEs were only tree
  icons; see [`UPGRADES.md`](UPGRADES.md) §D.)
- **Relocatable / selectable KSC** — let the player choose or move the launch site ("united
  Kerbalkind → launch from anywhere"), where it's valid gameplay. Mechanically grounded:
  `KerbalKonstructs` + RSS launch sites (already in the RO_clean loadout); RP-1 has a launch-site
  system to study and strip of its career coupling.
- **Fuel as a usability gate** (tree design, 2026-07-01) — make propellants *unlockable*, keyed off
  Propellant Chemistry's tier ladder = the real fuel-availability timeline (alcohol/LOX & crude kerolox
  ~1950 → RP-1 ~1957 → storable hypergolics late-50s/60s → hydrolox ~1963 → methalox/densified 2010s).
  An engine homed/gated by its *bottleneck* discipline becomes **usable only once its fuel's tier is
  reached** — so a "1963 hydrolox" engine researched early still can't fly until cryogenic fuel
  production matures. Gives the "research the hardware, then unlock its fuel to use it" dynamic and makes
  Propellant Chemistry a load-bearing cross-cutting axis **with no tree edges** (kills the fuel-hub
  spaghetti). Keys off the RealFuels **engine-config** propellant (an engine can fly kerolox now, gain a
  hydrolox config later) — same axis as the curated upgrades. **Same mechanism family as the VISION
  probe "prerequisite-tech checklist"** — one plugin + checklist UI ("⚠ needs LH2 — unlock in Propellant
  Chemistry") could serve both. NEW mechanic (RP-1/RO don't gate fuel *use*), so **post-MVP**. This is
  why the tree drops "true-but-routine" fuel edges (kerosene→F-1): fuel realism lives on the Prop-Chem
  ladder + this gate, not in per-engine prerequisite edges.
