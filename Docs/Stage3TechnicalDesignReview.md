# 阶段 3：技术架构与第一章切片规划审查

日期：2026-11-21。负责人：Game Director。范围：技术架构、数据/API 契约、第一章事件映射、HDRP 规范、测试与开发路线。此文记录设计验收，不表示游戏已实现。

**结论：八份设计与规划文档已完成；独立 QA 未发现未闭环的设计阻断，静态检查通过，提交用户验收。阶段 4 未开始。** 目标硬件、资源许可、模型供应商及严格 JSON 解析候选依赖等未决决定按本文第 6 节及各规范处理，不能把设计采纳等同于安装/调用授权。

## 1. 授权、资料与真实现状

用户本轮完整阶段 3 任务将既有 GDD、StoryBible 明确作为已验收输入，并确认第一章为下一阶段完整 3D 垂直切片目标。本轮授权止于八份技术/规划文档及 README 入口；画面与沉浸优先，不修改原剧情，不安装依赖、不创建代码/正式资源、不调用真实付费模型、不暂存或提交 Git。历史报告仍保留当时“待验收”的原文，当前任务授权记录在本报告，不倒改历史。

已按任务核对 AGENTS、README、GDD、StoryBible、阶段 1/2 报告、Sources/README、历史总纲/时间线/知识矩阵/证据矩阵/第一章，并检查工程目录、版本/包清单及锁文件、Assets、Server、五份角色配置、Git。来源入口为 [Sources/README](Sources/README.md)；不是重新编写案件。

| 检查项 | 当前证据与结论 |
| --- | --- |
| Unity | ProjectSettings/ProjectVersion.txt 为 6000.3.29f1；没有升级或启动编辑器 |
| 直接非模块包 | HDRP 17.3.0、Input System 1.20.1、Cinemachine 3.1.7、AI Navigation 2.0.16、Timeline 1.8.13、uGUI 2.0.0、ProBuilder 6.1.4、Visual Scripting 1.9.13、Collab Proxy 2.14.0、Development feature 1.0.2、Multiplayer Center 1.0.1、UI Test Framework 6.3.0；manifest 与 lock 逐项相符，锁文件共 67 项 |
| 输入与构建 | activeInputHandler: 1；EditorBuildSettings 当前只列 Assets/OutdoorsScene.unity；不能说已有第一章场景或 Windows 包 |
| Assets | _Project 是脚本/场景/Prefab/Art/Audio/VFX/Data/Tests 骨架，含 .meta/.gitkeep；现有 OutdoorsScene、InputSystem_Actions、中文 OTF/SDF、HDRP 画质/Profile、TMP 与 TutorialInfo 保留。两份模板说明 C# 不构成玩法实现 |
| Server | requirements.txt 仅注释，app/tests 仅 .gitkeep，无游戏后端源码或项目锁依赖 |
| 当前解释器环境 | python 3.10.10 的分发元数据可见 FastAPI 0.156.4、Uvicorn 0.54.0、Pydantic 2.13.4；pytest 未检出。此为当前解释器观测，不证明项目集成或应锁这些版本；本轮未安装 |
| Agent 配置 | 现有五份 .codex/agents/*.toml 与 config 可解析，角色名齐全，原有 Astra/high 或 xhigh 设置保留。只读解析不证明任何其他宿主的模型加载行为；未重复创建配置 |
| Git | Git 2.52.0.windows.1、LFS 3.7.1；master 无提交、索引为空，项目目录整体未跟踪。普通 git diff 为空不能证明保护范围，因此本轮另对开始时 245 个正式/管理文件保存 SHA256 基线 |

### 事实与冲突处理

- 根协作/角色文件保留早期“阶段 1”范围文字，本轮用户明确授权技术文档设计，按用户当前范围执行，未借此开发游戏或改角色配置。
- 历史 D02 兜底文字曾有“收件后才更新”的歧义，已由现行 StoryBible 和阶段 2 审查澄清；本轮按本人实际看过单据完成核对即知情，暂收另需 R01 与暂收条。
- 原案点击/2D、旧 Godot 方向由已确认 Unity 3D 要求替代；真相、E/D/R/A 条件与正文不变。
- GDD 的技术部署/参数留白由本轮提出推荐并显式登记 [待确认]，不能据此声称运行效果已达标。

## 2. 分工、依赖与文件所有权

四个并发名额包含 Director。第一批 Unity、AI、Art；三者交付稳定架构/契约/视觉后，再开第二批 Narrative、QA。使用项目现有五种专业职责，不创建新的同类角色配置。各文件均明确独占，跨作者修改须先移交。

| 角色 | 唯一写入文件 | 依赖与责任 |
| --- | --- | --- |
| Unity Engineer | [TechnicalDesign.md](TechnicalDesign.md) | 客户端模块/场景/控制/UI/人物表现；以 DataSchema 的协议为准 |
| AI Engineer | [Architecture.md](Architecture.md)、[DataSchema.md](DataSchema.md) | 本机服务、规则、数据库、模型边界及唯一规范契约；先向 Unity 稳定字段 |
| Art Director | [VisualDirection.md](VisualDirection.md) | HDRP、人物、资源管线、UI 层级、画质档和可读性 |
| Narrative Designer | [Chapter01ImplementationMap.md](Chapter01ImplementationMap.md) | 严格按获批故事将 E01–E05、D01–D03、R01/R02、A01/A02 映射为事件/条件 |
| QA Engineer | [TestPlan.md](TestPlan.md) | 可执行测试方案；对其他所有文档独立只读审查，问题交原作者修订 |
| Game Director | [VerticalSlicePlan.md](VerticalSlicePlan.md)、本报告、根 README.md | 资料核对、冲突裁决、M0–M10、文件/链接/JSON/哈希验证、用户验收汇总 |

TechnicalDesign 与 TestPlan 初始标题和“待补充。”保留为历史前缀，新增正文不以占位交付；README 只追加。既有 GDD、StoryBible、历史来源、阶段 1/2 报告、Packages、ProjectSettings、.codex、所有现有 Assets/Server 与 .meta 均属保护范围。

## 3. 最终架构与核心取舍

~~~mermaid
flowchart LR
    U["Unity：空间/输入/人物/UI/只读状态镜像"] -->|HTTP JSON /api/v1| A["本机 FastAPI：权威命令与最小投影"]
    A --> R["确定性规则：E D R A / NPC知识 / 关系 / 章节"]
    R --> DB["SQLite：结构事件 + 当前状态 + 检查点"]
    A --> C["按NPC构建获准最小上下文"]
    C --> L["可替换云LLM：理解/非关键衔接"]
    L --> V["结构/权限/内容校验或固定回退"]
    V --> U
~~~

1. **本机服务伴随启动为推荐。** Unity 负责高质量空间与人物，FastAPI 负责规则和保存，SQLite 本地持久化，模型提供者可替换。无需为单机状态引入常驻云端与复杂分布式基础设施；其他部署方式的权衡见 Architecture。
2. **单命令入口与唯一契约。** 所有权威变化经 DataSchema 的 /commands，按获准 command_type 分派。证据登记、关系和章节更新是已校验动作的结果，不能调用任意“加证据/设信任/跳章节”接口。
3. **防迟到、防重复与读档隔离。** request_id 识别重试；save_id 标识存档；runtime_id 在每次激活/读档后更换；state_version 在同一存档生命周期保持单调，恢复旧检查点也不倒退。服务器事务屏障拒绝旧会话命令，客户端丢弃旧响应；仅客户端取消请求不够。
4. **展示与权威分离。** NPC 就位、注视和签字有真实 3D 动作，但 AnimationEvent 不判证据/物权。明确确认、规则校验、暂收条/保管/章状态由单次事务提交，动画失败后按已提交状态重建。
5. **固定关键文本与自由交谈共存。** 世界事实不全量送入每个 NPC；K/H/B/L/N 按人按最小片段过滤。关键证词和物证固定，生成只作非关键衔接。语义校验不能被描述为数学保证的零幻觉，关键规则不依赖生成成功。
6. **事件加状态快照。** 少量结构事件服务去重、关系/披露依据和审查；当前状态供快速读取，命名检查点供恢复。不是无限事件溯源平台，不增加消息队列/向量库。自由输入正文默认不持久保存、不进日志或幂等请求正文。
7. **第一章先做高质量样段。** 单 Station 内容组织承载三区域，成熟现有包组合优先。先验柜台、怀表和一个样人，再扩全场景。高/中/低档可以削减效果成本，不能删除证据信息。

## 4. 文件交付与覆盖矩阵

本轮仅更新三个既有文档（TechnicalDesign、TestPlan、README），新增六份设计文档（Architecture、DataSchema、VisualDirection、Chapter01ImplementationMap、VerticalSlicePlan、本报告），总计九个文件；没有游戏代码/资源修改。

| 交付 | 必须具备的内容 |
| --- | --- |
| TechnicalDesign | 模块与场景依赖；控制/射线/IME/光标；五部位近检；NPC/Animator/事务；十五 UI；HTTP 与取消/恢复 |
| Architecture | 部署比较与推荐；伴随进程生命周期；权威规则和模型边界；最小上下文/事件记忆/失败回退/本机信任边界 |
| DataSchema | 十六领域模型、数据库约束/索引/迁移/事务；完整 API、JSON、错误/超时/幂等；E01/NPC/R01/save 实例 |
| VisualDirection | 三区域 HDRP、两人物/动作/LOD/导入、AI 辅助管线比较、十五 UI 的层级与高/中/低档、测量与验收 |
| Chapter01ImplementationMap | 原文与来源；E/D/R/A 条件/副作用/去重；完整推荐流程和可逆序状态机；最短装袋与核证暂交；切片结束边界 |
| TestPlan | 前置/输入/步骤/可观察断言/证据/负责者；Unity/Python/剧情/边界/视觉；AC01–AC15 分配章节 |
| VerticalSlicePlan | M0–M10 每项的目标/依赖/任务/作者/范围/交付/验收/风险/相对工作量，明确并行与用户门槛 |
| 本报告与 README | 真实状态、来源、设计取舍、修改与验证证据、QA问题闭环、未决决定和后续入口 |

## 5. 验证与独立 QA 记录

### Director 整合检查与已修问题

| 问题 | 修订与对齐结果 |
| --- | --- |
| activate 已成功但丢响应，旧 runtime 失效后普通重试无从取得新身份 | 管理 operation_receipts 先于旧时代拒绝逻辑查询；仍活动的新时代返回原结果；增加认证 GET /api/v1/active，服务重启重新握手；普通 commands 不享有此例外 |
| HTTP 玩家状态示例使用动态字典，与客户端显式 DTO/数组序列化方案冲突 | checked_parts、item_custody 改为有字段定义的数组；内部快照与 HTTP 玩家投影分开；双方文档同步 |
| 关闭近检仅本地隐藏 UI，服务 token 没有撤销路径 | scene.interact 明确 begin_interaction/close_interaction；换对象/取消/恢复/重启撤销，另有待测失效时间；旧 token 不能发证 |
| 仅说“同版本/同存档外键”，实施者仍需猜补公共列 | DataSchema 明确 content_version 公共列、player_saves 复合唯一、同版静态外键、会话跨存档复合外键及回执/事件归属；历史事件/检查点不被迁移改写 |
| 命令返回局部结果，客户端可能自行拼凑权威投影 | changed=true 后 GET 完整 PlayerStateView，再开下一写动作或播依赖新状态的动画；不以事件 ID 或局部 E 列表补权威状态 |
| QA：首次 npc.present 的空事件示例与人物记忆要求不一致 | 首次按本人/证据/字段差集写 npc.evidence_presented 与本人结构记忆，版本递增；重复仅重建临时出示上下文；出示本身不代替 D 或新增知识权限 |
| QA：首次开包状态变化与空 event_ids 不一致 | 首次例改为 package.opened 事件，world flag、事件与幂等结果同事务；重复打开只恢复上下文 |
| QA：表现去重序号被误列为 Animator 参数 | Art 明确移交后由 Director 仅修该句：presentation_id 是本地去重序号，非 Animator/HTTP 参数，也非权威事件 ID |
| QA：PlayerStateView 只给 E 编号，手册没有合法获取正文/来源的路径 | 统一在 GET state 增加 typed 可见证据正文、来源、证明范围与已观察字段；只返回已获内容，不预打包整作者目录后隐藏；413 大小错误一并规范 |
| 固定旧证词只在 ConversationMessage，读档可能丢失或混回未来陈述 | 当前 world_states 中保存获批固定片段的 Journal 投影，随检查点恢复；D 自身事务写入，非 D 固定结果经短期交付 token 确认；不归档生成正文，不扫描旧分支 messages 补记 |
| Director/QA：JsonUtility 默认忽略未知成员、缺失字段默认化，与严格契约不符 | 推荐官方 Newtonsoft JSON 候选作为 M0 需单独批准的依赖；先做 token 级结构/精确类型/必填/未知字段/重复键校验，再 DTO；保留 U02，不能为省依赖降低断言 |

整合问题由原主笔在移交前修订；QA 后发现的 DataSchema 问题由 Director 重新明确分配同一主笔独占返修，完成再移交；VisualDirection 的单句修订由 Director 在 Art 明确移交后接管完成。没有并写。第二批 QA 负责独立复核，并对全部完成稿提出剩余问题；后续实际运行行为仍未验证。

### 独立 QA 与最终静态检查

QA Engineer 逐份只读复核七份他人技术/规划文档、当前剧情及接口，缺口交唯一作者返修后读回复核；TestPlan 由 Director 完整审读，Narrative Designer 另只读交叉核对剧情用例与映射一致。最终结论为“无未闭环的设计阻断，建议提交用户验收”，没有自行批准实施阶段。

Director 运行只读内存检查脚本，得到以下结果（不是运行游戏/API 的测试）：

| 静态检查 | 证据 |
| --- | --- |
| 文档与链接 | Docs 与根 README 共 23 份 Markdown，139 个本地链接（含 4 个标题锚点）有效，缺失目标 0 |
| JSON 示例 | 阶段 3 文档共 51 个 JSON 块严格解析通过，拒重复键/非有限常量的检查无报错；其中 DataSchema 45、剧情映射 4、TestPlan 2 |
| 图与模型 | 八份交付含 14 个 Mermaid 源码块；16 个要求的领域模型全部声明。图作人工结构核对，未单独运行图形渲染器 |
| 剧情一致性 | 映射中的 E01–E05 四列证据表与原矩阵逐行一致；TestPlan 的 AC01–AC15 共 15 行与 GDD 逐行一致 |
| 测试设计覆盖 | 81 个情景：CH 20、Unity 12、API 17、DB 10、AI 10、视觉 12；有 fixture/步骤或请求/结果/证据及阶段归属，尚未执行 |
| 来源保护 | 八份历史稿 SHA256 与来源登记全部一致；更广的源文件保护以本轮前后基线检查为准 |
| 原文保留 | TechnicalDesign/TestPlan 原始标题和占位文本前缀保留；README 原内容作为完整前缀保留，只追加 |
| 范围保护 | 开始时 245 个正式/管理文件，当前 251 个；既有文件仅 TechnicalDesign、TestPlan、README 变化，其余 242 个哈希一致；新增恰为本报告第 4 节六份设计稿，删除 0、越界变更 0 |
| Git | git ls-files 与 git diff --cached --name-only 仍无条目；status 仍为原项目目录整体未跟踪；未暂存/提交/推送/重置/清理或改 LFS |

本轮没有启动 Unity、PlayMode、FastAPI、真实模型、数据库迁移或 Windows 构建，也没有产出第一章游戏程序、测试源码或正式资源。上述检查不能证明帧率、画面、语音、IME、HTTP 并发/恢复或真实通关已运行通过。

### 阶段 3 文档验收清单

以下勾选只表示设计资料及静态检查就绪，用户仍为阶段验收方。

- [x] Unity 客户端架构完整。
- [x] AI 与规则层边界明确。
- [x] FastAPI 接口、错误、超时及恢复策略完整。
- [x] SQLite 数据结构、归属约束、快照与迁移设计完整。
- [x] NPC 知识隔离与固定主线回退可实施。
- [x] E01–E05 映射、D01–D03、R01/R02 条件完整。
- [x] A01 一次结算与 A02 两种保管选择完整。
- [x] 3D 场景与美术/人物/动画规范完整。
- [x] M0–M10 开发路线与并行/互斥依赖完整。
- [x] TestPlan 有可执行输入、步骤及验收断言，AC01–AC15 保留。
- [x] 文档间接口、字段和状态职责经独立 QA 对齐。
- [x] 文档本地链接有效，示例 JSON 可解析。
- [x] 所有未决决定有推荐、理由和确认门槛。
- [x] 原剧情、Unity 工程、包/设置、角色配置和版本管理文件未改动。

## 6. 未决项、风险与确认点

| 未决事项 | 推荐、理由与需要用户确认的内容 |
| --- | --- |
| [待确认] 目标硬件/性能 | 指定一台验收 Windows 机及显示分辨率；1080p/60fps 只作讨论起点，目标未获批不得宣布帧率通过 |
| [待确认] 人物工具/资产来源 | 采用可导出、可商用、能清理面部/手部动作的统一管线，先样人；需确认预算、许可证、肖像与声音来源和服装参照 |
| [待确认] 本机服务发行 | 推荐伴随 Unity 的本地可执行服务与 SQLite；需确认打包方式、发行渠道、签名/防病毒测试及存档/备份位置 |
| [待确认] 云模型配置 | 推荐 Provider 抽象与固定/mock 路径先验；需确认厂商、预算、发送数据边界，不在本轮调用 |
| [待确认] 手感与视觉参数 | 采用文档候选值做后续原型验证，之后冻结距离/镜头/LOD/材质/雨雾成本；需用户认可最终手感/画面，不将候选值冒称实测 |
| [待确认] 严格 JSON 解析依赖 | 当前锁文件无 Newtonsoft JSON；推荐官方 com.unity.nuget.newtonsoft-json 候选，经用户单独批准准确版本及 Packages 文件后再安装；未批准前 M0 网络解析定稿阻塞，不能声称 JsonUtility 天然满足严格契约 |
| [待确认] 设置/可达性/保存策略 | 键鼠中文为第一章基线；确认重绑定/控制器支持范围、字幕/字号、存档槽位/保留与删除策略；默认不保存自由输入全文 |
| [待确认] Git/LFS 执行 | 源码/正式配置/资源.meta纳入精确清单后再申请明确暂存/提交授权；按具体大二进制类型决策 LFS，需确认存储与协作成本 |

未决项都有推荐及受影响门槛，集中在 [开发路线](VerticalSlicePlan.md)和对应技术规范；不把未决事项伪装为已安装或已实现。技术审查通过不等于上述制作参数已获用户批准。

## 7. 第一章后续路线与停止条件

M0 版本/环境/管理基线 → M1 工程与视觉样段 → M2 控制探索 → M3 近检证据 → M4 人物基础对话 → M5 本机规则/存档 → M6 AI → M7 完整剧情 → M8 UI/存档/音画整合 → M9 测试/Windows 构建 → M10 完整试玩。M5 从 M0 后可并行，不应等 M4 完成才启动；依赖图和具体范围以 VerticalSlicePlan 为准。

阶段状态必须分开记录：

| 层级 | 本轮意义 |
| --- | --- |
| 文档设计 | 八份规范/规划已完成并提交用户审阅；尚待本阶段用户验收 |
| 静态验证 | 已完成本文第 5 节检查及独立 QA；通过范围仅限文档与条件一致性 |
| 实际工程运行 | 本轮不启动 Unity、规则服务或真实模型，尚未验证 |
| 游戏功能实现 | 本轮没有 C#、Python、Scene、Prefab、模型、动画或音频产出 |
| 玩家试玩 | 本轮无可玩切片包，尚未通过试玩 |

完成全部文档、修订、链接/JSON检查及独立 QA 后，本轮即停止。下一阶段实施、真实模型调用、依赖安装、共享配置及 Git/LFS 操作均不得仅凭本报告自动开始。
