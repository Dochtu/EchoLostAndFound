# M5-C-A 完成矩阵

状态图例：
- ✅ 完成并已实测（附证据）
- 🟡 完成代码与本地测试，但平台项未验证（上线阻塞）
- ⛔ 未执行（受硬性约束，禁止执行）

验收日期：2026-11-25（本地 Windows + Docker Desktop）
测试基线：`Server` 206 passed；Docker E2E 21/21 passed（`Builds/M5CA/candidate/evidence/e2e_results.json`）。

---

## 2. 工程保护前置任务

| # | 要求 | 状态 | 证据 / 说明 |
| --- | --- | --- | --- |
| 2.1 | 核对 Git HEAD、工作区与 M5BR1 备份 | ✅ | `M5CA/evidence/git/status-all.txt`；HEAD `4c51712c362e18bfcf9215cea766e61731773c74`；M5BR1 zip 与 SHA256 文件在根目录 |
| 2.2 | 创建独立 M5-C 开发分支/工作区 | ✅ | 分支 `m5c-a-dev`；未触碰 Codex 美术目录；独立候选位于 `Builds/M5CA/candidate` |
| 2.3 | 不覆盖 M5-A 候选与可运行 Mock 版本 | ✅ | `Builds/M4D-Dev/M5A/candidate` 未修改；新候选使用独立目录与 compose 项目名 |
| 2.4 | 应用复核过的 .gitignore 安全补丁 | ✅ | `.gitignore` 追加 14 条；覆盖 edge-profile、pkg、sqlite、zip、临时目录、evidence |
| 2.5 | 排除浏览器配置、pkg、重复报告、缓存、DB、凭据、构建产物 | ✅ | 同上；`git status` 中不再出现 `M5B/edge-profile`、`M5B/r1/pkg` |
| 2.6 | 检查敏感文件是否进入索引或历史 | ✅ | `M5CA/evidence/git/history-sensitive.txt`；`secret-scan.json`：`sensitive_tracked_files: []` |
| 2.7 | 重新生成精确提交清单并执行敏感信息扫描 | ✅ | `M5CA/evidence/git/status-m5ca.txt`；`scan_secrets.py`：66 文件，0 命中 |
| 2.8 | 源码入库、WebGL 构建产物独立发布 | ✅ | 候选只含 `Server/app` 与部署文件；WebGL 未重新构建、未纳入本轮 |
| 2.9 | 删除浏览器配置、提交/推送需用户明确授权 | ✅ | 未执行任何 `git add/commit/push`，未删除浏览器目录；仅创建分支（用户已授权开发分支） |
| 2.10 | 不执行 add -A / reset / clean / 历史重写 | ✅ | `git reflog` 无 reset/clean；仅 `switch -c` |

> 注：当前基线仓库从未把 `Server/` 纳入索引（除 `requirements.txt` 为 modified），因此 `Server` 全部源码在 `status` 中显示为 untracked，这是既有状态，本轮未改变。提交清单已生成，等待明确授权后执行。

---

## 3. 显式 AI 模式切换

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 3.1 | 统一入口 `APP_ENTRY_MODE=mock\|live`，默认 mock | ✅ | `config.py`/`entry.py`；`test_entry_mode.py::test_default_env_is_mock_mode` |
| 3.2 | Mock 无条件屏蔽外部模型调用 | ✅ | mock 路径从不构造 `LlmProvider`；`test_mock_mode_makes_zero_network_calls` 用禁止性替身证明零调用 |
| 3.3 | 非法模式拒绝启动 | ✅ | `test_invalid_entry_mode_refused`、`test_mock_refuses_llm_provider` |
| 3.4 | Live 需合法 provider/Key/预算/可用账本 | ✅ | 参数化 10 组拒绝用例 + 三种账本故障（缺失/代次/不可写）启动拒绝 |
| 3.5 | 真实模型未就绪明确报告原因，不冒充 | ✅ | 拒绝信息含具体原因；E2E L1 区分 `game_ready` / `model_ready` |
| 3.6 | 区分游戏服务与模型服务就绪 | ✅ | health `game_ready` / `model_ready` / `model_available` / `model_mode` |
| 3.7 | 模型故障时游戏仍可继续 | ✅ | E2E L3 九类故障全部降级，L4 固定台词可用；B3 额度耗尽后仍可玩 |
| 3.8 | 健康接口非敏感字段 | ✅ | mock 与 live 实测 payload 见 `evidence/e2e/e2e_results.json`（L1/M1）；无 key |
| 3.9 | 日志/前端/健康接口不暴露 API Key | ✅ | `test_llm_key_never_appears_in_health_or_meta`；E2E L5；日志过滤器 + 上游错误只出状态码 |
| 3.10 | 保留现有 Provider 抽象 | ✅ | `providers/base.py` 协议、`factory.py`、`MockAiProvider`/`LlmProvider` 均保留，新增字段向后兼容 |

---

## 4. 魔搭兼容模型 Provider

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 4.1 | OpenAI-compatible `/chat/completions` | ✅ | `llm_provider.py`；E2E L2 使用 fake 上游返回中文 |
| 4.2 | 六个环境变量可配置 | ✅ | `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`AI_TIMEOUT_MS`、`LLM_REQUEST_LIMIT`、`LLM_REQUEST_LIMIT_PER_SESSION` |
| 4.3 | 本轮不配置真实 Key、不发真实请求 | ✅ | 全部测试使用 `httpx.MockTransport` 或本地 fake server；无外网请求 |
| 4.4 | 覆盖正常/超时/401/429/500/非法 JSON/截断/连接失败 | ✅ | `test_llm_transport.py` 16 例；E2E L3 九类 |
| 4.5 | 不使用 DGX Spark、不购买服务 | ✅ | 无相关依赖与费用 |

---

## 5. 额度保护

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 5.1 | 基于现有 SQLite RequestBudget | ✅ | `Server/app/budget.py`（自候选 `usage.py` 前移并扩展） |
| 5.2 | 先记账后请求 | ✅ | `reserve()` 在 POST 之前；失败请求仍计 1（`test_failed_attempt_still_counted`） |
| 5.3 | 全局+会话额度事务内原子预留 | ✅ | `BEGIN IMMEDIATE`；12 线程限额 4 → 恰好 4 |
| 5.4 | 单会话不得耗尽全服务 | ✅ | 配置强制 `per_session < global`；`test_greedy_session_cannot_exhaust_service` |
| 5.5 | 失败请求计入预算 | ✅ | E2E L3 九次失败后 `global_used=9`；transport 测试逐例断言 |
| 5.6 | 记录实际输入/输出 token | ✅ | `attempts.prompt_tokens/completion_tokens`；成功用例回读 12/5 |
| 5.7 | 限制输入上下文与最大输出 | ✅ | `LLM_INPUT_MAX_CHARS=800`、`LLM_MAX_OUTPUT_TOKENS=220`，payload 断言 |
| 5.8 | 不自动重试产生费用 | ✅ | 每用例断言上游 `requests == 1`；无 retry 逻辑 |
| 5.9 | 连续错误熔断 | ✅ | `breaker.py`；5×500 → open，冷却→half-open→closed |
| 5.10 | 账本不可写/损坏禁止真实调用 | ✅ | `ledger_read_only` / `ledger_corrupt` 启动拒绝；E2E B5/B6 |
| 5.11 | 丢失/清空/代次不匹配不自动恢复额度 | ✅ | 启动拒绝 + 不自动创建文件；`test_deleted_ledger_never_recreated` |
| 5.12 | 期望代次存独立可信位置 | 🟡 | sentinel JSON 与 SQLite 分离；平台上"独立可信"未验证 → 上线阻塞 |
| 5.13 | 首次初始化/重置为显式管理操作 | ✅ | `ledger_admin init/reset` 需 `--confirm`；服务不自动初始化 |
| 5.14 | 账本可靠性无法证明则禁止上线 | 🟡 | 已实现 fail-closed；魔搭持久化未实测 → 明确阻塞 |
| 5.15 | Docker VOLUME ≠ 平台持久化 | ✅ | 文档与报告明确声明；未把 VOLUME 当保证 |
| 5.16 | 实测七类场景 | ✅ | 进程重启/容器重启/删除重建/删除/损坏/权限/并发 全部覆盖（见 Budget 报告） |
| 5.17 | 30 全局 / 8 会话暂定额度 | ✅ | 默认配置与 live E2E 实际使用 |

---

## 6. 限流保护

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 6.1 | 全局请求限流 | ✅ | `test_global_limit_returns_429_with_retry_after` |
| 6.2 | 客户端请求限流 | ✅ | `test_client_limit_is_separate_from_global` |
| 6.3 | 会话对话限流 | ✅ | `test_session_turn_limit_is_per_session` |
| 6.4 | 新建会话限流 | ✅ | `test_new_session_limit` |
| 6.5 | 上游模型并发限制 | ✅ | 信号量 2；E2E B2 `max_upstream_inflight=2` |
| 6.6 | 不无条件信任 XFF | ✅ | `network.py`；`test_untrusted_peer_ignores_xff` 等 5 例 |
| 6.7 | 仅可信代理拓扑识别客户端 | ✅ | CIDR 白名单 + 右向左剥离；拒绝 `0.0.0.0/0` |
| 6.8 | 平台拓扑未确认保持安全默认并记录阻塞 | 🟡 | `TRUST_FORWARDED_FOR=false`；已列为上线阻塞 |
| 6.9 | 静态 WebGL 资源不参与模型限流 | ✅ | `test_static_site_not_rate_limited_by_model_buckets` |
| 6.10 | 单进程单实例，不引入 Redis/付费 DB | ✅ | 无新依赖；`--workers 1` |

---

## 7. AI NPC 剧情安全

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 7.1 | 保留案件真相/证据规则/知识矩阵/披露条件/两条路线 | ✅ | 内容包未改动；E2E M2/M3 全量走通 |
| 7.2 | 模型仅生成语言/受限意图/允许建议 | ✅ | 响应模型仅三字段；建议须在可用主题内 |
| 7.3 | 禁止修改证据状态 | ✅ | `test_model_cannot_grant_evidence`；E2E 状态无变化 |
| 7.4 | 禁止解锁未满足披露 | ✅ | 真相追问不解锁 `repeat_b01`；`/evidence` 是唯一通道 |
| 7.5 | 禁止改写真相 | ✅ | 模型文本不进入内容包，不落库 |
| 7.6 | 禁止修改 NPC 知识权限 | ✅ | `allowed_evidence_ids` 来自内容包；E02→林遥 409 |
| 7.7 | 禁止修改章节进度 | ✅ | 响应无进度字段；`test_model_cannot_close_session` |
| 7.8 | 禁止决定结局 | ✅ | 结算在 Unity 侧，服务端无 ending 字段 |
| 7.9 | 自动化覆盖泄露真相/伪造证据/改状态/泄露提示词/越权披露 | ✅ | `test_story_safety.py` 11 例 + `test_llm.py`/`test_security.py` |
| 7.10 | 错误/越权/非结构输出拒绝或降级 | ✅ | invalid_output / unsafe_output / fallback，HTTP 200 降级 |
| 7.11 | 不只依赖 System Prompt | ✅ | 解析层 + 文本层 + Policy 层 + 规则层四重校验 |

---

## 8. 本地端到端验收（Docker + 本地模拟模型）

| # | 项目 | 状态 | E2E 检查 |
| --- | --- | --- | --- |
| 8.1 | 默认 Mock 正常启动 | ✅ | M1 |
| 8.2 | Live 缺配置安全拒绝 | ✅ | `evidence/entry_mode/*` + `test_entry_mode.py` |
| 8.3 | Fake LLM 返回中文 NPC 对话 | ✅ | L2（`source=external_model`，中文正文） |
| 8.4 | 模型故障自动降级 | ✅ | L3 九类 + L4 |
| 8.5 | E01–E05 调查正常 | ✅ | M2 |
| 8.6 | D01–D03 披露正常 | ✅ | M2（老周 D01/D03，林遥 D02） |
| 8.7 | 两条保管路线均可结算前置 | ✅ | M3（route A / route B） |
| 8.8 | 刷新存档恢复正常 | ✅ | M4 |
| 8.9 | 会话隔离正常 | ✅ | M5 |
| 8.10 | 预算耗尽后游戏继续 | ✅ | B3 |
| 8.11 | 账本丢失后无上游请求 | ✅ | B4 |
| 8.12 | 并发不超预算 | ✅ | B2（6 上游 / 6 账本 / 2 并发） |
| 8.13 | Mock 零外部请求 | ✅ | M6（fake stats 0） |
| 8.14 | 完整安全回归 | ✅ | 206 单元/集成测试 + L3/L5 + `pytest-verbose.txt` |

说明：结算（两条路线最终结局）由 Unity 客户端确定性逻辑完成，本轮未重新构建 Unity；服务端验证的是"结算所需前置（证据、披露、字段）可达成"，未把 WebGL 结算界面当作本轮实测对象。

---

## 9. 交付物

| 交付物 | 状态 |
| --- | --- |
| 可运行源码（`Server/app` 等） | ✅ |
| 独立部署候选（`Builds/M5CA/candidate` 34 文件） | ✅ |
| 自动化测试（206 pytest + 21 E2E） | ✅ |
| 八份报告 + `evidence/` + `MANIFEST.txt` | ✅ |
| `M5CA_Reports.zip` + 外部 SHA256 | ✅（哈希见 `M5CA_Package_SHA256.txt`） |

---

## 10. 强制约束核对

| 约束 | 状态 |
| --- | --- |
| 不消耗魔粒 | ✅ 未调用平台 |
| 不进行真实模型请求 | ✅ 仅 MockTransport / 本地 fake |
| 不修改线上部署 | ✅ 未触碰线上 |
| 不公开创空间 | ✅ |
| 不购买资产/服务 | ✅ |
| 不开发第二章 | ✅ |
| 不破坏第一章 | ✅ 206 测试 + E2E 全绿 |
| 不覆盖 Codex 美术工作区 | ✅ 未修改 `Assets/_Project/Art` 等 |
| Fake 测试不冒充真实 AI | ✅ 报告与 health 均标注 `is_synthetic` |
| 平台持久化未验证标记阻塞 | ✅ |

---

## 结论

- 本地开发目标全部完成并通过实测；8.1–8.14 全部为通过。
- 仍有两项**上线阻塞**（非本地开发阻塞）：魔搭代理拓扑未确认、平台账本持久化未验证。
- 未进入真实模型线上试运行；等待技术负责人验收。
