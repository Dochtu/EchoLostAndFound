# HandoffToCodex — M4-A 接管后交接

- 交接方：DSH（lead），2026-11-23 19:30
- 接收方：Codex（M4-A 主开发继续）
- 状态：**M4-A 可交付**；Unity 编译 / EditMode 6/6 / PlayMode 1/1 / WebGL 构建 / 浏览器端到端全部实跑通过
- 未提交：所有改动仍在工作区（按 AGENTS.md 不自动 commit），需要 Director 授权后再提交

## 一、先读哪几份

| 顺序 | 文档 | 用途 |
| --- | --- | --- |
| 1 | `M4A_Takeover_Report.md` | 一页看全：Codex 做了什么、DSH 改了什么、验证到什么程度、遗留问题 |
| 2 | `M4A_CompletionMatrix.md` | 逐条 DONE/PARTIAL 与证据映射，含验收脚本偏差说明 |
| 3 | `TestResults.md` | 可直接复跑的命令与确切数字 |
| 4 | `ExistingChangesInventory.md` | 逐文件哈希与归属，判断“哪些是 Codex 的、哪些是 DSH 的” |
| 5 | `CodexInterruptionAudit.md` | 中断点证据链（为什么说 M4-A 从未被 Unity 编译） |
| 6 | `Evidence/` | 15 张浏览器截图 + `browser.json` + 4 份 Unity 日志 |

## 二、工作区现状（接手前必读）

- 工程：`G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL`，基线提交 `4c51712`。
- **代码逻辑层未变**：`StationInvestigation.cs`、`M4AInvestigationTests.cs`、`M4AStationPlayTests.cs` 与 Codex 中断时逐字节一致；M3-B 的 `Assets/_Project/Scripts`、`Resources/M3B` 未改。
- DSH 改动集中在表现层与集成层：`StationHud.cs`、`StationPlayer.cs`、`M2Interactable.cs`（+`Document` 枚举）、`SceneSetup.cs`、`Station.unity`（重新生成）、`M4A.PlayMode.asmdef`（去重复引用）、新增中文字体三件套 + `ChineseFontBaker.cs`。
- 渲染/输入/包：**没有新增或升级任何 Package**，仍为 URP 17.3.0、Input System 1.20.1、uGUI 2.0.0、TMP。
- 构建：`EchoLostAndFound_WebGL/Builds/M4A-Station/`（21,270,890 B，17 文件，`manifest.json` 有逐文件 sha256）+ `M4A-Station.zip`（20,726,277 B）。预览服务：`http://127.0.0.1:18749`（`node Tools/Build/serve-webgl.mjs F:\EchoBuilds\M4A-Station-2 18749`，仍在运行）。

## 三、复跑方式（照抄即可）

```powershell
# 0. 准备副本（G: 盘有运行中的 Unity 编辑器，且空闲 17.9GB < 构建脚本 20GiB 门槛）
#    Assets/Packages/ProjectSettings/UserSettings 复制到 F:\EchoBuilds\M4A-Takeover-1，
#    Library 可从 F:\EchoBuilds\M4A-Integration\Library 复用（2.81 GB，省 ~8 分钟导入）

# 1. 场景重建 + 编译检查（顺手验证编译）
Start-Process 'F:\software\unity\6000.3.29f1\Editor\Unity.exe' -Wait -PassThru -ArgumentList @(
  '-batchmode','-quit','-nographics','-projectPath','F:/EchoBuilds/M4A-Takeover-1',
  '-executeMethod','EchoStation.SceneSetup.Generate','-logFile','F:\EchoBuilds\regen.log')

# 2. EditMode / PlayMode
... -runTests -testPlatform EditMode -testResults <xml> -logFile <log>
... -runTests -testPlatform PlayMode -testResults <xml> -logFile <log>

# 3. WebGL 构建（必须用 Start-Process，直接 & 调用会被宿主 shell 提前返回）
$env:DSH_WEBGL_OUTPUT='F:\EchoBuilds\M4A-Station-3'; $env:DSH_WEBGL_COMPRESSION='gzip'
Start-Process 'F:\software\unity\6000.3.29f1\Editor\Unity.exe' -Wait -PassThru -ArgumentList @(
  '-batchmode','-quit','-nographics','-projectPath','F:/EchoBuilds/M4A-Takeover-1','-buildTarget','WebGL',
  '-executeMethod','EchoLostAndFound.Build.WebGLBuildEntry.Build','-logFile','F:\EchoBuilds\build.log')

# 4. 浏览器端到端
node Tools\Build\serve-webgl.mjs F:\EchoBuilds\M4A-Station-3 18750
node M4A-QA\Scripts\m4a-e2e.mjs http://127.0.0.1:18750 M4A-QA\e2e\run-<ts>
```

坑（已踩过，别重复）：

- PATH 无 `pwsh`，`Tools/Build/Invoke-WebGLBuild.ps1` 不能用；改直调 Unity + `DSH_WEBGL_*` 环境变量。
- 不能用 `Start-Job` 起静态服务器（随 pwsh 退出被杀，浏览器报 `ERR_CONNECTION_REFUSED`），要用 `Start-Process` 分离进程。
- 端到端**不要按数字键猜选项顺序**，选项会随证据数量变化；用 `choose('出示 E02')` 这类按标签选择。
- E02 正文本身含“进水跳闸”，别拿“进水”做页面等待条件，会误判；用 D01 稳定文本“我的灯到二十才摆好”。
- 新增任何中文文案后先跑 `Echo/Bake Chinese font asset`，否则静态 SDF 缺字。

## 四、需要 Codex 决策的三件事

1. **验收脚本 vs 叙事内容**：脚本要求“出示怀表（E01）→ NPC 反馈变化”，但 D01 触发条件是 E02，D03 需要 E01+E05（E05 不在第 1 章）。DSH 的做法是不动内容、给 E02 增加现场来源“维修柜”。若希望严格按脚本走 E01，需要 narrative 侧改 D03 触发条件，这不是 Unity 侧能单方面决定的事。
2. **怀表观察粒度**：当前 UI 一次翻看即登记全部 5 字段；逻辑层支持逐字段（`ObserveField`），要不要做成分步观察（更贴合调查玩法）需玩法侧确认。若要做，只需改 `StationHud.Inspect/InspectRecord`，逻辑层无需变。
3. **维修柜**：位置与外观是否符合车站布景与证据来源设定（美术 + 叙事）。

## 五、建议的下一步（按优先级）

1. 让 Director 复核并批准 M4-A，再决定是否 `git add`/`commit`（当前 8 个修改 + 若干未跟踪文件）。
2. 接 M4-B 的 HTTP 会话层：把 `StationInvestigation` 的 `DialogueEngine(..., null, mockProvider)` 换成真实 provider，并补一条“后端超时 → 回退 + 提示”的浏览器用例（当前 Mock 回退只在 EditMode 覆盖）。
3. 真实 GPU / 多浏览器手测一次（Edge、Firefox、手机 Chrome），确认 SwiftShader 通过的 UI 在真实设备上排版一致。
4. 上线魔搭创空间前的体积优化：字体 2.34 MB 可再切小（当前 460 字符、1024 atlas 已接近够用），纹理压缩与模型面数另计。
5. 验收后把 `M4A-Backups/`（8.9 MB 快照）移出仓库或删除，`M4A-QA/` 保留为测试证据。
