# DSH_Project_Audit.md · Task 1 审计总报告（索引与结论）

**任务**：Task 1 — 现有工程审计（Unity 版本、Packages、场景、资源、核心脚本、WebGL 兼容性）
**审计人**：DSH　**日期**：2026-11-23　**范围**：只读核查，未修改任何 `Assets/`、`ProjectSettings/`、`Packages/` 文件
**详细版**：`Docs/AgentHandoff/DSH/ProjectAudit.md`（工程事实与 P-01…P-15 问题清单）、`Docs/AgentHandoff/DSH/WebGLCompatibility.md`（WebGL 兼容性与 W-01…W-14）、`Docs/AgentHandoff/DSH/DSH_WebGL_Risk_Report.md`（风险登记册）

---

## 1. 一句话结论

工程是一个**能跑、能测、能出 Windows 包**的 M0–M2 垂直切片：Unity `6000.3.29f1` + HDRP `17.3.0` + Input System 1.20.1，场景 `Assets/_Project/Scenes/Station.unity` 已有第一人称移动与 4 个交互点；但它**没有任何对话、证据、章节、存档、AI 或后端代码**，**渲染管线决定了它不能产出 WebGL 包**，且**没有 Git 基线**。目标"浏览器可玩的 3D AI 调查推理游戏"当前完成度约为**玩法骨架 25%、AI 0%、WebGL 0%、内容数据 0%**。

---

## 2. 核心事实快照（每条都有实际文件路径）

| 维度 | 事实 | 证据路径 |
| --- | --- | --- |
| Unity 版本 | `6000.3.29f1`（`96d2fe17529c`） | `ProjectSettings/ProjectVersion.txt` |
| 渲染管线 | HDRP `17.3.0`，`GraphicsSettings.m_CustomRenderPipeline` guid `b9f3086da92434da0bc1518f19f0ce86` | `ProjectSettings/GraphicsSettings.asset`、`Assets/Settings/HDRP Balanced|High Fidelity|Performant.asset` |
| 画质档 | 3 档，当前 High Fidelity；`supportSSGI 1`、`supportSSAO 1`、`supportRayTracing 0` | `Assets/Settings/HDRP High Fidelity.asset` |
| 色彩/输入 | Linear；`activeInputHandler: 1`（仅新 Input System） | `ProjectSettings/ProjectSettings.asset` |
| 打包场景 | 2 个：`Station.unity`（正式）+ `OutdoorsScene.unity`（模板，0 MeshRenderer） | `ProjectSettings/EditorBuildSettings.asset` |
| 场景规模 | `Station.unity` 1,357,967 B / 185 GameObject / 60 MeshRenderer / 36 Light / 3 ReflectionProbe / 45 MonoBehaviour | `Assets/_Project/Scenes/Station.unity` |
| 运行时脚本 | **仅 3 个**：`M2Player.cs`、`M2Interactable.cs`、`M2InteractionHud.cs` | `Assets/_Project/Scripts/M2/` |
| 交互点 | **4 个**：站内旅客(Npc)、登记册(Item)、柜台(Counter)、怀表(Item) | 同上（guid `d6abc9d4e2fb4833be87af358139a532`） |
| 测试 | 2 个 EditMode + 5 个 PlayMode 用例（本轮**未运行**） | `Assets/_Project/Tests/M2/` |
| 服务端 | **空壳**（`.gitkeep` + 一行注释 `# Python dependencies will be added when the server is implemented.`） | `Server/` |
| 内容数据 | `Data/{Chapters,Evidence,NPCs}` 全空 | `Assets/_Project/Data/` |
| 资产体量 | `Assets/` 188.3 MB / 743 文件；单文件最大 `SourceHanSansSC-Regular.otf` 15.76 MB | `Assets/` |
| Windows 产物 | 4 个，M2 = 438.9 MB（`sharedassets0.assets.resS` 160.64 MB） | `Builds/` |
| WebGL 产物 | **0 个** | `Builds/` 无 WebGL 目录 |
| Git | branch `master`，**0 提交**，全部未跟踪；`.gitattributes` 不存在，LFS 无配置 | `git status` / `.git` |

---

## 3. 问题清单（按严重度，详情见 ProjectAudit.md）

| 级别 | ID | 问题 | 影响 |
| --- | --- | --- | --- |
| S1 | P-01 | 无 Git 基线提交、无 LFS 规则，两个 49/209 MB zip 与 166.9 MB 资产裸放在工作区 | 任何回滚/协作都无安全网 |
| S1 | P-02 | HDRP 不支持 WebGL/WebGPU（Unity 6.3 平台矩阵） | **首要目标"浏览器可玩"被硬阻断** |
| S2 | P-03 | 模板场景 `OutdoorsScene.unity` 在构建列表内 | 包内多余场景，体积与加载列表污染 |
| S2 | P-04 | `Assets/_Recovery/0.unity`（1.06 MB）留在工程内 | 误用/误打包风险 |
| S2 | P-05 | 运行时仅 3 个脚本，无对话/证据/章节/存档 | 距"完整交互"差 M3–M8 |
| S2 | P-06 | 服务端零实现（无 FastAPI/SQLite/LLM） | 无 AI、无存档 |
| S2 | P-07 | HUD 是 IMGUI + 硬编码中文字符串（NPC 仅"对话位置已就绪。"） | 无法承载 15 类 UI |
| S2 | P-08 | 166.9 MB 资产、13 张 4–10 MB Mask/Normal、字体 15.76 MB | 浏览器首包不可行 |
| S3 | P-09 | `InteractionKind {Counter,Item,Npc}` 三值不足以表达内容 ID/证据/对话 | M3/M4 必须改数据模型 |
| S3 | P-10 | Unity 编辑器占用工程（PID 8272） | 无法并行批处理构建 |
| S3 | P-11 | 文档称 409 对象，实测 185 GameObject | 性能/体积口径不一致 |
| S3 | P-12 | 根目录游离 `profile`（25 B，内容 `Library/R1Baseline/action`） | 仓库噪声 |
| S3 | P-13 | `Builds/` 无产物命名/清单约定 | 无法追溯哪个包对应哪次提交 |
| S3 | P-14 | 磁盘剩余 15.1 GB | WebGL/IL2CPP 中间产物可能写满 |
| S3 | P-15 | 无 `Assets/WebGLTemplates`、无构建入口脚本 | 构建需先补 |

---

## 4. 已执行的验证（可复现）

1. 读取 `ProjectVersion.txt`、`manifest.json`、`packages-lock.json`、`GraphicsSettings.asset`、`QualitySettings.asset`、`ProjectSettings.asset`、`EditorBuildSettings.asset`、`EditorSettings.asset`、`VersionControlSettings.asset`。
2. 枚举 `Assets/` 全部 743 个文件与 30 个 `.cs`，逐个读取 3 个运行时脚本全文与 2 个测试文件用例名。
3. 解析 `Station.unity`（185 GameObject / 332 Transform / 4 个 `M2Interactable` / 24 种 Prefab 实例）与 `StationNight.asset` 的 7 个 Volume 组件 guid。
4. 统计 HDRP 包缓存：**148 个 `.compute`**、`UNITY_WEBGL` 命中 **0**、`SHADER_API_GLES3` 命中 **0**。
5. 统计 `Builds/` 4 个 Windows 产物体积与 `Builds/M2/Station_Data` 头部大文件。
6. 核对 `Server/`（3 文件，全空壳）与 `Tools/M1_5/`（19 个几何生成脚本，非游戏逻辑）。
7. 运行 `Tools/Build/Invoke-WebGLBuild.ps1` 预检：3 FAIL（编辑器占用 / HDRP / 磁盘）+ 5 WARN，退出码 2。
8. `git status` / `git log` / `git lfs env`：0 提交、无 LFS。

## 5. 未验证事项

| 项 | 原因 |
| --- | --- |
| M2 的 7 个测试当前是否通过 | 未运行 Unity（编辑器被占用），无本轮日志 |
| 409 vs 185 对象口径 | 需在编辑器内用 `Stage4StationSceneBuilder`/`StationAudit` 复核 |
| Prefab 内部层级（怀表五部位、NPC Avatar/Animator） | 未在编辑器打开 |
| 本机显存/驱动对 URP WebGL 的实际表现 | 无 URP 工程，无法测 |
| WebGL 真实首包体积 | 无产物，40 MB 是预算目标不是实测 |

## 6. 哪些 DSH 能独立完成 / 哪些必须 Codex

**DSH 可独立完成（不碰 `Assets/`）**
1. 纯逻辑层与 DTO（证据状态机、9 类命令校验、幂等键），以独立 asmdef/`.cs.txt` 交付；
2. `Docs/DataSchema.md` 契约的自测与 JSON Schema 校验；
3. `Server/` 的契约测试、Mock Provider、CI 脚本；
4. 构建/打包/体积分析脚本与报告（已完成初版，已实跑预检）；
5. 全部审计、风险评估与交接文档（已完成）。

**必须 Codex（工程内写入或架构决策）**
1. `Assets/` 内任何脚本/场景/Prefab/材质/`.meta` 的落位；
2. 构建列表清理、`WebGLBuildEntry.cs` 落位、URP 浏览器工程创建；
3. 场景、UI 框架、材质迁移、Volume 重建；
4. `ProjectSettings/` 与 `Packages/` 的授权变更；
5. Git 基线与 LFS 规则（需 Director/用户批准后执行）。

## 7. 下一步任务

1. 用户裁决浏览器路线（独立 URP 工程 / 非 Unity 网页端）；
2. Codex 按 `HandoffToCodex.md` §2 回填 D-01…D-06 与 Q-01…Q-07；
3. 关闭占用编辑器、清理 4 个旧 `Builds/`（1.7 GB）、建立 Git 基线；
4. DSH 在其后提供：逻辑层代码 + 契约测试 + 首包预算实测。
