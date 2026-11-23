# Docs/AgentHandoff/DSH

DSH 在 2026-11-23 交付的审计与构建方案。所有结论基于只读核查；**未修改 `Assets/`、`ProjectSettings/`、`Packages/`，未执行任何 Unity 构建**。

## 阅读顺序

| 顺序 | 文件 | 读者 | 内容 |
| --- | --- | --- | --- |
| 1 | [DSH_Project_Audit.md](DSH_Project_Audit.md) | Director | Task 1 总报告：一句话结论、事实快照、P-01…P-15、验证与分工 |
| 2 | [ProjectAudit.md](ProjectAudit.md) | Codex | Task 1 详细版：11 节取证、版本/包/场景/脚本/测试/构建事实表 |
| 3 | [DSH_WebGL_Risk_Report.md](DSH_WebGL_Risk_Report.md) | Director | 风险登记册：硬阻断 B-01…B-04、R-01…R-20、验收 6 条门槛 |
| 4 | [WebGLCompatibility.md](WebGLCompatibility.md) | Codex | WebGL 兼容性论证：平台矩阵、本地证据、W-01…W-14、路线 A/B |
| 5 | [GameplayModuleInventory.md](GameplayModuleInventory.md) | Codex + 各 Engineer | Task 2：M-01…M-12、两幅依赖图、A/B/C 可迁移性、M3–M8 差距 |
| 6 | [BuildAndDeploymentPlan.md](BuildAndDeploymentPlan.md) | Codex + 部署 | Task 3：四步流水线、压缩/资源策略、魔搭部署、10 项浏览器验收 |
| 7 | [HandoffToCodex.md](HandoffToCodex.md) | Codex | 交接单：D-01…D-06 决策、Q-01…Q-07 待确认、接口边界 |

## 配套脚本（`Tools/Build/`）

| 文件 | 状态 |
| --- | --- |
| `Invoke-WebGLBuild.ps1` | 已实跑预检（3 FAIL / 5 WARN / 退出码 2）；兼容 Windows PowerShell 5.1（UTF-8 BOM） |
| `serve-webgl.mjs` | 已实测：MIME、`Content-Encoding: br`、越界 404 |
| `WebGLBuildEntry.cs.txt` | 构建入口片段，**待 Codex 落位到 `Assets/_Project/Editor/`** |

## 底线

- 当前工程是 HDRP，**不能**产出 WebGL 包（B-01）。
- 浏览器可玩版本必须来自 URP 工程或非 Unity 网页端，需用户批准。
- 任何"WebGL 构建成功"的表述在本轮都不成立。
