# NPC AI 服务 API 契约（M4-B v1）

本契约供 Unity WebGL 客户端调用，并与 `M3B/Shared/Ai/NpcAiContracts.cs`、`Docs/DataSchema.md` 的既有语义对齐。服务默认地址：`http://127.0.0.1:8787`（本机）；部署后由部署方提供 HTTPS 基址，路径不变。

- 版本前缀：`/api/v1`
- 内容版本：`story-v1.0-phase2`（由 `GET /api/v1/meta` 的 `content_version` 返回）
- 传输：HTTP/1.1 + JSON（UTF-8）；所有请求体必须是 JSON 对象，未知字段一律拒绝（422）。

## 1. 公共约定

### 1.1 响应包络

成功：

```json
{"request_id": "5f1c...", "data": { }, "error": null}
```

失败：

```json
{
  "request_id": "5f1c...",
  "data": null,
  "error": {
    "code": "PRECONDITION_FAILED",
    "message": "该话题尚未开放。",
    "retryable": false,
    "details": {}
  }
}
```

- HTTP 状态码与 `error.code` 同时表达错误；客户端应两者都检查。
- 服务端不回传内部异常、堆栈、上游响应正文或密钥。
- 响应头：`X-Request-ID`（回显或新生成）、`Cache-Control: no-store`、`X-Content-Type-Options: nosniff`。

### 1.2 请求 ID

- 可发送 `X-Request-ID`，只允许 `[A-Za-z0-9._:-]{1,64}`，否则服务端替换为新 UUID。
- 会话创建与回合请求体也可带 `request_id`（同一格式）。头与体的取值规则（M4-C §C1.3 起）：

| 请求头 | 请求体 | 结果 |
| --- | --- | --- |
| 合法值 | 无 | 使用请求头值 |
| 无/非法值 | 合法值 | 使用请求体值（回写进包络与响应头） |
| 合法值 | 同一值 | 使用该值 |
| 合法值 | 不同合法值 | 400 `INVALID_REQUEST` |
| 无 | 无/非法值 | 服务端生成新 UUID |

- 成功与失败响应（含中间件层的 401/413/429 与 422/500）都带 `X-Request-ID`，包络 `request_id` 与响应头一致。
- 本服务为同步接口，不做幂等重放缓存；重试语用由客户端按幂等 GET/新回合处理。

### 1.3 本机/私网令牌（可选）

设置 `LOCAL_AUTH_TOKEN` 后，除 `GET /api/v1/health` 外的所有请求需带：

```http
X-Dialogue-Token: <token>
```

- 默认头名可用 `LOCAL_AUTH_HEADER` 修改；只有改成 `Authorization` 时才接受 `Bearer <token>`。
- ModelScope 创空间占用 `Authorization`、`X-modelscope-*`、`X-studio-*` 头，因此默认**不要**使用 `Authorization`。
- 该令牌不是用户身份认证，不能替代 TLS/平台鉴权；不得写入客户端资源或 Git。

### 1.4 CORS

`CORS_ALLOWED_ORIGINS` 必须是逗号分隔的完整源（如 `http://localhost:8080,https://example.com`），不允许 `*`。服务返回：

- `Access-Control-Allow-Origin`：精确回显允许的源；
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`；
- `Access-Control-Allow-Headers: Content-Type, X-Request-ID, Authorization, <LOCAL_AUTH_HEADER>`；
- `Access-Control-Expose-Headers: X-Request-ID, Retry-After`；
- 预检缓存 `Access-Control-Max-Age: 600`。

凭据（Cookie）不启用。

## 2. 端点

### 2.1 `GET /api/v1/health`

无需鉴权。用于部署健康检查。

```json
{
  "request_id": "...",
  "data": {
    "service_instance_id": "uuid",
    "service_name": "echolostfound-npc-ai",
    "api_version": "1.0",
    "schema_version": "1",
    "content_version": "story-v1.0-phase2",
    "ready": true,
    "model_available": false,
    "model_mode": "mock",
    "provider": {"kind": "mock", "id": "mock-deterministic", "is_synthetic": true}
  },
  "error": null
}
```

`model_available` 仅在 `MODEL_PROVIDER=llm` 且配置完整时为 true。

### 2.2 `GET /api/v1/meta`

返回公开内容元数据，供客户端构建选项、校验内容版本、展示“内容仍在确认”的标记。

```json
{
  "content_version": "story-v1.0-phase2",
  "npcs": [
    {
      "npc_id": "npc_laozhou",
      "display_name": "老周",
      "allowed_evidence_ids": ["E01", "E02", "E03", "E04", "E05"],
      "opening_segments": [
        {"content_ref": "dialogue.CH01.opening.laozhou", "text": "这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。"}
      ],
      "topics": [{"topic_id": "opt.laozhou.ask_b01", "label": "问那晚的灯"}]
    }
  ],
  "disclosures": [
    {
      "disclosure_id": "D01",
      "npc_id": "npc_laozhou",
      "kind": "testimony",
      "required_evidence_ids": ["E02"],
      "required_observed_field_ids": []
    }
  ],
  "provisional_content_refs": [
    "dialogue.CH01.opening.laozhou",
    "dialogue.CH01.opening.linyao",
    "dialogue.CH01.D01.laozhou",
    "dialogue.CH01.D03.laozhou",
    "dialogue.CH01.linyao.engraving",
    "dialogue.CH01.linyao.refusal"
  ],
  "limits": {
    "player_input_max_chars": 1000,
    "request_max_bytes": 32768,
    "ai_timeout_ms": 12000,
    "session_ttl_seconds": 1800.0,
    "max_sessions": 512
  },
  "provider": {"kind": "mock", "id": "mock-deterministic", "is_synthetic": true, "available": false}
}
```

### 2.3 `POST /api/v1/sessions`

创建一个 NPC 会话。会话之间完全隔离：新建会话**不会**关闭或影响同一实例上其他玩家已打开的会话（M4-C §C1.1 修正了 M4-B 的“新建即关闭旧会话”行为）。

每个实例的会话数受 `MAX_SESSIONS`（默认 512，`/api/v1/meta` 的 `limits.max_sessions`）限制。达到上限时按以下顺序腾出位置：

1. 清理超时的已结束会话（`closed`/`cancelled`/`expired` 且超过保留期 300 秒）；
2. 淘汰最旧的已结束会话；
3. 仍无空位则淘汰最旧的仍未结束会话（被淘汰的 `conversation_id` 之后返回 404 `NOT_FOUND`，客户端应重新创建会话）。

该淘汰策略优先保证新玩家可进入，代价是极端压力下最旧的活跃会话可能被回收；它不改变单个会话内部证据/披露/对话状态的一致性。

请求：

```json
{"npc_id": "npc_laozhou", "evidence_ids": ["E01"], "observed_field_ids": ["watch.dial"]}
```

- `npc_id`：必填，格式 `npc_[a-z][a-z0-9_]{0,40}`；只允许内容中存在的 NPC（当前为老周、林遥；`npc_xucheng` 未开放）。
- `evidence_ids`：客户端当前已获得的证据编号，可空；服务端只做记录与校验，不授予证据。
- `observed_field_ids`：客户端已观察到的字段，可空。

响应 `201`：

```json
{
  "request_id": "...",
  "data": {
    "conversation_id": "608239e4-...",
    "npc_id": "npc_laozhou",
    "status": "open",
    "opening_segments": [
      {"content_ref": "dialogue.CH01.opening.laozhou", "text": "这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。"}
    ],
    "available_topic_ids": ["opt.laozhou.ask_b01", "opt.laozhou.leave"],
    "expires_in_seconds": 1800.0
  },
  "error": null
}
```

### 2.4 `GET /api/v1/sessions/{conversation_id}`

查询当前会话（不延长以外的修改，读取会滑动续期）。

```json
{
  "conversation_id": "...",
  "npc_id": "npc_laozhou",
  "status": "open",
  "presented_evidence_ids": ["E02"],
  "triggered_disclosure_ids": ["D01"],
  "available_topic_ids": ["opt.laozhou.ask_b01", "opt.laozhou.repeat_b01", "opt.laozhou.leave"]
}
```

### 2.5 `POST /api/v1/sessions/{conversation_id}/turns`

提交一个回合。**必须且只能**提供 `topic_id` 或 `text` 之一。

固定话题请求：

```json
{"topic_id": "opt.laozhou.ask_b01"}
```

自由输入请求：

```json
{"text": "那晚灯亮着吗", "timeout_ms": 4000}
```

- `text`：去除首尾空白后 1..1000 字符。
- `timeout_ms`：可选，100..30000；超过 `AI_TIMEOUT_MS` 会被服务端截断。
- `evidence_ids` / `observed_field_ids`：可选，用于同步客户端当前状态（只记录，不授予）。

响应 `200`（同步完成，`status` 恒为 `completed`）：

```json
{
  "turn_id": "turn_f32cb2...",
  "status": "completed",
  "source": "fixed_line",
  "fixed_segments": [
    {"content_ref": "dialogue.CH01.B01.initial", "text": "站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。"}
  ],
  "fixed_delivery_token": null,
  "generated_bridge": null,
  "fallback_reason": null,
  "suggested_actions": [],
  "provider": {"kind": "mock", "id": "fixed-line-content", "is_synthetic": false},
  "available_topic_ids": ["opt.laozhou.ask_b01", "opt.laozhou.leave"],
  "conversation_id": "...",
  "npc_id": "npc_laozhou"
}
```

`source` 取值与语义：

| source | 含义 | provider.kind | is_synthetic |
|---|---|---|---|
| `fixed_line` | 已批准固定台词/话题（固定优先，不调用模型） | `mock` | `false` |
| `mock` | Mock Provider 的测试回复 | `mock` | `true` |
| `external_model` | 真实模型桥接文本 | `external_model` | `false` |
| `fallback` | 模型失败/无匹配，无生成文本 | `fallback` | `true` |

`fallback_reason` 只在 `source=fallback` 时非空，取值：

`model_unavailable` / `timeout` / `invalid_output` / `unsafe_output` / `unknown_intent`

失败模型调用**不是** HTTP 错误：仍返回 200 completed turn + `fallback_reason`，客户端据此选择重试或显示沉默/固定反应。`generated_bridge` 可能为 `null`。

固定优先规则：自由文本命中已批准的意图关键词（老周：`灯`、`照明`、`油灯` → B01 话题；林遥：`背刻`、`表背`、`刻字` → 表背辨认；`闲聊`、`别的`、`闲话` → 拒绝闲聊）或精确说出已开放话题的 `label` 时，直接返回固定台词，**即使配置了真实模型也不调用**。这是防止模型改写已批准剧情的硬性策略。

### 2.6 `POST /api/v1/sessions/{conversation_id}/evidence`

出示证据（对应 `npc.present` / `disclosure.trigger` 的服务端确定性实现）。

```json
{"evidence_ids": ["E03", "E04"], "observed_field_ids": ["watch.back_engraving"]}
```

- `evidence_ids`：1..8 个，必须形如 `E##` 且存在于内容目录；重复编号去重。
- 未知 NPC/证据 → 404；格式非法 → 400；该 NPC 没有为证据配置已批准回应 → 409 `PRECONDITION_FAILED`。
- 空数组 → 422。
- 出示会记录“客户端已持有”，服务端**不会**因此新增客户端没有的证据。

响应 `200`：

```json
{
  "presented_evidence_ids": ["E02"],
  "newly_presented_field_ids": ["power_fault.branch_fault", "power_fault.timestamp", "power_fault.lamp_time", "power_fault.not_restored"],
  "already_presented": false,
  "available_disclosure_ids": [],
  "triggered_disclosure_ids": ["D01"],
  "fixed_segments": [
    {"content_ref": "dialogue.CH01.D01.laozhou", "text": "进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。"}
  ],
  "event_ids": ["evt_..."],
  "observed_field_ids": [],
  "conversation_id": "...",
  "npc_id": "npc_laozhou"
}
```

规则：

| 触发 | NPC | 需求 | 台词 |
|---|---|---|---|
| `D01` | 老周 | E02 | 已批准 |
| `D02` | 林遥 | E03 + E04 | 已批准 |
| `D02` | 老周 | E03 + E04 | 仅核对，无新剧情台词（`fixed_segments=[]`） |
| `D03` | 老周 | E01 + E05 | 已批准 |
| `REC.engraving` | 林遥 | E01 + 已观察 `watch.back_engraving` | 表背辨认，不属于 D |

- 每个 D 在同一会话内只触发一次；重复出示 → `already_presented=true`、`newly_presented_field_ids=[]`、`event_ids=[]`、不重复台词。
- 已触发过的 D 不再出现在 `available_disclosure_ids`。
- 退出/关闭/过期的会话不再保留可出示上下文；需重新创建会话。
- 服务端只做“同一 NPC 当前出示集合”的确定性判定，不做世界真相推断。

### 2.7 `POST /api/v1/sessions/{conversation_id}/cancel`

```json
{"conversation_id": "...", "npc_id": "npc_laozhou", "status": "cancelled"}
```

取消后该会话的后续请求返回 404/410。

### 2.8 结束语话题 `*.leave`

`opt.laozhou.leave`、`opt.linyao.leave` 等回合会返回固定告别语并把会话置为 `closed`；此后请求该会话返回 410 `TURN_EXPIRED`。客户端应主动释放会话引用。

## 3. 错误码

| HTTP | code | 场景 |
|---|---|---|
| 400 | `INVALID_REQUEST` | 编号格式错误、请求头/体 `request_id` 不一致、Content-Length 非法 |
| 401 | `LOCAL_AUTH_REQUIRED` | 已启用 `LOCAL_AUTH_TOKEN` 但缺失/错误 |
| 404 | `NOT_FOUND` | 未知 NPC、未知话题、未知证据/字段、未知会话、未知路由、被容量上限淘汰的会话 |
| 405 | `INVALID_REQUEST` | 方法不允许 |
| 409 | `PRECONDITION_FAILED` | 话题未开放、证据未被该 NPC 允许 |
| 410 | `TURN_EXPIRED` | 会话已过期/已关闭/已取消 |
| 413 | `REQUEST_TOO_LARGE` | 请求体超过 32 KiB（含未声明 `Content-Length` 的分块请求，由 ASGI 中间件累计字节数判定） |
| 422 | `VALIDATION_ERROR` | 请求体结构、类型、长度、互斥字段校验失败 |
| 429 | `RATE_LIMITED` | 触发限流；带 `Retry-After` 与 `details.retry_after_seconds` |
| 429 | `TURN_BUSY` | 预留：并发回合冲突 |
| 500 | `INTERNAL_ERROR` | 未预期异常，已记录日志，不泄漏细节 |

限流：默认每来源每分钟 60 次、突发 20 次（按 `RATE_LIMIT_PER_MINUTE`、`RATE_LIMIT_BURST` 配置）。只有设置 `TRUST_FORWARDED_FOR=true` 且部署在可信代理后，才使用 `X-Forwarded-For` 的第一段作为来源。

## 4. Provider 语义

| 配置 | provider.kind | provider.id | 行为 |
|---|---|---|---|
| 固定台词 | `mock` | `fixed-line-content` | 不调用任何模型 |
| `MODEL_PROVIDER=mock` | `mock` | `mock-deterministic` | 读取 `app/content/mock_ai_fixtures.json`，所有回复 `is_synthetic=true` |
| `MODEL_PROVIDER=llm` + 配置 | `external_model` | 配置的 `LLM_PROVIDER_ID` | OpenAI 兼容 `POST {LLM_BASE_URL}/chat/completions` |
| `MODEL_PROVIDER=llm` 未配置 | `fallback` | `disabled` | `model_unavailable` |
| 模型失败 | `fallback` | 实际 provider id | 200 + `fallback_reason` |

模型输出必须严格为：

```json
{"npc_id": "npc_laozhou", "text": "……", "suggested_topic_id": "opt.laozhou.ask_b01"}
```

- `npc_id` 必须与请求一致；`text` 1..400 字符；拒绝 `<` `>`、控制字符与“系统提示 / 忽略上面 / 忽略以上 / api key / apikey / sk-”等片段。
- `suggested_topic_id` 只能来自本回合 `available_topic_ids`，否则丢弃。
- 模型不能授予证据、不能改变任务状态、不能伪造 D、不能下发客户端指令；服务端只读取文本。
- 密钥只从服务端环境变量读取，只放在上游请求头；日志与响应不包含密钥。

## 5. 与 DataSchema 的差异（显式记录）

1. 回合为**同步完成**（200），不实现 202 + pending 轮询 + `fixed_delivery_token`。原因：固定台词与 Mock 立即产出，轮询无收益；真实模型超时也在 `AI_TIMEOUT_MS` 内收敛为 fallback。`fixed_delivery_token` 字段保留为 `null` 以保持形状。
2. 会话保存在**进程内存**，不写入 `PlayerStateView`/存档；重启即失效，符合 DataSchema “会话不持久化”的约束。
3. 客户端上报 `evidence_ids` 是“确认持有”，不是获取入口；真正的证据获取仍由 Unity 端 `EvidenceRegistry` 决定。
4. 增加 `RATE_LIMITED`、`INTERNAL_ERROR` 两个传输层错误码（DataSchema §7 未定义）。
5. 本服务提供 `npc.present`/`disclosure.trigger` 的服务端等价端点，但路径按 REST 组织，而非 RPC 命名。

## 6. 版本与兼容

- 破坏性变更需提升 `/api/v2`；响应内 `content_version` 必须与客户端内容版本一致，否则客户端应拒绝展示并要求更新。
- 内容变更不得改动已批准台词的 `content_ref` 与 `text`；`provisional_content_refs` 中的引用在内容确认前可能被替换。

## 7. M4-C 变更记录（v1，兼容）

M4-C 修复了四处实现缺陷，未新增端点、未改变成功响应形状，因此仍为 v1：

1. 会话隔离：`POST /sessions` 不再关闭其他会话；新增容量上限与淘汰（§2.3）。
2. 模型调用改为 `httpx.AsyncClient`，回合路由 `await` 模型；超时/异常回退语义不变（§4）。
3. `request_id` 头/体规则改为 5 种明确情形，体自带 ID 不再误判 400；所有响应均回显 `X-Request-ID`（§1.2）。
4. 未声明长度的分块请求体也被 413 拦截；服务端日志对密钥类片段做脱敏（§3、§4）。

## 8. M5-C-A 变更记录（v1，向后兼容）

### 8.1 `GET /api/v1/health` 新增字段

```json
{
  "entry_mode": "mock",
  "game_ready": true,
  "model_ready": false,
  "is_synthetic": true,
  "ledger": {
    "status": "mock",
    "global_used": 0,
    "global_limit": 0,
    "session_limit": 0,
    "epoch_fingerprint": null,
    "persistent": false
  },
  "breaker": null
}
```

- `model_available` 仅在 live 模式、provider 可用且非合成时为 `true`；Mock 模式恒为 `false`。
- `ledger.status`：`mock` / `not_configured` / `ready` / `unavailable`；真实模型不可用时附带非敏感原因。
- `breaker`：`{state, consecutive_failures, threshold}`，Mock 模式为 `null`。

### 8.2 `fallback_reason` 细化（仅新增取值）

- 原有：`timeout`、`model_unavailable`、`invalid_output`、`unsafe_output`、`unknown_intent`。
- 新增本地拒绝原因：`budget_global_exhausted`、`budget_session_exhausted`、`ledger_*`、`circuit_open`、`upstream_busy`。
- 上述原因不触发上游请求；HTTP 状态码语义不变（成功包络内降级）。

### 8.3 限流分桶

- 全局、客户端、会话对话、新建会话分别计数；超限仍返回 `429 RATE_LIMITED` 并带 `Retry-After`。
- 会话对话限流只作用于 `POST /api/v1/sessions/{id}/turns`；静态资源与健康接口不受业务限流。
