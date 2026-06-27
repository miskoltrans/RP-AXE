# RP-AXE Workflow

How to build the plugin, deploy the mod into the test instance, test, and keep yoinked configs
fresh. Read [`ARCHITECTURE.md`](ARCHITECTURE.md) first.

## Machine layout

```
C:\git\ksp\
  RP-AXE\     <- this repo (edit here)
  RP-1\       <- RP-1 SOURCE repo (yoink/reference; do not edit)
  LRTR\       <- LRTR (reference only)
  Instance\   <- KSP 1.12 test install (CKAN-managed)
```

## The deploy model

The `Instance/` already has the full RP-1 dependency stack installed via CKAN (RO, RSS, RealFuels,
ContractConfigurator, ROEngines/Tanks/Solar/Capsules/Heatshields, ReStock, Kerbalism, …). Those
shared deps are exactly what RP-AXE needs — **we reuse them**.

To test RP-AXE we must (a) make our `GameData/RP-AXE/` live in the instance, and (b) disable
RP-1's *career layer* so it doesn't collide (duplicate trees/contracts) — while leaving the shared
deps in place.

`tools/deploy.ps1` does this:

1. Creates a **directory junction** `Instance/GameData/RP-AXE` → `RP-AXE/GameData/RP-AXE`, so edits
   in the repo are instantly live in the instance (no copy step).
2. Toggles RP-1's own folder: renames `Instance/GameData/RP-1` ⇄ `Instance/GameData/RP-1.disabled`.
   This removes `RP0.dll`, `CC_RP0.dll`, and RP-1's configs from the load — but keeps RP-1 around
   for A/B comparison and re-enabling.
3. Leaves every shared dependency untouched.

```powershell
# from repo root
pwsh tools/deploy.ps1          # link AXE in, disable RP-1 career layer
pwsh tools/deploy.ps1 -Revert  # unlink AXE, re-enable RP-1
```

> ⚠️ Do **not** install RP-AXE *and* RP-1's career layer at the same time. They both define a
> `@TechTree` and the same contract groups — KSP will load a broken merge.

> ⚠️ CKAN: removing the `RP-1` module via CKAN would also remove its dependencies. We do **not**
> do that. We only rename the `GameData/RP-1` folder. Dependency set of record is in
> [`DEPENDENCIES.md`](DEPENDENCIES.md) so the instance can be rebuilt if needed.

## Rebuilding a clean instance (nuke & restore)

> **Fast path — `tools/rebuild-instance.ps1`** automates the whole nuke→restore→deps→deploy below:
> ```powershell
> pwsh tools/rebuild-instance.ps1          # prompts before the destructive nuke
> pwsh tools/rebuild-instance.ps1 -Force   # skip the prompt
> ```
> It (1) unlinks the `GameData\RP-AXE` junction then deletes `Instance\`, (2) robocopies the pristine
> snapshot `C:\git\ksp_instance_clean` (a clean KSP 1.12.5 **with both DLCs**, kept outside the working
> tree) into a fresh `Instance\`, (3) `ckan install -c RP-AXE-deps.ckan --gamedir Instance --no-recommends
> --headless` (targets the folder directly — no Manage-instances registration needed), and (4) runs
> `deploy.ps1`. **No RP-1** is ever installed, so nothing has to be disabled. `AXE.dll` ships in the repo
> (junctioned in), so no build step is required. Paths override via `-InstancePath`/`-CleanSnapshot`/
> `-CkanExe`/`-DepsCkan`. The manual steps below are the same flow, by hand.

When the instance's mod set drifts/breaks (e.g. a partial CKAN update leaves DLL versions
inconsistent — see the cold-load assembly gotcha), the fastest fix is a clean rebuild. The whole
dependency set installs in one shot from **`../RP-AXE-deps.ckan`** — a CKAN *metapackage* whose
`depends` is the **exact installed mod set of the curated test instance** (the "perfect environment").
It is generated straight from the live CKAN registry (snippet at the bottom of this section; re-run
whenever the instance's mod set changes). It has no version pins, so CKAN resolves a latest
mutually-compatible set.

> **Dependency model (2026-06-27):** `depends` = **all 81 installed modules** (57 user-requested +
> 24 CKAN-resolved transitive, incl. MakingHistory-DLC + BreakingGround-DLC), derived from
> `Instance/CKAN/registry.json` rather than hand-curated. `RP-AXE.netkan` and `RP-AXE-deps.ckan`
> carry the identical list; there are no `recommends`/`suggests` (anything not installed isn't part
> of the perfect environment). Listing the full set — not just the roots — makes the rebuild
> reproduce the stack verbatim without depending on CKAN's recommend-resolution behaviour.

1. **Nuke:** in CKAN, *Manage instances* → remove the `Instance` entry (this only de-registers it),
   then delete `C:\git\ksp\Instance\`. (Or keep the folder and just `git`-style wipe `GameData/`
   back to stock — but a fresh copy is cleaner.)
2. **Fresh KSP:** copy a pristine **KSP 1.12.5** (Steam → *Verify integrity*, or copy
   `steamapps/common/Kerbal Space Program`) to `C:\git\ksp\Instance\`. Keep a vanilla copy so Steam
   updates can't touch the modded one. Make sure **Making History** (and Breaking Ground if owned)
   are present — RO/RP-1 require MH; CKAN can't install DLCs, only detect them.
3. **Register:** CKAN → *Manage instances* → *Add instance* → point at `C:\git\ksp\Instance`. CKAN
   creates a fresh empty registry.
4. **Install deps:** CKAN → *File* → *Install from .ckan file* → pick `RP-AXE\RP-AXE-deps.ckan`
   (CLI: `ckan install -c RP-AXE-deps.ckan`). Apply — CKAN pulls all 81 modules (the full installed
   set is listed explicitly, so transitive deps like Kopernicus, FAR, AJE, B9PartSwitch, CRP,
   KSPBurst are named directly rather than left to resolution).
5. **Deploy RP-AXE:** `pwsh tools/deploy.ps1` (defaults to `C:\git\ksp\Instance`). Rebuild `AXE.dll`
   if needed, then launch.

> The instance path stays `C:\git\ksp\Instance`, so `deploy.ps1` and the `KSPRoot` build property
> need no changes. For an *exact* reproduction (version-pinned lockfile) instead of latest, export a
> modpack from a known-good instance: CKAN → *File* → *Export installed mods*.

```powershell
# regenerate depends from the LIVE instance registry = the perfect environment (run from repo root).
# Source of truth is what CKAN actually has installed, not a hand-curated list.
$reg = Get-Content ..\Instance\CKAN\registry.json -Raw | ConvertFrom-Json
$ids = $reg.installed_modules.PSObject.Properties.Name | Sort-Object
$depends = @($ids | ForEach-Object { [ordered]@{ name = $_ } })

# 1) RP-AXE.netkan — replace its depends with the full installed set
$nk = Get-Content RP-AXE.netkan -Raw | ConvertFrom-Json
$nk.depends = $depends
$nk | ConvertTo-Json -Depth 6 | Set-Content RP-AXE.netkan -Encoding utf8

# 2) RP-AXE-deps.ckan — metapackage mirroring the same list
$meta = [ordered]@{ spec_version='v1.18'; identifier='RP-AXE-deps'
  name='RP-AXE: all dependencies (metapackage)'
  abstract='Installs the complete RP-AXE perfect-environment mod set. Derived from the live registry.'
  author=@('miskoltrans'); version='0.2.0'; kind='metapackage'; license='CC-BY-NC-SA-4.0'
  ksp_version_min=$nk.ksp_version_min; ksp_version_max=$nk.ksp_version_max
  depends=$depends; conflicts=@([ordered]@{ name='RP-1' }) }
$meta | ConvertTo-Json -Depth 6 | Set-Content RP-AXE-deps.ckan -Encoding utf8
```

## Building the plugin (`AXE.dll`)

> `AXE.dll` is **load-bearing** (it started as a researched fallback — D2 — but D5/D6/D8 made it
> required). It implements: the 14 ContractConfigurator types (`Contracts/`, every ported contract
> needs them), Career-enable (`EnableCareer.cs`, reflects RO's `_overrideCareer`), the program
> switcher (`AxeProgramHandler`), the free-parts economy (`FreePartUnlock.cs`), and the 100 k
> generous start (`GenerousStart.cs`). **If it fails to build/load, no career loads** — keep it green.
> (The AutoTest harness also lives here but ships disabled; the `-axe-autotest` flag force-enables it.)

`Source/AXE/` is a .NET Framework 4.8 class library. It references KSP's managed assemblies and
`ContractConfigurator.dll` **from the instance**, via the `KSPRoot` MSBuild property.

```powershell
# point the build at the test instance, then build into GameData/RP-AXE/Plugins/
$env:KSPRoot = "C:\git\ksp\Instance"
dotnet build Source/AXE/AXE.csproj -c Release
```

The build's post-step copies `AXE.dll` to `GameData/RP-AXE/Plugins/`. Because `GameData/RP-AXE` is
junctioned into the instance, the new DLL is live on next KSP launch. (KSP loads plugins only at
startup — restart KSP after a rebuild.)

If `dotnet` resolves the wrong toolchain, mirror RP-1's approach: it pins Roslyn via
`Source/Directory.Build.props`. Our `Directory.Build.props` does the same.

## The test loop

1. Edit configs in `GameData/RP-AXE/` and/or code in `Source/AXE/`.
2. If code changed: rebuild (`dotnet build …`).
3. Launch KSP (`Instance/KSP_x64.exe`) — or ask the user to, since it's a GUI app:
   suggest they type `! Instance/KSP_x64.exe` in the prompt.
4. **Read `Instance/KSP.log`** — this is the primary feedback channel for an agent. Grep it for:
   - `[ModuleManager]` patch counts / exceptions
   - `ContractConfigurator` parse errors (these tell you which custom `type =` failed to resolve)
   - `[AXE]` — our plugin should log under this prefix
   - `NullReferenceException` / `[ERR]`
5. For gameplay verification (does the contract offer? does the node unlock?) prefer a quick
   in-game check; capture findings in the relevant task.

> Tip: a load-to-main-menu + new-science-game smoke test surfaces ~90% of config/plugin breakage
> via `KSP.log` without flying anything.

## Vendoring & keeping it fresh

- `tools/sync-seed.ps1` vendors RP-1's `Tree/`, `Contracts/`, `Science/` into
  `GameData/RP-AXE/seed/` and stamps the RP-1 version into `seed/_README.md`. Run it when RP-1
  updates. `seed/` is committed (the mod ships self-contained).
- **Never edit `seed/`.** All RP-AXE changes are ModuleManager patches in `GameData/RP-AXE/design/`,
  applied `:AFTER[...]`/`:FINAL` and tagged `:FOR[RP-AXE]`. This keeps re-vendoring a clean diff.

## Config iteration (no rebuild needed)

After editing config (anything under `GameData/RP-AXE/`), force a full re-patch and inspect:

- Delete `Instance/GameData/ModuleManager.ConfigCache` so ModuleManager re-applies all patches on
  next launch.
- In-game, the **Contract Configurator debug menu (Alt+F10)** reloads contracts live and prints
  parse errors — the fastest way to see which `type =` failed to resolve after a Pass-A patch.

## Conventions for agents picking up work

- One task from [`TASKS.md`](TASKS.md) at a time; keep its checkbox + notes updated as you go.
- **Never edit `seed/`** — all changes are `design/` patches (see ARCHITECTURE §8). Default to
  config; reach for `AXE.dll` only when the M2 CC-type triage says stock config can't do it.
- All plugin log lines start with `[AXE]`. All MM patches use `:FOR[RP-AXE]` /
  `:AFTER[...]` / `:NEEDS[...]` / `:FINAL` so ordering and conditionality are explicit.
- After any change that touches load, re-run the smoke test and paste the relevant `KSP.log`
  excerpt into the task notes.
