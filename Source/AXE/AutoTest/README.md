# AXE AutoTest — launch-time smoke test

A hands-free smoke test baked into `AXE.dll`, driven by a config file. On launch (if enabled) it:

1. starts a fresh game — **CAREER** by default (save folder `AXE_AutoTest`, overwritten each run),
2. once the Space Center is up, walks the **configured facility screens** in order, doing
   **enter → dwell → exit** on each (default: **R&D → Mission Control**),
3. then **quits KSP automatically** (on success *or* failure) so the run is fully hands-free.

This exercises — without clicking — the paths that have historically thrown in RP-AXE: new-game
scenario setup and ContractConfigurator's R&D / Mission Control UI. It's the "load-to-main-menu +
new-game smoke test" from [`docs/WORKFLOW.md`](../../docs/WORKFLOW.md), automated.

## Configuration

Everything is in **`GameData/RP-AXE/Plugins/PluginData/AutoTest.cfg`** — edit and relaunch KSP, no
rebuild needed. (If the file is missing, the plugin writes a default copy on first launch.)

```cfg
AXE_AUTOTEST
{
    enabled  = true              // run on launch? (also force-on via -axe-autotest / AXE_AUTOTEST=1)
    gameMode = CAREER            // CAREER | SCIENCE_SANDBOX | SANDBOX
    saveName = AXE_AutoTest

    screens  = RND, MISSIONCONTROL   // ordered; tokens below

    dwellSeconds       = 5       // how long to linger in each screen
    settleSeconds      = 2
    stepTimeoutSeconds = 60      // give up on a step after this long (logs a FAILED)

    quitWhenDone     = true      // close KSP when finished?
    quitDelaySeconds = 3

    kscSwitchTest    = false     // opt-in: also verify free KSCSwitcher switching (see below)
}
```

**Free-KSC-switch check (`kscSwitchTest = true`).** After the screen walk, the harness loads the
**Tracking Station** (the only scene where KSCSwitcher's UI and its `LastKSC` persistence module
live) and drives a real site switch — default **Cape Canaveral → Kourou**. It logs, under the
`[AXE][AutoTest][KSC]` prefix, three downstream checks: the live site changed
(`regexKSP.KSCSiteManager.lastSite`), a CommNet ground station is co-located at the new site (RA's
~56-station real-world network is fixed and needs no "home follow"), and `LastKSC.OnSave` serializes
`LastLaunchSite` — then a real `SaveGame`, so `saves/AXE_AutoTest/persistent.sfs` should contain
`LastLaunchSite = fr_kourou`. A clean run ends `RESULT … => PASS`. Switching from any *other* scene
sets the live site but does **not** persist (OnSave only fires where `LastKSC` is active), which is
why the check runs in the Tracking Station — the same place the player switches.

**Screen tokens** (for `screens`, comma-separated, any order, repeats allowed):
`RND`, `MISSIONCONTROL`, `ADMINISTRATION`, `ASTRONAUTCOMPLEX`. Unknown tokens are skipped with a
warning. Examples: `screens = MISSIONCONTROL` (just contracts), `screens = RND, ASTRONAUTCOMPLEX, ADMINISTRATION`.

To turn it **off**, set `enabled = false` (the instance is then usable for normal play). `-axe-autotest`
on the command line, or `AXE_AUTOTEST=1` in the environment, force-enables regardless of the file.

## How to run

Deploy + build so the DLL is fresh, then launch KSP — it runs by itself:

```powershell
pwsh C:\git\ksp\RP-AXE\tools\deploy.ps1
$env:KSPRoot = "C:\git\ksp\Instance"; dotnet build C:\git\ksp\RP-AXE\Source\AXE\AXE.csproj -c Release
C:\git\ksp\Instance\KSP_x64.exe
```

## Reading the result

Everything logs to `Instance/KSP.log` under the `[AXE][AutoTest]` prefix. A clean run ends with:

```
[AXE][AutoTest] SUCCESS: visited N screen(s) [...]. Test sequence complete.
```

Any failure logs `[AXE][AutoTest] FAILED: <why>` and aborts (then still quits if `quitWhenDone`);
NREs / ContractConfigurator parse errors surface inline in the log right where they happen.

```powershell
Select-String -Path C:\git\ksp\Instance\KSP.log -Pattern '\[AXE\]\[AutoTest\]'
```

## How it works (KSP internals it relies on)

- New game: `MainMenu.CreateAndStartGame(saveName, gameMode)` — the same call the new-game dialog
  makes — after seeding the static `MainMenu.newGameParameters`. Bypasses the dialog (and thus
  Realism Overhaul's career gate), but flips RO's `_overrideCareer` too, defensively.
- Enter a facility: the **public** `SpaceCenterBuilding.EnterBuilding()` on the found building
  (`RnDBuilding` / `MissionControlBuilding` / `AdministrationFacility` / `AstronautComplexFacility`),
  with the building's private `OnClicked()` as a fallback.
- Open/closed detection + exit: each facility complex is an additive scene with a `*SceneDespawner`
  (`RDSceneDespawner`, `MCDespawner`, `ACSceneDespawner`, `AdministrationSceneDespawner`). Its
  presence means the screen is open; its `BtnExit()` leaves (same as the on-screen Exit button).
- Dwells use **unscaled** time, because facility screens / modal popups pause the game (timeScale 0)
  and `WaitForSeconds` would never advance. New-game popups are dismissed before each entry.
