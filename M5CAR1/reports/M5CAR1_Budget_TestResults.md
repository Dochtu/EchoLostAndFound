# M5-C-A-R1 预算与账本测试结果

对象：`Server/app/budget.py`（schema v2）、`Server/app/knowledge.py`（token 估算与分类预算）、
`Server/app/providers/llm_provider.py`（预留/结算/降级）、`Server/app/ledger_admin.py`（运维入口）。

## 1. 预算模型

### 1.1 两层预算并存

| 层 | 参数 | 语义 | 超限后果 |
| --- | --- | --- | --- |
| 请求次数 | `LLM_REQUEST_LIMIT` / `LLM_REQUEST_LIMIT_PER_SESSION` | 全局与会话的**调用次数**上限（M5-C-A 已有） | `budget_global_exhausted` / `budget_session_exhausted` |
| Token 总量 | `LLM_TOKEN_LIMIT` | 已结算 + 已预留 token 的**上限** | `budget_token_exhausted` |

### 1.2 每次调用的时序

```
reserve(session, request, reserved_tokens = llm_token_reservation)   # 预留
    ├─ BEGIN IMMEDIATE → 计数校验 → INSERT reserved 行 → usage_count+1 → token_reserved += R → COMMIT
    └─ 写哨兵 {high_water, token_high_water}    # 失败 ⇒ 禁用台账并拒绝调用
调用上游（恰好一次，无重试）
finish(attempt, completed|failed, prompt_tokens, completion_tokens, usage_known)
    ├─ consumed = prompt+completion（已知） 或 R（未知/失败/超时）
    └─ token_used += consumed；token_reserved -= R；哨兵重写
```

`llm_token_reservation` 默认 = `llm_context_max_tokens + llm_max_output_tokens` = 1536 + 220 = **1756**。

### 1.3 usage 缺失的语义

| 上游响应 | `usage_known` | `billing_uncertain` | 记账 |
| --- | --- | --- | --- |
| 完整 `usage` | 1 | 0 | 实际 prompt+completion |
| 无 `usage` | 0 | 1 | 预留额 1756 |
| 超时 / 传输错误 / 非 2xx | 0 | 1 | 预留额 1756 |
| 输出被安全校验拒绝 | 按上游 usage | 0/1 | 实际或预留额 |

`usage()` 暴露 `unknown_usage_attempts`、`uncertain_billing_attempts`，便于运营核对"有多少次说不清花了多少"。

## 2. 单元测试结果（`Server/tests/test_token_budget.py`，14 项全通过）

| 用例 | 断言要点 |
| --- | --- |
| `test_reported_usage_is_recorded_exactly` | `12+5=17` 精确入账 |
| `test_missing_usage_is_unknown_not_free` | `tokens_used += 1756`，`unknown_usage_attempts==1` |
| `test_timeout_charges_the_reservation` | 超时同样按 1756 计 |
| `test_token_budget_blocks_before_the_second_call` | `LLM_TOKEN_LIMIT=3000` → 1 次后 `budget_token_exhausted`，上游调用数为 1 |
| `test_unknown_usage_still_consumes_the_budget` | 两次 unknown 后预算耗尽（无"免费"漏洞） |
| `test_output_and_input_caps_are_sent_upstream` | `max_tokens=64`、`stream=false`、用户输入截断到 120 字符 |
| `test_context_budget_covers_system_and_user_text` | 1024 上下文 + 800 字输入 → 调用前拒绝，`global_used==0` |
| `test_reservation_is_request_scoped_and_released` | 结算后 `tokens_reserved==0`，`tokens_used==10` |
| `test_disabled_ledger_blocks_the_upstream` | `ledger_replaced` → 不发请求，`fallback_reason` 以 `ledger_` 开头 |
| `test_upstream_errors_charge_one_attempt_and_no_retry` | 401/429/500/503 各恰好 1 次调用、1 次计费 |
| `test_fake_key_never_appears_in_the_response` | 响应与 health 均无密钥 |

## 3. 账本故障矩阵（`Server/tests/test_ledger_faults.py`，14 项全通过）

| 故障 | 期望行为 | 实际 |
| --- | --- | --- |
| DB 与哨兵同时丢失 | 拒绝，不自动初始化 | `epoch_missing`（先查哨兵），未重建文件 |
| 只丢 DB | 拒绝 | `ledger_missing` |
| 只丢哨兵 | 拒绝 | `epoch_missing`，未重建 |
| **两者一起回退到同一旧快照** | 记录为已知缺口 | **接受**，`global_used` 从 4 回退到 2（口径已固化） |
| 只回退 DB | 检测 | `ledger_rollback_detected` |
| 代次不匹配（重置后重启） | 拒绝 | `ledger_epoch_pin_mismatch` |
| 哨兵写入失败 | 拒绝本次调用并计数 | `epoch_write_failed`，attempt 记为 failed |
| 磁盘写满（注入 `OperationalError`） | fail-closed | `ledger_write_failed` |
| COMMIT 后、哨兵前崩溃 | 自愈 | 下次 `load` 把哨兵抬到 `usage_count` |
| 哨兵后、请求前崩溃 | 孤儿结算 | `restart_orphan`，按 1756 保守计 |
| 重启 | 计数一致 | 3/30 保持 |
| 运行中被替换 | 检测 | `ledger_replaced`（`st_dev/st_ino` 变化） |
| 运行中被删除 | 检测 | `ledger_missing` |
| 失败与孤儿不退款 | 保守 | `tokens_used == 1756 + 18` |

## 4. 进程级 E2E（`M5CAR1/e2e/run_e2e_r1.py`，25/25 通过）

| 检查 | 观测值 |
| --- | --- |
| B1 请求次数预算 | 前三次 `external_model`，第四次 `budget_global_exhausted`，额外上游调用 **0** |
| B2 Token 预算 | 连续 9 次成功（每次 20 token）后 `budget_token_exhausted`；`tokens_used=180`，`token_limit=1000`，额外调用 0 |
| B3 台账损坏 | live 启动退出码 1：`RuntimeError: APP_ENTRY_MODE=live refused: budget ledger unusable (ledger_corrupt)` |
| L7 失败矩阵累计 | `tokens_used=5362`、`global_used=9`（失败也计费） |
| R1-R3 重启 | 代次指纹 `1d1a47fd9805` 与用量在重启后保持；旧会话 404 |

> B2 最初失败（12 次全部 `model_unavailable`、`token_limit=0`），根因是 `main.py:_build_live_provider`
> 没有把 `token_limit`/`epoch_pin` 传给 `RequestBudget.load`，导致 token 预算被静默禁用。修复后重跑通过。
> 该缺陷能存在，正是因为"配置存在"曾被当成"已经生效"——于是本轮同时加入了 7.4/7.5 的状态真实性检查。

## 5. 未覆盖 / 残余

| 项 | 说明 |
| --- | --- |
| 真实磁盘写满 | 只用注入 `sqlite3.OperationalError` 模拟；未做真实磁盘填充实验 |
| 平台多副本/多进程 | 单进程假设；`workers>1` 会让预算与限流不一致（已固定 `workers=1`） |
| 整体快照回滚 | 无法在本机区分，需平台侧独立可信存储（列为上线阻塞） |
| Token 估算误差 | `estimate_tokens` 偏保守（CJK 1 token/字，其他 3 字符/token，×1.1）；真实分词器下会高估，方向安全 |
| 真实计费口径 | ModelScope 官方未公布 token→魔粒 换算，本轮记账以 token 为唯一单位，不引入魔粒折算 |
