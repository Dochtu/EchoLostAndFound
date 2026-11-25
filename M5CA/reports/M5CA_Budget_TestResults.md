# M5-C-A 额度与持久化测试结果

执行日期：2026-11-25
环境：本地 Docker Desktop 28.5.1（Linux 容器，命名卷），Windows 11
上游：本地 `fake_llm_server.py`（无真实计费、无真实请求）
额度：本地验收使用 **30 全局 / 8 会话**；tight 场景另用 **6 全局 / 2 会话** 以放大耗尽行为。
**这些额度仅为测试值，不代表正式上线额度。**

---

## 1. 单元/集成测试

命令与结果：`206 passed`，其中额度相关 37 例：

| 文件 | 用例数 | 覆盖 |
| --- | ---: | --- |
| `Server/tests/test_budget.py` | 16 | 账本核心 |
| `Server/tests/test_llm_transport.py` | 16 | 上游交互中的记账/拒绝 |
| `Server/tests/test_ledger_admin.py` | 5 | 管理 CLI |

关键断言：

| 场景 | 断言 | 结果 |
| --- | --- | --- |
| 先记账后请求 | 预留发生在 POST 之前；失败请求仍占 1 | 通过 |
| token 用量 | 成功响应 `usage` 的 12/5 写回 `attempts` | 通过 |
| 全局额度 3 | 第 4 次拒绝 `global_exhausted` | 通过 |
| 会话额度 2 / 全局 6 | 贪婪会话第 3 次拒绝 `session_exhausted`；其他会话仍可请求 | 通过 |
| 并发预留 | 12 线程、限额 4 → 恰好 4 个成功，账本计数 4 | 通过 |
| 进程崩溃 | 预留后直接重开（不 finish）→ 记录仍在，额度不回滚 | 通过 |
| 账本缺失 | `ledger_missing`，不自动创建文件 | 通过 |
| 账本损坏 | 截断/垃圾字节 → `ledger_corrupt` / `ledger_unreadable` | 通过 |
| sentinel 缺失/损坏 | `epoch_missing` / `epoch_corrupt` | 通过 |
| 代次不匹配 | `ledger_epoch_mismatch` | 通过 |
| 数据库回滚 | 用备份覆盖 → `ledger_rollback_detected`（高水位） | 通过 |
| 计数篡改 | `usage_count` 与行数不符 → `ledger_inconsistent` | 通过 |
| 只读 | `chmod 444` → `ledger_read_only` / `ledger_unreadable` | 通过 |
| 显式重置 | `reset --confirm` 轮换 epoch 并清零；无 `--confirm` 拒绝 | 通过 |
| 高水位 | sentinel `high_water` 随预留递增 | 通过 |
| 上游失败不重试 | 401/429/500/超时/非法 JSON 每例上游仅 1 次请求，且均记 `failed` | 通过 |
| 熔断 | 连续 5 次 500 → `open`，期间 0 上游请求；冷却后 half-open 成功 → `closed` | 通过 |
| 账本删除后 | `provider.available=false`，`ledger_unavailable`，0 上游请求 | 通过 |

## 2. Docker 端到端（tight 场景）

配置：`LLM_REQUEST_LIMIT=6`、`LLM_REQUEST_LIMIT_PER_SESSION=2`、`LLM_MAX_CONCURRENCY=2`、`AI_TIMEOUT_MS=1500`、`LLM_BREAKER_THRESHOLD=4`、冷却 10s。

| 检查 | 实际值 | 判定 |
| --- | --- | --- |
| B1 初始账本 | `status=ready`、`global_used=0`、`global_limit=6`、`session_limit=2`、`persistent=true`、epoch `931a3141e073` | 通过 |
| B2 8 个并发请求 / 4 会话 | 上游请求 6、账本已用 6、预算拒绝 2、最大上游并发 2、完成 6 | 通过 |
| B3 耗尽后继续 | 第 7 次 `budget_global_exhausted`，上游仍为 6；固定台词 `fixed_line` 正常返回 | 通过 |
| B4 删除账本后启动 | 容器退出（`state=missing`），日志含 `ledger_missing`，上游 before=6 / after=0 | 通过 |
| B5 损坏账本后启动 | 容器退出，日志拒绝原因损坏类 | 通过 |
| B6 目录 `chmod 500` 后启动 | 容器退出，`RuntimeError: APP_ENTRY_MODE=live refused: budget ledger unusable (ledger_read_only)` | 通过 |

B2 的并发细节：8 个请求中有 2 个因会话额度（每会话 2）被拒，6 个进入上游；上游统计 `max_inflight=2`，证明信号量与账本同时生效；`ledger_used == upstream_requests`，不存在"发了请求没记账"或"记了账没发请求"的偏差。

## 3. 生命周期与持久化

| 检查 | 操作 | 观察 | 判定 |
| --- | --- | --- | --- |
| R1 进程/容器重启 | `docker compose restart live` | 已用额度 11 → 重启后仍 11；epoch 不变 | 通过 |
| R2 容器删除重建 | `docker compose down`（保留卷）+ `up` | 11 → 11 | 通过 |
| R3 重启后旧会话 | 用旧 `conversation_id` 请求 | 404，无幽灵状态 | 通过 |
| R4 重启后上游 | 重启后发起一次对话 | 上游可达，`upstream=1` | 通过 |

说明：R1/R2 使用的持久化载体是**本地 Docker 命名卷**。这只能证明"容器生命周期内卷保留数据"，**不能证明魔搭平台会持久化该路径**。

## 4. 账本结构复核

```sql
meta: schema_version, ledger_epoch, usage_count, created_at
attempts: id, started_at, request_id, session_id, model, npc_id,
          status(reserved|completed|failed), latency_ms,
          prompt_tokens, completion_tokens, error
```

- `usage_count` 与 `COUNT(attempts)` 双重计数用于一致性校验。
- sentinel：`{epoch, high_water, updated_at}`，位于账本目录之外的独立文件（默认 `Server/.local/epoch/ledger-epoch.json`）。
- 每次预留提交后原子重写 sentinel；sentinel 写入失败会将本次尝试标记失败并禁用账本。
- SQLite 使用 `journal_mode=DELETE`、`synchronous=FULL`、`busy_timeout`，牺牲部分吞吐换取崩溃一致性。

## 5. 额度耗尽后的游戏行为

- 模型调用返回 `source=fallback`（或固定台词 `fixed_line`），HTTP 200。
- `game_ready=true` 不变；`model_ready` 仍为 true（模型可用，只是额度耗尽），`ledger.status=ready`、`global_used=6`。
- 玩家可继续调查、提交证据、触发披露；仅自由对话降级为确定性回复。
- 前端无需特殊处理：`fallback_reason` 可用于提示"本班次对话额度已用完"，但不影响流程。

## 6. 未验证 / 阻塞

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 魔搭平台账本持久化 | ⛔ 未验证 | 仅 `/mnt/workspace` 持久；账本卷是否保留未知 → **上线阻塞** |
| 平台重启/迁移后的代次行为 | ⛔ 未验证 | 本地卷通过，平台未测 |
| 真实上游计费口径 | ⛔ 未验证 | 未发真实请求；token 统计依赖上游 `usage` 字段 |
| 多副本额度一致性 | ⛔ 不支持 | 单进程设计；多副本会各自计数 |
| 长时间浸泡/磁盘写满 | ⛔ 未测 | 仅测了权限与损坏 |

## 7. 结论

- "先记账、后请求、失败也计数、绝不自动重试"已在单元与容器两层验证。
- 账本丢失/损坏/只读/代次不符/回滚/篡改六类异常均 fail-closed，且不会自动生成新额度。
- 并发场景下账本、信号量、上游统计三者一致，未发现超发。
- 唯一未闭环的是**平台持久化证明**；在该证明完成前，live 不得上线，这一点与预检结论一致。
