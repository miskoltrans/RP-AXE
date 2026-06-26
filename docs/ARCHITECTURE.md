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

1. **Config-first; our own minimal `AXE.dll` where config can't reach.** Behaviour comes from
   vendored config + stock systems + dependency mods wherever possible. Never ship/load
   `RP0.dll`/`CC_RP0.dll`. **NOTE (D6/D8): `AXE.dll` is now load-bearing, not optional** — it
   implements the 14 ContractConfigurator types every ported contract needs (D6), enables Career
   (D5), runs the free-parts economy + generous start (D8), and is the program switcher's real
   gating. If it fails to load, no career loads. (The original "plugin-free by default" posture is
   superseded; "config-first for *content*, small own plugin for *mechanics*" is the live stance.)
2. **Self-contained + `conflicts: RP-1`.** Vendored RP-1 config must never coexist with a real RP-1
   install (double-patching). CKAN metadata declares the conflict.
3. **Funds ON; parts unlock FREE (D8 supersedes the entryCost sink).** Science is the *only* gate on
   *what* you can build; the only ongoing funds sink is **launch cost** (the entryCost sink was
   abandoned). RealFuels engine-CONFIG charging is the one kept buy-to-unlock. No time pressure.
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
| Parts funds sink | RP0 tooling/maintenance | **DROPPED (D8)** — parts unlock **free** (`ZeroEntryCost.cfg` + `FreePartUnlock.cs`); only funds sink is **launch cost**; RealFuels engine-CONFIG charging kept |
| Avionics (`ModuleAvionics`, proc avionics) | RP0 | **AXE** — craft become stock-controllable (stock `ModuleCommand`); start-node command guaranteed (D9/M6, `StartParts.cfg`); inert proc-avionics parts **kept** (still work as probe cores) |
| Build/integration times, KCT, maintenance, tooling, crew, confidence/unlock-credit, leaders, milestones, careerlog, editor warnings | RP0 | **AXE** — gone by design (this is the grind) |
| Near/far-future parts | RP-1 *suggests* | **PROMOTE** to expected end-game content (Pass F, needs RO/RSS scaling) |

## 5. Contract transformation strategy (the plan; see the D6 update box for what shipped)

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

> **Update (D6 — what actually happened).** The per-type triage concluded RP-1's 14 custom CC types
> are mostly self-contained stock-logic, so we implemented our **own** versions of all of them in
> `AXE.dll` (`Source/AXE/Contracts/`, table in `_CCTYPES.md`) under their registered names — the
> ported contracts then load **verbatim** (356/356, AutoTest). `design/Contracts/` ended up holding
> only *fixups* (dedupe, Uranus/Neptune moon-group plumbing), not the broad config type-swap this
> section originally envisioned. So the DLL is load-bearing (invariant 1), not a dormant fallback.

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
- **Parts sink (D) — DROPPED (D8):** parts unlock **free** (`ZeroEntryCost.cfg` + `FreePartUnlock.cs`).
  The only ongoing funds sink is **per-launch vehicle cost** (Σ part `cost` + propellant, 90 %/95 %
  recovered) — exactly the "dominant RSS drain" this section always warned about; RealFuels
  engine-CONFIG charging is the one kept buy-to-unlock. Income (C, scaled ×1.25) + 100 k start
  (`GenerousStart.cs`) fund the missions. **Open:** mid/late solvency vs procedural big vehicles.
- **Science pacing (E):** kept the vendored `Science/` at **RP-1 ×1.0** (a ×0.8 trim was tried and
  **reverted**, D9 — the solvency audit showed ~57× headroom, so science is *not* a binding gate).
  **Earth sub-40 km science removed** (`EarthScienceRemoval.cfg`) so the home planet isn't a farm.
  The futuristic extension (Pass F) is the one region with no upstream balancing. See
  [`SCIENCE_AUDIT.md`](SCIENCE_AUDIT.md).

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
- Is the `start` node actually flyable? **Config-complete (D9/M6 — 549 parts on `start`: command,
  engines, guidance, tanks, antennas, instruments). The build-and-fly proof is still a play session.**
- Per-tier science solvency: **audited (`SCIENCE_AUDIT.md`) — ~57× headroom, solvent at every era;
  a play session confirms it *feels* right.**
- Tech progression without avionics gating — does the tree still feel like progression? *(user flag;
  sharpened by the audit: science is abundant, so science is a weak gate — see playtest watchlist.)*
