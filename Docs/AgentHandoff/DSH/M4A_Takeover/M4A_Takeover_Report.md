# M4-A 接管报告

- 接管方：DSH（lead），2026-11-23 18:56 开始，19:30 完成交付
- 被接管：Codex 的 M4-A Unity 集成轮次（额度耗尽中断）
- 工程：`G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL`
- Unity 6000.3.29f1 / URP 17.3.0 / WebGL
- 结论：**M4-A 达到可交付状态**；Unity 编译、EditMode、PlayMode、WebGL 构建、浏览器端到端全部实跑通过；无 BLOCKED 项，2 处 PARTIAL 与 1 处叙事内容偏差已显式记录。

配套文档：`CodexInterruptionAudit.md`、`ExistingChangesInventory.md`、`M4A_CompletionMatrix.md`、`TestResults.md`、`HandoffToCodex.md`；证据：`Evidence/`（15 张浏览器截图 + `browser.json` + 4 份 Unity 测试/构建日志）。

## 1. Codex 中断前已经完成什么

- **M3-B 逻辑层接入代码**（已落盘，未编译）：`StationInvestigation.cs`、重写版 `StationHud.cs`、`Assets/Tests/Editor/M4AInvestigationTests.cs`、`Assets/Tests/PlayMode/M4AStationPlayTests.cs` + `M4A.PlayMode.asmdef`，以及 asmdef 引用更新。
- **M3-B 资产导入**：`Assets/_Project/Scripts/M3B/`（四模块 + 四 asmdef，`noEngineReferences: true`）、`Assets/_Project/Resources/M3B/`（`ch01_evidence.json`、`ch01_dialogue.json`、`mock_ai_fixtures.json`，版本 `story-v1.0-phase2`）。
- **逻辑层控制台测试**：用 csc + 控制台 harness 在 Unity 之外编译 19 个运行时源文件 + 7 个测试文件，29/29 通过（`M4A-QA/Logs/logic-results.txt`）。
- **未完成**：M4-A 代码在 Unity 内的编译、EditMode/PlayMode 执行、场景更新、WebGL 构建、浏览器验证。依据：预检副本 `F:\EchoBuilds\M4A-Integration` 中 `StationHud.cs` 仍是 18:23 的旧版、无 `StationInvestigation.cs`，且预检（18:48:52）早于源码写入（18:50:04）。

Codex 的工作成果**全部保留**：`StationInvestigation.cs`、`M4AInvestigationTests.cs`、`M4AStationPlayTests.cs` 的 SHA-256 与接管前完全一致，DSH 一个字节都没改。

## 2. DSH 接管后新增或修改什么

修复（承接 Codex 遗留缺陷）：

1. **编译阻断**：`M4A.PlayMode.asmdef` 删除与 `optionalUnityReferences: ["TestAssemblies"]` 重复的 `UnityEngine.TestRunner` 引用。此前整个 WebGL 工程 `Scripts have compiler errors.`。
2. **HUD 无法关闭 / 指针锁死**：重写 `StationPlayer.cs` —— 面板打开时强制解锁光标、禁用移动/环视/射线，`E` 关闭并重新锁定、`Esc` 关闭并释放，`Capture()` 统一锁定入口。
3. **出示按钮匹配不到**：选项文案改为 `出示 <证据号> <标题>`，并让 `Present` 捕获 `GameContractException`（未满足前置条件时显示“现在不适合出示这份证据（code）。”）。
4. **中文缺字**：新增 `Assets/_Project/Resources/M4A/StationChinese.ttf`（思源黑体 SC 子集，2,066 字形）、`StationChinese SDF.asset`（预烘焙静态 TMP 资产，460 字符，1024 atlas，SDFAA，2,338,006 B）与编辑器工具 `Assets/Station/Editor/ChineseFontBaker.cs`（菜单 `Echo/Bake Chinese font asset`）。HUD 优先加载预烘焙资产，才回落到运行时 `CreateFontAsset`。
5. **E02 无现场来源**：`SceneSetup.cs` 在站台左侧新增“维修柜”（`InteractionKind.Document`，追加在枚举尾部），HUD 新增 `InspectCabinet()` → E02。这样“出示证据 → 老周反馈变化”在浏览器可实证。
6. **UI 布局缺陷**（DSH 自查）：E01 长文本压到选项行、面板半透明透背景。重排为 sheet 560×470、标题 26 号 (0,210)、正文 17 号 (0,130,520×116, Top)、选项自 y=38 起每行 30、关闭提示 (0,-210)，面板底色改为不透明 `(.035,.085,.095,1)`。
7. **场景重新生成**：全部交互标签中文化（老周 / 怀表 / 维修柜、`E 返回车站`、`WASD 移动 鼠标 环视 E 调查 Esc 释放鼠标`），`Station.unity` 由 `Echo/Generate WebGL station` 重新生成（190,083 B），未手改 YAML，GUID 未变。

新增交付物：

- `EchoLostAndFound_WebGL/Builds/M4A-Station/`（17 文件 21,270,890 B + `manifest.json` 逐文件 SHA-256）与 `M4A-Station.zip`（20,726,277 B，sha256 `BBB58625C3CDAC16AD1A6C00B848129F8BBA779B8966E74F4B5E95D194AF2473`）。
- `M4A-QA/Scripts/m4a-e2e.mjs`（零依赖 CDP 端到端脚本，按标签选选项、断言 D01 只触发一次）、`M4A-QA/Scripts/make-font.py` + `font-chars.txt`（字体子集）。
- `M4A-Backups/WebGL-before-DSH-20261123-190008/`（接管前快照，220 文件 8.9 MB，含逐文件 SHA-256）。
- 测试日志 `M4A-QA/Logs/takeover-final-*.{log,xml}`、`M4A-QA/e2e/final-01/`、本目录 6 份交接文档。

## 3. 哪些功能通过真实 Unity 测试

| 功能 | 验证方式 | 结果 |
| --- | --- | --- |
| M3-B 内容加载与版本校验 | PlayMode 真实 `Resources.Load` | 通过 |
| 怀表 5 字段观察 / 重复观察无重复事件 | EditMode（真实 EvidenceSystem） | 通过 |
| 证据登记与快照持久化（PlayerPrefs） | PlayMode 真实场景重载 | 通过（存档含 `E01`/`E02`） |
| 证据前置条件（未持有时出示被拒） | EditMode 断言 `PreconditionFailed` | 通过 |
| 出示 E02 → D01 解锁 → 选项变化 | EditMode + PlayMode + 浏览器 | 通过（三轮一致） |
| 场景重载后老周会话重建 | PlayMode | 通过 |
| Mock AI 超时回退 | EditMode（`FallbackReason=="timeout"`） | 逻辑层通过，UI 未触发 |
| 中文 TMP 字体在运行时可用 | PlayMode 日志 `M4A font StationChinese SDF 怀=True 证据=True` | 通过 |
| 聚合结果 | EditMode 6/6、PlayMode 1/1，均 exit 0 | 通过 |

## 4. WebGL 是否构建成功

**成功。** `WebGL build Succeeded: 65698620 bytes, 00:02:40.3059370, errors 0`，exit 0，场景仅 `Assets/Station/Scenes/Station.unity`，产物 17 文件 21,270,890 B（gzip 压缩，`decompressionFallback=false`、`threadsSupport=false`）。发布目录与 zip 已就位（见上）。对照 M3-A 的 20,591,622 B，增量主要来自 2.34 MB 中文字体资产。

## 5. 浏览器是否实际运行成功

**成功。** headless Chrome 157（SwiftShader WebGL 2.0）通过本地 HTTP 服务加载构建，冷启动 1,447 ms，刷新启动 931 ms。端到端脚本 `completed=true`：11 个页面、5 次交互、`D01` 恰好触发 1 次、JS 异常 0、HTTP ≥ 400 为 0，15 张截图。

可视化确认（`Evidence/browser/`）：

- `02-npc-opening.png`：中文「老周」对话框，开场白 + 1/2 选项，底部中文操作条。
- `07-watch-dial.png`、`08-watch-e01.png`：表盘页「指针停在 9:17。」→ E01 证据页（本次修复后文字与选项不再重叠，面板不透明）。
- `11-disclosure.png`：出示 E02 后正文变为老周证词，选项从 4 条增至 5 条并出现「再问站台那晚的照明」。
- `14-reloaded.png`、`15-persisted-disclosure.png`：刷新后重新出示 E02 仍触发 D01，证明证据状态真实持久化。

## 6. 是否影响原始 HDRP 工程

**未影响。**

- `git status --porcelain -- Assets Packages ProjectSettings`（仓库根）输出为空。
- 未在 G: 盘工程上跑过任何 batchmode 编译/测试/构建（该工程被运行中的 Unity 编辑器 PID 8272 占用），全部操作在 `F:\EchoBuilds\M4A-Takeover-1` 副本。
- 未修改 `Server/`（M4-B 他人在研后端）；`Server/requirements.txt` 的未暂存修改早于本接管，来自 M4-B，DSH 未触碰。
- 未删除任何场景、Prefab 或 `.meta`；未执行 `git reset --hard` / `git clean -fd` / 强制覆盖 / 任何 `git add`、`commit`。
- M3-A 验收构建 `Builds/M3A-Station` 原样保留。

## 7. 还有哪些问题待 Codex 审查

1. **验收脚本与叙事内容冲突**：原脚本要求“出示怀表证据（E01）→ NPC 反馈变化”，但 M3-B 内容里 D01 需要 E02、D03 需要 E01+E05（E05 不在第 1 章）。DSH 未改内容，改为给 E02 增加现场来源“维修柜”。**请 Codex/Director 裁定**：是调整验收脚本，还是让 D03 只挂 E01（属叙事改动，需 narrative 授权）。
2. **怀表字段观察的 UI 粒度**：HUD 目前一次“翻看背刻、编号和表冠”即观察全部 5 个必填字段（逻辑层支持逐字段，EditMode 已覆盖）。是否要做逐字段渐进观察（更贴合“观察→推断”玩法）待定。
3. **Mock AI 回退未在界面触发**：`SubmitFreeText` 超时回退仅 EditMode 覆盖；HUD 无自由输入控件，且尚无 HTTP 会话层（M4-B）。接入后端后需要补一条浏览器级回退用例。
4. **字体的可维护性**：`StationChinese SDF.asset` 是静态子集（460 字符）。**任何新增中文文案必须先运行 `Echo/Bake Chinese font asset` 重新烘焙**，否则运行时会缺字；`ChineseFontBaker.CharacterSet()` 只扫描 `Assets/Station`、`Assets/_Project/Scripts` 与 `Assets/_Project/Resources/M3B/*.json`。
5. **场景是程序化生成的**：`Station.unity` 由 `Echo/Generate WebGL station` 生成，手改场景会在下次生成时被覆盖；美术如需手工布置需先改 `SceneSetup.cs` 或锁定场景。
6. **维修柜属 DSH 新增场景对象**（位置 `-3.1, 1.05, 3.42`，尺寸 `1.12×2.10×0.34`，`InteractionKind.Document = 3`），需美术/叙事确认是否符合车站布景与证据来源设定。
7. **浏览器覆盖有限**：仅 headless Chrome + SwiftShader，未测真实 GPU、Edge/Firefox、移动端。
8. **状态层仍是本地 PlayerPrefs**，未接 M4-B 的 HTTP 会话/存档；`StationInvestigation.cs` 的 `DialogueEngine(..., null, ...)` 第二参数（证据视图）之外的 provider 已在用 Mock，但会话层空缺。
9. **未提交**：所有改动仍未 `git add`/`commit`（遵循 AGENTS.md），`M4A-Backups/`、`M4A-QA/` 为未跟踪目录，验收后建议把 `M4A-Backups/` 移出仓库。
10. **构建体积/发布**：21.27 MB（gzip）未做纹理解压优化与模型体积裁剪；魔搭创空间上传与线上验证尚未执行（属发布阶段）。
11. **端口 18749 的测试服务器仍在运行**（供预览），18748（旧构建）已停止。
