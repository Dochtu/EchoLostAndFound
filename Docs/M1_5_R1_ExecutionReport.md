# EchoLostAndFound · M1.5-R1 定向返工

**阶段结论为 PARTIAL。仍未满足进入 M2 的条件。** 本轮沿用现有 Station、人物 Avatar、剧情身份和证据，仅更新已确认的视觉及渲染问题。零预算，Unity 6000.3.29f1、HDRP 17.3.0。全部对照原图取自 M1.5 交付包，R1 图取自 1920×1080 High Fidelity Game View。

## 人物

沿用 MakeHuman CC0 样板和原 FBX 的 GUID。Blender 为三层发束新增 715 束几何，调整 186 个眼睑顶点及 5,703 个衣物顶点，衣褶最大位移 7.74 mm。头部、肩臂和手加入不对称微动作。Unity 确认原 Avatar 有效、64 骨模型仍有八个蒙皮部件，4 秒 Humanoid Idle 可循环。侧上方局部聚光、软阴影和皮肤光滑度重映射用于改善脸部与鞋底接触。近景中发束与眉睑可辨，受限于原发型体积与皮肤底图，人物仍是通用样板。

4.083 秒视频包含 98 张连续的实际 Game View 帧，按每秒 24 帧的固定模拟步长采集并编码。Animator 归一化时间由 0.0000 到 1.0104，完整覆盖一个循环。视频录制与性能采样分别运行。[人物对照](Evidence/M1_5_R1/NPC_Comparison.png) · [面部近景](Evidence/M1_5_R1/Face_Closeup.png) · [完整 Idle](Evidence/M1_5_R1/Idle.mp4) · [采集日志](Evidence/M1_5_R1/Capture.log)

## 大厅和站台

保留拱顶、柱列和通行路线。大厅远端门增加门套、黄铜踢板和两侧散热器，侧窗补光与门厅斜照塑造明暗层次。降低水磨石颗粒反差与法线强度，原有家具继续使用。站台保留雨棚和轨道，远景增加扶壁、压顶与厂房屋面轮廓，地面光滑度沿檐线变化，将雨幕分成两个不同密度、大小和透明度的层次。[大厅对照](Evidence/M1_5_R1/Hall_Comparison.png) · [站台对照](Evidence/M1_5_R1/Platform_Comparison.png) · [编辑器播放状态](Evidence/M1_5_R1/PlayMode.png)

## 工程与复测

原 M1.5 交付包作为安装基线。R1 增量包在其上覆盖同名文件并添加新资源。相机、场景和原资源保留 GUID。新增环境物件和发束由 Blender 本地自制，贴图加工沿用已记录 CC0 来源。共享 HDRP、Packages 和 ProjectSettings 已与执行前备份逐字节核对。没有新增模型服务、付费依赖或游戏玩法。[资源清单](M1_5_R1_AssetManifest.csv) · [免费许可记录](M1_5_R1_FreeAssetManifest.csv) · [场景重开日志](Evidence/M1_5_R1/Reload.log)

以现有 Station 进入 Play 可检查场景。用于复现取证的 R1Station 编辑器工具从 Library/R1Baseline/action 读取一次性指令。capture 使用已保存的场景采集四张正式镜位和完整 Idle 序列。build 仅构建当前场景的 Windows Development Player。该构建包含帧计时支持；独立 Player 使用 -r1-benchmark -r1-output 后接新的输出目录，-r1-off-first 调换 VSync 顺序，-r1-profile 在测量后另录 CPU Profiler。每个输出目录对应一次独立进程。[性能报告](M1_5_R1_Performance.md) · [独立 QA](Evidence/M1_5_R1/IndependentQA.md)

## 验收结果

三组共 12 段独立 Player 采样，P95 为 16.63–19.04 ms，全部低于 25 ms，采样段中超过 100 ms 的帧为 0。VSync 开启时平均 59.51–60.00 FPS；关闭时平均 56.74–63.76 FPS。固定机位的 VSync 开启 P95 从 M1.5 两轮的 33.3 ms 缩短到 16.68–16.69 ms。部分场景段仍低于 60 FPS，按用户阈值保留 PARTIAL。三次启动均出现一次 D3D12 环形缓冲区空间警告。

独立 QA 通过了实际面部取景和完整动画的证据核验。人物固定镜位的发丝边缘、面颊层次及正面站姿仍需改善。大厅和站台的局部改进已可对照，整体阶段继续停留在 R1。
