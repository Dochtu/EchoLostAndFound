# HandoffToCodex · DSH → Codex 交接单

**发出方**：DSH（审计 / 构建 / 文档 / 独立 C# 模块 / 服务端契约）
**接收方**：Codex（Unity 工程架构、渲染管线、核心场景、最终集成）
**日期**：2026-11-23　**基线**：`G:\projects\EchoLostAndFound` @ `6000.3.29f1` / HDRP `17.3.0`，Git 无提交
**一句话**：工程是 M0–M2 的可运行 Windows 切片（3 个运行时脚本、4 个交互点、1 个 IMGUI 面板），**零服务端、零对话、零证据、零存档**；浏览器路径被 HDRP 硬阻断，DSH 已完成审计与构建脚本，**没有执行任何 WebGL 构建**。

---

## 1. DSH 本轮交付物（已写入磁盘）

| 文件 | 内容 | 读者 |
| --- | --- | --- |
| `Docs/AgentHandoff/DSH/ProjectAudit.md` | Task1 工程审计：版本/包/场景/脚本/构建/服务端事实表，P-01…P-15 | Codex + Director |
| `Docs/AgentHandoff/DSH/WebGLCompatibility.md` | Task1 WebGL 兼容性：平台矩阵、本地证据、设置逐项、包体预算、W-01…W-14 | Codex + Director |
| `Docs/AgentHandoff/DSH/GameplayModuleInventory.md` | Task2：M-01…M-12 模块表、两幅依赖图、A/B/C 可迁移性、M3–M8 差距 | Codex + 各 Engineer |
| `Docs/AgentHandoff/DSH/BuildAndDeploymentPlan.md` | Task3：三条路线、四步流水线、压缩/资源策略、魔搭部署、验收清单 | Codex + Director |
| `Docs/AgentHandoff/DSH/HandoffToCodex.md` | 本文件 | Codex |
| `Docs/AgentHandoff/DSH/DSH_Project_Audit.md` | Task1 指定命名的索引与结论 | Director |
| `Docs/AgentHandoff/DSH/DSH_WebGL_Risk_Report.md` | Task1 指定命名的风险登记册 | Director |
| `Tools/Build/Invoke-WebGLBuild.ps1` | 预检/构建/打包脚本（已实跑预检） | Codex |
| `Tools/Build/serve-webgl.mjs` | 带 `Content-Encoding` 的本地静态服务器（已实测） | 全体 |
| `Tools/Build/WebGLBuildEntry.cs.txt` | 构建入口 C# 片段（**待你落位**） | Codex |

未改动：`Assets/` 下**任何**文件、`ProjectSettings/`、`Packages/`、`Station.unity`、`Library/`。

---

## 2. 需要你做决定的事（先决策，再动手）

| # | 决策点 | 选项 | DSH 建议 | 阻塞谁 |
| --- | --- | --- | --- | --- |
| D-01 | 浏览器路线 | A 独立 URP 工程 / B 同工程双管线 / C 非 Unity 网页端 | **A**（主工程零风险，符合 Architecture §9.6） | 全部 WebGL 工作 |
| D-02 | 内容数据格式 | ScriptableObject / JSON / 混合 | **ScriptableObject 做编辑期源 + 运行时导 JSON**（浏览器版可直接吃 JSON） | M3/M4/M7 |
| D-03 | UI 框架 | uGUI / UI Toolkit | uGUI + TMP（团队与现有 TMP 资源最顺） | M3/M4 UI |
| D-04 | 是否加 Addressables | 加 / 不加 | 浏览器版**加**（分段加载）；Windows 版可不加 | 包体 |
| D-05 | 构建入口落位 | 你按 `WebGLBuildEntry.cs.txt` 放入 `Assets/_Project/Editor/` | 直接采用 | Task3 构建 |
| D-06 | `WebGLTemplates` 是否新建 | 新建中文加载页 / 用默认 | 建议新建（含 pointer lock 引导、中文进度条） | 体验 |

---

## 3. 请你在 Unity 侧完成的具体改动（DSH 不做）

### 3.1 立即可做（不依赖 D-01）

1. **清理构建污染**
   - `ProjectSettings/EditorBuildSettings.asset`：把 `Assets/OutdoorsScene.unity`（guid `8124e5870f4fd4c779e7a5f994e84ad1`，模板场景，0 个 MeshRenderer）从启用列表移除 → 消除构建内空白场景（P-03）。
   - `Assets/_Recovery/0.unity`（1,059,872 B）确认无人使用后移出版本管理或删除（P-04）。
2. **落位构建入口**：`Tools/Build/WebGLBuildEntry.cs.txt` → `Assets/_Project/Editor/WebGLBuildEntry.cs`（会自动生成 `.meta`，属你的写入范围）。
3. **`.gitattributes` 决策**：当前 `git lfs` 无配置、无基线提交。209 MB / 49 MB 两个交付 zip 与 166.9 MB `Assets/_Project` 是否入 LFS，需你与 Director 定（P-01）。**DSH 未执行任何 git add/commit**。

### 3.2 浏览器路线批准后（D-01 = A）

4. 新建 URP 工程，导入 §4 的"可搬迁资产"；不要复制 HDRP 场景/材质/Volume。
5. 按 `GameplayModuleInventory.md` §4 做管线解耦：新逻辑放独立 asmdef（如 `EchoLostAndFound.Core`），**不引用** `UnityEngine.Rendering.HighDefinition`。
6. 输入补齐：`InputSystem_Actions.inputactions` 无触摸绑定；若需移动浏览器可玩，需新增 Touch 映射与屏上摇杆（属新功能）。

### 3.3 与 DSH 的接口约定（避免撞车）

| 边界 | DSH 写 | Codex 写 | 规则 |
| --- | --- | --- | --- |
| `Assets/**` | **不写** | 写 | DSH 需要新脚本时，以 `.cs.txt` 片段交付 |
| `Server/` | 契约、DTO、测试、Mock | 集成时改动需协调 | M5/M6 由 AI Engineer 主责 |
| `Tools/` | 写 | 只读 | 构建脚本归 DSH |
| `Docs/AgentHandoff/DSH/` | 写 | 只读 | 你的回复写 `Docs/AgentHandoff/Codex/` |
| `Station.unity` | 不碰 | 主责 | DSH 永不同时改同一场景 |

---

## 4. 可搬迁 / 需隔离 / 必须重写（摘自上表文档）

- **可直接带走**：`Assets/_Project/Scripts/M2/M2Interactable.cs`（改枚举后）、`Assets/InputSystem_Actions.inputactions`、`Assets/TextMesh Pro/Shaders/TMP_SDF-URP Lit.shadergraph`、25 个 FBX、`Docs/*` 内容文本、`Docs/DataSchema.md` 契约。
- **隔离后带走**：`M2Player.cs`（去 `HDAdditionalCameraData`）、贴图（降规格）、字体（子集化）、`Assets/_Project/Tests/` 纯逻辑部分。
- **必须重写**：`M2InteractionHud.cs`（IMGUI→TMP/uGUI）、`Station.unity`、25 个 Prefab、73 个 `.mat`、`Assets/Settings/HDRP *.asset`（3 档）、Volume 配置。
- **不可迁移**：HDRP Volume（`VisualEnvironment`/`GradientSky`/`Fog`/`Exposure`/`Tonemapping`）、实时反射探针方案、体积雾、SSGI。

---

## 5. 需要你确认的 7 个"我不知道"（DSH 未验证）

| # | 问题 | 为什么重要 |
| --- | --- | --- |
| Q-01 | `Docs/Stage4_M0_M1_ExecutionReport.md` 写"409 对象"，我数 `Station.unity` 是 **185 个 GameObject / 332 个 Transform**。哪个口径对？ | 影响性能预算与场景体积估算 |
| Q-02 | `PocketWatch.prefab`（157,915 B）是否已含 M3 需要的五部位子网格命名（表盘/背刻/编号/侧冠/冠轴）？ | 决定 M3 是"接线"还是"重做资产" |
| Q-03 | `StationVisitor.prefab` / `NPC_VisualSample.prefab` 的 Avatar、Animator 状态机是否可用？ | 决定 M4 人物工期 |
| Q-04 | `Docs/VerticalSlicePlan.md` 说 M4 要"15 类 UI"，具体是哪 15 类？ | 决定 M4 UI 拆分 |
| Q-05 | `Assets/_Project/Art/Textures/M1_5/*` 导入 2048 + 未 crunched，是否可降到 1024/512？ | 包体 166.9 MB 的主要来源 |
| Q-06 | `Assets/SourceHanSansSC-Regular.otf`（15.76 MB）许可允许子集化与嵌入 WebGL 包吗？ | 合规 + 包体 |
| Q-07 | `profile`（25 B，内容 `Library/R1Baseline/action`）是遗留文件吗？可删？ | 仓库整洁 |

---

## 6. 当前真实状态（请勿假设更好）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| Windows 构建 | 可构建（4 个历史产物，438.9 MB） | `Builds/M2/` |
| WebGL 构建 | **不可**（HDRP） | 预检 FAIL ×3 |
| 第一人称移动 + 射线交互 | 可用（有 7 个 PlayMode/EditMode 用例） | `Assets/_Project/Tests/M2/` |
| 对话 / 证据 / 章节 / 存档 | **不存在** | `Scripts/{Dialogue,Evidence,Investigation,Save}/` 仅 `.gitkeep` |
| 后端 / AI | **不存在** | `Server/` 仅 `.gitkeep` + 一行注释 |
| M2 测试是否仍绿 | **未运行**（编辑器占用） | 无本轮测试日志 |

---

## 7. 建议的下一步顺序

1. 你回填 §2 的 D-01…D-06 与 §5 的 Q-01…Q-07（写 `Docs/AgentHandoff/Codex/` 即可，DSH 会读）；
2. 我做 D-02/D-03 定下后的**纯逻辑层 + DTO + 单元测试**（不碰 `Assets/`，以 `.cs.txt` 交付或经你授权落位）；
3. 你做 §3.1 的三件事（清理构建污染、落位入口、LFS 决策）；
4. 用户批准 D-01 后，你建 URP 工程，我在其上跑通构建流水线并产出 `manifest.json`。
