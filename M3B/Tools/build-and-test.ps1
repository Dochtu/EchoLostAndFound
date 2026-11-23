<#
.SYNOPSIS
    Builds and runs the EchoLostAndFound M3-B pure C# modules and their tests.

.DESCRIPTION
    The sandbox has no NuGet/MSBuild access and blocks the named pipes that MSBuild uses
    to spawn the compiler, so this script invokes the Roslyn compiler (csc.dll) directly
    with the installed targeting reference assemblies. No third-party dependency is used.
    Modules compile against the netstandard2.1 reference set (Unity-compatible surface);
    the console test runner compiles against the net10.0 reference set and loads the
    module assembly.

    Outputs:
      M3B/_artifacts/lib/EchoLostAndFound.M3B.dll
      M3B/_artifacts/tests/EchoLostAndFound.M3B.Tests.dll (+ runtimeconfig.json)
      M3B/Tests/RESULTS.txt (captured console output of the test run)
#>
$ErrorActionPreference = "Stop"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_NOLOGO = "1"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"

$root = Split-Path -Parent $PSScriptRoot
$csc = "C:\Program Files\dotnet\sdk\11.0.100\Roslyn\bincore\csc.dll"
$netstandardRefs = "C:\Program Files\dotnet\packs\NETStandard.Library.Ref\2.1.0\ref\netstandard2.1"
$net10Refs = "C:\Program Files\dotnet\packs\Microsoft.NETCore.App.Ref\10.0.15\ref\net10.0"

foreach ($required in @($csc, $netstandardRefs, $net10Refs)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required build input not found: $required"
    }
}

$artifacts = Join-Path $root "_artifacts"
$libDir = Join-Path $artifacts "lib"
$testDir = Join-Path $artifacts "tests"
New-Item -ItemType Directory -Force -Path $libDir, $testDir | Out-Null

# Source sets. Content/*.json is copied next to the DLLs so the tests can also be run
# from the artifacts directory.
$moduleSources = @(
    Get-ChildItem -LiteralPath (Join-Path $root "Shared") -Recurse -Filter *.cs
    Get-ChildItem -LiteralPath (Join-Path $root "EvidenceSystem") -Recurse -Filter *.cs
    Get-ChildItem -LiteralPath (Join-Path $root "DialogueSystem") -Recurse -Filter *.cs
    Get-ChildItem -LiteralPath (Join-Path $root "MockAIProvider") -Recurse -Filter *.cs
) | Where-Object { $_.FullName -notmatch "[\\/]_artifacts[\\/]" } | ForEach-Object { $_.FullName }

$testSources = @(
    Get-ChildItem -LiteralPath (Join-Path $root "Tests") -Recurse -Filter *.cs
) | Where-Object { $_.FullName -notmatch "[\\/]_artifacts[\\/]" } | ForEach-Object { $_.FullName }

if ($moduleSources.Count -eq 0) { throw "No module sources found." }
if ($testSources.Count -eq 0) { throw "No test sources found." }

$libDll = Join-Path $libDir "EchoLostAndFound.M3B.dll"
$testDll = Join-Path $testDir "EchoLostAndFound.M3B.Tests.dll"

Write-Host "== Compiling modules (netstandard2.1 surface) =="
Write-Host "Sources: $($moduleSources.Count)"
$refArgs = Get-ChildItem -LiteralPath $netstandardRefs -Filter *.dll | ForEach-Object { "-r:" + $_.FullName }
& dotnet $csc -nologo -target:library -langversion:9.0 -deterministic -optimize+ -out:$libDll @refArgs @moduleSources
if ($LASTEXITCODE -ne 0) { throw "Module compilation failed with exit code $LASTEXITCODE." }

Write-Host "== Compiling test runner (net10.0) =="
Write-Host "Sources: $($testSources.Count)"
$testRefArgs = Get-ChildItem -LiteralPath $net10Refs -Filter *.dll | ForEach-Object { "-r:" + $_.FullName }
$testRefArgs += "-r:" + $libDll
& dotnet $csc -nologo -target:exe -langversion:9.0 -deterministic -optimize+ -out:$testDll @testRefArgs @testSources
if ($LASTEXITCODE -ne 0) { throw "Test runner compilation failed with exit code $LASTEXITCODE." }

$runtimeConfig = @{
    runtimeOptions = @{
        tfm = "net10.0"
        framework = @{
            name = "Microsoft.NETCore.App"
            version = "10.0.15"
        }
    }
}
$runtimeConfigPath = Join-Path $testDir "EchoLostAndFound.M3B.Tests.runtimeconfig.json"
$runtimeConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $runtimeConfigPath -Encoding utf8
Copy-Item -LiteralPath $libDll -Destination $testDir -Force

Write-Host "== Running tests =="
$resultsFile = Join-Path $root "Tests\RESULTS.txt"
$header = @(
    "EchoLostAndFound M3-B test run",
    "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
    "Compiler: $csc",
    "Module TFM refs: $netstandardRefs",
    "Runner TFM refs: $net10Refs",
    "Content root: $root",
    ""
)
$header | Set-Content -LiteralPath $resultsFile -Encoding utf8
$output = & dotnet $testDll $root 2>&1
$exitCode = $LASTEXITCODE
$output | Add-Content -LiteralPath $resultsFile -Encoding utf8
$output | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Exit code: $exitCode"
Write-Host "Results:   $resultsFile"
exit $exitCode
