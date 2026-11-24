# M4-B 测试结果（真实验证记录）

记录时间：2026-11-23（Asia/Shanghai）
执行人：DSH AI 后端工程师（agent）
工作目录：`G:\projects\EchoLostAndFound\Server`

本文件记录**实际执行**的测试与运行证据。未执行的项目在“未验证项”中明确列出；本交付没有把 Mock 调用声称为真实模型测试。

## 1. 环境

| 项目 | 值 |
|---|---|
| 操作系统 | Windows-11-10.0.26200-SP0（win32） |
| Python | 3.12.14（Microsoft Store-free 运行时） |
| 虚拟环境 | `Server\.venv`（由上一行 Python 创建） |
| pip | 25.0.1 |
| pytest | 9.2.0（pluggy 1.7.0） |
| FastAPI / Starlette / Pydantic | 0.165.0 / 1.10.0 / 2.14.4 |
| Uvicorn / httpx | 0.54.0 / 0.28.1 |

安装来源为 PyPI（https://pypi.org/simple/），未使用未经验证的第三方依赖；依赖清单固定在 `requirements.txt` 与 `requirements-dev.txt`。

## 2. 单元 / 契约 / 集成测试

命令：

```powershell
Set-Location G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest
```

实际输出（结尾）：

```text
77 passed, 1 warning in 0.95s
```

唯一 warning：

```text
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

该 warning 来自 FastAPI 自带的 `TestClient` 兼容层，不影响被测服务代码；`pytest.ini` 未把它升级为错误。逐条明细见 `pytest-verbose.txt`（77 个测试名称与耗时）。

按文件分布：

| 文件 | 数量 | 覆盖内容 |
|---|---|---|
| `tests/test_content.py` | 5 | 内容版本、NPC 白名单、已批准台词逐字一致、D 规则需求集合、证据字段索引 |
| `tests/test_contract.py` | 11 | 响应 envelope、错误码、X-Request-ID、CORS、404 包络 |
| `tests/test_evidence.py` | 9 | D01/D02/D03/REC 出示触发、重复出示、未授权证据、无效证据编号、不得授予证据 |
| `tests/test_guards.py` | 6 | 本机令牌、Authorization 头不被误用、限流 429、413、非法 JSON |
| `tests/test_integration.py` | 3 | 双 NPC 全流程、会话不持久、固定内容不调用模型 |
| `tests/test_llm.py` | 8 | 真实 Provider 适配层（假 transport）：输出校验、超时、上游 5xx、密钥不泄漏 |
| `tests/test_providers.py` | 10 | Mock Provider：确定性、超时/错误/非法输出/越权内容、证据门槛 |
| `tests/test_security.py` | 12 | 模型输出白名单、危险片段、拒绝授予证据/指令字段 |
| `tests/test_sessions.py` | 13 | 开场白、话题锁定、单输入校验、关闭/取消/过期、400/404/409/410 |

关键行为验证（全部通过）：

- 老周 B01、D01、D03，林遥 D02、表背辨认台词与 `Docs/Chapter01ImplementationMap.md` 逐字一致。
- D02 必须由林遥同时看到 E03 与 E04 才触发；老周出示 E03+E04 只做核对、不产生新剧情台词。
- 重复出示同一批证据：`already_presented=true`、`newly_presented_field_ids=[]`、`event_ids=[]`，不重复触发 D。
- 证据不能由模型授予：响应中不存在 `registered_evidence_ids`/`granted_evidence_ids`；模型输出里的 `evidence_ids`、`rule_commands` 等额外键被拒绝。
- Mock 回复一律带 `provider.id="mock-deterministic"` 与 `is_synthetic=true`，文本含“模拟回复·仅测试”。
- 模型不可用/超时/非法输出/不安全输出时返回 200 的 completed turn，带 `fallback_reason`，不伪装为成功生成。
- 密钥只进入 Provider 的 `Authorization` 请求头；测试断言它不出现在请求体、错误响应、日志可导出字段中。
- 会话按服务端 UUID 管理，其他进程/实例不可见；TTL 过期后请求返回 410 `TURN_EXPIRED`。

## 3. 真实进程运行验证（uvicorn + httpx）

启动（后台进程）：

```powershell
$env:MODEL_PROVIDER = "mock"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:8080"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

实际结果：

```text
health 200 story-v1.0-phase2
       provider {'kind': 'mock', 'id': 'mock-deterministic', 'is_synthetic': True}
meta   200 access-control-allow-origin: http://localhost:8080
create 201
turn   200 source=fixed_line
preflight 200 access-control-allow-origin: http://localhost:8080
```

说明：这次运行是真实的 HTTP 进程外调用（不是 TestClient），验证了 ASGI 入口 `app.main:app`、CORS 预检、固定台词回合与服务端会话创建。测试结束后已终止该后台进程。

## 4. 未验证项（明确声明）

| 项目 | 状态 | 原因 |
|---|---|---|
| Docker 镜像构建 / 容器运行 | 未验证 | 本机没有 Docker 引擎；`Dockerfile`、`Dockerfile.modelscope`、`docker-compose.yml` 未实际构建 |
| 真实 LLM 调用 | 未验证 | 没有 API Key；仅用 `httpx.MockTransport` 验证适配层行为 |
| ModelScope 创空间实际上线 | 未验证 | 需要平台账号、实名认证与公网部署，未在本次执行 |
| Unity WebGL 客户端联调 | 未验证 | 约束要求不修改 Unity 工程；仅提供 `UnityIntegrationGuide.md` |
| HTTPS / 反向代理 | 未验证 | 属于部署环境配置，未在本机执行 |
| 长期运行内存与并发压测 | 未验证 | 仅有滑动窗口限流单元测试，未做压测 |

以上未验证项没有被描述为已通过。

## 5. 结论

- 服务端代码、内容数据与测试套件在 Python 3.12.14 下**实际运行并通过 77/77**。
- 固定台词、D 规则、证据门槛、失败回退与安全限制均有可执行测试覆盖。
- Mock 结果与真实模型结果在响应中明确区分（`is_synthetic`、`provider.kind`），不存在“Mock 冒充真实模型”的情况。

## 6. M4-C 追加记录（C1：后端稳定性修复）

记录时间：2026-11-23。执行命令与 M4-B 相同（`Server` 目录下 `.\.venv\Scripts\python.exe -m pytest`），未新增第三方依赖（`requirements-dev.txt` 仍只有 pytest），并发/异步测试用 `asyncio.run(...)` 驱动 `httpx.ASGITransport`，因此无需 pytest-asyncio。

| 项目 | M4-B | M4-C |
|---|---|---|
| 用例数 | 77 | **112**（77 保留 + 35 新增） |
| 结果 | 77 passed | **112 passed, 1 warning in 2.98s** |
| 新增测试文件 | — | `tests/test_isolation.py`、`tests/test_request_id.py`、`tests/test_concurrency.py`、`tests/test_public_safety.py` |

C1 修复与验证对应关系：

1. **多玩家会话隔离**：`SessionStore.create()` 不再关闭其他会话；新增 `MAX_SESSIONS` 上限、已结束会话保留期清理与淘汰策略。`tests/test_isolation.py` 覆盖双玩家并存、各自证据/披露/取消互不影响、容量淘汰、过期会话释放名额。
2. **模型请求不再阻塞事件循环**：`NpcAiProvider.generate` 与 `DialoguePolicy.respond` 改为 `async`，`LlmProvider` 使用 `httpx.AsyncClient` 并懒创建、`aclose()` 释放。`tests/test_concurrency.py` 用 0.4s 慢 provider 证明慢回合期间 `GET /health` 仍 <0.2s 返回、固定台词不被模型阻塞、provider 异常收敛为 fallback、客户端在关停时释放。
3. **`request_id` 头/体规则**：只传头、只传体、两者一致、两者不一致（400）、两者都无（自动生成）五种情形全部有测试，且 401/404/413/422 响应也回显 `X-Request-ID`（`tests/test_request_id.py`）。
4. **公开服务安全**：新增纯 ASGI `BodySizeLimitMiddleware`（分块且未声明长度的超限请求体也返回 413）、日志密钥脱敏（`sk-…`、`Bearer …`、`api_key=…`）、`.env.example` 仅占位值、`/health` 与 `/meta` 不含密钥（`tests/test_public_safety.py`）。

测试日志：`M4C/Logs/pytest-m4c-verbose.txt`（112 条用例逐条结果）。

仍未验证：Docker 构建、真实 LLM、ModelScope 上线、Unity WebGL 客户端联调中的服务端侧（客户端部分见 M4-C 的 C3/C4 记录）、HTTPS、压测。未验证项没有被描述为通过。
