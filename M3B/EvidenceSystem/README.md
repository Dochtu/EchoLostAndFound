# EvidenceSystem — 证据管理模块（M3-B）

纯 C#、无 UnityEngine 依赖、netstandard2.1 API 面（可在 Unity IL2CPP/WebGL 下编译）。
业务契约来源：`Docs/DataSchema.md`（证据 ID、字段登记表、固定文案、幂等语义、错误码）。

## 文件

| 文件 | 作用 |
| --- | --- |
| `EvidenceModel.cs` | `EvidenceSourceKind`、`EvidenceFieldDefinition`、`EvidenceDefinition`、`EvidenceCatalog`、`EvidenceIdRules` |
| `EvidenceCatalogJson.cs` | 严格 JSON 加载器（未知字段/非法枚举/重复 ID 一律拒绝） |
| `EvidenceRegistry.cs` | 运行时状态：观察字段、自动/手动登记证据、事件、查询 |
| `EvidenceSnapshot.cs` | 存档快照序列化、反序列化与校验 |
| `EvidenceViews.cs` | `EvidenceStatus`、`ObservedFieldView`、`VisibleEvidenceRecord`（供 UI 只读消费） |
| `Content/ch01_evidence.json` | 第一章 E01–E05 内容（固定文案与 DataSchema 一致） |

## 接口

### 目录

```csharp
var catalog = EvidenceCatalogJson.Parse(json);
EvidenceDefinition def = catalog.Get("E01");      // 非法格式 INVALID_REQUEST / 未知 NOT_FOUND
def.RequiredFieldIds; def.FixedText; def.ProofLimits; def.MediaRefs;
def.Fields; def.TryGetField("watch.dial"); def.ComposedFromParts;
```

### 运行时

```csharp
var registry = new EvidenceRegistry(catalog);                 // 或传入 EvidenceSnapshot 恢复
registry.StateChanged += e => { /* event_id, event_type, evidence_id, field_ids */ };

EvidenceObservationResult obs = registry.ObserveFields(def.RequiredFieldIds);
// ObservedFieldIds / NewlyObservedFieldIds / AlreadyObservedFieldIds / NewlyRegisteredEvidenceIds / EventIds

EvidenceRegistrationResult reg = registry.RegisterEvidence("E01");
// 重复：AlreadyRegistered == true，RegisteredEvidenceIds/EventIds 为空（与 DataSchema 一致）
// 字段不全：PRECONDITION_FAILED，消息列出缺失字段

registry.HasEvidence("E01"); registry.IsComplete("E01"); registry.IsFieldObserved("watch.dial");
registry.GetStatus("E01"); registry.GetVisibleEvidenceRecords(); registry.FindVisibleRecord("E01");
EvidenceSnapshot snapshot = registry.CreateSnapshot();  // snapshot.ToJson(pretty: true)
```

### 快照

```csharp
var restored = EvidenceSnapshot.ParseAndValidate(catalog, json);
var registry = new EvidenceRegistry(catalog, restored);
```

- 未知字段、重复字段、未知证据、已登记证据缺少已观察字段 → `SAVE_CORRUPT`（422）。
- `content_version` 漂移或 `schema_version != "1"` → `SAVE_INCOMPATIBLE`（409）。

### 事件

| EventType | 何时 |
| --- | --- |
| `evidence.fields_observed` | 一次观察调用产生新字段时（每个涉及的证据一条） |
| `evidence.registered` | 某证据首次被登记时 |

事件带 `EventId`（由 `IIdGenerator` 生成）、`EvidenceId`、`FieldIds`、`ContentVersion`。
重复观察/重复登记不产生事件。

## 测试方法与结果

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "G:\projects\EchoLostAndFound\M3B\Tools\build-and-test.ps1"
```

覆盖：正常获取、幂等观察、重复登记、字段不全、无效/畸形证据 ID（含整批回滚）、快照往返、快照损坏、目录 JSON 异常、快照 JSON 异常。
真实运行结果：`M3B/Tests/RESULTS.txt`（2026-11-23，29/29 通过，其中 Evidence 9 项）。

## 限制

- 未在 Unity Editor 中编译/运行（沙箱内只执行了 netstandard2.1 的 Roslyn 编译），Unity 侧标记**未验证**。
- 证据内容 E02–E05 的 `source_label`/`area_id` 由 `Docs/Sources/HistoricalStory/evidence_matrix.md` 推导，待内容确认（见交接文档）。
- 无 UI、无场景对象；仅状态与查询接口。
