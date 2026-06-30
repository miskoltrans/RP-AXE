<#
.SYNOPSIS
    Vendor the RP-1-authored PARTS we need into GameData/RP-AXE/seed/Parts/ (refreshable).

.DESCRIPTION
    RP-AXE replaces RP-1, so RP-1-authored parts (the RO-* science instruments, the contract
    sat buses, the procedural-avionics part, etc.) are absent in an AXE install. This vendors them
    from the RP-1 SOURCE REPO so the curated manifest is fully loadable. Re-run after `git pull`
    in the RP-1 clone to refresh when RP-1 advances (it stamps the synced RP-1 version).

    What it vendors into seed/Parts/:
      - RP-1/GameData/RP-1/Parts/**            (the 36 new parts + their 163 bundled assets, verbatim)
      - Tree/ProceduralAvionics.cfg            (single file: the proceduralAvionics +PART clone)
      - Science/Experiments/BioSample.cfg      (single file: the BioCapsule part + its experiment)

    Path transform: RP-1's part configs reference assets by the absolute GameData path
    "RP-1/Parts/...". Since there is no RP-1/ folder in an AXE install, every vendored .cfg has
    "RP-1/Parts/" rewritten to "RP-AXE/seed/Parts/" so MODEL/texture paths resolve. This is a
    deterministic transform applied by THIS script -- seed/ is still a refresh-on-resync import,
    never hand-edited (put AXE changes in design/).

    Deliberately NOT vendored: RP-1's Tree/ and Science/ wholesale (that is RP-1's tech tree +
    science system, which RP-AXE is rebuilding). Only the two part-defining outlier files above.

.EXAMPLE
    pwsh tools/sync-rp1-parts.ps1
    pwsh tools/sync-rp1-parts.ps1 -Rp1Path C:\git\ksp\RP-1
#>
[CmdletBinding()]
param(
    [string]$Rp1Path = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'RP-1')
)

$ErrorActionPreference = 'Stop'
$repoRoot   = Split-Path -Parent $PSScriptRoot
$rp1Data    = Join-Path $Rp1Path 'GameData\RP-1'
$partsDest  = Join-Path $repoRoot 'GameData\RP-AXE\seed\Parts'
$extraDest  = Join-Path $partsDest '_RP-AXE-extra'   # the single-file outliers from Tree/ & Science/

if (-not (Test-Path (Join-Path $rp1Data 'Parts'))) { throw "RP-1 Parts not found: $rp1Data\Parts" }

$REWRITE_FROM = 'RP-1/Parts/'
$REWRITE_TO   = 'RP-AXE/seed/Parts/'
$utf8 = New-Object System.Text.UTF8Encoding($false)   # no BOM

function Rewrite-CfgPaths([string]$root) {
    $n = 0
    Get-ChildItem $root -Recurse -Filter *.cfg -File | ForEach-Object {
        $txt = [System.IO.File]::ReadAllText($_.FullName)
        if ($txt.Contains($REWRITE_FROM)) {
            [System.IO.File]::WriteAllText($_.FullName, $txt.Replace($REWRITE_FROM, $REWRITE_TO), $utf8)
            $n++
        }
    }
    return $n
}

# --- 1. vendor RP-1/Parts/ verbatim (configs + assets) ---
if (Test-Path $partsDest) { Remove-Item $partsDest -Recurse -Force }
New-Item -ItemType Directory -Path $partsDest -Force | Out-Null
Copy-Item (Join-Path $rp1Data 'Parts\*') $partsDest -Recurse -Force
$cfgN = (Get-ChildItem $partsDest -Recurse -Filter *.cfg -File).Count
$astN = (Get-ChildItem $partsDest -Recurse -File | Where-Object { $_.Extension -in '.mu','.dds','.png' }).Count
Write-Host "Vendored RP-1/Parts/ -> seed/Parts/  ($cfgN cfgs, $astN assets)"

# --- 2. vendor the two part-defining outliers (single files) ---
New-Item -ItemType Directory -Path $extraDest -Force | Out-Null
$outliers = @('Tree\ProceduralAvionics.cfg', 'Science\Experiments\BioSample.cfg')
foreach ($rel in $outliers) {
    $from = Join-Path $rp1Data $rel
    if (-not (Test-Path $from)) { Write-Warning "skip (missing): $from"; continue }
    Copy-Item $from (Join-Path $extraDest (Split-Path $rel -Leaf)) -Force
    Write-Host "Vendored $rel -> seed/Parts/_RP-AXE-extra/"
}

# --- 3. rewrite RP-1/Parts/ asset paths in all vendored cfgs ---
$rw = Rewrite-CfgPaths $partsDest
Write-Host "Rewrote '$REWRITE_FROM' -> '$REWRITE_TO' in $rw cfg file(s)"

# --- 4. stamp provenance ---
$verFile = Join-Path $rp1Data 'RP-1.version'
$ver = if (Test-Path $verFile) { ((Get-Content $verFile -Raw) -replace '\s+', ' ').Trim() } else { '(RP-1.version not found)' }
$stamp = Join-Path $partsDest '_SYNC_PROVENANCE.txt'
Set-Content $stamp "Vendored from `"$rp1Data`" on $(Get-Date -Format 'yyyy-MM-dd HH:mm').`r`nRP-1.version: $ver`r`nPaths rewritten: $REWRITE_FROM -> $REWRITE_TO`r`nDo not hand-edit; re-run tools/sync-rp1-parts.ps1 to refresh." -Encoding UTF8
Write-Host "Stamped seed/Parts/_SYNC_PROVENANCE.txt (RP-1 $ver)" -ForegroundColor Green
Write-Host "Done. Reload KSP (cold MM re-patch) to load the vendored parts." -ForegroundColor Green
