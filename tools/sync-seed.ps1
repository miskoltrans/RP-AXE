<#
.SYNOPSIS
    Refresh the vendored RP-1 config in GameData/RP-AXE/seed/ from the RP-1 source repo.

.DESCRIPTION
    Vendors the RP-1 config that shapes parts / tech tree / economy into GameData/RP-AXE/seed/
    (overwriting), then stamps the RP-1 version + timestamp into seed/_README.md.

    Vendored set:
      - Folders (recursive, verbatim incl. binary part assets): Contracts, Science, Parts
        (NOT Tree -- RP-AXE builds its own tech tree from tree/nodes.yaml -> design/Tree/)
      - Loose root .cfg read by KEPT mods/stock: Deprecation, ResourceCosts, ProcCosts, PartHacks,
        RealFuelsSettings

    Everything else in RP-1/GameData/RP-1 is EXCLUDED on purpose (see $excludeReason) -- mostly the
    axed RP0.dll career/economy and configs RP-AXE already replaces in design/. Anything upstream that
    is neither vendored nor explicitly excluded raises a loud "UNCATEGORISED" warning (the
    anti-silent-drop guard): the old whitelist silently dropped Parts/ and that hid real tree changes.

    Files under seed/ are an upstream import and must never be hand-edited -- all RP-AXE changes belong
    in GameData/RP-AXE/design/ (see docs/ARCHITECTURE.md section 8).

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

# --- what we vendor -------------------------------------------------------------

# (a) whole folders, recursive (verbatim, incl. binary part assets under Parts/**)
#     NOT 'Tree': RP-AXE builds its own tech tree from scratch (tree/nodes.yaml -> design/Tree/).
$folders = @('Contracts', 'Science', 'Parts')

# (b) loose root-level .cfg files, copied individually into seed/ root (MM applies regardless of path).
#     Only files read by KEPT mods / stock that shape parts/tree/economy.
$rootFiles = @(
    'Deprecation.cfg',        # -PART removes superseded stock battery/avionics/heatshield parts
    'ResourceCosts.cfg',      # RealFuels/CRP propellant unitCost -> launch-cost (the kept funds sink)
    'ProcCosts.cfg',          # ProceduralParts/RealFuels/B9 part & tank cost/costPerkL -> launch-cost
    'PartHacks.cfg',          # tank-type availability, capsule EC cost, hides probeCoreSphere->ORPHANS
    'RealFuelsSettings.cfg'   # RealFuels MFSSETTINGS
    # ,'zTweakScale.cfg'       # optional: TweakScale freescale (safe; move here to include)
    # ,'KSPCommunityFixes.cfg' # optional: KSPCF toggles (safe; move here to include)
)

# (c) explicit, REASONED exclusions. Anything in RP-1/GameData/RP-1 that is NOT in (a)/(b)/(c) trips
#     the leftovers audit below -- that is the anti-silent-drop guard for future RP-1 bumps.
$excludeReason = [ordered]@{
    'Tree'                       = 'RP-AXE builds its own tech tree from tree/nodes.yaml -> design/Tree/ (build_tree.py); RP-1 RP0TechTree.cfg would conflict, HardDriveUpgrades.cfg lives in design/Science/'
    'Plugins'                    = 'axed RP0.dll / CC_RP0.dll'
    'PluginData'                 = 'RP0.dll data'
    'Resources'                  = 'RP0.dll UI images'
    'Programs'                   = 'replaced by design/Programs switcher'
    'Strategies'                 = 'Strategia / leaders system axed'
    'SCMData'                    = 'RP0.dll SpaceCenterManagement data'
    'KCT_Presets'                = 'build-time system axed (KCT not installed)'
    'Agencies'                   = 'RP0 contract sponsors; not parts/tree'
    'Scenarios'                  = 'RP-AXE uses GenerousStart.cs / design start'
    'Filter_Extensions_Configs'  = 'replaced by design/Filter_Extensions_Configs/AxeFilter.cfg'
    'Localization'               = 'only axed-KCT loc keys referenced; LocPatches rewrites mgmt UI'
    'Flags'                      = 'cosmetic'
    'Craft Files'                = 'stock craft, not config'
    'Tooling'                    = 'tooling system axed (husk-only)'
    'Avionics.cfg'               = 'replaced by design/Tree/AxeAvionicsCore.cfg'
    'NonRP0.cfg'                 = 'replaced by design zzzzAxeSackNonRO + OrphanBrowser'
    'ModuleStationParts.cfg'     = 'husk-only; revisit if station contracts need ModuleStationPart'
    'zFinal.cfg'                 = 'ModuleShowInfo flood; clamp-command bit -> design/ if wanted'
    'ToolingDefinitions.cfg'     = 'tooling system axed (inert)'
    'TestFlightRnD.cfg'          = 'TestFlight configs out-of-scope (DEPENDENCIES.md)'
    'CustomBarnKit.cfg'          = 'RP-AXE uses CBK defaults (DEPENDENCIES.md)'
    'GameParameters.cfg'         = 'difficulty/funds presets double-count with design/Rewards'
    'SpaceCenterSettings.cfg'    = 'RP0.dll budget/maintenance/training economy'
    'ProgramHandlerSettings.cfg' = 'RP0.dll ProgramHandler economy'
    'CrewSettings.cfg'           = 'RP0.dll crew retirement system'
    'CrewTrainingTimes.cfg'      = 'RP0.dll crew training'
    'changelog.cfg'              = 'KSP-AVC changelog'
    'RP-1.version'               = 'version stamp (read for _README)'
    'KACIcon15.truecolor'        = 'UI image'
    'maintecost.truecolor'       = 'UI image'
    'zTweakScale.cfg'            = 'optional (TweakScale freescale) -- move to $rootFiles to include'
    'KSPCommunityFixes.cfg'      = 'optional (KSPCF toggles) -- move to $rootFiles to include'
}

# --- vendor folders -------------------------------------------------------------
foreach ($f in $folders) {
    $from = Join-Path $rp1Data $f
    $to   = Join-Path $seedRoot $f
    if (-not (Test-Path $from)) { Write-Warning "skip (missing): $from"; continue }
    if (Test-Path $to) { Remove-Item $to -Recurse -Force }
    Copy-Item $from $to -Recurse -Force
    Write-Host "Vendored $f\ -> seed\$f\"
}

# --- strip design-owned science from the wholesale vendor ------------------------
# We vendor RP-1's whole Science\ folder as-is, EXCEPT the tech-remapped subset that
# GameData\RP-AXE\design\Science\ owns. Those gate on AXE tree nodes via patch
# directives ModuleManager can't overlay (@PART[*]:HAS[#TechRequired[...]],
# MODULE UPGRADE{techRequired__}), so their AXE-node versions had to be authored
# copies in design\. If RP-1's originals also shipped in seed\ they'd DUPLICATE:
# duplicate EXPERIMENT_DEFINITION ids (CrewScience) and a second HardDrive module on
# every command part (HardDriveConfigs). Strip them after the copy. See
# GameData\RP-AXE\design\Science\_README.md + CrewScience\_README.md.
$designOwned = @(
    'Science\Experiments\CrewScience'    # -> design\Science\CrewScience\ (nodes remapped)
    'Science\Configure.cfg'              # -> design\Science\Configure.cfg (Kerbalism SETUP tech= remapped)
    'Science\HardDriveConfigs.cfg'       # -> design\Science\HardDriveConfigs.cfg (nodes remapped)
    'Science\HardDriveConfigs.disabled'  #    (inert; design\ owns the HardDrive system)
    # (Tree\HardDriveUpgrades.cfg needs no strip -- Tree\ is no longer vendored; its
    #  remapped version lives in design\Science\HardDriveUpgrades.cfg)
)
foreach ($rel in $designOwned) {
    $p = Join-Path $seedRoot $rel
    if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "  Stripped design-owned $rel (lives in design\Science\)" -ForegroundColor Yellow }
}

# --- vendor loose root .cfg files (self-cleaning: drop stale seed root *.cfg first) ---
Get-ChildItem -Path $seedRoot -Filter '*.cfg' -File -ErrorAction SilentlyContinue | Remove-Item -Force
foreach ($f in $rootFiles) {
    $from = Join-Path $rp1Data $f
    $to   = Join-Path $seedRoot $f
    if (-not (Test-Path $from)) { Write-Warning "skip (missing): $from"; continue }
    Copy-Item $from $to -Force
    Write-Host "Vendored $f -> seed\$f"
}

# --- leftovers audit: turn future silent drops into loud warnings ---------------
$known = @($folders) + @($rootFiles) + @($excludeReason.Keys)
foreach ($item in Get-ChildItem $rp1Data) {
    if ($known -notcontains $item.Name) {
        Write-Warning ("UNCATEGORISED upstream item '{0}' -- neither vendored nor explicitly excluded. " +
                       "Triage it in tools/sync-seed.ps1 (this is the silent-drop class of bug)." -f $item.Name)
    }
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
