# IntegrationGuide — M3-B 调查逻辑集成说明

适用对象：Unity 工程师（Codex）、Game Director、QA。
本文描述 `M3B/` 内四个纯 C# 模块如何装配、调用、与 `Docs/DataSchema.md` 契约对应，以及已知边界。
**不修改现有场景、Prefab、ProjectSettings、Packages。** 如需写入 Unity Assets，见 `HandoffToCodex_M3.md` 的交接步骤。

## 1. 架构

```
                 ┌────────────────────────────┐
                 │ Shared (JSON / 契约 / AI 接口) │
                 └──────┬────────┬────────┬────┘
                        │        │        │
              EvidenceSystem  DialogueSystem  MockAIProvider
                        ▲        │              ▲
                        └────────┴──────────────┘
                        IEvidenceStateView（Dialogue 只依赖接口）
```

- 全部源码无 `UnityEngine` 引用，按 netstandard2.1 编译（C# 9），IL2CPP/WebGL 友好；无第三方依赖。
- `Shared`：严格 JSON 读写（拒绝未知字段、重复键、非法枚举）、`GameContractException` 错误码、`IEvidenceStateView`、`INpcAiProvider`/`NpcAiRequest`/`NpcAiReply`。
- `EvidenceSystem`：证据状态与快照。
- `DialogueSystem`：会话/节点/选项/条件/D 规则；通过 `IEvidenceStateView` 读取证据，不反向依赖 `EvidenceSystem`。
- `MockAIProvider`：确定性 AI 回退与真实模型适配占位。
- 关键状态（证据、节点、D 是否触发）只由上述确定性代码决定；AI 输出只作为 `GeneratedBridge` 文本，不能授予证据或命令。

## 2. 装配顺序

```csharp
// 1) 内容（一次加载，内容版本必须一致）
var evidenceCatalog  = EvidenceCatalogJson.Parse(evidenceJson);
var dialogueCatalog  = DialogueCatalogJson.Parse(dialogueJson);
var mockScenarios    = MockAiScenarioJson.Parse(mockFixturesJson);
if (evidenceCatalog.ContentVersion != dialogueCatalog.ContentVersion) { /* 内容版本冲突，拒绝启动 */ }

// 2) 状态
var evidence = new EvidenceRegistry(evidenceCatalog, new GuidIdGenerator());
var mock     = new MockAiProvider(mockScenarios);
var dialogue = new DialogueEngine(dialogueCatalog, evidence, new GuidIdGenerator(), mock);

// 3) 事件（写入 journal / 持久化事件流）
evidence.StateChanged += e => journal.Append(e);
dialogue.EventRaised  += e => journal.Append(e);

// 4) 读档恢复
var snapshot = EvidenceSnapshot.ParseAndValidate(evidenceCatalog, saveJson);
var restored = new EvidenceRegistry(evidenceCatalog, snapshot);
var restoredDialogue = new DialogueEngine(dialogueCatalog, restored, new GuidIdGenerator(), mock);
restoredDialogue.ExpireOpenSessions();   // 会话不持久化，读档后必须过期
```

完整可运行示例即 `M3B/Tests/IntegrationTests.cs`（`Integration_OfflineInvestigationFlow`，已编译并通过）。

## 3. 调查流程（离线，无需网络）

1. `StartSession("npc_laozhou")` → 开场固定台词（不调用模型）。
2. `Choose(..., "opt.laozhou.ask_b01")` → B01 固定台词。
3. `PresentEvidence(..., new[]{ "E02" })` → 触发 D01 固定台词，并解锁“重复询问 B01”选项（依赖 `requires_disclosure_ids: ["D01"]`）。
4. `PresentEvidence(..., new[]{ "E03","E04" })`（林遥会话）→ D02；只交 E03 不触发。
5. `SubmitFreeText(..., "灯")` → 调用注入的 `INpcAiProvider`；Mock 返回带“模拟回复·仅测试”的合成文本；无 provider/超时/非法输出 → `FallbackReason`，状态不变。
6. 证据全部获得后 `CreateSnapshot()`；读档走第 2 节第 4 步。

## 4. 与 DataSchema 的对应

| DataSchema 契约 | 本模块 |
| --- | --- |
| `evidence.register`（幂等、`already_registered`） | `EvidenceRegistry.RegisterEvidence`（`AlreadyRegistered`，空数组、无事件） |
| 字段观察 | `ObserveField(s)`（未知字段整批失败） |
| `npc.present` | `DialogueEngine.PresentEvidence`（证据级；`AlreadyPresented` 按会话） |
| `disclosure.trigger` | `PresentEvidence` 内自动评估 D，产生 `DisclosureTriggered` 事件 |
| D01 / D02 / D03 / REC | `ch01_dialogue.json`；D02 老周为 `verification`（无新台词） |
| `fallback_reason` 枚举 | `NpcAiFallbackReasons`（`model_unavailable/timeout/invalid_output/unsafe_output/unknown_intent`） |
| 会话状态 | `open/closed/cancelled/expired`（`StatusContractValue`） |
| 固定台词 `content_ref` + `text` | `DialogueSegment(ContentRef, Text)` |
| 错误码 | `GameContractException`（400/409/410/422 等与 §7 一致） |
| 会话不持久化、恢复即过期 | `ExpireOpenSessions()` |

未建模的 HTTP 细节（202/polling、`fixed_delivery_token`、幂等键）留给后续服务层；模块提供确定性内核。

## 5. 内容文件

- `EvidenceSystem/Content/ch01_evidence.json`：`content_version` + `evidence[]`；字段 id、固定文案、`proof_limits`、`media_refs` 与 DataSchema 一致。
- `DialogueSystem/Content/ch01_dialogue.json`：`content_version` + `npcs[]`（节点、选项、条件、D/REC）。
- `MockAIProvider/Content/mock_ai_fixtures.json`：`provider_id`、`content_version`、`scenarios[]`（回复/超时/错误/非法/不安全/证据门槛）。

三份内容均严格校验：未知字段、未知枚举、重复 ID、根类型错误都会抛 `JsonDataException`（JSON 异常）或 `GameContractException`（语义校验）。

## 6. 运行测试

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "G:\projects\EchoLostAndFound\M3B\Tools\build-and-test.ps1"
```

- 直接调用 Roslyn（`csc.dll`），不依赖 MSBuild/NuGet；模块引用 netstandard2.1 参考集，测试器引用 net10.0 参考集。
- 结果写入 `M3B/Tests/RESULTS.txt`；最近一次：2026-11-23，**29/29 通过**。

## 7. 已知边界 / 待确认

1. **Unity 内编译与 PlayMode：未验证。** 沙箱无 Unity 批处理执行，仅完成 netstandard2.1 编译与逻辑测试。
2. 六条 `content_ref` 为建议值（仅 B01.initial、D02.linyao 已在 DataSchema 记录），需内容确认后再写入正式数据。
3. E02–E05 的 `source_label`、`area_id` 由证据矩阵推导，待内容确认。
4. `npc.present` 的显式 `field_ids` 子集未实现：当前以整张已获得证据出示；字段级出示需扩展 `PresentEvidence` 重载。
5. 对话会话不持久化、无 HTTP 层、无 UI（TMP/uGUI 绑定由 Codex 完成）。
6. 真实 LLM 适配仅有接口与失败映射，未接真实服务、无密钥。
7. R 规则不在 M3-B 范围。
