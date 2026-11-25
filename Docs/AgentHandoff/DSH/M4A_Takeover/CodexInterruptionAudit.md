# M4-A Codex 中断审计

- 记录时间：2026-11-23 19:30 (+08:00)
- 接管方：DSH（lead）
- 被接管方：Codex（M4-A Unity 集成轮次）
- 工程：`EchoLostAndFound_WebGL`（独立 WebGL 工程，位于 `G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL`）
- 基线提交：`4c51712 Baseline HDRP, M3-A WebGL and M3-B before M4-A integration`

## 一、中断点判定

Codex 因五小时额度耗尽在执行 M4-A 途中中断。中断点是**写完源码与测试、尚未在 Unity 内编译**的状态。

| 时间（本地） | 事件 | 判定依据 |
| --- | --- | --- |
| 18:35:20 | M3-A 交付构建 `Builds/M3A-Station` 产出 | 构建目录 + `Docs/AgentHandoff/Codex/M3A-Delivery.md` |
| 18:47:58 | M3-B 四个 asmdef 写入 WebGL 工程 | 文件创建时间 |
| 18:48:52 | 在副本 `F:\EchoBuilds\M4A-Integration` 跑导入预检 | `M4A-QA/Logs/preflight.log` 首行时间戳 10:48:52Z |
| 18:49:00–18:49:25 | 生成 .meta、拷贝 M3-B 源码与内容 JSON | 文件创建时间 |
| 18:50:01 | M3-B 逻辑层控制台测试 29/29 通过（csc + 控制台 harness，**不经 Unity**） | `M4A-QA/Logs/logic-results.txt`、`logic-build.log` |
| 18:50:04 | `StationHud.cs`（8,676 B）、`StationInvestigation.cs`（2,962 B）写入 | 文件创建时间 |
| 18:50:20 | `Assets/Tests/PlayMode/M4AStationPlayTests.cs` 写入 | 文件创建时间 |
| 之后 | 无任何后续写入；无 Unity 编译日志、无测试结果、无 M4-A 构建 | 见下 |

**关键证据**：`F:\EchoBuilds\M4A-Integration`（预检所用副本）的 `Assets/Station/StationHud.cs` 仍是 18:23 的旧版 1,441 B，且没有 `StationInvestigation.cs`，`Assets/Tests/Editor` 下只有 M3-A 的 `StationAcceptanceTests.cs`。该副本创建于 18:47–18:49、预检运行于 18:48:52，均早于 M4-A 源码写入（18:50:04）。

结论：**M4-A 的 C# 源码从未被 Unity 编译过**，M4-A 的 EditMode/PlayMode/WebGL 构建从未执行。

## 二、中断时工作区实际状态

- Git 单一提交，所有 M4-A 工作均为未暂存修改 / 未跟踪文件。
- 未暂存修改（3 个）：
  - `EchoLostAndFound_WebGL/Assets/Station/Station.Runtime.asmdef`（+4 个 M3-B 程序集引用）
  - `EchoLostAndFound_WebGL/Assets/Station/StationHud.cs`（旧版 → Codex 版，197 行差异）
  - `EchoLostAndFound_WebGL/Assets/Tests/Editor/M3A.EditMode.asmdef`（+M3-B 引用）
- 未跟踪新增：`Assets/Station/StationInvestigation.cs`、`Assets/Tests/Editor/M4AInvestigationTests.cs(.meta)`、`Assets/Tests/PlayMode/`（含 `M4A.PlayMode.asmdef`）、`Assets/_Project/Scripts/`（M3-B 源码四模块）、`Assets/_Project/Resources/M3B/`（三份内容 JSON）、`M4A-QA/`（逻辑测试日志与脚本）、`M3B/`、`M4B/`、`Server/`（M4-B 其他 Agent）等。
- 另有无干改动 `Server/requirements.txt`（M4-B Agent，非 Codex 的 M4-A 范围，本接管未触碰）。

## 三、Codex 遗留缺陷（接管时已确认）

1. **编译错误（阻断级）**：`Assets/Tests/PlayMode/M4A.PlayMode.asmdef` 同时写 `references: ["UnityEngine.TestRunner", ...]` 与 `optionalUnityReferences: ["TestAssemblies"]`，Unity 报
   `Assembly has duplicate references: UnityEngine.TestRunner`，整个工程 `Scripts have compiler errors.`，任何测试/构建都无法进行。
2. **HUD 交互缺陷**：面板打开后 `StationPlayer` 只清 `ActiveTarget` 不调 `hud.ClosePanel()`，面板留屏但指针仍锁定，鼠标无法点击选项，逻辑上“进得去出不来”。
3. **出示按钮文案与测试不匹配**：HUD 生成 “出示 ”+Title，而 Codex 自己的 PlayMode 测试按 `FindButton("E02")` 查找，找不到。
4. **中文 TMP 字体缺失**：`Resources.Load<Font>("M4A/StationChinese")` 指向的文件在工程中不存在，中文 UI 必然缺字。
5. **无 E02 现场来源**：M3-B 内容中 D01（老周反馈变化）要求 E02，场景里却只有怀表与 NPC，浏览器端无法演示“证据改变 NPC 回应”。
6. **未验证即视为完成**：交接文档中未声称 M4-A 通过，但源码已落盘、无对应测试记录，存在“源码存在 = 功能可用”的误判风险。

上述 1–5 均由 DSH 在本轮修复，详见 `M4A_CompletionMatrix.md` 与 `M4A_Takeover_Report.md`。

## 四、未受影响的部分

- 原始 HDRP 工程（仓库根 `Assets/`、`Packages/`、`ProjectSettings/`）零改动：`git status --porcelain -- Assets Packages ProjectSettings` 输出为空。
- 打开 HDRP 工程的 Unity 编辑器进程（PID 8272）全程未被本接管操作触碰；所有 batchmode 编译、测试、构建均在 `F:` 盘副本执行。
- `Server/`（M4-B 其他 Agent 正在开发）未被修改或删除。
- M3-A 已交付构建 `Builds/M3A-Station` 原样保留，未覆盖。
