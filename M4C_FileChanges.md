# M4-C 文件改动清单

工作目录：`G:\projects\EchoLostAndFound`

## 0. Git 状态说明

- 分支 `master`，HEAD = `4c51712 Baseline HDRP, M3-A WebGL and M3-B before M4-A integration`。
- 本轮**未执行** `git add` / `git commit` / `git push` / `git reset --hard` / `git clean -fd`，也未做任何强制覆盖。
- 工作区当前 `git status --porcelain` 共 **114 条：24 modified + 90 untracked**（验收时实测）。其中大部分是 M3-A/M4-A/M4-B 阶段就已存在、尚未提交的成果（`Server/app`、`Server/tests`、`Server/*.md`、`EchoLostAndFound_WebGL/Assets/_Project`、`M3B/`、`M4A-*` 等），并非本轮新增；本轮最后新增的是根目录 7 份 `M4C_*.md` 交付文档。
- 本轮新增/修改的归属见下表；"归属"列中 **M4-C** 表示本轮产生，**遗留** 表示进入本轮前已存在的工作区改动。

---

## 1. 后端（`Server/`）

| 文件 | 变更 | 归属 | 原因 |
| --- | --- | --- | --- |
| `Server/app/sessions.py` | 重写 | M4-C | C1.1：删除"新建即关闭所有会话"逻辑；`OrderedDict` + 上限 + 终态清理 + 淘汰策略；`Session.ended_at/is_terminal`、`close()`、`open_count()` |
| `Server/app/config.py` | 改 | M4-C | C1.1 `max_sessions`（`MAX_SESSIONS`，1..10000）；C5 `web_root`（`WEB_ROOT`） |
| `Server/app/main.py` | 改 | M4-C | C1.2 `await policy.respond(...)`、lifespan 优先 `aclose()`；C1.3 request_id 五态与错误响应头；C1.4 请求体中间件、日志脱敏安装、限流仅作用于 `/api/v1/*`；C5 挂载同源静态站；`/meta.limits.max_sessions` |
| `Server/app/policy.py` | 改 | M4-C | C1.2 `respond` 改异步并 `await provider.generate`；离开话题时记录 `ended_at` |
| `Server/app/providers/base.py` | 改 | M4-C | C1.2 `NpcAiProvider.generate` / `DisabledProvider.generate` 改 `async def` |
| `Server/app/providers/mock_provider.py` | 改 | M4-C | C1.2 `generate` 改异步（行为与 fixture 不变） |
| `Server/app/providers/llm_provider.py` | 改 | M4-C | C1.2 改 `httpx.AsyncClient`、惰性创建、`async aclose()`、`available` 语义、错误映射不变 |
| `Server/app/middleware.py` | **新增** | M4-C | C1.4 纯 ASGI 请求体大小限制（含 chunked），返回统一信封 |
| `Server/app/logging_utils.py` | **新增** | M4-C | C1.4 日志脱敏（`sk-…`/`Bearer …`/`api_key=` 等） |
| `Server/app/static_site.py` | **新增** | M4-C | C5 同源托管 WebGL：MIME、预压缩 gzip、`Content-Encoding`、`Vary`、防目录穿越、API 优先 |
| `Server/app/__init__.py` 等其余 app 文件 | 未改 | 遗留 | M4-B 成果 |
| `Server/tests/test_isolation.py` | **新增** | M4-C | C1.1 双玩家隔离、容量上限、过期与清理（8 项） |
| `Server/tests/test_request_id.py` | **新增** | M4-C | C1.3 五态 + 错误响应头（12 项） |
| `Server/tests/test_concurrency.py` | **新增** | M4-C | C1.2 事件循环不阻塞、并发、异常回退、客户端释放（5 项） |
| `Server/tests/test_public_safety.py` | **新增** | M4-C | C1.4 请求体上限、chunked、脱敏、密钥不泄漏（10 项） |
| `Server/tests/test_static_site.py` | **新增** | M4-C | C5 同源静态站与 gzip/MIME/防穿越（11 项） |
| `Server/tests/test_sessions.py` | 改 | M4-C | 把编码旧 bug 的 `test_new_conversation_closes_previous_one` 改写为 `test_new_conversation_does_not_close_previous_one`（**有意的测试语义变更**） |
| `Server/tests/test_llm.py` | 改 | M4-C | provider 改异步：新增 `_generate()` 帮助函数（`asyncio.run` + `aclose`），7 处调用异步化；不引入 pytest-asyncio |
| `Server/tests/test_integration.py` | 改 | M4-C | 隔离断言改写；`NoModel` 改异步并统计调用次数 |
| `Server/tests/test_providers.py` | 改 | M4-C | `ExplodingProvider.generate` 改异步 |
| `Server/tests/conftest.py`、`test_content.py`、`test_contract.py`、`test_evidence.py`、`test_guards.py`、`test_security.py` | 基本未改 | 遗留 | M4-B 成果（`test_guards.py` 仅随限流范围改动而无结构性修改） |
| `Server/API_CONTRACT.md` | 改 | M4-C | §1.2 request_id 五态表、§2.2 `max_sessions`、§2.3 会话隔离与淘汰、§3 404/413 说明、新增 §7 M4-C 变更记录 |
| `Server/DEPLOYMENT.md` | 改 | M4-C | 环境变量表新增 `MAX_SESSIONS`、`WEB_ROOT` 说明 |
| `Server/TEST_RESULTS.md` | 改 | M4-C | 追加 §6 M4-C 后端记录（77→123） |
| `Server/.env.example` | 改 | M4-C | 新增 `MAX_SESSIONS=512`（仍全为占位值，无真实密钥） |
| `Server/requirements.txt` | 未改（历史改动） | 遗留 | M4-B 记录依赖，本轮未新增依赖 |

> 后端未引入任何新的第三方依赖：异步化使用标准库 `asyncio` 与已有 `httpx`；并发测试用 `httpx.ASGITransport` + `asyncio.run`，不依赖 pytest-asyncio。

---

## 2. Unity（`EchoLostAndFound_WebGL/`）

### 2.1 新增脚本

| 文件 | 变更 | 归属 | 原因 |
| --- | --- | --- | --- |
| `Assets/Station/StationTargets.cs` | **新增** | M4-C | 场景标签 ↔ 目标 ↔ 证据/NPC 映射（怀表/维修柜/失物包/副联册/老周/林遥） |
| `Assets/Station/StationInvestigationGates.cs` | **新增** | M4-C | C2 观察门槛（钢印编号、背刻、故障卡索引）判定，供 HUD 与测试复用 |
| `Assets/Station/StationApiClient.cs` | **新增** | M4-C | C3.1 网络层（5 个端点、协程、手工超时、`X-Request-ID`、信封解析、base URL 解析） |
| `Assets/Station/StationDialogueBridge.cs` | **新增** | M4-C | C3.2/3.4 在线会话编排、版本校验、离线回退、证据镜像、回复标注 |

### 2.2 修改脚本与资源

| 文件 | 变更 | 归属 | 原因 |
| --- | --- | --- | --- |
| `Assets/Station/StationHud.cs` | 大改 | M4-C | 统一 `Interact(IInteractable)` 入口；怀表五部位逐一查看；失物包/副联册/维修柜二级菜单；自由输入行 + 「发送」+ 状态行；UI 事件模块 `AssignDefaultActions`；出示后镜像披露 |
| `Assets/Station/StationPlayer.cs` | 改 | M4-C | 交互分派改为 `BeginInteraction`；输入框聚焦时 E/Esc 不关闭面板（`hud.IsTyping`）；新增 `M4C probe pos/yaw/pitch/target` 导航日志 |
| `Assets/Station/Editor/SceneSetup.cs` | 改 | M4-C | 新增林遥、西值班窗、失物包、副联册等灰盒道具与交互体 |
| `Assets/Station/Scenes/Station.unity` | 重新生成 | M4-C | 由 `Echo/Generate WebGL station` 重建（218,223 B） |
| `Assets/_Project/Resources/M4A/StationChinese SDF.asset` | 重新烘焙 | M4-C | 新增中文字符后重烘（520 字，2,369,239 B） |
| `Assets/_Project/Resources/M4A/StationChinese.ttf` | 未改 | 遗留 | M4-A 子集字体源 |
| `Assets/Tests/Editor/M4CInvestigationTests.cs` | **新增** | M4-C | 9 项调查规则测试（乱序查看、门槛、D02/D03 唯一触发、整章可收集） |
| `Assets/Tests/PlayMode/M4CStationPlayTests.cs` | **新增** | M4-C | 2 项场景可达性测试（失物包/副联册/索引/林遥） |
| `Assets/Tests/PlayMode/M4COnlinePlayTests.cs` | **新增** | M4-C | 3 项自由输入 UI 测试 |
| `Assets/Tests/PlayMode/M4AStationPlayTests.cs` | 改写 | M4-C | 适配新 HUD API（`Interact` + 逐部位 `ActivateChoice`） |
| `Assets/Station/M2Interactable.cs` | 未改（历史改动） | 遗留 | M4-A 引入 `Document` 种类 |
| `Assets/Station/Station.Runtime.asmdef` | 未改（历史改动） | 遗留 | M4-A/B 已加入四个项目 asmdef 引用 |
| `Assets/Tests/Editor/M3A.EditMode.asmdef` | 未改（历史改动） | 遗留 | 同上 |
| `Assets/Station/StationInput.inputactions` | 未改（历史改动） | 遗留 | M3-A/M4-A 输入资产 |
| `Assets/Station/Materials/*.mat`（5 个） | 未主动修改 | 遗留 | Unity 导入时同步 `_Color` 字段（值等价，无视觉变化） |

### 2.3 包清单（需技术负责人知悉）

| 文件 | 变更 | 归属 | 原因 |
| --- | --- | --- | --- |
| `Packages/manifest.json` | 增加 1 行 | M4-C | `"com.unity.modules.unitywebrequest": "1.0.0"` —— Unity 6 的内建模块需显式声明，否则 `UnityWebRequest` 编译报 `CS1069`；**这是 C3 编译所必需的最小包清单变更**，未升级任何包版本、未更换渲染管线 |
| `Packages/packages-lock.json` | 自动 | M4-C | 解析上述内建模块时由 Unity 自动写入 |

### 2.4 新增 .meta

Unity 为新脚本/资源生成的 `.meta`（`StationTargets.cs.meta`、`StationInvestigationGates.cs.meta`、`StationApiClient.cs.meta`、`StationDialogueBridge.cs.meta`、`M4CInvestigationTests.cs.meta` 等）随工程保留，未手工编辑 GUID。

---

## 3. 部署（`Deploy/`，全部新增）

| 文件 | 原因 |
| --- | --- |
| `Deploy/Dockerfile` | C5 单镜像：FastAPI `/api/v1` + WebGL 静态页 `/`，非 root，`EXPOSE 7860`，内置 HEALTHCHECK |
| `Deploy/build.ps1` | 组装构建上下文 `Deploy/context`（`server/` + `webgl/`），可选 `-Build`；兼容 Windows PowerShell 5.1（`$PSScriptRoot` 为空时回退 `$PSCommandPath`/`$MyInvocation`），脚本存为 UTF-8 with BOM |
| `Deploy/.dockerignore` | 排除缓存/日志/`.env`，**不**排除 `server/`、`webgl/` |
| `Deploy/.gitignore` | 忽略生成的 `context/`（避免 21 MB 中间产物进版本库；未改动根 `.gitignore`） |
| `Deploy/docker-compose.yml` | 本地等价编排（`7860:7860`、`MODEL_PROVIDER=mock`、`WEB_ROOT=/app/web`） |
| `Deploy/README.md` | 结构说明、构建/运行命令、环境变量表、魔搭注意事项与风险 |

---

## 4. 验收证据（`M4C/`，全部新增）

| 路径 | 内容 | 是否应入库 |
| --- | --- | --- |
| `M4C/Scripts/m4c-e2e.mjs` | 零依赖 CDP 端到端驱动（online/offline/resume 三阶段） | 建议入库 |
| `M4C/Scripts/probe-typing.mjs` | 输入能力探针（确定 Unity WebGL 的键盘注入方式） | 建议入库 |
| `M4C/Logs/` | pytest / Unity 编译、EditMode、PlayMode、WebGL 构建、服务日志 | 建议入库（体积约 8 MB）或按需归档 |
| `M4C/E2E/<run>/` | 每组运行的 `browser.json` + PNG 截图（含关键交互截图） | 建议入库（关键截图）或仅保留 `online-05`/`gpu-02`/`offline-03`/`resume-03`/`container-01` |

---

## 5. 未改动（明确声明）

- 原始 HDRP 工程 `G:\projects\EchoLostAndFound\Assets`、`Packages`、`ProjectSettings` 未做任何修改（该工程当时被 Unity GUI 进程 PID 8272 占用，全程只读）。
- M3-B 稳定模块 `Assets/_Project/Scripts/M3B/**`（EvidenceSystem / DialogueSystem / MockAIProvider / Shared）零改动。
- `Assets/_Project/Resources/M3B/*.json` 内容零改动（剧情、证据、披露规则保持原样）。
- 根 `.gitignore`、`AGENTS.md`、`.codex/` 未改动。
- 未删除任何场景、资源或既有测试文件。

---

## 6. 建议的后续整理（不擅自执行）

1. 由 Game Director 决定是否把 `Deploy/context/` 之外的新增物（`M4C/`、`Deploy/`）纳入版本库，以及 `M4C/Logs`、`M4C/E2E` 的入库策略。
2. `Packages/manifest.json` 的单行内建模块声明建议随本轮一并提交，否则新建的 `StationApiClient.cs` 无法编译。
3. 若后续引入真实模型，`Server/.env` 只保留在运行环境，`LLM_API_KEY` 绝不写入 `.env.example` 之外的任何文件。
