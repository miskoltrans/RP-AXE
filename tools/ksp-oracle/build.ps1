# Build the oracle against the install's own KSP assemblies.
#
# csc.exe rather than `dotnet build`, and .NET Framework rather than net8.0, because that is what
# Assembly-CSharp is: a Unity mono assembly. This is the toolchain it already links against, and
# it needs no targeting pack installed.
#
#   pwsh tools/ksp-oracle/build.ps1 [-Instance C:\git\ksp\Instance]

param(
    [string]$Instance = "$PSScriptRoot\..\..\..\Instance"
)

$ErrorActionPreference = "Stop"

$managed = Join-Path $Instance "KSP_x64_Data\Managed"
if (-not (Test-Path $managed)) { throw "no KSP Managed directory at $managed" }

$bin = Join-Path $PSScriptRoot "bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null

# The exe must sit beside the assemblies it loads; .NET Framework will not probe elsewhere.
foreach ($dll in @("Assembly-CSharp.dll", "UnityEngine.dll", "UnityEngine.CoreModule.dll")) {
    Copy-Item (Join-Path $managed $dll) $bin -Force
}

$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "csc.exe not found at $csc" }

$bridge = Join-Path $PSScriptRoot "..\..\Source\AXE\Bridge"
$sources = @(
    (Join-Path $bridge "AxeJson.cs"),
    (Join-Path $bridge "AxeJsonReader.cs"),
    (Join-Path $PSScriptRoot "Shim.cs"),
    (Join-Path $PSScriptRoot "OracleSystem.cs"),
    (Join-Path $PSScriptRoot "Shooter.cs"),
    (Join-Path $PSScriptRoot "SelfTest.cs"),
    (Join-Path $PSScriptRoot "Program.cs")
)

& $csc -nologo -optimize+ -platform:x64 -warn:2 `
    -r:"$bin\Assembly-CSharp.dll" -r:"$bin\UnityEngine.dll" -r:"$bin\UnityEngine.CoreModule.dll" `
    -out:"$bin\KspOracle.exe" $sources
if ($LASTEXITCODE -ne 0) { throw "compile failed" }

Write-Host "built $bin\KspOracle.exe"
& "$bin\KspOracle.exe" --selftest
if ($LASTEXITCODE -ne 0) { throw "selftest failed" }
