# Assemble the M5-C-A independent deployment candidate.
# Source stays in Server/; this script copies a frozen snapshot into
# Builds/M5CA/candidate so Docker builds never depend on the dirty worktree.
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$server = Join-Path $repo "Server"
$target = Join-Path $repo "Builds\M5CA\candidate"

if (-not (Test-Path (Join-Path $repo "M5CA\deploy\Dockerfile"))) {
    throw "M5CA deploy sources not found under $repo"
}
if (-not (Test-Path (Join-Path $server "app\entry.py"))) {
    throw "Server app not found under $server"
}

if (Test-Path $target) {
    $resolved = (Resolve-Path $target).Path
    if ($resolved -ne $target) { throw "unexpected target resolution: $resolved" }
    Remove-Item -Recurse -Force $target
}
New-Item -ItemType Directory -Force -Path $target | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $target "fake_llm") | Out-Null

Copy-Item -Recurse -Force (Join-Path $server "app") (Join-Path $target "app")
Copy-Item -Force (Join-Path $server "requirements.txt") (Join-Path $target "requirements.txt")
Copy-Item -Force (Join-Path $repo "M5CA\deploy\Dockerfile") (Join-Path $target "Dockerfile")
Copy-Item -Force (Join-Path $repo "M5CA\deploy\docker-compose.mock.yml") $target
Copy-Item -Force (Join-Path $repo "M5CA\deploy\docker-compose.live.yml") $target
Copy-Item -Force (Join-Path $repo "M5CA\deploy\docker-compose.tight.yml") $target
Copy-Item -Force (Join-Path $server "tools\fake_llm_server.py") (Join-Path $target "fake_llm\fake_llm_server.py")
Copy-Item -Recurse -Force (Join-Path $repo "M5CA\e2e") (Join-Path $target "e2e")
New-Item -ItemType Directory -Force -Path (Join-Path $target "evidence") | Out-Null

# Strip caches from the copied snapshot.
Get-ChildItem -Path $target -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $target -Recurse -File -Include "*.pyc", "*.pyo" |
    Remove-Item -Force -ErrorAction SilentlyContinue

$hash = Get-ChildItem -Path $target -Recurse -File |
    Sort-Object FullName |
    Get-FileHash -Algorithm SHA256
$manifest = foreach ($entry in $hash) {
    "{0}  {1}" -f $entry.Hash.ToLowerInvariant(), $entry.Path.Substring($target.Length + 1).Replace('\', '/')
}
$manifest | Set-Content -Encoding UTF8 (Join-Path $target "MANIFEST.txt")

Write-Host "candidate assembled: $target"
Write-Host ("files: {0}" -f $hash.Count)
