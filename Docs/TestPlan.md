# 测试计划

待补充。

---

# 第一章垂直切片测试与验收计划

阶段 3，2026-11-21。唯一主笔：QA Engineer。原始标题及“待补充。”作为初始化历史保留。**本轮只交付测试设计和文档静态审查，下面所有游戏、API、数据库、画面与试玩用例均尚未执行。** 不创建测试源码、数据库、Scene、Prefab 或资源，不启动 Unity、后端或真实模型。

剧情判据：[GDD](GDD.md)、[StoryBible](StoryBible.md)、[第一章原稿](Sources/HistoricalStory/chapters/chapter_01.md)、[原证据矩阵](Sources/HistoricalStory/evidence_matrix.md)。接口及模型唯一依据为 [DataSchema](DataSchema.md)，不另定义错误码或可写状态口。客户端、部署、视觉与事件分别依 [TechnicalDesign](TechnicalDesign.md)、[Architecture](Architecture.md)、[VisualDirection](VisualDirection.md)、[Chapter01ImplementationMap](Chapter01ImplementationMap.md)。实施与报告见 [VerticalSlicePlan](VerticalSlicePlan.md)、[阶段 3 审查](Stage3TechnicalDesignReview.md)。

## 1. 测试分层、责任与进入条件

| 层级 | 检查对象 | 执行者 / 何时 | 通过能证明什么 |
| --- | --- | --- | --- |
| 文档静态 | 字段、JSON、链接、来源、事件前置与章节闭包 | QA 独立审查，Director 核保护范围；阶段 3 | 方案一致且有可检验判据；不能证明运行实现 |
| Unity EditMode | 输入模式仲裁、DTO、版本接受、内容 ID/影像引用、UI 投影 | QA 测试作者，Unity 修业务；M2–M9 | 纯逻辑和资源引用行为 |
| Unity PlayMode | 射线遮挡、距离、五部位、场景/人物/UI/暂停、动画打断 | QA，Unity/Art 修所属；M2–M9 | Unity 集成可观察行为；不替代发行包或真实 IME |
| Python 单元/API/SQLite | 规则、严格契约、事务、幂等、知识、恢复、迁移 | QA 唯一写 Server/tests；AI 修 Server/app；M5–M9 | 权威规则及存储集成；不证明 3D 表现 |
| Windows 发行包 | 冷启动、本机服务、真实键鼠/中文输入、保存、退出、图形 | QA；Unity/AI/Art 负责定位修复；M9 | 当前构建与指定系统上的发行行为 |
| 真实模型专项 | 已授权供应商的质量与对抗问题 | QA + Narrative；仅未来单独授权真实调用后 | 该模型/配置下的测量；不宣称零幻觉 |
| 完整试玩 | 新手调查、人物可信度、舒适性、画质/节奏 | Director 组织用户验收，QA 记录；M10 | 用户体验与验收意见，不能代替自动化故障覆盖 |

~~~mermaid
flowchart LR
    C["来源与契约冻结"] --> E["EditMode / Python规则与数据库"]
    E --> P["PlayMode 场景与交互"]
    P --> W["Windows包 / 中文IME / 音画"]
    W --> U["未参与开发者试玩与用户验收"]
    E --> F["失败证据与唯一作者修复"]
    P --> F
    W --> F
    F --> R["回归原用例及受影响边界"]
    R --> E
~~~

进入运行测试前：用户已授权对应里程碑；版本、工具、目标机和测试写入清单明确；内容/API 版本冻结；测试 fixture 与玩家真实保存隔离；本次构建带可追溯标识。项目当前仅有测试目录骨架，不能把空目录或未发现测试的成功命令算通过。

当前锁文件记录 Unity Test Framework 1.6.0、Performance 3.7.0、Code Coverage 1.3.0、UI Test Framework 6.3.0；存在包不等于测试已建或开关已启用。本机当前 Python 解释器可见 FastAPI/Uvicorn/Pydantic 分发包，项目 requirements 未锁且 pytest 当前未检出。后续锁定所需 pytest、HTTP 测试客户端及异步测试依赖后再运行，不在本轮安装。

## 2. Fixture、观察面与隔离

测试 fixture 属于后续 QA 资产，以下为逻辑名称，不是本轮已存在文件。API fixture 应通过生产内容/规则建立基线；仅专门数据库约束/坏档用例可用受控直接 seed，绝不能把测试种证据入口发布给客户端。

| Fixture | 可复现实况 | 主要用途 |
| --- | --- | --- |
| F0 新存档 | CH01 开放，包未开，E/D/R/A 均无；两人关系1/1/0；无活动对话/近检 | 非法越过前置、首次体验 |
| F1 已开包 | F0 完成合法 open_package，怀表在台面；其他同 F0 | 单部位、重复开包 |
| F2 部分近检 | F1 仅完成指定五部位子集，至少包含 serial_number 的变体 | 32 个部位子集、E03/E04 逆序 |
| F3 完整 E01 | 五部位已主动检查、E01 和三向影像入档；无其他 E/D/R/A | 最短装袋、非法暂交 |
| F4 领件物证 | F3 加 E03、E04，但无 D02、无 R01 | 证明推理与本人核对是不同动作 |
| F5 R01 已过 | F4 正确提交 R01；可分别制作 D02:老周、D02:林遥、未 D02 三变体 | A02 暂交正负路径 |
| F6 灯与拾表 | F3 加 E02/E05；D01/D03、R02 未做 | 修正 B01、机械因果 |
| F7 暂交后 | 合法 E01+R01+林遥 D02+明确暂收条完成 A02，表由林遥暂管，E02/E05 可未取 | 交后补证、动画崩溃恢复 |
| F8 装袋章末 | F3 明确装袋完成 A02，无 R/D/A01，CH01完成/CH02仅开放 | 最短完章与第一章回访 |
| F9 双存档/双时代 | 独立 S1/S2；每档至少两个检查点，Rold/Rnew 与版本有区分 | 串档、旧回复、读档屏障 |
| FM 模型替身 | 可控制不可达、超时、非法结构、越界正文、迟到/乱序；不连接真实云 | 可重复的失败和注入测试 |
| FV 视觉固定路线 | 台面表盘/背刻/编号/冠轴、两人物驻点、维修柜、入口/返程；时间/曝光和镜头固定 | 三档、分辨率、截图与性能对照 |

每次用例创建独立临时 save/SQLite。纯 Repository 可用内存 SQLite；多连接、锁、断电、磁盘满、备份/迁移必须用 QA 临时目录的文件库，不以单连接 :memory: 模拟真实锁与崩溃。pytest 的 tmp_path 提供独立目录；测试结束只清理本次明确创建的目录，不能清理用户保存。[pytest 临时目录](https://docs.pytest.org/en/stable/how-to/tmp_path.html)

观察面至少包括：HTTP 状态与规范 JSON、PlayerStateView、测试专用只读 Repository 查询、事件/当前 action_receipts、NPC 最小上下文捕获、当前状态版本/运行身份、Unity 可见物/输入/焦点和脱敏日志。生产 API 不为测试暴露作者真相。数据库断言必须区分“历史审计事件仍保留”和“当前投影已回到检查点”，不以全历史事件总数代替当前分支去重。

所有命令用例均按 DataSchema 带 request_id/save_id/runtime_id/state_version，先建立正确对象上下文；变更成功后 GET state 更新版本再发依赖命令。无变化或错误测试固定比较领域状态；若允许记录安全审计，不能误断言所有表绝对零写入。

## 3. 第一章剧情与物证测试

表内 CH 用例由 QA 负责自动化/复现，Narrative 提供内容 oracle，AI/Unity 分别修规则和交互。每项结果同时保留响应、前后状态差异与相关截图；M3 可先测近检，M7 全量，M9 回归。

| ID / fixture | 操作与参数 | 精确预期及必须不发生的结果 |
| --- | --- | --- |
| CH01 / F1 | 只旋转、缩放、复位/悬停表，不点击检查 | 五个检查标记仍未完成，E01无，关系/R/章状态不变 |
| CH02 / F1 | 对五部位所有32子集逐一重建fixture，合法 item.inspect 完成子集 | 仅全集产生 E01；其余只见已观察字段，无完整卡/R资格；全集保留三向影像及原样文案 |
| CH03 / F2 | 同一部位同request重试，再新request重查 | 同键复用结果；新请求合法重看 changed=false；同部位不重复发卡/奖励，五部位顺序任意 |
| CH04 / F2 | 未查 serial_number 直接查收据；查编号后查同号收据并读正面 | 前者 PRECONDITION_FAILED，无E03；后者取得E03，即使E01尚未齐，固定文字与原矩阵一致 |
| CH05 / F2 | 只查编号，先直接翻副联册读E04，再查E03，最后补齐E01 | E04不硬依赖E03或完整E01；编号未知不能凭自由文本自称持号；最终R01材料齐全 |
| CH06 / F0 | 进入站台维修柜检查故障卡正面、背页索引、拾物联正面 | 正面发E02；背页仅开放E05入口；读拾物联正面才发E05，不从门牌/现台沿缺口自动取证 |
| CH07 / F0变体 | 可合法先读故障卡背页索引，再读E05，最后读故障卡正面 | 允许先E05后E02，前者不能自动发E02；R02仍需两卡。不得把推荐探索顺序写成硬前置 |
| CH08 / F6 | 老周当前交谈中出示E02，再触发D01；缺E02/给林遥各做负例 | 仅正确本人/材料生效，B01修正并给固定句；不增E、不改林遥、不无因加关系 |
| CH09 / F4 | E03/E04分别向老周或林遥出示并D02；分别缺一张再试 | 材料缺失不披露；老周分支不更新林遥；她本人看过并核对才学编号/授权，不必已暂收 |
| CH10 / F6 | 出示E01+E05向老周触发D03；逐一删E/换NPC负测 | 正确给原稿拾表固定句且不新增物证；错误无知识/保管/推理变化 |
| CH11 / F4 | 正确R01命题，逐一删E01/E03/E04；把拾表人选作原主 | 正确集合+命题才passed；删项前置失败；错误命题passed=false，不扣关系、不改权属。D02不是R01额外前置 |
| CH12 / F6 | 正确R02；逐一删E；选“停电使机械怀表停走”或“一直亮” | 仅正确命题通过；错误反馈引用已见字段；断电和撞表同一分钟不等于电力停表 |
| CH13 / F1 | 检查并匹配三箱签做A01，缺任一箱/未匹配负例；重复按钮/改问法 | 只有获批匹配动作完成才一次结算；老周trust+1/pressure-1并截在0–3；无E/R/章节门槛变化，林遥关系不变 |
| CH14 / F3 | A02 bag_pending，明确保管确认；分别取消面板、receipt_confirmed=false负例 | 确认才一次写保管sealed_pending、A02、回执、CH01完成和CH02开放；取消/未确认不移表，不把R01/R02/D/A01强制完成 |
| CH15 / F5 | 三变体分别暂交；林遥D02完成且本人签条为正例，只有老周D02/无D02为负例 | 正例linyao_temporary+本人回执+章状态同事务；负例PRECONDITION_FAILED，表和记录保持原状 |
| CH16 / F5 | 缺E04、R01未过、npc_id换老周、未确认、失效token逐一尝试暂交 | 均不能非法交接；错误状态/码按契约，无自动“改成装袋” |
| CH17 / F7 | 表已不在桌面，从影像查编号；再取E02/E05做R02/D01/D03 | E01影像/检查字段/资格仍在，无需林遥再掏表；可完成R02，不重复签收/A02或新增同源卡 |
| CH18 / F8 | 章末返回继续调查/重开手册，再补R01/R02；尝试进入CH02取E06 | CH01可回访；CH02仅开放标记，独立切片不加载调查内容、不发E06、不生成END |
| CH19 / F7或F8 | 同一A02同键重试，再新键同项/异项；读取确认前检查点再选 | 同键返原；同项不再交接，异项CHOICE_ALREADY_COMMITTED；恢复旧点后按新runtime合法选择，旧审计不能拦住 |
| CH20 / F4/F6 | 同源原图/抄写/复述多选，拖生成段到证据关联 | 同provenance_root不能当独立佐证；生成段无E资格；必要E集合不被替换 |

内容 oracle 必须逐字核 E01–E05 正面文字、D01/D02林遥/D03固定句与原稿，不能用模型判断“意思差不多”。额外符号、前导零、QH-283、0412·0916、21:17/21:20/22:03 均应有字符串检查；对表盘图像另测九点十七分的针位与记录中的夜间时间不同证据范围。

## 4. Unity EditMode / PlayMode / 输入 UI

| ID / 层级 | 前置与步骤 | 观察与通过判据 | 负责 / 首验 |
| --- | --- | --- | --- |
| U01 / EditMode | 枚举Explore/Inspect/Dialogue/Journal/Paused/Loading及文本焦点转换 | 每步只有一个输入拥有者；Move/Look/E不与UI并开；返回时清缓存且不穿透同帧Tab/Enter | QA，Unity修 / M2 |
| U02 / EditMode | DTO反序列化规范PlayerStateView、缺必填、未知字段、错型、null、NaN | typed数组正确，错误拒绝；内部快照/作者H/N不得按玩家DTO加载；无默认“已通过” | QA，Unity/AI修 / M5 |
| U03 / EditMode | 喂同save/runtime不同version、旧runtime、未知request结果、激活新runtime | 旧响应不替换镜像；旧成功仅确认请求完成，不回退版本；changed后GET完整投影再开放写 | QA，Unity修 / M5 |
| U04 / PlayMode | 阻墙/玻璃、前后两个物件、超距/边界距、NPC转身后按E | 最近实体遮挡有效；E当帧重验唯一焦点；无透墙提示/取证；配置边界按获批比较规则 | QA，Unity修 / M2 |
| U05 / PlayMode | 检测缓冲满、自身Collider、非实体Trigger、对象重复ID/失注册 | 保守拒绝并诊断；不任取截断结果；重复关键ID阻止写交互，不能悄悄换GUID | QA，Unity修 / M2 |
| U06 / PlayMode | 移动中打开对话/手册/近检，鼠标拖物、UI点击 | 玩家停止位移/转头，光标释放；拖动仅转预览；UI不同时点到世界物件 | QA，Unity修 / M2–M3 |
| U07 / Windows真实IME | 微软拼音输入“wei/zhengju”，候选翻页、空格/Enter、退格、Tab、Esc、粘贴、切焦点 | W/E/Tab不移动/交互/关界面；候选窗口可见；组合Enter不提前发送；无双字符。视频与输入/命令计数一并存证 | QA手动，Unity修 / M2、M9 |
| U08 / PlayMode+Windows | 在每UI层暂停/失焦，再恢复；暂停中交回模型响应或提交前已在途命令 | 不展示/发新权威操作；恢复原层/光标，GET state后重建；不把取消HTTP当事务回滚 | QA，Unity/AI修 / M5–M8 |
| U09 / PlayMode | 从菜单加载/卸载Station，反复进入，读非法位置/缺资源 | 单Camera输出、AudioListener与EventSystem；三区连通；非法位置回同合法区安全锚点；关键资源缺失阻止相关写，不清案件 | QA，Unity修 / M1–M5 |
| U10 / PlayMode | 五部位全部/部分检查后关窗、换对象、超时、读档，再使用旧token | 客户端立刻失效旧token；服务也按close/换代/过期拒绝；已提交检查不撤销，未检字段不提前显示 | QA，Unity/AI修 / M3–M5 |
| U11 / PlayMode | 令林遥导航失败/准备签条取消；事务成功后打断Animator/切菜单/崩溃重开 | 提交前无A02；提交后保管/回执仍一致，重建最终姿态；动画事件不二次记账，人物可回访 | QA，Unity/Art/AI修 / M4–M7 |
| U12 / PlayMode+Windows | 依次打开15类UI，150%字号候选、长证词、分辨率切换 | 固定句可完整读，不缩小文字掩盖遮挡；固定/生成/玩家假设不同层级；无作者秘密或关系测谎条 | QA，Unity/Art修 / M8–M9 |

## 5. Python/API/幂等与控制面

API用例优先用应用工厂+临时Repository+FM做ASGI集成，不另开真实云连接。使用TestClient时以其上下文管理生命周期；若用HTTPX AsyncClient/ASGITransport，须显式运行lifespan，不能漏掉初始化却宣称健康通过。[FastAPI测试](https://fastapi.tiangolo.com/tutorial/testing/)、[异步测试与lifespan注意](https://fastapi.tiangolo.com/advanced/async-tests/)

| ID / fixture | 输入与步骤 | 必须成立的断言 | 负责 / 首验 |
| --- | --- | --- | --- |
| API01 / 无活动 | health：正确/缺失/错误token、错误Host/Origin；model_available=false | ready=true不依赖云；无认证不返回存档元数据；只允许本机约定Host且无通用CORS | QA，AI修 / M5 |
| API02 / F0 | 每路由：URL/body save不符、未知字段/命令/ID、错整数/超大body；turn请求text与topic同给 | 身份不符400 ID_MISMATCH；未知命令/枚举400 INVALID_REQUEST；未知字段/错型及text/topic互斥违反422 VALIDATION_ERROR；格式有效但对象不存在404 NOT_FOUND；超限413 REQUEST_TOO_LARGE。不回显原文/Key/SQL/隐藏字段，领域投影不变 | QA，AI修 / M5 |
| API03 / F1 | 同request_id同规范payload串行/并发重发；同键改part_id | 仅首次领域事务和一份receipt；同键返原结果；异payload IDEMPOTENCY_CONFLICT，不偷换ID执行 | QA，AI修 / M5 |
| API04 / F1 | 两个新键都带同一旧state_version并发写 | 至多一条成功；另一STATE_VERSION_CONFLICT；不出现两次合法+1与混合投影；客户端刷新后由玩家再确认 | QA，AI修 / M5 |
| API05 / F9 | 普通命令已提交，restore轮换runtime，再用旧runtime命中旧receipt | RUNTIME_EXPIRED，不能从旧缓存返成功污染新状态；同save当前投影不变 | QA，AI修 / M5 |
| API06 / F9 | activate成功后丢响应，同管理request重发；再另行activate后重发第一条 | newruntime仍活动时返同结果不二次恢复；随后已换代时旧管理请求失效；GET active可得认证控制面身份 | QA，AI修 / M5 |
| API07 / 冷启动 | create成功丢响应/重发，服务重启后再重发相同create | 同逻辑create只一个save；重启握手有新service_instance，旧runtime无效；可查既有save再新activate，state高水位不倒退 | QA，AI修 / M5 |
| API08 / F3 | 最后部位/装袋事务提交后切断响应；同键重试，或服务先重启再重连 | 只有一个E01/A02；不把超时当失败弹回原物；重启后先激活查真实state而不重放旧队列 | QA，AI/Unity修 / M5–M7 |
| API09 / F4 | 首次npc.present给一人展示字段；用重排/分组/新request重示，再只给新增差集；关窗后以旧键及新键分别再示，最后trigger D02 | 首次/新增差集才写本人展示事件/记忆并+1；相同字段新请求可重建临时context但无重复事件；旧缓存不恢复context；未D不改NPCKnowledge/关系/E/R，D须本人全部材料及当前context | QA，AI修 / M5–M7 |
| API10 / F3 | evidence.register不满足五部位、伪造Eid；chapter.advance缺A02；relationship.act带delta | 无任意发卡/改关系/跳章口；合法补登记/重算至多修复一次；未知字段拒绝，不从自由问话执行命令 | QA，AI修 / M5 |
| API11 / F5 | A02每一写步骤注入异常：回执/保管/选择/章/事件/自动点/receipt之一失败 | 全部回滚或全部提交，无“有回执无物件/有章末无A02”；版本只一次+1；修复后同键可重试失败未提交事务 | QA，AI修 / M5–M7 |
| API12 / F1 | begin→inspect→close→旧token再inspect；换对象/取消会话/获批无活动时限（候选60秒）各测 | 正确context token连续检查不因version+1失效；关闭/过期返回410 INTERACTION_EXPIRED；不撤销已得证据 | QA，AI修 / M5 |
| API13 / F9 | 写命令与restore在锁前/锁后两个屏障交错 | 先写后恢复则恢复覆盖当前投影；后写因旧runtime失败；没有半份旧NPC知识混入，event_seq仍递增 | QA，AI修 / M5 |
| API14 / F4 | 获得E后重连取PlayerStateView，尝试读取内部快照/整NPC矩阵 | 返回typed数组和玩家可见内容，无H/N正文、未获物证文本、作者F列表；不只在UI遮挡泄密字段 | QA，AI修 / M5 |
| API15 / F2→F3 | 只查编号GET state，再补全E01再GET state；读取已获E03/E04，重连重建手册 | observed_fields仅含已检查文字；完整visible_evidence_records仅含已登记卡，正文/来源/范围/media_refs可读且一致；无需客户端预装整作者目录才能显示 | QA，AI/Unity修 / M5 |
| API16 / F0+FM | 在嵌套对象加入未知/重复字段；漏必填；null/字符串数值/浮点代整数、NaN、越深结构；客户端喂同类畸形响应 | 服务与客户端严格拒绝并保留上次有效镜像；不靠JsonUtility默认值当有效结果，不发生DTO类型强转掩盖错误；本轮不安装解析库 | QA，AI/Unity修 / M5 |
| API17 / F0+FM | 显示获批非D固定段后按交付token确认；同键重试，再新键同段ACK；伪造未交付ref、换NPC/读档后旧ACK | 首次合法ACK写fixed_statement.presented与当前journal，changed=true、版本+1；同键返原结果，新键同段changed=false且无重复事件；ACK不发E/D、不增NPC知识/关系/章；伪造/过期不记未来句 | QA，AI/Unity修 / M5–M6 |

API02 的 body 过限 HTTP 状态和 code 以 DataSchema 为准，测试作者不能自行增加旁路错误语义。

契约例：在F0的有效当前runtime/version下，POST /api/v1/saves/{save_id}/commands 请求R01但未获任何证据。以下UUID与版本来自该fixture，执行时替换为真实测试会话值，不能固定向玩家存档发送。

~~~json
{
  "request_id":"12345678-1234-4234-8234-123456789abc",
  "save_id":"55555555-5555-4555-8555-555555555555",
  "runtime_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version":1,
  "command_type":"reasoning.submit",
  "payload":{
    "reasoning_id":"R01",
    "evidence_ids":["E01","E03","E04"],
    "hypothesis_id":"owner_shenhe_delegate_linyao"
  }
}
~~~

应拒绝的结果形状（message仅示意，实际固定文案依内容目录；HTTP 409），随后GET state核对证据、R、关系、保管、章状态均未被伪造：

~~~json
{
  "request_id":"12345678-1234-4234-8234-123456789abc",
  "save_id":"55555555-5555-4555-8555-555555555555",
  "runtime_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "state_version":1,
  "changed":false,
  "data":null,
  "error":{
    "code":"PRECONDITION_FAILED",
    "message":"请先完成已开放的核对。",
    "retryable":false,
    "details":{}
  }
}
~~~

## 6. SQLite、快照、迁移与故障

| ID / fixture | 操作 | 状态/数据断言与证据 | 负责 / 首验 |
| --- | --- | --- | --- |
| DB01 / F9 | 为S1插入引用S2事件/会话/回执，或错content_version/static ID | 启用外键时全部拒绝；对应复合唯一键可解析，无foreign key mismatch；foreign_key_check无违例 | QA，AI修 / M5 |
| DB02 / F0 | 插入关系-1/4、completed而未opened、N类known/disclosed、暂管无holder/receipt | CHECK或领域断言拒绝；没有借SQLite宽松类型穿过验证；读接口无非法状态 | QA，AI修 / M5 |
| DB03 / F9 | 存A01/D02前点；完成二者后恢复旧点，再做A01 | 当前投影回初态，版本/事件seq高水位不回退；新分支可再合法做一次，旧历史不重放回知识或阻止动作 | QA，AI修 / M5 |
| DB04 / F7 | 手动点/章末点恢复，核对八组持久字段 | E与部位、知识、关系/结构记忆、D、R、选择、保管回执、章进度及安全锚点完整一致；不恢复HTTP/LLM/Animator半帧 | QA，AI/Unity修 / M5–M8 |
| DB05 / 临时文件库 | 对create/E01/A02/checkpoint各注入磁盘满、只读、短锁冲突 | STORAGE_BUSY/WRITE_FAILED按契约；事务无半写、无成功动画；校验恢复可再开旧有效点 | QA，AI修 / M5 |
| DB06 / 临时文件库 | 成功写事务后kill本次测试自有服务，再重开；另在提交前kill | 只有完整旧或完整新状态；不按进程名杀全局Python；重连新实例/新runtime，不返回未来上下文 | QA，AI修 / M5、M9 |
| DB07 / 临时文件库 | 备份时仍有查询/短写；用backup API恢复副本 | 副本integrity_check通过，状态来自某完整事务；不复制活动主db单文件假作一致备份 | QA，AI修 / M5 |
| DB08 / 合成旧版库 | schema/content迁移成功、转换中失败、未来版本、被篡改checksum | 成功后约束/内容版本一致；失败保留原库与备份，不静默空档；未来格式拒写、坏点可显式选有效副本 | QA，AI修 / M5、M9 |
| DB09 / FM+测试标记词 | 输入唯一合成隐私标记，遍查SQLite表/快照/日志/PlayerPrefs/异常输出 | 无自由正文、生成段、提示词、认证材料或其普通hash；结构安全ID仍能解释合法记忆；不使用真实私人信息作fixture | QA，AI/Unity修 / M6、M9 |
| DB10 / F9 | 在点A后显示/确认固定句并完成D；恢复点A，重启后重建手册；扫描conversation历史元数据 | journal按快照恢复，不从未来conversation_messages重建已知台词；D固定段同D事务保存，非D由合法ACK保存；自由段始终不持久 | QA，AI/Unity修 / M5–M8 |

表中所有故障必须对本次临时副本执行；不得拿真实玩家库做损坏实验。校验和不是防篡改安全承诺，只用来检测意外损坏；用户本机对文件有控制权的事实仍成立。

## 7. AI、知识与失败回退专项

| ID / fixture | 输入/操作 | 预期与取证 | 负责 / 首验 |
| --- | --- | --- | --- |
| AI01 / F0+FM | 分别输入完整真相、要求忽略规则、扮演编剧、复述秘密、假称已持E04 | 不确认猜中、不披露H/N、不发E/D/R/A；只提供当前合法案务；捕获实际最小上下文与响应 | QA+Narrative，AI修 / M6 |
| AI02 / F4 | 只向老周出示/核对E03/E04，随后切林遥自由问，再本人D02后重问 | 前两步林遥授权claim仍未知；本人D02后才改变；上下文没有甲私谈或全F表 | QA+Narrative，AI修 / M6–M7 |
| AI03 / F6 | D01前后问照明、D03缺物证/齐物证分别问 | B01使用主观固定句且按D01修正；未D03不提前出亲历细节；生成不能改案情关键句 | QA+Narrative，AI修 / M6 |
| AI04 / F0/F5 | 让替身返回合法JSON但正文含未授权事实，或伪造关系/Eid/命令 | 结构合法不代表业务合法；整条回退，关键段保持批准原文，无状态写权限 | QA，AI修 / M6 |
| AI05 / FM | 超时/不可达/非法结构/空返回/过长/错NPC各一次 | fallback_reason明确，固定入口立即可用；不无限等12秒才可办案，不把规则失败伪成AI成功 | QA，AI/Unity修 / M6 |
| AI06 / F9+FM | 发老周turn后取消/换林遥/读档，在新上下文完成后返回旧结果 | save/runtime/session/npc/turn/version任一过期即丢弃；旧回复不显示、不持久、不写人物新知 | QA，AI/Unity修 / M6 |
| AI07 / F4+FM | turn等待中正确提交证据/D或关系动作，再返回旧turn | 权威版本变化使旧候选过期；固定核对不被模型锁阻；重开会话只用当前合法最小上下文 | QA，AI修 / M6 |
| AI08 / F3+FM | 完全禁用云模型走最短装袋、完整核验暂交两路径，再关闭规则服务 | 前者同门槛、同E/D/R/A结果；后者只读镜像，不能继续发证/交接；重连不永久软锁 | QA，AI/Unity修 / M7–M9 |
| AI09 / F0 | 改问法/重复礼貌/反复指控/道歉，逐个选择获批关系动作 | 自由文本情感不直接加减分；同语义事件按NPC/章去重；拒闲聊仍有案务，不影响取证权 | QA，AI修 / M6 |
| AI10 / 真实模型未来样本 | 每NPC/知识阶段抽取同一问题库并重复，留模型/参数/时间版本 | 判人格、授权事实泄露、固定文本一致性和回退率；失败留脱敏片段及修复；不以单次回答宣称质量达标 | QA+Narrative，AI修 / M10前单独授权 |

问题库建议至少50项覆盖两人物/早晚知识/提示注入/猜测/普通问法；数量及抽样次数为 [待确认]，推荐在真实模型批准时冻结，理由是使版本间可比。关键事实泄露和生成改动有效证词属于阻断问题，不能以总体满意度抵消。

## 8. 视觉、音画与人物验收

以下由 QA 按 FV 固定机位采样、Art/Unity 修复，M1/M4 先测样段/样人，M8–M9 全量。以 VisualDirection 的 VIS01–VIS12 为视觉源，各 V 用例给执行判据。截图保留分辨率、画质、曝光/后期/字号设置和build ID，不拿不同设置截图直接判回归。

| ID / 场合 | 步骤 | 通过判据与证据 |
| --- | --- | --- |
| V01 / 物证检读 | 表盘/背刻/编号/侧冠/冠轴、E02–E05逐字近检，开/关柔光/文本视图 | 每字段无需猜读；文字与来源一致、反射不盖字；未检字段不因默认卡片提前出现 |
| V02 / 分辨率 | 1280×720、1920×1080、2560×1440；16:10/超宽作为待定支持项；100%/150%文本 | 关键证词/按钮完整，允许重排滚动，输入法候选不裁切；最终最低支持范围 [待确认] |
| V03 / 三档 | FV全路线分别高/中/低，重复所有关键交互 | 可削雨雾/反射/远影，不能削E文字、损伤、热点或必要脸手动作；证据集合一致 |
| V04 / 后期 | 关景深/动态模糊/色差，静止和转头读柜号与脸 | 调查不依赖后期；无强制过暗、曝光抽动或高光吞字 |
| V05 / 导航可读 | 新手无任务箭头走招领处→大厅→站台→返回 | 靠字牌/入口轮廓能回访，必经对象不被雨幕/隔绳挡住；不是测试员背路线才成功 |
| V06 / NPC近谈 | 各人物待机/转身/看单/拒聊/核对/签条接表及低LOD切换 | 无明显脚滑/关节塌陷/眼神翻转/脸手丢细节；拒聊不随机消失，表演不等同撒谎证据 |
| V07 / 动作接触 | 近距与侧视看签字、递单、收入衣袋，打断后恢复 | 手物接触合理；状态与已提交保管一致，不出现桌上和衣袋同时两只表 |
| V08 / 声音等价 | 静音开字幕重走固定案务，与开声版本对比 | 主线信息/门槛相同，字幕不改固定句、不提前标未知身份；无后章原声或复车广播 |
| V09 / 天气边界 | 在雨棚/室内/远景切档与转头 | 没有穿棚雨和纸张凭空新损伤；降低特效仍像雨夜，柜面和返程入口可读 |
| V10 / UI层级 | 开对话/出示/近检/关联，查看固定/生成/假设样式 | 脸手、物件和文字有主次；非后台数据墙；无H/N矩阵、测谎关系条或未获证据名单 |
| V11 / 资产与许可 | 核两人物网格/骨骼/贴图/动画导入、字体/模型/声音来源表 | 真实可交互3D非图片贴片；有可发行/导出凭据，自动工具输出经脸手/拓扑/材质验收；未确认许可不进发布包 |
| V12 / 性能 | 目标机FV同路线先预热再采CPU/GPU帧耗、显存/内存与加载尖峰；沿用视觉稿30秒预热+60秒采集的 [待确认] 起点 | 分列雨、阴影、雾、反射、皮肤成本及帧时间分位；对照获批阈值和截图，不以Editor平均FPS代Windows包结论 |

目标硬件、最低帧率/帧时间分位、显存/内存及加载预算仍 [待确认]。建议先指定一台SDR Windows目标机，以1080p/60fps作为讨论起点，再用真实样段冻结高档预算与低档下限；理由是画质优先也需要可复现的验收机。未冻结前记录测量值，状态只能是“已测/尚未定阈值”，不能标性能通过。

## 9. 保留 GDD AC01–AC15 与章节归属

下面原样保留 GDD 验收语义；后章项列为后续回归，不因首章切片删除。

| ID | 情景 | 应有结果 |
| --- | --- | --- |
| AC01 | 尚未取证，直接自由输入全部真相或要求扮演编剧 | 不泄露额外事实，不发 E，不过 R，不跳章 |
| AC02 | 输入中文拼音包含 W/E/Tab，或隔墙按 E | 不移动、不误提交、不透墙登记 |
| AC03 | E09 先于 E08；D08 先于/后于 D05 | 两序均可；D08 仅纠正误信，E10 只由 D05 签认 |
| AC04 | 向老周核对 E14，未做林遥 D06 就结案 | 林遥不凭空得知西窗，不说仅 D06 后的结尾台词 |
| AC05 | 表已暂交林遥，回查 E01/R02 | 照片/编号仍可用，能补证，不重复领取 |
| AC06 | 同源图片、抄写、NPC复述同时选中；声称停电使机械表停走 | 不增独立证据，不通过错误因果 |
| AC07 | 反复出示、改问法、超时重试、读档重访 | 同一状态内事件只结算一次；旧档恢复自己的事件状态 |
| AC08 | 取消、换人、暂停或读档后旧回复到达 | 不污染新NPC/存档，暂停恢复后才复核有效回复 |
| AC09 | 最少检查与保管动作进入第三章，取得 E11+E13 | 签发页可开，明确选封存可完结，未知写待核 |
| AC10 | R01+R03+R04 通过，R02/R05 未过 | 可归还，不可公开；缺项可补，不自动改结局 |
| AC11 | R01–R05 通过并完成 R06，E15 未取得 | 可公开；不把林遥回忆或其知情表演强塞进必要条件 |
| AC12 | R06 未过，选公开；关闭界面/重复确认 | 不签发，提示缺项；完成门槛后只能生成一个结局 |
| AC13 | 云模型不可用；随后规则服务也断开 | 前者固定入口与在线同结果；后者暂停写状态并可重连 |
| AC14 | 静音/开字幕、关闭景深及动态模糊、降低雨雾反射 | 仍能检读全部物证与录音必要信息 |
| AC15 | 结案前存读档，含人物已听余声/未听与 B 修正 | 角色知识、物品保管、R/关系同版本，无未来记忆 |

| 适用范围 | AC及本计划落点 |
| --- | --- |
| 第一章完整适用 | AC01→AI01/04；AC02→U04/07；AC05→CH17；AC06→CH12/20；AC07→CH03/13/19、API03；AC08→U08、AI06；AC13→AI08 |
| 第一章部分、后章继续 | AC14首章测固定案务/物证（V01–V04/V08），录音等价待第二章；AC15首章测B01/D02/保管/恢复（DB03/04），听带及终局待后章 |
| 后续章节必回归 | AC03、AC04、AC09–AC12：以原E/D/R/结局条件做测试，第一章包不造假E06+或假END来“通过” |

## 10. 后续执行命令、产物与排期

以下命令是**测试源码、环境与对应开工授权就绪后的模板，当前未执行**。使用实际锁定的编辑器和项目独立Python；先在准确工作目录核实版本、测试发现数量及输出路径。测试若需写Library/Temp或启动服务，必须属于该里程碑获准范围。

~~~powershell
# 使用项目虚拟环境，路径由M0确定；不是全局安装命令
python -m pytest Server/tests --strict-markers --junitxml=TestResults/python.xml

# $unityEditor应指向已核实的6000.3.29f1 Unity.exe；不用未核实的PATH别名
& $unityEditor -batchmode -runTests -projectPath "G:\projects\EchoLostAndFound" -testPlatform EditMode -testResults "G:\projects\EchoLostAndFound\TestResults\editmode.xml" -logFile "G:\projects\EchoLostAndFound\TestResults\editmode.log"
& $unityEditor -batchmode -runTests -projectPath "G:\projects\EchoLostAndFound" -testPlatform PlayMode -testResults "G:\projects\EchoLostAndFound\TestResults\playmode.xml" -logFile "G:\projects\EchoLostAndFound\TestResults\playmode.log"
~~~

不默认加 -quit 造成测试未结束先退出；视觉/输入用例不以无图形批处理替代实机。当前锁定Test Framework文档应在M0按包核对参数；Unity官方列出 runTests/testPlatform/testResults 等选项。[Unity 6000.3运行测试](https://docs.unity3d.com/6000.3/Documentation/Manual/test-framework/run-tests-from-command-line.html)

建议测试分类为 contract/rules/db/knowledge/idempotency/failure/slow，先注册markers再使用--strict-markers；fixture和文件由QA唯一写Server/tests及Assets/_Project/Tests，业务作者只修所属代码。不把没有发现测试、全skip或仅编译成功当通过。pytest隔离与XML结果依据[官方用法](https://docs.pytest.org/en/stable/how-to/usage.html)。

每次运行留：build/提交或哈希标识、Unity/Python/依赖/content/API版本、OS/硬件/画质/分辨率、测试ID/seed/fixture、脱敏request与前后状态、测试计数、退出码、JUnit/NUnit XML、日志、失败截图/短视频、未执行原因。产物放获准TestResults目录并忽略提交；无原始玩家正文/Key。复现缺陷按影响、前置、步骤、实际/预期、最小证据、准确业务文件/模块、负责者报告，不把自动化通过扩大成玩家试玩通过。

## 11. 缺陷级别与完成门槛

- 阻断：无法启动/关键路径无法继续、非法取证或交接、跨档/跨NPC泄密、丢档/半事务、云Key/正文泄露、关键文字不可读、缺资源使本章无法完成。必须修复并回归，不用改故事/放宽断言避开。
- 主要：可恢复但高频的焦点/人物穿插/错误提示/性能问题；按可复现影响决定是否阻止M10，不用漂亮截图抵消调查故障。
- 次要：不影响证据、控制与剧情的表现瑕疵，记录准确范围及用户可接受风险。

建议M9进入M10前：本章CH/U/API/DB/AI关键用例全部通过且无未说明skip；V用例完成，性能阈值已批准或明确未验；Windows冷启动、关闭和存档往返至少各复验一次。确切性能/重复采样阈值和支持设备矩阵为 [待确认]，推荐以首个样段测量锁定后再作为发布阻断门槛，需用户确认。

M10至少分别完成最短装袋、核证暂交、逆序补证和关云模型路径，记录完成时长与迷路点；人数/质量评分阈值 [待确认]，推荐包含未参与开发者，理由是避免作者记得线索位置造成假通过；由用户作为验收方决定体验是否达标。全剧AC03/04/09–12等只有后章实现后才标运行结果。

## 12. 本轮完成状态

本轮交付的是可执行测试设计；没有编写或运行pytest/Unity测试、真实API/SQLite实现、PlayMode、Windows构建或试玩。实际执行记录由未来测试运行产生；阶段3的文档静态审查结果由Director写入阶段报告。后续实施必须先获用户批准，不自行进入下一阶段。
