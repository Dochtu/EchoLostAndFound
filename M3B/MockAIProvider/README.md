# MockAIProvider — AI Mock 服务（M3-B）

独立的 `INpcAiProvider` 实现：确定性、可离线、无 API Key、无网络。
输出明确标记为合成测试内容（`ProviderId = "mock-deterministic"`、`IsSynthetic = true`、文案带“模拟回复·仅测试”），
**不伪装成真实 LLM 推理**，也不会授予证据或修改游戏规则状态。

## 文件

| 文件 | 作用 |
| --- | --- |
| `MockAiModels.cs` | 场景定义/匹配、场景集、fixture JSON 加载器 |
| `MockAiProvider.cs` | `MockAiProvider`、`NpcReplyValidation`（结构化回复校验与安全过滤） |
| `LlmBackedNpcAiProvider.cs` | 预留真实大模型适配层：`ILlmNpcReplyTransport` + `LlmBackedNpcAiProvider`（默认无 transport，必须显式注入，不做网络请求） |
| `Content/mock_ai_fixtures.json` | 7 条固定测试场景（回复/超时/传输错误/坏输出/不安全输出/证据门槛） |

## 接口

```csharp
var scenarios = MockAiScenarioJson.Parse(fixturesJson);
var provider = new MockAiProvider(scenarios);              // 或 MockAiProvider.FromJson(json)

var request = new NpcAiRequest(
    requestId: "req-1",
    npcId: "npc_laozhou",
    playerInput: "灯",
    acquiredEvidenceIds: evidence.AcquiredEvidenceIds,
    availableTopicIds: new[] { "opt.laozhou.ask_b01" },
    timeoutMilliseconds: 3000,
    contentVersion: "story-v1.0-phase2");

NpcAiReply reply = provider.Generate(request);
// reply.Outcome / ProviderKind / ProviderId / IsSynthetic / Text / SuggestedTopicId / FallbackReason / FailureDetail
```

### 行为

| 条件 | 结果 |
| --- | --- |
| `content_version` 不符 | `ModelUnavailable`，detail `content_version_mismatch` |
| 无匹配场景 | `UnknownIntent`，detail `no_fixture_match` |
| `behavior = timeout` | `TimedOut`，detail `simulated_timeout` |
| `behavior = transport_error` | `ModelUnavailable`，detail `simulated_transport_error` |
| `behavior = reply` 且 JSON 合法 | `Completed`，`IsSynthetic = true` |
| 回复缺字段/非 JSON/npc_id 不符 | `InvalidOutput`，detail 指明原因 |
| 含 `<`/`>` 或注入类片段 | `UnsafeOutput` |

`NpcReplyValidation` 还会校验文本长度（≤400），并只保留白名单内的 `suggested_topic_id`。

### 预留真实模型适配

```csharp
sealed class MyTransport : ILlmNpcReplyTransport
{
    public LlmTransportResponse Send(NpcAiRequest request) { /* 未来由服务端代理实现 */ }
}

var real = new LlmBackedNpcAiProvider(new MyTransport()); // ProviderKind 为 ExternalModel，IsSynthetic=false
```

适配层不包含密钥、不发起网络请求；错误、超时、非法输出全部映射为 `NpcAiReply` 回退，调用方无需感知传输细节。
（真实接入属于后续阶段，需服务端环境变量与安全评审，当前**未实现**。）

## 测试方法与结果

同 `M3B/Tools/build-and-test.ps1`。覆盖：完成回复且确定性、超时/传输错误回退、非法/不安全输出拒绝、无匹配与保留 NPC、证据门槛、版本不符、fixture JSON 异常、真实模型适配器的失败映射。
真实结果：`M3B/Tests/RESULTS.txt`（29/29 通过，其中 Mock 8 项）。

## 限制

- fixture 文案全部为测试用合成文本，**不是正式剧情内容**。
- 超时/错误为 fixture 模拟，不依赖真实时钟或网络。
- 未在 Unity Editor 中运行（**未验证**）。
