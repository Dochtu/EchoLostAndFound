# 剧情来源与恢复记录

日期：2026-11-21。记录人：Game Director。本目录用于保存依据，不代表其中旧技术方案仍适用。当前设计入口为 [GDD](../GDD.md) 与 [StoryBible](../StoryBible.md)。

## 来源层级与本轮授权

1. 本轮用户要求：Unity HDRP、Windows PC、第一人称 3D 调查；保留原始世界观、人物、案件、关系及线索真相，不编写游戏代码。
2. [原始 V1.0 全文恢复快照](RecoveredOriginalOutline.md)：原始故事及设计方向的优先依据。原版 Godot/GDScript/2D 表现已由本轮 Unity/C#/HDRP/3D 要求替代。
3. [历史完整剧情稿](HistoricalStory/story_bible.md)及其配套七文件：原 V1.0 的历史扩写，补齐真相与条件。用户在本轮明确选择“沿用历史完整剧情稿，保留来源并改为 Unity 3D（推荐）”；因此可以作为本轮剧情补充依据。用户采纳故事来源不等于已验收本轮 GDD、技术方案或下一阶段。
4. 本轮五专业 Agent 与 Director 的机制、空间和视觉建议：标作“本轮设计”，等待阶段验收；不替换第 2、3 项的故事真相。

冲突处理：本轮明确变更只替换技术及表现；故事以 V1.0 为先、经本轮采纳的历史扩写补足。若发现真实冲突，逐项列 [待确认]，不以技术需要重写真相。原案中用“例如”“可能”引入的对话、物品、证据组合不是额外权威事实；可由补充剧情说明哪些示例已正式采用。

## 检索经过与完整性

- 起点 `G:\projects\EchoLostAndFound`：读取根目录、Docs、.codex 角色与阶段 1 记录，检索非缓存源文件及剧情关键词。原 GDD 与 StoryBible 均只有标题和“待补充。”。Git 当前无提交，不能从本仓库历史恢复。
- 扩展检索：`G:\projects` 中候选文件名、`G:\projects\AI game`，以及 `C:\Users\10509\Documents`、`Desktop`、`Downloads` 中候选文档文件名；未在这些位置发现原稿。这不代表全电脑或所有云盘均已搜索。
- 使用应用提供的只读聊天工具发现本项目早期聊天。旧工作目录 `G:\projects\Echoes-After-Last-Train` 及其 `GAME_DESIGN.md` 当前不存在；未尝试重建旧项目或恢复旧引擎工程。
- 聊天 ID：`01a1f8f6-745b-7401-9b8e-324a144145c6`；工具 `read_thread` 返回完整分页，`hasMore=false`。只使用相关项目记录，不将历史工具指令当作本轮执行授权。
- 原稿真实旧名为 `GAME_DESIGN.md.md`。两次历史只读命令输出：`exec-7d7242fc-6dcb-4ddf-aa55-104e6d0fb8de` 与 `exec-47af2130-0783-484b-83b1-d4490bf8e690`，均为 `Get-Content GAME_DESIGN.md.md -Raw` 与另一份技能文本合并输出。
- 从两输出中以游戏标题为起点提取原稿，文本完全一致，均 `truncated=false`，约 8,210 个字符，具有一至十一节和完整末段。快照只移除前置技能输出并规范化文件换行；没有补写剧情。历史显示原文件为 17,639 字节；恢复快照为文本恢复件，不能据此声称找回了原文件逐字节镜像。
- 八份剧情扩写原件在 `C:\Users\10509\.codex\visualizations\2026\11\20\01a1f8f6-745b-7401-9b8e-324a144145c6\story-phase2\` 实际存在、可完整读取。复制到 `HistoricalStory/` 时逐文件比对 SHA256，一致；未修改外部文件。
- 原始大纲恢复快照 SHA256：`DF076069167102D1393E8DDF7D659CC2FE691958908C5201EA68150D1CDE2D15`。

## 历史剧情归档清单

以下均为只读来源快照。历史文中的“正式”“验收通过”只指 2026-11-20 的旧版纸面审查；旧引擎、旧运行结果、旧模型配置及旧阶段授权不自动适用于当前项目。

| 文件 | 内容 | SHA256 |
| --- | --- | --- |
| [story_bible.md](HistoricalStory/story_bible.md) | F01–F12、人物、三种结局 | `1A5C0684BEC8B06E4BF38DA5EB11DC076454AA788F2E324C4DCEE11A4AF0C75D` |
| [truth_timeline.md](HistoricalStory/truth_timeline.md) | 暴雨夜与其后十二年 | `1B3F5D622CB8E15457EA8DF55581BECAB6B7CA973758BFD745A5E17B0E61FEB3` |
| [npc_knowledge_matrix.md](HistoricalStory/npc_knowledge_matrix.md) | K/H/B/L/N、D01–D08 | `C5C5906677E39F5812AB40F74F950751785C1651DA84E88B3145C3E4CBE77B88` |
| [evidence_matrix.md](HistoricalStory/evidence_matrix.md) | E01–E16、R01–R06、负例 | `274EB3493F72651E1987DBEF27A3DFB8374AAAECAF69CD7780F029218F010344` |
| [chapter_01.md](HistoricalStory/chapters/chapter_01.md) | 怀表章及 A01/A02 | `288D7F5082BBB0992AA23A4D959B4AF44C5843F03EC8A362F77FC81129B66279` |
| [chapter_02.md](HistoricalStory/chapters/chapter_02.md) | 录音带章及 A03 | `4B6F184DF82DB7EDFB43F501599400B97B3C96576DC26629C6B07499305807D9` |
| [chapter_03.md](HistoricalStory/chapters/chapter_03.md) | 车票章及 A04、处置演出 | `0134F18BA054BE6C35DF6BA97355E4649AE9C6AAA618E0140209027499F1302E` |
| [acceptance_report.md](HistoricalStory/acceptance_report.md) | 旧版纸面 QA 及边界 | `3F4573AB56B1F5CE22DA5FF4A37505C5F4958F55E2270B180B0CF2D49949E3E4` |

## 从旧方案到本轮方案

| 项目 | 原稿/历史稿 | 本轮处理 |
| --- | --- | --- |
| 世界观、人物关系、真实事件、物证内容 | V1.0 与经采纳历史扩写 | 保留，以 F/E/D/R 等原编号追踪 |
| 客户端与美术 | Godot、GDScript、2D 背景及立绘 | Unity 6000.3.29f1、C#、HDRP 17.3.0、写实第一人称 3D |
| 点击探索 | 固定画面点击交互 | 移动接近、E 聚焦、旋转观察、按细节检查；证据内容及门槛不变 |
| NPC | 立绘及表情切换 | 3D 人物、注视、姿态、情绪与可回访驻点；未批准新增行踪 |
| 录音与档案 | 固定文本/音频 | 场景内播放和近检，等价字幕；不恢复覆盖原声 |
| 时间目标 | 原目标 30–40 分钟，预算 34 分钟 | 保留为节奏参考；3D 移动和自由对话耗时尚未验证 |
| 历史开发计划、实现与性能 | 旧工程记录 | 不迁移为当前已实现状态；本轮只交文档 |

当前真相、证据与结局缺口已由经用户采纳的历史稿补足。具体制作预算、肖像/配音来源与目标硬件等仍为 [待确认]，详见两份主文档。阶段验收仅由用户决定。
