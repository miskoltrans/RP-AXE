<#
.SYNOPSIS
    Rebuild the KSP test Instance from a pristine snapshot: nuke -> copy clean -> install
    RP-AXE CKAN deps -> install our SCANsat fork -> deploy RP-AXE. No RP-1 anywhere.

.DESCRIPTION
    Five steps:
      1. NUKE     - delete C:\git\ksp\Instance (after first unlinking the RP-AXE junction so the
                    recursive delete can't follow it into the repo and wipe GameData\RP-AXE).
      2. COPY     - mirror the pristine snapshot (..\ksp_instance_clean) into a fresh Instance.
                    The snapshot is a clean KSP 1.12.5 with the DLCs present, kept OUTSIDE this
                    working tree so nukes/Steam updates can't touch it.
      3. DEPS     - ckan install the RP-AXE perfect-environment mod set from RP-AXE-deps.ckan,
                    targeting the instance directly via --gamedir (no CKAN registration needed).
      4. SCANSAT  - build our SCANsat fork (C:\git\ksp\SCANsat, not on CKAN) and copy its
                    GameData\SCANsat into the instance. NOT a CKAN dependency on purpose.
      5. DEPLOY   - junction GameData\RP-AXE in via deploy.ps1 (AXE.dll ships in the repo, so no
                    build step is required).

    The pristine snapshot does NOT contain RP-1, so nothing has to be disabled.

.PARAMETER CleanSnapshot
    Pristine KSP install to copy from. Default C:\git\ksp_instance_clean (sibling of the ksp
    working tree, so a nuke of Instance never reaches it). Create it once by copying a verified
    stock KSP 1.12.5 (with Making History / Breaking Ground) here.

.PARAMETER ScanSatForkPath
    Our SCANsat fork checkout (miskoltrans/SCANsat-GPU). Default C:\git\ksp\SCANsat. Built with
    `dotnet build SCANsat\SCANsat.csproj -c Release` (not the .sln -- SCANmechjeb in the same
    solution doesn't build against the current MechJeb API and isn't needed).

.PARAMETER Force
    Skip the "are you sure" confirmation before the destructive nuke.

.EXAMPLE
    pwsh tools/rebuild-instance.ps1
    pwsh tools/rebuild-instance.ps1 -Force
    pwsh tools/rebuild-instance.ps1 -CleanSnapshot D:\ksp_clean -Force
#>
[CmdletBinding()]
param(
    [string]$InstancePath    = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'Instance'),
    [string]$CleanSnapshot   = (Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))) 'ksp_instance_clean'),
    [string]$CkanExe         = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'ckan.exe'),
    [string]$DepsCkan        = (Join-Path (Split-Path -Parent $PSScriptRoot) 'RP-AXE-deps.ckan'),
    [string]$ScanSatForkPath = (Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))) 'SCANsat'),
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$deployScript = Join-Path $PSScriptRoot 'deploy.ps1'

function Step($n, $msg) { Write-Host "`n[$n/5] $msg" -ForegroundColor Cyan }

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
$scanSatCsproj = Join-Path $ScanSatForkPath 'SCANsat\SCANsat.csproj'
if (-not (Test-Path $scanSatCsproj)) { throw "SCANsat fork not found: $scanSatCsproj  (-ScanSatForkPath wrong?)" }
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw "dotnet CLI not found on PATH (needed to build the SCANsat fork)" }
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
Write-Host "  scansat  : $ScanSatForkPath (our fork, built fresh)"
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
# --no-recommends keeps the set to the curated 81 modules (no extra recommends pulled in).
& $CkanExe install -c $DepsCkan --gamedir $instFull --no-recommends --headless
if ($LASTEXITCODE -ne 0) { throw "ckan install failed (exit $LASTEXITCODE)" }
Write-Host "  dependencies installed."

# --- step 4: build + install our SCANsat fork (not a CKAN dependency) -------------------------
Step 4 "Build and install SCANsat fork"
Push-Location $ScanSatForkPath
try {
    # Build just SCANsat.csproj (pulls in SCANsat.Unity via ProjectReference). Not the .sln --
    # SCANmechjeb in the same solution targets a MechJeb API that's since changed and won't build,
    # and we don't ship it. KSPBuildTools' post-build target syncs the DLLs + .version into the
    # fork's own GameData\SCANsat automatically.
    & dotnet build 'SCANsat\SCANsat.csproj' -c Release
    if ($LASTEXITCODE -ne 0) { throw "dotnet build failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}
$scanSatSrc = Join-Path $ScanSatForkPath 'GameData\SCANsat'
$scanSatDst = Join-Path $instFull 'GameData\SCANsat'
if (-not (Test-Path $scanSatSrc)) { throw "SCANsat build did not produce $scanSatSrc" }
robocopy $scanSatSrc $scanSatDst /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy (SCANsat) failed (exit $LASTEXITCODE)" }
$global:LASTEXITCODE = 0
Write-Host "  SCANsat fork built and installed -> $scanSatDst"

# --- step 5: deploy RP-AXE -------------------------------------------------------------------
Step 5 "Deploy RP-AXE (junction in)"
& $deployScript -InstancePath $instFull

Write-Host "`nInstance rebuilt. RP-AXE deployed, our SCANsat fork installed, no RP-1." -ForegroundColor Green
