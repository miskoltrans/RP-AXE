<#
.SYNOPSIS
    Refresh the vendored RP-1 config in GameData/RP-AXE/seed/ from the RP-1 source repo.

.DESCRIPTION
    Copies the RP-1 config folders we vendor (Tree, Contracts, Science) into
    GameData/RP-AXE/seed/ (overwriting), then stamps the RP-1 version + timestamp into
    seed/_README.md. Files under seed/ are an upstream import and must never be hand-edited --
    all RP-AXE changes belong in GameData/RP-AXE/design/ (see docs/ARCHITECTURE.md section 8).

.EXAMPLE
    pwsh tools/sync-seed.ps1
    pwsh tools/sync-seed.ps1 -Rp1Path C:\git\ksp\RP-1
#>
[CmdletBinding()]
param(
    [string]$Rp1Path = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'RP-1')
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$seedRoot = Join-Path $repoRoot 'GameData\RP-AXE\seed'
$rp1Data  = Join-Path $Rp1Path 'GameData\RP-1'

if (-not (Test-Path $rp1Data)) { throw "RP-1 GameData not found: $rp1Data" }

# folders to vendor verbatim
$folders = @('Tree', 'Contracts', 'Science')

foreach ($f in $folders) {
    $from = Join-Path $rp1Data $f
    $to   = Join-Path $seedRoot $f
    if (-not (Test-Path $from)) { Write-Warning "skip (missing): $from"; continue }
    if (Test-Path $to) { Remove-Item $to -Recurse -Force }
    Copy-Item $from $to -Recurse -Force
    Write-Host "Vendored $f -> seed\$f"
}

# Stamp provenance in seed/_README.md.
$verFile = Join-Path $rp1Data 'RP-1.version'
$ver = if (Test-Path $verFile) { ((Get-Content $verFile -Raw) -replace '\s+', ' ').Trim() } else { '(RP-1.version not found)' }
$line = "- Synced from `"$rp1Data`" on $(Get-Date -Format 'yyyy-MM-dd HH:mm'). RP-1.version: $ver"

$readme = Join-Path $seedRoot '_README.md'
if (Test-Path $readme) {
    $content = Get-Content $readme -Raw
    $content = $content -replace '- _\(not yet run.*?\)_', $line
    if ($content -notmatch [regex]::Escape($line)) {
        # already stamped before: replace the previous stamp line
        $content = $content -replace '(?m)^- Synced from .*$', $line
    }
    Set-Content $readme $content -Encoding UTF8
    Write-Host "Stamped provenance in seed/_README.md"
}
Write-Host "Done. Never edit files under seed/ -- put changes in design/." -ForegroundColor Green
