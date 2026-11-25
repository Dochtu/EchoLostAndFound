# M5-C-A 移交给 Codex 的说明

日期：2026-11-25
对象：Codex（美术/客户端工作区负责人）
结论先行：**本轮不需要重新构建 Unity，不需要修改任何 Scene/Prefab/美术资源；客户端协议向后兼容。** 唯一可选的改动是前端展示"模型状态"，不是必需项。

---

## 1. 本轮改动范围

- 修改：`Server/`（FastAPI 后端）、`.gitignore`、新增 `M5CA/` 与 `Builds/M5CA/candidate`。
- 未修改：`EchoLostAndFound_WebGL/`、`Assets/`、`ProjectSettings/`、`Packages/`、`Builds/M4D-Dev/M5A/`、`M5B/` 既有产物。
- 未触碰：`Assets/_Project/Art/`、`Materials/`、`VFX/`、`Audio/`（Codex 美术工作区）。

## 2. 协议兼容性

| 项目 | 变化 | 客户端影响 |
| --- | --- | --- |
| `/api/v1/sessions`、`/turns`、`/evidence`、`/cancel` | 请求/响应字段未删除、未改语义 | 无 |
| `/api/v1/health` | **只新增字段**：`entry_mode`、`game_ready`、`model_ready`、`model_mode`、`is_synthetic`、`ledger`、`breaker` | 旧解析忽略新字段即可 |
| `provider` 对象 | 保持 `kind/id/is_synthetic` | 无 |
| 错误码 | 未改；新增 429 的 `RATE_LIMITED` 语义沿用旧约定 | 已存在的错误处理可复用 |
| `fallback_reason` | 新增取值：`budget_global_exhausted`、`budget_session_exhausted`、`ledger_unavailable`、`ledger_*`、`circuit_open`、`upstream_busy` | 若前端按字符串分支，建议加默认分支；不识别也不影响流程 |
| 固定台词 `source` | 仍为 `fixed_line`；`fallback` 语义不变 | 无 |

**结论**：不需要改 Unity 代码。如果客户端对未知 JSON 字段做了严格反序列化（例如 `JsonUtility` 本身会忽略未知字段，通常无问题），请确认一次即可。

## 3. 可选前端增强（非必须）

如果希望在 HUD 上提示"AI 状态"，可读取：

```json
{
  "entry_mode": "mock|live",
  "game_ready": true,
  "model_ready": true,
  "model_mode": "mock|live|unavailable",
  "is_synthetic": true,
  "fallback_reason": "budget_global_exhausted"
}
```

建议文案：
- `model_ready=false` 或 `is_synthetic=true`：不提示或提示"离线对话模式"，**不要**展示成"AI 已接入"。
- `fallback_reason` 以 `budget_` 开头：可提示"本班次对话额度已用完，仍可继续调查"。
- 其余 fallback：静默降级，不打断玩家。

注意：不要在前端展示 `ledger.epoch_fingerprint`（内部运维字段），也不要尝试读取或传递 API Key（客户端本来就没有）。

## 4. 需要 Codex 复核的点

1. WebGL 页面在 mock 模式下仍能完整走完第一章（本轮后端未改内容包与规则，回归已由 206 测试 + E2E M2 覆盖）。
2. 如果客户端有"健康检查"轮询，确认新增字段不会导致解析异常。
3. 如果美术工作区需要重启本地服务，使用 `Builds/M5CA/candidate` 的 mock compose（端口 18080），不要与 M5-A 候选混用端口。
4. 不要修改 `Server/app/content/*.json`；内容变更需走 Narrative/QA 流程。

## 5. 本地启动方式（给客户端联调用）

```powershell
cd G:\projects\EchoLostAndFound\Builds\M5CA\candidate
docker compose -f docker-compose.mock.yml up -d --build
# http://127.0.0.1:18080
```

Mock 模式**不会**发出任何外部模型请求（E2E M6 已验证 fake 上游请求数为 0）。

## 6. 明确不要做的事

- 不要重新构建 WebGL 并把构建产物提交进 Git（采用"源码入库、构建产物独立发布"策略）。
- 不要覆盖 `Builds/M4D-Dev/M5A/candidate`。
- 不要将本候选部署到线上创空间（等待技术负责人验收）。
- 不要把本地假上游的回复当作真实 AI 效果对外展示（`is_synthetic`/`provider.kind` 已如实标注）。

## 7. 联系与证据

- E2E 结果：`M5CA/evidence/e2e/e2e_results.json`（21/21）
- 单元/集成：`M5CA/evidence/tests/pytest-verbose.txt`（206 passed）
- 部署与配置：`M5CA/reports/M5CA_ModelScope_ConfigGuide.md`
- 架构：`M5CA/reports/M5CA_Architecture.md`

如客户端确需协议变更，请先提交影响清单，由技术负责人授权后再动 Unity 工程。
