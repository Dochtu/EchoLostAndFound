# M3-A 工程保护与恢复

本轮操作前根仓库为 master，HEAD 尚未创建，索引为空。首次完整枚举有 969 条未忽略的未跟踪路径。基线采用本地 ZIP，适用于尚无提交、DSH 同时工作的工作区。未运行 git add、commit、reset、clean 或 LFS track。

工作区内 M3A-Backups/HDRP-before-M3A.zip 收录快照枚举时的 999 个文件、全部 HDRP Assets（含 .meta）、Packages、ProjectSettings、既有 Docs、Tools、Server、角色配置、根文件和两份历史交付 ZIP。压缩包 585,565,119 字节，已从 ZIP 逐个解压读取并与源文件逐字节比对。SHA-256 为 e0d06898b741bedd9032c9478e7f16a222e147feb2f01d1864759e02031ff367。此为同盘源码恢复点。历史 Builds 与自动生成的 Library、Temp、Logs、UserSettings、.git 排除；原目录保留。后续并行产生的 DSH M3B 工作不属于这个时间点。

## 恢复到新目录

从仓库根目录运行 PowerShell，选择有足够空间的新目标。此流程保留活跃工作区和此后新增的 DSH 文件。

```powershell
$archive = (Resolve-Path 'M3A-Backups/HDRP-before-M3A.zip').Path
$expected = (Get-Content 'M3A-Backups/HDRP-before-M3A.sha256').Split(' ')[0]
if ((Get-FileHash $archive).Hash -ne $expected) { throw 'SHA-256 mismatch' }
$restore = 'F:\EchoBuilds\HDRP-Restore-' + (Get-Date -Format yyyyMMdd-HHmmss)
if (Test-Path $restore) { throw 'Choose a new directory' }
Expand-Archive -LiteralPath $archive -DestinationPath $restore
```

Unity Hub 打开恢复目录，使用 6000.3.29f1。包导入后可打开 Assets/_Project 下原场景。

## Git 与 LFS

原 .gitignore 已覆盖根项目的 Unity/Python 缓存、构建、环境变量和 IDE 输出。追加忽略本机快照并保留 M3-A 验证日志。独立项目自带根相对的 Unity 忽略规则。两套工程的 .meta、清单和设置均可纳入版本管理。Git LFS 3.7.1 已安装，git lfs ls-files 为空。历史交付 ZIP 分别为 209,186,401 与 49,432,802 字节，适合作为版本发布附件；需要源控时可单独批准 LFS 规则。大型贴图、模型及原始采集文件建议按实际路径审查，保留 Unity YAML 为普通文本。没有写入 .gitattributes。
