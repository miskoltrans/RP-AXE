<#
.SYNOPSIS
    Refresh the vendored RP-1 config in GameData/RP-AXE/seed/ from the RP-1 source repo.

.DESCRIPTION
    Vendors the RP-1 config that shapes parts / tech tree / economy into GameData/RP-AXE/seed/
    (overwriting), then stamps the RP-1 version + timestamp into seed/_README.md.

    Vendored set:
      - Folders (recursive, verbatim incl. binary part assets): Contracts, Science, Parts
        (NOT the whole Tree -- RP-AXE builds its own tech tree from tree/nodes.yaml -> design/Tree/)
      - Loose root .cfg read by KEPT mods/stock: Deprecation, ResourceCosts, ProcCosts, PartHacks,
        RealFuelsSettings
      - A NARROW slice of Tree/ (upgrade CONTENT, not tree STRUCTURE): TREE-Engines.cfg,
        UpgradeCleanup.cfg, RFTechLevels.cfg (engines) + PFTechLevels.cfg, PayloadLevels.cfg (capability
        keepers) -> seed/Tree/. These define the RealFuels engine CONFIG
        upgrade ladder (517 RFUpgrade_* PARTUPGRADEs + the deleteme/orphan-cleanup machinery); AXE
        overlays their techRequired onto AXE nodes in design/Tree/ (AxePartPlacement.cfg +
        AxeEngineConfigGates.cfg). RP0TechTree.cfg (the tree structure) stays EXCLUDED.

    Everything else in RP-1/GameData/RP-1 is EXCLUDED on purpose (see $excludeReason) -- mostly the
    axed RP0.dll career/economy and configs RP-AXE already replaces in design/. Anything upstream that
    is neither vendored nor explicitly excluded raises a loud "UNCATEGORISED" warning (the
    anti-silent-drop guard): the old whitelist silently dropped Parts/ and that hid real tree changes.

    Files under seed/ are an upstream import and must never be hand-edited -- all RP-AXE changes belong
    in GameData/RP-AXE/design/ (see docs/WORKFLOW.md, "Vendoring & keeping it fresh").

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

# (b2) a NARROW slice of Tree/ -- engine-upgrade CONTENT only (NOT the tree structure). Vendored into
#      seed/Tree/ verbatim; AXE remaps their techRequired -> AXE nodes via design/Tree/ overlays
#      (AxePartPlacement.cfg for the PARTUPGRADEs, AxeEngineConfigGates.cfg for the CONFIG gates).
#      RP0TechTree.cfg and everything else under Tree/ stay EXCLUDED (see $excludeReason['Tree']).
$treeFiles = @(
    'TREE-Engines.cfg',       # 517 RFUpgrade_* PARTUPGRADEs + per-CONFIG walker + deleteme decrement
    'UpgradeCleanup.cfg',     # !PARTUPGRADE:HAS[#deleteme[>0]] -- inert-deletes host-absent configs
    'RFTechLevels.cfg',       # engine-TYPE tech levels + solids/RCS typelevel upgrades + MLI tank ins.
    'PFTechLevels.cfg',       # PFTech-Fairing-I..VI: procedural minDensity (mass) tech tokens + UPGRADES effect
    'PayloadLevels.cfg'       # ComSat/NavSat bus avionics tokens (RFTech-Com/NavSat-II/III + RP-1-PayloadTech-*)
)

# (c) explicit, REASONED exclusions. Anything in RP-1/GameData/RP-1 that is NOT in (a)/(b)/(c) trips
#     the leftovers audit below -- that is the anti-silent-drop guard for future RP-1 bumps.
$excludeReason = [ordered]@{
    'Tree'                       = 'tree STRUCTURE stays AXE-authored (tree/nodes.yaml -> design/Tree/ via build_tree.py); RP0TechTree.cfg would conflict, HardDriveUpgrades.cfg lives in design/Science/. NARROW exception: 5 upgrade CONTENT files (3 engine + PFTech/Payload capability keepers) are selectively vendored into seed/Tree/ via $treeFiles above.'
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
    'TestFlightRnD.cfg'          = 'TestFlight configs out-of-scope (see docs/WORKFLOW.md)'
    'CustomBarnKit.cfg'          = 'RP-AXE authors its OWN CBK ladders in design/Settings/AxeFacilities.cfg + AxeTrackingStation.cfg (launchpad, Mission Control, VAB/SPH, runway, R&D, Astronaut Complex, tracking station). Was "RP-AXE uses CBK defaults" -- true once, false since the facility passes; kept excluded because AXE owns these numbers, not because it has no opinion.'
    'GameParameters.cfg'         = 'difficulty/funds presets double-count with design/Rewards'
    'SpaceCenterSettings.cfg'    = 'RP0.dll budget/maintenance/training economy'
    'ProgramHandlerSettings.cfg' = 'RP0.dll ProgramHandler economy'
    'CrewSettings.cfg'           = 'RP0.dll crew retirement/training system -- BUT NOT ALL OF IT: the file also carries a @PHYSICSGLOBALS block (kerbal G tolerance) and @EXPERIENCE_TRAIT modifiers that RP0.dll has nothing to do with. Excluding the file wholesale on the strength of its name left those at stock for months (docs/BUG-CLASSES.md finding 6). AXE now re-authors that half itself in design/Settings/AxeCrewPhysics.cfg -- re-read the RP-1 file, not just this line, when bumping.'
    'CrewTrainingTimes.cfg'      = 'RP0.dll crew training'
    'changelog.cfg'              = 'KSP-AVC changelog'
    'RP-1.version'               = 'version stamp (read for _README)'
    'KACIcon15.truecolor'        = 'UI image'
    'maintecost.truecolor'       = 'UI image'
    'zTweakScale.cfg'            = 'optional (TweakScale freescale) -- move to $rootFiles to include'
    'KSPCommunityFixes.cfg'      = 'RP-AXE authors its own KSPCF toggles in design/Settings/AxeCommunityFixes.cfg (it takes 4 of RP-1s 8 and records why StrategyDuration is refused). Do NOT move to $rootFiles -- that would re-add RP-1s set on top.'
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
    'Parts\Science\US2.cfg'              # -> design\Science\US2.cfg (US2 wedge inline Configure tech= remapped)
    'Science\HardDriveConfigs.cfg'       # -> design\Science\HardDriveConfigs.cfg (nodes remapped)
    'Science\HardDriveConfigs.disabled'  #    (inert; design\ owns the HardDrive system)
    # Not design-owned but DEAD: IGNORED_EXPERIMENTS has no reader outside RP0.dll (RP-1 reads it in
    # RP0\Singletons\Database.cs to pre-complete body/experiment/situation combos). Shipping it made
    # a 280-line file that looks authored and does nothing -- bug family A1, and it failed
    # check_liveness.py check C on every run. AXE's equivalent intent lives in
    # design\Science\EarthScienceRemoval.cfg, which zeroes the situations rather than pre-completing
    # them. Re-vendor it only if AXE ever ships a reader.
    'Science\IgnoredExperiments.cfg'
    # (Tree\HardDriveUpgrades.cfg needs no strip -- Tree\ is no longer vendored; its
    #  remapped version lives in design\Science\HardDriveUpgrades.cfg)
)
foreach ($rel in $designOwned) {
    $p = Join-Path $seedRoot $rel
    if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "  Stripped design-owned $rel (lives in design\Science\)" -ForegroundColor Yellow }
}

# --- rewrite RP-1 prose that describes systems AXE does not have -----------------
# The contract DESCRIPTIONS are vendored verbatim, and some of them explain RP-1's career
# mechanics to the player. Those paragraphs are not flavour we can leave alone: they are
# instructions for systems AXE cut, so they are actively false in game. This is a TEXT pass
# only -- verified 2026-07-30 that nothing mechanical rides on either one (the 17 crewed/X-plane
# contracts carry stock CC `HasCrew`, never a training REQUIREMENT; RP-1 enforced training in
# RP0.dll's preflight, not in the contract).
#
# It lives HERE, not as a hand edit of seed\, because seed\ is wholesale re-vendored from the
# RP-1 clone on every refresh -- an edit there dies silently on the next `git pull` + re-sync.
#
# Each fix asserts its EXPECTED hit count and shouts when reality disagrees, because the whole
# pass is a string match against upstream prose: if RP-1 reworded a sentence, a silent 0 matches
# would leave the false text shipping while this step still printed success. docs/BUG-CLASSES.md
# family C, rules 2 and 3 -- a bounded pass must report what it did not do.
$textFixes = @(
    @{
        Name     = 'RP-1 crew-training note'
        Expected = 17
        # One byte-identical block, always the trailing sentence of `description`. Lazy to the first
        # closing tag; `.` does not cross newlines in .NET regex and the value is a single line.
        Pattern  = '<br><br><b><color=green>Note: Astronauts must be trained before launch\..*?toolbar\.</color></b>'
        Replace  = ''
        Why      = 'crew training + its toolbar UI are CUT from AXE -- there is no RP-1 window and no Training tab'
    },
    @{
        Name     = 'Astronaut Complex level number'
        Expected = 2
        Pattern  = 'updated your Astronaut Complex to level five'
        Replace  = 'upgraded your Astronaut Complex to level two'
        # AXE keeps CustomBarnKit's stock 3-level Astronaut Complex on purpose (AxeFacilities.cfg
        # @ASTRONAUTS) and leaves unlockedEVAFlags = 2, so flag planting unlocks at L2 of 3.
        # RP-1's "level five" is the top of its own 5-level ladder and cannot be reached here.
        Why      = 'RP-1 ladder number; AXE unlocks flags at Astronaut Complex L2 of 3'
    }
)

$contractsRoot = Join-Path $seedRoot 'Contracts'
if (Test-Path $contractsRoot) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $cfgs = Get-ChildItem -Path $contractsRoot -Filter '*.cfg' -File -Recurse
    foreach ($fix in $textFixes) {
        $hits = 0
        foreach ($cfg in $cfgs) {
            $text = [System.IO.File]::ReadAllText($cfg.FullName)
            $new = [regex]::Replace($text, $fix.Pattern, $fix.Replace)
            if ($new -ne $text) {
                [System.IO.File]::WriteAllText($cfg.FullName, $new, $utf8NoBom)
                $hits++
            }
        }
        $label = "  Rewrote $($fix.Name): $hits file(s) -- $($fix.Why)"
        if ($hits -eq $fix.Expected) {
            Write-Host $label -ForegroundColor Yellow
        } elseif ($hits -eq 0) {
            Write-Host "  !! $($fix.Name): 0 matches, EXPECTED $($fix.Expected)." -ForegroundColor Red
            Write-Host "     The pattern has rotted -- RP-1 most likely reworded it. The false text is" -ForegroundColor Red
            Write-Host "     SHIPPING until the pattern is re-derived. Do not ignore this." -ForegroundColor Red
        } else {
            Write-Host "$label  [!! expected $($fix.Expected) -- upstream changed; confirm the delta is intended]" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  !! seed\Contracts missing -- RP-1 prose fixes did not run." -ForegroundColor Red
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

# --- vendor the narrow Tree/ engine-upgrade slice into seed/Tree/ (self-cleaning) ---
$seedTree = Join-Path $seedRoot 'Tree'
if (Test-Path $seedTree) { Get-ChildItem -Path $seedTree -Filter '*.cfg' -File -ErrorAction SilentlyContinue | Remove-Item -Force }
else { New-Item -ItemType Directory -Path $seedTree | Out-Null }
foreach ($f in $treeFiles) {
    $from = Join-Path $rp1Data (Join-Path 'Tree' $f)
    $to   = Join-Path $seedTree $f
    if (-not (Test-Path $from)) { Write-Warning "skip (missing): $from"; continue }
    Copy-Item $from $to -Force
    Write-Host "Vendored Tree\$f -> seed\Tree\$f"
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
