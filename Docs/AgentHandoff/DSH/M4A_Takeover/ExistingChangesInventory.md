# 现有变更清单（Codex → DSH）

- 记录时间：2026-11-23 19:30 (+08:00)
- 范围：仅 `EchoLostAndFound_WebGL` 工程（仓库根 `Assets/`、`Packages/`、`ProjectSettings/` 无改动）
- 基线提交：`4c51712`
- 接管前快照（DSH 修改前）：`G:\projects\EchoLostAndFound\M4A-Backups\WebGL-before-DSH-20261123-190008\`（Assets/Packages/ProjectSettings 共 220 个文件，8.9 MB，含逐文件 SHA-256 `Assets.sha256`）
- Codex 版完整 diff：`G:\projects\EchoLostAndFound\M4A-QA\Logs\codex-unstaged.diff`
- 说明：所有文件均未 `git add`/`commit`（遵循 AGENTS.md「未经明确要求不得提交」）。

## 一、逐文件状态与哈希（SHA-256 前 12 位 / 字节数）

“接管前”指 DSH 开始修改之前的磁盘状态（= Codex 中断时状态）。

| 文件（相对 `EchoLostAndFound_WebGL`） | 接管前 | 当前 | 归属与改动 |
| --- | --- | --- | --- |
| `Assets/Station/StationInvestigation.cs` | F54A077F6E6D / 2962 | F54A077F6E6D / 2962 | **Codex 新增，DSH 原样保留**（逻辑层接入，内容版本校验、PlayerPrefs 存档） |
| `Assets/Tests/Editor/M4AInvestigationTests.cs` | D23C2BA8D41C / 5698 | D23C2BA8D41C / 5698 | **Codex 新增，DSH 原样保留**（3 条 EditMode） |
| `Assets/Tests/PlayMode/M4AStationPlayTests.cs` | A0AD288DDA48 / 3165 | A0AD288DDA48 / 3165 | **Codex 新增，DSH 原样保留**（1 条端到端 PlayMode） |
| `Assets/Station/Station.Runtime.asmdef` | C41DD4B02AD6 / 258 | C41DD4B02AD6 / 258 | Codex 改（+M3-B 四程序集），DSH 未动 |
| `Assets/Tests/Editor/M3A.EditMode.asmdef` | 9A8D85BBF1D0 / 461 | 9A8D85BBF1D0 / 461 | Codex 改（+M3-B 引用），DSH 未动 |
| `Assets/Tests/PlayMode/M4A.PlayMode.asmdef` | FE4A6F1F17AB / 260 | 3D737EADF1AB / 233 | **DSH 修**：删除与 `optionalUnityReferences: ["TestAssemblies"]` 重复的 `UnityEngine.TestRunner` 引用（原编译失败） |
| `Assets/Station/StationHud.cs` | 20FB212CC2F5 / 8676 | 0A741E522C3A / 10395 | Codex 重写 → **DSH 重写**（修复关闭流程、出示文案、字体加载、布局） |
| `Assets/Station/StationPlayer.cs` | 22AE1678BC64 / 4332 | 3CCD99759EF4 / 5105 | HEAD 版 → **DSH 重写**（面板打开时解锁光标 + E/Esc 关闭 + 禁用移动） |
| `Assets/Station/M2Interactable.cs` | 00E25EF3E5D5 / 2227 | EB0DDD1F83EC / 2316 | **DSH 改**：`InteractionKind` 追加 `Document = 3`（枚举尾部追加，旧场景值不变） |
| `Assets/Station/Editor/SceneSetup.cs` | 4731925986AC / 11541 | FBE75C7C78F2 / 11948 | **DSH 改**：新增“维修柜”（E02 来源）、交互标签中文化、HUD 新布局与不透明面板底色 |
| `Assets/Station/Scenes/Station.unity` | 8176BA948898 / 186385 | 1B0F0026B06D / 190083 | **DSH 重新生成**（经 `Echo/Generate WebGL station`，未手改 YAML）；GUID 仍为 `a1909a2cd244bed4f941264730418188` |
| `Assets/Station/Editor/ChineseFontBaker.cs` | 不存在 | 0115688F3CED / 4090 | **DSH 新增**（编辑器字体烘焙工具） |
| `Assets/_Project/Resources/M4A/StationChinese.ttf` | 不存在 | 72FB99931F15 / 469368 | **DSH 新增**（思源黑体 SC 子集，2066 字形，TrueType） |
| `Assets/_Project/Resources/M4A/StationChinese SDF.asset` | 不存在 | 83E842E1151E / 2338006 | **DSH 新增**（预烘焙静态 TMP 字体资产，460 字符，1024 atlas） |

`.meta` 文件：`ChineseFontBaker.cs.meta`、`StationChinese.ttf.meta`、`StationChinese SDF.asset.meta`、`Assets/_Project/Resources/M4A.meta` 及目录 meta 均由 Unity 生成，随文件一同保留。

## 二、Codex 已移交并原样保留的 M3-B 资产

| 路径 | 内容 |
| --- | --- |
| `Assets/_Project/Scripts/M3B/Shared/` | `GameContracts.cs`、`ErrorCodes.cs`、`JsonSupport.cs`、`IdGenerators.cs` 等（`noEngineReferences: true`） |
| `Assets/_Project/Scripts/M3B/EvidenceSystem/` | `EvidenceModel.cs`、`EvidenceCatalog.cs`、`EvidenceRegistry.cs`、`EvidenceSnapshot.cs`、`EvidenceObservationResult.cs` 等 |
| `Assets/_Project/Scripts/M3B/DialogueSystem/` | `DialogueEngine.cs`、`DialogueCatalog.cs`、`DialogueSession.cs`、`DialogueTurnResult.cs`、`DialogueEvidencePresentationResult.cs` 等 |
| `Assets/_Project/Scripts/M3B/MockAIProvider/` | `MockAiProvider.cs`、`MockAiScenarioJson.cs` 等 |
| `Assets/_Project/Scripts/M3B/*.asmdef` | `EchoLostAndFound.Shared/Evidence/Dialogue/MockAi` 四个程序集 |
| `Assets/_Project/Resources/M3B/ch01_evidence.json` | 内容版本 `story-v1.0-phase2`，证据卡 E01–E05 |
| `Assets/_Project/Resources/M3B/ch01_dialogue.json` | NPC `npc_laozhou` / `npc_linyao`，节点、选项条件、disclosure D01–D03 |
| `Assets/_Project/Resources/M3B/mock_ai_fixtures.json` | 7 个 mock AI 场景 |

**DSH 未修改上述任何一个字节**（仅 `StationInvestigation.cs`/HUD 读取它们）。

## 三、DSH 新增的工程外记录

| 路径 | 内容 |
| --- | --- |
| `M4A-QA/Logs/logic-results.txt`、`logic-build.log` | Codex 的 M3-B 控制台测试 29/29（继承，仍是逻辑层唯一证据） |
| `M4A-QA/Logs/codex-unstaged.diff` | 接管前未暂存 diff 全文 |
| `M4A-QA/Logs/takeover-final-EditMode.{log,xml}` | 最终 EditMode 6/6 |
| `M4A-QA/Logs/takeover-final-PlayMode.{log,xml}` | 最终 PlayMode 1/1 |
| `M4A-QA/Scripts/make-font.py`、`font-chars.txt` | 中文字体子集生成脚本与字符表 |
| `M4A-QA/Scripts/m4a-e2e.mjs` | WebGL 浏览器端到端脚本（CDP，零依赖） |
| `M4A-QA/e2e/final-01/` | 最终浏览器证据：15 张截图 + `browser.json` |
| `M4A-Backups/WebGL-before-DSH-20261123-190008/` | 接管前快照 |

## 四、明确的“未触碰”清单

- `Server/`（M4-B 其他 Agent 的后端；`Server/requirements.txt` 的未暂存修改早于本接管，来自 M4-B，DSH 未改）。
- 仓库根 `Assets/`、`Packages/`、`ProjectSettings/`（原始 HDRP 工程）。
- `EchoLostAndFound_WebGL/Builds/M3A-Station`（M3-A 已验收构建，原样保留）。
- 无 `git reset`、无 `git clean`、无强制覆盖、无删除任何 `.meta`、未删除任何场景或 Prefab。
