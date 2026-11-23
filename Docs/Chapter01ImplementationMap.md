# 第一章《停走的怀表》剧情技术映射

阶段 3，2026-11-21。唯一主笔：Narrative Designer。本文是将已验收剧情转为可执行条件的技术设计，不是新增剧情，不表示事件、规则、场景或测试已经实现。本文唯一写入文件，不修改 GDD、StoryBible 和历史原稿。

## 1. 依据、范围与裁决顺序

依据用户阶段 3 明确要求、[GDD](GDD.md)、[StoryBible](StoryBible.md)、[来源记录](Sources/README.md)，以及历史[总纲](Sources/HistoricalStory/story_bible.md)、[时间线](Sources/HistoricalStory/truth_timeline.md)、[知识矩阵](Sources/HistoricalStory/npc_knowledge_matrix.md)、[证据矩阵](Sources/HistoricalStory/evidence_matrix.md)和[第一章剧本](Sources/HistoricalStory/chapters/chapter_01.md)。已核对阶段 1/2 记录；本轮用户将既有 GDD/StoryBible 作为已验收输入，不回写旧报告的当时状态。

工程基线为 Unity 6000.3.29f1、HDRP 17.3.0，保持当前依赖。客户端实现边界见 [TechnicalDesign](TechnicalDesign.md)，规则权威、上下文与恢复见 [Architecture](Architecture.md)，所有 HTTP 方法、字段、枚举、错误码和事务规范仅以 [DataSchema](DataSchema.md)为准。本文的流程节点和中文条件说明不是额外 API。美术、测试、实施分别见 [VisualDirection](VisualDirection.md)、[TestPlan](TestPlan.md)、[VerticalSlicePlan](VerticalSlicePlan.md)。

范围包含 E01–E05、D01–D03、R01/R02、A01 和 A02 两种保管选择。主要交互人物是老周、林遥。三主区域为失物招领处、候车大厅、站台安全内侧；东室、西窗及档柜仍是既有区域内的位置。后章不在切片内实现；不新增许澄第一章强制流程，不制作第三章三种 END 结局。

规则优先级：用户当前明确要求 → 现行 GDD/StoryBible → 已采纳历史原稿 → 本轮技术建议。历史知识矩阵 D02 兜底中的“收件”歧义按现行 StoryBible 澄清：林遥本人看过两张单完成核对即更新其知识，暂收另外校验签条。技术上的输入焦点、动画、网络或物件移动都不得改变剧情真相和证据证明力。

## 2. 技术 ID、状态与不变量

### 2.1 与唯一契约对应

| 对象 | DataSchema 中的标识 |
| --- | --- |
| 当前章 / 后章开放标志 | CH01 / CH02（只存资格，不加载第二章内容） |
| 老周 / 林遥 | npc_laozhou / npc_linyao |
| 失物处 / 大厅 / 站台安全内侧 | lost_property / waiting_hall / platform_safe |
| 包 / 怀表 | package_A0641 / item_pocket_watch |
| E03 / E04 的物件 | record_repair_receipt / record_designated_receipt |
| E02 / E05 的物件 | record_power_fault / record_pickup_inspection |
| 联册 / 维修柜 / 箱签区 | station_lost_property_ledger / station_maintenance_cabinet / box_labels |
| 三个箱签检查对象 | box_label_1 / box_label_2 / box_label_3 |
| A01 / A02 选项 | assist_box_check / temporary_handover、bag_pending |
| R01 / R02 正确命题 | owner_shenhe_delegate_linyao / impact_jam_same_minute |
| 保管表现 | station_table / sealed_pending / linyao_temporary |

事件编号 E/D/R/A 是故事标识，不使用 Unity instanceID、场景层级序号或 NPC 名称显示文本作为存档主键。

### 2.2 必须持久化的最小进度

| 内容 | 权威结构与含义 | 不能由什么代替 |
| --- | --- | --- |
| 已开包、同号查源、档案索引等动作 | world_states 中的内容白名单动作 | 看见物件、摄像机进入区域 |
| 怀表和文书已查部位 | InspectionState；每部位独立，带来源字段 | 旋转次数、停留秒数、近检界面曾打开 |
| E01–E05 | EvidenceRecord 及 EvidenceSource，保留 media_refs 和原文 | 模型说“你找到线索了”或任意截图 |
| D01–D03 | DisclosureEvent，按 disclosure_id + npc_id + 内容动作键分开 | 全局 D02=true、玩家自己通过 R01 |
| 知识 / 误信 / 结构记忆 | NPCKnowledge、NPCMemory，逐角色记录来源 | 全局玩家已知、其他 NPC 的私谈 |
| 关系与一次性行为 | NPCRelationship、action_receipts、ChoiceRecord | 生成文本的礼貌/攻击判断、重复提问次数 |
| R01/R02 | ReasoningResult；持证且正确命题显式提交 | 手册连线、聊天中猜中答案 |
| A02 保管和回执 | ChoiceRecord、ItemCustody、custody_receipts | 动画已经演到一半、客户端把模型藏起来 |
| 章末 / 继续资格 | ChapterProgress，CH01 完成、CH02 开放 | 倒计时、必须全取证的隐含门槛 |

所有结构、公共列、主外键和检查点格式依 DataSchema，不在此另建数据库模式。GameEvent 记录由规则层派生的安全领域 ID；事件类型及内容动作键随同版内容目录发布，不使用自由输入正文作事件键。

不变量：

- 世界 F01–F12 始终不变。21:17 照明跳闸与坠表同分钟，**机械表因撞击卡滞，不能由停电推出停表**。
- 已取得证据、已查部位、编号与影像在当前存档分支不会因暂交/装袋/关窗消失。显式读更早检查点时，按该点恢复进度；这与原物保管变化导致证据丢失不同。
- NPC 的“真实知道”“当前可说”“误信”和“玩家转述”各自分开。林遥没参加 D02，不因玩家有 E04、老周核对或 R01 通过而获领取授权知识。
- R01 不增加 D02 条件；R02 不增加 D01/D03 条件。A02 暂交单独检查林遥 D02；装袋不要求 D、R 或 A01。
- CH01 完成条件只有 E01 已登记且 A02 已确认。实现范围包含全套 E/D/R/A，但玩家单次通关不必全做。
- A02 结果在当前分支只确认一次；需要比较另一保管选择时读确认前检查点。后续终局的合法物品处置是另外的规则，不以第一章重复 choice.commit 代替。

## 3. 开场、空间与交互准备

开场采用原章稿：玩家在失物招领处接班，打开「暴雨滞留／A-0641」积压包，怀表、带套、封票袋可见；先检查表，后两物按后章登记流程开放。站内广播固定为「青禾站今晚完成最后一次值班交接。候车厅内侧可以通行。」不增加日期或未批准的通知。

老周在候车大厅清点桌边，林遥在西值班窗旁等叫号，均可回访。固定开场句分别为：

> 老周：「这封从旧库搬过两回。我来对号，你来签。先看表背，失物只认号。」
>
> 林遥：「公告上有一张我妈留的领取凭号。我把原来的带来了。表还在吗？」

| 区域 | 第一章交互点 | 结果边界 |
| --- | --- | --- |
| lost_property | 包、怀表、夹层、柜台副联册、保管回执与章交接页 | 看见带和票不取得 E06/E11；无模型揭晓后章 |
| waiting_hall | 老周、林遥、三箱签；交谈/核对锚点 | 路径与站位是表现约束，不随机消失或用关系锁死案务 |
| platform_safe | 维修柜、故障卡正背、拾物检点联、灯罩/台沿 | 当前台沿缺口是环境细节，不发证，不证明当年事故 |

所有场景操作先满足当前区域、无遮挡距离和内容前置，由 scene.interact 打开具体目标上下文，再由 item.inspect 或 NPC 命令执行明确动作。检测是单机体验报告，不宣称防篡改。

打开包用 open_package；进入物件近检/交谈用 begin_interaction。切换目标先使旧上下文失效，退出用 close_interaction；token、超时及读档失效语义依 DataSchema。旋转、缩放、复位、悬停、打开手册都不是取证事件。取证成功后按 changed 结果获取全量 PlayerStateView，再开放依赖它的下一写动作。

## 4. E01–E05：原文、来源与获取规则

### 4.1 证据原文与证明范围（逐字采用原矩阵）

| 证据 | 固定正面文字或明示观察 | 来源与首开条件 | 支持、边界及不会证明的事 |
| --- | --- | --- | --- |
| E01 停表与编号 | 「表面 21:17。背刻 0412·0916。后盖边钢印 QH-283。侧冠凹陷，冠轴可见偏斜。」 | 第 1 章失物招领处，开 A-0641 包后翻面，再检侧冠。保留有方向的三面照片。 | F03–F04 的实物之一。盘面读数本身不能证明跌落时间或是谁的表。 |
| E02 配电故障卡 | 「站台照明支路进水跳闸 21:17。21:20 内侧油灯临时补照。本夜该支路未恢复。」 | 第 1 章站台内侧维修柜。开场移交手册标出。 | F02；用于修正 B01。无末班停运原因。 |
| E03 旧修表收据 | 「交修人 沈禾／物件 QH-283／该机为机械上链／背刻 0412·0916。」 | 第 1 章失物包夹层。观察到编号后固定点「查同号单据」，夹层和翻背可重复。 | 与 E01 核对来源，辅助 F03、支持 F04。交修人与指定领取人是两条记录。 |
| E04 指定领件联 | 「第十日补登记。表主 沈禾／指定领件 林遥／QH-283。由领件人本人决定并持凭号联络。沈禾。」 | 第 1 章柜台内失物副联册。由 E03 上的小字档位或直接翻失物册按 QH-283 找，林遥在场时可用同号凭证提示。 | F04、F12 的部分；授权为核实后的领取，第一章签新暂收条才产生保管变动。 |
| E05 拾物与检点联 | 「21:17 沈禾扶 0641 乘客避滑，怀表落至内侧台沿。拾取时盘面停 21:17。22:03 表冠凹、冠轴侧弯，传动卡滞，未拆修。周。」 | 第 1 章站台维修柜，E02 背页索引「该时段拾物联」可直接翻取。 | F03 的时点、事故和症状。E01 验痕，E02 负责独立区分站台电力。 |

### 4.2 怀表五部位

| part_id | 明确检查得到的内容 | 保存与发卡 |
| --- | --- | --- |
| dial | 时针/分针所示九点十七分；不凭指针判断昼夜 | 单项已查；不立刻给完整 E01 |
| back_engraving | 0412·0916 | 单项已查；辨认特征，不是物权 |
| serial_number | QH-283 | 单项已查；可查同号 E03/E04，即使 E01 尚未齐 |
| side_crown | 侧冠凹陷 | 单项已查，不自动断言机理 |
| crown_shaft_damage | 冠轴可见偏斜 | 单项已查，不增拆修或“修好表”的玩法 |

第一次观察部位，在合法 item_pocket_watch 上下文中提交 item.inspect。规则层写本部位 InspectionState；五项齐全且 E01 尚未登记时，在同一事务建立 E01 与获准三方向 media_refs。每项只登记一次；重复检查返回既有内容，不新增证据或关系收益。检查顺序不限，编号可先查。

未齐全时，玩家手册只显示已查字段；物件表面本来可见不等于正式已查。不能首次打开近检就把全部钢印、刻字和损伤全文列在侧栏，也不能用自动环绕镜头代替主动点击检查。

### 4.3 文书与查源的程序前置

| 证据 | 合法访问与主动检查 | 原子结果 | 不应新增的门槛 |
| --- | --- | --- | --- |
| E02 | 到 platform_safe 维修柜，begin_interaction 指向 record_power_fault；item.inspect 的 document_front | 登记 E02 正面来源与固定全文 | 不需先完成 R/D 或帮助老周 |
| E03 | 开包且 serial_number 已主动观察；选择「查同号单据」路由到 record_repair_receipt；begin_interaction 后 document_front | 登记 E03，保留同号来源 | 不强制 E01 完整卡，不要求先找林遥 |
| E04 | 由 E03 小字档位，或按已观察 QH-283 直接翻副联册；进入 record_designated_receipt 后 document_front | 登记 E04，仍未自动更新林遥 | 不硬依赖 E03，不需 R01 或老周许可 |
| E05 | 维修柜中主动查看 record_power_fault 的 document_back_index，沿「该时段拾物联」进入 record_pickup_inspection，再 document_front | 登记 E05；正面故障、索引和拾物联的观察状态分开 | 不要求先触发 D01；不把“读到索引”当已读 E05 |

E05 的前置是读过故障卡**物件背页索引**，不是必须已经登记 E02 正面证据卡。因此可以先翻背找 E05、后来才读 E02 正面；R02 仍需两张证据。E03/E04 的查源动作名由内容路由绑定 DataSchema 已有目标和 begin_interaction，不建立另一个任意“按编号发卡”接口。

首发卡由 item.inspect 派生。evidence.register 只可重新核验持久观察条件并补登记/重显，不能跳过上述来源与检查。E01–E05 同一 EvidenceRecord 主键只一份；照片、抄写与 NPC 复述共享原来源，不重复充当独立证据。

### 4.4 可引用字段 registry

以下字段名由 Director 核准并交 AI Engineer 写入 DataSchema 唯一 registry；这里只按同一命名映射原文字段，不产生第二套协议。字段正文仅来自上表固定文本，PlayerStateView 只返回已观察的字段与已取得证据全文，不下发完整作者材料。

| 证据 | field_ids（完整规范集合） |
| --- | --- |
| E01 | watch.dial、watch.back_engraving、watch.serial_number、watch.side_crown、watch.crown_shaft_damage |
| E02 | power_fault.branch_fault、power_fault.timestamp、power_fault.lamp_time、power_fault.not_restored |
| E03 | repair_receipt.customer、repair_receipt.item_number、repair_receipt.mechanism、repair_receipt.back_engraving |
| E04 | designated_receipt.registration_day、designated_receipt.owner、designated_receipt.recipient、designated_receipt.item_number、designated_receipt.collection_terms |
| E05 | pickup_inspection.incident_time、pickup_inspection.incident_description、pickup_inspection.dial_at_pickup、pickup_inspection.inspection_time、pickup_inspection.mechanical_findings、pickup_inspection.recorder |

D01 的固定核对使用 E02 全集合；D02 使用 E03+E04 全集合；D03 使用 E01+E05 全集合，接收人仍须匹配下节规则。只选部分字段可以作为展示，但不能满足一次完整 D 的当前出示前置。模型生成文字没有 field_id 资格，也不因为玩家打出了钢印或字段名而增加 observed_fields。

## 5. D01–D03：固定披露、错误记忆与本人核对

D 的标准调用为：对当前本人 begin_interaction → npc.present 出示已持证据及获准字段 → 玩家明确选择固定核对/追问 → disclosure.trigger。DataSchema 要求本 NPC 当前出示记录与有效上下文；只打开出示面板不触发，退出再回需重示。同一材料可以分别给两人看，但必须是两个各自实际参与的动作。

npc.present 第一次实际展示某本人尚未见过的证据/字段差集时，保存安全的展示事件与该 NPC 事件记忆，changed=true、版本递增；它仍不改变 NPCKnowledge、不代替 D。重复展示同一差集仅恢复当前临时展示上下文，changed=false、不重复记忆。退出后，幂等缓存的旧成功结果不能重新建立有效上下文；重新交谈须以新 request_id 重示，再明确触发 D。开包首次也写持久开包动作并递增版本，不把场景显隐当只有本地效果。

| ID / 接收人 | 前置 | 固定内容与权威副作用 | 不产生的结果 |
| --- | --- | --- | --- |
| D01 / npc_laozhou | E02；向老周出示后明确核对照明 | 固定句见下；停用 B01 未修正版本，记录本人已据 E02 核对跳闸/补照时点的知识与结构记忆，登记本人的 DisclosureEvent | 不增加证据；不自动通过 R02；不改变林遥；无默认关系分 |
| D02 / npc_linyao | E03+E04；林遥本人实际看过两张单并完成核对 | 固定句见下；更新她对 F04 的编号/领取授权的知识，记本人 D02；即使未暂收也已知情 | 不自动产生 R01 或 A02；不因她知道母亲姓名而提前开放完整授权 |
| D02 / npc_laozhou | E03+E04；老周本人核对单据 | 登记老周 D02 与本人的核对记忆；以已批准单据原文核对展示，不编原稿未给出的新案情长台词 | 不更新林遥，不满足 A02 的林遥本人 D02 条件 |
| D03 / npc_laozhou | E01+E05；向老周出示后明确追问撞击 | 固定句见下；开放他本人亲历拾表及冠轴说明，记本人 D03 与结构记忆 | 不额外发 E05，不自动通过 R02，不扩到后章秘密 |

### 固定台词与修正口径

| 情境 | 获批固定文字 |
| --- | --- |
| B01 尚未修正时问老周照明 | 「站台那晚在我印象里一直亮着。我还把那盏油灯拖到里头去了。」 |
| D01 | 「进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。」 |
| 林遥看见并辨认表背时 | 「四月十二是我妈的生日，九月十六是我的。那个点，我小时候摸得到。柜里究竟是不是那一只，你得对上号。」 |
| D02 林遥 | 「沈禾，是我妈妈。这个号和她放在家里那张一样。她写着要我自己领。」 |
| D03 | 「她抓住小姑娘的胳膊，表掉到台沿。我弯腰拣的时候指针已经不动了，冠头是歪的。」 |
| 林遥拒绝可选闲聊 | 「表的事按签单。别的今天先别问。」 |

B01 修正后不再把初始“一直亮着”作为当前有效陈述播放；可回看旧陈述和修正来源，不当作故意说谎。林遥的辨刻字句只说明辨认和生日，不能替代 E03/E04 或本人 D02；要在她实际参与该观察时呈现，不因玩家在另一房间翻背就自动令她作出反应。

三类 D 均按当前分支一次结算。重复本人同 D 可回看固定句，changed=false，不叠加知识、证据或关系；D02 的去重包含 npc_id。拒绝闲聊、模型超时或不可用仍保留「照明」「表背」「领件编号」和固定案务；条件不足只提示当前允许的来源动作，不给未获事实全文。D01/D03 不要求先出现 B01 问话，避免错过闲聊后无法核对。

**知识边界：** 老周仍不能在第一章主动讲 F08/F10 的后章覆盖/改簿细节；林遥仍不能把 E05 机理变成她亲历的事故观察，不因 D02 提前得知西窗签询。R01 通过属于玩家的推理，不是林遥的 D02。

## 6. R01、R02：证据集合与显式命题

| ID | 全部必要证据 | hypothesis_id 与应通过的固定结论 | 成立后保存 |
| --- | --- | --- | --- |
| R01 | E01+E03+E04 | owner_shenhe_delegate_linyao：「怀表原主沈禾；今可由她书面指定的林遥领件。」 | R01 passed；固定结论及所用证据引用；不更新林遥 D02 |
| R02 | E01+E02+E05 | impact_jam_same_minute：「21:17 照明支路跳闸和怀表坠地同时发生，机械传动因撞击卡住，约三分钟后才临时补照。」 | R02 passed；固定结论与来源；不自动执行 D01/D03 |

通过条件为玩家确已登记全部必要证据，选择对应正确命题并提交 reasoning.submit。先后不限；可以先 R02 后 R01，或完全不提交而装袋结束本章。多选其他已持 E 不替代缺项，来源同一性按原证据记录校验。

| 失败/重复输入 | 规则结果与反馈 |
| --- | --- |
| 缺 E04 却只凭刻字/老周拾表断言领件 | PRECONDITION_FAILED，R01 不成立；提示去核对同号授权来源，不凭模型赞同通过 |
| 材料齐全但 R01 选老周为原主 | 业务响应 passed=false、changed=false；依已见拾物/修表/领件内容区分经手人与原主 |
| R02 选“停电使机械表停了” | passed=false、changed=false；指出电力与机械传动是不同系统，相关来源仍可重看 |
| R02 选“站台完全一直亮” | passed=false；据已取得 E02 指向 21:20 补照，不追加人物恶意 |
| 初次错误后重选正确命题 | 保留证据，允许新意图提交；不扣关系、不删卡 |
| 已过 R 再次提交正确命题 | 返回既有 passed=true、changed=false；不重复事件、奖励或表演 |
| 在自由输入框写完整正确结论 | 仅算问题/猜测，不发 R，不改知识或保管；提示使用已开放的明确核对/提交入口 |

错误命题 ID 从获批内容白名单取得；本文不另命名与 DataSchema 竞争的错误枚举。关键反馈必须固定、只引用玩家已见材料；不能为了反馈完整性提前公开后章真相。

## 7. A01、A02 与第一章结束事务

### 7.1 A01：可选箱签核对

在大厅 box_labels 区，玩家分别主动检查 box_label_1、box_label_2、box_label_3，并完成已批准的同号匹配后，选择 A01/assist_box_check。此行动不以 E01/D/R 为前置，也不是任何证据或章末的必经步骤。

规则层校验三个已查对象和匹配结果，首次成功同一事务写 A01、一次性 action_receipts 与老周关系变化：trust +1、pressure -1，分别 clamp 到 0–3，suspicion 不变。初始 1/1/0 的示例结果为 2/1/0。固定过渡句为「行，回头我给你腾柜台」。重复点击、同键重试或换新 request_id 重做已结算 A01 均不再加分。

三箱签的具体非案情文字/编号 [待确认]：推荐使用与物证真相无关的库房同号核对内容，保留三次观察和匹配行为；需 Director/Narrative 在内容冻结时批准确切文字，再由 Art 排版与 QA 制作 fixture。技术 ID box_label_1/2/3 已在 DataSchema 定义，不把这些 ID 冒充原故事箱号，不新增票号、人物、日期或事故线索。

### 7.2 A02：两种保管选择

| 选项 | 必要前置 | 单次事务写入 | 确认后的表现 |
| --- | --- | --- | --- |
| bag_pending（装袋待核） | E01 已登记；合法保管上下文；玩家明确确认装袋 | ChoiceRecord(A02)、保管 sealed_pending、固定保管回执、CH01 完成/CH02 开放、自动章末检查点、幂等结果；证据与检查状态保留 | 表放回有案号软衬袋；章交接写已核/待核；不默认已定权属 |
| temporary_handover（暂交林遥） | E01 已登记、R01 passed、**林遥本人 D02**、npc_linyao 本人在获准核对/交接中、玩家在可读今夜暂收条上明确确认 | ChoiceRecord(A02)、保管 linyao_temporary、接收人 npc_linyao、暂收回执、CH01 完成/CH02 开放、自动章末检查点、幂等结果；证据与检查状态保留 | 她把表收入衣袋，仍留站等结案；照片/编号/回执可查，日后合法终局处置范围依原授权 |

暂收条保留原章稿的授权含义：最终可由她签收；去名公开后由她签收；或按其今夜授权交回受限封存。本文不新增她永久离站、物权改变或新的案件结局。receipt_confirmed 是本章明确交互的确认，不代表外部法律签名，也不能让任意客户端真值绕过证据及本人核对条件。

准备阶段先校验站位、显示回执与选项，允许取消；不改变保管。确认后使用 choice.commit，由后端一次提交全部权威变化，成功投影同步后才播入袋/收表。签字动画、回执模型显隐、角色走到桌边都不是事务触发器；AnimationEvent 不能发证、交物或判章末。

提交前取消无 A02。请求超时不等于失败：同键查询/重试；已提交但动画失败按权威保管重建；未提交则保管仍原状。不能因动画中断复制两只表或丢 E01，也不能因为未取得 R02 而挡住暂交。

### 7.3 结束与回访

判定式为 **E01 已登记 AND A02 已确认**。若未满足，chapter.advance 只能报告/重算前置，不得直接设置 completed；一旦 A02 同事务满足，CH01 完成与 CH02 开放已存在，无需靠第三次点击才真正开章。

独立切片保持当前可游玩内容为 CH01：章交接页可返回补查第一章、读确认前检查点比较另一选择或退出；CH02 只保存开放资格。章末不显示 END_RETURN/END_SEAL/END_PUBLIC，不调用第二章录音调查。已完成 CH01 后仍可补 E02–E05、D01–D03、R01/R02、尚未做过的 A01；不能把 CH01 completed 当所有入口关闭条件。

原稿的磁带套「A 面」与老周推放音机的固定引入可作为章节收束表现，不能因此读取 E06/E07 或启动第二章。任何引入音画也不能恢复被覆盖原声或提前解释后章秘密。

## 8. 完整流程、依赖与状态机

### 8.1 推荐完整调查流程（不是强制锁）

下图实现任务书所列的完整展示路线；取证和核对之间可回访、逆序。虚线是可以更早结束章节的选择，不能被完整路线的演示顺序覆盖。

~~~mermaid
flowchart TD
    S["开场接班与安全引导"] --> P["打开 A-0641 包"]
    P --> W["主动检查怀表五部位"]
    W --> E1["E01 入档"]
    E1 --> E3["按编号查同号单据：E03"]
    E3 --> E4["查询副联册：E04"]
    E4 --> N["与老周、林遥分别交流"]
    N --> T["前往站台安全内侧"]
    T --> E2["读故障卡：E02"]
    E2 --> E5["翻背页索引再查拾物联：E05"]
    E5 --> D["分别执行 D01、D02、D03"]
    D --> R["可提交 R01、R02；任一都可暂挂"]
    R --> C["明确执行 A02 合法选项"]
    E1 -. "不强求其他调查" .-> B["A02 装袋待核"]
    B --> F["CH01 完成；仅记录 CH02 开放"]
    C --> F
    F --> V["章交接：返回补证 / 读取 / 退出"]
    V -. "尚未完成的调查" .-> N
    N -. "完全可选" .-> A["A01：核对三个箱签，只结算一次"]
    A -.-> N
~~~

### 8.2 条件依赖图

~~~mermaid
flowchart LR
    O["已开包"] --> I["怀表主动检查"]
    I --> SN["编号已查"]
    I --> FIVE["五部位已查"]
    FIVE --> E1["E01"]
    SN --> E3["E03"]
    SN --> E4["E04：也可直接查册"]
    SOURCE["故障卡物件"] --> FRONT["读正面：E02"]
    SOURCE --> BACK["读背页索引"]
    BACK --> E5["再读拾物联：E05"]
    E3 --> D2["本人 D02"]
    E4 --> D2
    E1 --> R1["R01 + 正确命题"]
    E3 --> R1
    E4 --> R1
    E1 --> R2["R02 + 正确命题"]
    FRONT --> R2
    E5 --> R2
    E1 --> BAG["A02 装袋"]
    R1 --> HAND["A02 暂交 + 暂收确认"]
    D2 -->|"必须为林遥本人"| HAND
    BAG --> END["CH01 完成"]
    HAND --> END
~~~

图中 D02 与 R01 是并列条件，不互为前置；暂交同时检查两者。D01/D03 的依赖见第 5 节，不是 R02 的额外门槛。E03/E04 可在 E01 未合成前先取得。

### 8.3 章状态机与叠加进度

~~~mermaid
stateDiagram-v2
    [*] --> Loading
    Loading --> Investigating: 新建或激活并完成状态绑定
    Investigating --> ChoiceReady: E01已登记
    ChoiceReady --> PreparingChoice: 选择一个当前合法A02选项
    PreparingChoice --> ChoiceReady: 确认前取消或就位失败
    PreparingChoice --> SubmittingChoice: 明确确认
    SubmittingChoice --> ChoiceReady: 确定未提交且前置失败
    SubmittingChoice --> Reconcile: 响应丢失或结果未知
    Reconcile --> SubmittingChoice: 同请求恢复查询
    SubmittingChoice --> ChapterCompleted: 权威提交成功
    Reconcile --> ChapterCompleted: state证实已提交
    ChapterCompleted --> ChapterCompleted: 回访补证不重做A02
    ChapterCompleted --> Loading: 显式读取确认前检查点
~~~

这是客户端呈现/章进度映射，不把 E/D/R 全部排列成一个线性枚举。包、检查部位、E 集合、各人 D、R 和 A01 是正交持久进度；任何合法可达顺序都按集合前置判断。Reconcile 中不擅自复原原物或换 request_id；普通命令幂等、activate 控制面恢复与时代失效按 DataSchema 执行。

## 9. 规范 JSON 与事务示例

以下是可解析的文档示例，不是已实现接口。URL 为 POST /api/v1/saves/55555555-5555-4555-8555-555555555555/commands；认证头依 DataSchema。假定同一有效 runtime、state_version=20，E01/E03/E04 已取得且 R01 尚未提交，玩家选择正确命题。

~~~json
{
  "request_id": "12345678-1234-4234-8234-123456789012",
  "save_id": "55555555-5555-4555-8555-555555555555",
  "runtime_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version": 20,
  "command_type": "reasoning.submit",
  "payload": {
    "reasoning_id": "R01",
    "evidence_ids": ["E01", "E03", "E04"],
    "hypothesis_id": "owner_shenhe_delegate_linyao"
  }
}
~~~

~~~json
{
  "request_id": "12345678-1234-4234-8234-123456789012",
  "save_id": "55555555-5555-4555-8555-555555555555",
  "runtime_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version": 21,
  "changed": true,
  "data": {
    "reasoning_id": "R01",
    "passed": true,
    "conclusion_ref": "reasoning.R01.correct",
    "fixed_feedback": "怀表原主沈禾；今可由她书面指定的林遥领件。",
    "event_ids": ["e4444444-4444-4444-8444-444444444444"]
  },
  "error": null
}
~~~

这个成功只更新玩家 R01。客户端按 DataSchema 获取完整 PlayerStateView，不由 event_ids 推测知识。若林遥 D02 尚未完成，立即暂交仍失败；不能将 R01 的 conclusion_ref 当林遥已看过授权。

另一个独立示例：假定已获 E01、R01 和林遥 D02，林遥在合法交接上下文，玩家已在可读暂收条上确认。state_version=27 是此次查询所得当前版本，与上例不构成完整请求日志；token 值只为示意，运行时由服务签发。

~~~json
{
  "request_id": "22345678-1234-4234-8234-123456789012",
  "save_id": "55555555-5555-4555-8555-555555555555",
  "runtime_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version": 27,
  "command_type": "choice.commit",
  "payload": {
    "choice_id": "A02",
    "option_id": "temporary_handover",
    "npc_id": "npc_linyao",
    "receipt_confirmed": true,
    "interaction_token": "issued-by-server"
  }
}
~~~

~~~json
{
  "request_id": "22345678-1234-4234-8234-123456789012",
  "save_id": "55555555-5555-4555-8555-555555555555",
  "runtime_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version": 28,
  "changed": true,
  "data": {
    "choice_id": "A02",
    "option_id": "temporary_handover",
    "item_id": "item_pocket_watch",
    "custody_state": "linyao_temporary",
    "receipt_id": "77777777-7777-4777-8777-777777777777",
    "chapter_completed": ["CH01"],
    "chapter_opened": ["CH02"],
    "registered_evidence_ids": [],
    "event_ids": ["e6666666-6666-4666-8666-666666666666"]
  },
  "error": null
}
~~~

事务包含保管、签条、A02、章资格、章末检查点与幂等结果，不在生成回复或动画事件里分批写入。装袋 payload、E01/NPC/检查点完整结构参见 DataSchema 的对应示例，不复制一套不同 DTO。

## 10. 存读档、失败和异常序列

| 情景 | 保留/恢复及可观察结果 |
| --- | --- |
| 只查表盘后保存 | 仅恢复 dial 已查；不出现完整 E01、刻字或授权 |
| 查编号→先 E04→E03→补五部位 | 全序合法；记录真实取证顺序，R01 仍等齐 E01 |
| 先 E05 后 E02 | 要先读故障卡背页索引再查拾物联；未读正面不给 E02，R02 不成立 |
| 老周 D02 后保存/读档 | 林遥 D02 仍未做，授权知识不凭空出现；A02 暂交仍不可用 |
| 暂交后继续查 E02/E05、交 D03、做 R02 | 手册影像/编号/检查资格保留，林遥仍可回访；不要求再从她身上取走实物 |
| 连续出示/重复正确推理/A01 重复 | 同请求返回原结果；新请求也受领域去重，不叠关系和证据 |
| 缺 E04 却试暂交，或签条未确认 | 整个 choice.commit 不提交；表、回执、章状态保持原状 |
| 提交后断网/动画中断 | 先查询/同键重试确定已提交与否；按 ItemCustody 重建；不造第二回执 |
| 模型不可用、非法结构或超前猜问 | 同条件固定话题/案务可用；不发 E/D/R/A，不确认猜中 |
| NPC 拒绝闲聊 | 固定核对仍可用；无永久软锁，不要求刷关系 |
| 规则后端不可用 | 只可看已有手册/设置；暂停所有权威变化；不由客户端填成功结果 |
| 换人/取消后旧回复到达 | 不呈现、不写记忆；新 NPC 只用自身上下文 |
| 读取 A01 或 A02 之前的检查点 | 当前进度、知识、关系、保管及去重标记按该点恢复；旧审计事件不重新补未来动作；runtime 换代、版本高水位递增 |
| 坏档/内容版本不兼容 | 保留原库与最后有效检查点，明确拒写/恢复入口，不静默清空 |

日志/持久事件仅保存获准 ID、固定内容引用与安全结构值，不保存自由输入全文或由其生成的摘要。读取旧档不恢复未决 turn、输入草稿、interaction_token 或旧 HTTP 请求。

## 11. QA fixture 与验收对应

以下是测试计划可实现的行为 fixture，名称仅作测试夹具说明，不是新游戏内容。所有断言检查服务内部状态和玩家投影两侧；当前阶段未生成测试代码或运行游戏。

| fixture | 最小构造与顺序 | 核心断言 |
| --- | --- | --- |
| FRESH_CH01 | 新建 CH01，未开包 | 无 E/D/R/A、初始保管 station_table；无后章事实 |
| PARTIAL_SERIAL | 开包，仅主动查 serial_number | 可查同号 E03/E04，不存在完整 E01 |
| E01_READY | 任意顺序主动查齐五部位 | 恰一 E01、三方向影像、R01/R02 尚未自动成立 |
| BAG_MINIMAL | E01_READY→A02 bag_pending | CH01 完成、CH02 开放、sealed_pending；D/R/A01 可全部为空 |
| OWNER_READY | E01+E03+E04→R01 正确提交 | 玩家 R01 已过，林遥授权知识仍未获；暂交仍缺本人 D02 |
| LAOZHOU_REVIEW_ONLY | OWNER_READY→只向老周做 D02 | 老周 D02 已记，林遥 D02 未记，暂交拒绝 |
| HANDOVER_READY | OWNER_READY→林遥本人 D02→明确暂收条 | A02 temporary_handover 一次提交；E01/影像和 R01 保留 |
| IMPACT_AFTER_HANDOVER | HANDOVER_READY→补 E02/E05→R02 | 可完成正确机理，表不需回柜台；“停电使机械表停”仍不通过 |
| INDEX_FIRST | 读故障卡背页索引→E05→后读故障卡正面 | 先无 E02，后才有；不把索引当 E05 正文 |
| RESTORE_PRE_CHOICE | A02 后激活 A02 前检查点 | 恢复该点已有知识/关系及保管，不回补该点之后的动作；旧 runtime 回复无效，可按新分支合法选择 |

需覆盖的删除前置负例：E01 缺任一部位、R01 缺 E03/04、R02 缺 E02/05、D02 对错人/缺单、暂交缺本人 D02/缺确认、A01 缺一个已查箱签或匹配错误。每次失败证据不丢、物件不移动、不隐式增加关系。

本章直接关联 GDD AC01、AC02、AC05、AC06、AC07、AC08、AC13、AC14 的第一章部分和 AC15 的章内恢复部分；AC03/04/09–12 及 AC14/15 中录音/终局部分属于后章保留回归。完整用例步骤、运行命令、截图与故障注入方案以 QA 的 TestPlan 为准。

## 12. 未决项与完成边界

| 项目 | 推荐与理由 | 需要确认/执行门槛 |
| --- | --- | --- |
| [待确认] 三箱签的确切非案情文字/同号内容 | 使用中性库房标签，保留三个对象的主动核对，不新增事故线索 | Director/Narrative 批准内容后才能制作正式纹理与匹配 fixture |
| [待确认] 暂收/保管回执具体版面 | 使用原章稿既定处置授权，固定可读文案与明确确认，不保存自由手写签迹 | Narrative/Director 核准最终版面文字，Art/Unity 做读字与签条动作验收 |
| [待确认] 驻点、热点、读单/交接锚点坐标 | 在已批准三区域平面内设可达锚点，全部必要交互在安全侧 | Unity/Art 灰盒与目标机验证；不得借坐标调整改变案情 |
| [待确认] 技术阈值及发布范围 | 距离/镜头/超时等沿技术文档候选值验证再冻结 | 用户确认体验与目标硬件；不影响既定 E/D/R/A 条件 |

本章正式故事事实、核心证据文字、正确命题与章末门槛均已确定；上述制作细节不允许用 AI 即兴内容填充。文档映射完成不代表数据资产、规则程序、3D 表演、主线通关或实际时长已验证。待独立 QA 检查与 Director 汇总后交用户验收，不自行开始实现或第二章开发。
