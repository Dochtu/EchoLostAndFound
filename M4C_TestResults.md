# M4-C 测试结果

所有结果均来自本轮实际执行；日志与截图路径为仓库相对路径（根目录 `G:\projects\EchoLostAndFound`）。

## 0. 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows（工作目录 `G:\projects\EchoLostAndFound`） |
| Unity | 6000.3.29f1（`F:\software\unity\6000.3.29f1\Editor\Unity.exe`），含 WebGL 模块 |
| 渲染管线（参赛工程） | URP 17.3.0 |
| Python | 3.12.14（`Server\.venv`） |
| 后端依赖 | fastapi 0.165.0 / starlette 1.10.0 / pydantic 2.14.4 / uvicorn 0.54.0 / httpx 0.28.1 / pytest 9.2.0 |
| 内容版本 | `story-v1.0-phase2` |
| 浏览器 | Chrome（headless SwiftShader）与 Chrome（headed，NVIDIA RTX 4060 Laptop GPU / D3D11） |
| Docker | Docker Desktop 28.5.1（本地 linux 容器） |

---

## 1. 后端 pytest

命令：

```powershell
cd G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

结果：

```
123 passed, 1 warning in 2.85s
```

- 基线（M4-B）：77 passed
- 本轮新增：46（含 5 个新测试文件 + 3 个既有文件扩充）
- 唯一 warning：`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` —— 依赖层提示，与本轮改动无关。

分文件用例数：

| 文件 | 用例数 | 说明 |
| --- | --- | --- |
| `tests/test_sessions.py` | 13 | 改写 `test_new_conversation_does_not_close_previous_one` |
| `tests/test_request_id.py` | 12 | 新增：五态 + 错误响应头 |
| `tests/test_security.py` | 12 | 既有 |
| `tests/test_contract.py` | 11 | 既有 |
| `tests/test_public_safety.py` | 10 | 新增：体积、脱敏、密钥 |
| `tests/test_providers.py` | 10 | 既有，`ExplodingProvider` 改异步 |
| `tests/test_static_site.py` | 11 | 新增：同源静态站 + gzip + 防穿越 |
| `tests/test_isolation.py` | 8 | 新增：双玩家隔离与容量 |
| `tests/test_llm.py` | 8 | 既有，8 项异步化（`asyncio.run` 包装） |
| `tests/test_evidence.py` | 9 | 既有 |
| `tests/test_guards.py` | 6 | 既有 + 静态资源不限流 |
| `tests/test_concurrency.py` | 5 | 新增：非阻塞、并发、异常、客户端释放 |
| `tests/test_content.py` | 5 | 既有 |
| `tests/test_integration.py` | 3 | 既有，隔离断言改写 |
| **合计** | **123** | |

详细日志：`M4C\Logs\pytest-m4c-verbose.txt`

### 进程外 HTTP 冒烟（真实 uvicorn，非 TestClient）

`M4C\Logs\c1-http-smoke.txt`：

| 场景 | 结果 |
| --- | --- |
| `GET /api/v1/health` | 200，带 `X-Request-ID` |
| `POST /api/v1/sessions`（带 `X-Request-ID: create-001`） | 201，响应头回显 `create-001` |
| `POST /turns` 仅请求体 `request_id=body-only-002` | **200**，`X-Request-ID: body-only-002`，信封 `request_id` 一致，`source=fixed_line` |
| `POST /turns` 仅请求头 `hdr-only-003` | 200，回显 `hdr-only-003` |
| `POST /turns` 头 `hdr-004` + 体 `body-004` | **400**，`X-Request-ID: hdr-004` |
| `GET /api/v1/meta` | 200，`limits.max_sessions=512` |

双玩家隔离（`M4C\Logs\c1-isolation-smoke.txt`）：A 建会话 → 建 B → A 仍 `status=open`；A 出示 E02 → `triggered=D01`；B 仍 `status=open`、无出示无披露。

---

## 2. Unity：导入与编译

命令（batchmode，工程 `EchoLostAndFound_WebGL`）：

```powershell
F:\software\unity\6000.3.29f1\Editor\Unity.exe -batchmode -quit `
  -projectPath G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL `
  -executeMethod EchoStation.ChineseFontBaker.Bake -logFile M4C\Logs\unity-bake-5.log
```

结果：exit 0，无编译错误。

过程中修复的真实编译错误（保留记录，便于复用）：

| 日志 | 错误 | 处理 |
| --- | --- | --- |
| `unity-bake-2.log` | `CS0117: 'StationTargets' does not contain a definition for 'Laozhou' / 'Linyao'` | 枚举类型名为 `StationTarget`，静态类为 `StationTargets`，测试改用 `StationTargets.NpcId(StationTarget.Laozhou)` |
| `unity-bake-2.log` | `CS0161: 'M4CStationPlayTests.LinyaoPackageBinderAndPickupSheetAreReachable()': not all code paths return a value` | 从 `[UnityTest] IEnumerator`（无 yield）改为 `[Test] public void` |
| `unity-bake-3.log` | `CS0051: Inconsistent accessibility: parameter type 'StationInvestigation' is less accessible than method 'StationDialogueBridge(...)'` | `StationInvestigation` 为 `internal sealed`，构造器改 `internal` |
| `unity-bake-4.log` | `CS1069: The type name 'UnityWebRequest' … could not be found` | `Packages/manifest.json` 增加内建模块 `com.unity.modules.unitywebrequest` |
| `unity-bake-4.log` | `CS1622: Cannot return a value from an iterator` | `ProbeRoutine()` 中 `return;` → `yield break;` |
| `unity-bake-4.log` | `CS0029: Cannot implicitly convert 'IReadOnlyList<ObservedFieldView>' to 'IReadOnlyList<string>'` | `FieldIds()` 逐个取 `view.FieldId` |

字体烘焙（`Echo/Bake Chinese font asset`）：

```
FONT bake chars=520 glyphs=520 atlases=1 missing=none
FONT saved=True glyphs=520 uncovered=0
```

产物 `Assets/_Project/Resources/M4A/StationChinese SDF.asset` = 2,369,239 B（原 2,338,006 B / 460 字）。

场景重建（`Echo/Generate WebGL station`，`unity-scene.log`）：`Assets/Station/Scenes/Station.unity` = 218,223 B（原 190,083 B），包含林遥、失物包、副联册、西值班窗。

---

## 3. Unity EditMode

```powershell
F:\software\unity\6000.3.29f1\Editor\Unity.exe -batchmode -quit `
  -projectPath …\EchoLostAndFound_WebGL `
  -runTests -testPlatform EditMode -testResults M4C\Logs\editmode-results.xml `
  -logFile M4C\Logs\unity-editmode.log
```

结果：`result=Passed total=15 passed=15 failed=0`

| 测试类 | 用例 | 结果 |
| --- | --- | --- |
| `M4CInvestigationTests` | `SceneLabelsRouteOnlyWhenLabelAndKindMatch` | Passed |
| | `WatchPartsCanBeReadInAnyOrderAndRegisterE01WhenComplete` | Passed |
| | `PackageAndBinderOpenOnlyAfterTheSerialNumberIsObserved` | Passed |
| | `PickupInspectionNeedsTheFaultCardIndexNotTheFrontCard` | Passed |
| | `LinyaoOnlyRecognisesTheEngravingOnceTheWatchIsComplete` | Passed |
| | `D03NeedsE01AndE05AndNeverFiresTwice` | Passed |
| | `D02HasOneBranchPerNpcAndConsumesE03AndE04` | Passed |
| | `WholeChapterCanBeCollectedThroughSceneTargetsOnly` | Passed |
| | `EvidenceStillPersistsAndContentVersionIsChecked` | Passed |
| `M4AInvestigationTests` | `WatchNeedsAllFiveFieldsAndRecheckingEmitsNoDuplicateEvents` | Passed |
| | `PresentationHonoursMaterialAndNpcAndUnlocksD01OnlyOnce` | Passed |
| | `TimeoutPreservesNodeAndSnapshotAndRestoreRejectsInvalidEvidence` | Passed |
| `StationAcceptanceTests` | `BothEntryPointsHaveDisplayableContentAndDistinctCommandIdentities` | Passed |
| | `BuildStartsInStationWithInvestigatorAndBothInteractions` | Passed |
| | `InvestigationRayHonoursRangeAndCannotReachThroughStationWalls` | Passed |

---

## 4. Unity PlayMode

在线（服务在 8787 运行）：

```
result=Passed total=6 passed=6 failed=0    → M4C\Logs\playmode-online-results.xml
```

离线（不启动服务）：

```
result=Passed total=6 passed=6 failed=0    → M4C\Logs\playmode-results2.xml
```

| 测试类 | 用例 | 在线 | 离线 |
| --- | --- | --- | --- |
| `M4AStationPlayTests` | `WatchCardSurvivesReturnAndRepairCardChangesNpcOptions` | Passed | Passed |
| `M4CStationPlayTests` | `LinyaoPackageBinderAndPickupSheetAreReachable` | Passed | Passed |
| | `PackageAndBinderRefuseBeforeTheSerialNumberIsRead` | Passed | Passed |
| `M4COnlinePlayTests` | `FreeTextRowOnlyAppearsWhileTalkingToAnNpc` | Passed | Passed |
| | `EmptyFreeTextIsRefusedWithoutWaiting` | Passed | Passed |
| | `FreeTextSubmitAlwaysReleasesTheWaitingState` | Passed | Passed |

在线运行关键日志：

```
M4C online dialogue ready, provider=mock base=http://127.0.0.1:8787
M4C server session <uuid> for npc_laozhou
M4C online probe online=True status=在线对话已连接（服务器当前为 Mock 模拟回复，非真实模型）。
```

离线运行关键日志：

```
M4C online dialogue offline: 离线模式：固定剧情与证据调查仍可进行，自由输入暂不可用。
M4C online probe online=False status=离线模式：…
```

两轮均证明：Unity 侧 `UnityWebRequest` 与 FastAPI 的真实往返可用，且服务缺失时安全降级。

---

## 5. WebGL 构建

命令：

```powershell
$env:DSH_WEBGL_OUTPUT='F:\EchoBuilds\M4C-WebGL-03'
$env:DSH_WEBGL_COMPRESSION='gzip'
F:\software\unity\6000.3.29f1\Editor\Unity.exe -batchmode -quit `
  -projectPath G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL `
  -executeMethod EchoLostAndFound.Build.WebGLBuildEntry.Build `
  -logFile M4C\Logs\unity-webgl-build-3.log
```

结果：

```
WebGL build Succeeded: 21364584 bytes, 00:02:41.0864021, errors 0
```

产物清单（17 个文件，合计 21,364,584 B）：

| 文件 | 字节 |
| --- | --- |
| `Build\M4C-WebGL-03.wasm.gz` | 11,148,016 |
| `Build\M4C-WebGL-03.data.gz` | 10,080,203 |
| `Build\M4C-WebGL-03.framework.js.gz` | 89,825 |
| `Build\M4C-WebGL-03.loader.js` | 26,983 |
| `index.html` | 5,661 |
| `unity-logo-light.png` | 3,077 |
| 其余 11 个（模板/图标/样式） | 合计约 14.8 KB |

构建配置：`threadsSupport=false`、`decompressionFallback=false`、gzip 预压缩。

---

## 6. 服务端同源与容器验证

### 6.1 同源（`WEB_ROOT`）

```powershell
cd Server
$env:WEB_ROOT='F:\EchoBuilds\M4C-WebGL-03'
$env:MODEL_PROVIDER='mock'
$env:AI_TIMEOUT_MS='4000'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8790
```

| 请求 | 结果 |
| --- | --- |
| `GET /api/v1/health` | 200，`ready=true provider.kind=mock is_synthetic=true content_version=story-v1.0-phase2` |
| `GET /` | 200 `text/html`，5,661 B |
| `GET /Build/M4C-WebGL-03.wasm` | 200，`Content-Encoding: gzip`，`Content-Type: application/wasm` |
| `GET /Build/M4C-WebGL-03.loader.js` | 200，`text/javascript` |
| `GET /Build/M4C-WebGL-03.data.gz` | 200，`Content-Encoding: gzip`，`Content-Type: application/octet-stream` |

### 6.2 Docker 容器

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Deploy\build.ps1 -WebBuild F:\EchoBuilds\M4C-WebGL-03
# context=…\Deploy\context  webgl_files=17 webgl_bytes=21364584  server_bytes=262335
docker build -t echolostfound-unified:local Deploy\context      # exit 0, manifest sha256:68ab62e02497…
docker run -d --name echolostfound-m4c -p 7860:7860 -e MODEL_PROVIDER=mock echolostfound-unified:local
```

| 检查 | 结果 |
| --- | --- |
| 容器状态 | `Up (healthy)` |
| `/api/v1/health` | 200 |
| `/` | 200 `text/html; charset=utf-8`，5,661 B |
| `/Build/M4C-WebGL-03.wasm` | 200，`enc=gzip`，`application/wasm`，`vary=Accept-Encoding, Origin` |
| 容器日志 | `Uvicorn running on http://0.0.0.0:7860` |
| 容器内完整第一章 E2E | `M4C\E2E\container-01`，通过 |

---

## 7. 浏览器端到端

驱动脚本：`M4C\Scripts\m4c-e2e.mjs`（零依赖 CDP 驱动，`--remote-debugging-pipe`）。
运行方式（示例）：

```powershell
$env:M4C_PROFILE='C:\Users\10509\.dsh\m4c-profile-03'
node M4C\Scripts\m4c-e2e.mjs "http://127.0.0.1:8790/" "M4C\E2E\online-05" online
```

### 7.1 各轮结果

| 运行 | 场景 | 目标 | 渲染 | 完成 | API 请求 | JS 异常 | HTTP≥400 | 截图 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `online-05` | 在线全章 | 8790 同源 | headless / SwiftShader | true | 20 | 0 | 0 | 26 |
| `gpu-02` | 在线全章 | 8790 同源 | **headed / RTX 4060 D3D11** | true | 20 | 0 | 0 | 26 |
| `offline-03` | 离线回退 | 静态 8080（API 全停） | headless | true | 2（均为预期 404） | 0 | 2（预期） | 8 |
| `resume-03` | 重启恢复 | 8790 重启后 | headless | true | 4 | 0 | 0 | 6 |
| `container-01` | 容器同源全章 | 容器 7860 | headless | true | 20 | 0 | 0 | 26 |

在线三轮（online-05 / gpu-02 / container-01）指标完全一致：

```
d01Events=1  d03Events=1  recEvents=1  mirrorLogs=8  soft=[]  completed=true
```

`mirrorLogs` 示例：`M4C mirror ok E04 disclosures=[D02]` —— 服务端镜像与本地披露一致，无 mismatch。

### 7.2 自由输入三类回复（每轮均验证）

| 输入 | 期望 | 实测 |
| --- | --- | --- |
| 「站台那晚亮着吗」 | 不命中关键词 → `unknown_intent` 兜底 | `M4C free text reply ok=True source=fallback synthetic=True reason=unknown_intent`，页面「（对方不知道该怎么接这句话）」 |
| 「超时测试」 | Mock 行为 timeout | `reason=timeout`，页面「（模型回应超时，对方没有再说下去）」 |
| 「这两样对上了吗」（E01+E02 已收） | Mock 命中 → 明确标注模拟 | `source=mock synthetic=True`，正文「（模拟回复·仅测试，非正式台词）两样东西都把时间对上了。」+「（服务器模拟回复，非真实模型）」 |

`resume-03` 中输入「灯还亮着吗」命中服务端固定意图，返回 `source=fixed_line synthetic=False`，页面「站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。」——证明固定台词与生成回复在客户端可区分。

### 7.3 完整第一章流程（每轮复现）

老周开场 → 自由输入 → 超时测试 → 结束对话 → 走到怀表 → 五个部位逐一查看 → E01（含 QH-283）→ 失物包「查同号单据」→ E03 → 「翻副联册的对应档位」→ 副联册「取出指定领件联」→ E04 → 刷新 → 维修柜「看配电故障卡正面」→ E02 → 维修柜「翻看故障卡背面的索引」→ 背面索引 → 「照索引取拾物与检点联」→ E05 → 刷新 → 老周：出示 E02（D01）→ E03 → E04（镜像 D02）→ E01 → E05（D03）→ 结束对话 → 刷新 → 走到林遥 → 出示 E01（REC.engraving）→ E03 → E04（D02 林遥）。

### 7.4 中文与缺字

逐屏核对（截图）：

- `M4C\E2E\gpu-02\17-mock-reply-reply.png`：自由输入行、占位提示、「发送」、状态行、Mock 回复与标注、7 个出示选项全部正常显示，**无缺字方块**。
- `M4C\E2E\gpu-02\14-cabinet-index.png`：「维修柜 · 背面索引」「卡背印着一行索引：该时段拾物联。」正常。
- `M4C\E2E\gpu-02\23-linyao-d02.png`：林遥 D02「沈禾，是我妈妈。这个号和她放在家里那张一样。她写着要我自己领。」正常。

### 7.5 输入方式说明

Unity WebGL 不创建隐藏 DOM input（`document.activeElement` 始终是 `CANVAS:unity-canvas`，`querySelectorAll('input,textarea').length == 0`），因此 `Input.insertText` / IME 组合事件无效；实测有效方式是逐字符 `Input.dispatchKeyEvent({type:'char', text: ch})`（ASCII 与中文均通过），驱动脚本据此实现 `typeText()`。真实 OS 输入法组合窗口未验证（PARTIAL）。

---

## 8. 日志与证据索引

### `M4C\Logs\`

| 文件 | 内容 |
| --- | --- |
| `pytest-m4c-verbose.txt` | 123 项 pytest 详细输出 |
| `c1-http-smoke.txt` | request_id 五态真实 HTTP 冒烟 |
| `c1-isolation-smoke.txt` | 双玩家隔离真实 HTTP 冒烟 |
| `unity-bake-2/3/4/5.log` | 逐轮编译日志（含错误与修复） |
| `unity-font-bake.log` | 字体烘焙 |
| `unity-scene.log` | 场景重建 |
| `unity-editmode.log` / `editmode-results.xml` | EditMode 运行与结果 |
| `unity-playmode*.log` / `playmode-*.xml` | PlayMode 在线/离线运行与结果 |
| `unity-webgl-build{,-2,-3}.log` | WebGL 构建日志（以 `-3` 为准） |
| `uvicorn-8787.log`、`uvicorn-unified-8790.*` | 服务运行日志 |
| `static-8080.*` | 静态服务器日志 |

### `M4C\E2E\`

| 目录 | 说明 |
| --- | --- |
| `online-05`、`gpu-02`、`container-01` | 完整在线第一章（26 张截图 + `browser.json`） |
| `offline-03` | 离线回退（8 张） |
| `resume-03` | 重启恢复（6 张） |
| `online-01..04`、`offline-01..02`、`gpu-01`、`resume-01..02`、`probe-typing-01` | 迭代过程中的中间证据（保留，便于追溯失败与修复） |

### 复现命令速查

```powershell
# 后端
cd Server; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider

# EditMode / PlayMode
F:\software\unity\6000.3.29f1\Editor\Unity.exe -batchmode -quit `
  -projectPath G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL `
  -runTests -testPlatform EditMode -testResults M4C\Logs\editmode-results.xml `
  -logFile M4C\Logs\unity-editmode.log

# 同源服务
cd Server; $env:WEB_ROOT='F:\EchoBuilds\M4C-WebGL-03'; $env:MODEL_PROVIDER='mock'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8790

# 浏览器 E2E
$env:M4C_PROFILE='C:\Users\10509\.dsh\m4c-profile-03'
node M4C\Scripts\m4c-e2e.mjs "http://127.0.0.1:8790/" "M4C\E2E\online-05" online
```
