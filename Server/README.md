# EchoLostAndFound — NPC AI 服务（M4-B）

面向 Unity WebGL 的独立 NPC AI 服务端。**固定台词优先**，模型只提供非权威的桥接文本，失败安全回退；所有游戏状态判定留在确定性的 M3-B/Unity 侧。

- Python 3.12 + FastAPI + Pydantic v2 + httpx
- 无可选数据库；会话在内存（重启即失效，符合 DataSchema 的会话不持久化约束）
- Mock Provider 与 OpenAI 兼容的真实模型 Provider 可替换；无 Key 也能完整运行
- 明文密钥只存在于服务端环境变量，客户端只持有服务地址

## 快速开始

```powershell
Set-Location G:\projects\EchoLostAndFound\Server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
$env:MODEL_PROVIDER = "mock"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:8080"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

```powershell
curl.exe http://127.0.0.1:8787/api/v1/health
.\.venv\Scripts\python.exe -m pytest
```

## 目录

```text
Server/
├─ app/
│  ├─ main.py            FastAPI 入口、中间件、路由
│  ├─ config.py          环境变量 → 冻结配置
│  ├─ errors.py          DataSchema 风格错误包络
│  ├─ security.py        模型输出校验（长度、标记、危险片段）
│  ├─ schemas.py         Pydantic 严格请求模型
│  ├─ content.py         内容加载与交叉校验
│  ├─ sessions.py        服务端会话（内存、TTL）
│  ├─ rate_limit.py      滑动窗口限流
│  ├─ policy.py          固定优先 / D 规则 / 回退策略
│  ├─ providers/         mock_provider、llm_provider、factory
│  └─ content/           ch01_dialogue.json、ch01_evidence.json、mock_ai_fixtures.json
├─ tests/                77 个 pytest 测试
├─ Dockerfile            通用镜像（python:3.12-slim）
├─ Dockerfile.modelscope 创空间镜像（7860 端口、ModelScope 基础镜像）
├─ docker-compose.yml    本机容器编排
├─ requirements.txt      fastapi/starlette/pydantic/uvicorn/httpx（固定版本）
├─ requirements-dev.txt  pytest
├─ .env.example          配置模板（无真实密钥）
├─ API_CONTRACT.md       完整请求/响应、错误码、回退语义
├─ TEST_RESULTS.md       真实测试与运行记录（77/77）
├─ DEPLOYMENT.md         本机/Docker/反向代理/创空间评估
├─ UnityIntegrationGuide.md  UnityWebRequest 协程示例与 WebGL 检查清单
└─ HandoffToCodex_M4B.md 交接清单
```

## API 一览

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查（无需令牌） |
| GET | `/api/v1/meta` | 内容版本、NPC、话题、D 规则、限制 |
| POST | `/api/v1/sessions` | 创建会话，返回开场白与可用话题 |
| GET | `/api/v1/sessions/{id}` | 查询会话状态 |
| POST | `/api/v1/sessions/{id}/turns` | 固定话题或自由输入回合 |
| POST | `/api/v1/sessions/{id}/evidence` | 出示证据，确定性触发 D |
| POST | `/api/v1/sessions/{id}/cancel` | 取消会话 |

请求/响应示例与错误码见 [API_CONTRACT.md](API_CONTRACT.md)。

## 安全要点

- `Authorization`、`X-modelscope-*` 等头在创空间被平台占用；默认私网令牌头为 `X-Dialogue-Token`。
- CORS 只接受显式源，禁止 `*`。
- 请求体 ≤ 32 KiB，玩家输入 ≤ 1000 字符，模块回复 ≤ 400 字符。
- 模型输出必须是 `{npc_id,text,suggested_topic_id}`；拒绝标记、控制字符、越权片段；建议话题必须在白名单内。
- 模型不能授予证据、改变任务状态、伪造 D、执行客户端指令；这些均由服务端确定性规则与 Unity 端状态决定。
- 日志不记录请求正文与密钥；上游错误只记录状态码。

## 状态与限制

- 已验证：77/77 pytest、真实 uvicorn 进程下的 HTTP/CORS 冒烟（详见 `TEST_RESULTS.md`）。
- 未验证：Docker 构建、创空间上线、真实模型调用、Unity WebGL 联调。
- v1 回合为同步完成，不实现 DataSchema 的 202 + 轮询；`fixed_delivery_token` 保留为 `null`。差异已记录在 API 契约第 5 节。
- 会话仅在单进程内存；多副本部署时无需粘滞，但限流按副本独立计算。

## 相关文档

- `API_CONTRACT.md` — 客户端契约
- `DEPLOYMENT.md` — 部署与 ModelScope 评估
- `TEST_RESULTS.md` — 真实运行证据
- `UnityIntegrationGuide.md` — Unity 接入
- `HandoffToCodex_M4B.md` — 交接说明
- 上游 M3-B：`../M3B/README.md`、`../M3B/IntegrationGuide.md`

## 许可与内容

剧情台词来自项目已批准内容（`Docs/Chapter01ImplementationMap.md`、`Docs/DataSchema.md`）。`mock_ai_fixtures.json` 中所有文本均为**测试用合成数据**，不是正式剧情，不进入设定。

## M5-C-A 增补（2026-11）

- 新增 `APP_ENTRY_MODE=mock|live` 单一开关：默认 `mock` 且绝不访问外部模型；`live` 缺少 provider 配置、预算参数或可用账本时拒绝启动。
- 新增 SQLite 额度账本与独立代次哨兵（先记账后请求、全局/会话额度原子预留、失败计数、连续错误熔断、账本丢失/损坏/回滚一律 fail-closed，禁止自动补额度）。
- 新增 ModelScope/OpenAI 兼容 Provider：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`AI_TIMEOUT_MS`、`LLM_REQUEST_LIMIT`、`LLM_REQUEST_LIMIT_PER_SESSION` 等服务端环境变量；一次请求不重试。
- 新增四类请求限流 + 上游并发限制，以及仅在可信代理 CIDR 内采信 `X-Forwarded-For` 的客户端识别。
- 故事安全加固：模型文本二次校验，证据/披露/章节/结局状态只由确定性内容规则变更；越权、越界或不合结构输出一律拒绝并降级。
- 测试：`python -m pytest`（当前 206 项）+ 独立 Docker/fake-model 端到端 21 项，均在本机通过；真实模型与平台持久化仍未验证。
- 报告与证据：`M5CA_Reports.zip`（含 `M5CA_Delivery_Report.md` 等 8 份报告与 `evidence/`）。
