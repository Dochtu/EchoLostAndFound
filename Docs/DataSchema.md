# 数据模型与 HTTP JSON 契约

阶段 3，2026-11-21。唯一主笔：AI Engineer。状态：待用户验收的设计；没有实现 API、Schema 文件、SQL 数据库或测试代码。本文是本轮字段、枚举、错误语义与 API 的唯一规范；其他文档引用本文，不另造可写状态旁路。

架构见 [Architecture](Architecture.md)，客户端见 [TechnicalDesign](TechnicalDesign.md)，第一章条件见 [Chapter01ImplementationMap](Chapter01ImplementationMap.md)，故事文字以 [StoryBible](StoryBible.md)及[证据原稿](Sources/HistoricalStory/evidence_matrix.md)为准。本文的新英文技术 ID 不增加故事事实。

## 1. 类型、ID、版本和可见性

| 名称 | 类型与约束 |
| --- | --- |
| request_id | 客户端生成 UUID 字符串，代表一次逻辑请求；网络重试沿用，用户新意图换 ID |
| save_id | 服务端生成 UUID，逻辑存档永久标识；URL 与 JSON 必须一致 |
| runtime_id | 服务端随机 UUID，当前激活时代；每次激活/读档/服务重启恢复轮换，旧值永久失效 |
| state_version | JSON 整数，0–2^53-1；客户端发送当前已知值作 CAS，服务端响应提交后的值；save 内单调高水位，恢复不倒退 |
| event_seq | 数据库 INTEGER，save 内严格递增；恢复不倒退；JSON 如输出需在安全整数内 |
| schema_version / save_format_version | 正整数，分别为数据库与快照结构版本，首版建议均为 1 |
| content_version | 不可变故事内容版本字符串，首版示例 story-v1.0-phase2；不是 API 版本 |
| api_version | 字符串 1.0；路由前缀 /api/v1；破坏兼容的改动不得偷偷复用 v1 |
| 时间 | 真实系统审计时间为 UTC ISO 8601、毫秒、Z；故事 21:17 等单独为内容文本，不用现实日期替代 |
| 数字与空值 | 禁止 NaN/Infinity/字符串代整数；null 只在表列可选字段使用，省略与 null 不混用 |

规范化 JSON 按已验证 DTO 的字段/类型规范化，用于幂等比较；未知字段一律拒绝。所有实体 ID 区分大小写，静态白名单校验；不能让玩家造新 evidence_id、claim_id 或 npc_id。

| 技术枚举 | 值 |
| --- | --- |
| chapter_id | CH01；CH02/CH03 仅保留未来开放标志，本切片不实现其内容 |
| npc_id | npc_laozhou、npc_linyao；npc_xucheng 为后章预留，CH01 禁止调用其正式互动 |
| area_id | lost_property、waiting_hall、platform_safe |
| item_id | item_pocket_watch；其他正式剧情物件按内容登记，不开放任意创建 |
| watch part_id | dial、back_engraving、serial_number、side_crown、crown_shaft_damage |
| knowledge_class | K、H、B、L、N，原分类不因披露而丢弃来源 |
| choice_id / option_id | A01: assist_box_check；A02: temporary_handover 或 bag_pending |
| reasoning_id / hypothesis_id | R01: owner_shenhe_delegate_linyao；R02: impact_jam_same_minute；错误命题也来自获批白名单 |
| custody_state | station_table、sealed_pending、linyao_temporary；本章不产生最终归还/公开/封存结局 |

### 1.1 第一章证据字段唯一注册表

以下字段只拆解已批准的固定文案，不增加事实。文书 document_front 检查完成后登记本证据列出的全部字段；怀表按各部位分别登记。新章节字段须另经内容批准，客户端、剧情映射与测试不得另取别名。

| 证据 | field_id → 固定字段内容 |
| --- | --- |
| E01 | watch.dial → 表面21:17；watch.back_engraving → 背刻0412·0916；watch.serial_number → 后盖边钢印QH-283；watch.side_crown → 侧冠凹陷；watch.crown_shaft_damage → 冠轴可见偏斜 |
| E02 | power_fault.branch_fault → 站台照明支路进水跳闸；power_fault.timestamp → 21:17；power_fault.lamp_time → 21:20内侧油灯临时补照；power_fault.not_restored → 本夜该支路未恢复 |
| E03 | repair_receipt.customer → 交修人沈禾；repair_receipt.item_number → 物件QH-283；repair_receipt.mechanism → 该机为机械上链；repair_receipt.back_engraving → 背刻0412·0916 |
| E04 | designated_receipt.registration_day → 第十日补登记；designated_receipt.owner → 表主沈禾；designated_receipt.recipient → 指定领件林遥；designated_receipt.item_number → QH-283；designated_receipt.collection_terms → 由领件人本人决定并持凭号联络，沈禾签记 |
| E05 | pickup_inspection.incident_time → 21:17；pickup_inspection.incident_description → 沈禾扶0641乘客避滑，怀表落至内侧台沿；pickup_inspection.dial_at_pickup → 拾取时盘面停21:17；pickup_inspection.inspection_time → 22:03；pickup_inspection.mechanical_findings → 表冠凹、冠轴侧弯，传动卡滞，未拆修；pickup_inspection.recorder → 周 |

每字段的 display_text 保留原文字符与单位，表中紧凑写法不是替代整张文书原样文本。field_id 与证据/原物的映射由静态内容登记；同一个字段不能因出现在复本而变成新证明。D01 默认出示 E02 全四字段，D02 默认出示 E03 全四字段和 E04 全五字段，D03 默认出示 E01 全五字段和 E05 全六字段。UI 选中这些披露时由服务提供默认集合；显式field_ids不全则不得执行对应D。默认集合只是材料条件，D仍需本人明确核对，不能由展示自动完成。

数据分三种视图：

1. ContentCatalog/内部权威快照：可包含作者事实、各 NPC 知识分类、披露门槛。只在本机后端和制作资料中使用，不直接发给 Unity 或云模型。
2. PlayerStateView：仅玩家已主动取得的证据/已检查字段、已做动作、已通过命题、保管回执、可访问区域、可见话题和已呈现人物信息；不输出 H/N 正文、未见文书、隐藏真相列表、内部知识矩阵。
3. NPCContextView：仅某 NPC 当前可说的最小陈述、语气、与其有关的事件记忆。玩家全局 StateView 也不得直接作为模型上下文。

## 2. 统一请求和响应

UTF-8 application/json；不含云 Key。所有请求带本机认证头 Authorization: Bearer <临时本机令牌>，不将该占位字面量作为真实值。GET 带 X-Request-ID；POST 在 body 有 request_id，若同时有头必须一致。响应 Cache-Control: no-store。身份无效的响应不返回其他存档元数据。

权威命令完整 envelope：

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "save_id": "55555555-5555-4555-8555-555555555555",
  "runtime_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version": 10,
  "command_type": "item.inspect",
  "payload": {
    "item_id": "item_pocket_watch",
    "part_id": "serial_number",
    "interaction_token": "issued-by-server"
  }
}
```

interaction_token 是 scene.interact 为已开放对象发出的短期 token，绑定 save/runtime/对象/有效访问上下文，不随每次检查 state_version 失效；切换对象、读档或退出近检使其失效。客户端报告射线/距离供体验校验，服务检查内容前置与 token。不是对恶意单机客户端的防作弊证明。

所有常规成功 envelope：

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "save_id": "55555555-5555-4555-8555-555555555555",
  "runtime_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version": 11,
  "changed": true,
  "data": {
    "checked_part_id": "serial_number",
    "observed_field_ids": ["watch.serial_number"],
    "registered_evidence_ids": [],
    "event_ids": ["e1111111-1111-4111-8111-111111111111"]
  },
  "error": null
}
```

changed 表示权威游戏投影是否改变；查询、会话调度和纯重看为 false。一次有领域改变的事务 state_version 恰 +1，不按同事务内多个事件分别加。失败或合法无变化不加版本。成功响应可缓存旧提交结果，客户端若已经应用更高版本不得倒退；必要时再 GET state。data 不暗含完整作者状态。快照读写等管理操作依第 6 节有显式语义。

统一失败 envelope，data 为 null：

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "save_id": "55555555-5555-4555-8555-555555555555",
  "runtime_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version": 11,
  "changed": false,
  "data": null,
  "error": {
    "code": "STATE_VERSION_CONFLICT",
    "message": "调查状态已更新，请重新同步。",
    "retryable": false,
    "details": {"refresh_state": true}
  }
}
```

未创建存档的管理响应 save_id/runtime_id/state_version 可为 null；解析失败时 request_id 无法读取则为 null。不在错误消息打印自由原文、密钥、SQL、系统提示或隐藏缺失事实。缺项仅给当前已开放、允许玩家得知的条目/动作提示。

## 3. API 清单

表中 {s}=save_id、{c}=conversation_id、{t}=turn_id。全部前缀 /api/v1，完整 URL 以启动握手返回的 127.0.0.1:port 为基址。每一项用本节 envelope，GET 无 JSON body。

| 方法 / URL | 请求 | data 成功形状 | HTTP |
| --- | --- | --- | --- |
| GET /api/v1/health | X-Request-ID + token | service_instance_id、api_version、schema_version、content_version、ready、model_available | 200/503 |
| POST /api/v1/saves | request_id、content_version、locale | save_id、runtime_id、state_version、player_state | 201 |
| GET /api/v1/saves | X-Request-ID | saves 数组：save_id、updated_at、chapter_id、state_version、compatible；不含隐藏内容 | 200 |
| GET /api/v1/active | X-Request-ID，不需旧runtime | service_instance_id、save_id、runtime_id、state_version；无活动时后三项null | 200 |
| POST /api/v1/saves/{s}/activate | request_id、save_id、runtime_id、state_version、checkpoint_id（null 表示最近已提交状态） | 新 runtime_id、source_checkpoint_id、player_state | 200 |
| GET /api/v1/saves/{s}/state?runtime_id=... | X-Request-ID，当前 runtime | player_state 全量玩家视图 | 200 |
| POST /api/v1/saves/{s}/commands | 完整 CommandRequest，见第 4 节九类 | 每命令规定的 data | 200 |
| POST /api/v1/saves/{s}/conversations | request_id、save_id、runtime_id、state_version、npc_id、interaction_token | conversation_id、npc_id、available_topic_ids | 201 |
| POST /api/v1/saves/{s}/conversations/{c}/turns | 同身份版本 + text 或 topic_id，二选一 | turn_id、status: pending、poll_after_ms | 202 |
| GET /api/v1/saves/{s}/turns/{t}?runtime_id=... | X-Request-ID，当前 runtime | turn_id、conversation_id、npc_id、status、fixed_segments、fixed_delivery_token、generated_bridge、suggested_actions | 200 |
| POST /api/v1/saves/{s}/conversations/{c}/cancel | request_id、save_id、runtime_id、conversation_id | conversation_id、status: cancelled | 200 |
| POST /api/v1/saves/{s}/checkpoints | request_id、save_id、runtime_id、state_version、kind、resume_anchor | checkpoint_id、captured_state_version、checksum | 201 |
| GET /api/v1/saves/{s}/checkpoints | X-Request-ID | checkpoints：id、captured_state_version、created_at、kind、valid | 200 |

新建示例：

```json
{"request_id":"22222222-2222-4222-8222-222222222222","content_version":"story-v1.0-phase2","locale":"zh-CN"}
```

新建的 data 示例（outer envelope 同第 2 节）：

```json
{"save_id":"55555555-5555-4555-8555-555555555555","runtime_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","state_version":1,"player_state":{"chapter_id":"CH01","evidence_ids":[],"visible_evidence_records":[],"observed_fields":[],"journal_fixed_entries":[],"checked_parts":[],"reasoning_passed":[],"completed_action_ids":[],"available_area_ids":["lost_property","waiting_hall","platform_safe"],"item_custody":[{"item_id":"item_pocket_watch","custody_state":"station_table","holder_npc_id":null,"receipt_id":null}],"chapter_completed":[],"chapter_opened":["CH01"],"visible_npcs":[],"available_action_ids":["package_A0641.open_package"],"resume_anchor":{"area_id":"lost_property","anchor_id":"counter_safe","yaw_degrees":90}}}
```

健康 data 示例：

```json
{"service_instance_id":"99999999-9999-4999-8999-999999999999","api_version":"1.0","schema_version":1,"content_version":"story-v1.0-phase2","ready":true,"model_available":false}
```

健康可 ready=true、model_available=false；无模型不是规则服务不可用。冷启动先通过列表获得 save 当前高水位，activate 的 runtime_id 可 null（无活动时代时）；若已有活动时代必须给其 ID。服务端只允许一个活动 runtime；激活另一存档同样使旧时代失效。读取存档本质为 activate，不用 GET state 假装完成恢复。

命令响应只含第 4 节规定的结果字段，不是任意数据库 patch。changed=true 后，客户端先采用响应版本作为同步目标，GET state 取得完整 PlayerStateView 后再开放下一条写动作；不得把事件 ID 解析成权威状态。数据已在服务提交而动画还未完成时，UI可暂锁但模型不能阻止查询同步。通过同键缓存得到较旧版本结果时，只刷新到服务当前版本，不倒退镜像。

## 4. 权威命令：逐类 payload 和 data

全部是 POST /api/v1/saves/{s}/commands。所有 payload 都不接受世界真相、NPC 自定义知识、关系 delta、passed、chapter_completed 或任意 evidence 内容。调用者只能选已定义动作，结果由 RuleService 派生。下列每个 JSON 是 payload 或 data，外层按第 2 节拼装；没有省略号或伪 JSON。

### 4.1 scene.interact：场景对象/入口与交互上下文

对象 ID 首章白名单含 package_A0641、item_pocket_watch、record_repair_receipt、record_designated_receipt、record_power_fault、record_pickup_inspection、station_lost_property_ledger、station_maintenance_cabinet、npc_laozhou、npc_linyao、box_labels。具体路由动作与位置以内容目录固定。

文书近检使用同名 item_id；scene.interact 需要访问该对象并发近检 token，item.inspect(document_front) 才登记正文。record_repair_receipt 需已观察 serial_number 并选择查同号单据；record_designated_receipt 可按已观察编号直接翻册；record_pickup_inspection 依 record_power_fault 的 document_back_index 进入。完整 E01 不是 E03/E04 的额外前置。box_label_1/2/3 是 box_labels 内三个可检查子对象，只记核对动作，不新造正式物证。

```json
{"area_id":"lost_property","target_id":"package_A0641","action_id":"open_package","client_observation":{"distance_m":1.2,"line_of_sight":true}}
```

```json
{"interaction_token":"issued-by-server","opened_target_id":"package_A0641","visible_target_ids":["item_pocket_watch"],"observed_field_ids":[],"registered_evidence_ids":[],"event_ids":["e0000000-0000-4000-8000-000000000000"]}
```

上例为首次开包：写入 package.opened 结构事件、world_states.package_A0641_opened 与命令幂等结果，同事务 changed=true、state_version+1。不同 request_id 重复打开已开的包，只恢复/发出当前交互上下文，changed=false、event_ids为空，不重复领域事件。区域连接/驻点移动用白名单入口 action_id enter_area；服务检查相邻区、切片访问权，位置由客户端呈现，不由模型决定。target_id 未开放或隔墙检测不合格拒绝；不以距离数据构造虚假的防作弊承诺。

近检/交谈打开时 action_id 为 begin_interaction，绑定当前target并使该runtime原token失效。客户端关窗发同一command_type、action_id=close_interaction，payload如下；服务核对归属后撤销token和相应近检上下文，重复关闭为合法无变化，不增加state_version。新对象begin_interaction、会话cancel、进入加载/activate和服务重启也撤销旧上下文。后台未收到close时，客户端仍立即停止使用旧token；服务端有效性不能只依赖UI状态，token另有建议60秒无活动过期并在合法检查后续期，具体时限 [待确认]。

```json
{"area_id":"lost_property","target_id":"item_pocket_watch","action_id":"close_interaction","interaction_token":"issued-by-server"}
```

```json
{"closed_target_id":"item_pocket_watch","interaction_closed":true,"event_ids":[]}
```

同一 scene.interact 白名单另含 acknowledge_fixed_segment，仅登记当前本人已呈现的获批固定话题文本，供手册恢复旧证词；不增加端点或新的剧情条件。客户端在固定片段确已展示后，带当前交互token及服务下发的 fixed_delivery_token 提交：

```json
{"area_id":"waiting_hall","target_id":"npc_laozhou","action_id":"acknowledge_fixed_segment","interaction_token":"issued-by-server","fixed_delivery_token":"fixed-result-delivery-token","content_refs":["dialogue.CH01.B01.initial"]}
```

```json
{"recorded_fixed_content_refs":["dialogue.CH01.B01.initial"],"journal_entry_ids":["f1111111-1111-4111-8111-111111111111"],"event_ids":["f2222222-2222-4222-8222-222222222222"]}
```

fixed_delivery_token 在内存中绑定本次 save/runtime/NPC/interaction/conversation/turn/state_version 与获批 content_refs；RuleService验证当前上下文及文本权限后才写 fixed_statement.presented 结构事件和 world_states.journal_fixed_entries，changed=true、版本+1。不能只凭客户端任意content_ref写入已知证词。不同request_id重复同本人/同版content_ref不重复登记；旧turn、关闭上下文、读档或服务重启后的令牌失效。提交本身只记展示，不更新NPC知识、关系、E/R/A或章节。

非D固定片段未确认入册时可暂留当前会话界面，不能宣称已持久；断线/重启后只按已提交Journal重建。确认失败可重新执行合法固定问句取得新交付令牌，不冻结主线或增加章节条件。D类证词直接在D事务写入同一Journal投影，不依赖此确认命令，确认同一D片段亦不重复。AI生成段及自由输入绝不写入Journal；此动作不开放AI任意写权威状态。

### 4.2 item.inspect：部位和文书检查

```json
{"item_id":"item_pocket_watch","part_id":"crown_shaft_damage","interaction_token":"issued-by-server"}
```

```json
{"checked_part_id":"crown_shaft_damage","observed_field_ids":["watch.crown_shaft_damage"],"registered_evidence_ids":["E01"],"event_ids":["e2222222-2222-4222-8222-222222222222"]}
```

此成功示例假定其他四部位已完成，最后一部位与 E01 合成在同事务。只看表盘不会返回完整 E01 文案。文书 item_id 使用第 4.1 节对应 record_*，part_id 为 document_front；E02 另有背页索引 document_back_index，只给 E05 入口，不自动读其内容。纸面影像是版本化 content_ref，不让客户端发任意本地路径。

### 4.3 evidence.register：已观察内容的补登记

```json
{"evidence_id":"E01"}
```

```json
{"evidence_id":"E01","already_registered":true,"registered_evidence_ids":[],"event_ids":[]}
```

正常在 item.inspect 派生发卡；该命令仅用于漏显/重连后的补登记请求，重新核对已持久的观察条件，不能由请求任意 grant。满足且未登记则登记 E01 并增版本；不满足返回 PRECONDITION_FAILED，不因发出物名就新增。

### 4.4 npc.present：给指定人物展示已有材料

```json
{"npc_id":"npc_laozhou","evidence_ids":["E02"],"field_ids":["power_fault.branch_fault","power_fault.timestamp","power_fault.lamp_time","power_fault.not_restored"],"interaction_token":"issued-by-server"}
```

```json
{"npc_id":"npc_laozhou","presented_evidence_ids":["E02"],"newly_presented_field_ids":["power_fault.branch_fault","power_fault.timestamp","power_fault.lamp_time","power_fault.not_restored"],"already_presented":false,"available_disclosure_ids":["D01"],"fixed_segments":[],"event_ids":["e9999999-9999-4999-8999-999999999999"]}
```

上例为首次实际出示。服务先验证玩家持卡、当前NPC/token、该NPC此时允许接触的字段白名单，再按以下两层处理：

- 持久层：对于本人尚未见过的字段，写 npc.evidence_presented 结构事件，safe_payload 仅含 npc_id、evidence_id 与新增 field_ids；同事务写该NPC的 event 类 NPCMemory、逐字段 action_receipts、命令幂等结果，changed=true、state_version+1。NPC下次交流可记得“玩家曾给我看过这份材料”，不能自动记为其他NPC也看过。
- 临时层：当前interaction_token绑定“本次向此人实际展示的证据及字段集合”，供紧接的 disclosure.trigger 校验。退出/关闭/换人/token过期即撤销；仅有历史记忆不能冒充本次出示。

去重语义键按 (save_id,content_version,npc_id,evidence_id,field_id) 逐字段保存到 action_receipts，semantic_key 使用这些批准ID的无歧义规范编码。一次请求的字段排序、分组合并或更换request_id不产生重复记忆；只给同一人增加尚未展示的合法字段时，事件和记忆只含新增差集。不同NPC独立结算。读档后去重记录按所选快照恢复，不从未来审计事件补回。

新 request_id 在有效当前上下文中重新出示完全相同字段：不重复事件/记忆、不加版本，already_presented=true、newly_presented_field_ids为空、event_ids为空，但重新建立本次展示集合，允许随后D校验。同 request_id 的网络重试只返回原缓存，不重放临时副作用；若上下文已关闭/失效，玩家须重新进入并以新request_id明确重示，不能把旧成功回包当现时出示。

“记得见过材料”不等于采用其全部内容为人物认知，更不等于固定披露完成。npc.present 不改 NPCKnowledge 的 known/disclosed/belief_active，不生成 E、R 或关系分，不绕过 D02 更新林遥的领取授权；ContextBuilder最多引用安全的展示行为，不以记忆字段解引用隐藏事实。具体知识与误信修正仍由本人D校验后更新。一份 E12 未来也只能给许澄允许的调度字段，不能把票袋私事写进其记忆。UI只显示可核对按钮，D仍需玩家明确下一命令，且所需材料必须在当前上下文确已展示。

### 4.5 disclosure.trigger：固定披露与本人知识

```json
{"disclosure_id":"D02","npc_id":"npc_linyao","evidence_ids":["E03","E04"],"interaction_token":"issued-by-server"}
```

```json
{"disclosure_id":"D02","npc_id":"npc_linyao","fixed_segments":[{"content_ref":"dialogue.CH01.D02.linyao","text":"沈禾，是我妈妈。这个号和她放在家里那张一样。她写着要我自己领。"}],"registered_evidence_ids":[],"event_ids":["e3333333-3333-4333-8333-333333333333"]}
```

要求同 NPC 的对应出示记录及当前交互上下文；出示不是永久授权上下文，退出再回可重示。D01=npc_laozhou+E02；D02 可分别为 npc_linyao 或 npc_laozhou+E03/E04；D03=npc_laozhou+E01/E05。只更新所选本人，幂等领域键含 npc_id，不能用全局 D02=true 代表两人均知。R01 不依赖 D02，A02 暂交另查 D02:林遥。固定关键句以 StoryBible/原章稿，不允模型改写。没有原稿固定句的老周 D02 采用获批单据内容核对展示，不编造新长台词。

### 4.6 reasoning.submit：显式推理

```json
{"reasoning_id":"R01","evidence_ids":["E01","E03","E04"],"hypothesis_id":"owner_shenhe_delegate_linyao"}
```

```json
{"reasoning_id":"R01","passed":true,"conclusion_ref":"reasoning.R01.correct","fixed_feedback":"怀表原主沈禾；今可由她书面指定的林遥领件。","event_ids":["e4444444-4444-4444-8444-444444444444"]}
```

缺证先失败；具有材料但命题错误是有效的业务响应 200、changed=false、data.passed=false、fixed_feedback 只引用已见内容，不加关系惩罚，不写“推理已成立”。重复正确 R 返回 passed=true、changed=false。不接受模型打分。R02 要 E01+E02+E05 与 impact_jam_same_minute；停电使机械表停走的命题不得通过。额外证据允许随选但不替换必要集合，同 source_id 不重复计数。

### 4.7 choice.commit：A01/A02 与保管签条

```json
{"choice_id":"A01","option_id":"assist_box_check","checked_label_ids":["box_label_1","box_label_2","box_label_3"],"interaction_token":"issued-by-server"}
```

```json
{"choice_id":"A01","option_id":"assist_box_check","relationship_changed_npc_id":"npc_laozhou","event_ids":["e5555555-5555-4555-8555-555555555555"]}
```

三个箱签必须有各自检查结果并完成获批同号匹配。箱签文字由内容目录批准，不在本技术稿新编故事编号。关系按 GDD 定义：老周 trust+1、pressure-1，各在0–3范围，只结算一次；不是任意三字符串即可过。

```json
{"choice_id":"A02","option_id":"temporary_handover","npc_id":"npc_linyao","receipt_confirmed":true,"interaction_token":"issued-by-server"}
```

```json
{"choice_id":"A02","option_id":"temporary_handover","item_id":"item_pocket_watch","custody_state":"linyao_temporary","receipt_id":"77777777-7777-4777-8777-777777777777","chapter_completed":["CH01"],"chapter_opened":["CH02"],"registered_evidence_ids":[],"event_ids":["e6666666-6666-4666-8666-666666666666"]}
```

```json
{"choice_id":"A02","option_id":"bag_pending","receipt_confirmed":true,"interaction_token":"issued-by-server"}
```

```json
{"choice_id":"A02","option_id":"bag_pending","item_id":"item_pocket_watch","custody_state":"sealed_pending","receipt_id":"88888888-8888-4888-8888-888888888888","chapter_completed":["CH01"],"chapter_opened":["CH02"],"registered_evidence_ids":[],"event_ids":["e7777777-7777-4777-8777-777777777777"]}
```

暂交需 E01、R01、林遥 D02、指定本人及明确暂收确认；装袋只需 E01 和明确保管确认。两项均在同一事务写 ChoiceRecord、ItemCustody、回执、CH01完成/CH02开放、自动章末检查点与幂等结果。照片/证据/编号和 R 资格保留，不删除 E01。CH02开放不等于切片加载第二章；返回章交接页，允许继续补查 CH01。A02 本章确认后不以另一 request_id 再次移交，改选须读确认前检查点；后续全游戏终局合法处置由独立后章规则处理。

### 4.8 relationship.act：确定性关系行为

```json
{"npc_id":"npc_linyao","action_id":"respect_boundary","chapter_id":"CH01","interaction_token":"issued-by-server"}
```

```json
{"npc_id":"npc_linyao","action_id":"respect_boundary","already_applied":false,"relationship_presentation":"more_receptive","event_ids":["e8888888-8888-4888-8888-888888888888"]}
```

服务按 GDD 获准语义行为计算，不接受 trust/suspicion/pressure 或 delta。respect_boundary 每 NPC/章最多一次；accuse_without_new_evidence、pause_and_verify 各按获批条件/去重规则。尚未拒聊或未到适用情境时不把该动作当可刷按钮。A01 的关系效果只由 choice.commit 派生，relationship.act 不另设 assist_box_check 旁路。

### 4.9 chapter.advance：重新计算已满足的开放条件

```json
{"chapter_id":"CH01"}
```

```json
{"chapter_id":"CH01","completed":true,"opened_chapter_ids":["CH02"],"already_applied":true,"event_ids":[]}
```

正常在 A02 原子派生；此命令只校验 E01+A02 并修复漏显，不能传 completed=true、跳过 A02 或任意打开 CH03。未满足则失败。不要求 R01/R02、D01/D03 或 A01；完整玩法须实现它们，玩家单次通关可选。

## 5. 对话契约、结果与回退

打开会话完整请求：

```json
{"request_id":"33333333-3333-4333-8333-333333333333","save_id":"55555555-5555-4555-8555-555555555555","runtime_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","state_version":11,"npc_id":"npc_laozhou","interaction_token":"issued-by-server"}
```

data：

```json
{"conversation_id":"cccccccc-cccc-4ccc-8ccc-cccccccccccc","npc_id":"npc_laozhou","available_topic_ids":["CH01.station_work","CH01.lighting_recollection"]}
```

发 turn 请求：

```json
{"request_id":"44444444-4444-4444-8444-444444444444","save_id":"55555555-5555-4555-8555-555555555555","runtime_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","state_version":11,"text":"你对那晚的照明还有印象吗？"}
```

固定入口则去掉 text，给 topic_id，二者不能并存；topic_id 仍不得直接触发 D 或修改关系。202 的 data：

```json
{"turn_id":"dddddddd-dddd-4ddd-8ddd-dddddddddddd","status":"pending","poll_after_ms":300}
```

取回完成结果，固定句可独立展示，generated_bridge 仅非案情表达：

```json
{"turn_id":"dddddddd-dddd-4ddd-8ddd-dddddddddddd","conversation_id":"cccccccc-cccc-4ccc-8ccc-cccccccccccc","npc_id":"npc_laozhou","status":"completed","fixed_segments":[{"content_ref":"dialogue.CH01.B01.initial","text":"站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。"}],"fixed_delivery_token":"fixed-result-delivery-token","generated_bridge":null,"suggested_actions":[],"fallback_reason":"model_unavailable"}
```

status 为 pending/completed/cancelled/expired；fallback_reason 为 null 或 model_unavailable/timeout/invalid_output/unsafe_output/unknown_intent。固定结果交付时 fixed_delivery_token 为第4.1节绑定的临时令牌；pending/无固定片段/已失效结果时该字段为null。输出没有 revealed_fact_ids 可供直接发卡，更没有 rule_commands。suggested_actions 仅已有白名单按钮描述，实际执行仍须新 CommandRequest 校验。

同会话一次仅一个 turn；新的 NPC 会话关闭前一个；固定入口无需等待云模型。poll 回包必须匹配请求捕获的 save/runtime/conversation/npc/turn/state_version，任一失效标 expired，客户端清除而不呈现。存档状态改变后允许重新开启会话，不把旧上下文搬到新状态。

自由输入与生成文本只在内存，turn 幂等由内存键与带每 runtime 随机盐的 HMAC 摘要比对；服务退出清空。不得将原文、普通可字典攻击正文 hash、或完整请求写进持久命令账本。固定话题/证词消息可只存 content_ref 和安全 ID。对话端点不持有 RuleService 写权限。

## 6. 存档、检查点与恢复

checkpoints 的 kind 为 manual/chapter_end/pre_choice；resume_anchor 只允许已登记场景安全锚点及有限玩家朝向，不允许任意文件路径/跨区坐标。检查点请求 body：

```json
{"request_id":"66666666-6666-4666-8666-666666666666","save_id":"55555555-5555-4555-8555-555555555555","runtime_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","state_version":11,"kind":"manual","resume_anchor":{"area_id":"lost_property","anchor_id":"counter_safe","yaw_degrees":90}}
```

data：

```json
{"checkpoint_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","captured_state_version":11,"checksum":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
```

上例checksum仅示范64位十六进制格式，不是下文示例快照的实际计算结果。命名快照不修改游戏状态，changed=false、state_version 仍11；保存其元数据与幂等结果同一短事务。最新有效游戏事务始终已落库，用户“保存”不是把内存未决状态写进去。A02 自动检查点在同事务捕获其最终投影；章前 pre_choice 检查点用于回退重选，不在确认后覆盖旧点。

恢复请求：

```json
{"request_id":"99999999-9999-4999-8999-999999999999","save_id":"55555555-5555-4555-8555-555555555555","runtime_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","state_version":24,"checkpoint_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}
```

响应关键字段：runtime_id 换新，版本25，而不是被恢复快照里的11。

```json
{"request_id":"99999999-9999-4999-8999-999999999999","save_id":"55555555-5555-4555-8555-555555555555","runtime_id":"eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee","state_version":25,"changed":true,"data":{"source_checkpoint_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","player_state":{"chapter_id":"CH01","evidence_ids":["E01"],"reasoning_passed":[],"chapter_completed":[],"chapter_opened":["CH01"]}},"error":null}
```

恢复事务核对 checkpoint 所属 save、校验和、schema/save/content 版本；完整恢复当前证据、部位、人物知识/关系/结构记忆、D、R、A、保管、章与安全锚点。恢复不保留未来知识和已失效自由文本。旧事件留作审计，但当前投影只来自选定检查点；不得从旧分支事件重新“补回”未来动作。

全库状态换代也不覆盖 player_saves 的 state_version/event_seq 高水位。每次恢复追加 state.restored 事件，包含 checkpoint_ref，当前投影恢复后的动作去重标记也按快照回到对应时点：读 A01 之前的档后，允许在新的时代重新做一次 A01，不能被旧审计事件的唯一约束永久拦住。

## 7. 幂等、事务、冲突和错误

### 7.1 严格执行顺序

普通权威写请求：认证/结构 → 进入单写队列 → BEGIN IMMEDIATE → 核对活动 save 与 runtime → 查 (save_id,runtime_id,request_id) → 同键同内容返回原结果，同键异内容报冲突 → 新请求校验 state_version → 校验业务前置 → 更新投影/事件/版本/幂等结果 → COMMIT → 响应。错误必须回滚；没有“先发卡后保存”。已缓存业务拒绝或无变化结果的同键重试仍返回原结果；用户改意图/前置变化后重试须新 request_id。

结构有效的 commands 幂等记录持久保存，不把自由对话文本加入。重启后原 runtime 不再有效，旧缓存不能当新事务复用；客户端先 activate，再读取当前状态。数据已提交但响应丢失时，同 runtime 同键重发得到原结果；若已恢复则旧 runtime 拒绝。

activate 是唯一换代特例：认证/结构后先在持久 operation_receipts 按 request_id 查同一规范请求（包括旧 runtime、旧版本、checkpoint），先于普通旧 runtime 拒绝逻辑。命中且记录的 new_runtime 仍是本服务当前活动时代，就返回原结果，即使请求携带的 old_runtime 已失效。若之后又激活/恢复，或服务实例已重启而原 new_runtime 不再有效，则返回 RUNTIME_EXPIRED，不再次恢复。新激活仍必须在事务中核对旧时代及高水位后轮换。创建存档亦用持久管理 request_id 防重建；服务重启可返回已有 save_id，再要求新的 activate 请求，不重新创建第二份存档。检查点幂等同普通 runtime 规则。管理 ledger 不含自由正文或认证材料。

GET /api/v1/active 提供认证后的控制面恢复查询，无需旧runtime，data为 service_instance_id、save_id、runtime_id、state_version（无活动时后三项null）。它不激活、不读回作者内容；用于激活响应丢失或客户端重连。服务进程重启生成新 service_instance_id，启动时没有活动runtime；接入新健康握手后，以新 request_id 和 runtime_id=null 激活所需save的最近提交状态（或用户明确选择的checkpoint），版本继续当前高水位+1。旧进程令牌及结果不可用于新实例。命令端点没有这个控制面特例。

### 7.2 并发和超时建议

只一个权威命令在途；取消 HTTP 不回滚已提交事务。版本冲突必须刷新 state 后由玩家重新确认，不自动给新版本重新发送破坏性选择。SQLite 写锁等待建议1秒，普通HTTP客户端5秒，启动就绪20秒，模型总预算12秒；均为 [待确认] 的初始工程参数，理由是交互应及时提供固定入口，需用户确认后依据原型调整。禁止无限自动重试；GET/同键写网络重试建议最多2次，退避0.3/1秒，之后提供明确重连。

模型12秒预算不阻塞规则写队列；每 runtime 一个 turn 在途。首版建议自由输入最多1000个 Unicode 字符、JSON body最多32KiB、模型衔接最多120个中文字符、轮询300ms起，固定入口立即可选；均 [待确认]，须确认可用性与真实服务时延后冻结。

| HTTP / error.code | 含义及客户端动作 |
| --- | --- |
| 400 INVALID_REQUEST / ID_MISMATCH | 结构/枚举/URL-body身份不符；不重试原错误请求 |
| 401 LOCAL_AUTH_REQUIRED | 本机令牌错误/缺失；重新启动握手，不显示存档细节 |
| 404 NOT_FOUND | 未知或无权限对象；隐藏对象不返回秘密内容 |
| 413 REQUEST_TOO_LARGE | JSON body超过建议32KiB上限；拒绝请求且不改状态，不回显超限正文 |
| 409 STATE_VERSION_CONFLICT | 当前时代版本不符；刷新 state，未确认动作保留但不自动重签 |
| 409 RUNTIME_EXPIRED | 存档/运行时代已换；丢弃全部旧队列与会话，重新激活 |
| 409 IDEMPOTENCY_CONFLICT | 同键不同规范请求；程序错误，不换ID偷偷重做 |
| 409 PRECONDITION_FAILED | 缺证、错误本人、部位未全、上下文不合法；只提示允许缺项 |
| 409 CHOICE_ALREADY_COMMITTED | A02已有另一明确结果；允许读确认前档，不二次移交 |
| 410 INTERACTION_EXPIRED / TURN_EXPIRED | 近检token或对话上下文失效；重新进入对象/会话 |
| 422 VALIDATION_ERROR | 严格类型/范围/字段错误；响应details仅路径及规则，不回显敏感值 |
| 429 TURN_BUSY | 当前已有模型turn；可取消或使用固定入口 |
| 503 RULE_SERVICE_UNAVAILABLE / STORAGE_BUSY | 服务或短锁等待失败；暂停写，原request_id可重试 |
| 507 STORAGE_WRITE_FAILED | 磁盘满/只读等；不显示成功，修复后重试 |
| 409 SAVE_INCOMPATIBLE / 422 SAVE_CORRUPT | 内容版本不兼容或快照校验失败；保持原库/当前可用状态 |

模型不可用/超时/非法结构是对话成功回退结果，不使规则API伪返回成功。规则后端完全不可达属于传输失败，Unity自行显示断线但不能自行生成成功 envelope。

## 8. SQLite 模型、主外键、约束与索引

首版建议 schema_version=1，标准 sqlite3 Repository；表名均 snake_case。下列 T=TEXT、I=INTEGER、J=TEXT(JSON经严格DTO校验)、B=0/1 INTEGER；UUID为T，UTC timestamp为T，枚举有 CHECK，必填列 NOT NULL，列注明 ? 才可空。所有 save-scoped 投影有 FK save_id→player_saves；所有 static ID 都验证同 content_version 的目录存在。外键连接级启用，显式短事务；不依赖 SQLite 宽松类型自动兜底。

公共列与复合键的实施规则（是表结构的一部分，不由开发者猜补）：

- player_saves 增加 UNIQUE(save_id,content_version)。下表所有“当前投影”均显式包含 content_version T NOT NULL：chapter_progress、evidence_records、inspection_states、npc_knowledge、npc_relationships、npc_memories、disclosure_events、reasoning_results、choice_records、item_custodies，以及 action_receipts、custody_receipts、world_states；每表 FK(save_id,content_version)→player_saves(save_id,content_version)，同时所有静态FK都包含本列。
- NPC引用一律 FK(content_version,npc_id)→npc_profiles；item引用→item_defs；chapter引用→chapter_defs；evidence引用→evidence_defs；claim引用→claim_defs；D/R/A及option/part/hypothesis分别引用相应同版定义。item_defs与part_defs复合键分别为(content_version,item_id)、(content_version,item_id,part_id)。各内容子定义至少含该复合PK、content_ref T、prerequisites J、allowed_field_ids J；option_defs为(content_version,choice_id,option_id)，hypothesis_defs为(content_version,reasoning_id,hypothesis_id)。均是静态批准内容，不接受API写入。
- 投影中所有 *_event_seq（可空除外）都用 FK(save_id,该列)→game_events(save_id,event_seq)；相应事件先写入同事务。引用保管回执的 choice_records 与 item_custodies 使用 FK(save_id,receipt_id)→custody_receipts(save_id,receipt_id)，不得只凭receipt_id跨档联接。holder_npc_id 可空，但非空时使用同版NPC FK。
- conversation_sessions 显式含 save_id T、content_version T；UNIQUE(save_id,conversation_id,content_version)，同版NPC FK及 FK(save_id,content_version)→player_saves。conversation_messages 显式增加 save_id T、content_version T NOT NULL，FK(save_id,conversation_id,content_version)→conversation_sessions；固定content_ref按该版本校验。迁移内容版本前关闭并移除旧会话操作元数据，当前游戏投影走显式迁移；自由正文从不在该表。
- game_events、operation_receipts、save_checkpoints 是保留历史而非当前投影：仅save归属FK，不用同版save复合FK限制旧内容版本。game_events另显式保存 content_version T NOT NULL 以复现当时内容；旧快照和旧事件的版本不得为迁移方便改写。
- SQLITE的NULL外键语义不代替业务校验，必须有 holder/custody与receipt必需性 CHECK及领域断言；JSON引用数组逐项经领域校验。

| 模型 → 表 | 主键与字段 | 外键、唯一、索引与约束 |
| --- | --- | --- |
| PlayerSave → player_saves | save_id T PK；runtime_id T?；state_version I；event_seq I；schema_version I；save_format_version I；content_version T；locale T；created_at/updated_at T；resume_anchor J | state_version/event_seq≥0；runtime唯一（非空）；runtime与两个高水位不从旧快照回写 |
| ChapterProgress → chapter_progress | (save_id,chapter_id) PK；opened B；completed B；completed_event_seq I?；updated_at T | FK chapter_id→chapter_defs；CHECK completed≤opened；索引(save_id,opened) |
| EvidenceSource → evidence_sources | (content_version,source_id) PK；source_kind T；area_id T；item_id T；content_ref T；provenance_root_id T；proof_scope J | 静态来源；source_kind physical/document/audio/testimony；同源复制共享provenance_root_id；索引(content_version,item_id) |
| EvidenceRecord → evidence_records | (save_id,evidence_id) PK；source_id T；content_version T；acquired_event_seq I；acquired_at T；observed_field_ids J；media_refs J | 复合FK(content_version,evidence_id)→evidence_defs，(content_version,source_id)→evidence_sources；FK(save_id,acquired_event_seq)→game_events；索引(save_id,source_id)；禁止重复发同卡 |
| InspectionState → inspection_states | (save_id,item_id,part_id) PK；observed B；observed_field_ids J；observed_event_seq I?；updated_at T | FK内容item/part定义；索引(save_id,item_id)；仅批准部位，旋转角度不冒充已检查 |
| NPCProfile → npc_profiles | (content_version,npc_id) PK；display_name T；personality_ref T；knowledge_definition_ref T；visual_profile_ref T；fixed_dialogue_ref T | 静态只读；不直接将作者秘密字段发模型；索引(content_version,npc_id) |
| NPCKnowledge → npc_knowledge | (save_id,npc_id,claim_id) PK；knowledge_class T；known B；disclosed B；belief_active B；source_ref T；learned_event_seq I?；updated_at T | FK(content_version,npc_id)→npc_profiles（content_version T同行存）；claim_id→claim_defs；N不得known/disclosed；H未披露不能发上下文；索引(save_id,npc_id,disclosed) |
| NPCRelationship → npc_relationships | (save_id,npc_id) PK；trust I；suspicion I；pressure I；updated_at T | 同版NPC FK；每值0–3；初始1/1/0；不接收客户端delta；角色presentation由规则派生 |
| NPCMemory → npc_memories | (save_id,memory_id) PK；npc_id T；memory_kind T；source_event_seq I；content_ref T；safe_payload J；created_at T | memory_kind event/promise/fixed_statement；FK(save_id,source_event_seq)→game_events；UNIQUE(save_id,npc_id,source_event_seq,content_ref)；索引(save_id,npc_id,created_at)；无自由原文/摘要列 |
| DisclosureEvent → disclosure_events | (save_id,disclosure_id,npc_id,action_key) PK；source_evidence_ids J；event_seq I；fixed_content_ref T；completed_at T | 同版NPC及D定义FK；D02按本人独立；D04未来按不同action_key分开；索引(save_id,npc_id,disclosure_id) |
| ReasoningResult → reasoning_results | (save_id,reasoning_id) PK；passed B；hypothesis_id T；evidence_ids J；passed_event_seq I?；updated_at T | 同版R/命题定义FK；证据集合逐ID验证；错误尝试可记安全事件但不覆盖既有passed；索引(save_id,passed) |
| ChoiceRecord → choice_records | (save_id,choice_id) PK；option_id T；event_seq I；receipt_id T?；confirmed_at T | 同版A/option定义FK；A01一次/A02结果唯一；索引(save_id,confirmed_at)；A02与保管同事务 |
| ItemCustody → item_custodies | (save_id,item_id) PK；custody_state T；holder_npc_id T?；receipt_id T?；changed_event_seq I；updated_at T | 同版item/NPC定义FK；receipt_id→custody_receipts；linyao_temporary必须holder=npc_linyao且有回执 |
| ConversationSession → conversation_sessions | conversation_id T PK；save_id T；runtime_id T；npc_id T；opened_state_version I；status T；created_at/closed_at T? | 同版NPC FK；索引(save_id,runtime_id,status)；状态open/cancelled/expired/closed；不入剧情快照，恢复时全部过期 |
| ConversationMessage → conversation_messages | message_id T PK；conversation_id T；turn_id T；role T；topic_id T?；fixed_content_ref T?；status T；created_at T | FKconversation；UNIQUE(conversation_id,turn_id,role)；索引(conversation_id,created_at)；只存已批准topic/ref与状态，无user_text/generated_text/request_body/hash列 |
| GameEvent → game_events | (save_id,event_seq) PK；event_id T UNIQUE；runtime_id T；request_id T；event_type T；semantic_key T；safe_payload J；committed_state_version I；created_at T | FKsave；索引(save_id,runtime_id,request_id)及(save_id,event_type,event_seq)；追加不改；semantic_key不设跨恢复唯一，避免旧分支永久阻止A01 |

辅助表也属于同一数据库设计：

| 表 | 关键结构与用途 |
| --- | --- |
| command_receipts | save_id/runtime_id/request_id均T、复合PK；validated_command J、response J、created_at T；save归属FK；仅不含自由正文的commands/checkpoints，记录与业务同事务；规范请求同键不同值拒绝；不进可回退快照 |
| operation_receipts | request_id T PK、operation_kind T（create/activate）、old_runtime_id T?、new_runtime_id T?、save_id T FK、safe_request J、response J、service_instance_id T、created_at T；用于create/activate换代幂等；不随旧快照恢复回滚 |
| world_states | save_id T PK/FK、content_version T、world_flags J、journal_fixed_entries J、updated_at T；只允许内容白名单的开包、入口、文书索引等已完成动作和获批固定证词入册；随快照恢复；不能作为任意JSON状态写口 |
| action_receipts | save_id/semantic_key均T、复合PK；content_version T、event_seq I、npc_id T?、chapter_id T?、created_at T；当前投影去重A01/关系行为；恢复按检查点一起恢复 |
| custody_receipts | receipt_id T PK、save_id T FK、content_version T、item_id T、recipient_npc_id T?、custody_state T、fixed_terms_ref T、confirmed_at T；UNIQUE(save_id,receipt_id)，不存手写签迹/自由文字 |
| save_checkpoints | checkpoint_id T PK、save_id T FK、kind T、captured_state_version I、captured_event_seq I、schema_version I、save_format_version I、content_version T、snapshot_json J、checksum T（64位SHA256十六进制）、created_at T；索引(save_id,created_at)；不可变，不含未决LLM任务 |
| chapter_defs/evidence_defs/item_defs/claim_defs/disclosure_defs/reasoning_defs/choice_defs | 静态内容定义，PK(content_version,对应id)；存批准字段/条件与文案ref，发布与规则同版本。关联表按复合键验证，不靠字符串存在就发证 |

所有跨表 save-scoped FK 必须包含 save_id，避免A档引用B档事件/回执；部分静态模型行的 content_version 由 save固定并以复合外键约束。JSON数组的内容引用由领域校验补足SQLite外键无法逐元素约束的部分。外键不等于业务前置，也不保证知识可披露。

### 8.1 事件、快照与恢复算法

当前投影用于低成本查询；审计事件只存固定ID与安全值；不可变快照用于恢复。不是要求每次启动重放全部事件。state.restored 事件带所恢复 checkpoint_ref，未来审计重建必须遵守此基线，不能把旧分支A01/D02混回新投影。

单次动作可产生多个事件但共享一个 committed_state_version。所有事件、投影、command_receipt与A02自动检查点在同一事务提交。无变化重试不新增领域事件。恢复前已完成A01的快照包括action_receipts，恢复到A01前则不包括；审计历史仍保留但不影响当前资格。

schema迁移与内容迁移分开版本：一致备份→校验→显式事务迁移→foreign_key_check/integrity_check→成功才标新版本。失败保留原库和备份，不悄悄新建。收到更高未来格式只读拒写。具体Python/SQLite发行版本、迁移发布支持范围 [待确认]，推荐先锁定打包运行时，再制作真实旧版fixture验证；不以本机可导入版本当项目依赖承诺。

## 9. 实际数据示例

### 9.1 E01（内部 EvidenceRecord 与获批内容联接后的完整示例）

```json
{
  "save_id":"55555555-5555-4555-8555-555555555555",
  "evidence_id":"E01",
  "source_id":"src_watch_original",
  "content_version":"story-v1.0-phase2",
  "acquired_event_seq":8,
  "acquired_at":"2026-11-21T07:00:00.000Z",
  "observed_field_ids":["watch.dial","watch.back_engraving","watch.serial_number","watch.side_crown","watch.crown_shaft_damage"],
  "media_refs":["evidence.E01.front","evidence.E01.back","evidence.E01.side"],
  "fixed_text":"表面 21:17。背刻 0412·0916。后盖边钢印 QH-283。侧冠凹陷，冠轴可见偏斜。",
  "provenance_root_id":"watch.QH-283",
  "proof_limits":["盘面读数不能单独证明坠表时刻","物件编号与背刻不能单独证明领取授权"]
}
```

前四部位时只返回已观察字段，不显示第五部位或完整卡。media_refs 是随内容发布的证据影像引用，原物移交不删除；未来可录制静态近检影像，但不把玩家任意截图当新的独立物证。

### 9.2 NPC 内部状态（禁止原样发Unity或模型）

```json
{
  "npc_id":"npc_linyao",
  "content_version":"story-v1.0-phase2",
  "relationship":{"trust":1,"suspicion":1,"pressure":0},
  "knowledge":[
    {"claim_id":"F04.owner_is_mother","knowledge_class":"K","known":true,"disclosed":true,"belief_active":false,"source_ref":"profile.linyao"},
    {"claim_id":"F04.designated_collection_number","knowledge_class":"L","known":false,"disclosed":false,"belief_active":false,"source_ref":"D02:npc_linyao"},
    {"claim_id":"B03.mother_did_not_visit_west_window","knowledge_class":"B","known":true,"disclosed":true,"belief_active":true,"source_ref":"profile.linyao"},
    {"claim_id":"F03.crown_shaft_mechanism","knowledge_class":"N","known":false,"disclosed":false,"belief_active":false,"source_ref":"profile.linyao"}
  ],
  "completed_disclosure_keys":[],
  "safe_memory_refs":[]
}
```

此例来自D02前。K的disclosed=true表示允许说，不强迫玩家已听见；玩家听见记录另由会话固定片段/已知档案投影表示。内部B不被当F真相。单个F行分claim，不能因owner_is_mother已知就开放该F其余授权字段。

### 9.3 PlayerStateView 示例

```json
{
  "chapter_id":"CH01",
  "evidence_ids":["E01"],
  "visible_evidence_records":[{
    "evidence_id":"E01",
    "title":"停表与编号",
    "source_id":"src_watch_original",
    "source_label":"失物招领处，A-0641包内怀表实物",
    "source_kind":"physical",
    "area_id":"lost_property",
    "item_id":"item_pocket_watch",
    "provenance_root_id":"watch.QH-283",
    "fixed_text":"表面 21:17。背刻 0412·0916。后盖边钢印 QH-283。侧冠凹陷，冠轴可见偏斜。",
    "proof_limits":["盘面读数不能单独证明坠表时刻","物件编号与背刻不能单独证明领取授权"],
    "media_refs":["evidence.E01.front","evidence.E01.back","evidence.E01.side"],
    "observed_field_ids":["watch.dial","watch.back_engraving","watch.serial_number","watch.side_crown","watch.crown_shaft_damage"],
    "content_version":"story-v1.0-phase2",
    "acquired_at":"2026-11-21T07:00:00.000Z"
  }],
  "observed_fields":[
    {"field_id":"watch.dial","item_id":"item_pocket_watch","part_id":"dial","label":"表盘","display_text":"表面 21:17。","media_refs":["evidence.E01.front"]},
    {"field_id":"watch.back_engraving","item_id":"item_pocket_watch","part_id":"back_engraving","label":"背刻","display_text":"背刻 0412·0916。","media_refs":["evidence.E01.back"]},
    {"field_id":"watch.serial_number","item_id":"item_pocket_watch","part_id":"serial_number","label":"编号","display_text":"后盖边钢印 QH-283。","media_refs":["evidence.E01.back"]},
    {"field_id":"watch.side_crown","item_id":"item_pocket_watch","part_id":"side_crown","label":"侧冠","display_text":"侧冠凹陷。","media_refs":["evidence.E01.side"]},
    {"field_id":"watch.crown_shaft_damage","item_id":"item_pocket_watch","part_id":"crown_shaft_damage","label":"冠轴损伤","display_text":"冠轴可见偏斜。","media_refs":["evidence.E01.side"]}
  ],
  "journal_fixed_entries":[{
    "entry_id":"f1111111-1111-4111-8111-111111111111",
    "npc_id":"npc_laozhou",
    "content_ref":"dialogue.CH01.B01.initial",
    "fixed_text":"站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。",
    "source_kind":"conversation_fixed",
    "source_event_seq":9,
    "status":"active",
    "superseded_by_entry_id":null
  }],
  "checked_parts":[{"item_id":"item_pocket_watch","part_ids":["dial","back_engraving","serial_number","side_crown","crown_shaft_damage"]}],
  "reasoning_passed":[],
  "completed_action_ids":[],
  "chapter_completed":[],
  "chapter_opened":["CH01"],
  "item_custody":[{"item_id":"item_pocket_watch","custody_state":"station_table","holder_npc_id":null,"receipt_id":null}],
  "visible_npcs":[{"npc_id":"npc_laozhou","display_name":"老周","presentation":"guarded"},{"npc_id":"npc_linyao","display_name":"林遥","presentation":"guarded"}],
  "available_area_ids":["lost_property","waiting_hall","platform_safe"],
  "available_action_ids":["A02.bag_pending"],
  "resume_anchor":{"area_id":"lost_property","anchor_id":"counter_safe","yaw_degrees":90}
}
```

此完整示例为已取得E01、听见并入册B01，但未取得其他卡的状态。没有H/N、作者真相、未取得E02–E05文字、R02正确答案，也不直接暴露内部信任数字。GET state 内直接给可见正文与来源，不要求客户端根据裸E ID去加载整套作者目录；下载整个作者内容再在UI遮挡不是权限设计。

PlayerStateView 新增三类typed数组，都是必填且初始为空数组：

| 字段 | 每行完整形状与过滤条件 |
| --- | --- |
| visible_evidence_records | evidence_id T、title T、source_id T、source_label T、source_kind T、area_id T、item_id T、provenance_root_id T、fixed_text T、proof_limits T数组、media_refs T数组、observed_field_ids T数组、content_version T、acquired_at T。严格等于当前evidence_records持有集合；卡未登记则不出现整卡正文或证明范围。source_label/proof_limits只描述该卡已批准的来源与边界，不额外附作者F正文 |
| observed_fields | field_id T、item_id T、part_id T、label T、display_text T、media_refs T数组。只联接当前InspectionState已检查字段与第1.1节registry，可在E01尚未合成时显示局部观察；不能据部分观察展开整卡、其他部位或未检查索引 |
| journal_fixed_entries | entry_id UUID、npc_id T、content_ref T、fixed_text T、source_kind T（conversation_fixed/disclosure）、source_event_seq I、status T（active/corrected）、superseded_by_entry_id UUID?。只从当前world_states.journal_fixed_entries及同版固定内容生成；旧陈述修正仍保留并指向修正条目；无自由正文/AI生成段 |

例如只检查表盘时，evidence_ids和visible_evidence_records均为空，observed_fields只含watch.dial一行，checked_parts只含dial；手册能回看这一观察，却不能看到背刻、编号、冠轴或E01完整卡。文书检查完成后按对应registry一次记录已读正面字段；未翻背页索引不显示其关联入口。证据影像必须按当前卡/部位授权，若同张图片拍入未检查部位或文字，先使用获批裁切/遮挡引用，不用一个含隐藏内容的图再靠UI裁切。

fixed_text和media_refs来自服务端可见内容投影，不接受客户端回传任意正文或文件路径。media_refs是表现内容引用而非作者事实目录；只对服务已授权条目解析相应资源，不附隐藏说明、完整NPC Profile或未获文书文本。

Journal恢复规则：D事务把自身固定片段及旧B修正状态写入当前Journal；旧B仅在当前投影已有入册条目时标corrected，不能补造玩家从没听过的旧证词。非D已呈现固定片段按第4.1节的确认动作入册。持久Journal条目保存固定ref、本人、出处事件与修正状态，fixed_text按同content_version受控联接生成。Journal投影随检查点完整保存/恢复，读档后GET state只从恢复的当前投影重建。ConversationMessage属于操作元数据，不参与恢复，也不得从未来分支的对话记录或GameEvent扫描“补全”Journal。缺少已提交入册事件的旧固定片段不凭空补回，可再次合法交谈取得。固定ref归档后同版文本可重建，模型生成内容永远不能成为“旧证词”。

HTTP PlayerStateView 使用显式字段与typed数组，checked_parts 为每item一行的 {item_id,part_ids} 数组，item_custody 为 {item_id,custody_state,holder_npc_id,receipt_id} 数组；不使用动态键字典。typed数组仅简化DTO形状，不代表JsonUtility能实现本文的严格协议校验；严格解析按 TechnicalDesign 的方案，推荐官方Newtonsoft JSON候选依赖，M0后须单独确认准确包版本和Packages修改授权，本轮不安装。PlayerStateView 的数组字段默认空数组，不用null。内部SQLite/snapshot的JSON可使用固定受控字典，两种视图转换由后端投影负责。第6节恢复回包只演示关键字段；实际player_state须输出第9.3节列出的全部字段。

### 9.4 内部存档快照结构

```json
{
  "save_format_version":1,
  "schema_version":1,
  "content_version":"story-v1.0-phase2",
  "save_id":"55555555-5555-4555-8555-555555555555",
  "captured_state_version":11,
  "captured_event_seq":8,
  "created_at":"2026-11-21T07:00:00.000Z",
  "projection":{
    "chapter_progress":[{"chapter_id":"CH01","opened":true,"completed":false}],
    "evidence_records":[{"evidence_id":"E01","source_id":"src_watch_original","acquired_event_seq":8,"observed_field_ids":["watch.dial","watch.back_engraving","watch.serial_number","watch.side_crown","watch.crown_shaft_damage"],"media_refs":["evidence.E01.front","evidence.E01.back","evidence.E01.side"]}],
    "inspection_states":[{"item_id":"item_pocket_watch","checked_parts":["dial","back_engraving","serial_number","side_crown","crown_shaft_damage"]}],
    "npc_knowledge_overrides":[],
    "npc_relationships":[{"npc_id":"npc_laozhou","trust":1,"suspicion":1,"pressure":0},{"npc_id":"npc_linyao","trust":1,"suspicion":1,"pressure":0}],
    "npc_memories":[],
    "disclosure_events":[],
    "reasoning_results":[],
    "choice_records":[],
    "action_receipts":[],
    "custody_receipts":[],
    "item_custodies":[{"item_id":"item_pocket_watch","custody_state":"station_table","holder_npc_id":null,"receipt_id":null}],
    "resume_anchor":{"area_id":"lost_property","anchor_id":"counter_safe","yaw_degrees":90},
    "world_flags":{"package_A0641_opened":true},
    "journal_fixed_entries":[]
  }
}
```

空 npc_knowledge_overrides 是相对同版静态Profile的差量，不表示人物没有初始知识；非空要保存实际已学与B修正。所有投影项实际持久值必须完整序列化，示例省掉的数据库审计列由快照元信息及对应事件引用重建，不丢失去重资格。snapshot不含runtime_id、版本高水位覆盖值、conversation/turn、自由正文、模型请求、认证材料。内部快照不是通过HTTP给Unity下载的PlayerStateView。

## 10. 待定参数与后续验证

| 项目 | 推荐与理由 | 需要确认 |
| --- | --- | --- |
| API/输入限值 [待确认] | 第7节初始预算先保证固定回退可用，不无限等待 | 首个原型测量后冻结响应和大小上限 |
| 快照/槽位 [待确认] | 手动槽+章前/章末自动点；保留恢复前副本，避免误覆盖 | 槽数、自动轮换和UI删除策略 |
| 部署/内容打包 [待确认] | 后端只读故事目录与Unity表现目录同content版本，玩家只收可见投影 | 发布工具链与内容升级兼容范围 |

官方依据：[SQLite 显式事务与单写限制](https://www.sqlite.org/lang_transaction.html)、[连接级外键](https://www.sqlite.org/foreignkeys.html)、[一致备份](https://www.sqlite.org/backup.html)、[FastAPI 响应模型](https://fastapi.tiangolo.com/tutorial/response-model/)。这些机制不代替本项目知识/故事业务规则；本轮仅静态设计，真实路由、迁移、故障、并发与存读档均尚未验证。
