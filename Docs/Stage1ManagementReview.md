# 阶段 1：项目管理体系验收记录

日期：2026-11-21。范围：版本管理、五个专业 Agent、协作规则及文档审查；不包含玩法、正式场景或后端实现。

## 读取与保护

已实际读取 AGENTS.md、README.md、GDD.md、StoryBible.md、TechnicalDesign.md、TestPlan.md。
阶段开始时未发现 .codex/config.toml、.codex/agents/、.git/ 或 .gitignore。
保留 README 和四份设计文档原文；AGENTS.md 以追加方式补充，保留禁止 computer-use:computer-use 的原规则。
没有找到独立原始游戏大纲；不得将用户本次概要当作已经读取的完整剧情文件。

## 文档逐项审查

| 文件 | 当前实际内容 | 已完成部分 | 缺失部分 | 待确认内容 |
| --- | --- | --- | --- | --- |
| GDD.md | 标题“游戏设计文档”；正文“待补充。” | 文件与标题 | 核心循环、系统范围、操作/UI、章节流程、资源与性能预算、里程碑、验收标准 | 首个可玩范围、目标配置、玩法优先级、AI 交互失败体验 |
| StoryBible.md | 标题“故事设定集”；正文“待补充。” | 文件与标题 | 世界观、人物、时间线、秘密、人物知识边界、线索链、矛盾、分支与结局 | 原始大纲来源、全部游戏真相、三名人物关系与秘密、三章具体剧情、结局条件 |
| TechnicalDesign.md | 标题“技术设计文档”；正文“待补充。” | 文件与标题 | 模块及程序集、状态归属、HTTP JSON 契约、数据模型、存档版本、AI 约束、错误处理、部署与测试架构 | 后端部署位置、模型来源、离线与超时策略、接口版本、HTTP 开发策略、资源加载与性能目标 |
| TestPlan.md | 标题“测试计划”；正文“待补充。” | 文件与标题 | EditMode/PlayMode、Python/API、剧情路径、存档回归、中文 UI、失败回退、性能及 Windows 构建矩阵 | 验收阈值、目标硬件、自动化范围、测试数据来源、剧情覆盖标准 |

以上文档均未完善。已知游戏名、类型、技术方向、三名核心人物及三章名称来自用户要求；没有据此补造真相。

## Agent 配置约定

- 依据当前官方 Subagents 文档：项目级 .codex/agents/*.toml，每个文件使用 name、description、developer_instructions。
- name 采用 unity-engineer、art-director、narrative-designer、ai-engineer、qa-engineer；英文职称记录在 description 中。
- 不指定模型、推理参数、服务商、权限或并发数；.codex/config.toml 仅显式启用 agents。
- 角色文件的目录边界是协作指令，不是操作系统权限隔离或自动文件锁。实际权限、并发和项目可信状态由宿主决定。
- 现有 Art/Materials/ 优先沿用；没有创建单独 Materials/。Server/tests/ 由 QA 主责，AI Engineer 需按文件授权。
- 五个角色定义不表示五个 Agent 同时运行。QA 的只读审查可并行，写入仍必须分配唯一文件负责人。

## 下一阶段建议（尚未授权执行）

先确认原始大纲与第一章最小范围，再补齐设计和技术契约、验收标准，随后验证当前准确路径的 Unity 打开及 Windows 构建。
大型美术资源导入前确定 LFS 文件类型、存储和协作方案；不要对全部 Assets 或文本格式资源盲目启用 LFS。
阶段 1 完成后停止，等待用户验收，不自动开发玩家控制器、玩法、正式场景或后端。

## 配置依据

- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/config-reference

静态检查与实际客户端加载验证须分别报告，不能将 TOML 可解析等同于运行中的客户端已经发现角色。

## 已执行验证

- Git 2.52.0.windows.1，Git LFS 3.7.1 均可用；已在当前根目录初始化 Git，默认分支为 master，提交数 0，索引为空。未执行 git add、git commit、推送或 LFS 配置变更。
- 五个 Agent 文件通过本地 TOML 解析；逐一检查只有 name、description、developer_instructions 三个非空字符串字段，标识与文件名一致，无模型或推理覆盖。
- 本机 Codex CLI 为 0.171.0-alpha.13；codex --strict-config app-server --print-startup-config 返回成功。该命令验证启动配置，不证明当前桌面会话已发现五个角色。
- CLI 输出全局 arg0 临时目录清理及 PATH 别名写入权限警告，命令仍返回成功；未修改全局配置或尝试放宽权限。
- git check-ignore 验证 Unity 临时目录、IDE 生成文件、Python 虚拟环境与缓存、真实 .env 文件及运行日志命中忽略规则；示例 .env.example、.env.template 保留。
- 对 Assets、Packages、ProjectSettings、Docs、Server、.codex 中 198 个现有正式/管理文件进行忽略检查，误忽略数量为 0。
- README、四份原有设计文档、manifest、packages-lock、ProjectSettings.asset、OutdoorsScene.unity 的 SHA256 与修改前一致；AGENTS.md 原始内容前缀保留。
- 未启动 Unity、Play Mode、Windows 构建、后端或真实 AI 调用。本阶段不以这些未执行项目作为验收通过证据。
- 自定义角色的宿主发现、实际调用、模型继承及项目可信状态尚未进行运行验证，需在后续获准的会话中核对。

## 独立 QA 审查

只读 QA 子任务已独立重读管理文件和四份设计文档，复核 TOML 字段、职责与文件边界、Scene 互斥、Server/tests 归属、原始禁用规则及剧情事实来源，未发现阻塞问题。
QA 独立执行 git status、git ls-files 和 git check-ignore，确认无暂存、无提交，所测缓存被忽略，正式场景、.meta、包清单、ProjectSettings 与 Agent 文件未被忽略。
结论限于本阶段管理文件；这次 QA 子任务不构成项目自定义角色已被宿主加载的证明。阶段 1 等待用户验收，后续开发尚未获准。
