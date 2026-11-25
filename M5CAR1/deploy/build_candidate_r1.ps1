# Assemble an M5-C-A-R1 deployment candidate WITHOUT deleting anything.
#
# Audit finding (M5CA/deploy/build_candidate.ps1, lines 17-21): it does
#     if (Test-Path $target) { Remove-Item -Recurse -Force $target }
# against one fixed path (Builds\M5CA\candidate).  Re-running it destroys a
# previously accepted release candidate, and the "$resolved -ne $target" guard
# only compares strings (case/separator sensitive, no reparse-point check).
#
# This script never removes an existing directory. It writes to a new
# timestamped directory and refuses if that path already exists.

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$server = Join-Path $repo "Server"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $repo "Builds\M5CAR1\candidate-$stamp"

function Assert-UnderRepo([string] $path) {
    $full = [System.IO.Path]::GetFullPath($path)
    $root = [System.IO.Path]::GetFullPath($repo)
    if (-not $full.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "refusing to touch a path outside the repository: $full"
    }
    if (Test-Path $path) {
        $item = Get-Item -LiteralPath $path -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "refusing to write through a reparse point: $full"
        }
    }
    return $full
}

Assert-UnderRepo $target | Out-Null
if (Test-Path $target) {
    throw "target already exists, refusing to overwrite: $target"
}
if (-not (Test-Path (Join-Path $server "app\entry.py"))) {
    throw "Server app not found under $server"
}

New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item -Recurse (Join-Path $server "app") (Join-Path $target "app")
foreach ($name in @("requirements.txt", "Dockerfile", "Dockerfile.modelscope", "docker-compose.yml", ".env.example", "DEPLOYMENT.md", "README.md", "API_CONTRACT.md")) {
    $source = Join-Path $server $name
    if (-not (Test-Path $source)) { throw "missing deployment input: $source" }
    Copy-Item $source (Join-Path $target $name)
}
Copy-Item (Join-Path $repo "M5CAR1\deploy\DEPLOY_R1.md") (Join-Path $target "DEPLOY_R1.md")

# Strip caches from the copy only; nothing outside $target is touched.
Get-ChildItem -Path $target -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path $target -Recurse -File -Include "*.pyc", "*.pyo" | Remove-Item -Force
Get-ChildItem -Path $target -Recurse -File -Include "*.sqlite3", "*.sqlite", "*.db" | Remove-Item -Force

$hashes = Get-ChildItem -Path $target -Recurse -File | Sort-Object FullName | Get-FileHash -Algorithm SHA256
$manifest = foreach ($entry in $hashes) {
    "{0}  {1}" -f $entry.Hash.ToLowerInvariant(), $entry.Path.Substring($target.Length + 1).Replace('\', '/')
}
$manifest | Set-Content -Encoding UTF8 (Join-Path $target "MANIFEST.txt")

Write-Host "candidate assembled: $target"
Write-Host ("files: {0}" -f $hashes.Count)
