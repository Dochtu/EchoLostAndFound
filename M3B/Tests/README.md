# Tests — M3-B 单元测试

零第三方依赖的 C# 控制台测试器（自写 `Assert`/`TestRegistry`），与模块一起由 `Tools/build-and-test.ps1` 编译运行。
模块按 netstandard2.1 编译（Unity 兼容面）；测试器按 net10.0 编译并引用模块 DLL。

## 运行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "G:\projects\EchoLostAndFound\M3B\Tools\build-and-test.ps1"
```

- 输出：控制台 + `Tests/RESULTS.txt`（含时间戳、编译器路径、逐项结果）。
- 退出码：0 全通过；1 有失败；2 内容加载失败。

## 覆盖（对应任务四）

| 要求 | 测试 |
| --- | --- |
| 证据正常获取 | `Evidence_CompleteCardIsAcquiredWithEvents`、`Integration_OfflineInvestigationFlow` |
| 重复证据处理 | `Evidence_ObservationIsIdempotent`、`Evidence_DuplicateRegistrationIsIdempotent`、`Dialogue_EvidencePresentationTriggersD01`（重复出示） |
| 无效证据 ID | `Evidence_InvalidIdsAreRejected`（畸形/未知/空/整批回滚）、`Dialogue_PresentationRejectsUnknownEvidence` |
| NPC 对话状态转换 | `Dialogue_SessionTransitionsAndFixedLines`、`Dialogue_SessionLifecycleAndExpiry` |
| 条件分支 | `Dialogue_ConditionalOptionUnlocksAfterDisclosure` |
| 出示证据 | `Dialogue_EvidencePresentationTriggersD01`、`Dialogue_D02RequiresBothDocuments`、`Dialogue_D02VerificationForLaozhouHasNoLine`、`Dialogue_D03RequiresWatchAndInspection` |
| JSON 数据异常 | `Evidence_CatalogJsonRejectsAnomalies`、`Evidence_SnapshotJsonRejectsAnomalies`、`Dialogue_CatalogJsonRejectsAnomalies`、`Mock_FixtureJsonRejectsAnomalies` |
| Mock 服务失败回退 | `Mock_TimeoutAndTransportErrorFallBack`、`Mock_InvalidAndUnsafeOutputAreRejected`、`Mock_NoMatchAndUnknownNpcFallBack`、`Mock_ContentVersionMismatchFallsBack`、`Dialogue_FreeTextFallbackNeverChangesState`、`LlmAdapter_MapsTransportFailuresToFallbacks` |

附加：`Dialogue_FreeTextUsesMockBridgeOnly`（AI 只产生 bridge）、`Mock_CompletedReplyIsSyntheticAndDeterministic`（确定性/合成标识）、`Mock_EvidenceConditionsGateScenarios`、`Evidence_SnapshotRoundTrips` / `Evidence_SnapshotRejectsCorruption`、`Evidence_IncompleteRegistrationFails`。

## 文件

| 文件 | 作用 |
| --- | --- |
| `TestFramework.cs` | Assert、异常断言、注册表、结果输出 |
| `TestData.cs` | 内容路径与惰性目录加载、测试用 Registry/Engine 构造 |
| `EvidenceSystemTests.cs` | 9 项 |
| `DialogueSystemTests.cs` | 11 项 |
| `MockAiProviderTests.cs` | 8 项 |
| `IntegrationTests.cs` | 1 项端到端（与 IntegrationGuide 示例一致） |
| `Program.cs` | 入口，参数为内容根目录 |
| `RESULTS.txt` | 最近一次真实运行记录 |

## 未验证项

- 未在 Unity Test Framework（NUnit EditMode/PlayMode）中运行；本套件不依赖 Unity API，可后续迁移。
- 未在 WebGL/IL2CPP 构建中验证；已按 netstandard2.1 API 面与同步调用编写。
