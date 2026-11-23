# DialogueSystem — NPC 对话状态模块（M3-B）

纯 C#、无 UnityEngine 依赖、可完全离线运行（固定台词不经过任何模型）。
契约来源：`Docs/DataSchema.md §5`（会话/turn/fallback_reason）、`Docs/Chapter01ImplementationMap.md §5`（已批准固定台词）。

## 文件

| 文件 | 作用 |
| --- | --- |
| `DialogueModel.cs` | 节点、选项、条件、披露（D/REC）、NPC 定义、目录 |
| `DialogueCatalogJson.cs` | 严格 JSON 加载器 |
| `DialogueEngine.cs` | 会话生命周期、选项推进、出示证据、自由文本接入 AI Provider、结果事件 |
| `Content/ch01_dialogue.json` | 老周 / 林遥 的固定对话与 D 规则 |

## 接口

```csharp
var catalog = DialogueCatalogJson.Parse(json);
var engine = new DialogueEngine(catalog, evidenceView, idGenerator, aiProvider /* 可空 */);
engine.EventRaised += e => { /* 写入 journal/event 流 */ };

DialogueTurnResult turn = engine.StartSession("npc_laozhou");
// turn.ConversationId / NodeId / Segments / AvailableOptions / SessionStatus / StatusContractValue

engine.Choose(turn.ConversationId, "opt.laozhou.ask_b01");
engine.GetAvailableOptions(turn.ConversationId);
DialogueEvidencePresentationResult p = engine.PresentEvidence(turn.ConversationId, new[] { "E02" });
// TriggeredDisclosureIds / Segments / NewlyPresentedFieldIds / AlreadyPresented / Events

DialogueTurnResult free = engine.SubmitFreeText(turn.ConversationId, "灯", timeoutMilliseconds: 3000);
// 成功：GeneratedBridge；失败：FallbackReason ∈ model_unavailable/timeout/invalid_output/unsafe_output/unknown_intent

engine.CloseSession(turn.ConversationId);
engine.ExpireOpenSessions();   // 读档后调用：所有 open → expired
engine.GetSession(turn.ConversationId).Status; // open/closed/cancelled/expired
```

### 会话与选项语义

- 同时只允许一个打开会话：`StartSession` 会关闭上一个（产生 `SessionClosed` 事件）。
- 选项 `kind` 为 `topic`（跳转节点）或 `end`（结束会话）；条件不满足的选项不出现在 `AvailableOptions` 中，直接 `Choose` 返回 `PRECONDITION_FAILED`。
- `npc_id` 必须是 `npc_` 前缀且存在于目录；`npc_xucheng` 在 CH01 目录中不存在 → `NOT_FOUND`。
- 空闲文本不会改变当前节点（AI 不能推进剧情），也不会授予证据。

### 证据出示（对齐 `npc.present` / `disclosure.trigger`）

- `PresentEvidence` 要求会话打开、证据为该 NPC 白名单、且证据已获得（完整卡片）；否则 `PRECONDITION_FAILED`。
- 引擎记录每个会话已出示的证据与字段；重复出示 → `AlreadyPresented == true`，不产生新事件，但仍重放该 NPC 已触发的固定台词。
- 满足 D 规则时自动触发一次（每个 NPC 每条 D 只触发一次），产生 `DisclosureTriggered` 事件：
  - D01：老周 + E02（台词已批准）
  - D02：林遥 + E03 + E04（台词已批准）；老周 + E03 + E04 为 `verification`，无新台词
  - D03：老周 + E01 + E05（台词已批准）
  - 林遥辨认表背：E01 且已观察 `watch.back_engraving`（recognition，不算 D）
- 已触发但对白为 `verification` 的 D 只返回空 `Segments`。

### 事件

`SessionOpened`、`TurnCompleted`、`EvidencePresented`、`DisclosureTriggered`、`SessionClosed`、`SessionExpired`，
字段：`EventId`、`EventType`、`ConversationId`、`NpcId`、`NodeId`、`DisclosureId`、`EvidenceIds`、`FieldIds`、`ContentRefs`、`ContentVersion`。

## 测试方法与结果

同 `M3B/Tools/build-and-test.ps1`。覆盖：会话状态转换、固定台词逐字校验、条件选项解锁、D01/D02/D03 触发与重复出示、`verification` 无台词、非法证据、自由文本回退且状态不变、Mock 桥接、生命周期与过期、对话 JSON 异常。
真实结果：`M3B/Tests/RESULTS.txt`（29/29 通过，其中 Dialogue 11 项）。

## 限制

- `content_ref` 中只有 `dialogue.CH01.B01.initial` 与 `dialogue.CH01.D02.linyao` 已在 DataSchema 记录；其余为建议值，待内容确认。
- 未实现 `npc.present` 的字段级显式 `field_ids` 子集：本模块以“整张证据”为单位出示，字段集合取已观察字段。
- 未实现 HTTP turn 的 202/polling 与 `fixed_delivery_token`；会话不持久化，读档后需 `ExpireOpenSessions`。
- 未在 Unity Editor 中运行（**未验证**）。
