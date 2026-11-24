# M4-C 完成矩阵

状态定义：**DONE**＝真实验证通过；**PARTIAL**＝已实现但验证不足；**TODO**＝尚未实现；**BLOCKED**＝存在阻断；**UNVERIFIED**＝缺少实际运行证据。

---

## C1 FastAPI 后端

| 编号 | 验收点 | 状态 | 证据 |
| --- | --- | --- | --- |
| C1.1 | 玩家 A 新建会话不影响玩家 B | DONE | `tests/test_sessions.py::test_new_conversation_does_not_close_previous_one`、`tests/test_isolation.py`（8 项）、`M4C\Logs\c1-isolation-smoke.txt` |
| C1.1 | 不同会话的证据/披露/对话状态互相隔离 | DONE | `test_isolation.py::test_evidence_and_disclosures_stay_per_session` 等 |
| C1.1 | 关闭/超时/取消行为正确 | DONE | `test_isolation.py`（取消、离开、过期后 410→404） |
| C1.1 | 会话数量上限与过期清理（防内存无限增长） | DONE | `max_sessions`（512，`MAX_SESSIONS`）、终态保留 300s、淘汰顺序；`test_store_never_exceeds_its_cap_even_when_all_sessions_are_open`、`test_terminal_sessions_are_purged_after_retention` |
| C1.1 | 其余 API 契约行为保持 | DONE | 123 项 pytest 全绿；`API_CONTRACT.md` §2.3 已同步 |
| C1.1 | 双用户并发回归测试 | DONE | `test_isolation.py`、`test_concurrency.py` |
| C1.2 | 同步模型调用改为非阻塞（httpx.AsyncClient） | DONE | `llm_provider.py`、`policy.py`、`main.py`；`test_concurrency.py::test_health_answers_while_a_slow_model_turn_is_in_flight` |
| C1.2 | 固定剧情/Mock 行为不回归 | DONE | 原 77 项测试全部保留通过；123 项全绿 |
| C1.2 | 超时与异常回退语义不变 | DONE | `test_providers.py`、`test_llm.py`（8 项异步化）、`test_concurrency.py::test_provider_exception_becomes_fallback` |
| C1.2 | 模型超时期间其他会话仍可响应 | DONE | 同上，`/health` < 0.20s、两会话并发总耗时 < 0.64s |
| C1.2 | 正确释放 HTTP 客户端资源 | DONE | `aclose()` 惰性创建/幂等关闭；`test_llm_client_is_created_lazily_and_released_on_shutdown` |
| C1.3 | 只传请求头 → 正常 | DONE | `test_request_id.py`、`M4C\Logs\c1-http-smoke.txt`（`hdr-only-003`） |
| C1.3 | 只传请求体 → 正常 | DONE | 同上（`body-only-002`，真实 uvicorn 200） |
| C1.3 | 两者一致 → 正常 | DONE | `test_request_id.py` |
| C1.3 | 两者不一致 → 400 | DONE | `test_request_id.py`、`c1-http-smoke.txt`（`hdr-004` → 400） |
| C1.3 | 两者均无 → 服务端生成 | DONE | `test_request_id.py`（UUID 且唯一） |
| C1.3 | 成功与失败响应都带 `X-Request-ID` | DONE | 12 项覆盖 200/400/401/404/413/422/500 |
| C1.4 | 请求体大小限制（含 chunked） | DONE | `middleware.py`；`test_public_safety.py`（声明 40KB、分块 8KB 上限各一） |
| C1.4 | 异常日志脱敏 | DONE | `logging_utils.py`；`test_public_safety.py`（`sk-`/`Bearer`/`api_key=`、caplog 校验） |
| C1.4 | 限流 | DONE | 仅作用 `/api/v1/*`；`test_guards.py::test_static_assets_are_not_rate_limited` |
| C1.4 | 会话资源清理 | DONE | 同 C1.1 |
| C1.4 | 跨域策略 | DONE | 显式来源、拒绝 `*`；容器 E2E 同源验证 |
| C1.4 | 真实 Key 不在客户端/产物/Git/日志/模板 | DONE | `test_public_safety.py`（内容与模板扫描）、Unity 客户端无 key、E2E 日志无 key |
| C1 | 全部既有 pytest + 新增测试通过 | DONE | **123 passed, 1 warning, 2.85s**；`M4C\Logs\pytest-m4c-verbose.txt` |

---

## C2 Unity 第一章调查

| 编号 | 验收点 | 状态 | 证据 |
| --- | --- | --- | --- |
| C2.1 | WASD/鼠标控制保留 | DONE | PlayMode 全流程（移动/环视/交互），E2E 实走 |
| C2.1 | 怀表 E01、维修柜 E02 保留 | DONE | `M4AStationPlayTests`、E2E `online-05` |
| C2.1 | 老周 NPC 与固定话题保留 | DONE | E2E「问站台那晚的照明 / 结束对话」 |
| C2.1 | D01 由 E02 解锁 | DONE | `d01Events=1`（online-05 / gpu-02 / container-01） |
| C2.1 | 中文 HUD 保留 | DONE | 截图 `gpu-02\17-mock-reply-reply.png` 等 |
| C2.1 | PlayerPrefs 存档 | DONE | E2E 刷新/重启后证据保留（`resume-03`） |
| C2.1 | 内容版本校验 | DONE | `EvidenceStillPersistsAndContentVersionIsChecked`；运行时版本不一致阻断在线对话 |
| C2.2 | 林遥是否进入第一章 | DONE | 依 `Docs/Chapter01ImplementationMap.md` 进入；场景对象「林遥」+ `npc_linyao` |
| C2.2 | E03 获取来源 | DONE | 失物包 A-0641，需先观察 `watch.serial_number` |
| C2.2 | E04 获取来源 | DONE | 副联册，凭编号直取 / E03 记录页跳转 |
| C2.2 | E05 获取来源 | DONE | 维修柜：正面卡 → 背面索引 → 拾物联 |
| C2.2 | D02 触发条件 | DONE | 林遥/老周各 E03+E04，JSON 未改 |
| C2.2 | D03 触发条件 | DONE | **保持 E01+E05**；`D03NeedsE01AndE05AndNeverFiresTwice` + E2E 实测 |
| C2.2 | 玩家能否自然完成调查 | DONE | 仅用场景目标即可收齐 E01–E05 并触发 D01/D02/D03/REC.engraving（`WholeChapterCanBeCollectedThroughSceneTargetsOnly` + E2E） |
| C2.2 | 不编造剧情/证据/人物关系 | DONE | 台词全部来自既有 JSON；新增仅为操作提示 UI 文案 |
| C2.3 | 场景入口、观察交互、证据登记 | DONE | 怀表五部位、失物包、副联册、维修柜二级菜单 |
| C2.3 | 出示证据与 NPC 状态反馈 | DONE | 出示列表随可见证据刷新；已出示/无补充有中文反馈 |
| C2.3 | D01 保持 E02 触发 | DONE | JSON 未改，E2E 复核 |
| C2.3 | 不通过“直接授予证据”伪造流程 | DONE | 门槛不满足时只给提示，不登记证据（PlayMode 反向用例） |
| C2.3 | EditMode/PlayMode 测试更新 | DONE | EditMode 15/15（新增 9）、PlayMode 6/6（新增 3 + 改写 1 + 新增 2） |
| C2.3 | 灰盒锚点坐标 | PARTIAL | 地图 §12 标注“待确认”，当前为灰盒摆位（功能性可达，非美术定稿） |

---

## C3 Unity ↔ FastAPI

| 编号 | 验收点 | 状态 | 证据 |
| --- | --- | --- | --- |
| C3.1 | 五个端点在 Unity 侧接入 | DONE | `StationApiClient.cs`（meta/sessions/turns/evidence/cancel） |
| C3.1 | UnityWebRequest 协程 / WebGL 兼容 | DONE | 协程 + 手工超时轮询；WebGL 浏览器实测 20 次 API 调用 |
| C3.1 | WebGL 中不阻塞等待 | DONE | 无 `Thread.Sleep`/同步 IO；等待期间 HUD 可交互 |
| C3.2 | 本地 EvidenceRegistry 权威 | DONE | 证据只在本地登记；服务端 `/evidence` 仅镜像 |
| C3.2 | 模型回复不得授予证据/推进剧情 | DONE | 自由输入只影响对话文本；E2E 中 `source=mock` 不产生新证据 |
| C3.2 | 服务端 D 规则与本地一致 | DONE | 镜像比对日志：8 条 `M4C mirror ok`，无 mismatch（online-05/gpu-02/container-01） |
| C3.2 | 避免同一次出示双端重复触发 | DONE | 服务端返回的披露 id 只比较/记录，不渲染、不重放事件 |
| C3.2 | 存档加载/NPC 会话重建/刷新一致 | DONE | E2E 多次 `loadPage()` + `resume-03` |
| C3.2 | 版本不一致安全阻断 | DONE | `meta.content_version` 校验 → 离线提示，不崩溃 |
| C3.3 | 中文自由输入 UI | DONE | `TMP_InputField` + 「发送」+ 状态行；浏览器逐字符输入实测 |
| C3.3 | 与第一人称鼠标控制不冲突 | DONE | 输入框聚焦时 E/Esc 不关闭面板（`hud.IsTyping` 守卫），PlayMode 覆盖 |
| C3.3 | 发送期间等待反馈 | DONE | 「正在等待对方回应…」+ 按钮置灰；`FreeTextSubmitAlwaysReleasesTheWaitingState` |
| C3.3 | 正常/Mock/超时/异常处理 | DONE | 三类回复均实测：`fixed_line`(resume-03)、`mock`、`timeout`；异常走「对方暂时没有回应。」 |
| C3.3 | 不允许重复提交 | DONE | `turnInFlight` + `interactable=false` |
| C3.3 | 不显示原始错误堆栈 | DONE | 只显示中文提示；E2E 0 exception |
| C3.3 | 不破坏原有固定选项 | DONE | 选项始终渲染在状态行下方 |
| C3.3 | 重新烘焙 TMP 字体并验证无缺字 | DONE | `FONT bake chars=520 glyphs=520 missing=none`；截图逐字核对无缺字 |
| C3.3 | 真实 OS 输入法（IME）组合态 | PARTIAL | 中文经 CDP 逐字符事件送达 Unity（等同提交后字符流），未验证真实 IME 组合窗口 |
| C3.4 | 固定剧情仍可运行 | DONE | `offline-03` 全流程 |
| C3.4 | 证据仍可收集、不丢失 | DONE | `offline-03`：离线取 E01（QH-283）、刷新后仍在 |
| C3.4 | 原有 NPC 选项继续工作 | DONE | 离线页展示「问站台那晚的照明 / 结束对话 / 出示 E01」 |
| C3.4 | 自由输入提示无法回应 | DONE | 「离线模式：固定剧情与证据调查仍可进行，自由输入暂不可用。」 |
| C3.4 | Mock 不冒充真实 AI | DONE | 「（服务器模拟回复，非真实模型）」+ 状态行说明 |

---

## C4 真实验收（逐步骤）

| # | 步骤 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | Unity 完整导入与编译 | DONE | `M4C\Logs\unity-bake-5.log`（exit 0，无编译错误） |
| 2 | EditMode 测试 | DONE | `editmode-results.xml` 15/15 |
| 3 | PlayMode 测试 | DONE | `playmode-online-results.xml` 6/6；`playmode-results2.xml` 6/6（离线） |
| 4 | WebGL 构建 | DONE | `unity-webgl-build-3.log`：21,364,584 B / 17 files / 2 分 41 秒 / errors 0 |
| 5 | 本地 HTTP 服务 | DONE | `serve-webgl.mjs` 8080、uvicorn 8790、容器 7860 |
| 6 | 浏览器真实加载 | DONE | headless Chrome（SwiftShader）+ **headed Chrome on RTX 4060 / D3D11** |
| 7 | E01、E02、D01 流程 | DONE | `online-05`、`gpu-02`：`d01Events=1` |
| 8 | 本轮新增调查交互 | DONE | E03/E04/E05、林遥 REC.engraving、D02（双分支） |
| 9 | NPC 固定话题 | DONE | 问/再问照明、结束对话、林遥「问表以外的事」 |
| 10 | 自由输入 Mock 回复 | DONE | 「这两样对上了吗」→ `source=mock synthetic=True` |
| 11 | Mock 超时 | DONE | 「超时测试」→ `reason=timeout`，页面「模型回应超时」 |
| 12 | 关闭 FastAPI 后离线回退 | DONE | `offline-03`（API 全停，仅静态服务） |
| 13 | 重开服务后会话恢复 | DONE | `resume-03`：在线恢复、5 项证据保留、自由输入成功 |
| 14 | JS 异常 / HTTP 错误 / 中文缺字 | DONE | 所有跑批 0 exception、0 HTTP≥400；截图逐屏核对无缺字 |
| 附 | 非 Headless 真实 GPU 渲染 | DONE | `gpu-02`：`ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Laptop GPU, Direct3D11 vs_5_0 ps_5_0)` |
| 附 | 同源容器内端到端 | DONE | `container-01`：`http://127.0.0.1:7860/` 跑通完整第一章 |

---

## C5 魔搭部署预检

| 编号 | 验收点 | 状态 | 证据 |
| --- | --- | --- | --- |
| C5 | 推荐部署目录与 Docker 配置 | DONE | `Deploy/`（Dockerfile、build.ps1、.dockerignore、docker-compose.yml、README.md） |
| C5 | 同一服务提供 WebGL 页面与 `/api/v1` | DONE | `static_site.py` 挂载 `/` + API 路由优先；容器实测 |
| C5 | 入口页面直接开始游戏 | DONE | `/` 返回 `index.html`（5,661 B），E2E 从该 URL 直接开局 |
| C5 | gzip 资源 Content-Type/Content-Encoding 正确 | DONE | `.wasm`→`application/wasm`、`.data`→`application/octet-stream`、`.js`→`text/javascript`，均带 `Content-Encoding: gzip` 与 `Vary` |
| C5 | 无真实密钥也能完整运行（Mock） | DONE | 容器 `MODEL_PROVIDER=mock`，完整第一章 E2E 通过 |
| C5 | 真实密钥仅服务端注入 | DONE | `Deploy/README.md` 环境变量说明；容器内无 key |
| C5 | 公网无认证的成本/滥用风险说明 | DONE | `Deploy/README.md` + `M4C_ModelScope_Preflight.md` |
| C5 | 本地 Docker 构建与容器验证 | DONE | `docker build` exit 0、`Up (healthy)`、容器内 E2E |
| C5 | 魔搭创空间实际发布 | UNVERIFIED | 按任务要求未上线、未使用账号、未购买资源 |
| C5 | 平台反向代理下的 gzip/MIME | UNVERIFIED | 仅本地验证，未在真实平台链路验证 |

---

## 边界与禁止项自查

| 要求 | 状态 |
| --- | --- |
| 未修改原始 HDRP 工程（`G:\projects\EchoLostAndFound` 根 Assets 等） | 遵守；Unity GUI（PID 8272）占用该工程，全程未触碰 |
| 未重写稳定的 EvidenceSystem/DialogueSystem | 遵守；M3-B 脚本零改动 |
| 未删除现有场景与资源 | 遵守；仅新增对象/脚本 |
| 未未授权修改故事设定 | 遵守；台词取自既有 JSON |
| 未下载付费资产/订阅服务 | 遵守；无新第三方依赖（后端仍为既有 requirements；Unity 仅加内建模块） |
| 未以 DGX Spark 作为运行依赖 | 遵守 |
| 未将本地测试等同公网部署成功 | 遵守；公网项标 UNVERIFIED |
| 未将 Mock 测试等同真实模型验证 | 遵守；真实模型标 UNVERIFIED |
| 未伪造运行记录或测试结果 | 遵守；所有结论有日志/截图/XML |
| 未 `git reset --hard` / `git clean -fd` / 强制覆盖 | 遵守 |
| 未自行提交或推送 | 遵守 |
