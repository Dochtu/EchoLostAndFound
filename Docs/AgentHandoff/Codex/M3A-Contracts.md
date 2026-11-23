# M3-A 车站交互契约

Unity 客户端使用纯 C# 程序集 `EchoLostAndFound.WebGL.Contracts`。所有类型位于同名命名空间。DSH 提供后续适配器与 Mock。M3-A 单机预览可以独立显示怀表表盘和老周对话入口。

| 边界 | Unity / DSH 调用约定 |
| --- | --- |
| 交互事件 | 适配器在启用时订阅 `IStationInteractionSource.Interacted`，停用时取消订阅。每个玩家动作发布一次，可在本地直接传递可序列化的 `InteractionEvent`。重试沿用同一个 request_id。 |
| 证据 | `EvidenceObservation` 是一个已观察字段在 UI 中的投影。适配器从可见 observed_fields 映射 field_id、label、display_text 到 field_id、title、observation_text。完整证据卡 ID 只取自已获准的 evidence_ids。 |
| 对话状态 | `DialogueState` 提供 conversation_id、npc_id、status 和 available_topic_ids，status 沿用 open / cancelled / expired / closed。当前没有会话时 dialogue 为 null。入口预览只显示固定 UI 文字。 |
| 游戏状态 | `IStationGameSession.ReadAsync` 读取已绑定存档的快照。`InteractAsync` 接收意图、当前 runtime_id 和预期 state_version，返回服务已确认的可见快照。返回数组使用空数组。Unity 将返回值视为只读。 |

## 交互映射

| 工厂方法 | kind | target_id | part_id | DSH 适配行为 |
| --- | --- | --- | --- | --- |
| InspectDial() | inspect_part | item_pocket_watch | dial | 向 DSH 调查模块提交表盘观察。单独检查表盘可见 watch.dial，完整 E01 的注册条件由 DSH 判断。 |
| OpenDialogue() | open_dialogue | npc_laozhou | 空字符串 | 适配器向 DSH 对话模块申请会话。只有模块返回的 topic 可以显示。 |

快照带 save_id、runtime_id、state_version 和 chapter_id。真实 HTTP 接入时，由适配器补全存档上下文、所需的交互凭据，并依据现有 DataSchema 翻译 v1 请求与完整响应。网络错误通过失败的 Task 传回。Unity 取消订阅或切换会话后应丢弃迟到响应。发生运行时代码或 CAS 冲突时重新 ReadAsync 获取快照，再根据玩家意图决定是否发送新操作。已取消本地等待的请求仍可能在服务端提交。

## 可复用资料

- JSON 固定展示数据位于 `Assets/Contracts/Resources/M3A/StationPreview.json`，按 `StationPreview` 读取。字段 ID watch.dial 来自 Docs/DataSchema.md §1.1。单独观察十二小时表盘显示 9:17，遵循 Docs/TestPlan.md 对表针读数的约束。正式证据卡的文字保留原稿的 21:17。老周入口显示固定操作提示。
- 存档、鉴权、幂等、服务端知识边界和 HTTP 数据格式遵循根工程 Docs/DataSchema.md §§1、4、9。M3-A 投影只包含场景使用的字段。
- DSH 的 `M3B/Shared/Contracts/IEvidenceStateView.cs` 提供证据查询，`M3B/Shared/Ai/NpcAiContracts.cs` 定义 AI 请求与结果。适配器可引用这些模块；只应把获准可见的状态交给 Unity。
