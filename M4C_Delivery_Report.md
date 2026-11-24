# M4-C 交付报告（DSH 独立执行）

- 项目：EchoLostAndFound —《回声失物招领处：末班车之后》
- 阶段：M4-C（后端稳定性修复 + 第一章调查交互补全 + Unity↔FastAPI 联调 + WebGL 真实验收 + 魔搭部署预检）
- 执行者：DSH（本轮 Codex 未参与）
- 内容版本：`story-v1.0-phase2`
- 基线提交：`4c51712 Baseline HDRP, M3-A WebGL and M3-B before M4-A integration`（分支 `master`）
- 执行顺序：C1 → C2 → C3 → C4 → C5，每部分完成后保存成果并运行测试

---

## 一、总览

| 任务 | 内容 | 状态 |
| --- | --- | --- |
| C1 | FastAPI 后端稳定性：会话隔离、异步模型调用、request_id、公开服务安全 | DONE |
| C2 | Unity 第一章调查交互补全（E01/E03/E04/E05、林遥、D02/D03 入口） | DONE |
| C3 | Unity 接入 FastAPI：网络层、状态一致性、中文自由输入、离线回退 | DONE |
| C4 | Unity/WebGL 真实验收（含真实浏览器 E2E、真实 GPU 渲染） | DONE（1 项 PARTIAL：真实 IME） |
| C5 | 魔搭统一部署预检（本地 Docker 构建 + 容器内 E2E 已验证） | DONE（公网发布 UNVERIFIED） |

状态含义：DONE＝真实验证通过；PARTIAL＝已实现但验证不足；TODO＝未实现；BLOCKED＝存在阻断；UNVERIFIED＝缺少实际运行证据。

### 关键数字

| 项目 | 结果 |
| --- | --- |
| 后端 pytest | **123 passed, 1 warning, 2.85s**（M4-B 基线 77，新增 46） |
| Unity EditMode | **15/15 passed**（其中 M4-C 新增 9） |
| Unity PlayMode | **6/6 passed**（服务在线与离线各跑一遍均 6/6） |
| WebGL 构建 | `F:\EchoBuilds\M4C-WebGL-03`，17 个文件，**21,364,584 B**，gzip，构建 2 分 41 秒，errors 0 |
| 浏览器 E2E | 5 组通过（online-05 / gpu-02 / offline-03 / resume-03 / container-01），每组 0 JS 异常、0 HTTP ≥400 |
| 真实 GPU | NVIDIA GeForce RTX 4060 Laptop GPU，ANGLE / Direct3D11（非 headless） |
| Docker | 镜像构建 exit 0，容器 `Up (healthy)`，容器内跑通完整第一章在线流程 |

---

## 二、C1：FastAPI 后端修复

代码位置：`G:\projects\EchoLostAndFound\Server`

### C1.1 多玩家会话隔离

**原问题**：`SessionStore.create()` 会把该实例上所有 `open` 会话置为 `closed`，玩家 A 新建会话即踢掉玩家 B。

**修复**（`Server/app/sessions.py`）：

- `create()` 不再触碰其他会话；会话之间只共享实例级上限。
- 存储改为 `OrderedDict` + `threading.Lock`，新增 `max_sessions`（默认 512，`MAX_SESSIONS`，范围 1..10000）。
- 内存上界：先清过期终态会话（`TERMINAL_RETENTION_SECONDS=300`），再按“最旧终态 → 最旧打开”的顺序淘汰；被淘汰的 id 之后返回 404 `NOT_FOUND`（已写入契约）。
- 新增 `Session.ended_at`、`is_terminal`、`close(conversation_id)`、`open_count()`、`__len__()`，关闭/取消/过期都会记录结束时间。
- 证据、披露、出示状态本来就是 `Session` 字段，随隔离自然互不影响。

**验证**：

- `tests/test_isolation.py`（8 项）：双会话并存、证据/披露互不影响、取消一方不影响另一方、离开一方不影响另一方、上限淘汰、终态清理、上限永不超过、过期不占位。
- `tests/test_sessions.py::test_new_conversation_does_not_close_previous_one`：原测试 `test_new_conversation_closes_previous_one` 断言的是 bug 本身，已改写为隔离断言（**这是有意的测试语义变更，见 M4C_FileChanges.md**）。
- 进程外实测（`M4C\Logs\c1-isolation-smoke.txt`）：A=老周(E02) 打开 → 建 B → A 仍 `status=open`、无出示无披露；A 出示 E02 → `D01`；B 仍干净。

### C1.2 模型请求非阻塞

**原问题**：`LlmProvider.generate` 用同步 `httpx.Client`，`DialoguePolicy.respond` 同步调用，堵住事件循环，模型超时期间所有会话一起卡住。

**修复**：

- `Server/app/providers/llm_provider.py`：改 `httpx.AsyncClient`，**首次使用时惰性创建**（避免模块导入期就建 anyio 原语），`async def generate`、`async def aclose()`（幂等），`available` 由 `settings.llm_configured and not _closed` 决定。
- `Server/app/providers/base.py` / `mock_provider.py` / `policy.py`：`NpcAiProvider.generate`、`DisabledProvider.generate`、`MockAiProvider.generate`、`DialoguePolicy.respond` 全部 `async`；`main.py` 回合路由 `turn = await policy.respond(...)`。
- lifespan 关停时优先 `await provider.aclose()`，回退同步 `close()`。
- 固定剧情（`fixed_line`）与 Mock 行为、超时与异常回退语义完全不变（仍映射 `upstream_timeout` / `upstream_status_*` / `upstream_transport_error` → `fallback_reason`）。

**验证**：`tests/test_concurrency.py`（5 项）——慢模型在飞时 `/health` < 0.20s 返回；两个会话并发总耗时 < 0.64s；模型忙时固定台词回合 < 0.20s；provider 抛异常 → `source=fallback, fallback_reason=model_unavailable`；`AsyncClient` 惰性创建且关停后释放（`_client is None`、`available is False`）。

### C1.3 request_id 五态

**原问题**：中间件无条件写入 `request.state.request_id`，导致“只传请求体”被误判为“头体不一致”而 400。

**修复**（`Server/app/main.py`）：

- 中间件额外记录 `request.state.request_id_from_header`；只有“确实带了合法请求头”才做一致性比较。
- 仅请求体：采用请求体 id 并回写 state，响应头与信封都用它。
- 仅请求头：沿用请求头 id。
- 一致：正常。不一致：400 `INVALID_REQUEST`。
- 都不传：服务端生成 UUID。
- `_json_error` 自行补 `X-Request-ID`，因此 401/413/429/422/500 与中间件级拒绝也都带头。

**验证**：`tests/test_request_id.py`（12 项）+ 真实 uvicorn 实测（`M4C\Logs\c1-http-smoke.txt`）：仅请求体 → 200 且 `X-Request-ID=body-only-002`；仅请求头 → 200；不一致 → 400 且响应头为头 id。

### C1.4 公开服务安全

- 请求体上限：新增纯 ASGI `BodySizeLimitMiddleware`（`Server/app/middleware.py`），对声明长度快速 413，对分块/chunked 请求边收边判（超限即拒，并回显 `details.limit_bytes`）。
- 异常日志脱敏：新增 `Server/app/logging_utils.py`（`redact()` + `RedactingFilter`），覆盖 `sk-…`、`Bearer …`、`api_key=`/`token=`/`secret=` 等模式，服务端 logger 默认安装。
- 限流：沿用滑动窗口，但**只作用于 `/api/v1/*`**（E2E 发现一次页面加载 10+ 静态请求会打满 burst 后 429 `loader.js`，已修）。
- 会话资源清理：见 C1.1 上限与终态清理。
- CORS：显式来源列表，暴露 `X-Request-ID`/`Retry-After`；拒绝 `*`。
- 密钥：Unity 客户端与 WebGL 产物中无任何 key（客户端只配置 base URL）；`.env.example` 仅占位值；测试用假 key `test-key-not-a-real-secret`。

**验证**：`tests/test_public_safety.py`（10 项，含 40KB→413、chunked 超限、脱敏、日志泄露、`.env.example` 占位、内容 JSON 无 key）。

### C1 验收

```
cd G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
→ 123 passed, 1 warning in 2.85s
```

完整日志：`M4C\Logs\pytest-m4c-verbose.txt`。唯一 warning 来自 Starlette `TestClient` 的 `httpx` 弃用提示，与本轮改动无关。

---

## 三、C2：Unity 第一章调查交互

代码位置：`G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL`（URP WebGL 工程）。原始 HDRP 工程未做任何修改。

### C2.1 既有流程保护

WASD/鼠标第一人称、怀表 E01、维修柜 E02、老周 NPC、D01 由 E02 触发、中文 HUD、PlayerPrefs 存档、`story-v1.0-phase2` 版本校验全部保留；PlayMode 旧用例（`M4AStationPlayTests.WatchCardSurvivesReturnAndRepairCardChangesNpcOptions`）改写为新 API 后仍通过。

### C2.2 第一章交互审计结论

依据 `Docs/Chapter01ImplementationMap.md`、`server/app/content/ch01_*.json` 与 M3-B 数据：

| 项 | 审计结论 | 实现 |
| --- | --- | --- |
| 林遥是否进第一章 | **要进**。地图明确“林遥在西值班窗旁等叫号”，且 `REC.engraving`、`D02` 都挂在林遥名下 | 场景新增 `Station visitor (linyao)`，标签「林遥」，`npc_linyao` |
| E03 来源 | 失物包 A-0641 夹层，需先“开包 + 主动看清 QH-283” | 新增「失物包」交互，未看清编号时给出提示，不直接授予 |
| E04 来源 | 柜台内失物副联册，凭 QH-283 可直取，或从 E03 记录页跳转 | 新增「副联册」交互 + E03 记录页「翻副联册的对应档位」 |
| E05 来源 | 维修柜拾物与检点联，**前置是读到故障卡背面索引**，不是“先拿 E02” | 维修柜改为二级菜单：正面卡 → 背面索引 → 照索引取 E05 |
| D02 触发 | 林遥与老周各一条分支，条件均为 E03+E04 | 未改动 JSON，仅补齐可走通的场景入口 |
| D03 触发 | 老周 E01+E05 | **保持 E01+E05，未降级为仅 E01** |

不充分内容一律未编造：剧情台词全部来自既有 JSON；新增的只有操作提示性 UI 文案（如「包口封条已经拆开…得先看清表背的钢印编号…」）。场景坐标属灰盒占位，地图 §12 明确“驻点/热点/读单/交接锚点坐标 待确认”，报告中列为待裁定项。

### C2.3 可玩流程补全

- 怀表：五个部位（表盘/背刻/编号/侧冠/冠轴损伤）逐一查看，未看清的排前，全部看清才登记 E01。
- 失物包 / 副联册 / 维修柜：按条件解锁，不满足时给出“需要先做什么”的中文提示，不授予证据。
- NPC 面板随证据变化刷新可选项与“出示”列表。
- 新文件：`Assets/Station/StationTargets.cs`（标签↔目标↔证据/NPC 映射）、`Assets/Station/StationInvestigationGates.cs`（观察门槛判定）。

**验证**：EditMode `M4CInvestigationTests`（9 项，覆盖乱序查看、编号门槛、索引门槛、D02/D03 唯一触发、整章可仅靠场景目标收集）；PlayMode `M4CStationPlayTests`（2 项）。

---

## 四、C3：Unity 接入 FastAPI

### C3.1 网络层

新文件 `Assets/Station/StationApiClient.cs`：

- 覆盖 `GET /api/v1/meta`、`POST /sessions`、`POST /sessions/{id}/turns`、`POST /sessions/{id}/evidence`、`POST /sessions/{id}/cancel`。
- 全部 `UnityWebRequest` 协程，WebGL 中无阻塞等待；超时用 `Time.realtimeSinceStartup` 手工轮询 + `Abort()`（WebGL 上 `UnityWebRequest.timeout` 不可靠）。
- 每次请求带 `X-Request-ID`，解析统一信封 `{request_id,data,error}`。
- base URL：`?api=` 查询参数 → 页面同源（`Application.absoluteURL`）→ 回退 `http://127.0.0.1:8787`。

`Packages/manifest.json` 追加内建模块 `com.unity.modules.unitywebrequest`（Unity 6 内建模块需显式声明，原工程清单未列）。这是**为编译所必需的包清单变更**，已在此明确记录。

### C3.2 数据与状态一致性

新文件 `Assets/Station/StationDialogueBridge.cs`：

- 本地 M3-B `EvidenceRegistry`/`DialogueEngine` 仍是唯一权威：证据登记、披露触发、剧情推进全部在本地结算。
- 服务端 `/evidence` 只做镜像：仅打印 `M4C mirror ok <id> disclosures=[...]` 或 `M4C disclosure mismatch ...`，不渲染服务端台词、不重放剧情事件 → 同一次出示不会两端各触发一次。
- `meta.content_version` 与 `story-v1.0-phase2` 不一致时进入离线态并提示「服务端内容版本不一致，已停用在线对话。」，游戏不崩溃。
- 会话生命周期：进入 NPC 面板 `Open()`，关闭 `Close()`（发 `/cancel`），404/410 视为过期并回到离线提示。
- 存档：证据快照仍在 PlayerPrefs，刷新/重开后 `E01…E05` 与出示列表保留（E2E 实测）。

### C3.3 自由输入 UI

- 中文 `TMP_InputField`（单行、限 200 字），占位「点这里，用中文说出你的问题…」，「发送」按钮，状态行显示连接/等待/离线。
- 等待态：按钮置灰 + 「正在等待对方回应…」，`turnInFlight` 防止重复提交；输入框聚焦时按 E/Esc 不关闭面板（`StationPlayer` 新增 `hud.IsTyping` 守卫）。
- 不向玩家显示原始错误/堆栈：网络失败显示「对方暂时没有回应。」或离线提示。
- 原有固定选项与“出示”按钮保持不变。
- 字体：新增中文后重新烘焙 TMP 字体（`Echo/Bake Chinese font asset`）→ `FONT bake chars=520 glyphs=520 atlases=1 missing=none`，`StationChinese SDF.asset` 2,369,239 B；浏览器实测无缺字（见 C4）。

### C3.4 离线回退

服务不可用时：固定剧情可跑、证据可收集、固定选项可用、证据不丢；自由输入提示「离线模式：固定剧情与证据调查仍可进行，自由输入暂不可用。」；Mock 回复明确标注 `（服务器模拟回复，非真实模型）`，绝不冒充真实 AI。

---

## 五、C4：Unity 与 WebGL 真实验收

全部为实际执行，日志与截图见 `M4C\Logs`、`M4C\E2E`。

| 步骤 | 执行 | 结果 |
| --- | --- | --- |
| 1 Unity 完整导入与编译 | `Unity.exe -batchmode -projectPath …EchoLostAndFound_WebGL` | DONE（`unity-bake-5.log`，exit 0） |
| 2 EditMode | `editmode-results.xml` | DONE 15/15 |
| 3 PlayMode | `playmode-online-results.xml` / `playmode-results2.xml` | DONE 6/6（在线）/ 6/6（离线） |
| 4 WebGL 构建 | `WebGLBuildEntry.Build`，gzip | DONE 21,364,584 B / 17 files |
| 5 本地 HTTP 服务 | `serve-webgl.mjs` 8080 + uvicorn 8790 + 容器 7860 | DONE |
| 6 浏览器真实加载 | Chrome headless SwiftShader + **headed RTX 4060 D3D11** | DONE |
| 7 E01/E02/D01 | `online-05`、`gpu-02` | DONE，D01 恰好 1 次 |
| 8 新增调查交互 | 失物包→E03、副联册→E04、索引→E05、林遥 REC.engraving/D02 | DONE |
| 9 NPC 固定话题 | 问/再问站台照明、结束对话、办表以外的事 | DONE |
| 10 自由输入 Mock 回复 | 「这两样对上了吗」→ `source=mock, synthetic=True` | DONE |
| 11 Mock 超时 | 「超时测试」→ `fallback_reason=timeout`，页面「模型回应超时」 | DONE |
| 12 关闭 FastAPI 离线 | `offline-03`（API 全停） | DONE |
| 13 重启后会话恢复 | `resume-03`（重启 8790，复用 profile） | DONE，证据 5 项全部保留 |
| 14 JS 异常/HTTP/缺字 | 全部跑批 | DONE：0 exception，0 HTTP≥400，无缺字 |

### 端到端证据

- `M4C\E2E\online-05\`：26 张截图 + `browser.json`（`completed: true`、`d01=1 d03=1 rec=1`、0 异常、20 次 API 调用）。
- `M4C\E2E\gpu-02\`：非 headless 真实 GPU，`ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Laptop GPU, Direct3D11…)`，同样 26 张截图与全绿指标。
- `M4C\E2E\offline-03\`：服务停止后固定流程、证据持久化、离线提示。
- `M4C\E2E\resume-03\`：服务重启后在线恢复、证据保留、自由输入走 `fixed_line`。
- `M4C\E2E\container-01\`：**同一容器**同时提供页面与 `/api/v1`，跑通完整第一章（C5 证据）。

关键截图（可直接打开核对）：

- `M4C\E2E\gpu-02\17-mock-reply-reply.png`：自由输入 Mock 回复 + 「（服务器模拟回复，非真实模型）」标注 + 7 个出示选项。
- `M4C\E2E\gpu-02\14-cabinet-index.png`：维修柜背面索引 → 拾物与检点联入口。
- `M4C\E2E\gpu-02\23-linyao-d02.png`：林遥 D02（「沈禾，是我妈妈…」）。

---

## 六、C5：魔搭部署预检

目录 `G:\projects\EchoLostAndFound\Deploy`：

| 文件 | 作用 |
| --- | --- |
| `Dockerfile` | 单镜像：`python:3.12-slim` + FastAPI（`/api/v1`）+ WebGL 静态站（`/`），非 root 用户，`EXPOSE 7860`，容器内 HEALTHCHECK |
| `build.ps1` | 组装 `Deploy/context`（`server/` + `webgl/`），可选 `-Build` |
| `.dockerignore` | 只排除缓存/日志/`.env`，**不**排除 `server/`、`webgl/` |
| `docker-compose.yml` | 本地等价编排，`7860:7860`，`MODEL_PROVIDER=mock` |
| `README.md` | 结构、同源原因、构建运行命令、环境变量表、魔搭注意事项 |

**已实际执行**：`docker build` exit 0（manifest `sha256:68ab62e02497…`）；`docker run` → `Up (healthy)`；`/api/v1/health` 200、`/` 200 `text/html; charset=utf-8` 5,661 B、`/Build/M4C-WebGL-03.wasm` 200 `Content-Encoding: gzip` + `application/wasm` + `Vary: Accept-Encoding, Origin`；容器内跑通完整在线第一章（`container-01`）。

**设计要点**：同源部署免 CORS；`MODEL_PROVIDER=mock` 为默认（无 key 也能完整游玩）；真实 key 只经服务端环境变量注入；公网无认证访问存在模型成本与滥用风险，README 中给出限流、`MAX_SESSIONS`、仅 Mock 公开体验等缓解建议。

**未执行**：未把镜像推送到任何注册表、未使用用户魔搭账号、未购买资源、未公网发布。

---

## 七、待裁定项（不擅自决定）

1. **灰盒锚点坐标**：地图 §12 明确“驻点/热点/读单/交接锚点坐标 待确认”。当前林遥/失物包/副联册/西窗为灰盒摆位，仅保证可达与可交互。
2. **箱签文字、暂收/回执版面**：地图未定稿，本轮未实现 A01/R01/R02 相关 UI。
3. **故障卡背面索引是否应持久化**：当前“是否读过索引”是会话内状态（证据 E05 本身持久化，不会丢），刷新后需重读索引才能再取 E05。若产品希望“读过即永久解锁”，需策展确认后改为一并写入快照。
4. **第一章完成判定**：地图写“E01 + A02 确认”，A02 不在本轮切片范围，未实现完成度结算 UI。

---

## 八、已知问题与风险

| 级别 | 问题 | 说明 |
| --- | --- | --- |
| 中 | 真实模型路径未验证 | 全程 Mock/Disabled；真实 provider 的延迟、超时、限流行为未实测（UNVERIFIED） |
| 中 | Mock 超时是瞬时返回 | `mock_provider` 无 sleep，UI 的超时路径由“行为=timeout”触发，非真实网络挂起 |
| 中 | 公网无认证 | 若开放真实模型，需限流/额度/白名单，否则有成本与滥用风险 |
| 低 | 无静态资源长效缓存 | `Cache-Control: no-store`，~21MB gzip 每次冷加载；魔搭 CDN 场景可放宽 |
| 低 | 真实 IME 未测 | 中文输入通过 CDP 逐字符事件验证（Unity WebGL 实收路径），未在真实 OS 输入法组合态下验证（PARTIAL） |
| 低 | `POST /sessions` 不接受请求体 `request_id` | 与 `/turns` 不对称（422 `extra_forbidden`），已在契约中写明 |
| 低 | 每 NPC 一个服务端会话 | 切换 NPC 会取消上一会话，属既定设计 |

---

## 九、未验证项（UNVERIFIED）

1. 魔搭创空间真实部署与平台反向代理下的 gzip/MIME 行为（仅本地容器验证）。
2. 真实外部模型 Provider（无 key，未调用任何真实模型）。
3. HTTPS/TLS 与代理后 `trust_forwarded_for` 的真实链路。
4. 压力/并发基准（仅做了功能级并发与限流测试）。
5. 真实 OS 输入法（IME）组合输入。
6. 长时间挂机会话回收（TTL 有单测，未做长跑）。

---

## 十、交付物

| 文件 | 内容 |
| --- | --- |
| `M4C_Delivery_Report.md` | 本文件：总览、逐任务说明、待裁定项、风险 |
| `M4C_CompletionMatrix.md` | 逐条完成矩阵（DONE/PARTIAL/UNVERIFIED） |
| `M4C_TestResults.md` | 后端/Unity/WebGL/E2E 测试结果与日志索引 |
| `M4C_FileChanges.md` | 全部改动文件、原因、Git 状态说明 |
| `M4C_WebGL_Report.md` | WebGL 构建与浏览器验收细节 |
| `M4C_ModelScope_Preflight.md` | 魔搭部署方案与预检结论 |
| `M4C_HandoffToCodex.md` | 移交说明与后续建议 |

配套证据：`M4C\Logs\`（编译/测试/服务日志）、`M4C\E2E\`（浏览器截图与 `browser.json`）、`M4C\Scripts\`（E2E 驱动脚本）、`Deploy\`（部署件）。

Git：本轮**未提交、未推送、未执行 reset/clean**；工作区改动清单见 `M4C_FileChanges.md`。
