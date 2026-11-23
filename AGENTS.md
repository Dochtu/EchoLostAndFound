# 项目协作指令

- 禁止使用 `computer-use:computer-use` 技能。

## 项目与事实来源

- 游戏：《回声失物招领处：末班车之后》，Windows PC，3D 第一人称调查、推理、AI 互动叙事。
- 核心人物：老周、林遥、许澄。计划三章：《停走的怀表》《没有寄出的录音带》《没有名字的车票》。名称之外的真相、人物秘密与结局条件须由获批资料确认。
- 先读取实际存在的文档，不假设读取过不存在的原始大纲。文档存在不代表内容完善；不确定设定标记“待确认”。
- 不覆盖已有有效文档，不删除已有内容；补充时保留来源并区分已确认事实、建议及待确认项。

## 项目技术规范

- Unity 6.3 LTS，当前工程记录为 6000.3.29f1；HDRP，当前包版本为 17.3.0；C#、Input System、Cinemachine 3、TextMeshPro。
- 后端技术方向：Python、FastAPI、SQLite；Unity 与后端采用 HTTP + JSON。方向不等于已经实现或安装，依赖以实际清单为准。
- 以 ProjectSettings/ProjectVersion.txt、Packages/manifest.json 和 Packages/packages-lock.json 为准。不随意升级 Unity、安装或升级 Package、更换渲染管线。
- 本阶段只建立项目管理与多 Agent 协作体系，不开发游戏玩法，不创建玩家控制器、正式场景或后端功能。

## 团队与文件管理

Game Director 负责目标、任务拆分、依赖、文件分配、跨模块授权及验收汇总。阶段推进最终等待用户作为验收方明确批准，不允许 Agent 自行批准下一阶段。

| Agent 标识 / 职称 | 主要写入范围 | 职责 |
| --- | --- | --- |
| unity-engineer / Unity Engineer | Assets/_Project/Scripts/、Prefabs/、Scenes/ | C#、玩家控制、交互、NPC 游戏逻辑、UI、线索证据、场景集成、存档 |
| art-director / Art Director | Assets/_Project/Art/、Materials/、VFX/、Audio/ | HDRP 美术、模型、材质、贴图、灯光方案、VFX、动画、音频与视觉风格 |
| narrative-designer / Narrative Designer | Docs/StoryBible.md、Assets/_Project/Data/ | 世界观、剧情、人物、秘密、线索、对话、知识边界、多结局、剧情数据 |
| ai-engineer / AI Engineer | Server/，默认排除 QA 主责的 tests/ | Python、FastAPI、LLM、自由对话、上下文、记忆、SQLite、接口与异常处理 |
| qa-engineer / QA Engineer | Assets/_Project/Tests/、Server/tests/ | Unity/C#、Python/API、剧情路径、Bug 定位、回归及性能审查与测试 |

- 表中 Assets/_Project/ 下的缩写目录均相对于该根目录；目录归属包含相应 Unity .meta 文件。
- 当前材质目录为 Assets/_Project/Art/Materials/，优先沿用；Assets/_Project/Materials/ 仅为允许的备选范围，不因角色配置自动创建或迁移。
- 每个 Agent 原则上只能修改自己的负责目录；其他目录可以按需只读。跨模块修改必须由 Game Director 明确授权到具体文件。
- Docs/GDD.md、Docs/TechnicalDesign.md、Docs/TestPlan.md、README.md、AGENTS.md、.codex/ 和根版本管理文件由 Director 协调并指定唯一写入者。
- Server/tests/ 默认由 QA 主责；AI Engineer 写测试前必须取得具体文件分配。美术编辑 Scene 或 Prefab 也必须先取得跨模块授权。
- 多个 Agent 不得同时修改同一个文件，尤其禁止同时修改同一 Unity Scene；Prefab、.meta、共享数据和测试同样适用。
- Director 在分派任务时记录目标、依赖、唯一写入者、准确文件清单、验收条件；编辑前确认清单，移交后方可更换写入者。可以使用任务消息记录，本规则不是自动文件锁。
- 禁止手工拼接 Unity Scene YAML；无法通过获准的 Unity 工作流编辑时报告阻塞。
- 未经明确授权不得修改 ProjectSettings/、Packages/ 或共享 HDRP 配置。
- 保留正式资源与 Assets 下所有 .meta，不随意重建 GUID，不为整理目录删除资源。
- 自定义 Agent 使用 .codex/agents/*.toml；name 是调用标识，description 包含英文职称。不设置 model 或推理参数，默认沿用父会话的模型解析规则。
- 角色配置不等于启动工作；实际并发以宿主限制为准，不绕过权限或并发限制。

## 代码与数据规范

- 模块化设计、单一职责、合理使用接口、避免过度设计，避免超大 MonoBehaviour。
- 重要业务逻辑必须有测试；测试应验证行为、边界及失败路径。
- 关键游戏状态不能由 LLM 直接决定。线索、矛盾、信任变化、章节及结局条件由确定性规则校验。
- 区分世界真相、人物所知与人物愿意透露的信息，AI 输出不能自行成为正式设定。
- API Key 只能放在服务端环境变量中，禁止写入客户端、资源、配置正文或日志；.env 示例只能包含占位值。
- .gitignore 不能识别任意文件中嵌入的密钥，提交审查必须核对是否泄露；不因忽略规则而假设安全。

## 版本管理

- 保留 Assets/、Packages/manifest.json、Packages/packages-lock.json、ProjectSettings/ 与正式游戏配置。
- 忽略 Unity/Python 缓存、IDE 生成文件、构建产物、本地运行日志、虚拟环境及真实环境变量文件。
- 未经明确要求不得执行 git add、git commit、推送、重置、清理、全局 Git 配置修改或 LFS 跟踪规则变更。
- Git LFS 已在阶段 1 检查到；大型二进制资源导入前再确定具体类型与 .gitattributes，不自动将全部资源纳入 LFS。

## 阶段开发流程

每个阶段依次执行：

1. 明确开发目标与验收条件。
2. 确认依赖关系、实际资料与待确认项。
3. 分配 Agent。
4. 明确文件修改范围和唯一写入者。
5. 实现本阶段获准的功能或管理变更。
6. 运行与变更相称的测试；无法执行的内容明确标记“尚未验证”。
7. QA 审查，修复获准范围内的问题并复核。
8. 输出验收报告：目标、修改文件、验证证据、问题、风险、未验证项及下一步建议。
9. 等待 Game Director 汇总及用户明确批准下一阶段，禁止自动开始下一阶段。
