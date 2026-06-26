# RP-AXE Decision Log

Append-only record of architectural decisions. Newest at the bottom.

---

### D0 — 2026-06-25 — Project charter

RP-AXE is a config-first, lightweight career/science layer on RP-1's realism stack. Realism kept;
RP-1's career grind axed. Ahistorical/what-if. Near/far-future parts are expected content.
Contracts guide early game then step aside. MVP scope. (From project brief.)

### D1 — 2026-06-25 — Contracts: PORT & STRIP

**Context:** RP-1's 312 contracts are pervasively coupled to `CC_RP0.dll` (e.g. `ProgramActive`
used 742× across 300/312 files), which itself depends on `RP0.dll`. Pure-config yoinking is
impossible.

**Options weighed:** (A) author a fresh lightweight set; (B) ship RP-1's plugins; (C) port & strip.

**Decision: (C) Port & strip** RP-1's contracts — remove/replace RP0 coupling rather than
rewriting from scratch or shipping RP-1's plugins.

**Why it's viable (not the "enormous/lossy" version):** combined with D2, we reimplement the custom
CC types under their **existing registered names** in our own DLL, so most ported contracts load
nearly verbatim. See ARCHITECTURE §5.

### D5 — 2026-06-25 — RealismOverhaul gates Career/Science → fixed via AXE.dll reflection

**Discovery during M1:** with RP-1 removed, RealismOverhaul.dll Harmony-patches
`MainMenu.ConfirmNewGame` and forces **"Only Sandbox Supported"** for Career & Science. Verified
against the RO source (cloned shallow to `C:\git\ksp\RealismOverhaul`, `Source/Harmony/MainMenu.cs`):

```
_hasRP1 = AssemblyLoader.loadedAssemblies.FirstOrDefault(a => a.name == "RP-0") != null;
if (_needCheckDB) { ...read REALISMOVERHAULSETTINGS{allowCareer}... }   // _needCheckDB inits FALSE, never set
if (_hasRP1 || _overrideCareer) return true;                            // else: sandbox-only popup
```

Two consequences: (1) RO detects RP-1 by a **loaded assembly named `"RP-0"`**; (2) the
`REALISMOVERHAULSETTINGS { allowCareer }` config override is **dead code** in the shipped build —
**so there is no pure-config fix.**

**Decision:** flip RO's private `_overrideCareer` flag by reflection from our own `AXE.dll`
(`Source/AXE/EnableCareer.cs`, a MainMenu KSPAddon). We do **not** name our assembly `"RP-0"` —
that would also trip every `:NEEDS[RP-0]` ModuleManager patch (uncontrolled RP-1-tuned config).
This is the first real use of the D2 "minimal own plugin" escape hatch. The inert config node is
kept as future-proofing (see `design/Settings/RO_EnableCareer.cfg`).

### D2 — 2026-06-25 — A minimal plugin of OUR OWN is allowed

**Context:** the program starter and several contract checks (Mach, downrange, return-home, collect-
science) have no stock ContractConfigurator equivalent.

**Decision:** MVP stays config-first, but we **may ship a minimal `AXE.dll`** — a ContractConfigurator
extension + a simple program ScenarioModule. Explicitly **not** RP-1's plugins, and explicitly
**not** a reimplementation of KCT/maintenance/tooling/avionics/crew.

**Implication:** the repo needs a `Source/` tree and a build step (see WORKFLOW.md).

### D3 — 2026-06-25 — Merge with the build brief (supersedes the framing of D1/D2)

The user's prior build brief was reviewed and merged. It refines D1/D2:

- **Config-first via `seed/`+`design/` split.** Vendor RP-1 config pristine in `seed/`; do all
  transformation as ModuleManager patches in `design/` (`:AFTER[...]`/`:FINAL`). MM runs before
  ContractConfigurator parses contract types, so Pass-A patches rewrite `type =`, delete params,
  and zero rewards before CC ever sees them. This is the primary mechanism — *not* "reimplement
  custom types in our DLL" (the old D1/§5 framing).
- **Plugin = researched fallback, not default.** Per the plugin decision: keep a **boilerplate
  `AXE.dll` scaffold ready**, but gate using it on a **per-CC-type triage** (Pass A research) —
  default to config (swap-to-stock / strip); write code only where stock genuinely can't express a
  check. Honours "plugin-free by default" while keeping the escape hatch.
- **Funds ON, rebuilt light** (see D4). **Name confirmed:** "Ahistorical Xploration & Engineering".

### D4 — 2026-06-25 — Funds ON, rebuilt (resolves OD1) — ⚠️ SUPERSEDED by D8 (parts now free; sink = launch cost)

Career with funds, **not** science-only and **not** RP-1's plugin economy. Science is the primary
gate; funds are a secondary budget with **no time pressure**. Income = per-contract rewards
(program `baseFunding` redistributed, Pass C); sink = part `entryCost` (Pass D). OD1 closed.

### D6 — 2026-06-25 — M2: write our OWN CC types in AXE.dll (✅ VALIDATED via AutoTest 2026-06-26)

Research (reading `CC_RP0` source) showed RP-1's 14 custom contract types are *mostly* self-contained
stock-logic, not coupled to the RP0 career engine. Per direction ("write our own from scratch; use
stock where it's complicated; transmit science is enough"), we implemented our own versions in
`AXE.dll` (`Source/AXE/Contracts/`), **not** forking `CC_RP0`:
- **Real:** `ReachMach`, `DownrangeDistance`, `RP1ReturnHome` (simplified), `RP1CollectScience`
  (simplified to "science received"), `AcceptContractBehaviour`.
- **No-op (always-pass):** `HorizontalLanding`, `AvionicsCheck`, `VesselBuiltAt`, `RP1Rendezvous`,
  `RP1NoDocking`, `ImpactCB`, `RP1HasSamples`, `RP1HasExperiment`.
- **`ProgramActive`:** always-true stub → real gating in M4.

CC auto-discovers our factories by class name (`XxxFactory` → `type = Xxx`). Full table:
`Source/AXE/_CCTYPES.md`. **Builds clean but NOT yet validated in a running game** — see the M2
validation checklist in `docs/TASKS.md`. M3/M4 depend on this validating.

### D7 — 2026-06-25 — M3 + M4 first-pass implemented (✅ VALIDATED via AutoTest 2026-06-26; Pass D later superseded by D8)

At the user's direction ("do 1 and 2"), implemented the next milestones on top of the still-
unvalidated M2 rather than waiting:
- **M4 program switcher:** `AxeProgramHandler` (ScenarioModule), `ActivateProgram` behaviour, and
  `ProgramActive` made **real** (was the M2 always-true stub). 12 early "Begin Program" charters
  with a guided chain (`design/Programs/ActivatePrograms.cfg`). Added an `AXEInstant` parameter so
  charters complete at the space centre.
- **M3 Pass C:** flat per-program `rewardFunds` on gated contracts (`design/Rewards/ProgramRewards.cfg`).
- **M3 Pass D:** conservative category-default `entryCost` (`design/EntryCosts/Defaults.cfg`).
- **Expression stub:** `RP1CommsPayload`/`RP1WeatherPayload` → 0 (`ExpressionFunctions.cs`).

Consequence: making `ProgramActive` real **changes the validation flow** — gated contracts now appear
only after accepting a charter. Validation is therefore a single **combined M2+M3+M4** pass (checklist
in `docs/TASKS.md` M2). Known risk to watch: charters surfacing under KSP's offered-contract limit
(RP-1 raised it via plugin; we don't).

### D8 — 2026-06-26 — Economy pivot: parts unlock FREE (supersedes D4 + invariant 3's entryCost sink)

After in-game review the economy is reframed: **exploration + engineering, not management.** This
**supersedes D4 / ARCHITECTURE invariant 3** ("sink = part `entryCost`", Pass D).

- **Parts unlock free with science** — science is the *only* gate on *what* you can build. The
  entryCost funds-sink (Pass D) is **abandoned**. Implemented as `design/EntryCosts/ZeroEntryCost.cfg`
  (`@PART[*]:FINAL %entryCost = 0`) **plus** `Source/AXE/FreePartUnlock.cs` (reflect-zeroes the private
  `AvailablePart._entryCost` after RealFuels/ProceduralParts recompute it at load — config alone can't
  reach those ~936 parts).
- **NOT via `BypassEntryPurchaseAfterResearch`** — that flag *also* disables RealFuels' engine-CONFIG
  charging, which we deliberately **keep** (verified: `RP0/Harmony/RealFuels.cs` gates config cost on
  the flag; `RealFuels.dll` honours it).
- **RealFuels engine-config development is the one buy-to-unlock with engineering meaning** — kept,
  and works without RP0 (RF resolves the `ENTRYCOSTMODS` tree itself; e.g. Aestus config = 70 000,
  verified at runtime).
- **Launch cost (Σ part `cost` + propellant, 90 %/95 % recovered) is the only ongoing funds sink.**
- **"Generous" bite (locked, not for further tuning):** 100 000 starting funds
  (`Source/AXE/GenerousStart.cs`, a ScenarioModule — CustomBarnKit has no `startingFunds` field),
  contract income ×1.25 (`design/Rewards/FundsTrim.cfg` `globalHardContractMultiplier` +
  `ProgramRewards.cfg`), CBK building-upgrade costs left at defaults.
- **Canonical record:** this entry + the doc-comments in `GenerousStart.cs` / `FreePartUnlock.cs`.
  `docs/ENTRYCOSTS.md` is **superseded/historical**. Open: mid/late funds solvency vs procedural
  big-vehicle costs (play-session question).

### D9 — 2026-06-26 — M5/M6: future-part placement, science economy, flyable start

- **Science pace = RP-1 original ×1.0.** Trialled a ×0.8 trim then **reverted**: the solvency audit
  (`docs/SCIENCE_AUDIT.md`, `tools/science_audit.py`) showed the system holds **~57× the tree's
  science** — science is *not* a binding gate, so easing it was pointless. **Earth sub-40 km science
  removed** (`design/Science/EarthScienceRemoval.cfg`) so the home planet isn't a science farm.
- **M5 Pass F:** orphan browser (`design/Tree/OrphanBrowser.cfg`, 12 visible category nodes) + **828
  Tantares/NearFuture/Cryo/Atomics parts placed** (`design/Tree/AxePlace_*.cfg`, ported from LRTR via
  an awk node-remap, `:LAST[RP-AXE]` to override `OrphanNode`). Every RP-AXE-touched part is marked
  (`ModuleAxeMarker` + `rp-axe` tag + `[RP-AXE]` note).
- **M6 start-of-career:** RP-1's 506-part "Starting Parts" node (`unlockParts`, cost 999) was
  auto-unlocked by the axed plugin → stranded at turn 1. `design/Tree/StartParts.cfg` repoints it onto
  `start`. **Avionics:** stock `ModuleCommand` control works without RP-1's mass-based system; the
  inert `ModuleProceduralAvionics` parts are **kept** (still function as probe cores), not removed.

---

## Open decisions (resolve as MVP progresses)

- **OD1 — RESOLVED (D4, then reframed by D8):** funds ON; parts free, launch cost is the sink.
- **OD2 — RESOLVED (D9/M6):** accept stock-like probe control (RP-1 avionics axed; `ModuleCommand`
  works). No config gating added — science + RF-config charging are the gates.
- **OD3 — TestFlight (part failures):** **dropped from the MVP** — `suggests`-only in `RP-AXE.netkan`,
  not a dependency (lightweight default; revisit if realism is wanted).
- **OD4 — Program starter UX:** plugin ScenarioModule + small UI (preferred) vs. pure-CC "charter
  contract" chains (zero-code fallback).
- **OD5 — Far-future part pack selection** (post-MVP research).
