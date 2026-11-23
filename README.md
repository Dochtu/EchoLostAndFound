# EchoLostAndFound

Unity 工程版本：6000.3.29f1。

## 目录

- `Assets/_Project/`：场景、脚本、美术、预制体、音频、特效、数据及测试。
- `Server/app/`：后端应用目录。
- `Server/tests/`：后端测试目录。
- `Server/requirements.txt`：后端 Python 依赖清单。
- `Docs/GDD.md`：游戏设计文档。
- `Docs/StoryBible.md`：故事设定集。
- `Docs/TechnicalDesign.md`：技术设计文档。
- `Docs/TestPlan.md`：测试计划。

当前仅补齐目录骨架，文档为占位，后端尚未实现。空目录中的 `.gitkeep` 用于版本控制保留目录；Unity 的 `.meta` 由编辑器导入时生成。

## 2026-11-21：阶段 2 设计稿

上述“文档为占位”保留为初始化记录。[GDD](Docs/GDD.md) 与 [StoryBible](Docs/StoryBible.md) 已结合恢复的原始大纲和用户确认沿用的历史完整剧情更新；[来源记录](Docs/Sources/README.md)保留依据，[阶段 2 报告](Docs/Stage2DesignReview.md)说明独立静态 QA 和未验证项。

阶段 2 仅完善策划，等待用户验收；未开始游戏代码、后端或正式资源制作。TechnicalDesign 与 TestPlan 仍为占位文档，不将设计稿视为系统已实现或下一阶段已批准。

## 2026-11-21：阶段 3 技术设计与第一章规划

用户阶段 3 任务明确将既有 GDD、StoryBible 作为已验收输入，确认第一章为后续完整 3D 垂直切片目标。前文保留各阶段当时的状态；当前技术文档入口如下：

- [Unity 客户端设计](Docs/TechnicalDesign.md)：控制、输入、场景、物件检查、NPC 与 UI。
- [整体架构](Docs/Architecture.md)：本机 FastAPI、SQLite、规则权威与可替换模型。
- [数据与 API 契约](Docs/DataSchema.md)：统一字段、数据库、幂等、读档隔离与 JSON。
- [HDRP 视觉规范](Docs/VisualDirection.md)：三区域、人物、资源管线与画质档。
- [第一章事件映射](Docs/Chapter01ImplementationMap.md)：E/D/R/A 的前置、事件与章末条件。
- [测试计划](Docs/TestPlan.md)：Unity、Python、剧情、故障与视觉验证。
- [垂直切片开发路线](Docs/VerticalSlicePlan.md)：M0–M10 依赖、职责、文件范围与验收。
- [阶段 3 审查报告](Docs/Stage3TechnicalDesignReview.md)：现状、决策、静态检查、独立 QA 与未决项。

本轮仅技术文档设计，尚无第一章游戏代码、规则服务、正式 3D 场景或可玩构建。阶段 3 完成审查后等待用户验收，不自动进入阶段 4；Git 初始跟踪/提交、LFS、依赖安装和共享配置改动仍须明确授权。

## 2026-11-21：后续模型与浏览器部署约束

赛事方向的架构补充见 [Architecture 第 9 节](Docs/Architecture.md#9-魔搭模型接入与浏览器部署的后续约束)，客户端预留见 [TechnicalDesign 第 11 节](Docs/TechnicalDesign.md#11-后续-ai-与浏览器适配边界)。

后端统一 LLMProvider，优先预留魔搭 API-Inference、其他 OpenAI 兼容服务和 MockAIProvider，不依赖专用推理 GPU；Key 仅服务端环境变量。Windows 第一章保持 HDRP，未来 WebGL 另验 URP 展示路径与 HTTPS 远端后端，不能直接导出 HDRP。此次仅追加设计说明，Provider 和 WebGL 尚未实现，未改代码、资源、包或设置。
