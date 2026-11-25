# M4-C-G WebGL 运行质量核查

**验收场景在真实 GPU 上可玩。** 正常窗口 Chrome 157.0.8103.79 报告 WebGL 2.0、ANGLE、NVIDIA GeForce RTX 4060 Laptop GPU、Direct3D11。浏览器从 F 盘恢复的 gzip 包加载游戏。两条 A02 路线、确认前回退和刷新后的回执均通过，软失败、JS 异常、浏览器对话框和 HTTP ≥400 均为 0。[硬件章末操作记录](M4CG/gpu-chapter/browser.json) · [刷新后回执](M4CG/gpu-chapter/08-persisted-settlement.png)

## 性能与画面

两次测试使用同一游戏包、本机同源 Mock、独立浏览器配置，在初始车站视点、页面可见且加载完成后采样约 10 秒。在 requestAnimationFrame 回调间统计发生 WebGL 绘制调用的帧，计算帧数/实际时长和绘制间隔 P95。此数值描述单次浏览器绘制采样，不是显示器呈现统计、Unity GPU profiler 耗时或全章最低帧率。

| 渲染路径 | 有绘制的帧 / 时长 | 帧率 | 帧间隔 P95 | 首次加载条消失 |
| --- | ---: | ---: | ---: | ---: |
| 正常窗口 Chrome，RTX 4060 / D3D11 | 601 / 10.001 秒 | 60.10 FPS | 16.9 ms | 1.508 秒 |
| Headless Chrome，SwiftShader / Vulkan | 112 / 10.075 秒 | 11.12 FPS | 100.1 ms | 1.079 秒 |

硬件截图可辨认站内标牌、柜台、人物、怀表、中文 HUD 与交接文字，观察画面中未见整屏黑屏或明显粉色错误材质。软件渲染能够加载和打开 NPC，对照帧率显著较低。两次测试还同时改变了有无窗口条件，差值不能单独归因于 GPU。[硬件采样](M4CG/gpu/browser.json) · [软件采样](M4CG/software/browser.json) · [硬件车站截图](M4CG/gpu/01-station.png) · [NPC 面板](M4CG/gpu/02-npc-opening.png)

## 五项日志核查

下表计数顺序为“本轮硬件章末路线 / 上次同包 SwiftShader 章末路线”。本轮硬件与软件各一次开局对照，同样复现前三项各一次，仅软件出现 Cookie 回退。前三项经 Unity 输出为 Chrome console log；检查 console.error 数量会漏掉这些消息。[硬件章末日志](M4CG/gpu-chapter/browser.json) · [同包软件章末日志](M4C/Closeout/browser-01/browser.json)

| 观察项 | 次数 | 依据与结论 |
| --- | ---: | --- |
| Hidden/CoreSRP/CoreCopy | 4 / 4 | 两种渲染路径均报告无可用 subshader。CoreCopy 含 Copy 与 CopyMS，后者指定 target 4.5、msaatex。构建日志显示 gles3 变体被编译并序列化。尚未定位运行时拒绝的具体 pass、能力或变体。 |
| Hidden/Universal Render Pipeline/StencilDitherMaskSeed | 4 / 4 | URP 17.3 的 shader 声明 target 4.5，构建日志含其 gles3 编译记录。硬件亦复现，已测可玩路径未出现可见遮罩故障。专用 stencil 路径未单测。 |
| Hidden/Universal/HDRDebugView | 4 / 4 | 包内为 HDR 调试视图，含 target 4.5、DEBUG_DISPLAY 变体。真实硬件同样报告不支持。当前场景正常显示，未验证 HDR 调试视图功能。 |
| Additional Lights Cookie Format | 0 / 4 | WebGL 默认质量级 0 引用 Mobile_RPAsset，GrayscaleHigh 对应 R16_UNorm。URP 使用 SystemInfo.IsFormatSupported(..., Render) 筛选，无可用格式则回退 RGBA8 UNorm。SwiftShader 实际打印此回退，RTX 未打印。检查到 Station 已序列化灯光的 cookie 引用为空。 |
| 手动同步 persistentDataPath 弃用 | 3 / 3 | 两端在保存/刷新路线均出现。交付 index.html 中 config.autoSyncPersistentDataPath 为注释状态。Unity 消息指向旧同步机制；源码扫描未找到自定义 JS_FileSystem_Sync 调用。存档在本轮实际刷新后可恢复，弃用仍需跟踪。 |

诊断依据为已安装的 SRP/URP 17.3.0 源码、项目设置与该包构建日志。三个隐藏 shader 的最终兼容性根因仍有未验证部分；单次通章不足以证明所有渲染功能均兼容。本轮保留原管线配置、着色器和存档机制。[实际构建日志](M4C/Closeout/final-Build.log) · [WebGL 质量设置](EchoLostAndFound_WebGL/ProjectSettings/QualitySettings.asset) · [移动管线资源](EchoLostAndFound_WebGL/Assets/Settings/Mobile_RPAsset.asset)

## Windows 中文 IME

**UNVERIFIED**，覆盖拼音输入、候选词显示、选词确认上屏、发送及退出输入框。已在真实硬件 Chrome 打开老周对话、点击输入区并尝试原生输入。Windows 前台窗口归属检查未确认当前接收输入的窗口属于隔离测试 Chrome，探针记录 sent=[]、nativeEvents=[]。本轮没有可用于判定真实系统候选窗与上屏行为的证据。历史 CDP 逐字发送中文的通过结果仅覆盖提交后的字符流。[探针记录](M4CG/gpu/browser.json) · [尝试时窗口](M4CG/gpu/03-native-input.png)
