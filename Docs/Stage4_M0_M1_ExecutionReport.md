# 阶段四 M0＋M1 实施验收

2026-11-21，Windows PC，第一章车站视觉样段。

**M0 PASS，M1 PASS。** 19:55:36 保存最终场景，19:56:26 从磁盘重新打开，19:56:57 完成最终取证。独立 QA 26 项全部通过。9 张指定 PNG 已逐张复核，最终 Console 为 0 错误、0 警告。

## 打开与复现

在 Unity 6000.3.29f1 中打开 [Station.unity](../Assets/_Project/Scenes/Station.unity)，按 Play 从大厅相机观看。展开 Station 下的 Cameras / ShotAnchors 可查看五个镜位。Hierarchy 中选择一个区域网格并按 F 可以定位该模块。

| 编辑器菜单 | 用途 |
| --- | --- |
| Tools → Echo → Run HDRP Baseline | 打开校准场景、进入 Play、保存基线画面 |
| Tools → Echo → Build Station | 按当前美术源码重建本样段的专属场景、模型和预制件，再从磁盘重开 |
| Tools → Echo → Validate open Station scene | 独立检查当前打开的 Station，并写入 QARuntime.log |
| Tools → Echo → Validate Station and Capture Game View | 重开保存的场景、检查资源、进入 Play、按镜位取图，最后记录编辑器窗口 |

重建会重写生成器管理的 Station 资产。仅观看或验收时可以直接使用已保存的场景。截图工具在 Windows 的交互式 Unity Editor 中运行。

## M0 工程与渲染基线

版本文件记录 Unity 6000.3.29f1（96d2fe17529c）。manifest、lock 与本地包确认 HDRP 17.3.0。Input System 1.20.1、Cinemachine 3.1.7、AI Navigation 2.0.16、Timeline 1.8.13、ProBuilder 6.1.4、uGUI 2.0.0。Graphics 使用 HDRenderPipelineAsset，并已注册 HDRenderPipelineGlobalSettings。Quality 的 High Fidelity、Balanced、Performant 分别引用对应 HDRP 资产。实测为 High Fidelity、Linear、Direct3D 12。

OutdoorsScene 原有 7 个对象、6 个根节点、9 个可解析的脚本引用，含 Main Camera、Sun、Sky and Fog Volume、Canvas。场景内有 0 个 MeshRenderer。保存的 Scene View 焦点约在 (−12.44, −41.09, 77.43)，视野尺度约 160。这个位置和场景内容足以解释编辑视图显得空旷。原场景 SHA-256 为 `B425C5F68DACC69E4DF8365E57B4EC9E2F54BF1E58B7FD57EF39D08FDE6EF5B4`，本轮复核一致。

校准场景使用 HDRP Lit 接收面、球、立方体和胶囊，配方向光、点光、聚光、反射探针、固定曝光、ACES 和雾。经编辑器保存并从磁盘重开，10 个根节点，Missing Script 为 0。Play Mode 中通过 Calibration Camera 取得 1101×534 的基线图，三种表面轮廓、高光和投影可辨。画面为偏亮的雾天基线。Console 在取图时为 0 错误、0 警告。[基线图](Evidence/Stage4_M0_M1/00_GameView_HDRP_Baseline.png) · [基线日志](Evidence/Stage4_M0_M1/BaselineRuntime.log)

## 场景结构与可复用资源

```text
Station
  Environment
    LostAndFound        室内建筑、柜台、物品架、储物柜、档案
    WaitingHall         桶形拱顶、铸铁柱、窗框、长椅、西值班窗
    Platform            雨棚、檐口、轨道、排水沟、雨洼、维修柜
  Characters            NPC_VisualSample
  Props                 PocketWatch
  Lighting              GlobalVolume、InteriorLights、ExteriorLights、ReflectionProbes
  Weather               OpenPlatformRain、RoofDrips
  Cameras               StationPreviewCamera、ShotAnchors
  SceneSystems
```

大厅内宽约 12 m、长约 20 m，拱顶最高约 7.4 m。西侧门洞接失物室，东侧门洞接站台。建筑网格由面片、截面、梁、圆柱及檐口构件生成，按功能合并为有材质分组的持久 Mesh。柜台以实木面、包边和框板结构组成，带台灯、台垫、失物包和登记册。站台区分棚下地面、露天湿带、排水沟、独立雨洼、边缘、安全隔栏、枕木及双轨。雨丝与檐滴使用不同发射范围。

怀表表壳约 55 mm，有表盘玻璃、表针、刻度、表冠、侧冠损伤、偏斜冠轴及表链。九点十七分对应时针 278.5°、分针 102°。背刻为「0412·0916」，后盖边钢印为「QH-283」。西窗人物是可替换的 Visual Placeholder，有独立头部、躯干、手臂、手、腿、鞋和服装材质，并留有 Animator。脸型和服装不作为叙事设定。

逐件路径、类型、来源、许可、占位标记和 .meta 路径见 [资源清单](Stage4_M0_M1_AssetManifest.csv)。程序生成的建筑、表面纹理和模型均落盘。中文牌使用工程既有思源黑体排印。后端、案件规则和 M2 控制系统均未进入本次制作范围。

## 证据索引

| 序号 | 证据 | 来源 |
| --- | --- | --- |
| 00 | [HDRP 校准场景](Evidence/Stage4_M0_M1/00_GameView_HDRP_Baseline.png) | Play Mode，校准相机 |
| 01 | [候车大厅](Evidence/Stage4_M0_M1/01_GameView_StationOverview.png) | Play Mode，Station_MainHall |
| 02 | [失物室柜台](Evidence/Stage4_M0_M1/02_GameView_LostAndFound.png) | Play Mode，Station_LostFound |
| 03 | [怀表](Evidence/Stage4_M0_M1/03_GameView_PocketWatch.png) | Play Mode，Station_Watch |
| 04 | [人物样板](Evidence/Stage4_M0_M1/04_GameView_NPC.png) | Play Mode，Station_NPC |
| 05 | [雨夜站台](Evidence/Stage4_M0_M1/05_GameView_PlatformRainNight.png) | Play Mode，Station_Platform |
| 06 | [Game 标签与播放状态](Evidence/Stage4_M0_M1/06_Editor_GameView_PlayMode.png) | Unity Editor 窗口，播放中 |
| 07 | [Scene 与 Hierarchy](Evidence/Stage4_M0_M1/07_Editor_SceneHierarchy.png) | Unity Editor 窗口，编辑状态 |
| 08 | [Console](Evidence/Stage4_M0_M1/08_Editor_Console.png) | Unity Editor 窗口，编辑状态 |

首次制作中触发过 TextMeshPro 替换 Transform 后的 MissingReferenceException。修复方式是在创建文字时直接使用 RectTransform，再保存预制件。首次站台组图采集因后台等待超时，后续在交互式编辑器聚焦 Game 标签、恢复绘制并逐镜头读取帧状态。

## 文件变更和资产归属

资源清单共 114 条，含 106 条本阶段资产及 8 条既有依赖。阶段资产包括 2 个 Scene、7 个 Prefab、37 个材质、37 个 Mesh、15 张纹理、2 个 Volume Profile 和 6 个 Editor 脚本，每条均有对应 .meta。窗口取证、基线、独立检查及运行日志位于证据目录。

| 写入者 | 交付内容 |
| --- | --- |
| Unity Engineer | Station、Stage4Baseline 场景，三区域、柜台、NPC、怀表和雨水预制件，场景生成器、校准器、夜景 Volume 和牌面资源 |
| Art Director | Stage4StationArt，材质、表面纹理、怀表和 NPC 的原型网格 |
| Game Director | Stage4Architecture，十组建筑网格、资源清单、报告、汇总日志 |
| QA Engineer | Stage4SceneValidationTests、Stage4GameViewCapture、逐项检查、运行指标和取证 |

- ProjectSettings/EditorBuildSettings.asset 经 Unity Editor API 添加首个启用场景 Station。与[设置备份](Evidence/Stage4_M0_M1/EditorBuildSettings.before.txt)比较，仅多三行启用值、路径和 GUID。原 OutdoorsScene 仍在列表内。
- 编辑器运行期间，Assets/SourceHanSansSC-Regular SDF.asset、Assets/TextMesh Pro/Resources/Fonts & Materials/LiberationSans SDF.asset 以及 ProjectSettings/Packages/com.unity.probuilder/Settings.json 的写入时间发生变化。项目没有初始 Git 提交，未能确认这三项的逐字节差异。没有执行包升级。
- 根 .gitignore 给四份指定验收日志增加例外，便于后续版本管理。本次没有暂存、提交或推送。

## QA 范围

以保存后的 Station 为输入，检查实际管线、全部对象的 Missing Script、网格引用和启用的非粒子 Renderer 材质、主相机、五个镜位、Volume、HDRP 灯、反射探针、两个雨水系统和预制件连接。对两处门洞使用不同高度和横向位置的测试射线，核验可视建筑几何留出了通道。怀表检查两枚指针角度和两处刻印，人物检查四肢及世界坐标包围盒。运行画面另行检查雨粒子材质、中文牌可读性、手脸与地面接触、积水反射和光照层次。[逐项结果](Evidence/Stage4_M0_M1/QARuntime.log)

最终场景共 409 个对象，308 个启用的非粒子 Renderer 通过材质引用检查，7 个预制件实例连接有效。人物实测高 1.717 m，鞋底距地面 0.001 m。最终图中，失物室中文牌、柜台包签和登记册可读，怀表全链和尾扣入镜，站台干区、露天雨线与湿地暖色倒影可以分别辨认。

## 最终光照和天气

StationNight 独立设置固定曝光 4.95 EV、ACES、白平衡、对比度、渐变夜空及体积雾。雾的平均自由程 62 m，最大高度 19 m。26 个 HDRP 光源中包括冷色月光、暖色吊灯、盖下工作灯、人物补光及站台低位灯。大厅、柜台和站台各有一个启用时更新的实时反射探针。露天雨幕和檐口独立发射，降雨边界位于棚外，棚内保留干地。水面有低强度法线与局部粗糙度，14 处异形积水共用保存的网格模块。雨、雾和镜头均由环境系统驱动。

## 实测性能

AMD Ryzen 7 8745H、NVIDIA GeForce RTX 4060 Laptop GPU，High Fidelity，DX12。最终五张相机图均为 1920×1080，三张编辑器窗口图均为 1936×1096。计数来自切换镜位后短时间取样。[原始运行记录](Evidence/Stage4_M0_M1/StationRuntime.log)

| 镜位 | 采样帧 | 平均 FPS | 最长帧 ms | CPU 主线程均值 ms | GPU 均值 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 大厅 | 88 | 49.2 | 306.3 | 18.7 | 17.0 |
| 柜台 | 144 | 94.9 | 12.1 | 8.9 | 10.5 |
| 怀表 | 130 | 86.0 | 13.4 | 10.1 | 11.6 |
| 人物 | 122 | 80.9 | 13.9 | 10.8 | 12.3 |
| 站台 | 112 | 74.2 | 15.2 | 11.8 | 13.4 |

首轮较低分辨率进入大厅时曾记录 6443.6 ms 长帧。最终大厅仍有一次 306.3 ms 停顿，其余四个镜位在最终采样中均无超过 100 ms 的帧。大厅样本中主线程耗时高于 GPU，其余镜位的 GPU 均值稍高。尚无 Profiler 时间线可以把启动停顿归因到具体着色器、探针、磁盘或编辑器开销。

## 范围与后续

本次验证针对 Windows Unity Editor 中的 High Fidelity 档。独立 Windows Player 构建、其他质量档、长时间运行、低配显卡和玩家控制器碰撞尚未实测。M2 接手时可沿实际连通门洞选定出生点、回访点和碰撞边界，分别验证角色净高、通行宽度、交互距离及站台隔离。是否进入 M2 由用户验收后决定。
