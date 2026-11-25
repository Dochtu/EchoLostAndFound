# M5-C-A 架构说明（显式 AI 模式 / 额度账本 / 限流 / 剧情安全）

版本：M5-C-A（本地开发与验收阶段）
基线：Git HEAD `4c51712c362e18bfcf9215cea766e61731773c74`，分支 `m5c-a-dev`
范围：仅第一章；不新增玩法、不接入真实模型、不修改线上部署。

---

## 1. 设计目标

1. **模式显式化**：服务只有一个入口模式变量 `APP_ENTRY_MODE=mock|live`，默认 `mock`；mock 在代码层面不具备调用外部模型的能力，而不是靠提示词或约定。
2. **失败关闭（fail-closed）**：live 模式缺少合法配置、缺少可信账本、账本损坏、账本不可写、代次不匹配时，进程**拒绝启动**，返回明确原因。
3. **游戏与模型解耦**：游戏就绪（`game_ready`）与模型就绪（`model_ready`）是两个独立状态；任何模型故障都自动降级到确定性回复，第一章流程不中断。
4. **状态只由确定性规则修改**：模型只能生成"角色语言 + 受限建议"，不能写证据、进度、披露、结局。
5. **成本可控且可证明**：请求先记账后发送；全局与会话额度在同一事务中原子预留；账本持久化不可证明时禁止 live。
6. **单进程单实例**：不引入 Redis / 付费数据库；所有限流与账本均在进程内或本地 SQLite 完成。

---

## 2. 入口模式与启动流程

```
APP_ENTRY_MODE (默认 mock)
   │
   ├─ mock ──> Settings.validate() 要求 MODEL_PROVIDER=mock
   │            build_provider() 直接返回 MockAiProvider
   │            不构造 LlmProvider、不读取账本、不创建 httpx client
   │
   └─ live ──> Settings.validate() 要求 MODEL_PROVIDER=llm
                ├─ LLM_BASE_URL / LLM_MODEL / LLM_API_KEY 齐全
                ├─ 账本路径已配置
                ├─ RequestBudget.load()
                │    ├─ 成功 ──> LlmProvider(budget, breaker)
                │    └─ 失败 ──> RuntimeError: APP_ENTRY_MODE=live refused:
                │                 budget ledger unusable (<reason>)
                └─ 进程退出（uvicorn 启动失败），不会半启动
```

要点：
- `Server/app/entry.py` 只有 `from .main import app`。启动命令统一为 `uvicorn app.entry:app --workers 1`，导入期即完成校验，因此配置错误不会拖到第一个请求才暴露。
- `MODEL_PROVIDER=llm` 且 `APP_ENTRY_MODE=mock` 会被 `Settings.validate()` 直接拒绝，防止"以为在 mock，实际已具备外呼能力"的误配置。
- 非法 `APP_ENTRY_MODE`（空串、`prod`、`MOCK` 以外的大小写变体等）同样拒绝启动。

实测拒绝信息（见 `evidence/entry_mode/`）：

```
ValueError: APP_ENTRY_MODE=live refused: LLM_BASE_URL, LLM_MODEL and LLM_API_KEY are all required
RuntimeError: APP_ENTRY_MODE=live refused: budget ledger unusable (epoch_missing)
RuntimeError: APP_ENTRY_MODE=live refused: budget ledger unusable (ledger_read_only)
```

---

## 3. 组件视图

```
Client (Unity WebGL)
   │ HTTP + JSON
   ▼
FastAPI (app.entry:app, single worker)
   ├─ BodySizeLimitMiddleware        请求体上限、分块读取累计上限
   ├─ Guard (main.py)
   │    ├─ X-Request-ID 解析/生成
   │    ├─ 可选本地鉴权头（X-Dialogue-Token）
   │    ├─ 全局限流  ── SlidingWindowLimiter("global")
   │    ├─ 客户端限流 ── resolve_client_ip() → SlidingWindowLimiter("client:<ip>")
   │    ├─ 新建会话限流（POST /sessions）
   │    └─ 会话对话限流（POST /sessions/{id}/turns）
   ├─ Routes: /health /meta /sessions /turns /evidence /cancel
   ├─ DialoguePolicy（确定性优先）
   │    ├─ 固定台词匹配 → 直接返回 fixed_line
   │    ├─ 否则调用 Provider
   │    └─ 二次校验模型文本 + 证据/披露规则
   ├─ SessionStore（内存，单实例）
   └─ Provider
        ├─ MockAiProvider（mock 模式）
        ├─ LlmProvider（live 模式）
        │    ├─ CircuitBreaker
        │    ├─ asyncio.Semaphore(llm_max_concurrency)
        │    └─ RequestBudget（SQLite + epoch sentinel）
        └─ DisabledProvider（未配置/不可用兜底，不发送请求）
```

---

## 4. 请求路径与限流顺序

`main.py` 的 Guard 对所有 `/api/v1/*` 请求按固定顺序检查：

1. `X-Request-ID`（缺失则生成 UUID；非法则 400）。
2. 本地鉴权（若配置了 `LOCAL_AUTH_TOKEN`；health 与 meta 规则保持原状）。
3. `Content-Length` 超限直接 413；分块读取由 BodySizeLimitMiddleware 累计拦截。
4. 全局限流（所有业务 API）。
5. 客户端限流（key 由 `resolve_client_ip` 计算）。
6. 新建会话限流（仅 POST `/api/v1/sessions`）。
7. 会话对话限流（仅 POST `/api/v1/sessions/{id}/turns`）。

静态站点（`/`、`/index.html`、`.gz` 资源）不经过业务限流，避免 WebGL 加载被模型限流误伤。

限流桶默认值（全部可配置，单位：每分钟请求数 / 突发容量）：

| 桶 | 环境变量 | 默认 |
| --- | --- | --- |
| 全局 | `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_BURST` | 60 / 20 |
| 客户端 | `CLIENT_RATE_LIMIT_PER_MINUTE` / `CLIENT_RATE_LIMIT_BURST` | 60 / 30 |
| 会话对话 | `SESSION_TURN_RATE_PER_MINUTE` / `SESSION_TURN_RATE_BURST` | 30 / 10 |
| 新建会话 | `NEW_SESSION_RATE_PER_MINUTE` / `NEW_SESSION_RATE_BURST` | 20 / 5 |

`SlidingWindowLimiter` 的实际上限为 `min(per_minute, burst)`，窗口 60 秒，线程锁保护。

## 5. 可信客户端地址

```python
resolve_client_ip(peer, forwarded_for, trusted_proxy_cidrs)
```

- `trusted_proxy_cidrs` 为空：**完全忽略** `X-Forwarded-For`，只使用 TCP peer 地址。
- peer 不在可信网段：忽略 XFF。
- peer 在可信网段：从 XFF 右向左跳可信代理，取第一个不可信地址。
- 无法解析：返回 `"unknown"`（这些请求共享一个客户端桶，宁可过严）。

配置校验拒绝 `0.0.0.0/0` 与 `::/0`，防止把"信任所有代理"当成默认。

由于魔搭真实代理拓扑未确认，本轮保持 `TRUST_FORWARDED_FOR=false`、`TRUSTED_PROXY_CIDRS` 为空，并在交付报告中列为**上线阻塞项**。

---

## 6. 模型 Provider 与调用序列

`LlmProvider.generate()` 的顺序（每一步失败都不发请求）：

```
1. configured?          否 → model_unavailable (llm_not_configured)
2. breaker.allow()?     否 → model_unavailable (circuit_open)        不记账
3. semaphore slot?      超时 → model_unavailable (upstream_busy)     不记账
4. budget.reserve()?    否 → model_unavailable (budget_* / ledger_*) 不发送
5. POST /chat/completions  恰好一次，绝不自动重试
6. 无论成功失败 budget.finish()（失败也计入额度）
7. 成功：breaker.success；失败：breaker.failure
```

细节：
- 请求地址：`{LLM_BASE_URL}/chat/completions`，`Authorization: Bearer <key>`。
- 开关 `LLM_JSON_MODE=true` 时附带 `response_format={"type":"json_object"}`（ModelScope 兼容 OpenAI 协议；默认关闭以兼容更多上游）。
- `max_tokens = LLM_MAX_OUTPUT_TOKENS`（默认 220，上限 1024）。
- 玩家输入截断到 `LLM_INPUT_MAX_CHARS`（默认 800，硬上限 4000）。
- `stream: false`，避免流式截断与半包解析。
- 超时取 `min(AI_TIMEOUT_MS, 请求剩余 timeouts)`。
- 解析 `usage.prompt_tokens` / `usage.completion_tokens` 写入账本；上游未返回 usage 时记 0 并在测试中确认不伪造。
- `finish_reason == "length"` 视为 `invalid_output / response_truncated`，不进入正文。
- 上游错误体只映射为 `upstream_status_N`，不落日志、不回传。

`ProviderResult.fallback_reason` 对本地原因（`budget_*`、`ledger_*`、`circuit_open`、`upstream_busy`）保留具体原因，其余按 outcome 映射，便于前端与运维区分"没钱了"和"上游挂了"。

---

## 7. 额度账本（RequestBudget）

### 7.1 双文件结构

| 文件 | 作用 | 位置默认值 |
| --- | --- | --- |
| SQLite 账本 | 每次尝试的预留/完成记录、token 用量 | `Server/.local/llm-usage.sqlite3` |
| epoch sentinel | 代次、已提交高水位、更新时间 | `Server/.local/epoch/ledger-epoch.json` |

sentinel 是"独立可信位置"的最简实现：它不在 SQLite 内，无法通过回滚数据库或替换数据库文件恢复额度。生产环境应把 sentinel 放在与账本不同的持久卷/系统（见配置指南的阻塞项）。

### 7.2 表结构

```sql
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- schema_version, ledger_epoch, usage_count, created_at

CREATE TABLE attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  request_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  model TEXT NOT NULL,
  npc_id TEXT NOT NULL,
  status TEXT NOT NULL,          -- reserved / completed / failed
  latency_ms INTEGER,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  error TEXT
);
```

### 7.3 预留事务

```sql
BEGIN IMMEDIATE;
SELECT COUNT(*) FROM attempts;                                  -- 全局已用
SELECT COUNT(*) FROM attempts WHERE session_id = ?;             -- 会话已用
-- 任一超限 → ROLLBACK，返回 global/session exhausted
INSERT INTO attempts(... status='reserved' ...);
UPDATE meta SET value = value + 1 WHERE key='usage_count';
COMMIT;
-- 提交成功后原子重写 sentinel: {epoch, high_water: usage_count}
```

- `BEGIN IMMEDIATE` 让并发预留串行化；实测 12 线程 × 限额 4 → 恰好 4 个成功。
- 先记账后请求：即使上游超时、401、进程崩溃，该次尝试也已占用额度。
- 单会话额度严格小于全局额度（配置校验强制 `per_session < global`），单会话无法耗尽全服务。

### 7.4 加载校验清单（任一失败 → live 拒绝启动）

1. sentinel 存在 / 可读 / JSON 合法 → `epoch_missing` / `epoch_unreadable` / `epoch_corrupt`
2. 账本文件存在（**绝不自动创建**）→ `ledger_missing`
3. `PRAGMA integrity_check == ok` → `ledger_corrupt`
4. `schema_version` 匹配
5. DB 内 `ledger_epoch` == sentinel `epoch` → `ledger_epoch_mismatch`
6. `COUNT(attempts) == meta.usage_count` → `ledger_inconsistent`
7. `COUNT(attempts) >= sentinel.high_water` → `ledger_rollback_detected`
8. 目录可写 + SQLite 可写（BEGIN IMMEDIATE / UPDATE / **COMMIT**）→ `ledger_read_only`

第 8 条同时做文件系统探针（创建、fsync、删除 `.write-probe-*`）与真实 SQLite 提交，因为 0 行变更的 ROLLBACK 不会创建 journal，无法证明写权限。

### 7.5 显式管理操作

首次初始化与额度重置只能通过 CLI 完成，服务自身永不"自动补额度"：

```bash
python -m app.ledger_admin init  --confirm --limit 30 --per-session 8
python -m app.ledger_admin reset --confirm --limit 30 --per-session 8
python -m app.ledger_admin verify
```

- `init`：账本或 sentinel 已存在 → 退出码 2，绝不覆盖。
- `reset`：轮换 epoch，清零计数，属于显式管理操作。
- `verify`：只读检查，失败退出码 3。

---

## 8. 熔断与降级

- `CircuitBreaker(threshold=LLM_BREAKER_THRESHOLD, cooldown=LLM_BREAKER_COOLDOWN_SECONDS)`。
- 连续失败达到阈值 → `open`，期间不发请求、不记账。
- 冷却后放行**一个** half-open 探测：成功 → `closed`；失败 → 重新 `open`。
- `upstream_busy`（本地并发槽满）不计入熔断失败，避免本地背压误判上游故障。
- 任何模型故障，`DialoguePolicy` 都返回 fallback（中文确定性文案 + 可选固定台词），HTTP 仍为 200，游戏继续。

---

## 9. 剧情安全分层

| 层 | 机制 | 位置 |
| --- | --- | --- |
| 1 | 严格 JSON 解析、只允许 `npc_id/text/suggested_topic_id` 三个键 | `security.validate_model_reply` |
| 2 | 文本校验：长度 ≤400、控制字符、`<`/`>`、禁用片段（提示词/密钥/绕过语） | `security.validate_bridge_text` |
| 3 | Policy 二次校验：即使自定义 Provider 绕过适配器，也在此拦截 | `policy._provider_turn` |
| 4 | 建议 topic 必须存在于当前 NPC 可用主题，否则丢弃 | `policy` |
| 5 | 状态变更只走 `/evidence` + 批准内容规则（D01/D02/D03/REC） | `policy.present` |
| 6 | 终局/证据/进度字段根本不在响应模型中 | `schemas` / 响应构造 |

模型输出没有 `evidence_granted`、`chapter_progress`、`ending` 等字段；即使上游强行返回，解析层直接判 `invalid_output` 并降级。

---

## 10. 部署拓扑（候选，未上线）

`M5CA/deploy/` 提供三个独立 compose，项目名隔离，端口互不冲突：

| 文件 | 项目名 | 服务端口 | 上游 | 用途 |
| --- | --- | --- | --- | --- |
| `docker-compose.mock.yml` | `m5ca` | 18080 | 无 | 默认 Mock 验收 |
| `docker-compose.live.yml` | `m5ca-live` | 18081 | fake-llm:19000 | 假模型 live 验收 |
| `docker-compose.tight.yml` | `m5ca-tight` | 18082 | fake-llm:19001 | 小额度/并发/故障验收 |

安全默认：
- 非 root（uid 10001）、`--workers 1`、无 volume 自动初始化。
- live 的账本卷必须先 `ledger_admin init --confirm` 才能启动。
- 静态资源与 API 同容器，但静态路径不参与模型限流。

Docker `VOLUME` 声明**不等于**平台持久化保证；魔搭上仅 `/mnt/workspace` 持久，账本卷是否真正持久未验证 → 上线阻塞。

---

## 11. 已知限制与上线阻塞（详见交付报告）

1. 魔搭真实代理拓扑未确认 → `TRUSTED_PROXY_CIDRS` 保持空，所有请求按 peer 地址限流。
2. 平台持久化未验证 → 账本可靠性无法证明，禁止 live 上线。
3. 未做真实模型调用（本轮硬性约束）→ 上游真实延迟、限流策略、返回格式差异未验证。
4. 单进程设计：多副本会各自持有独立额度和限流窗口，不适用于横向扩容。
5. 会话仍在内存：容器重启后旧会话 404 属预期行为（E2E R3 已验证"干净失败"）。
