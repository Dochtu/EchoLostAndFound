# M5-C-A-R1 完成矩阵

对照用户 2026-11-25 任务书（第 2–11 节）逐条核对。状态含义：
✅ 已实现并有证据；🟡 已实现但存在明确残余/未验证面；❌ 未实现或无法证明。

## 2. 工程保护

| # | 要求 | 状态 | 证据 / 说明 |
| --- | --- | --- | --- |
| 2.1 | 延续 `m5c-a-dev` 分支 | ✅ | `evidence/git/status-all.txt`：分支 `m5c-a-dev`，HEAD `4c51712c3` |
| 2.2 | 保存可恢复快照（源码/测试/配置/部署候选） | ✅ | `ServerSource.zip`、`DeploymentCandidate.zip`、`Builds/M5CAR1/candidate-20261125-123351`（39 文件，含 `MANIFEST.txt`）；上一轮已验收候选 `Builds/M5CA/candidate/`（36 文件）原样保留未覆盖 |
| 2.3 | 重新生成源码 SHA256 清单 | ✅ | `evidence/git/source_sha256.txt`（`Server` 全部纳入包的文件） |
| 2.4 | 核对实际 Git 跟踪状态 | ✅ | `git ls-files Server` = 3、`git ls-files M5CAR1` = 0、`git status --porcelain` = 163 行；已写入 `M5CAR1_Handoff.md` |
| 2.5 | 经授权后按精确文件列表本地提交 | 🟡 | 清单已生成（`M5CAR1_Handoff.md` 第 2 节），**未执行**任何 `git add/commit`，等待授权 |
| 2.6 | 不执行 `git add -A` / push / reset / clean | ✅ | 本轮 git 只读（`status`、`ls-files`、`log`） |
| 2.7 | 不覆盖 M5-A / M6-A / M6-B / Codex 工作区 | ✅ | 未写入 `Assets/`、`EchoLostAndFound_WebGL/`、`M6B_*`、`M6C_*`；仅新增 `M5CAR1/`、`Builds/M5CAR1/` |
| 2.8 | 修正 66/73 文件扫描统计不一致 | ✅ | `M5CAR1_SecurityReview.md` 第 6 节；旧脚本复算 82，新脚本发布 227 候选/143 扫描/逐根明细 |
| 2.9 | 扩展敏感信息扫描到 ModelScope Token | ✅ | `tools/scan_secrets.py`：`modelscope_token_strict` + `modelscope_token_loose` |
| 2.10 | 检查候选组装脚本覆盖删除风险 | ✅ | 风险确认于 `M5CA/deploy/build_candidate.ps1:17-21`；新脚本 `M5CAR1/deploy/build_candidate_r1.ps1` 使用时间戳目录 + 拒绝覆盖 + reparse point 检查 |

## 3. Token 与魔粒预算保护

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 3.1 | 限制完整模型上下文大小（非仅玩家输入） | ✅ | `llm_context_max_tokens`（默认 1536）+ `_prompt_plan` 总预算门禁；`test_token_budget` 的 1024 上下文用例在调用前拒绝 |
| 3.2 | 系统提示/历史/证据分类预算 | ✅ | `llm_system_prompt_max_tokens=768`、`llm_history_max_tokens=0`、`llm_evidence_context_max_tokens=320`；`knowledge.build_prompt` 分段计量并在超限时裁剪/拒绝 |
| 3.3 | 输出 Token 上限 | ✅ | `llm_max_output_tokens=220`（32..1024）→ 请求体 `max_tokens`；`test_token_budget` 断言 64 |
| 3.4 | 全局 Token 预算 + 请求前保守预留 | ✅ | `llm_token_limit=60000`；`reserve(reserved_tokens=context+output)`；E2E B2 |
| 3.5 | usage 缺失标记 unknown，不解释为零 | ✅ | `usage_known=0`、`billing_uncertain=1`、按预留额记账；`unknown_usage_attempts` 计数 |
| 3.6 | 超时/不确定计费保守记账 | ✅ | 任何失败按预留额结算（`test_token_budget` 超时用例） |
| 3.7 | 无法证明预算有效时停止外部调用并降级 | ✅ | 台账不可用 → `available=False` 且 live 启动拒绝；上下文超限 → `context_budget_exceeded` 零调用 |
| 3.8 | 失败也计数、无自动重试 | ✅ | 失败仍 `global_used+1`；上游 401/429/500/503 均恰好 1 次调用 |
| 3.9 | 不虚构 Token 与魔粒换算 | ✅ | `M5CAR1_ModelScope_Preflight.md` 明确"官方未公布换算比例"，未写入任何换算逻辑 |

## 4. NPC 语义安全

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 4.1 | 不传完整真相/StoryBible/他人私知/未解锁披露 | ✅ | `knowledge.build_knowledge_scope`；`test_knowledge_safety` 断言初始 Prompt 不含真相段落 |
| 4.2 | 上下文由确定性知识权限 + 证据状态筛选 | ✅ | 证据按 `profile.allowed_evidence_ids ∩ 已取得`；话题按 `requires_*` 与观察字段筛选 |
| 4.3 | 模型不能创造新证据或剧情事实 | ✅ | 输出校验 `unknown_evidence_cited` + 锁定事实比对；模型输出无法改动会话状态 |
| 4.4 | 关键事实优先使用确定性台词 | ✅ | `policy._match_fixed_intent` 走固定台词，零模型调用 |
| 4.5 | 无法满足安全边界时降级 | ✅ | `source=fallback` + `fallback_reason` |
| 4.6 | 不以关键词过滤等同语义安全 | ✅ | 明确写入残余风险，并用 `test_keyword_guard_is_not_semantic_safety` 固定该事实 |
| 4.7 | 8 项新增语义安全测试 | ✅ | `test_knowledge_safety.py`：12 个测试函数 / 16 个用例覆盖 8 类场景，映射见 `M5CAR1_SecurityReview.md` 第 4 节 |
| 4.8 | 保存脱敏实际模型请求上下文证据 | ✅ | `evidence/security/prompt_samples.md` + `.json`（三个调查进度 × 两名 NPC） |

## 5. 额度账本安全

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 5.1 | 继续使用 SQLite | ✅ | `app/budget.py`（无付费数据库） |
| 5.2 | DB 与哨兵同时丢失 | ✅ | `epoch_missing`；不自动重建 |
| 5.3 | DB 与哨兵同时回退到旧快照 | 🟡 | **可被接受**（一致性快照无法与合法状态区分）；已固化为已知缺口并标记平台上线阻塞 |
| 5.4 | 哨兵高水位写入失败 | ✅ | `epoch_write_failed` → 拒绝调用并计数 |
| 5.5 | 事务提交后、哨兵更新前崩溃 | ✅ | 下次 `load` 以 `usage_count` 抬高哨兵 |
| 5.6 | 哨兵写入后、外部请求前崩溃 | ✅ | 孤儿预留按 `restart_orphan` + 保守 token 结算 |
| 5.7 | 运行中删除/替换账本 | ✅ | `_ledger_is_intact()` 对比 `st_dev/st_ino` → `ledger_missing` / `ledger_replaced` |
| 5.8 | 磁盘写满 | 🟡 | 以 `sqlite3.OperationalError("disk I/O error")` 注入验证 `ledger_write_failed`；未做真实磁盘填满实验 |
| 5.9 | 进程重启后预算一致 | ✅ | `test_budget` 重启用例；E2E R1-R3 |
| 5.10 | 独立可信配置保存预期代次 | ✅ | `llm_ledger_epoch_pin` + `ledger_admin --epoch-pin`；live 启动路径已生效 |
| 5.11 | 无法证明共同回滚保护则标记上线阻塞 | ✅ | 两条阻塞项写入完成矩阵与交接文档 |
| 5.12 | 不得自动初始化/自动重置绕过错误 | ✅ | `initialize` 需 `reset=True` 显式确认；缺失即拒绝启动 |

## 6. 代理与限流

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 6.1 | 审查 Uvicorn 自身 proxy headers 行为 | ✅ | `test_proxy_limiter` 用真实 uvicorn 复现：`proxy_headers=True` 时伪造 `X-Forwarded-For` 会改写客户端地址 |
| 6.2 | 客户端地址解析唯一责任层 | ✅ | `app/server_entry.py` 固定 `proxy_headers=False`；仅 `network.resolve_client_ip` 解析 |
| 6.3 | 验证 `--no-proxy-headers` 配置 | ✅ | 12 项代理/限流测试 + 生产入口 |
| 6.4 | 实际 HTTP 请求测试伪造 XFF | ✅ | E2E P1：伪造 XFF 得到 200/429；`test_proxy_limiter` 同上 |
| 6.5 | 连续新建会话不能绕过预算 | ✅ | E2E P2 `[201,201,429,429]`；客户端桶 + 新会话桶 + 全局桶 |
| 6.6 | 同一 NPC 多会话数据隔离 | ✅ | E2E M4；`test_isolation` |
| 6.7 | 限流器内存增长与过期桶回收 | ✅ | `OrderedDict` + `max_keys` + 过期清理；`test_proxy_limiter` 断言键数上界 |
| 6.8 | 拓扑未确认前不启用不可信转发头 | ✅ | `TRUSTED_PROXY_CIDRS` 默认空；文档明确未确认 |

## 7. 模型状态真实性

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 7.1 | 保留 `APP_ENTRY_MODE=mock|live` | ✅ | `config.py` 未改名 |
| 7.2 | Mock / Fake LLM 标记 synthetic | ✅ | Mock `is_synthetic=True`；Fake 上游经 `X-Test-Upstream` 头识别 |
| 7.3 | 真实模型需真实调用成功后才可声称已接入 | ✅ | `model_state.verified_real` 仅在真实成功计数 > 0 时为真 |
| 7.4 | 区分配置就绪/请求成功/不可用/预算耗尽/熔断 | ✅ | `model_status`: `configured_unverified` / `connected` / `upstream_error` / `budget_exhausted` / `circuit_open` / `budget_unavailable` |
| 7.5 | 禁止仅因配置存在就宣称已连接 | ✅ | 未调用时为 `configured_unverified`，`model_ready=false`；`test_model_state` 14 项 |

## 8. 测试补强与命名修正

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 8.1 | 服务端会话查询≠浏览器刷新存档 | ✅ | 新 E2E 检查名显式声明"NOT a browser refresh or save restore" |
| 8.2 | 服务端结算前置≠Unity 完整通关 | ✅ | "server-side prerequisites only, NOT a Unity ending" |
| 8.3 | Fake LLM≠真实模型 | ✅ | "a Fake LLM is NOT a real model" |
| 8.4 | 本地 Docker 卷≠平台持久化 | ✅ | "local process only, NOT platform persistence" |
| 8.5 | 使用既有 WebGL 产物创建独立本地联调候选 | ✅ | `M5CAR1/local_candidate/webgl/`（17 文件，字节一致）+ 独立 zip + 哈希 |
| 8.6-1 | 浏览器正常加载游戏 | 🟡 | 页面/loader/data/wasm 200，引擎启动日志齐全，客户端调用 `GET /api/v1/meta` 200；**3D 渲染未证明** |
| 8.6-2 | 两名 NPC 对话 | ❌ | 无输入注入能力，未验证 |
| 8.6-3 | 中文输入 | ❌ | 同上 |
| 8.6-4 | E01–E05、D01–D03（浏览器内） | ❌ | 服务端已验，浏览器内未验证 |
| 8.6-5 | 双路线完整结算（浏览器内） | ❌ | 服务端前置已验，Unity 结算未验证 |
| 8.6-6 | 浏览器刷新恢复 | ❌ | 未验证 |
| 8.6-7 | 服务端重启后旧会话 404 的客户端恢复 | 🟡 | 服务端 404 已验证（E2E R2）；客户端恢复行为未验证 |
| 8.6-8 | 模型超时/额度耗尽后仍可完整通关 | 🟡 | 服务端降级已验证（L3/L4、B1/B2、固定台词兜底）；浏览器内通关未验证 |
| 8.7 | 不修改美术工作区 | ✅ | 仅读取 `Builds/` |
| 8.8 | 需改 Unity 客户端时先给影响清单 | ✅ | `M5CAR1_Handoff.md` 第 4 节给出影响清单，未改动任何 Unity 文件 |

## 9. 魔搭平台试运行准备

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 9.1 | API Base URL 与模型 ID 核实方法 | ✅ | `M5CAR1_ModelScope_Preflight.md` 第 2 节 |
| 9.2 | API Key 服务端配置位置 | ✅ | 同上第 3 节（环境变量 / 密钥注入，禁止写入 `ms_deploy.json`） |
| 9.3 | 计费方式与魔粒余额核对方法 | ✅ | 同上第 4 节（含"官方未公布 token→魔粒 换算"的结论） |
| 9.4 | 平台持久化与代理拓扑验证方案 | ✅ | 同上第 5、6 节 |
| 9.5 | 独立私有测试候选 | ✅ | `DeploymentCandidate.zip` + `DEPLOY_R1.md` |
| 9.6 | 失败后立即回滚方式 | ✅ | 同上第 7 节 |
| 9.7 | 首轮真实调用 ≤5 次且等授权 | ✅ | 同上第 8 节（5 次方案，未执行） |
| 9.8 | 不依赖 DGX Spark | ✅ | 方案仅涉及 ModelScope 平台与本地进程 |

## 10. 强制交付物

| 交付物 | 状态 | 位置 |
| --- | --- | --- |
| `M5CAR1_Delivery_Report.md` | ✅ | `M5CAR1/reports/` |
| `M5CAR1_CompletionMatrix.md` | ✅ | 本文件 |
| `M5CAR1_SecurityReview.md` | ✅ | `M5CAR1/reports/` |
| `M5CAR1_Budget_TestResults.md` | ✅ | `M5CAR1/reports/` |
| `M5CAR1_Integration_TestResults.md` | ✅ | `M5CAR1/reports/` |
| `M5CAR1_ModelScope_Preflight.md` | ✅ | `M5CAR1/reports/` |
| `M5CAR1_Handoff.md` | ✅ | `M5CAR1/reports/` |
| `ServerSource.zip` | ✅ | 仓库根目录 |
| `DeploymentCandidate.zip` | ✅ | 仓库根目录 |
| `evidence/` | ✅ | `M5CAR1/evidence/` |
| `MANIFEST.txt` | ✅ | `M5CAR1/MANIFEST.txt` 与报告包内 |
| 统一 `M5CAR1_Reports.zip` | ✅ | 仓库根目录 |
| 本地 WebGL 候选（独立打包 + 版本/哈希） | ✅ | `M5CAR1_LocalWebGLCandidate_<时间戳>.zip` + `.sha256`，构建版本 `M4C-Closeout-Player`（Unity 6000.3.29f1） |

## 11. 强制边界

全部遵守，逐条核对见 `M5CAR1_Delivery_Report.md` 第 5 节。

## 剩余上线阻塞（2 项，均未解除）

1. **平台持久化**：`/mnt/workspace` 之外数据不持久；创空间转移/改名后仍丢失；本地 Docker 卷结论不可外推。
2. **平台代理拓扑**：`X-Forwarded-For` 透传行为无官方文档；`TRUSTED_PROXY_CIDRS` 保持为空，客户端地址按代理地址计。

此外新增 1 项阻塞：**浏览器级玩法验证未完成**（需要人工交互会话或 CDP 驱动），不作为服务端上线阻塞，
但作为"联调完成"的验收阻塞。
