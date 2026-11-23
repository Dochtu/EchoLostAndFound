# HandoffToCodex_M3 — M3-B 交接包

日期：2026-11-23 ｜ 来源：游戏逻辑工程师（M3-B）
状态：模块已实现、已编译、29/29 测试通过；**未写入 Unity Assets**，Unity 内编译与运行**未验证**。
本交接不涉及原始 HDRP 工程改造，不触碰 Codex 正在使用的场景、Prefab、ProjectSettings、Packages。

## 1. 交付范围

| 目录 | 内容 |
| --- | --- |
| `M3B/Shared/` | 严格 JSON 读写、错误码、`IEvidenceStateView`、`INpcAiProvider` 与 DTO |
| `M3B/EvidenceSystem/` | 证据目录、登记表、快照、视图、事件 |
| `M3B/DialogueSystem/` | 会话、节点、选项、条件、D/REC、自由文本桥接 |
| `M3B/MockAIProvider/` | 确定性 Mock、回复校验/安全过滤、真实模型适配占位 |
| `M3B/Tests/` | 29 项控制台测试 + 真实运行结果 `RESULTS.txt` |
| `M3B/Tools/build-and-test.ps1` | 无 MSBuild/NuGet 的 Roslyn 构建与测试脚本 |
| `M3B/IntegrationGuide.md` | 装配顺序、契约映射、边界 |
| `M3B/*/README.md` | 各模块接口、测试方法、运行结果 |

所有代码在工作目录 `G:\projects\EchoLostAndFound\M3B\`，与 `Assets/` 完全隔离。

## 2. 文件清单（相对 `M3B/`）

```
EvidenceSystem/EvidenceModel.cs
EvidenceSystem/EvidenceCatalogJson.cs
EvidenceSystem/EvidenceRegistry.cs
EvidenceSystem/EvidenceSnapshot.cs
EvidenceSystem/EvidenceViews.cs
EvidenceSystem/Content/ch01_evidence.json
DialogueSystem/DialogueModel.cs
DialogueSystem/DialogueCatalogJson.cs
DialogueSystem/DialogueEngine.cs
DialogueSystem/Content/ch01_dialogue.json
MockAIProvider/MockAiModels.cs
MockAIProvider/MockAiProvider.cs
MockAIProvider/LlmBackedNpcAiProvider.cs
MockAIProvider/Content/mock_ai_fixtures.json
Shared/Json/{JsonValue,JsonReader,JsonWriter,JsonContract,JsonDataException}.cs
Shared/Contracts/{GameContractException,IEvidenceStateView}.cs
Shared/Ai/NpcAiContracts.cs
Tests/{Program,TestFramework,TestData,EvidenceSystemTests,DialogueSystemTests,MockAiProviderTests,IntegrationTests}.cs
Tests/RESULTS.txt
Tools/build-and-test.ps1
IntegrationGuide.md
HandoffToCodex_M3.md
```

共 19 个运行时 `.cs`、7 个测试 `.cs`、3 份内容 JSON、1 个构建脚本。

## 3. 导入 Unity 的建议步骤（由 Codex 执行，需 Game Director 授权）

1. 在 `Assets/_Project/Scripts/M3B/` 下按模块建目录，复制对应 `.cs` 与 `Shared/`。
2. 为每个模块添加 asmdef（下节内容）。**不要**把 `Tests/` 拷入 Unity；控制台测试保持在 `M3B/`，避免与现有 NUnit 程序集冲突。
3. 内容 JSON 放入 `Assets/_Project/Resources/M3B/`（`Resources.Load<TextAsset>("M3B/ch01_evidence")` 等）。
   未使用 Addressables；文件很小。也可放 StreamingAssets，但 WebGL 需 `UnityWebRequest`，不推荐。
4. 在集成层读取 `TextAsset.text` 后调用 `*Json.Parse`；内容版本不一致时拒绝启动（`story-v1.0-phase2`）。
5. 证据/对话事件写入现有 journal/存档前，先与 QA 对齐 schema；本模块不直接写 `PlayerStateView`。

### asmdef

`Assets/_Project/Scripts/M3B/Shared/EchoLostAndFound.Shared.asmdef`

```json
{
  "name": "EchoLostAndFound.Shared",
  "rootNamespace": "EchoLostAndFound.Shared",
  "references": [],
  "includePlatforms": [],
  "excludePlatforms": [],
  "allowUnsafeCode": false,
  "overrideReferences": false,
  "precompiledReferences": [],
  "autoReferenced": false,
  "defineConstraints": [],
  "versionDefines": [],
  "noEngineReferences": true
}
```

`EchoLostAndFound.Evidence.asmdef`、`EchoLostAndFound.Dialogue.asmdef`、`EchoLostAndFound.MockAi.asmdef`
均与上面相同，仅 `name`/`rootNamespace` 改为对应模块，并设置 `"references": ["EchoLostAndFound.Shared"]`。
所有模块 `noEngineReferences: true`（源码不使用 UnityEngine）。若集成层需要 UnityEngine，另建 `EchoLostAndFound.M3B.Integration.asmdef` 引用这四个模块。

> 未提供 `.meta`/GUID：Unity 首次导入时自动生成。当前没有其他程序集引用这些模块，不存在 GUID 冲突。

## 4. Codex 集成点

| 场景 | 用法 |
| --- | --- |
| 场景交互获得证据 | `registry.ObserveFields(fieldIds)`；完成即自动登记（或关闭自动登记后显式 `RegisterEvidence`） |
| 证据 UI | `GetVisibleEvidenceRecords()` / `FindVisibleRecord()`；媒体键 `evidence.E01.front` 等自行映射贴图 |
| 对话 UI | `StartSession` → 显示 `Segments`；`AvailableOptions` 渲染为按钮；`Choose` 推进 |
| 出示证据 UI | `PresentEvidence(sessionId, evidenceIds)` → 展示返回 `Segments`，并刷新选项 |
| 自由输入 | `SubmitFreeText(...)`；`GeneratedBridge` 仅作为“生成桥接文本”，UI 必须标注为 AI（非固定台词），回退时显示 `FallbackReason` 对应提示 |
| 存档 | `CreateSnapshot().ToJson()` 存证据部分；会话不存，读档后 `ExpireOpenSessions()` |
| 事件流 | 两个 `event` 均带 `EventId`，可直接作为 `event_ids` 写入 |

安全边界（已实现）：AI 回复不能授予证据、不能跳转节点、不能执行规则；`NpcAiReply` 结构里没有这些字段。
Mock 文本明确含“模拟回复·仅测试”，`IsSynthetic = true`，不得进入正式剧情数据。

## 5. 与 DataSchema 的差异（需知情）

1. **整张证据 vs 字段级出示**：`npc.present` 允许显式 `field_ids` 子集；当前 `PresentEvidence(conversationId, evidenceIds)` 以整张已获得证据为单位，字段集取该证据全部已观察字段。字段级子集需要重载，未实现。
2. **HTTP 会话层未建模**：无 202/polling、`fixed_delivery_token`、幂等键、TURN_BUSY；模块是同步确定性内核。
3. **`already_presented` 粒度**：按“会话内是否已出示过该证据集合”判断（`DialogueEvidencePresentationResult.AlreadyPresented`），与契约字段语义接近但不等同于服务端完整语义。
4. **D/REC 归属**：D02 对老周为 `verification`，返回空 `Segments`（无新台词）；这是按已批准资料的设计，不是遗漏。
5. **R 规则**不在本阶段。

## 6. 内容待确认（不得直接当作正式设定）

| 项 | 现状 | 需要 |
| --- | --- | --- |
| `dialogue.CH01.opening.laozhou` / `.linyao` | 建议值（台词已批准，ref 未登记） | Narrative 确认 ref |
| `dialogue.CH01.D01.laozhou` | 建议值（台词已批准） | 同上；DataSchema 未记录 ref |
| `dialogue.CH01.D03.laozhou` | 建议值（台词已批准） | 同上 |
| `dialogue.CH01.linyao.engraving` | 建议值（台词已批准） | 同上 |
| `dialogue.CH01.linyao.refusal` | 建议值（台词已批准） | 同上 |
| E02–E05 `source_label` / `area_id` | 由 `evidence_matrix.md` 推导 | Narrative 确认 |
| Mock fixture 文本 | 合成测试文本 | 不得作为正式台词 |

已登记且逐字校验的 ref 仅：`dialogue.CH01.B01.initial`、`dialogue.CH01.D02.linyao`。

## 7. 验证证据

- 命令：`powershell -NoProfile -ExecutionPolicy Bypass -File "G:\projects\EchoLostAndFound\M3B\Tools\build-and-test.ps1"`
- 编译：Roslyn `csc.dll`（SDK 11.0.100）；模块 19 文件按 netstandard2.1；测试 7 文件按 net10.0。
- 结果：`M3B/Tests/RESULTS.txt`，2026-11-23 18:32:40 +08:00，**Total 29 / Passed 29 / Failed 0**。
- 覆盖任务四全部 8 类要求（映射见 `M3B/Tests/README.md`）。

## 8. 未验证项（必须如实记录）

- Unity Editor 内编译、PlayMode、WebGL/IL2CPP 构建均未执行。
- 未接入真实大模型；`LlmBackedNpcAiProvider` 仅用假 transport 验证错误映射，无网络、无密钥。
- 未与现有 M2 交互/存档代码联调；未做 UI 绑定。
- 测试脚本依赖本机 dotnet SDK 与 packs 路径，换机器需改 `Tools/build-and-test.ps1` 顶部路径。

## 9. 边界与回滚

- 本交付只在 `G:\projects\EchoLostAndFound\M3B\` 内新增文件；未修改 `Assets/`、`ProjectSettings/`、`Packages/`、场景、Prefab。
- 回滚：删除 `M3B/` 即可，不影响工程其余部分。
- 导入 Assets 属跨模块写入，需 Game Director 明确授权具体文件清单后再执行。
