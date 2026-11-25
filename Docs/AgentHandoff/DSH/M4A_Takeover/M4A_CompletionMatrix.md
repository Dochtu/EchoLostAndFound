# M4-A 完成度矩阵

- 记录时间：2026-11-23 19:30 (+08:00)
- 判定口径：**只有经过真实 Unity 编译 + 测试或浏览器实跑的功能才记 DONE**；“源码存在”“逻辑层控制台测试通过”不足以记 DONE。
- 状态：DONE = 已实现并经真实运行验证；PARTIAL = 已实现但覆盖不足或有已知缺口；TODO = 未实现；BLOCKED = 存在外部阻塞。

## 一、Task 1：集成 M3-B 逻辑模块

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| Shared 接入 | DONE | `Assets/Station/Station.Runtime.asmdef` 引用 `EchoLostAndFound.Shared`；EditMode 6/6 与 PlayMode 1/1 在 Unity 内编译通过 |
| EvidenceSystem 接入 | DONE | `StationInvestigation.cs` 构造 `EvidenceCatalog` + `EvidenceRegistry`；PlayMode 实测 `evidence.fields_observed`、`evidence.registered E01|E02` 事件 |
| DialogueSystem 接入 | DONE | `DialogueEngine` + `DialogueCatalog`；浏览器实测 `dialogue.session_opened / turn_completed / evidence_presented / disclosure_triggered D01` |
| MockAIProvider 接入 | DONE | `new DialogueEngine(dialogue, Evidence, null, new MockAiProvider(fixtures))`；EditMode `TimeoutPreservesNodeAndSnapshot...` 覆盖 `FallbackReason=="timeout"` |
| 内容 JSON 由 Resources 加载 + 版本校验 | DONE | `Resources.Load<TextAsset>("M3B/...")`，`ContentVersion != "story-v1.0-phase2"` 抛 `InvalidOperationException("调查内容版本不一致")`；PlayMode/浏览器均实际加载成功 |
| 不重新实现既有逻辑 | DONE | `StationInvestigation.cs`、`M4AInvestigationTests.cs`、`M4AStationPlayTests.cs` 哈希与 Codex 版一致（DSH 未改一字） |
| 不把 `M3B/Tests/` 拷入 Unity | DONE | Unity 工程内无 `Assets/_Project/Tests`；测试只在 `Assets/Tests/{Editor,PlayMode}` |

## 二、Task 2：怀表调查系统

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| 怀表观察 | DONE | 场景 `EvidenceWatch` + `InteractionKind.Item`；浏览器 `06-watch-approach.png`（准星锁定「怀表」）、`07-watch-dial.png`（页面「怀表 · 表盘 / 指针停在 9:17。」） |
| 证据字段展示 | DONE（UI 简化为一次翻看） | `翻看背刻、编号和表冠` → `InspectRecord("E01")` 观察全部 5 个必填字段并展示 `FixedText + ProofLimits`；截图 `08-watch-e01.png`。逐字段渐进观察只在逻辑层被覆盖（EditMode `WatchNeedsAllFiveFields...`），HUD 未做逐字段分步交互 |
| 证据登记 | DONE | `evidence.registered E01` 控制台事件 + PlayerPrefs `EchoStation.M4A.evidence.v1` 写入；PlayMode 断言存档含 `E01` |
| 重复获取处理 | DONE | 重复观察 `Changed == false`（EditMode）；`RegisterEvidence("E01").AlreadyRegistered == true`；浏览器重复出示不重复触发 `D01`（`d01Events === 1`） |
| 证据状态更新 | DONE | 已登记证据进入 `GetVisibleEvidenceRecords()`，成为 NPC 对话的“出示”选项；E02 使 `再问站台那晚的照明` 解锁（`requires_disclosure_ids:["D01"]`） |
| UI 反馈 | DONE | 中文证据页 `E01 · 停表与编号` + 正文 + `1 返回车站`；面板不透明、无文字重叠（`08-watch-e01.png` 复检） |

## 三、Task 3：NPC 对话

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| 开始 NPC 对话 | DONE | `E` 对准老周 → `StartSession("npc_laozhou")`；截图 `02-npc-opening.png`（开场白 + 2 个选项） |
| 对话节点选择 | DONE | 数字键 1–9 + 鼠标点击；`Choose(conversation, optionId)`；浏览器 `03-npc-question.png`、`12-repeat-question.png` |
| 出示已获得的证据 | DONE | 选项“出示 <证据号> <标题>”；`PresentEvidence(conversation, new[]{id})`；截图 `10-npc-with-evidence.png`（4 条选项含 E01/E02） |
| 对话条件判断 | DONE | 选项按 `requires_disclosure_ids` 过滤：D01 前只有“问站台那晚的照明”，D01 后出现“再问站台那晚的照明”（`11-disclosure.png` 5 条选项） |
| 出示条件校验 | DONE | 未持有 E02 时出示 → `GameContractException` code `PreconditionFailed`，HUD 显示“现在不适合出示这份证据（…）”（EditMode 断言 + HUD catch 分支） |
| 状态变化后的不同回复 | DONE | 出示 E02 → `dialogue.disclosure_triggered D01`，正文变为“进水，二十一点十七。我的灯到二十才摆好。是黑过，中间那点我记混了。”；刷新页面后同流程仍可复现（`15-persisted-disclosure.png`） |
| Mock AI 失败回退 | PARTIAL | 逻辑层 DONE：EditMode 断言 `SubmitFreeText` 超时 → `FallbackReason == "timeout"`、`GeneratedBridge == null`、节点与快照不变。**浏览器/PlayMode 未触发该路径**（HUD 当前未提供自由输入控件，无 HTTP 后端） |

## 四、Task 4：UI 集成

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| Unity uGUI + TextMeshPro | DONE | HUD 全部由 `Canvas`/`Image`/`Button`/`TMP_Text` 构成（`SceneSetup.MakeHud`），运行期动态建按钮 |
| 保留现有玩家操作 | DONE | WASD 移动、鼠标环视、E 交互、Esc 释放均可用（`StationPlayer`，M3-A 行为保留） |
| 接入中文 UI | DONE | 全部界面文案中文：操作条“WASD 移动 鼠标 环视 E 调查 Esc 释放鼠标”、焦点名“老周/怀表/维修柜”、面板“E 返回车站”；无英文残留（`02/08/11/15` 截图） |
| WebGL 字体正常显示 | DONE | 预烘焙 `StationChinese SDF`（460 字符）+ `TMP_FontAsset` 替换；浏览器控制台 `M4A font StationChinese SDF 怀=True 证据=True`；全部截图中文无缺字 |
| 鼠标锁定与解锁 | DONE | 点击画布 `Capture()`（`CursorLockMode.Locked`）；`Esc` → `Release()`；面板打开强制解锁、关闭后重新锁定（`StationPlayer.Update` 首段） |
| 避免 UI 与第一人称操作冲突 | DONE | 面板打开期间禁用移动/环视/射线；`E` 关闭并重新锁定、`Esc` 关闭并释放；面板内按钮可点击（PlayMode 用 `onClick.Invoke()`，浏览器用真实鼠标点击） |

## 五、Task 5：测试（实际执行）

| 要求 | 状态 | 证据 |
| --- | --- | --- |
| Unity 编译检查 | DONE | 副本内 batchmode 导入 + 编译：`AssetDatabase: script compilation time: 3.818662s`，无 `error CS`，`Exiting batchmode successfully now!` |
| EditMode 测试 | DONE | `total=6 passed=6 failed=0 result=Passed duration=0.1948031`（`Evidence/takeover-final-EditMode.xml`） |
| PlayMode 测试 | DONE | `total=1 passed=1 failed=0 result=Passed duration=0.6375689`（`Evidence/takeover-final-PlayMode.xml`），真实场景加载 + 真实点击/按键 |
| WebGL 构建 | DONE | `WebGL build Succeeded: 65698620 bytes, 00:02:40.3059370, errors 0`；产物 17 文件 21,270,890 B（gzip） |
| 本地 HTTP 浏览器测试 | DONE | `node Tools/Build/serve-webgl.mjs F:\EchoBuilds\M4A-Station-2 18749` + headless Chrome 157（SwiftShader WebGL2）实际加载，冷启动 1,447 ms |
| 证据与 NPC 对话端到端 | DONE | `M4A-QA/Scripts/m4a-e2e.mjs`：`completed=true`、11 个页面、5 次交互、D01 恰好 1 次、0 异常、0 HTTP≥400（`Evidence/browser/browser.json`） |

## 六、WebGL 验收流程（逐段）

| 步骤 | 状态 | 证据 |
| --- | --- | --- |
| 玩家进入车站 | DONE | `01-station.png`，冷启动 1,447 ms |
| 走向怀表 | DONE | `06-watch-approach.png` |
| 调查怀表 | DONE | `07-watch-dial.png`（E 键 → 表盘页） |
| 获得证据 | DONE | `08-watch-e01.png`（E01 登记，存档写入） |
| 与 NPC 对话 | DONE | `02-npc-opening.png` |
| 选择问题 | DONE | `03-npc-question.png`（问站台那晚的照明） |
| 出示怀表证据（E01） | DONE（可出示，但**无台词变化**） | E01 可出示；按 M3-B 内容，D01 需要 E02，D03 需要 E01+E05，故单独出示 E01 时 HUD 显示“证据已出示，老周没有补充。” |
| NPC 反馈发生变化 | DONE（经 E02 实现） | 维修柜取 E02 → 出示 E02 → `D01` → 正文变化（`11-disclosure.png`） |
| 游戏状态正确更新 | DONE | 刷新页面后重新出示 E02 仍触发 D01（`14-reloaded.png`、`15-persisted-disclosure.png`），`d01Events === 1` |

**验收脚本字面偏差（需 Codex / Director 裁定）**：原验收脚本写“出示怀表证据 → NPC 反馈发生变化”。按 M3-B 已交付内容，D01（老周承认照明问题）的触发条件是 E02，不是 E01；D03 需要 E01+E05，而 E05 不在第 1 章场景内。DSH 的处置是**不改叙事内容**，而是为 E02 增加现场来源“维修柜”，使“出示证据 → NPC 反馈变化”在浏览器可实证；E01 路径保留为“可出示、无新台词”。

## 七、总体判定

- Task 1：DONE
- Task 2：DONE（UI 为一次性翻看全部字段；逐字段渐进交互未做，逻辑层已具备）
- Task 3：PARTIAL（Mock AI 回退未在浏览器/PlayMode 触发）
- Task 4：DONE
- Task 5：DONE（浏览器验证为 headless Chrome + SwiftShader，未做真实 GPU 与多浏览器手测）
- WebGL 验收流程：9 步全部可观察；“出示怀表证据即改变 NPC 回复”这一步与内容设定不一致，按 E02 路径实证
- **M4-A 整体：可交付（PARTIAL 项已显式记录，无 BLOCKED）**
