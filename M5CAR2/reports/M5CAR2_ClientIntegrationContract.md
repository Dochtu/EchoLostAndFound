# M5-C-A-R2 客户端集成契约（交付给 M6-C）

> 本文是**客户端集成需求文档**，不是实现，也不是 Unity 玩法测试结论。本轮未修改任何 Unity 工程、场景、Prefab、美术资源或 `M6C_Work`。所有条目由 Codex 在 M6-C 写权限内实现与验证。

## 0. 服务端契约摘要（客户端必须遵守）

- 前缀 `/api/v1`；响应统一信封 `{"request_id","data","error"}`；成功看 HTTP 2xx **且** `data` 非空。
- `error` 含 `code`、`message`、可选 `details`；以 `code` 判断，不要匹配中文文案。
- 每个请求带 `X-Request-ID`（`[A-Za-z0-9._:-]{1,64}`），服务端回显同名头，用于日志对账。
- `content_version` 必须等于客户端期望的 `story-v1.0-phase2`；不一致时客户端应停止在线对话并提示重装/更新，而不是降级猜测。
- 若服务端启用 `LOCAL_AUTH_TOKEN`，客户端需带 `X-Dialogue-Token`（默认头名；不是 `Authorization`）。本地开发默认不启用。

## 1. API 基址运行时配置

**要求**：M6-C 构建不得把 `http://127.0.0.1:8787` 写死为唯一地址；必须支持“同源优先 + 显式覆盖”。

优先级（从高到低）：

1. URL 查询参数 `?api=https://host/prefix`（沿用现有 `StationApiClient.ResolveBaseUrl()` 行为，便于本地/灰度切换）；
2. 构建时注入的默认值（例如 `index.html` 中的 `window.__ELF_API_BASE__ = ""`，由发布脚本写入；空串表示同源）；
3. 同源推导：`Application.absoluteURL` 为 http(s) 时取其 origin；
4. 本地编辑器/兜底：`http://127.0.0.1:8787`。

**验收**：

- 同一份构建在“同源部署”和“`?api=` 指向另一主机”两种方式下都能工作；
- 基址末尾斜杠不产生 `//api`；
- 不在任何资源、文本、PlayerPrefs、日志中写密钥。

## 2. 同源请求支持

- 推荐部署形态：WebGL 静态文件与 `/api/v1` 由**同一 FastAPI 进程**提供（`WEB_ROOT` 指向静态目录，默认 7860 端口），此时无需 CORS。
- 若必须跨源：服务端 `CORS_ALLOWED_ORIGINS` 必须配置**精确 origin**（不接受 `*`），客户端不得携带 Cookie；预检需允许 `Content-Type`、`X-Request-ID`、`X-Dialogue-Token`。
- 客户端不得假定 `Authorization` 头可用：ModelScope 网关会保留/覆盖该头。

## 3. 会话过期与 404 恢复

现状（`StationDialogueBridge.cs`）：`turns` 返回 404/410 时把 `session.Id=null`、`Online=false`，仅提示“本次交谈已过期”，**不重建**。M6-C 需改为可恢复：

1. 收到 404 `NOT_FOUND` 或 410 `TURN_EXPIRED`：
   - 立即把本地 `conversation_id` 置空；
   - 用当前 `npc_id` + 最近一次 `evidence_ids/observed_field_ids` **重建一次** `POST /sessions`；
   - 重建成功后，把用户**尚未得到回复**的那条输入重发一次；
   - 仍失败 → 进入离线态，提示“在线对话暂不可用，固定剧情可继续”。
2. 自动重建**最多一次**，禁止循环重试；重建后要提示“连接已恢复/会话已重建”。
3. `conversation_id` 只在内存 + 本地持久化中各存一份（见 §7），不得用存档里的旧 ID 直接信任。
4. 展示 `opening_segments` 时不要把它当作玩家已看到的历史；刷新后不重放旧对话。

## 4. 429 与 503 处理

| 状态 | 含义 | 客户端行为 |
| --- | --- | --- |
| 429 `RATE_LIMITED` | 本地限流（默认 60/min，burst 20） | 读 `Retry-After` 或 `details.retry_after_seconds`，禁用发送按钮并倒计时；**不自动重发**，倒计时结束由玩家手动再发 |
| 429 `TURN_BUSY`（预留） | 同一会话并发 | 禁止并发发送（现有 `Send` 已有 in-flight 保护），提示“上一条还在处理” |
| 503 | **平台边缘/冷启动**，不是应用契约码 | 指数退避重试，最多 3 次（1s/2s/4s），仍失败则离线提示；不得当作“会话过期”处理 |
| 502/504 | 网关错误 | 同 503 |
| 500 `INTERNAL_ERROR` | 服务端异常 | 不自动重试；提示 + 记录 `request_id` 供排查 |

## 5. Mock 降级

- 服务端 `MODEL_PROVIDER=mock` 时返回 `source=fixed_line` 或 `source=mock`，且 `is_synthetic=true`；客户端必须把这种回复标为“演示/离线模式”，不得伪装成真实模型。
- 服务端 `source=fallback` 仍是 HTTP 200，客户端应按正常回复展示，但可附“本轮为固定内容（原因：…）”；`fallback_reason` 不要直接展示英文枚举，映射为中文提示。
- `/meta` 不可达或 `content_version` 不匹配 → 关闭在线输入，保留固定调查/剧情；**不得**在客户端伪造 NPC 回复或本地生成“模型风格”文本。
- 网络恢复后允许玩家手动重连（重新 `Probe`），不做后台轮询风暴。

## 6. 中文 NPC 对话

- 输入：沿用 Native DOM 输入桥；单条文本 1–1000 字符（服务端限制），超长在客户端截断并提示；不得发送空串。
- 字体：使用现有中文 TMP 字体/图集，覆盖对话、选项、错误提示、标点与省略号；WebGL 构建后检查缺字（豆腐块）。
- 展示：保留说话人、正文、`suggested_actions`（可点击填入输入框，不自动发送）；`fixed_segments` 按顺序展示。
- 错误文案统一中文，禁止把英文 `error.code` 直接暴露给玩家（可折叠在调试信息里）。
- 不得把“服务端接口测试通过”表述为“Unity 对话玩法通过”。

## 7. WebGL 刷新后的会话恢复

服务端会话在内存，刷新/重启后旧 ID 必然 404（E2E R2 已证明）。客户端需：

1. 在 `PlayerPrefs`/`localStorage` 持久化：`conversation_id`、`npc_id`、`last_turn_id`、`evidence_ids` 快照、`observed_field_ids` 快照、`saved_at`。
2. 页面启动后：若存在 `conversation_id`，先 `GET /sessions/{id}` 校验；
   - 200 → 恢复在线态，显示“已恢复上次对话”，不重放历史；
   - 404/410 → 丢弃 ID，标记“需要重新开始对话”，等玩家主动开口时再 `POST /sessions`；
   - 网络错误 → 离线态，不清空本地调查进度。
3. 本地调查状态（`StationInvestigation` 的 PlayerPrefs 检查点）继续作为调查进度权威；服务端会话只负责对话。
4. 不得在刷新后自动重发上一条玩家输入（避免重复计费/重复回复）；仅当 404 发生在“本次发送的响应”上时，才允许按 §3 重发一次。

## 8. 兼容性要求

- 超时：普通请求 15 s、回合 12 s（与 `AI_TIMEOUT_MS` 一致）；超时展示可重试提示，不自动重试。
- 证据：仍以本地 `EvidenceRegistry` 为权威；服务端 `POST /evidence` 返回的 `triggered_disclosure_ids` 只用于展示/日志，不得反向改写证据状态；`409 PRECONDITION_FAILED` 表示该组合无已批准回应，客户端提示“暂无对应回应”，不视为错误弹窗。
- 未知意图/不安全输出：服务端已兜底为 `fallback`，客户端正常展示。
- `X-Request-ID`：失败时把该 ID 显示在可复制的调试信息中。
- 分辨率：960×600 与 1280×720 下对话面板、按钮、长文本不截断。

## 9. 交付给 Codex 的验收清单（客户端侧）

- [ ] 构建产物中无硬编码唯一 API 地址；`?api=` 与同源两种方式可用。
- [ ] 同源部署时无 CORS 报错；跨源时按精确 origin 配置可用。
- [ ] 杀掉服务端进程后，客户端显示离线态且固定剧情可继续；重启服务端后可手动恢复。
- [ ] 会话 404 后自动重建一次并成功续聊；重建失败给出中文提示。
- [ ] 429 显示倒计时且不自动重发；503 退避 3 次后提示。
- [ ] mock 模式明确标注“演示模式”，不冒充真实模型。
- [ ] 中文输入、中文回复、标点、长文本、两档分辨率均正常。
- [ ] 刷新页面后：本地调查进度保留；在线会话按 §7 恢复或提示重新开始。
- [ ] 以上均有截图/录屏与日志，且与最终 WebGL 候选哈希绑定。

以上九项为客户端验收要求，本轮**未执行**，不得在 M5-C-A-R2 报告中记为通过。
