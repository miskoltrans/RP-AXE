# Editor Simulation — Implementation Plan

> Status: **built (v1), untested in-game.** Decision record + build plan for the VAB/SPH "Simulate"
> feature. Code lives in `Source/AXE/Simulation/` + the shared `Source/AXE/AxeVesselTeleport.cs`.
> Compiles clean; needs an in-game pass (see §8). Feature flag: `AXE_SIMULATION { enabled = true }`
> (defaults on).

## 1. Purpose & scope

A **Simulate** button in the editor spawns the *current* craft into orbit around a chosen
body, lets the player fly a throwaway test, and reverts for free with **nothing persisted**.

The purpose is narrow and deliberate: **validate a craft in an environment you have not
reached yet** — "does my lunar ascent stage actually have the dV to make orbit from the
surface" — *before* committing a real multi-day mission to find out the hard way.

What it is **not**:
- Not a reliability / data-gathering tool. VISION explicitly sacks RP-1's reliability sim.
- Not a build-time / tooling system. AXE has no KCT; a real launch already has no build cost,
  so "free testing" is not the selling point — **testing the unreachable** is.
- Not free-revert-as-a-feature. Stock revert-to-editor already does that when reverts are on.

### Locked design decisions

| Decision | Choice | Why |
|---|---|---|
| Core value | Test scenarios you can't yet reach | Stock revert already covers "free test at the pad"; the teleport-to-unreached-orbit is the only thing that adds value |
| Cost | **Free**, no fee, no funds | It's an engineering-validation / anti-frustration tool, not a power to be paid for |
| Persistence | **Nothing persists** — backup save on entry, restore on exit | Same guarantee as RP-1/LRTR |
| Placement | **Orbit-only** (+ inherited Earth launch-site "landed") | Matches RP-1/LRTR. Surface-spawn on other bodies dropped — you land yourself in-sim (tests descent *and* ascent in one run) |
| Gating | **2 rungs** by target body | Progression that expresses "computers let you simulate many scenarios" without punishing early-game learning |
| Rung A | **Earth** — launch site + any Earth orbit, current time. *Always available.* | Near-home testing is what you could physically do anyway |
| Rung B | **All other bodies + arbitrary time.** Unlocks at `comp_digitalGuidanceComputer` | The digital-computer era *is* the lunar era; the tech that lets you *simulate* the Moon is the tech that historically let you *go* |
| Failures | None | Reliability is sacked per VISION |

## 2. Reference lineage (read as spec, do **not** copy)

This is the same HyperEdit → KCT teleport lineage AXE's airlaunch already descends from
(`AxeAirlaunchTeleport` header). **Two local clones are the same code** — LRTR's sim is a fork of
RP-1's KCT sim. Verified line-for-line: identical function names (`MakeSimulationSave`,
`LoadSimulationSave`), the same backup filename (`KCT_simulation_backup.sfs`), the same
scene-change restore trigger, the same `if (!SimulateInOrbit || !CanRevertToPrelaunch)` move gate,
and the same **orbit-only** placement (no land-on-body path in *either*). So this is **not** an
old-vs-new choice — the mechanism is identical in both.

- **Primary reading copy: LRTR** (`C:/git/ksp/LRTR`) — the deliberately slimmer "RP-1 without RO"
  fork. Its sim reads as a near-isolated feature (fewer dependencies), which is what we want when
  *extracting* a standalone sim. It's also the exact file AXE's airlaunch already descends from.
- **Cross-check copy: RP-1** (`C:/git/ksp/RP-1`, v4.4.0.0, newer) — same architecture, but
  entangled with the modern ROUtils/RP0 career engine (`ROUtils.DataTypes.ConfigNodePersistenceBase`,
  `SpaceCenterManagement`, `VesselProject`). Not the cleaner read, **but its newer version has two
  improvements worth taking** (see below), since we reimplement anyway.

**LRTR & RP-1 are CC-BY-NC-SA / GPL — reimplement from the stock API**, the way the airlaunch
teleport already was. Key files:

| Concern | LRTR (read) | RP-1 (cross-check) |
|---|---|---|
| Config window / `StartSim` | `GUI/GUI_Simulation.cs` | `UI/KCT/GUI_Simulation.cs` |
| Param bag | `SimulationParams.cs` | `SpaceCenter/SimulationParams.cs` |
| Teleport | `Utilities/HyperEdit_Utilities.cs` | (same lineage) |
| Save backup/restore + locks | `Utilities/Utilities.cs:1898-1981` | `Utilities/KCTUtilities.cs:1049+` |
| Deferred move | `KerbalConstructionTime.cs:673-717` | `SpaceCenter/SpaceCenterManagement.cs:1258` |
| Scene-change restore | `KCTEvents.cs:377-382` | `SpaceCenter/SCMEvents.cs:278` |
| Recovery-button intercept | `SceneAddons/FlightAddon.cs` | (equivalent flight addon) |

**Two things to steal from the newer RP-1** (LRTR lacks them):
1. **Full orbital elements** — RP-1's `SimulationParams` carries `SimOrbitPe/Ap/Inclination/LAN/MNA/ArgPe`
   (elliptical orbits), where LRTR only does circular `altitude + inclination`. Cheap to add and
   more useful (test a Molniya, a transfer orbit, a specific Pe for aerobraking). See §3.1.
2. **Pre-sim-save-not-found safety** — RP-1 posts a "load the backup manually from
   `\saves\<save>\Backup\KCT_simulation_backup.sfs`" message if restore can't find the pre-sim
   state (`SpaceCenterManagement.cs:443`). Adopt this guard.

## 3. Architecture & files

New namespace `RPAxe.Simulation` under `Source/AXE/Simulation/`. All stock API + Harmony —
no new assembly references, no KCT, no MagiCore.

### 3.1 Prerequisite refactor — extract the shared teleport primitive

Airlaunch and Simulation are **different features that share one primitive.** Pull the
body-agnostic teleport out of `AxeAirlaunchTeleport` into a neutral helper so neither feature
owns it:

- **New `Source/AXE/AxeVesselTeleport.cs`** — move `SetOrbit`, `HardsetOrbit`,
  `PrepVesselTeleport`, `ResetGroundContact`, `Clone` here verbatim (they're already stock-API).
- `AxeAirlaunchTeleport.DoAirlaunch` keeps its drop-point/great-circle math, now calling
  `AxeVesselTeleport.SetOrbit`. **Airlaunch behaviour must be unchanged** — regression-check it.
- **Add `AxeVesselTeleport.PutInCircularOrbit(Vessel v, CelestialBody body, double altitude,
  double inclination)`:**
  ```
  double sma = body.Radius + altitude;
  var orbit = new Orbit(inclination, 0.0, sma, 0.0, 0.0, 0.0, Planetarium.GetUniversalTime(), body);
  SetOrbit(v, orbit);
  ```
  (`new Orbit(inc, e, sma, LAN, argPe, mEp, epoch, body)` is the exact ctor `Clone` already uses.)
  Clamp `altitude` to `[max(body.atmosphereDepth, 0), body.sphereOfInfluence)` before building.
- **Optional (from RP-1): elliptical variant** `PutInOrbit(v, body, pe, ap, inc, lan, argPe, mna)` —
  same ctor, `sma = body.Radius + (pe+ap)/2`, `e = (ap-pe)/(ap+pe+2·body.Radius)`. Circular is the
  minimum for the dV use case; add elliptical if testing Molniya / transfer / aerobraking orbits.

### 3.2 New simulation files

| File | Role | LRTR analog |
|---|---|---|
| `Simulation/AxeSimulationParams.cs` | `{ CelestialBody Body; bool InOrbit; double Altitude, Inclination; int DelaySeconds; double TargetUT; bool Moved; }` | `SimulationParams.cs` |
| `Simulation/AxeSimulation.cs` | Static session state: `Params`, `bool IsSimulatedFlight`. `StartSim(params)` (entry). | `KCTGameStates` + `StartSim` |
| `Simulation/AxeSimulationSave.cs` | `MakeBackup` / `Restore` / `DeleteBackup` / `BackupExists` + `Enable/DisableSimLocks` | `Utilities.cs:1898-1981` |
| `Simulation/AxeSimulationEditor.cs` | `[KSPAddon(EditorAny)]` — app-launcher button + config window + gated body chooser | `GUI_Simulation` config windows |
| `Simulation/AxeSimulationFlight.cs` | `[KSPAddon(Flight)]` — recovery intercept, sim window, `ProcessSimulation` move, autosave-off | `FlightAddon` + `ProcessSimulation` + `DrawSimulationWindow` |
| `Simulation/AxeSimulationRestore.cs` | `GameEvents.onLevelWasLoaded` hook: restore backup on entering EDITOR/SPACECENTER/TRACKSTATION | `KCTEvents.cs:377-382` |
| `Simulation/AxeSimulationGate.cs` | 2-rung body gate + node-title lookup for tooltips | (new — see §5) |

**Session state, not save state.** `IsSimulatedFlight` and `Params` are static fields (survive the
editor→flight scene load). The **source of truth for "a sim is in progress" is the backup file's
existence**, so a crash/alt-F4 mid-sim still self-heals on next load (§4, exit). No new
ScenarioModule needed. Quicksave/quickload are locked during a sim so the player can't entangle
the real save.

## 4. Lifecycle / state machine

**Entry (editor), `AxeSimulation.StartSim`:**
1. Guard: `!IsSimulatedFlight && !BackupExists()`; `EditorLogic.fetch.ship.Count > 0`.
2. Resolve params from UI; clamp altitude; resolve `TargetUT` (see §6 time note).
3. `MakeBackup()` → `GamePersistence.SaveGame("AXE_sim_backup", HighLogic.SaveFolder, SaveMode.OVERWRITE)`.
4. Save temp craft → `saves/<save>/Ships/AXE_sim_temp.craft`.
5. `IsSimulatedFlight = true`; `EnableSimLocks()`.
6. **Force-enable reverts for the sim** (see §7 reverts-off) — snapshot & set
   `HighLogic.CurrentGame.Parameters.Flight.CanLeaveToEditor / CanRestart / CanQuickLoad`.
7. `FlightDriver.StartWithNewLaunch(tempFile, EditorLogic.FlagURL, launchSiteName, manifest)`.

**Flight, `AxeSimulationFlight`:**
8. On `Start`: if `IsSimulatedFlight`, set `Flight.CanAutoSave = false`; intercept
   `AltimeterSliderButtons.vesselRecoveryButton.onClick` → open the sim window.
9. `ProcessSimulation` (per-frame until moved): once the active vessel is `loaded && !packed &&
   !Params.Moved`:
   - if `!Params.InOrbit` (Earth launch-site mode) → `Moved = true`, done (craft stays on pad).
   - else → after `DelaySeconds` + `WaitForEndOfFrame`, call
     `AxeVesselTeleport.PutInCircularOrbit(activeVessel, Body, Altitude, Inclination)`; set `Moved`.
   - (optional) warp to `TargetUT` if set.
10. Sim window (IMGUI): header "This is a simulation — nothing is saved."; buttons:
    - **Restart** → `FlightDriver.RevertToLaunch()`; `Params.Moved = false`.
    - **Revert to Editor** → `FlightDriver.RevertToPrelaunch(vabOrSph)`.
    - **Close**.

**Exit / restore (fail-safe), `AxeSimulationRestore`:**
11. `GameEvents.onLevelWasLoaded(scene)`: if `scene ∈ {EDITOR, SPACECENTER, TRACKSTATION}` and
    `BackupExists()`:
    - swap `persistent.sfs` from `AXE_sim_backup.sfs`; clear
      `FlightGlobals.PersistentVesselIds / PersistentLoadedPartIds / PersistentUnloadedPartIds`;
      reload game state (mirror LRTR `LoadSimulationSave`, editor-cache path for EDITOR).
    - `DisableSimLocks()`; restore the reverts-param snapshot; `DeleteBackup()` (archive to
      `Backup/`); `IsSimulatedFlight = false`.

Because the **backup file's existence** is the restore trigger — not an in-memory flag — the real
save is protected even if the sim is interrupted abnormally. Nothing from the sim (UT, science,
contracts, comm net) leaks: the whole `persistent.sfs` is swapped back.

## 5. The tech gate (2 rungs)

Mirror the established AXE idiom (`AxeTrackingStationGate.cs`, `ModuleAxeAvionics.cs:306`, etc.):

```csharp
const string RUNG_B_NODE = "comp_digitalGuidanceComputer";   // confirmed id in AxeTechTree.cfg:6932

static bool CanSimulate(CelestialBody b) =>
    b == Planetarium.fetch.Home
    || ResearchAndDevelopment.GetTechnologyState(RUNG_B_NODE) == RDTech.State.Available;
```

- Sandbox / no R&D: `GetTechnologyState` returns `Available` for everything → all bodies open. Good.
- **Arbitrary time** is a rung-B capability too: the time field is enabled only when the node is
  researched; pre-computer is Earth "now" only.
- **Legible, aspirational UX** (the point of gating-as-progression): the body chooser lists every
  `FlightGlobals.Bodies`, but non-simulatable ones are drawn with `GUI.enabled = false` and a
  tooltip — reuse `AxeTrackingStationGate`'s pattern of
  `ResearchAndDevelopment.GetTechnologyTitle(RUNG_B_NODE)` →
  *"Simulating other worlds requires the Digital Guidance Computer."* The player sees the Moon and
  planets waiting behind the node.

## 6. Time-warp (built)

Rung B's "arbitrary time" ships as a dependency-free **"Warp forward (days)"** field (no
`MagiCore.Utilities.ParseTimeString`). It's gated to the rung-B node (same unlock as other worlds)
and applies via `Planetarium.SetUniversalTime` **after** the teleport — i.e. once the vessel is on
rails (`SetOrbit` did `GoOnRails`), so advancing the whole system to the target date never disturbs
physics. Relative-only for now; absolute-date entry (`"1y 2d 3h"`) stays deferred (§9). Principia's
backwards-time guard is dropped — Principia isn't installed (patched conics only).

## 7. Edge cases & guards

- **No nested sim** — `StartSim` guard on `IsSimulatedFlight || BackupExists()`.
- **Reverts-off careers** — LRTR's buttons rely on `FlightDriver.CanRevertTo*`, which respect the
  difficulty setting; in a reverts-off career the player would be **stuck in the sim**. We diverge:
  force-enable the revert params at sim entry (§4 step 6) and restore them on exit. This is
  deliberate — it lets the sim work as a sanctioned test channel even for immersion players who run
  reverts off.
- **Empty ship** — guard.
- **Launch clamps** — killed by `PrepVesselTeleport` (already in the shared primitive).
- **Kerbalism** — sim flight may tick life-support/science; irrelevant, the save swap discards it.
- **AXE avionics control-lock** — behaves normally in-sim (you may be testing a craft whose flight
  computer isn't unlocked yet — that's legitimate feedback, leave it).
- **UT drift** — a sim advances UT; the backup restore resets it. Verify UT == pre-sim after exit.

## 8. Testing / verification

Use the existing AutoTest harness (`AxeAutoTest.cs`, `AutoTest.cfg`):
- **Round-trip (Earth):** build a known craft → `StartSim` to 200 km Earth orbit → assert active
  vessel is orbiting Earth at ~200 km → Revert to Editor → assert back in editor, `IsSimulatedFlight
  == false`, no `AXE_sim_backup.sfs`, **funds/science/UT unchanged**.
- **Gate:** with `comp_digitalGuidanceComputer` locked → Moon greyed & not startable; unlock →
  Moon selectable → sim to low lunar orbit succeeds.
- **Use-case smoke (manual):** lunar lander → sim to low lunar orbit → land → fire ascent stage →
  read dV margin → revert.
- **Reverts-off (manual):** career with reverts disabled → confirm "Revert to Editor" still returns.

## 9. Deferred / explicitly not in v1

Surface-spawn on other bodies · cost/fee · failures/TestFlight · **absolute-date** time entry
(`"1y 2d 3h"`; relative warp-forward is built, §6) · "build the simulated vessel" · 3rd rung
(Moon-then-planets split) · sim watermark (nice-to-have) · real icon asset (procedural placeholder).

**Built beyond the original v1 skeleton:** elliptical orbits (Pe/Ap/inc/LAN/argPe, §3.1) and
relative warp-forward-days (§6).

## 10. Build sequence & rough effort

The feature is **small in code (~400 lines) and conceptually simple** — the hard algorithm
(teleport) already exists in the repo. The effort is *not* in the algorithm; it's in (a) the
**save-swap safety** (steps 2 — we overwrite the player's real save file, the one genuinely
dangerous part, which must be tested hard) and (b) **KSP's slow test loop** (scene-transition and
save-restore bugs only surface at runtime, one game-restart per change). Estimates below are soft.

| # | Step | Effort |
|---|---|---|
| 1 | Extract `AxeVesselTeleport` + `PutInCircularOrbit` (refactor; airlaunch must still work) | ~0.5d |
| 2 | Save layer + `onLevelWasLoaded` restore — the fail-safe backbone; testable standalone | ~0.5d |
| 3 | `StartSim` + editor button + minimal config (Earth LEO, now), **ungated** — first round-trip | ~1d |
| 4 | Flight addon — recovery intercept, sim window, `ProcessSimulation`, reverts-off toggle | ~1d |
| 5 | Gate + body chooser (greying, tooltips) + other bodies | ~0.5d |
| 6 | AutoTest self-test + manual passes | ~0.5d |

- **Steps 1–3 (~2d) → a first playable** Earth-only, ungated round-trip you can *feel*.
- **Steps 4–6 (~2d) → hardening** (flight polish, the gate, tests). Total ≈ **4 days done properly**.
- A throwaway proof-of-life (Earth-only, ungated, no refactor, manual test) is genuinely ~1 day —
  but it skips the save-swap safety and the airlaunch-shared refactor, so it's not shippable.

Feature-flag it dark (mirror the existing bootstrap flag pattern) until step 6 passes.

## 11. Open questions to resolve at build time

- **Entry-point form** — app-launcher button (recommended, simplest) vs. patching the launch button.
- **Time in v1** — defer entirely (recommended) vs. simple "warp N days."
- **Reverts-off** — confirm we want to force-enable reverts during a sim (recommended: yes).
