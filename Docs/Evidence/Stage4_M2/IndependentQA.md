# M2 独立 QA 验收

## 检查范围

本次检查覆盖 Station 中的玩家 Prefab、两处门洞、调查对象、键鼠输入与占位界面。美术升级归入 M8。此轮没有证据登记、案情判断或 NPC 剧情对话验收。

| 测试 | 验收判据 |
| --- | --- |
| StationUsesConnectedPlayerPrefabAndSingleActiveEye | 场景复用玩家 Prefab，具有 CharacterController，第一人称 Camera 和 AudioListener 各启用一个 |
| EachStationInteractionHasDistinctVisibleNameAndSolidHitSurface | 柜台、怀表、登记册及 NPC 各有名称和可命中实体 |
| ProbeHonoursSurfaceDistanceNearestHitAndBlockingGlass | 两个目标只返回最近者，1.50 m 的表面在 1.49 m 射程外、1.51 m 射程内，实体玻璃遮挡，非实体触发器允许看穿 |
| CapsuleWalksBothDoorwaysReturnsAndCannotCrossWestHallWall | 在真实 Station 用逐步 CharacterController.Move 往返穿过两处门洞，保持地面高度，西墙挡住持续前进 |
| ReachAllFourAuthoredTargetsFromPlayableEyeHeight | 真实玩家眼高使用鼠标瞄准，四个实景对象显示正确名称，E 进入各自界面并可 Esc 返回 |
| AllFourMovementKeysFollowThePlayersHeading | 开阔地分别按 W、A、S、D，与人物前、左、后、右方向角偏差小于 2° |
| RealInputDrivesPlayerButStopsDuringPreviewAndDialogue | 虚拟键鼠向 Input System 提交状态事件。确认位移、转头、上下限、提示消失当帧 E 被实体阻断。两种界面都冻结走位和转头，解除光标锁定，Esc 返回 |

编辑器测试使用独立测试程序集。临时遮挡物与虚拟输入设备均只存在于 Play Mode。胶囊路线覆盖场景碰撞，全程由输入驱动的通行另检查录像。单靠注册测试和源代码不能核准 M2。

## 当前结果

编辑器内 TestRunnerApi 按 M2 分组使用既有测试包运行。09:01:19 的 EditMode 两例全过。09:04:33 PlayMode 加入实景交互后的四例全过。最终五例批次将独立核对 XML。

- 初次 PlayMode 测试在已完成标准路线往返后，尝试沿办公室 x=−7.20 接近西墙。该路径在 z=−4.19 遇到实体。修改独立墙测的接近路径，从大厅走向西墙 z=−4.85 处，持续西移约 3.6 m 的输入量后，胶囊中心停在 x=−5.85 至 −5.45 的墙面预期范围内。
- 初次 Prefab 独立源审发现 PlayerCamera 局部位置为 (2.10, 1.67, −8.65)，眼睛偏离碰撞胶囊。修复 Camera.CopyFrom 后的变换重置，重新生成 Prefab，确认局部位置为 (0, 1.65, 0)。新增眼高及横向偏移检查，重跑全部五个用例通过。
- 09:01 比对 616 条开发前文件散列，385 个既有 .meta 均吻合。69 个 .mat、25 个 .fbx 等清单内美术资源吻合。发现 ProBuilder Settings.json 变化，已通知 Director 核对。

- 实景交互首录发现，朝柜台抽屉俯视按 E 没有提示。射线在 0.075 m 命中玩家自身胶囊，柜台在 1.759 m。探测器现只过滤玩家层级内的碰撞体，并从其余实体中取最近命中。四个实景物件通过新回归，柜台面板亦在实际录像出现。

## 影像复核

| 录屏 | 独立解码 | 画面、操作与日志 |
| --- | --- | --- |
| [路线](Route.mp4) | H.264，1280×720，24 fps，787 帧，32.792 s；SHA-256 前 12 位 b188284e0ca2 | 抽帧识别招领处、大厅、站台护栏，再看到大厅和柜台。日志记录站台 (9.90, 0.03, 0.95)，返程 (−8.29, 0.03, −4.28)，偏离出生点约 0.17 m，末行 PASS。 |
| [交互](Interaction.mp4) | H.264，1280×720，24 fps，526 帧，21.917 s；SHA-256 前 12 位 18ccdee1ba65 | 逐项瞄准怀表、登记册、柜台、站内旅客。镜头在大厅走近 NPC 后出现“E 交谈 站内旅客”，打开界面显示“站内交谈”；物品面板显示“物品预览”。四项开启、关闭日志齐全。 |

使用 ffprobe 解码计数、ffmpeg 全片解码与定时抽帧检查。录像的 24 fps 来自编辑器固定模拟步长。采集工具用虚拟鼠标与键盘提交 Input System 事件，人物转向和位移经过运行时控制器。可读原始界面见 [怀表](WatchPanel.png)、[柜台](CounterPanel.png)、[NPC 提示](VisitorPrompt.png) 和 [NPC 面板](VisitorPanel.png)。

## Windows Player

等待本轮 Windows 构建运行与性能原始记录。
