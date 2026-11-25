# M5-C-A-R1 集成测试结果

三种执行形态，全部在本机进行，**没有一次真实模型调用**：

1. 单元/接口测试：`pytest`（进程内 TestClient + `httpx.MockTransport`）
2. 进程级 E2E：真实 uvicorn 进程（生产入口 `app.server_entry`）+ 本地 Fake LLM（`127.0.0.1:19100`）
3. 浏览器级：headless Chrome 打开本地 WebGL 候选，由后端自身托管静态站点

## 1. pytest：278 通过 / 0 失败 / 0 跳过

执行：`cd Server; .\.venv\Scripts\python.exe -m pytest -q --junitxml=..\M5CAR1\evidence\tests\junit_r1.xml`
证据：`evidence/tests/junit_r1.xml`（`tests=278 failures=0 errors=0 skipped=0 time=13.143`）

| 测试文件 | 用例数 | 本轮 |
| --- | ---: | --- |
| test_budget | 16 | 沿用 + 适配 schema v2 |
| test_concurrency | 5 | 沿用 |
| test_content | 5 | 沿用 |
| test_contract | 11 | 沿用 |
| test_entry_mode | 22 | 沿用 |
| test_evidence | 9 | 沿用 |
| test_guards | 6 | 沿用 |
| test_integration | 3 | 沿用 |
| test_isolation | 8 | 沿用 |
| **test_knowledge_safety** | **16** | 新增 |
| test_ledger_admin | 5 | 沿用 + `--token-limit` |
| **test_ledger_faults** | **14** | 新增 |
| test_llm | 8 | 沿用 |
| test_llm_transport | 16 | 沿用 |
| **test_model_state** | **14** | 新增 |
| test_providers | 10 | 沿用 |
| **test_proxy_limiter** | **14** | 新增 |
| test_public_safety | 10 | 沿用 |
| test_rate_limit_m5ca | 13 | 沿用 |
| test_request_id | 12 | 沿用 |
| test_security | 12 | 沿用 |
| test_sessions | 13 | 1 处断言随固定台词 synthetic 修正 |
| test_static_site | 11 | 沿用 |
| test_story_safety | 11 | 沿用 |
| **test_token_budget** | **14** | 新增 |
| 合计 | **278** | 基线 206 → +72 |

## 2. 进程级 E2E：25/25 通过

执行：`Server\.venv\Scripts\python.exe M5CAR1\e2e\run_e2e_r1.py`（退出码 0）
证据：`evidence/e2e/e2e_r1_results.json`（`passed: true`、`real_model_called: false`）、`evidence/e2e/logs/*.log`

| 组 | 检查 |
| --- | --- |
| M0–M7（8） | 生产入口启动；health 契约；E01–E05 逐件出示；D01–D03 + REC.engraving 触发；**新 HTTP 客户端读到同一服务端会话**（明确不是浏览器刷新）；同 NPC 双会话隔离；固定台词标记 synthetic；两种证据顺序都能到达 D01–D03（服务端前置，明确不是 Unity 结局） |
| L0–L7（8） | live 启动；配置就绪 ≠ 已验证；Fake 上游成功仍标记 synthetic；密钥不出现在信封；401/429/500 各自降级且恰好 1 次调用；超时降级并计数；模型失败后仍能提供固定内容；health 报出已结算 token |
| R1–R3（3） | 代次与用量跨进程重启保持（**明确不是平台持久化**）；重启后旧会话 404；新会话可用 |
| B0–B3（4） | 紧预算启动；请求上限强制且之后 0 次上游调用；Token 上限在调用前拒绝；台账损坏时拒绝启动 |
| P1–P2（2） | `--no-proxy-headers` 语义下伪造 XFF 不能换取新桶；洪水新建会话不能绕客户端预算 |

## 3. 验收表述修正（对照上一轮）

上一轮 `M5CA/e2e/run_e2e.py` 的 21 项检查存在"服务端能力被表述为客户端/平台能力"的问题。本轮逐条改写：

| 上一轮表述（问题） | 本轮表述 |
| --- | --- |
| "刷新/存档恢复保留服务端会话状态" | "a NEW plain HTTP client reads the same server-side session state (**this is NOT a browser refresh or save restore**)" |
| "两条保管路线均可达成结局" | "D01–D03 are reachable in both evidence orders (**server-side prerequisites only, NOT a Unity ending**)" |
| "live 模式接入真实模型" | "the Fake upstream answers a free turn, and the service still reports it as synthetic: **a Fake LLM is NOT a real model**" |
| "重启后持久化通过" | "the ledger generation and usage survive a process restart (**local process only, NOT platform persistence**)" |
| "重启用旧会话 404" | "after a restart the old conversation id returns 404, so **the client must re-establish the session (server-side only)**" |

其余修正：`source` 取值统一为 `fixed_line`；固定台词 `provider.kind=mock`、`provider.id=fixed-line-content`、
`is_synthetic=true`（审批过的固定内容不是模型回答）。

## 4. 浏览器级：已验证到"客户端与后端接通"，玩法未验证

执行脚本：`M5CAR1/tools/candidate_probe.py`、`M5CAR1/tools/render_probe.py`、`M5CAR1/tools/browser_smoke.py`
证据：`evidence/browser/candidate_probe/{candidate_probe.json,uvicorn.log}`、`evidence/browser/screenshot.png`、
`evidence/browser/gpu_probe/*.png`、`reports/browser_smoke_report.md`

关键发现：`M4C-Closeout-Player.data.gz` 中固化 API 基址 `http://127.0.0.1:8787`，端点 `/api/v1/meta`、
`/api/v1/sessions`、`/api/v1/sessions/{id}/cancel`。因此把后端起在 8787 并由其托管静态站点后，页面与 API 同源。

| 观测项 | 结果 | 证据 |
| --- | --- | --- |
| `/` 返回 WebGL 页面 | ✅ 200，5689 B，与本地副本字节一致 | `candidate_probe/uvicorn.log` |
| 资源加载 | ✅ `loader.js`、`framework.js.gz`、`wasm.gz`、`data.gz`、`TemplateData/*` 全部 200 | 同上 |
| 引擎启动 | ✅ `Initialize engine version: 6000.3.29f1`、`Creating WebGL 2.0 context`、`Loading player data` | `evidence/browser/chrome_probe_stderr.log` |
| DOM 含画布 | ✅ `<canvas id="unity-canvas">` | `evidence/browser/dom.html` |
| **Unpacked 客户端调用后端业务接口** | ✅ `GET /api/v1/meta` **200**（来自浏览器内的 Unity 客户端） | `candidate_probe/uvicorn.log` |
| 3D 场景渲染 | ❌ 未证明。headless SwiftShader 无法编译该构建的 3 个 URP shader；换 D3D11 后进度条推进到约 38%，截图仍停在加载界面 | `screenshot.png`、`gpu_probe/angle_d3d11_gpu.png` |
| 交互玩法（对话/输入/证据/结算/刷新恢复） | ❌ 未验证，无输入注入驱动（无 Playwright/CDP 客户端） | — |

截图客观指标：1280×800、592 种颜色、sha256 `8315ab90…eb39`（Unity 加载界面，进度条为空）；
D3D11 变体 624 种颜色、进度条约 38%。

## 5. Docker

| 项 | 结果 |
| --- | --- |
| 镜像构建 | ✅ `docker build -t echolostfound-npc-ai:r1 Server`（`Successfully installed … uvicorn-0.54.0`） |
| 容器启动 | ✅ `INFO: Uvicorn running on http://0.0.0.0:7860`（走 `app.server_entry`） |
| `GET /api/v1/health` | ✅ 200，返回完整 health 信封（`service_instance_id`、`entry_mode` 等） |
| `GET /` | 404 —— 预期：镜像未设置 `WEB_ROOT`，容器不托管静态站点 |
| 清理 | ✅ 容器已 `docker rm -f`；镜像保留以便复现 |

证据：`evidence/e2e/docker_r1.log`。

## 6. 结论

服务端行为（预算、账本、降级、限流、代理、状态真实性、知识边界）已由 278 项单元测试 + 25 项进程级 E2E 覆盖，
并且 Docker 镜像可用。浏览器侧只证明了"页面与资源可加载、引擎可启动、客户端确实调用了后端业务接口"，
**没有证明任何玩法路径**；该项作为联调验收阻塞记录，不冒充通过。
