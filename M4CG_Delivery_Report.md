# M4-C-G 工程基线保护与运行质量核查

**2026-11-24 已完成基线保护与本地恢复演练，等待技术负责人验收。** 本地分支 `codex/m4c-g-baseline-20261124`，实际提交 `fdd2ffdcf4283f22e7bdf68662bb082b4d23d55d`。原工作区仍在 master 的 `4c51712`，暂存区为空，未推送远程。

| 交付项 | 结果 |
| --- | --- |
| Git 与资产盘点 | 起始 24 个已跟踪文件修改、872 个未跟踪文件。442 个未跟踪文件进入基线、165 个仅进入备份、265 个留在原处。基线保存全部 24 个原有修改。 |
| 本地备份 | F:/EchoLostAndFound-Baselines/M4CG-20261124/。ZIP 逐文件恢复验证 1,859/1,859；含两套 Unity 工程、后端、剧情资料和交付用 WebGL 包。Git bundle 在新目录克隆并通过 fsck，恢复树共 1,618 个文件。 |
| 可玩性与画面 | 恢复的 WebGL 包在真实 RTX 4060 Laptop GPU 上完成装袋、回退、改选暂交和刷新后重开回执。JS 异常 0，软失败 0，HTTP ≥400 为 0。 |
| 性能与告警 | 同一开局视点约 10 秒，硬件 60.10 FPS、SwiftShader 11.12 FPS。两端均出现三项 Hidden Shader 提示。Cookie 回退仅见于软件对照。两端保存时都有同步弃用提示。 |
| 未完成 | Windows 中文 IME 候选、确认上屏、发送和退出的原生链路为 UNVERIFIED。HDRP 原样批处理问题继续登记。 |

**回滚方法。** 要获得精确文件字节和发布包，将 M4C-project.zip 解压到新空目录并验证 sha256.json。要恢复可继续开发的 Git 副本，从同目录 M4C-history.bundle 克隆指定分支，核对上述提交。两条方法均已在新目录实际执行。[恢复命令及校验值](M4CG_Backup_Verification.md)

**核查范围。** 本轮只增加工程保护及 QA 证据。游戏逻辑、剧情真相、证据及保管规则、Unity 版本和渲染配置均沿用已验收版本。运行测试使用本机 Mock；M4-D 未启动。

[Git 分类清单](M4CG_Git_Inventory.md) · [运行质量与截图](M4CG_Runtime_Quality_Report.md) · [剩余风险](M4CG_Remaining_Risks.md) · [硬件 Chrome 刷新后回执](M4CG/gpu-chapter/08-persisted-settlement.png)
