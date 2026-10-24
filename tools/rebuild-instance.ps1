<#
.SYNOPSIS
    Rebuild the KSP test Instance from a pristine snapshot: nuke -> copy clean -> install
    RP-AXE CKAN deps -> install local non-CKAN mods -> deploy
    RP-AXE. No RP-1 anywhere.

.DESCRIPTION
    Six steps:
      1. NUKE     - delete C:\git\ksp\Instance (after first unlinking the RP-AXE junction so the
                    recursive delete can't follow it into the repo and wipe GameData\RP-AXE).
      2. COPY     - mirror the pristine snapshot (..\ksp_instance_clean) into a fresh Instance.
                    The snapshot is a clean KSP 1.12.5 with the DLCs present. It sits BESIDE
                    Instance (both under C:\git\ksp), never inside it -- the nuke targets only
                    $InstancePath, and preflight refuses to run if the snapshot is under it.
      3. DEPS     - ckan install the RP-AXE perfect-environment mod set from RP-AXE-deps.ckan,
                    targeting the instance directly via --gamedir (no CKAN registration needed).
      4. LOCAL    - copy the non-CKAN mods we develop or vendor locally (see -LocalModGameData)
                    into GameData. These live in sibling repos, not on CKAN, so step 3 cannot
                    bring them back and a rebuild silently DELETES them -- which is exactly what
                    happened on 2026-08-17: FuelTankOptimizer and KSPTOTConnect vanished in a
                    rebuild and nothing noticed, because a missing mod looks identical to a mod
                    that was never installed. Anything not in RP-AXE-deps.ckan belongs here.
      5. DEPLOY   - junction GameData\RP-AXE in via deploy.ps1 (AXE.dll ships in the repo, so no
                    build step is required).
      6. VERIFY   - boot the instance once with -axe-autotest (hands-free: new career, walk R&D +
                    Mission Control, quit), then run tools\check_liveness.py and
                    tools\check_settings_parity.py against the cache that boot produced.
                    Skip with -NoVerify.

    The pristine snapshot does NOT contain RP-1, so nothing has to be disabled.

    WHY STEP 6 IS PART OF THE REBUILD. Every liveness question -- does this node grant a part, does
    this MODULE exist, does this tech gate resolve -- can only be answered from the MERGED cache,
    which does not exist until KSP has booted. A rebuild that stops at step 5 leaves an instance
    nobody has checked, and the checks then run when someone remembers, which is how 702 RCS engine
    configs stayed locked (docs\BUG-CLASSES.md). Booting here is the cheapest moment: the cache has
    to be built on first launch anyway.

.PARAMETER CleanSnapshot
    Pristine KSP install to copy from. Default C:\git\ksp\ksp_instance_clean (sibling of Instance,
    so a nuke of Instance never reaches it). Create it once by copying a verified stock KSP 1.12.5
    (with Making History / Breaking Ground) here.

    NOTE: this carries settings.cfg too, so a rebuild resets per-instance graphics/UI tweaks
    (AERO_FX_QUALITY, UI_SCALE, LOG_*_TO_SCREEN, ...) to whatever the snapshot has.

.PARAMETER LocalModGameData
    GameData roots of mods that are NOT on CKAN, so nothing else in this script would reinstall
    them. Each entry is a directory that CONTAINS mod folders (i.e. a "GameData"), and every child
    of it is copied into the instance's GameData.

    Defaults:
      C:\git\ksp\FuelTankOptimizer\GameData                          -> FuelTankOptimizer
      C:\git\ksp\KSP_Trajectory_Optimization_Tool-1.6.10.1\GameData  -> KSPTOTConnect

    NB the FuelTankOptimizer DLL under its GameData is gitignored build output. This step copies
    whatever is there; it does NOT build. If you changed FTO source, build it first or you will
    ship a stale DLL that looks perfectly installed.

.PARAMETER Force
    Skip the "are you sure" confirmation before the destructive nuke.

.PARAMETER NoVerify
    Skip step 6 (boot + liveness gate). The instance is then unverified -- run
    `python tools\check_liveness.py` yourself after the first launch.

.PARAMETER VerifyTimeoutMinutes
    Give up on the -axe-autotest boot after this long and kill it (default 15). A cold first launch
    compiles every part, so it is slow; the harness itself quits when done.

.EXAMPLE
    pwsh tools/rebuild-instance.ps1
    pwsh tools/rebuild-instance.ps1 -Force
    pwsh tools/rebuild-instance.ps1 -Force -NoVerify
    pwsh tools/rebuild-instance.ps1 -CleanSnapshot D:\ksp_clean -Force
#>
[CmdletBinding()]
param(
    # Everything below hangs off these two roots. Derive, never re-count Split-Paths by hand:
    # getting the nesting wrong silently produced defaults one directory too high (e.g.
    # C:\git\ksp_instance_clean), which nothing on disk matched, so preflight threw on every bare run.
    #   $PSScriptRoot = C:\git\ksp\RP-AXE\tools
    #   $AxeRepo      = C:\git\ksp\RP-AXE
    #   $KspRoot      = C:\git\ksp
    [string]$AxeRepo         = (Split-Path -Parent $PSScriptRoot),
    [string]$KspRoot         = (Split-Path -Parent $AxeRepo),
    [string]$InstancePath    = (Join-Path $KspRoot 'Instance'),
    [string]$CleanSnapshot   = (Join-Path $KspRoot 'ksp_instance_clean'),
    [string]$CkanExe         = (Join-Path $KspRoot 'ckan.exe'),
    [string]$DepsCkan        = (Join-Path $AxeRepo 'RP-AXE-deps.ckan'),
    [string[]]$LocalModGameData = @(
        (Join-Path $KspRoot 'FuelTankOptimizer\GameData')
        (Join-Path $KspRoot 'KSP_Trajectory_Optimization_Tool-1.6.10.1\GameData')
    ),
    [switch]$Force,
    [switch]$NoVerify,
    [int]$VerifyTimeoutMinutes = 15
)

$ErrorActionPreference = 'Stop'
$deployScript = Join-Path $PSScriptRoot 'deploy.ps1'

function Step($n, $msg) { Write-Host "`n[$n/6] $msg" -ForegroundColor Cyan }

# Unlink a directory junction / reparse point WITHOUT deleting its target contents.
function Remove-JunctionLink([string]$path) {
    if (Test-Path $path) {
        $item = Get-Item $path -Force
        if ($item.LinkType -eq 'Junction' -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            (Get-Item $path -Force).Delete()
            Write-Host "  unlinked junction: $path"
        }
    }
}

# --- preflight: fail loud BEFORE we delete anything -------------------------------------------
if (-not (Test-Path $CleanSnapshot)) { throw "Clean snapshot not found: $CleanSnapshot  (create it first - see -CleanSnapshot help)" }
if (-not (Test-Path (Join-Path $CleanSnapshot 'KSP_x64.exe'))) { throw "Clean snapshot has no KSP_x64.exe: $CleanSnapshot  (not a KSP install?)" }
if (-not (Test-Path $CkanExe))   { throw "ckan.exe not found: $CkanExe" }
if (-not (Test-Path $DepsCkan))  { throw "deps metapackage not found: $DepsCkan" }
if (-not (Test-Path $deployScript)) { throw "deploy.ps1 not found: $deployScript" }
# Check the local (non-CKAN) mod sources BEFORE the nuke: they are the one class of mod nothing
# else can restore, so a bad path here has to stop the run, not lose the mod.
foreach ($lm in $LocalModGameData) {
    if (-not (Test-Path $lm)) { throw "Local mod GameData not found: $lm  (-LocalModGameData wrong?)" }
    if (-not (Get-ChildItem $lm -Directory -ErrorAction SilentlyContinue)) {
        throw "Local mod GameData has no mod folders in it: $lm"
    }
}
# Guard against the snapshot living inside the instance we're about to wipe.
$instFull  = [IO.Path]::GetFullPath($InstancePath)
$cleanFull = [IO.Path]::GetFullPath($CleanSnapshot)
if ($cleanFull.StartsWith($instFull, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Clean snapshot ($cleanFull) is inside the instance ($instFull) - nuke would destroy it."
}

Write-Host "Rebuild plan:" -ForegroundColor White
Write-Host "  instance : $instFull   (will be DELETED and recreated)"
Write-Host "  snapshot : $cleanFull"
Write-Host "  deps     : $DepsCkan"
if (-not $Force) {
    $ans = Read-Host "`nThis DELETES $instFull. Type 'yes' to continue"
    if ($ans -ne 'yes') { Write-Host 'Aborted.' -ForegroundColor Yellow; return }
}

# --- step 1: nuke ----------------------------------------------------------------------------
Step 1 "Nuke $instFull"
if (Test-Path $instFull) {
    # Critical: drop the RP-AXE junction (and any stray reparse point under GameData) first, so
    # the recursive delete removes only the link, never the repo's real GameData\RP-AXE contents.
    Remove-JunctionLink (Join-Path $instFull 'GameData\RP-AXE')
    Get-ChildItem (Join-Path $instFull 'GameData') -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
        ForEach-Object { Remove-JunctionLink $_.FullName }
    Remove-Item $instFull -Recurse -Force
    Write-Host "  deleted."
} else {
    Write-Host "  (nothing there - skipping)"
}

# --- step 2: copy clean snapshot -------------------------------------------------------------
Step 2 "Copy clean snapshot -> Instance"
# robocopy is faster + handles long paths; exit codes 0-7 are success, 8+ are failure.
robocopy $cleanFull $instFull /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed (exit $LASTEXITCODE)" }
$global:LASTEXITCODE = 0
Write-Host "  copied."

# Clear stray example .craft so CKAN never aborts with "tried to overwrite a file we didn't
# install": part-mods (Tantares, US2, SSPX, ...) ship example craft into Ships\, and CKAN refuses
# to overwrite any pre-existing unowned file. The snapshot's example craft are noise for our
# part/tree work, so wipe them; mods reinstall their own and CKAN then owns them.
$craftCleared = 0
foreach ($d in @('Ships\VAB','Ships\SPH')) {
    $cd = Join-Path $instFull $d
    if (Test-Path $cd) {
        Get-ChildItem $cd -Filter *.craft -File -ErrorAction SilentlyContinue |
            ForEach-Object { Remove-Item $_.FullName -Force; $craftCleared++ }
    }
}
Write-Host "  cleared $craftCleared stray example craft."

# --- step 3: install RP-AXE CKAN dependencies ------------------------------------------------
Step 3 "Install CKAN dependencies (RP-AXE-deps.ckan)"
# --gamedir targets the instance directly (no Manage-instances registration needed).
# --no-recommends keeps the set to the curated deps list (no extra recommends pulled in).
& $CkanExe install -c $DepsCkan --gamedir $instFull --no-recommends --headless
if ($LASTEXITCODE -ne 0) { throw "ckan install failed (exit $LASTEXITCODE)" }
Write-Host "  dependencies installed."

# VERIFY the install actually contains what we asked for. `ckan install` can exit 0 having quietly
# dropped a module from its plan -- on 2026-08-17 it resolved Scatterer-config (a HARD dependency of
# Scatterer) out of the run, exited 0, and left an instance whose Scatterer had no config.cfg and no
# planetsList. Scatterer then did nothing at all, so every atmosphere, ocean and sky was missing and
# the game just "looked different" -- no crash, no error at build time, discovered only by eye.
# Exit code 0 from ckan is therefore NOT evidence the dependency set is present; compare the two
# lists and say so.
$regPath = Join-Path $instFull 'CKAN\registry.json'
if (-not (Test-Path $regPath)) { throw "no CKAN registry at $regPath -- cannot verify the install" }
$declared = (Get-Content $DepsCkan -Raw | ConvertFrom-Json).depends.name
$installed = (Get-Content $regPath -Raw | ConvertFrom-Json).installed_modules.PSObject.Properties.Name
# Some deps are 'provides' aliases, satisfied by a differently-named module, so the alias itself
# never appears in installed_modules. Map alias -> the module that must actually be there, rather
# than skipping the alias: skipping would blind the check for exactly the modules most at risk
# (we deliberately use the alias form BECAUSE the bare identifier is ambiguous, see RP-AXE-deps.ckan).
$providesAliases = @{
    'Scatterer-sunflare-default' = 'Scatterer-sunflare'
    'Scatterer-config-default'   = 'Scatterer-config'
}
$missingDeps = $declared | Where-Object {
    $needed = if ($providesAliases.ContainsKey($_)) { $providesAliases[$_] } else { $_ }
    $needed -notin $installed
}
if ($missingDeps) {
    Write-Host "  DECLARED BUT NOT INSTALLED:" -ForegroundColor Red
    $missingDeps | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    throw "$($missingDeps.Count) declared dependency/dependencies did not install (see above). The instance is incomplete."
}
Write-Host "  verified: all $($declared.Count) declared dependencies present in the CKAN registry."

# --- step 4: install local (non-CKAN) mods ----------------------------------------------------
Step 4 "Install local (non-CKAN) mods"
# Step 3 only knows what is in RP-AXE-deps.ckan, so a mod that lives in a sibling repo is
# invisible to it and the nuke in step 1 is the end of it. Copy each one in and NAME it -- a
# silent step here just moves the failure to the next rebuild.
$localInstalled = 0
foreach ($lm in $LocalModGameData) {
    foreach ($modDir in Get-ChildItem $lm -Directory) {
        $dst = Join-Path $instFull "GameData\$($modDir.Name)"
        robocopy $modDir.FullName $dst /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy (local mod $($modDir.Name)) failed (exit $LASTEXITCODE)" }
        $global:LASTEXITCODE = 0
        Write-Host "  installed $($modDir.Name)  <- $($modDir.FullName)"
        $localInstalled++
    }
}
Write-Host "  $localInstalled local mod(s) installed."

# --- step 5: deploy RP-AXE -------------------------------------------------------------------
Step 5 "Deploy RP-AXE (junction in)"
& $deployScript -InstancePath $instFull

# --- step 6: boot once, then judge what the boot produced -------------------------------------
Step 6 "Verify (boot with -axe-autotest, then run the liveness gate)"
if ($NoVerify) {
    Write-Host "  skipped (-NoVerify). The instance is UNVERIFIED -- after the first launch run:" -ForegroundColor Yellow
    Write-Host "    python tools\check_liveness.py" -ForegroundColor Yellow
} else {
    $kspExe = Join-Path $instFull 'KSP_x64.exe'
    if (-not (Test-Path $kspExe)) { throw "no KSP_x64.exe at $kspExe" }
    Write-Host "  launching $kspExe -axe-autotest (cold load compiles every part; this is slow)"
    # -Wait would block forever on a hung harness, so wait explicitly with a timeout and kill.
    # NB the autotest quits itself when done (quitWhenDone), which is what ends this normally.
    $proc = Start-Process -FilePath $kspExe -ArgumentList '-axe-autotest' `
                          -WorkingDirectory $instFull -PassThru
    $null = $proc.Handle   # cache the handle NOW -- once the process exits, .NET can no longer
                           # open it, and WaitForExit/ExitCode on an uncached handle throws.
    if (-not $proc.WaitForExit($VerifyTimeoutMinutes * 60 * 1000)) {
        Write-Host "  autotest did not finish in $VerifyTimeoutMinutes min -- killing it" -ForegroundColor Yellow
        try { $proc.Kill() } catch {}
        $proc.WaitForExit(30000) | Out-Null
    }

    $log = Join-Path $instFull 'KSP.log'
    if (Test-Path $log) {
        # The harness prints "SUCCESS: visited N screen(s)" -- matching only RESULT|FAILED made a
        # passing run report "(no result line)" every single time, i.e. a check that could never
        # say yes (docs\BUG-CLASSES.md, worthless-check family).
        $result = Select-String -Path $log -Pattern '\[AXE\]\[AutoTest\].*(SUCCESS|RESULT|FAILED)' |
                  Select-Object -Last 5
        if ($result) { $result | ForEach-Object { Write-Host "  $($_.Line.Trim())" } }
        else { Write-Host "  (no [AXE][AutoTest] result line in KSP.log)" -ForegroundColor Yellow }
    }

    $gate = 0
    Push-Location $AxeRepo
    try {
        Write-Host "`n  running tools\check_liveness.py"
        & python (Join-Path $PSScriptRoot 'check_liveness.py') --instance $instFull
        if ($LASTEXITCODE -ne 0) { $gate = 1 }

        Write-Host "`n  running tools\check_settings_parity.py"
        & python (Join-Path $PSScriptRoot 'check_settings_parity.py') `
            --cache (Join-Path $instFull 'GameData\ModuleManager.ConfigCache')
        if ($LASTEXITCODE -ne 0) { $gate = 1 }

        Write-Host "`n  running tools\check_model_anims.py"
        & python (Join-Path $PSScriptRoot 'check_model_anims.py') `
            --cache (Join-Path $instFull 'GameData\ModuleManager.ConfigCache') `
            --gamedata (Join-Path $instFull 'GameData')
        if ($LASTEXITCODE -ne 0) { $gate = 1 }

        Write-Host "`n  running tools\check_solar_wear.py"
        & python (Join-Path $PSScriptRoot 'check_solar_wear.py') `
            --cache (Join-Path $instFull 'GameData\ModuleManager.ConfigCache')
        if ($LASTEXITCODE -ne 0) { $gate = 1 }
    } finally { Pop-Location }
    $global:LASTEXITCODE = 0
    if ($gate -ne 0) {
        Write-Host "`nInstance rebuilt, but the liveness gate FAILED -- see above." -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nInstance rebuilt. RP-AXE deployed, no RP-1." -ForegroundColor Green
