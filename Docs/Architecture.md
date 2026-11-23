# 整体技术架构

阶段 3，2026-11-21。唯一主笔：AI Engineer；整合与验收：Game Director。本文是待用户验收的设计，未实现后端、规则、数据库或模型接入。

以本轮任务的画面、沉浸、玩法、AI、维护性优先级为准；故事依据 [GDD](GDD.md)、[StoryBible](StoryBible.md)及[来源记录](Sources/README.md)。客户端见 [TechnicalDesign](TechnicalDesign.md)，所有 API、字段与枚举以 [DataSchema](DataSchema.md)为唯一规范；剧情映射见 [Chapter01ImplementationMap](Chapter01ImplementationMap.md)，验证见 [TestPlan](TestPlan.md)，实施顺序见 [VerticalSlicePlan](VerticalSlicePlan.md)。不修改故事或工程依赖。

## 1. 实际起点与设计边界

- Unity 工程记录 6000.3.29f1、HDRP 17.3.0；Input System 1.20.1、Cinemachine 3.1.7。版本以工程清单和锁文件为准。
- Server/app、Server/tests 为占位目录，requirements.txt 只有说明；不存在已实现的游戏 API、数据库或规则引擎。本机某解释器能导入或列出 FastAPI 等分发包不等于项目已锁依赖，Python/打包工具版本仍须 M0 确认。
- 本轮只写架构与数据文档，不安装 Python/Package、不调用模型、不生成数据库、代码、Scene、Prefab 或正式资产。
- 单人本机架构优先保障可恢复交接与无模型可通关。单机玩家控制自己的客户端和文件；本方案防错误状态与意外跨会话，不宣称反篡改或多人服务器级防作弊。

## 2. 部署方案与推荐

| 方案 | 收益 | 成本及适用范围 | 结论 |
| --- | --- | --- | --- |
| Unity + 随游戏启动的本机 FastAPI + 本机 SQLite + 可替换云 LLM | 固定规则不依赖互联网；状态只有一个写入者；沿用 Python 方向，便于规则测试 | Windows 发布需携带受控 Python 运行时和服务进程；要处理端口、退出与防火墙提示 | 推荐垂直切片方案，打包方式 [待确认] |
| Unity + 远端 FastAPI/数据库 + 云 LLM | 集中更新与运营，客户端不持有云密钥 | 持续服务成本、联网/账户/隐私与断线设计，已超出首章必要范围 | 保留后续演进，不在首章引入 |
| Unity 内置 C# 规则 + Python 仅做 AI | 启动组件较少，规则可直接离线 | 两种语言迁移与故事规则分叉；违背本轮已明确 FastAPI 权威状态职责 | 不采用，不复制权威规则到客户端 |
| Unity 内嵌解释器/IPC | 无监听端口的可能收益 | Unity 构建、线程和解释器生命周期耦合，需额外桥接验证 | 无已测收益，不增加此复杂度 |

推荐本地服务单进程、单 worker、一个规则写队列。HTTP 足够处理当前低频调查动作，不引入 WebSocket、Redis、消息队列、向量库、分布式微服务或多 NPC 自主社会模拟。云 LLM 被替换或关闭时，规则与固定话题保持同结果。

### 2.1 本机启动、连接与关闭

1. Launcher/Unity 启动前确认用户数据目录可写，读取非敏感配置和版本；云凭据只由服务端环境变量获取。发布时推荐打包独立运行时，避免依赖用户全局 Python，[待确认] 具体封装工具及许可证。
2. 创建一次性的受限继承管道和本机随机令牌。服务绑定 127.0.0.1 的操作系统分配端口，不能监听 0.0.0.0。令牌用于防其他程序误调用，不是云 API Key，也不是本地用户安全边界。
3. 子进程以隐藏窗口启动；实际启动器未来使用 Windows 合适的隐藏进程选项，本轮不启动。就绪消息通过继承管道回传端口、服务实例 ID、API/content/schema 版本；令牌不放命令行、日志或 Unity 资源。
4. Unity 带令牌请求 /api/v1/health，核对服务实例与版本后才启用新建/激活存档。禁止因端口被占用就连接一个未验证进程；失败提供重试和退出。
5. 同一服务可管理多个存档槽，但全游戏只有一个活动 runtime。重复启动不得共享同一可写数据库；文件锁/实例握手明确拒绝第二个写服务。
6. 正常退出停止接收新指令，完成短事务，取消模型任务，关闭 SQLite，再退出自有子进程。只可关闭本次启动并验证实例归属的进程；不按进程名批量终止 Python。
7. 服务异常退出：UI 禁止权威动作，可查最后镜像。重启后激活最近已提交状态，生成新 runtime_id 和更高 state_version；不能重放旧队列。超时未确认结果通过查询与同键重试解决，不猜测操作成功。

未认证来源/Origin/Host 不合预期时拒绝；不开放通用 CORS；开发文档与调试端点发布默认关闭。HTTP 仅限 loopback，外部模型使用 HTTPS；远程部署需另做认证/TLS，不沿用本机临时令牌。令牌与云 Key 均不写入持久存档。

## 3. 模块与数据流

~~~mermaid
flowchart LR
    U["Unity：输入/场景/近检/NPC动画/UI"] --> G["CommandGateway：版本与幂等"]
    G --> A["FastAPI：身份与结构校验"]
    A --> R["RuleService：唯一剧情裁决"]
    R --> S["SQLite：事务、当前投影、检查点"]
    R --> P["玩家可见 StateView"]
    P --> U
    A --> C["ConversationCoordinator"]
    C --> K["ContextBuilder：按人物最小授权"]
    K --> M["ModelAdapter：可替换云服务"]
    M --> V["ResponseValidator：非关键表达"]
    V --> C
    R --> F["固定证词/话题文本"]
    F --> C
    C --> U
~~~

| 模块 | 输入与职责 | 输出及依赖边界 |
| --- | --- | --- |
| ContentCatalog | 读取经批准 F/E/D/R/A、文案、位置和行为规则的版本化内容 | 只读内容；完整作者事实只供规则与作者工具，不直接返回 Unity/LLM |
| API Boundary | 路由、令牌、严格 DTO、请求大小、版本及错误映射 | 只允许定义的命令，不暴露任意状态写接口 |
| RuleService | 读取当前投影，校验命令前置，计算结果 | 一个短数据库事务内写事件、投影、版本与幂等结果 |
| SaveRepository | 命名检查点、快照、恢复、校验和与迁移 | 不储存未决模型任务；不把旧 snapshot 的 state_version 覆盖运行高水位 |
| NPCStateService | 按 NPC 的知识、披露、关系、结构事件记忆 | 不依赖全局“玩家已知”等同人物已知 |
| ConversationCoordinator | 会话/轮次、取消、超时、模型调用、固定回退 | 无修改 E/R/关系/章节/保管的权限 |
| ContextBuilder | 单 NPC 的 Profile、当前可说片段、当前话题、已核事件 | 不发送 H/N 的未授权正文，不发送完整 F01–F12 或其他 NPC 私谈 |
| ResponseValidator | 结构/长度/来源/秘密/人称/角色与时效检查 | 无法确认就整体回退，不把生成段当证词 |
| ModelAdapter | 配置化 endpoint、model 名称、认证与超时 | 供应商可替换；不向模型暴露任意执行游戏命令的工具 |
| StateView Projector | 只投影玩家已见证据、允许话题、当前目标、关系表演状态 | 内部知识分类和隐瞒事实不可从调试字段泄露 |
| Unity Replica | 同 runtime 且不倒退的状态镜像、场景/动画呈现 | 不能本地授权物证/关系/推理；服务失联暂停写入 |

本轮规划目录仍沿用 Server/app；未来内部可按 api/domain/content/storage/conversation 分模块，具体文件清单在 M5 分派时确定，不提前创建重复 Server 工程。数据库首先用标准 sqlite3 与显式 Repository；若后续评估 ORM，须说明迁移收益，不为十六模型机械引入复杂 ORM 框架。

## 4. 权威状态与命令事务

~~~mermaid
sequenceDiagram
    participant U as Unity
    participant A as API
    participant R as RuleService
    participant D as SQLite
    U->>A: 身份、版本、request_id、命令
    A->>R: 严格结构及白名单校验
    R->>D: BEGIN IMMEDIATE
    R->>D: 核对runtime、幂等记录、state_version
    R->>R: 读取前置并计算领域事件
    R->>D: 写投影+事件+版本+幂等结果
    D-->>R: COMMIT
    R-->>U: 提交结果与固定呈现指令
    U->>A: GET state
    A-->>U: PlayerStateView
    U->>U: 播放动作/更新物件与UI
~~~

事务中不访问模型或等动画。检查部位完成、证据合成、D 本人核对与 A02 保管均由内容规则推导。A02 暂交一次事务内验证 E01、R01、林遥本人 D02、用户明确确认签条、物品当前保管，写入暂收回执/保管变更/A02/第一章完成与 CH02 开放标志。表现层动画在提交后播放；中断后按保管状态复位，不因一次 Animation Event 丢失而永久卡住，也不重复签字记账。

角色“签署暂收条”由玩家明确选择、固定台词和本人动作呈现；服务器记录的是该已批准交互的确认，不把任意客户端 receipt_confirmed 当真实外部签名。单机并不验证物理人真实在场；客户端检测是体验约束，服务做前置及角色匹配。

E01 五部位逐项记录，全部满足才合成；重复观察不再发卡。E03 需要已见编号并查同号单据；E04 可按已知 QH-283 直接查册，不强制先取得 E03。E05 的具体交互按第一章映射和来源索引执行。R01/R02 可不完成即装袋章末；CH02 只记录开放标志并展示切片交接，不开发其调查内容。

### 4.1 并发、幂等与读档屏障

- 一个活动存档命令在途，UI 不并发发多个写动作；服务仍以事务和版本检查处理重复/并发错误，不能依赖按钮变灰。
- runtime_id 每次激活、恢复、服务重启重建时轮换。state_version 是 save 的单调高水位；从旧检查点恢复后也是当前高水位 +1，不取旧值。
- 每条已完成指令与 request_id 同事务缓存。相同 runtime/键/规范化 payload 返回原结果；同键不同 payload 冲突；已经恢复的旧 runtime 请求即使键命中也拒绝。
- 恢复屏障先停止接单并清除会话输出，短事务拿写锁，核对旧 runtime/版本，恢复投影、更新 runtime/版本、记录恢复事件和幂等结果；解除屏障。旧指令若先提交，恢复覆盖其投影；若后拿到锁，因 runtime 失效而拒绝。
- 模型任务捕获 save/runtime/conversation/turn/state_version。完成时任何一项不合就丢弃；取消本身不撤销已经提交的 D、证据或选择。
- 超时不代表失败，也不保证服务器取消。客户端同键重试或查询 authoritative state；旧成功响应不能覆盖较新镜像。

## 5. 知识隔离与 AI 工作流

| 分类 | 存储与用法 | 生成上下文 |
| --- | --- | --- |
| K | 角色开场亲历、已可说片段，细分陈述而非整 F 行 | 仅本轮话题相关片段 |
| H | 作者知道角色已知但未披露，披露条件属于规则 | 未解锁不发送秘密正文；只给中性的回避方式 |
| B | 主观误信，必须有归属与修正条件 | 固定主观措辞；修正后仅可作为“以前以为” |
| L | 角色经指定动作真正看到/听到后获得 | 只在本人对应 D 后更新，记录来源与版本 |
| N | 本作无合法获得途径 | 不发送，不让玩家转述提升权限 |

Profile 只含获批身份、语气、目标和可演出态度，不将“秘密”字段整个塞进提示。Knowledge State 与 Disclosure State 按最小 claim 切片。事件记忆保存已实施行为/本人看过的证据和固定证词；短期自由文本只在当前会话内存，换人、读档、取消或退出即清空。自由文本摘要亦不持久化，防止隐私以摘要形式绕开边界。明确承诺需匹配获批 action，模型记忆候选不能直接成为长期事实。

对话处理：

1. 结构和长度检查，验证存档/运行/会话/当前状态；给输入当作不可信内容，不当指令。
2. 意图识别只看输入及当前合法话题 ID；识别器不持有完整剧情。输出只能是白名单 topic_id/unknown，不能输出新 evidence_id、命令或关系增量。
3. 将话题映射到规则允许的固定片段。需要 E/D 时返回“出示/核对”动作供玩家明确选择，不从一句自然语言直接执行取证、D 或签交接。
4. 生成器接收已归一化话题与本 NPC 最小允许摘要，不直接照搬包含玩家猜测秘密的自由输入；上下文不混其他 NPC 私谈。有效证词、音轨、文书逐句固定展示，AI 仅提供非关键衔接。
5. 验证后返回，不把文本直接入证据。任何无法判定安全性、角色漂移、事实冲突或错误结构整条回退到当前获批固定话题。
6. 同样话题可有表达差异，记得自己被出示过什么；表示迟疑不等于撒谎，主动表演不是新增信息。

提示词与模型校验不能数学证明自然语言永不幻觉。防护依靠不提供秘密正文、限制生成用途、关键文本固定、疑似案情断言拒绝、对抗测试及可用回退；上线前仍须实测。无法安全处理的自由问题不给确认/否认答案，也不以重复玩家写入的名字和时间暗示猜中。

### 5.1 两名 NPC 的第一章隔离

- 老周：D01 对时点修正 B01；D02 核对签单；D03 仅 E01+E05 的拾取/卡点。不能因看 E02 说出后章改簿与母女私谈。
- 林遥：只有本人参与 D02 并看 E03/E04 才知道本轮核实的编号与领取授权。玩家 R01 通过、与老周 D02、全局取得 E04 均不替她增加知识。
- 对话状态的“拒闲聊”不阻断案务固定入口。关系由获准行动去重更新，不能因模型判玩家礼貌/攻击而自主扣加分。
- 许澄后章知识规则保留内容架构能力，但本切片不制作许澄正式模型、自由对话或 D04+ 内容。

## 6. AI/规则/磁盘失效

| 失效 | 权威状态 | 玩家路径 |
| --- | --- | --- |
| 供应商不可达、超时、返回非法结构、越界内容 | 无权威变更，既有证据/知识不回退 | 同门槛固定话题继续，用户可关闭 AI |
| 取消/换人后迟到 | 丢弃旧 turn；不保存其自由正文 | 新 NPC 只看到自己的内容 |
| 规则服务断开 | 暂停所有权威动作，不客户端判案 | 查镜像；重连后新 runtime 与全量 state 重建 |
| 磁盘满、锁冲突或写失败 | 事务失败完整回滚，返回明确错误 | 保留未确认 UI，修复存储后同键重试；不得显示已发证或已交表 |
| 坏检查点或版本不兼容 | 不覆盖当前可用数据 | 只读列出最近验证成功检查点，显式恢复；不静默新建空档 |
| 服务/Unity 中断在动画中 | 已提交事务完整存在或完整不存在 | 以 state 显示保管和人物驻点，可重播非权威演出 |

超时和大小数值见 DataSchema，均为本轮建议默认、待切片测量确认，不能视为已达服务质量。

## 7. 持久化、隐私与演进

采用“小规模事件审计 + 当前关系投影 + 不可变检查点”。每次完成事务更新投影并追加足以审计的结构事件，普通读取不重放全历史。命名存档是同一已完成状态的快照，恢复显式记录检查点基线。该复杂度用于防半交接、恢复 NPC 知识和定位重试，不引入通用 CQRS 框架。

SQLite 连接启用外键、短显式事务；应用层单写队列，数据库层仍校验约束。首版建议默认 rollback journal + FULL synchronous，读负载很小无需先启用 WAL；若实测需要 WAL，再做备份/关闭及旁文件方案并冻结版本。[SQLite 事务](https://www.sqlite.org/lang_transaction.html)说明单写约束；[外键文档](https://www.sqlite.org/foreignkeys.html)要求连接级启用约束。

数据库/备份位于用户数据目录，不在安装目录、Assets、项目 Git 或真实 .env 内。推荐 %LOCALAPPDATA%/EchoLostAndFound/Saves/，最终目录与发布身份 [待确认]。不按字符串“复制主 db 文件”备份活动数据库，采用 SQLite backup API 制作一致副本再校验完整性；[官方备份说明](https://www.sqlite.org/backup.html)指出直接外部复制活动库有风险。

自由输入原文、模型生成段、云请求体、认证头、云 Key、系统提示不进持久日志/事件/幂等缓存；仅当前会话内存暂留。诊断持久化 request_id、错误码、耗时、内容版本与不含正文的领域 ID。固定获批证词可通过 content_ref 复现，不需存储所有展示文本。用户开启正文历史功能必须另定同意、删除和保留期，本切片默认关闭。

迁移前一致备份、校验 schema/content/save 版本；失败保留原库并阻止写入。故事内容版本变化不能用模型自动补齐旧知识；需要显式映射与回归。向后续章节仅扩展内容与命令白名单，不改变本章合法证据与结案条件。

## 8. 核验依据与未决项

已浏览的官方技术依据只用于设计，未执行实现验证：

- FastAPI 支持响应模型过滤与校验，用于区分内部作者状态和玩家 DTO；它不替代业务知识权限检查。[Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- 启停资源通过 lifespan 管理；它不是进程监管或事务持久队列。[Lifespan](https://fastapi.tiangolo.com/advanced/events/)
- 配置与密钥从环境读取，不把供应商写死。[Settings](https://fastapi.tiangolo.com/advanced/settings/)
- 显式事务、参数化 SQL、备份行为应按实际锁定 Python 的 sqlite3 文档实现。[Python sqlite3](https://docs.python.org/3/library/sqlite3.html)

| 决定 | 推荐、理由 | 需用户确认 |
| --- | --- | --- |
| Python/依赖与 Windows 打包 [待确认] | 独立受控运行时，固定版本并做最小包验证；不依赖全局解释器 | 支持的 Windows 版本、发行方式、打包工具 |
| 云模型与部署 [待确认] | provider adapter + 默认无模型可通关，不绑供应商 | 服务商、预算、网络/隐私政策与后续真实调用授权 |
| 存档位置/备份数量 [待确认] | 用户本地目录、三自动轮换+手动槽候选，防同盘单副本损坏 | 用户数据位置、保留/删除体验 |
| 输入与服务限值 [待确认] | 使用 DataSchema 建议上限，先测故障与交互时延 | 实测后的发布阈值 |

本轮完成状态仅为架构设计。实际子进程启动、FastAPI 路由、SQLite 事务、模型越权防护、存读档与 Windows 打包全部尚未验证。

## 9. 魔搭模型接入与浏览器部署的后续约束

2026-11-21，依据用户新增的魔搭 AI+ 游戏开发者大赛方向补充。唯一写入者：Game Director。本补充只确定接口边界、差异和后续实施顺序，不启动阶段 4，不安装包、不实现 Provider、不制作 WebGL 包。前八节保留为阶段 3 的 Windows 本机方案；本节增加未来部署适配，不改第一章 E/D/R/A、NPC 知识和存档规则。

核心决定：Windows 第一章继续使用当前 Unity HDRP + 本机 FastAPI；模型调用统一经过 LLMProvider，优先预留 ModelScope API-Inference，并提供 MockAIProvider 和其他 OpenAI 兼容服务适配。未来 Web 客户端连接远端 FastAPI，复用业务契约、知识过滤和规则实现，使用独立兼容渲染方案。不依赖 DGX Spark、指定自有推理 GPU 或需申请专用 GPU 配额的环境；普通 CPU 服务处理规则/SQLite，云端提供模型推理。游戏本身的图形硬件要求仍由画质验收确定。

### 9.1 当前架构与新增要求的差异

本次实际核查：Server/app 和 Server/tests 仍仅 .gitkeep，requirements.txt 仅注释；Assets/_Project 尚无游戏实现。已有成果为策划与技术设计，不存在可据此声称已完成的第一章游戏功能。后续按这些边界首次实现即可，不为“预留”提前建立空框架或迁移模板资源。

| 项目 | 当前已有设计 | 本次明确的扩展边界 |
| --- | --- | --- |
| 模型接口 | 泛化的 ModelAdapter、尚无实现 | LLMProvider 是正式内部调用接口；原 ModelAdapter 职责由适配实现承担，不维护两套重叠抽象 |
| 模型渠道 | 云模型可替换，未选默认渠道 | 优先预留 ModelScope；其他 OpenAI 兼容服务通过配置与能力适配，不写死供应商/模型名 |
| 无模型模式 | 固定话题、关键证词与故障回退 | MockAIProvider 是后续首个实现；无 Key、云不可用仍能走固定案务和调查闭环，不冒充真实自由推理 |
| 运行拓扑 | Windows 隐藏伴随服务、loopback、临时令牌 | Windows 保持；未来 Web 使用 HTTPS 远端服务和按用户/会话授权，浏览器不启动本机 Python |
| 游戏 HTTP API | /api/v1、统一 commands、异步会话与轮询 | 模型渠道不进入 Unity 契约；部署差异集中在连接/认证，字段继续以 DataSchema 为准 |
| 活动存档 | 单机一个活动 runtime、全局单写服务 | 远端共享服务须按认证主体隔离存档与活动 runtime；不能直接暴露单机 /active 和全存档列表 |
| 渲染 | HDRP 17.3.0、Windows 高质量三空间 | HDRP 不支持 WebGL；未来浏览器版另做 URP 展示层验证，当前不切管线 |
| 配额与可用性 | 未固定供应商指标 | 不要求专用 GPU 配额，但云 API 的账户/模型可用性和调用限额仍须接入时确认，不能承诺无限服务 |

### 9.2 最小新增接口与模块

下表是后续准确文件分派的建议落点，本轮没有创建对应源码。Python 位于现有 Server/app 内；目录归 AI Engineer，测试目录另由 QA 唯一负责。

| 接口或模块 | 最小职责 | 明确不承担的职责 |
| --- | --- | --- |
| LLMProvider | 异步 generate(LLMRequest) → LLMResponse；声明 capabilities；释放网络资源 | 不读取/修改 SQLite 权威投影，不发 E、D、R、A 或关系变更 |
| ModelScopeLLMProvider | 魔搭端点、模型 ID、认证与能力配置；复用 OpenAI-compatible HTTP 传输 | 不在 NPC 逻辑中散落魔搭 SDK/专属参数 |
| OpenAICompatibleLLMProvider | 归一化 Chat Completions 风格请求/响应、错误、取消、用量 | 不把“兼容”当 JSON Schema、tool calling、流式等能力全部相同 |
| MockAIProvider | 无网络的确定性结果、获准话题映射/unknown、空衔接或批准的中性衔接 | 不生成隐藏真相，不假装理解所有任意问题，不替代 RuleService |
| ProviderFactory / ProviderSettings | 服务端环境配置选择一个 Provider，校验配置和能力 | 不接受客户端任意 base_url/Key；不自动切到另一付费服务商 |
| ConversationCoordinator | 维持既有会话、上下文白名单、总超时、过期检查、校验和固定回退 | 不因 Provider 失败改变已取得证据、关系或章节 |
| IGameServerConnection | Unity 中提供后端地址、游戏会话认证与就绪状态 | 不接触云模型 Key 或供应商 SDK |
| DesktopCompanionConnection | 未来封装当前计划的 Windows 启停/管道/loopback 握手 | 不进入 Web 编译路径 |
| RemoteWebConnection | 未来读取非敏感站点配置，经 HTTPS 连接已部署服务 | 不用 localhost 假装访问服务器，不启动/终止 Python |

LLMRequest 只含 task（intent 或 bridge）、经筛选的当前话题/上下文、允许话题 ID、输出限制及剩余时间预算。save/runtime/NPC/turn 等追踪信息供协调层检查，不无条件拼成模型提示。任何 Provider 均不接收完整 F01–F12、未开放 H/N 正文或其他 NPC 私谈。

LLMResponse 内部规范区分成功、mock、不可用和错误，带归一化的意图候选/非关键衔接、可选用量及脱敏错误类别。不返回能直接执行的 game commands、evidence grants 或关系 delta。capabilities 明列是否支持结构化输出、取消、用量、流式；能力未核验时按不支持处理。无需为支持更多供应商引入 Agent 编排框架或本地模型权重。

### 9.3 魔搭优先与配置方式

魔搭官方项目的接入示例使用 OpenAI 兼容客户端和 https://api-inference.modelscope.cn/v1/。因此推荐魔搭适配使用同一兼容传输，只把端点、模型 ID、能力和认证配置留在服务端。[魔搭官方接入示例](https://github.com/modelscope/ms-agent/blob/main/docs/zh/Projects/deep-research.md)

| 服务端环境变量建议 | 含义 |
| --- | --- |
| LLM_PROVIDER | mock / modelscope / openai_compatible；开发默认 mock |
| LLM_BASE_URL | 魔搭模式默认上述官方 /v1 地址；其他模式由服务端可信配置指定 |
| LLM_MODEL | 接入时确认可用的准确模型 ID，不把当前示例模型固定为依赖 |
| MODELSCOPE_API_KEY | 魔搭服务端令牌，仅环境变量读取；没有真实值写入本文 |
| LLM_API_KEY | 其他兼容服务端凭据，仅所选适配器读取 |

环境变量名称是本项目建议，不是要求供应商使用同名变量。真正的 Key 不放 Unity 配置、PlayerPrefs、Web 页面、构建包、日志、错误正文或存档。示例文件如后续获准创建，只能有占位值。公开部署的游戏会话 token 与模型 Key 分开，浏览器可持有受限游戏会话凭据，但不能持有云模型 Key。

不把全模型列表、剩余额度或云连通性探测作为规则服务启动前置。/health 的 ready 代表规则可用，model_available 可为 false，不能启动时默认调用付费生成接口“测试连接”。模型选择、账户可用性、流控和真实请求验证均 [待确认]；推荐接入时先查官方当前列表/账号权限，再在授权预算内做一次最小验收。

### 9.4 Unity 与 FastAPI 通信

~~~mermaid
flowchart LR
    D["Windows HDRP 客户端"] -->|HTTP JSON /api/v1| L["本机 FastAPI"]
    W["未来 Unity Web 客户端"] -->|HTTPS JSON /api/v1| R["远端 FastAPI"]
    L --> C["共用业务模块：规则/存档/知识/会话"]
    R --> C
    C --> P["LLMProvider"]
    P --> M["ModelScope API-Inference"]
    P --> O["其他 OpenAI 兼容服务"]
    P --> F["MockAIProvider"]
~~~

图表示同一套业务模块可部署在本机或远端，不表示两部署同时写一个 SQLite。客户端不绕过 FastAPI 直接请求模型。

- 沿用 DataSchema 的 /api/v1/health、/saves、/commands、/conversations、/turns、/checkpoints 与状态读取，不为每个 Provider 新建一组公开对话接口。
- 沿用 request_id、save_id、runtime_id、state_version、会话/turn 身份；重复操作幂等，读档/换人后旧结果丢弃。Provider 切换不能创建第二套存档或重置调查进度。
- 游戏端继续 202 + 轮询 + 可取消。初次兼容接入优先非流式；未来供应商流式只能先在后端聚合/校验，不把未经检查的 token 直接显示给玩家，避免先剧透后撤回。
- Provider 的内部错误映射为现有 fallback_reason，例如限流/认证失败归 model_unavailable，超时归 timeout，结构异常归 invalid_output，越界归 unsafe_output；不未经版本设计向 DataSchema 的闭合枚举塞新值。
- 远端 Web 认证/存档归属为未来独立部署 profile。推荐同源 HTTPS 反向代理，以受限用户会话隔离 save、/active、列表、幂等键和 runtime；活跃存档不能全站唯一。cookie 方案须 Secure/HttpOnly 与写请求 CSRF 防护，令牌方案须短期及归属校验。具体认证方式、归属字段/迁移及兼容策略 [待确认]，未经确认不改当前单机 v1 契约。

远端首版可用普通 CPU 主机、单写服务和持久磁盘 SQLite；不需要申请专用推理 GPU。不得把各访问者放进同一公开存档，也不能把 SQLite 放在无持久磁盘的临时容器后宣称存档安全。共享部署并发超过测量范围时再评估数据库演进，不提前引入分布式组件。

### 9.5 模型调用与异常降级

固定主线内容由 RuleService/ContentCatalog 决定，Mock 与云模型都不能裁决真相。Mock 是明确的运行模式，不用它伪造“真实魔搭已接入”的参赛证据。

| 情形 | 协调层行为 | 游戏结果 |
| --- | --- | --- |
| 显式 mock、未配置 Key | 直接使用 MockAIProvider，不发网络请求；意图未知给当前合法话题选项 | 固定话题、出示、D/R/A/存档与第一章基础体验可继续 |
| 超时、网络错误、上游 5xx | 在既有总时间预算内有限重试；超出预算立即固定回退 | 不无限等待，不重复结算游戏事件 |
| 429/额度或并发限制 | 遵守 Retry-After；若等待超过总预算则直接回退；短期熔断避免每轮重打 | 可继续必要案务；不为无 Key/额度反复报错挡住玩家 |
| 401/403、无效模型或不支持的请求参数 | 不盲目重试，给脱敏服务诊断；固定回退 | 不把服务配置错误解释为角色拒绝或扣关系 |
| JSON/输出异常或案情越权 | 结构及人物权限检查失败整段拒用 | 有效关键证词仍来自固定批准文本 |
| 用户取消、切人、读档后迟到 | 丢弃过期响应，不再为已取消请求补一个 Mock 回复 | 不把旧回复显示给新 NPC，不写未来记忆 |
| FastAPI 规则服务断开 | 暂停权威变更，保留已有手册/设置并允许重连 | Mock 也不能替代规则服务；不承诺此时还能取证/交接 |

重试次数/熔断窗口仍 [待确认]，推荐沿用现有总预算而非叠加各适配器独立长超时。云生成可能已计费，即使客户端取消也不保证撤销上游工作；业务幂等与供应商计费幂等是不同问题。跨供应商回退须显式配置并获授权，默认只降到不联网的 Mock/固定内容。

### 9.6 WebGL 部署风险与预留

**渲染存在明确不兼容：Unity 6.3 官方表中 HDRP 对 WebGL/WebGPU 均不支持，URP 支持 WebGL。不能把切换 Build Profile 或降低 HDRP 画质称作 WebGL 适配。** 推荐 Windows 主工程保持 HDRP，未来经用户批准后用独立 URP 浏览器展示工程/构建路径共享纯逻辑、DTO、内容标识和后端契约，分别维护材质、灯光、VFX 和场景表现。这个建议不授权当前安装 URP、创建第二工程或迁移资源。[Unity 6.3 渲染管线兼容表](https://docs.unity.com/en-us/engine/6000.3/manual/render-pipelines/choose-a-render-pipeline/feature-comparison)

| 风险 | 最小预留与验收方向 |
| --- | --- |
| HDRP 专属依赖污染共享代码 | 调查/UI/HTTP DTO 不引用 HDRP 类型；Volume/灯/材质/天气仅在展示层，URP 后续用各自资源，不强求自动转换同一 Scene |
| 浏览器不能承担 Windows 进程启动/继承管道 | DesktopCompanionConnection 仅桌面编译；Web 只用 RemoteWebConnection 连接已运行的 HTTPS FastAPI，不能要求网页启动本机 Python |
| 跨域与混合内容 | 推荐同源 /api/v1；若分域，精确配置允许 Origin/Methods/Headers，处理 Authorization 与 X-Request-ID 预检；HTTPS 页面使用 HTTPS API，不用通配 CORS 代替认证 |
| 网络与异步能力不同 | 使用 UnityWebRequest 的异步路线；不在共享客户端用原生 sockets、阻塞等待、Task.Run 线程前提或依赖 System.Threading.Timer 的取消超时；以游戏非缩放计时/异步轮询检测 deadline |
| 存储、刷新和多标签 | SQLite 留后端；浏览器只持用户会话与可重建镜像。刷新/多标签竞争由认证主体下的 runtime/版本和显式恢复处理，不依赖页面退出一定发完保存 |
| 首包、内存与 Shader 成本 | 后续单独测 Web 的模型/纹理/字体体积、加载峰值与浏览器内存；HDRP 候选人物预算不自动套给 Web，证据可读性与两人物身份保持 |
| 输入、中文 IME、Pointer Lock、音频与宿主 iframe | 后续在目标浏览器实测候选框/焦点、Esc 解锁、用户手势启声、嵌入权限及暂停恢复；Windows 通过不能代表 Web 通过 |
| AOT 与 JSON 裁剪 | 共享 DTO 明确类型，第三方库在 Web IL2CPP/裁剪构建实测；不得依赖动态代码生成，严格字段/类型校验不为浏览器降级 |
| 服务可用性与多访问者 | Web 的 Mock 保底仍需远端规则服务可用；配 CPU 服务限流/持久存储/用户归属，不把“无云模型”说成“整站离线可玩” |

UnityWebRequest 在 Web 经浏览器 Fetch 工作，跨域受 CORS 限制；FastAPI 可配置精确来源。Unity 6.3 的 Web 技术限制还包括托管线程和计时相关行为，不能直接照搬桌面异步实现。[Unity Web 网络](https://docs.unity.com/en-us/engine/6000.3/manual/platform-specific/webgl/develop/networking)、[FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)、[Unity Web 技术限制](https://docs.unity.com/en-us/engine/6000.3/manual/platform-specific/webgl/intro/technical-overview)

WebGPU 在当前 6.3 文档中仍为实验路径，也不能解决 HDRP 的平台不支持问题；浏览器预留优先以 WebGL2 + URP 作为候选，不通过升级引擎或假定 WebGPU 可用来绕过现有边界。[Unity Web 图形 API](https://docs.unity.com/en-us/engine/6000.3/manual/platform-specific/webgl/develop/graphics)

### 9.7 后续实施顺序与验收

1. **本轮记录约束。** 仅追加本节、客户端预留说明和 README 入口；既有故事、API、第一章范围、Unity 版本/包/渲染设置不变。
2. **M5/M6 首次实现时加最小接口。** 在现有 Server/app 内实现 LLMProvider + MockAIProvider、配置工厂，与固定主线先打通；由 QA 在其专责目录验证无 Key/无外网仍可走两条第一章路径。不是先写大量空抽象。
3. **随后接魔搭。** 实现 OpenAI 兼容传输与薄魔搭适配，确认账户/模型/额度/能力；真实调用须另行授权。用 401/429/超时/非法/越界/取消 fixture 验证回退，不能只测成功一句聊天。
4. **再验另一兼容服务。** 仅替换服务端配置，验证统一响应与能力差异；Unity /api/v1、证据、知识和保存结果不变，不增加新收费渠道作为隐式回退。
5. **桌面第一章按原 M0–M10 路线完成。** Web 专属材质/认证/托管不阻塞当前 HDRP 切片；共享层在首次写入时避免平台硬依赖。
6. **另行批准浏览器验证切片。** 先做 URP 最小可读场景 + 中文输入 + 一 NPC + 远端 Mock/规则 + 保存恢复，测 WebGL 包、HTTPS/CORS/用户隔离及加载预算；通过后扩到完整第一章。共享逻辑/数据以受控模块复用，不复制维护两套剧情规则。

Web 验收新增最少覆盖：HDRP 桌面回归不变、Web 目标编译无 Windows-only 引用、模型 Key 不在构建/网络响应、Mock 无云请求、Provider 切换不改变存档、访客 A 不能读取/激活 B 的保存、旧 runtime 请求失效、低配表现下五部位及文书仍可读。Web 的目标浏览器、URP 隔离方案、远端鉴权/归属迁移、普通 CPU 托管与持久磁盘、资源预算和具体赛事提交要求均为 [待确认]；推荐按最小浏览器切片实测后再定，不影响当前第一章主线。

本补充完成的是架构检查与扩展设计。LLMProvider、ModelScopeLLMProvider、MockAIProvider、Web 连接器和浏览器构建均尚未实现或运行验证；没有真实模型调用，也没有申请专用 GPU。阶段 3 的历史验证计数只对应当时交付，本补充后以当前文件检查为准。

本次补充的静态检查：23 份 Markdown 中 142 个本地链接、7 个标题锚点有效，现有 51 个 JSON 示例仍可严格解析。251 个正式/管理文件前后比较，仅本文件、TechnicalDesign.md 和根 README.md 变化，其余 248 个 SHA256 一致；新增 0、删除 0。检查范围为文档与文件保护，未运行 Provider、Unity 或 WebGL，没有将本次自查冒称独立 QA 或运行验收。
