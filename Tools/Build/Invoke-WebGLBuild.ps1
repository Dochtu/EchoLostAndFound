#!/usr/bin/env pwsh
# EchoLostAndFound · Unity WebGL 构建/预检脚本
# 归属：DSH（构建与部署）。不修改 Assets/、ProjectSettings/、Packages/。
#
# 用法：
#   pwsh -NoProfile -File Tools/Build/Invoke-WebGLBuild.ps1                 # 只做预检
#   pwsh -NoProfile -File Tools/Build/Invoke-WebGLBuild.ps1 -Mode Build     # 预检通过后构建
#   pwsh -NoProfile -File Tools/Build/Invoke-WebGLBuild.ps1 -Mode Package   # 校验产物 + 生成 manifest + zip
#
# 前置（必须由 Codex/unity-engineer 提供，本脚本不自建）：
#   Assets/_Project/Editor/WebGLBuildEntry.cs   —— 见 Tools/Build/WebGLBuildEntry.cs.txt
#   该方法签名：public static void Build()，读取环境变量 DSH_WEBGL_OUTPUT / DSH_WEBGL_COMPRESSION

[CmdletBinding()]
param(
    [ValidateSet('Preflight', 'Build', 'Package')]
    [string]$Mode = 'Preflight',

    [string]$ProjectPath,

    [string]$UnityPath,

    [string]$ExecuteMethod = 'EchoLostAndFound.Build.WebGLBuildEntry.Build',

    [ValidateSet('brotli', 'gzip', 'disabled')]
    [string]$Compression = 'brotli',

    [string]$OutputDir,

    [int]$MinFreeSpaceGb = 20
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot 在参数默认值求值时尚未赋值，故在此处补算工程根目录。
if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$ProjectPath = [System.IO.Path]::GetFullPath($ProjectPath)

$script:Failures = @()
$script:Warnings = @()

function Write-Step([string]$Text) { Write-Host "`n=== $Text ===" -ForegroundColor Cyan }
function Add-Fail([string]$Text) { $script:Failures += $Text; Write-Host "  [FAIL] $Text" -ForegroundColor Red }
function Add-Warn([string]$Text) { $script:Warnings += $Text; Write-Host "  [WARN] $Text" -ForegroundColor Yellow }
function Add-Ok([string]$Text) { Write-Host "  [ OK ] $Text" -ForegroundColor Green }

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Find-AssetByGuid([string]$Guid) {
    $hit = Get-ChildItem -LiteralPath (Join-Path $ProjectPath 'Assets') -Recurse -Filter '*.meta' -File |
        Select-String -Pattern "guid: $Guid" -List -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $hit) { return $null }
    return ($hit.Path -replace '\.meta$', '')
}

# ---------------------------------------------------------------- 预检
Write-Step 'WebGL 构建预检'
Write-Host "工程：$ProjectPath"

if (-not (Test-Path -LiteralPath (Join-Path $ProjectPath 'Assets'))) { Add-Fail "缺少 Assets/：$ProjectPath" }
if (-not (Test-Path -LiteralPath (Join-Path $ProjectPath 'ProjectSettings\ProjectVersion.txt'))) { Add-Fail '缺少 ProjectSettings/ProjectVersion.txt' }

$versionFile = Join-Path $ProjectPath 'ProjectSettings\ProjectVersion.txt'
if (Test-Path -LiteralPath $versionFile) {
    $versionLine = (Get-Content -LiteralPath $versionFile -Encoding UTF8 | Where-Object { $_ -match '^m_EditorVersion:' })
    Add-Ok "Unity 版本记录：$versionLine"
}

# 1) Unity 可执行文件
if (-not $UnityPath) {
    $instance = Read-JsonFile (Join-Path $ProjectPath 'Library\EditorInstance.json')
    if ($instance -and $instance.app_path) { $UnityPath = $instance.app_path }
}
if ($UnityPath -and (Test-Path -LiteralPath $UnityPath)) {
    Add-Ok "Unity 可执行文件：$UnityPath"
} else {
    Add-Fail "找不到 Unity.exe（用 -UnityPath 指定）"
}

# 2) WebGL 构建模块
if ($UnityPath -and (Test-Path -LiteralPath $UnityPath)) {
    $editorData = Join-Path (Split-Path -Parent $UnityPath) 'Data'
    $webglModule = Join-Path $editorData 'PlaybackEngines\WebGLSupport'
    if (Test-Path -LiteralPath $webglModule) { Add-Ok "WebGL 模块已安装：$webglModule" }
    else { Add-Fail "缺少 WebGL 构建模块：$webglModule" }
}

# 3) 编辑器是否占用工程（同一工程不能并行打开）
$lockFile = Join-Path $ProjectPath 'Library\EditorInstance.json'
if (Test-Path -LiteralPath $lockFile) {
    $instance = Read-JsonFile $lockFile
    $editorPid = 0
    if ($instance -and $instance.process_id) { $editorPid = [int]$instance.process_id }
    $alive = if ($editorPid -gt 0) { Get-Process -Id $editorPid -ErrorAction SilentlyContinue } else { $null }
    if ($alive) {
        Add-Fail "工程被 Unity 编辑器占用（PID $editorPid）。批处理构建前必须关闭该编辑器实例。"
    } elseif ($instance) {
        Add-Warn "存在 $lockFile 但进程 $editorPid 已退出；Unity 可能自行清理，构建时留意锁文件。"
    }
}

# 4) 渲染管线：HDRP 不能构建 WebGL
$graphicsSettings = Join-Path $ProjectPath 'ProjectSettings\GraphicsSettings.asset'
if (Test-Path -LiteralPath $graphicsSettings) {
    $gsText = Get-Content -LiteralPath $graphicsSettings -Raw -Encoding UTF8
    $m = [regex]::Match($gsText, 'm_CustomRenderPipeline:\s*\{[^}]*guid:\s*([0-9a-f]{32})')
    if (-not $m.Success) {
        Add-Warn '未检测到自定义渲染管线（Built-in）：WebGL 可构建，但本工程目标管线是 HDRP，请确认。'
    } else {
        $rpGuid = $m.Groups[1].Value
        $rpAsset = Find-AssetByGuid $rpGuid
        $rpName = if ($rpAsset) { Split-Path -Leaf $rpAsset } else { '(未找到资产)' }
        $scriptGuid = ''
        if ($rpAsset -and (Test-Path -LiteralPath $rpAsset)) {
            $sm = [regex]::Match((Get-Content -LiteralPath $rpAsset -Raw -Encoding UTF8), 'm_Script:\s*\{fileID:\s*11500000,\s*guid:\s*([0-9a-f]{32})')
            if ($sm.Success) { $scriptGuid = $sm.Groups[1].Value }
        }
        $isHdrp = ($scriptGuid -eq '0cf1dab834d4ec34195b920ea7bbf9ec') -or ($rpName -match 'HDRP|HighDefinition|High Fidelity|Balanced|Performant')
        if ($isHdrp) {
            Add-Fail ("当前渲染管线是 HDRP（$rpName, guid $rpGuid）。HDRP 不支持 WebGL/WebGPU：本工程不能产出 WebGL 包。" +
                      ' 浏览器路径须另建 URP 工程/构建配置（见 Docs/AgentHandoff/DSH/WebGLCompatibility.md §8）。')
        } else {
            $isUrp = ($rpName -match 'URP|Universal')
            if ($isUrp) { Add-Ok "渲染管线：URP（$rpName）" } else { Add-Warn "渲染管线未识别：$rpName" }
        }
    }
}

# 5) URP 包是否安装（浏览器路径前提）
$manifestPath = Join-Path $ProjectPath 'Packages\manifest.json'
$manifest = Read-JsonFile $manifestPath
if ($manifest) {
    if ($manifest.dependencies.'com.unity.render-pipelines.universal') {
        Add-Ok ('URP 已安装：' + $manifest.dependencies.'com.unity.render-pipelines.universal')
    } else {
        Add-Warn '未安装 com.unity.render-pipelines.universal（浏览器路径需要，安装属 Packages 变更，须授权）。'
    }
    if ($manifest.dependencies.'com.unity.nuget.newtonsoft-json') {
        Add-Warn '检测到 Newtonsoft Json：WebGL 下 IL2CPP/AOT 需 link.xml 与实测。'
    }
}

# 6) WebGL Player 设置一致性
$playerSettings = Join-Path $ProjectPath 'ProjectSettings\ProjectSettings.asset'
if (Test-Path -LiteralPath $playerSettings) {
    $psText = Get-Content -LiteralPath $playerSettings -Raw -Encoding UTF8
    function Get-Setting([string]$Key) {
        $mm = [regex]::Match($psText, "(?m)^\s*${Key}:\s*(\S+)\s*$")
        if ($mm.Success) { return $mm.Groups[1].Value } else { return $null }
    }
    $fmt = Get-Setting 'webGLCompressionFormat'
    $fallback = Get-Setting 'webGLDecompressionFallback'
    $threads = Get-Setting 'webGLThreadsSupport'
    $analyze = Get-Setting 'webGLAnalyzeBuildSize'
    Add-Ok "webGLCompressionFormat=$fmt（0=Brotli,1=Gzip,2=Disabled），DecompressionFallback=$fallback，Threads=$threads"
    if ($fallback -eq '0' -and $fmt -ne '2') {
        Add-Warn '未开解压回退：托管服务器必须返回正确的 Content-Encoding（br/gz），否则页面加载失败。本地测试用 Tools/Build/serve-webgl.mjs。'
    }
    if ($analyze -eq '0') { Add-Warn 'webGLAnalyzeBuildSize 关闭：发布前建议开启一次做体积分析。' }
    if ($threads -eq '1') { Add-Warn '开启了多线程 WebGL：需要 COOP/COEP 响应头，iframe 嵌入会受影响。' }
}

# 7) WebGL 模板
if (Test-Path -LiteralPath (Join-Path $ProjectPath 'Assets\WebGLTemplates')) { Add-Ok '存在自定义 WebGL 模板' }
else { Add-Warn '没有 Assets/WebGLTemplates：将使用 Unity 默认模板（无中文加载提示/无 pointer lock 引导）。' }

# 8) 构建入口脚本
$entryFile = Get-ChildItem -LiteralPath (Join-Path $ProjectPath 'Assets') -Recurse -Filter '*.cs' -File -ErrorAction SilentlyContinue |
    Select-String -Pattern 'WebGLBuildEntry' -List | Select-Object -First 1
if ($entryFile) { Add-Ok "构建入口：$($entryFile.Path)" }
else { Add-Warn "未找到 $ExecuteMethod 的实现（需 Codex 依 Tools/Build/WebGLBuildEntry.cs.txt 添加）。-Mode Build 会失败。" }

# 9) 磁盘空间
$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($ProjectPath).TrimEnd(':', '\'))
if ($drive) {
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    if ($freeGb -lt $MinFreeSpaceGb) { Add-Fail "剩余空间 ${freeGb} GB < 门槛 $MinFreeSpaceGb GB（WebGL 中间产物 + IL2CPP 很占空间）" }
    else { Add-Ok "剩余空间 ${freeGb} GB（门槛 $MinFreeSpaceGb GB）" }
}

# 10) 输出目录不得位于 Assets/ 内
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectPath ("Builds\WebGL\" + (Get-Date -Format 'yyyyMMdd_HHmmss')) }
$resolvedOut = [System.IO.Path]::GetFullPath($OutputDir)
$assetsRoot = [System.IO.Path]::GetFullPath((Join-Path $ProjectPath 'Assets'))
if ($resolvedOut.StartsWith($assetsRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Add-Fail "输出目录不能位于 Assets/ 内：$resolvedOut"
} else {
    Add-Ok "输出目录：$resolvedOut"
}

# ---------------------------------------------------------------- 汇总
Write-Step '预检结果'
if ($script:Warnings.Count -gt 0) { Write-Host "警告 $($script:Warnings.Count) 条：" -ForegroundColor Yellow; $script:Warnings | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow } }
if ($script:Failures.Count -gt 0) {
    Write-Host "`n预检失败 $($script:Failures.Count) 项，未执行构建：" -ForegroundColor Red
    $script:Failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 2
}
Write-Host '预检通过。' -ForegroundColor Green

if ($Mode -eq 'Preflight') { exit 0 }

# ---------------------------------------------------------------- 构建
if ($Mode -eq 'Build') {
    Write-Step "WebGL 构建 → $resolvedOut"
    New-Item -ItemType Directory -Force -Path $resolvedOut | Out-Null
    $logFile = Join-Path $resolvedOut 'unity-webgl-build.log'
    $env:DSH_WEBGL_OUTPUT = $resolvedOut
    $env:DSH_WEBGL_COMPRESSION = $Compression
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $unityArgs = @(
        '-batchmode', '-quit', '-nographics',
        '-projectPath', "`"$ProjectPath`"",
        '-buildTarget', 'WebGL',
        '-executeMethod', $ExecuteMethod,
        '-logFile', "`"$logFile`""
    )
    Write-Host "执行：`"$UnityPath`" $($unityArgs -join ' ')"
    $proc = Start-Process -FilePath $UnityPath -ArgumentList $unityArgs -NoNewWindow -Wait -PassThru
    $sw.Stop()
    Remove-Item Env:\DSH_WEBGL_OUTPUT, Env:\DSH_WEBGL_COMPRESSION -ErrorAction SilentlyContinue
    Write-Host ("Unity 退出码：{0}，耗时 {1:N1} 分钟" -f $proc.ExitCode, ($sw.Elapsed.TotalMinutes))
    if ($proc.ExitCode -ne 0) {
        Write-Host "构建失败。日志：$logFile" -ForegroundColor Red
        if (Test-Path -LiteralPath $logFile) { Get-Content -LiteralPath $logFile -Tail 60 }
        exit 3
    }
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedOut 'index.html'))) {
        Write-Host "Unity 报告成功但缺少 index.html：$resolvedOut" -ForegroundColor Red
        exit 3
    }
}

# ---------------------------------------------------------------- 打包与清单
Write-Step '产物校验与清单'
if (-not (Test-Path -LiteralPath (Join-Path $resolvedOut 'index.html'))) {
    Write-Host "未找到 WebGL 产物：$resolvedOut" -ForegroundColor Red
    exit 4
}

$files = Get-ChildItem -LiteralPath $resolvedOut -Recurse -File | Where-Object { $_.Name -notin @('manifest.json', 'unity-webgl-build.log') }
$totalBytes = ($files | Measure-Object Length -Sum).Sum
$entries = foreach ($f in $files) {
    [pscustomobject]@{
        path   = $f.FullName.Substring($resolvedOut.Length).TrimStart('\').Replace('\', '/')
        bytes  = $f.Length
        sha256 = Get-FileSha256 $f.FullName
    }
}
$manifest = [pscustomobject]@{
    generatedAtUtc  = (Get-Date).ToUniversalTime().ToString('o')
    project         = 'EchoLostAndFound'
    mode            = $Mode
    compression     = $Compression
    outputDir       = $resolvedOut
    fileCount       = $entries.Count
    totalBytes      = $totalBytes
    totalMiB        = [math]::Round($totalBytes / 1MB, 2)
    files           = $entries
}
$manifestPath = Join-Path $resolvedOut 'manifest.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$requiredPatterns = @(
    @{ Name = 'index.html'; Pattern = 'index.html' },
    @{ Name = 'WASM 或 asm.js'; Pattern = '\.(wasm|asm)(\.br|\.gz|\.unityweb)?$' },
    @{ Name = '框架 js'; Pattern = '\.js(\.br|\.gz|\.unityweb)?$' },
    @{ Name = '数据包'; Pattern = '\.(data|bundle|unityweb)(\.br|\.gz)?$' }
)
foreach ($req in $requiredPatterns) {
    if ($entries | Where-Object { $_.path -match $req.Pattern }) { Add-Ok "包含 $($req.Name)" }
    else { Add-Warn "未找到 $($req.Name)（可能是命名差异，人工确认）" }
}
Add-Ok ("文件 {0} 个，合计 {1:N2} MiB" -f $entries.Count, ($totalBytes / 1MB))

$zipPath = Join-Path (Split-Path -Parent $resolvedOut) (Split-Path -Leaf $resolvedOut) + '.zip'
if (-not (Test-Path -LiteralPath $zipPath)) {
    Compress-Archive -Path (Join-Path $resolvedOut '*') -DestinationPath $zipPath -CompressionLevel Optimal
    Add-Ok ("已打包：{0}（{1:N2} MiB）" -f $zipPath, ((Get-Item -LiteralPath $zipPath).Length / 1MB))
}

Write-Host "`n完成。清单：$manifestPath" -ForegroundColor Green
Write-Host "本地浏览器测试：node Tools/Build/serve-webgl.mjs `"$resolvedOut`"" -ForegroundColor Gray
