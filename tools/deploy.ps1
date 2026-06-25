<#
.SYNOPSIS
    Link RP-AXE into the test KSP instance and disable RP-1's career layer (or revert).

.DESCRIPTION
    Creates a directory junction  Instance\GameData\RP-AXE -> repo\GameData\RP-AXE  so repo edits
    are live in the instance, and MOVES  Instance\GameData\RP-1  out to  Instance\RP-1.disabled
    (outside GameData) so RP-1's tree/contracts/plugins don't collide with RP-AXE. Shared
    dependencies are left untouched.

    NOTE: KSP's GameDatabase loads every .cfg and .dll found ANYWHERE under GameData, regardless of
    folder name. Renaming a folder to ".disabled" *inside* GameData does NOT disable it -- the mod
    must be moved out of GameData entirely. That's why the holding location is Instance\RP-1.disabled.

.EXAMPLE
    pwsh tools/deploy.ps1            # link AXE in, disable RP-1 career layer
    pwsh tools/deploy.ps1 -Revert    # unlink AXE, re-enable RP-1
#>
[CmdletBinding()]
param(
    [switch]$Revert,
    # Defaults assume the standard C:\git\ksp\ layout; override if your instance lives elsewhere.
    [string]$InstancePath = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'Instance')
)

$ErrorActionPreference = 'Stop'
$repoGameData = Join-Path (Split-Path -Parent $PSScriptRoot) 'GameData\RP-AXE'
$instGameData = Join-Path $InstancePath 'GameData'
$axeLink      = Join-Path $instGameData 'RP-AXE'
$rp1          = Join-Path $instGameData 'RP-1'
# Holding location is OUTSIDE GameData (see header note) so KSP stops scanning it.
$rp1Disabled  = Join-Path $InstancePath 'RP-1.disabled'

if (-not (Test-Path $instGameData)) { throw "Instance GameData not found: $instGameData" }
if (-not (Test-Path $repoGameData)) { throw "Repo GameData not found: $repoGameData" }

function Remove-Junction([string]$path) {
    if (Test-Path $path) {
        $item = Get-Item $path -Force
        if ($item.LinkType -eq 'Junction' -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            # Remove the reparse point without touching the target contents.
            (Get-Item $path -Force).Delete()
            Write-Host "Removed junction: $path"
        } else {
            throw "$path exists and is NOT a junction; refusing to delete a real folder."
        }
    }
}

if ($Revert) {
    Remove-Junction $axeLink
    if ((Test-Path $rp1Disabled) -and -not (Test-Path $rp1)) {
        Move-Item $rp1Disabled $rp1
        Write-Host "Re-enabled RP-1 career layer (moved back into GameData)."
    }
    Write-Host "Reverted. RP-1 active, RP-AXE unlinked." -ForegroundColor Green
    return
}

# --- deploy ---
if ((Test-Path $rp1) -and -not (Test-Path $rp1Disabled)) {
    Move-Item $rp1 $rp1Disabled
    Write-Host "Moved RP-1 career layer out of GameData -> $rp1Disabled"
} elseif (Test-Path $rp1) {
    Write-Warning "Both $rp1 and $rp1Disabled exist; leaving RP-1 in place. Resolve manually."
}

Remove-Junction $axeLink
New-Item -ItemType Junction -Path $axeLink -Value $repoGameData | Out-Null
Write-Host "Linked $axeLink -> $repoGameData"
Write-Host "Deployed. RP-AXE active, RP-1 disabled." -ForegroundColor Green
Write-Host "Reminder: build AXE.dll into GameData\RP-AXE\Plugins before launch (see docs/WORKFLOW.md)."
