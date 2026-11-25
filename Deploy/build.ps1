<#
.SYNOPSIS
  组装统一部署镜像的构建上下文：同一个容器里既放 WebGL 产物，也放 FastAPI 服务。

.DESCRIPTION
  镜像构建上下文必须自包含（Docker 不能从 Webl 工程外读取文件），所以这里先把
  仓库里的 Server 与 Unity 的 WebGL 构建产物复制到 Deploy/context，再让 Docker
  从该目录构建。context 目录属于中间产物，已列入 .gitignore，不进入版本库。

.PARAMETER WebBuild
  Unity WebGL 构建输出目录（必须包含 index.html 与 Build/）。

.PARAMETER Context
  构建上下文目录，默认 Deploy/context。

.PARAMETER Build
  组装完成后立即执行 docker build。若 Docker 引擎未启动会直接报错退出。

.EXAMPLE
  pwsh -File Deploy/build.ps1 -WebBuild F:\EchoBuilds\M4C-WebGL-03 -Build
#>
[CmdletBinding()]
param(
    [string]$WebBuild = 'F:\EchoBuilds\M4C-WebGL-03',
    [string]$Context = '',
    [string]$Tag = 'echolostfound-unified:local',
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 在 -File 模式下偶尔拿不到 $PSScriptRoot，这里逐级回退，
# 避免 Join-Path 收到空字符串而中断。
$scriptPath = $PSCommandPath
if (-not $scriptPath) { $scriptPath = $MyInvocation.MyCommand.Path }
if (-not $scriptPath) { $scriptPath = $MyInvocation.PSCommandPath }
if (-not $scriptPath) { throw '无法定位 build.ps1 路径，请显式传入 -Context 与 -WebBuild。' }
$here = Split-Path -Parent $scriptPath
if (-not $Context) { $Context = Join-Path $here 'context' }
$repo = Split-Path -Parent $here
$server = Join-Path $repo 'Server'

if (-not (Test-Path (Join-Path $WebBuild 'index.html'))) {
    throw "WebGL 构建目录缺少 index.html：$WebBuild"
}
if (-not (Test-Path (Join-Path $server 'app\main.py'))) {
    throw "Server 目录不完整（缺少 app\main.py）：$server"
}

if (Test-Path $Context) { Remove-Item -Recurse -Force $Context }
New-Item -ItemType Directory -Force -Path (Join-Path $Context 'server'), (Join-Path $Context 'webgl') | Out-Null

Copy-Item (Join-Path $server 'requirements.txt') (Join-Path $Context 'server\requirements.txt')
Copy-Item -Recurse (Join-Path $server 'app') (Join-Path $Context 'server\app')
Copy-Item -Recurse (Join-Path $WebBuild '*') (Join-Path $Context 'webgl')
Copy-Item (Join-Path $here 'Dockerfile') (Join-Path $Context 'Dockerfile')
Copy-Item (Join-Path $here '.dockerignore') (Join-Path $Context '.dockerignore')

$webBytes = (Get-ChildItem -Recurse -File (Join-Path $Context 'webgl') | Measure-Object -Property Length -Sum).Sum
$appBytes = (Get-ChildItem -Recurse -File (Join-Path $Context 'server') | Measure-Object -Property Length -Sum).Sum
"context=$Context"
"webgl_files=$((Get-ChildItem -Recurse -File (Join-Path $Context 'webgl')).Count) webgl_bytes=$webBytes"
"server_bytes=$appBytes"

if ($Build) {
    & docker build -t $Tag $Context
    if ($LASTEXITCODE -ne 0) { throw "docker build 失败，退出码 $LASTEXITCODE" }
    "image=$Tag"
}
