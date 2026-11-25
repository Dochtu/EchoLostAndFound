# M4-C 本轮文件变更 · 2026-11-24

工作分支 master，HEAD 4c51712。开始时有 24 个已跟踪文件未暂存修改和 754 个未跟踪文件，暂存区为空。既有变更包括 URP 场景、材质、包清单、服务端、DSH 源码和验收截图。[起始清单](M4C/Closeout/git-initial.txt)

| 文件（Unity 路径以 EchoLostAndFound_WebGL/Assets 为根） | 本轮作用 |
| --- | --- |
| Station/StationInvestigation.cs | 兼容旧证据存档，R01、保管守卫、单次写入、章末与确认前快照 |
| _Project/Scripts/M3B/DialogueSystem/DialogueEngine.cs | 导出和校验每 NPC 已出示字段及已触发披露，重开会话恢复选项 |
| Station/StationHud.cs、Station/StationChapterHud.cs 及新增脚本的 .meta | 现有场景入口、章末交接页、回退、菜单、保管表现、陈旧回复隔离 |
| Station/StationDialogueBridge.cs | 远程会话切换、出示顺序与披露镜像 |
| Station/Editor/ChapterFontBaker.cs 及 .meta、_Project/Resources/M4CChapterFont.asset 及 .meta | 新增 30 字静态图集，复用已有字体 |
| Tests/Editor/M4CChapterCloseoutTests.cs 及 .meta、Tests/PlayMode/M4CChapterCloseoutPlayTests.cs 及 .meta | 规则门槛、旧档与两条场景流程回归 |
| M4C/Scripts/m4c-e2e.mjs | 独立 chapter 测试路径 |
| M4C/Closeout/、M4C/CloseoutQA/ | 本轮 Git 清单、XML、编辑器日志、静态引用检查、浏览器记录及截图 |
| Builds/M4C-Closeout-URP/、Builds/M4C-Closeout-Player/ | 测试工程副本及可托管 WebGL 产物。HDRP 使用临时副本 F:/EchoM4C-QA-HDRP-20261124 |
| 项目根目录六份更新报告 | 遗留事项、矩阵、测试结果、文件变更、浏览器验证与交接 |

原 HDRP 的 Assets、Packages、ProjectSettings 以及剧情资料不在本轮写入范围。未暂存、提交或推送。完整工作区含多个阶段成果，不能用总 diff 计算本轮工作量。

交付时 master 仍指向 4c51712，暂存区为空，24 个已跟踪文件有未暂存修改，874 个文件未跟踪。新增验收资料包含首次失败和最终通过两套记录。[最终 Git 清单](M4C/Closeout/git-final.txt)
