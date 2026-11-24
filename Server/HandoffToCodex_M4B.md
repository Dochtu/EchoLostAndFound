# Handoff to Codex — M4-B NPC AI 服务

日期：2026-11-23
交接人：DSH AI 后端工程师（agent）
接收方：Unity/Codex 侧集成负责人、QA
工作目录：`G:\projects\EchoLostAndFound\Server`（本次唯一写入范围）

## 1. 交付范围（已完成）

在 `Server/` 下实现可独立运行的 NPC AI 服务：

- FastAPI 应用与入口 `app.main:app`（`uvicorn app.main:app`）；
- 环境变量配置（`.env.example`，无真实密钥）；
- 健康检查、内容元数据、会话、回合、证据出示、取消端点；
- Mock Provider 与 OpenAI 兼容真实 Provider，可替换；
- 固定台词优先 → 模型扩展 → 失败回退的三级策略；
- 确定性 D 规则（D01/D02/D03/REC.engraving）与重复出示处理；
- 严格模型输出校验（长度、NPC 匹配、标记/危险片段、话题白名单）；
- CORS 白名单、请求体/输入长度限制、滑动窗口限流、可选本机令牌、统一错误包络；
- 77 个 pytest 测试与真实 uvicorn 冒烟记录；
- 部署文档（含 ModelScope 创空间评估与来源链接）、API 契约、Unity 集成指南。

## 2. 未修改声明

- 未修改 `Assets/`、`ProjectSettings/`、`Packages/` 或任何 Unity 场景/Prefab。
- 未新增/修改 Unity 的 `.meta`、asmdef、`Packages/manifest.json`。
- 未执行 `git add`、`git commit`、推送或重置；没有创建 Git LFS 规则。
- 所有新增文件只在 `Server/` 内；`M3B/` 仅作为只读契约来源被引用。

## 3. 文件清单

| 路径 | 说明 |
|---|---|
| `Server/app/main.py` | FastAPI 入口、守卫中间件、路由、错误处理、CORS |
| `Server/app/config.py` | 冻结 Settings 与 `from_env()` 校验 |
| `Server/app/errors.py` | ErrorCodes、ApiError、统一错误 payload |
| `Server/app/security.py` | 模型输出校验、request_id 校验 |
| `Server/app/schemas.py` | Pydantic 严格请求模型（extra=forbid） |
| `Server/app/content.py` | 内容加载、交叉引用校验 |
| `Server/app/sessions.py` | 内存会话、TTL、关闭/取消/过期 |
| `Server/app/rate_limit.py` | 滑动窗口限流 |
| `Server/app/policy.py` | 固定优先、D 规则、Provider 调度、回退 |
| `Server/app/providers/base.py` | ProviderRequest/Result、协议、OUTCOME 常量 |
| `Server/app/providers/mock_provider.py` | 确定性 Mock Provider |
| `Server/app/providers/llm_provider.py` | OpenAI 兼容真实 Provider（httpx） |
| `Server/app/providers/factory.py` | 按配置构建 Provider |
| `Server/app/content/ch01_dialogue.json` | 服务端对话内容（已批准台词 + 结构） |
| `Server/app/content/ch01_evidence.json` | 证据目录（从 M3-B 原样复制，用于校验） |
| `Server/app/content/mock_ai_fixtures.json` | 7 个确定性测试场景（合成文本） |
| `Server/tests/` | 9 个测试文件 + conftest，共 77 个测试 |
| `Server/requirements.txt` / `requirements-dev.txt` | 固定版本依赖 |
| `Server/.env.example` | 配置模板（占位值，无密钥） |
| `Server/pytest.ini` / `.gitignore` | 测试与本地忽略 |
| `Server/API_CONTRACT.md` | 客户端契约（含示例与错误码） |
| `Server/TEST_RESULTS.md` | 真实测试/运行记录 |
| `Server/DEPLOYMENT.md` | 本机/Docker/反向代理/创空间评估 |
| `Server/UnityIntegrationGuide.md` | UnityWebRequest 协程接入与检查清单 |
| `Server/Dockerfile` / `Dockerfile.modelscope` / `docker-compose.yml` / `.dockerignore` | 容器化（未本机构建验证） |
| `Server/README.md` | 总览与快速开始 |

## 4. 运行方式

```powershell
Set-Location G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
$env:MODEL_PROVIDER = "mock"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:8080"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

另开终端：

```powershell
curl.exe http://127.0.0.1:8787/api/v1/health
curl.exe -X POST http://127.0.0.1:8787/api/v1/sessions -H "Content-Type: application/json" -d '{\"npc_id\":\"npc_laozhou\"}'
```

Windows PowerShell 中 `curl` 需写 `curl.exe`；JSON 引号按 shell 规则转义。

## 5. 验证证据

- `TEST_RESULTS.md`：77 passed（1 个来自 FastAPI TestClient 的弃用 warning），逐文件覆盖表。
- 真实 uvicorn 进程：health 200（`story-v1.0-phase2`，mock provider）、meta 200 且 CORS 头正确、create 201、固定回合 `source=fixed_line`、预检 200。
- 关键行数/断言：见各测试文件；没有“只写设计不写实现”的占位。

## 6. 未验证项（必须由后续环境补验）

1. Docker 镜像构建与运行（本机无 Docker）。
2. ModelScope 创空间实际上线（需账号/实名/公网）。
3. 真实 LLM 调用（无 Key）；仅用 `httpx.MockTransport` 验证适配层。
4. Unity WebGL 端到端（未改 Unity 工程）。
5. HTTPS/反向代理证书。
6. 并发压测与长稳测试。

## 7. Unity/Codex 集成步骤建议

1. 阅读 `API_CONTRACT.md` 与 `UnityIntegrationGuide.md`。
2. 客户端增加一个协程网络层（`UnityWebRequest`），`baseUrl` 由部署配置提供；**不要**在客户端放 Key。
3. 启动时 `GET /meta` 校验 `content_version == story-v1.0-phase2`。
4. 创建会话 → 显示 `opening_segments` → 话题回合使用 `topic_id`，自由输入使用 `text`。
5. 出示证据时，把 `EvidenceRegistry.AcquiredEvidenceIds` 的子集发给 `/evidence`；服务端返 D 台词，客户端只展示与记录，不据此改世界状态。
6. 对 `fallback_reason` 做本地 UI 策略（沉默/固定反应），不要显示技术错误。
7. WebGL 构建前设置 `CORS_ALLOWED_ORIGINS` 为页面实际源；HTTPS 页面必须配 HTTPS 服务。
8. 由 Game Director 分配 Unity 侧写入文件后，再接入 `DialogueEngine`/UI；本交付不包含任何 Unity 侧修改。

## 8. 内容状态（待确认）

- 已批准并逐字使用：老周开场、B01、D01、D03；林遥开场、表背辨认、拒绝闲聊、D02（`dialogue.CH01.D02.linyao`）。
- 内容引用中只有 `dialogue.CH01.B01.initial`、`dialogue.CH01.D02.linyao` 在 `Docs/DataSchema.md` 有登记；其余 `content_ref`（开场、D01.laozhou、D03.laozhou、linyao.engraving、linyao.refusal）为**提议值**，服务端已在 `/meta` 的 `provisional_content_refs` 暴露，需叙事负责人确认后固定。
- 证据 E02–E05 的 `source_label`/`area_id` 源自 `evidence_matrix.md` 的推导，需内容确认。
- 未新增任何剧情事实；Mock 文本明确标注“模拟回复·仅测试，非正式台词”。

## 9. 契约差异（需知）

1. 回合同步返回 200 completed，未实现 DataSchema 的 202 pending + 轮询；`fixed_delivery_token` 为 `null`。这是 v1 的设计选择，理由是固定台词与 Mock 即时返回，轮询无收益。
2. 新增 `RATE_LIMITED`、`INTERNAL_ERROR` 传输层错误码。
3. 私网令牌默认头为 `X-Dialogue-Token`，因为创空间占用 `Authorization`。
4. 会话仅内存，重启失效；客户端需处理 410 并重建。
5. 服务端不做证据授予；客户端上报的 `evidence_ids` 只是“确认持有”。

## 10. 安全注意

- 真实 `LLM_API_KEY` 只放服务端环境变量/secret；不要写入 `.env.example`、仓库、镜像、日志、客户端。
- 日志可能被平台采集；本服务不记录请求正文和密钥，但部署方仍需审查平台日志策略。
- 免费创空间无 SLA；公开试玩前建议加代理层限流与预算告警。
- 不要开启 `CORS_ALLOWED_ORIGINS=*`；不要在没有可信代理时开启 `TRUST_FORWARDED_FOR`。

## 11. 联系与下一步

建议下一步：由 QA 复核 `TEST_RESULTS.md`；由 Game Director 授权 Unity 侧文件后再做 WebGL 联调；由叙事负责人确认 `provisional_content_refs`；由运维验证 Docker/创空间上线。本 Agent 不自行进入下一阶段。
