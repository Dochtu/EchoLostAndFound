# M5-C-A-R1 安全审查

范围：Prompt 内容边界、模型输出可信度、预算/账本故障域、客户端地址解析、交付包敏感信息。
所有结论都对应仓库内可复算的文件或测试，未做任何真实模型调用。

## 1. 威胁模型（本轮假设）

| 攻击者能力 | 关心的后果 |
| --- | --- |
| 玩家自由输入（含中文、越狱话术） | 套出未解锁剧情/其他 NPC 私知/系统提示 |
| 上游模型胡编 | 编造证据、编造剧情、冒充其他角色 |
| 玩家伪造 `X-Forwarded-For` | 绕过客户端/IP 维度限流 |
| 反复新建会话 | 绕过会话级预算 |
| 参与者篡改本地文件 | 回滚账本换取免费额度 |
| 交付包泄露 | API Key / Token / 私有数据库外流 |

## 2. 发给上游的内容：只由确定性权限决定

`app/knowledge.py:build_knowledge_scope` 从内容包推导每个 NPC 的可见面，**不读取任何"完整真相"文本**：

| 组成 | 来源 | 规则 |
| --- | --- | --- |
| 已知证据 | `profile.allowed_evidence_ids ∩ 玩家已取得` | 只给编号与标题，不给 `fixed_text` 全文 |
| 可用话题 | `topic.is_available(triggered, observed)` | 需满足 `requires_disclosure_ids` / `requires_observed_field_ids` |
| 已触发披露 | 会话 `triggered_disclosure_ids` | 未触发即不可见 |
| 不可见证据 | 全量证据 − 已知 | 只给数量概念，**不列举编号与标题**（列举本身就是剧透） |
| 禁用事实 | 未触发的披露文本 + 其他 NPC 的话题文本 − 本 NPC 已可用文本 | 用于输出侧比对 |

因此上游永远拿不到：完整案件真相、StoryBible、其他 NPC 的私有知识、未解锁的披露文本。
`evidence/security/prompt_samples.md` 保存了三个调查进度 × 两名 NPC 的实际 system prompt（脱敏、无密钥），
可直接肉眼核对。

### 2.1 分类预算与裁剪

`build_prompt` 分段计量（`estimate_tokens`：CJK 按 1 token、其余按 3 字符/token，再乘 1.1 后向上取整，
故意偏保守），并按 `system / evidence / history / output` 四类上限裁剪：先删证据条目，再删"未见过的物件"整段，
最后删话题条目；仍超限则**拒绝调用**（`context_budget_exceeded`），绝不截断规则文本。

已知副作用：`_RULES` 本身约 425 token，因此 `LLM_SYSTEM_PROMPT_MAX_TOKENS < ~500` 会让所有真实调用永久拒绝。
这是 fail-closed 的刻意取舍，已写入 `M5CAR1_ModelScope_Preflight.md` 的配置建议。

## 3. 模型输出校验（四层）

| 层 | 实现 | 拦截 |
| --- | --- | --- |
| 1. 结构 | `security.validate_model_reply` | 非 JSON、根非对象、未知键、`npc_id` 不匹配 |
| 2. 文本 | `security.validate_bridge_text` | 空、超长（>400）、控制字符、`<`/`>` |
| 3. 权限 | 同上（R1 新增） | 引用未持有证据 `<E\d\d>` → `unknown_evidence_cited`；命中锁定事实 → `locked_fact_disclosed` |
| 4. 兜底 | `policy._provider_turn` 二次校验 | 通过 `validate_bridge_text` 再验一次；失败转固定台词 |

任何一层失败都只会得到 `source=fallback` 的已有确定性台词，**不会**改变证据、进度、披露、结局
（`test_knowledge_safety::test_output_cannot_mutate_session_state` 固定该性质）。

## 4. 8 类语义安全场景与测试映射

`Server/tests/test_knowledge_safety.py` 共 12 个测试函数（1 个参数化 → 16 个用例），映射如下：

| 场景 | 用例（实际函数名） |
| --- | --- |
| 初始阶段索要最终真相 | `test_initial_prompt_carries_no_case_truth`、`test_reply_quoting_locked_fact_is_downgraded_to_fallback` |
| 要求扮演开发者泄露剧情 | `test_locked_or_invented_content_is_rejected`（参数化覆盖 `开发者`、`忽略上面`、`sk-` 等禁用片段） |
| 暗示/同义表达泄露未解锁事实 | `test_keyword_guard_is_not_semantic_safety`（**故意断言改写句会通过**，见第 5 节） |
| 模型输出不存在的证据/行为 | `test_locked_or_invented_content_is_rejected` 的 `unknown_evidence_cited` 用例（`E09`） |
| NPC 编造其他 NPC 的知识 | `test_other_npc_evidence_is_withheld_from_prompt`、`test_prompt_scope_follows_deterministic_progress` |
| 合法 JSON 但案件事实错误 | `test_valid_json_with_wrong_case_fact_is_rejected` |
| 不同调查进度下的权限对照 | `test_prompt_scope_follows_deterministic_progress`（stage0/1/2 三态）、`test_prompt_states_the_deterministic_contract` |
| 输出无法改变状态 | `test_model_output_cannot_change_evidence_or_progress` |
| 预算门禁（附加） | `test_prompt_budget_is_enforced_and_reported`、`test_unbuildable_prompt_refuses_without_spending_a_request` |
| 测试上游标识（附加） | `test_test_upstream_reply_is_marked_synthetic` |

## 5. 明确的残余风险（不做粉饰）

1. **关键词/子串过滤不等于语义等价。** `validate_bridge_text` 采用禁用片段 + 规范化子串比对
   （去标点、casefold、最小 8 字符），对"换一种说法"无效。测试 `test_keyword_guard_is_not_semantic_safety`
   故意让一句改写过的锁定事实**通过**，把该风险固定在测试里而不是报告里。
   缓解：锁定事实的主要出口是确定性台词，模型只输出"桥接句"；上游看不到真相段落。
2. **模型仍可输出无害但无信息的句子。** 不构成安全事件，只是体验退化，落 `fallback` 重试路径不存在（不自动重试）。
3. **`X-Test-Upstream` 头可被真实上游伪造。** 只有我们把真实上游指向 ModelScope 时才生效；危害是"真实成功被标成
   synthetic"，方向是**保守**（宁可说没连上），可接受。
4. **单进程状态。** 会话/限流/熔断都在进程内，`workers=1` 是硬约束；多 worker 会让限流和会话一致性失效。

## 6. 敏感信息扫描与 66/73 统计口径

### 6.1 本轮扫描（`M5CAR1/tools/scan_secrets.py`，独立实现，不复用旧脚本）

| 指标 | 值 |
| --- | --- |
| 考虑的文件（`files_considered`） | 227 |
| 实际扫描的文本文件（`scanned_files`） | 143 |
| 命中（`credential_hits`） | **0** |
| 跳过（`skipped`） | `not_text: 78`、`unreadable: 1` |
| 逐根分布 | `Server` 75 / `M5CAR1` 101 / `Deploy` 48 / 根文件 3 |
| 敏感文件（已排除出包） | `M5CAR1/evidence/e2e/state/*.sqlite3`（5 个私有账本） |

新增规则（覆盖 ModelScope）：

| 规则 | 正则 | 性质 |
| --- | --- | --- |
| `modelscope_token_strict` | `\bms-[0-9a-fA-F]{8}-…-[0-9a-fA-F]{12}\b` | 启发式（官方未公布格式） |
| `modelscope_token_loose` | `\bms-[A-Za-z0-9_-]{20,}\b` | 启发式，易误报，故意保留 |
| 其余 | OpenAI 风格 `sk-`、AWS `AKIA…`、Bearer 字面量、JWT、私钥块、赋值型密钥 | — |

### 6.2 66/73 不一致的成因与修正

上一轮报告写"66 文件 0 命中"，技术负责人侧复算为 73。复算证据：用**旧脚本**在**当前工作区**重跑，
输出 `scanned_files=82`、`tracked_files=1176`、0 命中（`evidence/security/legacy_scan_replay.json`）。

结论：旧脚本只输出一个无分母的计数，且扫描根固定为 `Server/app`、`Server/tests`、`Server/tools`、`M5CA`、
`Server/Docs`，随代码增长与根集合变化而漂移；"66"与"73"是两个不同时刻/不同根集合的口径，不是同一次运行的两个数。
本轮修正做法：新脚本同时输出 `files_considered`、`scanned_files`、`files_considered_per_root` 与 `skipped` 明细，
任何人可用一条命令复算出同一组数字，**口径不再漂移**。

## 7. 账本与预算的故障域（安全视角摘要）

详见 `M5CAR1_Budget_TestResults.md`。安全相关的三条结论：

1. 任何"读不懂台账"的情形都**拒绝外部调用**（`ledger_missing/corrupt/read_only/replaced/epoch_*`），
   没有自动初始化、没有自动清零。
2. 支付语义保守：usage 缺失按预留额计费（默认 1756 token/次），失败也计次，孤儿预留按最坏情况结算。
3. 唯一接受的缺口是"数据库与哨兵被一起回退到同一份旧快照"——这类回滚在形状上与合法状态完全一致，
   本机无法区分。靠 `LLM_LEDGER_EPOCH_PIN` 只能挡住"重置后再重启"，挡不住"整体快照回滚"。
   → 列为平台上线阻塞，需平台侧提供独立可信存储或外部审计。

## 8. 代理与限流安全

- 唯一责任层：`app/server_entry.py` 固定 `proxy_headers=False` + `forwarded_allow_ips=""`，
  Uvicorn 不再改写 `request.client`；应用层只在 `X-Forwarded-For` 的对端属于 `TRUSTED_PROXY_CIDRS` 时才采信。
- 已用真实 uvicorn 复现入侵路径：`proxy_headers=True` 时伪造 `X-Forwarded-For: 203.0.113.9` 会把客户端地址改成伪造值；
  固定为 `False` 后地址恒为真实对端。
- 限流三个维度（全局 / 客户端 / 新会话 / 会话回合）在 E2E P1/P2 中经受伪造头与洪水新建验证。
- 限流桶用 `OrderedDict` + `max_keys` 硬上界 + 过期淘汰，避免"随机 key 打爆内存"。

## 9. 交付包卫生

| 检查 | 结果 |
| --- | --- |
| 包含真实 API Key / Token / Cookie | 无（扫描 0 命中，`test_public_safety` 断言 health/turn 响应无密钥） |
| 包含私有 SQLite 账本 | 已排除（`build_packages.py` 显式排除 `.sqlite3`，`evidence/packages.json` 列明排除项） |
| 包含浏览器配置/用户目录 | 已排除（`chrome-profile`、`profile-*`） |
| `.env.example` | 只有占位值与说明，无真实值 |
| 打包脚本破坏性 | 新脚本拒绝覆盖已存在产物（`build_packages.py`、`build_candidate_r1.ps1`） |
