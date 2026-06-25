# RP-AXE Architecture

Source of truth for **what we keep, what we axe, and how we transform RP-1's config** into a
lightweight, pluginless career. If you change the approach, update this file. Decisions are logged
in [`DECISIONS.md`](DECISIONS.md); the work breakdown is in [`TASKS.md`](TASKS.md).

## 1. Vision (the "why")

**RP-AXE = Ahistorical Xploration & Engineering.** RP-1's realism and curated tech tree, with the
entire *management* engine removed, the historical *rails* removed, and progression paced by
**science + exploration** instead of a timeline. One-line thesis: *the only challenge is
engineering, not logistics.*

Two pillars: **realism is kept** (RO/RSS/RealFuels/RealHeat/FAR/AJE/Kerbalism — separate mods, all
kept); **the career grind is axed** (build times, maintenance, tooling, crew training, the
Programs/Confidence economy, deadlines — all lived in RP-1's `RP0.dll`, which we never run).

## 2. Design invariants (do NOT violate)

1. **Plugin-free by default.** Behaviour comes from vendored config + stock systems + dependency
   mods. We *may* ship a small `AXE.dll` of **our own**, but only where research proves a contract
   check or feature genuinely can't be done in config (see §5). Never ship/load `RP0.dll`/`CC_RP0.dll`.
2. **Self-contained + `conflicts: RP-1`.** Vendored RP-1 config must never coexist with a real RP-1
   install (double-patching). CKAN metadata declares the conflict.
3. **Funds are ON, rebuilt light.** Not RP-1's plugin economy, not "no funds". Science is the
   primary gate; funds are a secondary budget with **no time pressure**. (Resolves OD1.)
4. **No time pressure anywhere.** No build time, research time, deadlines, or rep decay. (These were
   plugin systems — they vanish for free; just never re-introduce them.) Post-accept contract
   durations are fine.
5. **Science is finite & exploration-gated.** Each experiment/situation pays once; Kerbalism
   enforces fixed data quotas. Node costs must be budgeted **per-tier against reachable science**,
   or the player hits an unaffordable wall. Never assume grindable science.
6. **Don't re-place historical parts.** RP-1 already placed ~3,857 parts correctly — keep them.
   Original placement work is ONLY for new/futuristic part mods (and mind `OrphanNode`, §8).
7. **`seed/` and `design/` stay separated** (§8) so the upstream refresh is a clean diff.

## 3. The pivotal constraint (and why it's manageable)

RP-1's contracts are **not** trivially config-only. Of ~312 files / ~387 contract types, the
vast majority reference custom ContractConfigurator types from `CC_RP0.dll`, which itself
references `RP0.dll`. Coupling we measured:

| Custom type (origin) | ~uses | Plan |
|---|---|---|
| `ProgramActive` (req, CC_RP0→RP0) | 742 / ~362 types | **strip**; replaced by the program switcher (§6) |
| `AcceptContract` (behaviour, CC_RP0) | 496 | **stock CC has `AcceptContract`** — keep / re-point |
| `RP1ReturnHome` (param, CC_RP0) | 103 / ~98 | **swap → stock `ReturnHome`** (verify) |
| `RP1CollectScience` (param, CC_RP0) | 71 / ~62 | **swap → stock `CollectScience`** (verify) |
| `HorizontalLanding` (param, CC_RP0) | 38 | **triage** — stock approximate, strip, or `AXE.dll` |
| `VesselBuiltAt` (param, CC_RP0→RP0) | 27 | **delete** — guard rider, real objective survives |
| `AvionicsCheck` (param, CC_RP0→RP0) | 24 | **delete** — guard rider (avionics is axed) |
| `DownrangeDistance`, `ImpactCB`, `ReachMach`, `RP1Rendezvous`, `RP1NoDocking`, `RP1HasExperiment`, `RP1HasSamples` | a few each | **triage** per type |
| `AddToGroundSegment`, `AchieveConnectionAvailability` | ~45 / ~135 | **NOT CC_RP0** — RealAntennas-backed (kept dep). **Verify they load**, then trust. |

Key realisations: (a) the biggest hitters either strip (`ProgramActive`) or swap to stock
(`ReturnHome`, `CollectScience`, `AcceptContract`); (b) the guard riders (`AvionicsCheck`,
`VesselBuiltAt`) delete cleanly because the real objective lives in sibling stock parameters;
(c) some "custom" types are actually RealAntennas, which we keep. The residue is a short list of
low-count checks (`HorizontalLanding`, `DownrangeDistance`, `ReachMach`, …) that get triaged
per-type in Pass A.

## 4. Keep / Axe / Reimplement map

| Subsystem | RP-1 source | RP-AXE decision |
|---|---|---|
| Realism stack (RO, RSS, RealFuels, RealHeat, FAR, AJE, Kerbalism, RealAntennas…) | external mods | **KEEP** (same deps) |
| Tech tree (nodes, costs, part→node placement, OrphanNode) | `Tree/**` | **VENDOR** to `seed/` — config-only, loads via `@TechTree` MM patch, no plugin |
| Science rebalance | `Science/**` | **VENDOR** to `seed/` — pure config; tune pacing in `design/` (Pass E) |
| Contracts | `Contracts/**` + `CC_RP0.dll` | **VENDOR** seed + **de-rail/convert/strip** in `design/` (Pass A) |
| Programs | `Programs/Programs.cfg` + `ProgramHandler` (RP0) | **REPLACE** with config-only program switcher (Pass B); `Programs.cfg` is funding *reference only* |
| Contract rewards | program `baseFunding` (RP0) | **REBUILD** as per-contract `rewardFunds`/`rewardScience` (Pass C) |
| Parts funds sink | RP0 tooling/maintenance | **REBUILD** via part `entryCost` (Pass D; LRTR values + RO core hand-priced) |
| Avionics (`ModuleAvionics`, proc avionics) | RP0 | **AXE** — craft become stock-controllable; remove inert proc-avionics parts; guarantee start-node command part (Pass G) |
| Build/integration times, KCT, maintenance, tooling, crew, confidence/unlock-credit, leaders, milestones, careerlog, editor warnings | RP0 | **AXE** — gone by design (this is the grind) |
| Near/far-future parts | RP-1 *suggests* | **PROMOTE** to expected end-game content (Pass F, needs RO/RSS scaling) |

## 5. Contract transformation strategy (config-first, plugin as researched fallback)

`design/Contracts/` holds ModuleManager patches that run **before** ContractConfigurator parses the
contract types — so a patch can rewrite a contract's `type =` field, delete a parameter, or zero a
reward, and CC only ever sees the transformed result. Pass A is therefore mostly find-replace and
delete patches (see [`TASKS.md`](TASKS.md) Pass A and the table in §3).

**The DLL question (per the plugin decision):** we keep a boilerplate `AXE.dll` scaffold in
[`../Source/AXE`](../Source/AXE) **ready**, but reaching for it is gated on a **per-CC-type triage**
(a Pass-A research task): for each residual custom type, decide *tweak-in-cfg* vs *strip* vs
*implement in code*. Many may need no code at all. We only write a custom `ParameterFactory`/
`ContractRequirement` when stock config genuinely can't express the check. This honours "plugin-free
by default" while keeping the escape hatch the decision asked for. The plugin is also the home for
any *optional* future feature (e.g. an avionics-by-mass control model — explicitly out of scope for
v0).

## 6. Program switcher (replaces ProgramHandler) — Pass B

RP-1 "programs" did two jobs: **gate** which contracts are offered, and run a **funding/confidence
economy**. We keep gating (config-only) and drop the economy.

- For each program, author a trivial **"Activate [X] Program"** contract (always available).
- Member contracts gate on `REQUIREMENT { type = AcceptContract; contractType = Activate_X }`
  instead of the stripped `ProgramActive`.
- Result: opt-in themed bundles, **any order** (ahistorical), pluginless, no funding/clock/
  confidence. Early programs keep this gating for onboarding; late/exotic ones can be left open.

No `AXE.dll` is required for the switcher — it's pure ContractConfigurator.

## 7. Economy model — Passes C, D, E

- **Rewards (C):** contracts currently pay 0 (RP-1 parked income in program `baseFunding`). Take each
  program's `baseFunding` (from `Programs.cfg`, reference only) and distribute it across that
  program's member contracts as per-contract `rewardFunds` (capstone heavier than stepping-stones).
  `rewardScience` is a **modest supplement** to Kerbalism income, not the main source.
- **Parts sink (D):** most `entryCost` is `1`. Rebuild a real sink — lift LRTR's per-part values for
  add-on/futuristic mods (prices only, keep our `TechRequired`), hand-price RO core from
  `EntryCostModifiers.cfg`. Remember the dominant RSS drain is **per-launch vehicle cost**, not
  entry cost — balance era income (C) to comfortably cover era vehicle costs.
- **Science pacing (E):** keep the vendored `Science/` (ROKerbalism profile); target a **moderate**
  pace via the global multiplier; keep frontier nodes expensive; budget node costs per-tier against
  reachable Kerbalism quotas (invariant 5). The futuristic extension (Pass F) is the one region with
  no upstream balancing — hand-budget it.

## 8. Tech tree, OrphanNode & the update model

- Tree loads via a `@TechTree` MM patch (stock R&D) — no plugin. Vendored in `seed/Tree/`.
- **`OrphanNode.cfg` sweeps any part still on a stock/CTT node into a hidden `orphanParts` node.**
  So every newly-added (futuristic) part **must** be explicitly placed in `design/Tree/` or it
  vanishes. Keep the orphan hook as-is; maintain coverage by periodic whitelist refresh from RP-1.
- **`seed/` = pristine upstream import** (never edit). **`design/` = our patches**, applied
  `:AFTER[...]`/`:FINAL` and tagged `:FOR[RP-AXE]`. This keeps the periodic `sync-seed.ps1` refresh
  a clean diff and lets most upstream changes flow in for free.

## 9. Known consequences to verify in-game (config alone can't tell us)

- Do `.truecolor` node icons render pluginless (ROLibrary may load them) or fall back to blank?
- Do `AddToGroundSegment` / `AchieveConnectionAvailability` contracts load with RealAntennas but no
  RP0 plugin? (Verify one before trusting all.)
- Does engine-config / tank-type tech gating still hold (driven by RealFuels / stock upgrades, not
  the plugin)?
- Is the `start` node actually flyable (command part + enough to loft a first sounding rocket)?
- Per-tier science solvency: sum Kerbalism quotas per reachable destination; confirm each tier's
  node costs are affordable from that tier's new science.
- Tech progression without avionics gating — does the tree still feel like progression? *(user flag)*
