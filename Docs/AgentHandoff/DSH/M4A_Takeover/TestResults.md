# M4-A 测试结果

- 记录时间：2026-11-23 19:30 (+08:00)
- Unity：6000.3.29f1（`F:\software\unity\6000.3.29f1\Editor\Unity.exe`）
- 渲染管线：URP 17.3.0
- 执行位置：**全部测试在 `F:\EchoBuilds\M4A-Takeover-1` 副本执行**（G: 盘工程被运行中的 Unity 编辑器 PID 8272 占用，且空闲空间 17.9 GB 低于构建脚本 20 GiB 门槛）
- 副本内容：G: 工程的 `Assets/`、`Packages/`、`ProjectSettings/`、`UserSettings/` + `F:\EchoBuilds\M4A-Integration\Library`（2.81 GB 导入缓存）

## 一、Unity 编译检查

命令：

```
Start-Process "F:\software\unity\6000.3.29f1\Editor\Unity.exe" -ArgumentList @(
  '-batchmode','-quit','-nographics',
  '-projectPath','F:/EchoBuilds/M4A-Takeover-1',
  '-executeMethod','EchoStation.SceneSetup.Generate',
  '-logFile','F:\EchoBuilds\M4A-scene-regen.log') -Wait -PassThru
```

结果：`exit=0`，`AssetDatabase: script compilation time: 3.818662s`，日志无 `error CS`，`Exiting batchmode successfully now!`，场景重建为 190,083 B。

> 注：直接 `& Unity.exe ...` 调用在本宿主 shell 会提前返回（`$LASTEXITCODE` 为空、日志缺失），必须用 `Start-Process -Wait -PassThru`；本机 PATH 无 `pwsh`，故 `Tools/Build/Invoke-WebGLBuild.ps1` 不可用，改为直接设置 `DSH_WEBGL_OUTPUT`/`DSH_WEBGL_COMPRESSION` 后调用 `WebGLBuildEntry.Build`。

首次编译曾失败（Codex 遗留）：`Assembly has duplicate references: UnityEngine.TestRunner (Assets/Tests/PlayMode/M4A.PlayMode.asmdef)`，修复见 `ExistingChangesInventory.md`。

## 二、EditMode 测试

```
Unity.exe -batchmode -nographics -projectPath F:/EchoBuilds/M4A-Takeover-1 \
  -runTests -testPlatform EditMode \
  -testResults G:/projects/EchoLostAndFound/M4A-QA/Logs/takeover-final-EditMode.xml \
  -logFile G:/projects/EchoLostAndFound/M4A-QA/Logs/takeover-final-EditMode.log
```

| 项 | 值 |
| --- | --- |
| exit code | 0 |
| total / passed / failed / skipped | 6 / 6 / 0 / 0 |
| result | Passed |
| duration | 0.1948031 s |

用例构成：

- M3-A 遗留 3 条（`Assets/Tests/Editor/StationAcceptanceTests.cs`）
- M4-A 新增 3 条（`Assets/Tests/Editor/M4AInvestigationTests.cs`，Codex 编写，DSH 未修改）：
  - `WatchNeedsAllFiveFieldsAndRecheckingEmitsNoDuplicateEvents`
  - `PresentationHonoursMaterialAndNpcAndUnlocksD01OnlyOnce`
  - `TimeoutPreservesNodeAndSnapshotAndRestoreRejectsInvalidEvidence`

日志副本：`Evidence/logs/takeover-final-EditMode.log` / `.xml`

## 三、PlayMode 测试

```
Unity.exe -batchmode -nographics -projectPath F:/EchoBuilds/M4A-Takeover-1 \
  -runTests -testPlatform PlayMode \
  -testResults .../takeover-final-PlayMode.xml \
  -logFile .../takeover-final-PlayMode.log
```

| 项 | 值 |
| --- | --- |
| exit code | 0 |
| total / passed / failed | 1 / 1 / 0 |
| result | Passed |
| duration | 0.6375689 s |

`M4AStationPlayTests.WatchCardSurvivesReturnAndRepairCardChangesNpcOptions` 在日志中留下完整执行轨迹（真实场景加载 + TMP 字体 + 动态按钮）：

```
M4A font StationChinese SDF 怀=True 证据=True
M4A page 怀表 · 表盘 | 指针停在 9:17。
M4A choice 1 翻看背刻、编号和表冠
M4A page E01 · 停表与编号 | 表面 21:17。背刻 0412·0916。后盖边钢印 QH-283。侧冠凹陷，冠轴可见偏斜。
M4A page E02 · 配电故障卡 | 站台照明支路进水跳闸 21:17。21:20 内侧油灯临时补照。本夜该支路未恢复。
M4A page 老周 | 这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。
M4A choice 1 问站台那晚的照明 / 2 结束对话 / 3 出示 E01 停表与编号 / 4 出示 E02 配电故障卡
M4A choice 4 出示 E02 配电故障卡
M4A page 老周 | 进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。
M4A choice 1 问站台那晚的照明 / 2 再问站台那晚的照明 / 3 结束对话 / 4 出示 E01 / 5 出示 E02
```

日志副本：`Evidence/logs/takeover-final-PlayMode.log` / `.xml`

## 四、WebGL 构建

```
$env:DSH_WEBGL_OUTPUT='F:\EchoBuilds\M4A-Station-2'
$env:DSH_WEBGL_COMPRESSION='gzip'
Start-Process Unity.exe -ArgumentList @('-batchmode','-quit','-nographics',
  '-projectPath','F:/EchoBuilds/M4A-Takeover-1','-buildTarget','WebGL',
  '-executeMethod','EchoLostAndFound.Build.WebGLBuildEntry.Build',
  '-logFile','F:\EchoBuilds\M4A-Station-2-build.log') -Wait -PassThru
```

| 项 | 值 |
| --- | --- |
| exit code | 0 |
| 耗时 | 2.8 分钟（IL2CPP 缓存命中；首次构建为 8.2 分钟） |
| 摘要 | `WebGL build Succeeded: 65698620 bytes, 00:02:40.3059370, errors 0` |
| 场景 | `Assets/Station/Scenes/Station.unity` |
| 产物 | 17 个文件，21,270,890 B（gzip） |
| 压缩 | gzip，`decompressionFallback=false`、`threadsSupport=false`、`dataCaching=true`、`exceptionSupport=ExplicitlyThrownExceptionsOnly` |
| M3-A 对照 | 20,591,622 B → 21,270,890 B（增量主要来自 2.34 MB 中文字体资产） |

发布位置：`EchoLostAndFound_WebGL/Builds/M4A-Station/`（含逐文件 SHA-256 `manifest.json`），压缩包 `EchoLostAndFound_WebGL/Builds/M4A-Station.zip` 20,726,277 B，SHA-256 `BBB58625C3CDAC16AD1A6C00B848129F8BBA779B8966E74F4B5E95D194AF2473`。

构建日志副本：`Evidence/logs/webgl-build.log`

## 五、本地 HTTP 浏览器测试

```
node Tools\Build\serve-webgl.mjs F:\EchoBuilds\M4A-Station-2 18749   # 分离进程，隐藏窗口
node M4A-QA\Scripts\m4a-e2e.mjs http://127.0.0.1:18749 M4A-QA\e2e\final-01
```

服务器校验：`/index.html` 200、`/Build/M4A-Station-2.wasm.gz` 200 且 `Content-Encoding: gzip`。

浏览器：Chrome `157.0.8103.79`（`C:/Program Files/Google/Chrome/Application/chrome.exe`），headless=new + `--remote-debugging-pipe` + `--enable-unsafe-swiftshader` + `--use-angle=swiftshader`，窗口 1200×850。

WebGL 能力实测：WebGL 2.0，renderer `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)`，`MAX_VERTEX_UNIFORM_VECTORS=4096`。

## 六、端到端结果（最终运行 `M4A-QA/e2e/final-01`）

| 指标 | 值 |
| --- | --- |
| exit code | 0 |
| completed | true |
| 冷启动（loading bar 消失） | 1,447 ms |
| 刷新后启动 | 931 ms |
| 观测到的页面（`M4A page`） | 11 |
| `Station interaction:` 日志 | 5 条（老周 / 维修柜 / 怀表 / 老周 / 老周） |
| `dialogue.disclosure_triggered D01` | 恰好 1 次 |
| JS 异常 | 0 |
| JS 对话框 | 0 |
| HTTP ≥ 400 | 0 |
| 截图 | 15 张 |

步骤序列（脚本实际按键）：进入车站 → 点击锁定 → 走近老周 → `E` 开场 → 选“问站台那晚的照明” → 离开 → 走近维修柜 → `E` 取 E02 → 走近怀表 → `E` 表盘页 → 选“翻看背刻、编号和表冠” 取 E01 → 回老周 → 出示 E02 → 断言 D01 文本 → 选“再问站台那晚的照明” → 再次出示 E02（断言 D01 事件仍为 1） → 刷新页面（状态持久化） → 重新出示 E02 → 断言 D01 文本。

控制台证据（节选）：

```
M4A font StationChinese SDF 怀=True 证据=True
M4A event evidence.fields_observed watch.dial
M4A event evidence.registered E01
M4A event evidence.registered E02
M4A event dialogue.evidence_presented E02
M4A event dialogue.disclosure_triggered D01
```

已知无害告警：SwiftShader 上 3 个 URP 隐式 shader（`Hidden/CoreSRP/CoreCopy` 等）不支持、Additional Lights Cookie Format 回退 RGBA8、`JS_FileSystem_Sync` 弃用提示。不影响渲染与交互。

截图与数据：`Evidence/browser/`（`01-station.png` … `15-persisted-disclosure.png`、`browser.json`）

## 七、未执行/未覆盖的测试

| 项 | 原因 |
| --- | --- |
| 真实 GPU、Edge/Firefox/Safari、移动端浏览器 | 本机仅验证 headless Chrome + SwiftShader 软件渲染 |
| Mock AI 自由输入超时回退（浏览器/PlayMode） | HUD 未提供自由输入控件，逻辑层由 EditMode 覆盖 |
| 魔搭创空间线上部署验证 | 需上传，属 M4-C/发布阶段 |
| 大规模 PlayMode 回归 | 现有 PlayMode 用例 1 条（端到端覆盖） |
