[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$UnityPath,
    [string]$ProjectPath = $PSScriptRoot,
    [Parameter(Mandatory)][string]$OutputDir,
    [ValidateSet('brotli','gzip','disabled')][string]$Compression = 'gzip'
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
$output = [IO.Path]::GetFullPath($OutputDir)
$module = Join-Path (Split-Path $UnityPath) 'Data/PlaybackEngines/WebGLSupport/WebGLPlayerBuildProgram.exe'
if (!(Test-Path -LiteralPath $module)) { throw "Missing Web build support at $module" }
if (!(Test-Path -LiteralPath "$project/Assets/_Project/Editor/WebGLBuildEntry.cs")) { throw 'Select the M3-A WebGL project.' }
if (Test-Path -LiteralPath $output) { throw 'Choose a new output directory for each build.' }
$free = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($project)).AvailableFreeSpace
if ($free -lt 20GB) { throw 'Copy Assets, Packages and ProjectSettings to a volume with at least 20 GiB free and select it with -ProjectPath.' }
$buildLog = "$output.build.log"
if (Test-Path -LiteralPath $buildLog) { throw "Log already exists: $buildLog" }
[IO.Directory]::CreateDirectory((Split-Path -Parent $output)) | Out-Null
$env:DSH_WEBGL_COMPRESSION = $Compression
$env:DSH_WEBGL_OUTPUT = $output
$proc = Start-Process $UnityPath -WindowStyle Hidden -ArgumentList @(
    '-batchmode','-quit','-nographics','-projectPath',('"{0}"' -f $project),
    '-buildTarget','WebGL','-executeMethod','EchoLostAndFound.Build.WebGLBuildEntry.Build',
    '-logFile',('"{0}"' -f $buildLog)
) -Wait -PassThru
if ($proc.ExitCode -ne 0 -or !(Test-Path -LiteralPath "$output/index.html")) { throw "Build failed. See $buildLog" }
Write-Output $output
