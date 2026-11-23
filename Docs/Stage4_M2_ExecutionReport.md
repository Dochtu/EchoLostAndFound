# 阶段四 M2 · 玩家控制与场景探索

## 交付范围

在 M1.5-R1 的 Station 上新增第一人称探索。用户本次有条件的 M2 开发授权是本轮的阶段依据。场景仍使用 Unity 6000.3.29f1、HDRP 17.3.0，输入来自既有 Input System 1.20.1 动作资产。美术采购支出为零。

## 操作与验收入口

打开 [Station](../Assets/_Project/Scenes/Station.unity) 并进入 Play，或运行 [Windows x64 Development Player](../Builds/M2/Station.exe)。玩家出生在失物招领处柜台前。WASD 行走，鼠标转头，准星对准近处实体时出现中文名称与 E 提示。E 打开查看页或交谈页，Esc 返回探索。由柜台身后门洞进入候车大厅，绕过排椅，通过大厅东侧门洞可到达站台内侧。

| 证据 | 验证内容 |
| --- | --- |
| [完整往返录像](Evidence/Stage4_M2/Route.mp4) · [途经点](Evidence/Stage4_M2/Route.log) | 从出生位置连续步行至站台，转身后返回柜台。1280×720、24 fps、787 帧，32.79 秒 |
| [四对象交互录像](Evidence/Stage4_M2/Interaction.mp4) · [对象日志](Evidence/Stage4_M2/Interaction.log) | 依次瞄准怀表、登记册、柜台和站内旅客，按 E 打开各自页面并用 Esc 关闭。1280×720、24 fps、526 帧，21.92 秒 |
| [柜台前](Evidence/Stage4_M2/Office.png) · [站台](Evidence/Stage4_M2/Platform.png) · [怀表预览](Evidence/Stage4_M2/WatchPanel.png) · [旅客交谈](Evidence/Stage4_M2/VisitorPanel.png) | 从实际 Play Mode Game View 读回，保留当帧准星、对象提示或交互界面 |
| [EditMode](Evidence/Stage4_M2/EditMode.xml) · [PlayMode](Evidence/Stage4_M2/PlayMode.xml) · [独立 QA](Evidence/Stage4_M2/IndependentQA.md) | Unity Test Runner 原始结果与 QA 复核 |
| [编辑器执行记录](Evidence/Stage4_M2/EditorJobs.log) | 记录安装、重开、测试、录制及构建批次。早期失败留在时序日志中 |

录像使用虚拟键鼠提交 Input System 设备事件。真实玩家组件处理移动、转身和交互，录制器逐帧读取 Game View，在结束后编码视频。录像采用固定模拟帧率，运行性能单独在 Windows Player 中测量。

## 工程修改

| 唯一写入职责 | 文件与实际行为 |
| --- | --- |
| 控制与交互 | [M2Player.cs](../Assets/_Project/Scripts/M2/M2Player.cs)、[M2Interactable.cs](../Assets/_Project/Scripts/M2/M2Interactable.cs)、[M2InteractionHud.cs](../Assets/_Project/Scripts/M2/M2InteractionHud.cs)、同目录 asmdef 与 .meta。移动速度 2.6 m/s，鼠标灵敏度 0.12°/像素，俯仰 ±80°，交互距离按眼位到命中面计算，上限 2.4 m |
| 场景集成 | [M2Player.prefab](../Assets/_Project/Prefabs/Player/M2Player.prefab)、[增量安装器](../Assets/_Project/Editor/M2StationSetup.cs) 及 .meta；保存原 Station。启用玩家相机和监听器，保留预览机位。补齐连续地面、门洞两侧、排椅、柱体、站台边界及对象碰撞 |
| QA | [EditMode 用例](../Assets/_Project/Tests/M2/EditMode/M2EditTests.cs)、[PlayMode 用例](../Assets/_Project/Tests/M2/PlayMode/M2PlayTests.cs)、两个测试程序集及相关 .meta |
| 取证与构建 | [编辑器执行入口](../Assets/_Project/Editor/M2EvidenceEditor.cs)、[键鼠回放与采样](../Assets/_Project/Tests/M2EvidenceReplay.cs) 及 .meta；本报告与证据目录 |

交互探针选择最近的外部实体，只在击中的实体或其父级具有交互接口时显示提示。墙面、玻璃及家具可阻断射线。触发器不遮挡视线。按下 E 的当帧再次使用实时命中结果。界面打开期间禁用移动、转向和交互动作，释放光标并启用返回动作。关闭后恢复探索输入和光标锁定。占位页面使用工程已有的思源黑体。

`IInteractable` 提供显示名称与对象类型，`InterfaceOpened`、`InterfaceClosed` 为以后替换展示层保留入口。本轮交互不写入 E/D/R/A，不产生证据、章节、信任或对话状态。NPC 使用场景样板名称“站内旅客”。

## 联调修正

- QA 检出复制预览相机时带入了原镜位。修复后 Prefab 眼位固定在胶囊局部 (0, 1.65, 0)，局部旋转为单位旋转，并增加回归断言。
- 实际录制发现，斜看柜台时射线先在 0.075 m 命中自己的胶囊，柜台位于 1.759 m。修复后保持原眼位，排除玩家自身层级，再选最近外部表面。四个真实场景对象均经 E 和 Esc 验证。
- 西墙阻挡测试最初在通过两道门并返回后，沿办公室内一条有实体遮挡的路径接近测试点。QA 调整至大厅内可达位置，检查连续推向西墙后的实际停靠范围。

## M8 美术登记

| 延后问题 | M8 复查范围 |
| --- | --- |
| NPC 外观 | 发丝轮廓、双颊层次、正面站姿与鞋底接触 |
| 建筑细节 | 候车大厅远景层次、座椅与暗部材质辨识度 |
| 雨夜环境 | 雨丝尺度、湿面反射重复感和站台远景 |

保留 [R1 执行记录](M1_5_R1_ExecutionReport.md) 和 [独立视觉验收](Evidence/M1_5_R1/IndependentQA.md) 作为 M8 对照基线。
