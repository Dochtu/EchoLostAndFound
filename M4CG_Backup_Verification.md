# 独立备份与恢复验证

本地备份目录为 **F:/EchoLostAndFound-Baselines/M4CG-20261124/**。2026-11-24 实际解包 1,859 个文件并逐个核对 SHA-256，另从 bundle 克隆分支并运行 git fsck --full。两条恢复路径均通过。[验证记录](M4CG/backup-verification.json)

| 对象 | 结果 |
| --- | --- |
| 源文件与产物 ZIP | M4C-project.zip，386,470,279 字节，SHA-256 `1ba8164873a779c1a1c1ab9726d92363138e32d17da16b96c3a4224761021aca` |
| Git 历史包 | M4C-history.bundle，SHA-256 `0a12d2f707092fdfd051d162ce540d9953a498b8b62978f58091f38f9899a241` |
| 本地保护分支 | `codex/m4c-g-baseline-20261124` |
| 提交 / 父提交 | `fdd2ffdcf4283f22e7bdf68662bb082b4d23d55d` / `4c51712c362e18bfcf9215cea766e61731773c74` |
| Git 树 | `202f4544a28a9cd4398c2cd8caa55b7682bca811`，1,618 个路径 |
| 文件覆盖 | 根 HDRP 与独立 URP 的 Assets、.meta、Packages 和 ProjectSettings，Server/app 与 tests、Deploy、Docs/StoryBible.md、Docs/GDD.md、Docs/Sources/HistoricalStory/truth_timeline.md、测试材料及 WebGL 产物 |
| 构建核对 | 17 个发布文件均与 M4-C 交付的 build-verification.json 对应 SHA-256 相同；本轮硬件试跑使用解包产物 |

[ZIP 备份](F:/EchoLostAndFound-Baselines/M4CG-20261124/M4C-project.zip) · [Git bundle](F:/EchoLostAndFound-Baselines/M4CG-20261124/M4C-history.bundle) · [逐文件 SHA-256](F:/EchoLostAndFound-Baselines/M4CG-20261124/sha256.json)

提交在独立副本内按路径清单生成，本机从 bundle 新建本地分支引用。基线建成后、编写本轮报告前，原工作区的 git status --porcelain 与操作前逐字节相同。原仓库未切换分支，暂存区未被使用。

## 回滚和恢复

1. 要取回完整文件和已验收的播放器，在新空目录解压 M4C-project.zip，按 sha256.json 的相对路径核对文件。verified-source 已实际完成此验证。ZIP 保存原工作区字节，包括原有换行。
2. 要从版本历史继续，在一个不存在的目标路径运行下列命令。核对 HEAD 为上表提交后，在该副本内工作。verified-git 已实际完成同样的克隆和完整性检查。

```powershell
git clone -b codex/m4c-g-baseline-20261124 F:/EchoLostAndFound-Baselines/M4CG-20261124/M4C-history.bundle F:/M4CG-restored
git -C F:/M4CG-restored rev-parse HEAD
git -C F:/M4CG-restored fsck --full
```

Git 恢复树干净，逐文件对比中 1,077 个文件只出现 Git 检出换行差异，其他文件字节相同。需要字节级复原时使用 ZIP。两套工程使用 Unity 6000.3.29f1，恢复后的新工作副本首次打开时需要重新导入缓存。
