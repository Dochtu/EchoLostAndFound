# M5-C-A-R1 交付报告（安全补强与真实模型试运行准备）

- 项目：EchoLostAndFound《回声失物招领处：末班车之后》
- 分支：`m5c-a-dev`，基线 HEAD `4c51712c362e18bfcf9215cea766e61731773c74`
- 本轮性质：在已验收的 M5-C-A（CONDITIONAL PASS）之上做**安全补强**，不重写 Provider、SQLite 账本、限流、熔断
- 真实模型调用：**0 次**。魔粒消耗：**0**。线上魔搭创空间：**未触碰**
- 生成时间：2026-11-25（Asia/Shanghai）

## 1. 结论摘要

| 维度 | 结论 |
| --- | --- |
| 单元/接口测试 | ✅ 278 通过 / 0 失败 / 0 跳过（基线 206，本轮 +72） |
| 本地进程级 E2E（真实 uvicorn + Fake LLM） | ✅ 25/25 通过，退出码 0 |
| Docker 镜像 | ✅ 构建并起容器通过（见 `evidence/e2e/docker_r1.log`） |
| 浏览器级 WebGL 联调 | 🟡 页面/资源/引擎启动/客户端调用 `/api/v1/meta` 已验证；**游戏内渲染与玩法未验证** |
| 敏感信息扫描 | ✅ 227 个候选 / 143 个文本文件 / 0 命中（含新增 ModelScope `ms-` 规则） |
| 平台真实模型上线 | 🔴 仍阻塞：持久化与代理拓扑两项无法在本轮证明 |

本轮**没有**解除 M5-C-A 遗留的两项上线阻塞，而是把它们从"描述性风险"变成了有代码、有测试、有证据的
**明确阻塞项**，并补齐了真实模型试运行前必须解决的预算、上下文与状态真实性问题。

## 2. 交付物清单

### 2.1 报告（`M5CAR1/reports/`）

| 文件 | 内容 |
| --- | --- |
| `M5CAR1_Delivery_Report.md` | 本文件，总览与结论 |
| `M5CAR1_CompletionMatrix.md` | 逐条要求的完成矩阵与证据路径 |
| `M5CAR1_SecurityReview.md` | NPC 语义安全、输出校验、残余风险 |
| `M5CAR1_Budget_TestResults.md` | Token/请求预算与账本故障矩阵 |
| `M5CAR1_Integration_TestResults.md` | pytest、E2E、浏览器、Docker 结果与**验收表述修正** |
| `M5CAR1_ModelScope_Preflight.md` | 魔搭平台事实、待确认项、5 次请求预检方案 |
| `M5CAR1_Handoff.md` | 交接：待授权动作、人工联调清单、后续建议 |
| `browser_smoke_report.md` | 浏览器联调探针的原始实测报告 |

### 2.2 代码包

| 文件 | 说明 |
| --- | --- |
| `ServerSource.zip` | `Server/` 源码、测试、工具、配置、部署文件（已剔除 venv/缓存/私有库） |
| `DeploymentCandidate.zip` | 独立服务端部署候选：`app/` + 依赖 + 两个 Dockerfile + compose + `.env.example` + `DEPLOY_R1.md` |
| `M5CAR1_Reports.zip` | 本报告包（报告 + evidence + tools + e2e + MANIFEST，不含本地 WebGL 大文件） |
| `M5CAR1_LocalWebGLCandidate_<时间戳>.zip` | 本地 WebGL 联调候选（17 个文件，含构建清单哈希） |
| `MANIFEST.txt` | 报告包内每个文件的 SHA256 |

本地 WebGL 候选来自既有构建 `Builds/M4C-Closeout-Player`（Unity 6000.3.29f1），
**未修改任何 Unity 工程、场景、Prefab 或美术资源**。

关于"可恢复快照"的说明：上一轮已验收的 M5-C-A 部署候选仍完整保留在 `Builds/M5CA/candidate/`（36 个文件，含
`MANIFEST.txt`），本轮未覆盖它；本轮新增的 R1 快照为 `Builds/M5CAR1/candidate-20261125-123351/`（39 个文件）与
`ServerSource.zip`。由于 `Server/` 在 Git 中几乎全部未跟踪，**R1 之前不存在可 diff 的提交基线**，
因此无法给出"R1 精确 diff"，只能给出上一轮候选与本轮快照两份实体。

## 3. 代码变更（本轮实际写入）

| 文件 | 变更 | 目的 |
| --- | --- | --- |
| `Server/app/knowledge.py` | **新增** | 确定性知识范围 + 分类预算的 Prompt 构建 + 保守 token 估算 |
| `Server/app/model_state.py` | **新增** | 真实连接状态机（禁止"配置存在即宣称已连接"） |
| `Server/app/server_entry.py` | **新增** | 唯一客户端地址责任层，固定 `proxy_headers=False`、单 worker |
| `Server/app/budget.py` | 重写（schema v2） | Token 预算、保守预留、unknown usage、代次固定、故障域与回滚检测 |
| `Server/app/config.py` | 扩展 | 上下文/系统/证据/历史/总量/预留/代次/测试上游等 9 个配置项与校验 |
| `Server/app/security.py` | 扩展 | 禁用片段扩充、锁定事实比对、未持有证据编号引用拦截 |
| `Server/app/providers/base.py` | 扩展 | `ProviderRequest.knowledge`；`ProviderResult` 的 token/usage 真实性字段 |
| `Server/app/providers/llm_provider.py` | 重写生成路径 | 上下文预算门禁、unknown usage、测试上游识别、状态上报 |
| `Server/app/policy.py` | 扩展 | 组装知识范围、把锁定事实与已持有证据传入输出校验；固定台词标记 synthetic |
| `Server/app/content.py` | 扩展 | 证据标题索引（Prompt 用标题而非真相文本） |
| `Server/app/rate_limit.py` | 重写 | 限流桶内存上界与过期淘汰 |
| `Server/app/main.py` | 修改 | health 增加 `model`/`model_status`；live 启动路径传入 `token_limit` 与 `epoch_pin` |
| `Server/app/ledger_admin.py` | 扩展 | `--token-limit` 与三值限额 |
| `Server/tools/fake_llm_server.py` | 扩展 | 响应带 `X-Test-Upstream: fake`，使 Fake 上游可被识别为 synthetic |
| `Server/Dockerfile`、`Server/Dockerfile.modelscope` | 修改 | 统一走 `python -m app.server_entry` |
| `Server/.env.example` | 扩展 | 新增配置项脱敏说明（仅占位值） |
| `Server/tests/*` | 6 个新文件（5 个测试文件 + 1 个夹具）/ 2 处修改 | 见下节 |

新增测试文件：`llm_support.py`（测试夹具）、`test_knowledge_safety.py`（16）、`test_token_budget.py`（14）、
`test_ledger_faults.py`（14）、`test_model_state.py`（14）、`test_proxy_limiter.py`（14）。

## 4. 验证证据

| 证据 | 路径 |
| --- | --- |
| pytest JUnit（278/0/0/0） | `evidence/tests/junit_r1.xml` |
| pytest 原始输出 | `evidence/tests/pytest_r1.txt` |
| 本地 E2E 25 项结果 | `evidence/e2e/e2e_r1_results.json` |
| E2E 各服务日志 | `evidence/e2e/logs/*.log` |
| Docker 构建与运行 | `evidence/e2e/docker_r1.log` |
| 浏览器探针（含 Unity 访问日志） | `evidence/browser/candidate_probe/candidate_probe.json`、`uvicorn.log` |
| 浏览器截图 | `evidence/browser/screenshot.png`、`evidence/browser/gpu_probe/*.png` |
| 敏感信息扫描 | `evidence/security/secret_scan.json`、`legacy_scan_replay.json` |
| 源码哈希清单 | `evidence/git/source_sha256.txt` |
| 打包清单 | `evidence/packages.json` |

## 5. 边界遵守（逐条）

| 强制边界 | 状态 |
| --- | --- |
| 不调用真实模型 | ✅ 所有上游均为 `httpx.MockTransport` 或本地 `fake_llm_server.py`（127.0.0.1） |
| 不消耗魔粒 | ✅ 无任何对 `api-inference.modelscope.cn` 的请求（可用扫描与日志核对） |
| 不修改线上魔搭版本 | ✅ 未登录、未部署、未改动任何创空间 |
| 不公开创空间 | ✅ 未创建/未变更可见性 |
| 不购买资源 | ✅ 无付费行为 |
| 不开发第二章 | ✅ 内容包仍为 `story-v1.0-phase2`，未新增剧情 |
| 不重做已通过的基础架构 | ✅ Provider/SQLite/限流/熔断沿用，仅补强 |
| 不覆盖 M6-B 美术工作区 | ✅ 未写入 `Assets/`、`EchoLostAndFound_WebGL/`、`M6B_*` |
| 不虚报平台/浏览器结果 | ✅ 浏览器玩法明确标记"未验证"，平台持久化明确标记"未证明" |
| 未授权不 git 提交 | ✅ 仅生成提交清单，未 `git add/commit/push` |

## 6. 未完成 / 未验证项

1. **浏览器内玩法**（两名 NPC 对话、中文输入、E01–E05、D01–D03、双路线结算、刷新恢复、404 恢复）：
   当前环境无 CDP/Playwright 驱动，headless Chrome 又因 SwiftShader 无法编译该构建的 3 个 URP shader
   而停在加载界面。已验证到"客户端在浏览器里成功调用 `GET /api/v1/meta` 200"，其余需要人工联调。
2. **平台持久化**：本地进程重启已验证；创空间 `/mnt/workspace` 之外的数据不持久的结论来自官方文档，
   未在真实创空间验证。
3. **平台代理拓扑**：`X-Forwarded-For` 行为无官方文档；保持 `TRUSTED_PROXY_CIDRS` 为空。
4. **Git 提交**：`Server/` 目前仅 3 个文件被跟踪，其余源码与 `M5CAR1/` 全部未跟踪。提交清单已给出，
   等待用户明确授权后执行（本轮禁止擅自 `git add`）。

## 7. 下一步（建议）

1. 技术负责人复核本报告与 `M5CAR1_CompletionMatrix.md`；
2. 批准后按 `M5CAR1_Handoff.md` 执行**精确文件清单**的本地 Git 提交；
3. 如需真实模型试运行，先完成平台侧两项阻塞的确认，再按 `M5CAR1_ModelScope_Preflight.md` 的 5 次请求方案执行；
4. 浏览器玩法验证建议在有人工交互的 Windows 桌面会话中按交接清单执行。

完成后停止，等待批准 M5-C-B。
