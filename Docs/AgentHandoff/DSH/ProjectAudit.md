# DSH 工程审计 · EchoLostAndFound

**审计人**：DSH（主辅助开发 Agent）　**日期**：2026-11-23　**审计性质**：只读取证 + 静态分析
**审计基线**：工作区 `G:\projects\EchoLostAndFound`，Unity `6000.3.29f1 (96d2fe17529c)`、HDRP `17.3.0`
**结论**：工程**可打开、可 Play、可打包 Windows**，但内容完成度只到 M2（第一人称 + 4 个交互点占位）；**WebGL 无法由当前 HDRP 工程直接产出**（见 [WebGLCompatibility.md](WebGLCompatibility.md)）；服务端、证据、对话、AI、存档、任务推进**零实现**，只有文档契约。

> 本报告不修改任何 Unity 资产、场景、ProjectSettings 或 Packages。仅新增 `Docs/AgentHandoff/DSH/` 与 `Tools/Build/` 下的文件。

---

## 1. 取证范围与方法

| 手段 | 实际执行内容 | 是否改动工程 |
| --- | --- | --- |
| 文件系统枚举 | `Get-ChildItem -Recurse` 统计 Assets/Docs/Builds/Tools/Server 文件数、字节数、修改时间 | 否 |
| 文本检索 | `Select-String` / `grep` 读取版本文件、Manifest、Lock、Player/Quality/Graphics/EditorBuildSettings、场景 YAML、脚本源码 | 否 |
| Git 状态 | `git status --porcelain`、`git log`、`git config`、`Test-Path .gitattributes` | 否 |
| 进程与锁 | `Library/EditorInstance.json`、`Get-Process Unity` | 否 |
| 包缓存检索 | `Library/PackageCache/com.unity.render-pipelines.high-definition@2d37db618c5e` 内 `.compute` / `UNITY_WEBGL` / `SHADER_API_GLES3` 统计 | 否 |
| 构建产物核对 | `Builds/*` 目录结构、总字节、`boot.config` | 否 |

**未使用**：Unity 编辑器命令行、PlayMode、任何构建、任何网络服务调用。原因见 §7「未验证事项」。

---

## 2. 版本与包事实

| 项目 | 实测值 | 来源文件 |
| --- | --- | --- |
| Unity 版本 | `6000.3.29f1`，revision `96d2fe17529c` | `ProjectSettings/ProjectVersion.txt` |
| 编辑器安装 | `F:\software\unity\6000.3.29f1\Editor\Unity.exe` | `Library/EditorInstance.json`（`app_path`） |
| WebGL 构建模块 | **已安装**：`F:\software\unity\6000.3.29f1\Editor\Data\PlaybackEngines\WebGLSupport`（含 `WebGLPlayerBuildProgram.exe`） | PlaybackEngines 目录 |
| 其他构建模块 | 仅 `windowsstandalonesupport`（无 Android/iOS/Linux/macOS 模块） | 同上 |
| 渲染管线 | HDRP **17.3.0**（`com.unity.render-pipelines.high-definition`），Core/ShaderGraph/VFX/HDConfig 均 17.3.0，`source: builtin` | `Packages/manifest.json`、`Packages/packages-lock.json` |
| 当前管线资产 | guid `b9f3086da92434da0bc1518f19f0ce86` | `ProjectSettings/GraphicsSettings.asset`（`m_CustomRenderPipeline`） |
| 质量档 | 3 档各自独立 HDRP 资产：`36dd385e759c96147b6463dcd1149c11` / `3e2e6bfc59709614ab90c0cd7d755e48` / `168a2336534e4e043b2a210b6f8d379a`，当前档 `m_CurrentQuality: 0` | `ProjectSettings/QualitySettings.asset`；资产实体 `Assets/Settings/HDRP {Balanced,High Fidelity,Performant}.asset` |
| 输入 | Input System **1.20.1**，`activeInputHandler: 1`（仅新输入系统） | `Packages/manifest.json`、`ProjectSettings/ProjectSettings.asset` |
| 其他关键包 | Cinemachine 3.1.7、AI Navigation 2.0.16、Timeline 1.8.13、uGUI 2.0.0、ProBuilder 6.1.4、Visual Scripting 1.9.13、Test Framework 1.6.0、UI Test Framework 6.3.0 | `Packages/manifest.json` |
| URP | **未安装**（manifest/lock 中无 `com.unity.render-pipelines.universal`） | 同上 |
| 颜色空间 | Linear（`m_ActiveColorSpace: 1`） | `ProjectSettings/ProjectSettings.asset` |
| 序列化 | Force Text（`m_SerializationMode: 2`）、Visible Meta Files | `ProjectSettings/EditorSettings.asset`、`ProjectSettings/VersionControlSettings.asset` |

Force Text + Visible Meta Files 是好消息：Codex 与 DSH 的文本 diff 可审；`.meta` 必须同提交（AGENTS.md 已要求）。

---

## 3. 场景与内容

| 场景 | 大小 | 状态 |
| --- | --- | --- |
| `Assets/_Project/Scenes/Station.unity` | 1,357,967 B（2026-11-23 09:00） | 正式样段，已加入 Build Settings |
| `Assets/OutdoorsScene.unity` | 28,736 B | **Unity 模板场景**，0 个 MeshRenderer，仅 Main Camera/Sun/Sky and Fog Volume/Canvas；**也被加入 Build Settings** |
| `Assets/_Project/Scenes/Stage4Baseline.unity` | 54,982 B | HDRP 校准用，未入 Build |
| `Assets/_Recovery/0.unity` | 1,059,872 B | 编辑器崩溃恢复产物，非正式场景，**建议由 Codex 确认后移出 Assets** |

`Assets/_Project/Scenes/` 下 `Bootstrap/`、`MainMenu/`、`Stage4Calibration/`、`Station/` 四个子目录只有 `.gitkeep`。

`Station.unity` 内部实际对象统计（`--- !u!<class> &` 计数）：

| 类 | 数量 | 说明 |
| --- | --- | --- |
| GameObject | 185 | 场景自有对象；Prefab 展开后 M0/M1 报告记 409 对象，两者口径不同 |
| Transform | 332 | 含 Prefab 实例变换 |
| MeshRenderer | 60 | 场景自有；大量物件在 Prefab 内 |
| Light | 36 | HDRP 光源组件（M0/M1 报告记 26 个启用光源） |
| ReflectionProbe | 3 | 实时反射探针（与 M0/M1 报告一致） |
| Camera | 6 | 含 `StationPreviewCamera` 预览相机 |
| MonoBehaviour | 45 | 含 HDRP Volume、`M2Interactable`、输入资产等 |
| BoxCollider / CapsuleCollider / SphereCollider | 48 / 41 / 20 | 交互与碰撞面 |

场景根节点：`Station`、`Environment`、`SceneSystems`、`GlobalVolume`（第 23664 行，`sharedProfile` 指向 `Assets/_Project/Settings/StationNight.asset`，guid `563d790104b13e64d80e1b003d18f7ba`）、`Cameras`、`ShotAnchors`、`ReflectionProbes`、`InteriorLights`、`M2 Building Collision`、`M2 Cabinet body`、`M2 Register stack`、`Station_Watch`、`StationPreviewCamera`、`StationVisitor`。

`StationNight.asset` 内含 7 个 **HDRP 专属 Volume 组件**：`VisualEnvironment`、`GradientSky`、`Fog`（体积雾）、`Exposure`、`WhiteBalance`、`ColorAdjustments`、`Tonemapping`。这些类型在 URP 侧不存在同名同类实现，是浏览器路径必须重做的表现层。

**Prefab 25 个**（`Assets/_Project/Prefabs/`）：`Environment/`（Counter 122,794 B、LostAndFound 287,161 B、Platform 29,960 B、WaitingHall 34,818 B）、`Environment/M1_5/`（HallColumn、HallPaving、HallPendant、HallSash、HallSettee、HallVault、PiercedVaultBracket、PlatformCanopyBay、PlatformRailPanel）、`Interactables/PocketWatch`（157,915 B）、`NPCs/NPC_VisualSample`（160,919 B）、`Characters/M1_5/StationVisitor`、`Player/M2Player`（8,824 B）、`Props/M1_5/`（ArchiveCarton、BoundRegister、EvidenceWatch、FoundHoldall、IntakeCabinet、IntakeLamp、TiedFolios）、`VFX/Rain/StationRain`（235,216 B）。

**资产体量**：`Assets/` 共 **188.3 MB / 743 文件**（`_Project` 166.9 MB、`TextMesh Pro` 3.8 MB、`_Recovery` 1.0 MB、`Settings` 0.2 MB）。最大单项是**字体** `Assets/SourceHanSansSC-Regular.otf` 15.76 MB；其后是 2K PBR 贴图（Canvas/Mask 10.67 MB、Iron/Mask 9.32 MB、Lime/Normal 8.62 MB、Wood/Mask 8 MB、Concrete/Normal 7.77 MB…）。

扩展名统计：`.meta` 401、`.mat` 73、`.asset` 57、`.png` 43、`.cs` 30、`.gitkeep` 28、`.prefab` 25、`.fbx` 25、`.jpg` 21、`.shader` 14、`.unity` 4、`.shadergraph` 4、`.asmdef` 3、`.compute` 0。

**着色器全部来自 TextMesh Pro 默认资源**（`Assets/TextMesh Pro/Shaders/`：`TMP_SDF-HDRP LIT.shadergraph` 287,427 B、`TMP_SDF-HDRP UNLIT.shadergraph` 279,909 B、`TMP_SDF-URP Lit/Unlit.shadergraph`、`TMP_SDF SSD/Overlay/Mobile` 系列 `.shader`、`SDFFunctions.hlsl`）。工程**没有自写 `.shader`，也没有 `.compute`**。

---

## 4. 运行时代码（关键结论）

`Assets/` 下 30 个 `.cs`，**运行时代码只有 3 个文件**，全在 `Assets/_Project/Scripts/M2/`：

| 文件 | 字节 | 职责 |
| --- | --- | --- |
| `M2Player.cs` | 5,350 | 第一人称移动/转向/交互射线，`[RequireComponent(typeof(CharacterController))]` |
| `M2Interactable.cs` | 2,227 | `IInteractable` + `M2InteractionProbe.Find(...)` |
| `M2InteractionHud.cs` | 3,736 | IMGUI（`OnGUI`）占位提示面板 |

`Assets/_Project/Scripts/M2/EchoLostAndFound.M2.asmdef`：

```json
{ "name": "EchoLostAndFound.M2", "rootNamespace": "EchoLostAndFound.M2", "references": ["Unity.InputSystem"] }
```

其余 27 个 `.cs` 全部是 Editor / Test 工具（场景生成、资产检查、取证、基准、测试）：

- `Assets/_Project/Art/Editor/Stage4StationArt.cs`（33,915 B）、`Assets/_Project/Art/Environment/Editor/Stage4Architecture.cs`（17,450 B）
- `Assets/_Project/Editor/`：`M2EvidenceEditor`、`M2StationSetup`、`Stage4Baseline`、`Stage4GameViewCapture`、`Stage4StationSceneBuilder`
- `Assets/_Project/Editor/M1_5/`：`EditorEvidence`、`HallIntegration`（22,633 B）、`HallSurfaces`、`R1Environment`、`R1ProfilerAnalysis`、`R1Station`、`StationAudit`、`StationCharacter`、`StationFinish`、`StationLods`、`StationPlayerBuild`
- `Assets/_Project/Tests/`：`M2EvidenceReplay.cs`、`Editor/Stage4SceneValidationTests.cs`、`M1_5/{R1CaptureRunner,R1PlayerBenchmark,StationPlayerBenchmark}.cs`、`M2/EditMode/M2EditTests.cs`、`M2/PlayMode/M2PlayTests.cs`

`M2Player` 细节：序列化字段 `view`、`actions`、`chineseFont`、`movementSpeed 2.6`、`sensitivity 0.12`、`pitchLimit 80`、`interactionDistance 2.4`；动作表 `Player/Move`、`Player/Look`、`Player/Interact`、`UI/Cancel`；字段缺失时 `Debug.LogError("M2Player requires a world camera, input actions and Chinese UI font.", this)` 并自禁用；事件 `InterfaceOpened` / `InterfaceClosed`。

`M2InteractionHud` 是**硬编码中文占位**：NPC → `"对话位置已就绪。"`、Counter → `"你正在查看失物招领柜台。"`、Item → `"你正在单独查看这件物品。"`，按钮 `"返回探索   Esc"`。**没有对话数据、选项、输入框**。

场景内 `M2Interactable` 只有 **4 个实例**：`站内旅客`（`Npc`）、`登记册`（`Item`）、`柜台`（`Counter`）、`怀表`（`Item`）。玩家由 `Assets/_Project/Prefabs/Player/M2Player.prefab`（guid `9b810ccd4532aa8489cd4e9ee5aca7f4`）实例接入，相机子物体 local `(0, 1.65, 0)`、near clip 0.035、FOV 60，并挂着 **HDRP 专属 `HDAdditionalCameraData`**。

`Assets/_Project/Scripts/` 下 10 个预留目录全部为空（只有 `.gitkeep`）：`AI/`、`Core/`、`Dialogue/`、`Evidence/`、`Interaction/`、`Investigation/`、`NPC/`、`Player/`、`Save/`、`UI/`。`Assets/_Project/Data/` 的 `Chapters/`、`Evidence/`、`NPCs/` 同样为空。

**结论**：对话系统、线索/证据系统、任务与章节推进、存档、AI 服务接口、UI 框架**在运行时代码中不存在**，连占位类都没有。

---

## 5. 测试现状

`Assets/_Project/Tests/M2/EditMode/M2EditTests.cs`（3,049 B，2 个用例）：

- `StationUsesConnectedPlayerPrefabAndSingleActiveEye`
- `EachStationInteractionHasDistinctVisibleNameAndSolidHitSurface`

`Assets/_Project/Tests/M2/PlayMode/M2PlayTests.cs`（11,153 B，5 个用例）：

- `ProbeHonoursSurfaceDistanceNearestHitAndBlockingGlass`
- `ReachAllFourAuthoredTargetsFromPlayableEyeHeight`
- `CapsulesWalksBothDoorwaysReturnsAndCannotCrossWestHallWall`
- `AllFourMovementKeysFollowThePlayersHeading`
- `RealInputDrivesPlayerButStopsDuringPreviewAndDialogue`

两个测试 asmdef（`M2EditTests`、`M2PlayTests`）均为 `overrideReferences` + `nunit.framework.dll` + `defineConstraints: ["UNITY_INCLUDE_TESTS"]`。最近取证见 `Docs/Evidence/Stage4_M2/EditMode.xml`、`PlayMode.xml`（本轮未重跑）。

**没有一个测试覆盖对话、证据、任务推进、存档或 AI 接口**——因为对应代码不存在。

---

## 6. 构建产物与服务端

`Builds/` 下 4 个 Windows 构建，**没有任何 WebGL 产物**：

| 目录 | 总大小 |
| --- | --- |
| `Builds/M15R1` | 438.8 MB |
| `Builds/M1_5_QA_20261122_152234` | 402.3 MB |
| `Builds/M1_5_QA_20261122_203025` | 407.6 MB |
| `Builds/M2` | 438.9 MB |

`Builds/M2/Station_Data/` 头部大文件：`sharedassets0.assets.resS` **160.64 MB**、`globalgamemanagers.assets` 50.24 MB、`level0.resS` 30.14 MB、`sharedassets0.assets` 22.93 MB。`boot.config`：`gfx-enable-gfx-jobs=1`、`gfx-threading-mode=6`、`hdr-display-enabled=0`、`player-connection-*`（本机调试连接）。

这 160 MB 的 `.resS` 是**贴图流数据的直接规模证据**，对 WebGL 首包预算是硬约束（见 WebGLCompatibility.md §4）。

`Logs/` 只有 `AssetImportWorker0/1.log`（各约 168 KB，2026-11-23 09:32）与 `shadercompiler-*.log`，无崩溃日志。

`Server/` **完全是空壳**：

- `Server/app/.gitkeep`
- `Server/tests/.gitkeep`
- `Server/requirements.txt` 内容仅一行 `# Python dependencies will be added when the server is implemented.`

没有 FastAPI、没有 SQLite schema、没有 `LLMProvider`、没有 `.env`（含密钥的风险面因此暂为 0，但后续必须按 AGENTS.md 只在服务端环境变量持有 Key）。

`Tools/M1_5/` 19 个 Python 脚本是美术/几何生成与打包管线（`build_watch.py` 15,534 B、`build_character.py` 12,649 B、`package_r1.py` 13,451 B 等），**不是游戏逻辑，也不是 WebGL 构建工具**。

---

## 7. 版本管理现状（严重）

| 检查 | 结果 |
| --- | --- |
| `git log` | `fatal: your current branch 'master' does not have any commits yet` —— **0 个提交** |
| `git status --porcelain` | 全部未跟踪：`Assets/ Docs/ Packages/ ProjectSettings/ Server/ Tools/ .codex/ .gitignore README.md AGENTS.md .vsconfig profile`，另有 `Stage4_M1_5_R1_Delivery.zip`（49,432,802 B）与 `Stage4_M1_5_VisualUpgrade_Delivery.zip`（209,186,401 B） |
| `.gitattributes` | **不存在**（`Test-Path` = False） |
| LFS | `git config --get lfs.repositoryformatversion` 空；无 `.gitattributes` LFS 规则 |

`AGENTS.md` 与 `README.md` 记载“阶段 1 已检查到 Git LFS”，但仓库**没有任何基线提交，也没有 LFS 规则文件**。这是本次审计发现的最重要的管理风险：一旦首次提交用普通 Git 收编 188 MB Assets + 258 MB zip，后续清理需要重写历史。

`profile`（25 B，内容 `Library/R1Baseline/action`）是游离在根目录的临时文件，`Docs/Backups/M1_5/Station_before_M1_5.unity`（447,933 B）与 `Assets/_Recovery/0.unity` 是历史产物。

---

## 8. 问题清单与建议

严重度：**S1** 阻塞交付 / **S2** 影响里程碑 / **S3** 卫生问题。

| ID | 严重度 | 问题 | 证据 | 建议处理 | 归属 |
| --- | --- | --- | --- | --- | --- |
| P-01 | S1 | 无 Git 基线、无 `.gitattributes`，与文档“已检查 LFS”矛盾 | §7 | 先建立**不含 zip/Builds/Library** 的基线提交；`.gitattributes` 明确 FBX/PNG/OTF 用 LFS；zip 移出仓库或纳入 LFS。需用户明确授权 git 操作 | Codex / Director（DSH 只出方案，不执行） |
| P-02 | S1 | HDRP 工程无法产出 WebGL | §2 + WebGLCompatibility.md | 走 URP 独立浏览器工程/构建路径（Architecture §9.6 已定方向），不得声称降画质即适配 | Codex（渲染管线） |
| P-03 | S2 | 模板场景 `Assets/OutdoorsScene.unity` 进入 Build Settings，随构建打包一个空场景 | `ProjectSettings/EditorBuildSettings.asset` | 从 Build Settings 移除（保留文件，不删资源）；或明确它作为占位启动场景的用途 | Codex（场景/构建设置唯一写入者） |
| P-04 | S2 | 编辑器恢复文件 `Assets/_Recovery/0.unity`（1.06 MB）在 Assets 内 | 目录枚举 | 移出 Assets 或删除（需确认无引用后由 Codex 执行） | Codex |
| P-05 | S2 | 运行时只有 3 个 M2 脚本；10 个预留脚本目录、3 个数据目录全空 | §4 | 按 VerticalSlicePlan M3–M7 首次实现**真实功能**，不为“预留”建空抽象（Architecture §9.7 同结论） | DSH（纯逻辑）+ Codex（场景/UI 集成） |
| P-06 | S1 | 服务端零实现，而 DataSchema 已冻结 9 类权威命令 | §6 | 由 ai-engineer 按 `Docs/DataSchema.md` 实现最小 `/api/v1` 骨架 + MockAIProvider；DSH 只提供契约核对与测试用例 | ai-engineer / Codex |
| P-07 | S2 | HUD 是 `OnGUI` 硬编码中文占位，无本地化与数据驱动结构 | `M2InteractionHud.cs` | 替换为数据驱动 UI（ScriptableObject + TMP），把文案移出代码；WebGL 侧 IMGUI 与 IME 均有风险 | Codex（UI 框架） |
| P-08 | S2 | 贴图 160 MB 流数据 + 15.76 MB 未子集化字体 | §6、§3 | WebGL 侧：2K→1K/BC7、字体子集化或静态 SDF atlas；Windows 侧保持 | art-director（资产）+ DSH（预算脚本） |
| P-09 | S2 | `InteractionKind {Counter, Item, Npc}` 三类不足以承载 M4 的 15 类 UI 与证据部件 | `M2Interactable.cs` | 在 M3/M4 前由 Codex 定型交互/证据数据模型（引用 `Docs/Chapter01ImplementationMap.md` 的 E01–E05 部位） | Codex + narrative-designer |
| P-10 | S2 | Unity 编辑器正在运行并锁住工程（PID 8272），无法并行 batchmode 构建 | `Library/EditorInstance.json`、`Get-Process Unity` | 构建脚本须先探测锁并明确报错；CI/构建时要求关闭编辑器 | DSH（脚本）+ 用户（操作） |
| P-11 | S3 | 文档口径不一致：M0/M1 报告“409 对象” vs 场景文件 185 GameObject | §3 | 报告中固定口径（场景自有对象 / 含 Prefab 展开对象分别记录） | Codex / Director |
| P-12 | S3 | 根目录游离 `profile` 文件；`Docs/Backups/` 内有 447 KB 旧场景 | §7 | 清理需 Director 授权；`.gitignore` 可先忽略 `profile` | Director |
| P-13 | S3 | `Builds/` 被 `.gitignore` 忽略，当前无“可发布产物”目录约定 | `.gitignore` | 约定 `Builds/WebGL/<version>/` 为唯一发布源，并保留 `manifest.json`（字节数+SHA256）作为部署凭证 | DSH |
| P-14 | S3 | 磁盘余量 15.1 GB（G:），WebGL 构建中间产物 + 失败重试可能吃紧 | `Get-PSDrive G` | 构建前由脚本检查剩余空间并报门槛（建议 ≥ 20 GB） | DSH |
| P-15 | S3 | 没有 WebGL 构建脚本、模板、服务器配置 | 全量枚举 | 见 BuildAndDeploymentPlan.md；脚本放在 `Tools/Build/`，不碰 Assets | DSH |

---

## 9. 已执行的验证（可复现）

1. 读取 `ProjectSettings/ProjectVersion.txt` → `6000.3.29f1 (96d2fe17529c)`。
2. 读取 `Packages/manifest.json` / `packages-lock.json` → HDRP 17.3.0 builtin，无 URP。
3. 读取 `ProjectSettings/{ProjectSettings,QualitySettings,GraphicsSettings,EditorSettings,VersionControlSettings,EditorBuildSettings}.asset` → §2 表格全部数值。
4. `Library/EditorInstance.json` + `Get-Process Unity` → 编辑器运行中（PID 8272/23388/24584，自 8:04 起）。
5. 枚举 PlaybackEngines → `WebGLSupport` 与 `windowsstandalonesupport` 存在。
6. 场景类计数（185/332/60/36/3/6/45/48/41/20）与根节点、`GlobalVolume` 引用（第 23664 行）。
7. 30 个 `.cs` 清单、3 个运行时文件全文阅读、asmdef 内容。
8. 测试用例名清单（EditMode 2 + PlayMode 5）。
9. `Builds/*` 总字节与 `Builds/M2/Station_Data` 头部文件尺寸、`boot.config`。
10. `Server/` 三文件内容；`Tools/M1_5/` 脚本清单。
11. Git：`git log`、`git status --porcelain`、`.gitattributes` 不存在。
12. HDRP 包缓存：`.compute` **148** 个、`UNITY_WEBGL` **0** 处、`SHADER_API_GLES3` **0** 处（`Library/PackageCache/com.unity.render-pipelines.high-definition@2d37db618c5e`）。

---

## 10. 未验证事项（明确未做）

| 项 | 原因 | 谁来验证 |
| --- | --- | --- |
| 打开工程、进入 Play、重跑 EditMode/PlayMode 测试 | 编辑器由用户/Codex 会话占用（PID 8272）；DSH 不接管正被占用的编辑器，也不并发打开同一工程 | Codex 或用户 |
| Windows 构建 | 同上；且当前已存在 4 个历史构建，无新增需求 | Codex |
| WebGL 构建（成功或失败） | 编辑器被占用 + HDRP 平台不支持（见 WebGLCompatibility.md）；**DSH 未执行任何 WebGL 构建，也没有声称成功** | 需用户在关闭编辑器、获批 URP 路径后执行 |
| 场景内光源/渲染器启用数量精确值 | 仅能静态计数组件；启用状态需编辑器读取 | Codex |
| `Docs/Chapter01ImplementationMap.md` 的 E01–E05 与 15 类 UI 细节 | 本轮只核对了文件存在与大小（35,704 B），未逐条比对实现 | narrative-designer + Codex |
| ModelScope 创空间上传体积/端口限制 | 仅查第三方教程，官方限制未核验（见部署文档「待确认」） | 用户/发布执行人 |
| 服务器/模型调用 | 服务端为空壳，无任何可运行代码 | ai-engineer |

---

## 11. 下一步任务（按顺序）

**DSH 可独立完成（不碰场景/Prefab/ProjectSettings）**

1. 纯逻辑 C# 模块 + EditMode 测试：证据/线索状态机、9 类命令的请求/响应 DTO、幂等与版本校验（放进 `Assets/_Project/Scripts/Core|Evidence|Investigation/` 新文件，需 Director 分配唯一写入者）。
2. `Tools/Build/` 构建与预检脚本（本报告配套，已交付）。
3. WebGL 体积预算脚本（贴图/字体/包体统计）与部署产物清单生成。
4. 文档：模块依赖图、可迁移性矩阵、与 `Docs/DataSchema.md` 的契约一致性核对。

**必须 Codex 处理**

1. P-02 渲染管线路线决策与 URP 浏览器工程（需用户批准）。
2. P-03/P-04 场景与 Build Settings 清理；任何 `Station.unity` 改动。
3. P-07 UI 框架替换（TMP + 数据驱动），Prefab 结构。
4. P-09 交互/证据数据模型定型与场景挂接。
5. P-01 Git 基线与 LFS（或交 Director 指定唯一写入者）。

**需要用户决策**

- 是否为浏览器版另建 URP 工程（Architecture §9.6 已给建议，尚未批准）。
- Git 基线/`.gitattributes`/zip 归属是否由本次窗口执行。
