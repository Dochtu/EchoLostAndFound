# M5-C-A 魔搭（ModelScope）配置指南

适用版本：M5-C-A 独立候选（`Builds/M5CA/candidate`）
状态：**仅本地验证完成；未部署到魔搭，未做真实模型调用。**
本轮硬性约束：不配置真实 API Key、不发送真实模型请求、不消耗魔粒。

---

## 1. 模式总览

| 变量 | 取值 | 默认 | 含义 |
| --- | --- | --- | --- |
| `APP_ENTRY_MODE` | `mock` / `live` | `mock` | 服务唯一模式入口 |
| `MODEL_PROVIDER` | `mock` / `llm` | 随模式：mock→`mock`，live→`llm` | mock 模式禁止 `llm` |
| `LLM_JSON_MODE` | `true` / `false` | `false` | 是否发送 `response_format=json_object` |

规则（违反即**拒绝启动**）：

- `APP_ENTRY_MODE` 不是 `mock`/`live`。
- `APP_ENTRY_MODE=mock` 且 `MODEL_PROVIDER=llm`。
- `APP_ENTRY_MODE=live` 且 `MODEL_PROVIDER!=llm`。
- live 缺少 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY` 任一。
- live 的账本路径缺失、账本/哨兵不存在、损坏、不可写、代次不符。

---

## 2. Live 模式必需变量

| 变量 | 示例（占位，不是真实值） | 约束 |
| --- | --- | --- |
| `APP_ENTRY_MODE` | `live` | 必填 |
| `MODEL_PROVIDER` | `llm` | 必填 |
| `LLM_BASE_URL` | `https://api-inference.modelscope.cn/v1` | 必须 `http(s)`，禁止含用户名/密码 |
| `LLM_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | 上游模型 ID |
| `LLM_API_KEY` | `ms-xxxxxxxx`（占位） | 只放服务端环境变量；禁止入库/日志/前端 |
| `LLM_PROVIDER_ID` | `modelscope-qwen`（可选） | 健康接口展示的 provider 标识 |
| `LLM_USAGE_PATH` | `/mnt/workspace/m5ca/llm-usage.sqlite3` | 必须已初始化，服务不会自动创建 |
| `LLM_LEDGER_EPOCH_PATH` | `/mnt/workspace/m5ca/epoch/ledger-epoch.json` | 必须与账本分离存放 |

额度与成本：

| 变量 | 默认 | 范围 |
| --- | --- | --- |
| `LLM_REQUEST_LIMIT` | 30 | 1..10000（本地验收固定 30） |
| `LLM_REQUEST_LIMIT_PER_SESSION` | 8 | 必须严格小于全局 |
| `LLM_MAX_OUTPUT_TOKENS` | 220 | 32..1024 |
| `LLM_INPUT_MAX_CHARS` | 800 | 100..4000 |
| `AI_TIMEOUT_MS` | 12000 | 100..60000 |
| `LLM_MAX_CONCURRENCY` | 2 | 1..8 |
| `LLM_BREAKER_THRESHOLD` | 5 | 1..50 |
| `LLM_BREAKER_COOLDOWN_SECONDS` | 60 | 1..3600 |

> 30/8 是本地测试暂定值，不是正式上线额度；上线前必须由业务方确认。

---

## 3. 限流与代理变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_BURST` | 60 / 20 | 全局业务请求 |
| `CLIENT_RATE_LIMIT_PER_MINUTE` / `CLIENT_RATE_LIMIT_BURST` | 60 / 30 | 单客户端 |
| `SESSION_TURN_RATE_PER_MINUTE` / `SESSION_TURN_RATE_BURST` | 30 / 10 | 单会话对话 |
| `NEW_SESSION_RATE_PER_MINUTE` / `NEW_SESSION_RATE_BURST` | 20 / 5 | 新建会话 |
| `TRUST_FORWARDED_FOR` | `false` | 是否信任 XFF |
| `TRUSTED_PROXY_CIDRS` | 空 | 逗号分隔 CIDR；拒绝 `0.0.0.0/0`、`::/0` |

**魔搭上必须保持 `TRUST_FORWARDED_FOR=false`，直到平台代理拓扑被确认并给出可信 CIDR。**
原因：无条件信任 XFF 会让攻击者伪造客户端地址绕过客户端限流。当前拓扑未确认，属于上线阻塞。

---

## 4. 其他变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CONTENT_DIR` | `app/content` | 内容包目录 |
| `PLAYER_INPUT_MAX_CHARS` | 1000 | 玩家输入总上限（模型侧另有 800 截断） |
| `REQUEST_MAX_BYTES` | 32768 | 请求体上限 |
| `SESSION_TTL_SECONDS` | 1800 | 会话过期 |
| `MAX_SESSIONS` | 512 | 内存会话上限 |
| `CORS_ORIGINS` | 本地白名单 | 禁止 `*` |
| `LOCAL_AUTH_TOKEN` | 空 | 可选本地鉴权；不可与平台保留头冲突 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

注意：魔搭保留 `Authorization` 与 `X-modelscope-*` 头。本服务的 `LOCAL_AUTH_HEADER` 默认 `X-Dialogue-Token`，不要改成 `Authorization`。

---

## 5. 账本初始化（live 前置，必须显式执行）

服务**永远不会**自动创建账本或补额度。首次部署与额度重置都必须执行：

```bash
# 首次初始化（账本或哨兵已存在会失败，绝不覆盖）
python -m app.ledger_admin init \
  --path /mnt/workspace/m5ca/llm-usage.sqlite3 \
  --epoch-path /mnt/workspace/m5ca/epoch/ledger-epoch.json \
  --limit 30 --per-session 8 --confirm

# 校验（只读）
python -m app.ledger_admin verify \
  --path /mnt/workspace/m5ca/llm-usage.sqlite3 \
  --epoch-path /mnt/workspace/m5ca/epoch/ledger-epoch.json

# 额度重置（轮换代次，需明确确认）
python -m app.ledger_admin reset \
  --path /mnt/workspace/m5ca/llm-usage.sqlite3 \
  --epoch-path /mnt/workspace/m5ca/epoch/ledger-epoch.json \
  --limit 30 --per-session 8 --confirm
```

退出码：`0` 成功；`2` 已存在/参数错误/未确认；`3` 账本不可用（损坏、缺失、代次、只读）。

在 Docker 中执行（不启动主服务）：

```bash
docker compose -f docker-compose.live.yml run --rm --no-deps \
  --entrypoint python live -m app.ledger_admin init --confirm
```

---

## 6. 启动命令

```bash
uvicorn app.entry:app --host 0.0.0.0 --port 7860 --workers 1
```

- 必须监听 `0.0.0.0`、端口 `7860`（魔搭要求）。
- 必须 `--workers 1`：账本、限流、会话均为单进程设计；多 worker 会放大额度并破坏一致性。
- 不要使用 `--reload`。

---

## 7. 就绪检查

```bash
curl -s http://127.0.0.1:7860/api/v1/health
```

Mock（本地实测）：

```json
{"ready":true,"game_ready":true,"entry_mode":"mock","model_available":false,
 "model_ready":false,"model_mode":"mock",
 "provider":{"kind":"mock","id":"mock-deterministic","is_synthetic":true},
 "is_synthetic":true,
 "ledger":{"status":"mock","global_used":0,"global_limit":30,"session_limit":8,
           "epoch_fingerprint":"","persistent":false},
 "breaker":null}
```

Live（假上游实测）：

```json
{"ready":true,"game_ready":true,"entry_mode":"live","model_available":true,
 "model_ready":true,"model_mode":"live",
 "provider":{"kind":"external_model","id":"external-llm","is_synthetic":false},
 "is_synthetic":false,
 "ledger":{"status":"ready","global_used":11,"global_limit":30,"session_limit":8,
           "epoch_fingerprint":"a7328e321f45","persistent":true},
 "breaker":{"state":"closed","consecutive_failures":0,"threshold":50}}
```

判定：
- `game_ready=true`：第一章确定性流程可用。
- `model_ready=false` 且 `entry_mode=live`：模型不可用，但游戏仍可玩（降级）。
- `ledger.persistent=false`：账本未证明持久化 → 不得上线 live。
- `breaker.state=open`：上游连续故障，冷却后自动半开探测。

---

## 8. 平台持久化警告（上线阻塞）

- 魔搭仅保证 `/mnt/workspace` 持久；其他路径可能随容器重建丢失。
- `Dockerfile` 中的 `VOLUME` 只是声明，**不等于平台会持久化**。
- 账本与哨兵必须放在平台确认持久的路径，且二者应位于不同故障域（不同目录/卷/存储），否则同时丢失会导致额度被重置。
- 在平台完成"重启/重建后账本仍在、代次不变"的实测前，`LLM_REQUEST_LIMIT` 不能视为可靠成本上限，**live 禁止上线**。

---

## 9. 本地假上游联调（不消耗任何额度）

```bash
# 启动假上游（无外网、无计费）
python tools/fake_llm_server.py --port 9000

# live 指向本地假上游
LLM_BASE_URL=http://127.0.0.1:9000/v1 \
LLM_MODEL=fake-model \
LLM_API_KEY=placeholder-not-real \
APP_ENTRY_MODE=live ...
```

假上游支持在玩家输入中插入标记模拟异常：`[[fake:timeout]]`、`[[fake:401]]`、`[[fake:429]]`、`[[fake:500]]`、`[[fake:badjson]]`、`[[fake:truncate]]`、`[[fake:unsafe]]`、`[[fake:leak]]`、`[[fake:slow]]`；`GET /__stats` 查看请求数/并发/auth；`POST /__reset` 清零。

---

## 10. 常见拒绝信息对照

| 信息 | 原因 | 处理 |
| --- | --- | --- |
| `APP_ENTRY_MODE=live refused: LLM_BASE_URL, LLM_MODEL and LLM_API_KEY are all required` | 缺 provider 配置 | 补齐三项环境变量 |
| `APP_ENTRY_MODE=live refused: budget ledger unusable (epoch_missing)` | 未初始化账本/哨兵 | 执行 `ledger_admin init --confirm` |
| `... (ledger_missing)` | 账本文件被删 | 停止服务，确认原因后用 `init`（不得自动重建） |
| `... (ledger_corrupt)` / `(ledger_unreadable)` | 文件损坏/截断 | 保留现场取证；必要时 `reset --confirm` |
| `... (ledger_epoch_mismatch)` | 代次被替换 | 禁止自动修复；人工核对后再决定 reset |
| `... (ledger_rollback_detected)` | 数据库被回滚到旧副本 | 视为安全事件，禁止放行 |
| `... (ledger_read_only)` | 目录/SQLite 不可写 | 修权限；不要放宽到 777 |
| `MODEL_PROVIDER=llm requires APP_ENTRY_MODE=live; mock mode never calls an external model` | mock 模式误配 llm | 改回 `MODEL_PROVIDER=mock` |

---

## 11. 上线前必须补齐

1. 魔搭代理拓扑确认 → 配置 `TRUSTED_PROXY_CIDRS` 并开启 `TRUST_FORWARDED_FOR`（仅当 CIDR 可信）。
2. 平台持久化实测（重启、重建、迁移）→ 证明账本与哨兵不丢、代次不变。
3. 真实上游小额度试运行（需技术负责人另行批准；本轮禁止）。
4. 正式额度确认（本轮 30/8 仅为测试值）。
5. 真实上游的 `usage` 字段核对（部分兼容 API 不返回 token 用量）。
