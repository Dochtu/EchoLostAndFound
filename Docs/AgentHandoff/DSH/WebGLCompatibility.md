# DSH WebGL 兼容性与风险报告 · EchoLostAndFound

**审计人**：DSH　**日期**：2026-11-23　**性质**：只读静态核查（**未执行任何 WebGL 构建**）
**基线**：Unity `6000.3.29f1`、HDRP `17.3.0`、工程 `G:\projects\EchoLostAndFound`

## 0. 结论（三句话）

1. **当前 HDRP 工程不能产出可运行的 WebGL 包**：HDRP 在 Unity 6.3 官方平台支持矩阵中不支持 WebGL/WebGPU；本地包缓存也显示 HDRP 依赖 **148 个 compute shader** 且 **0 处 WebGL 平台守卫**，WebGL2 无 compute 能力，构建会在很晚的 shader 编译阶段失败而不是提前报错。
2. **浏览器版必须另建 URP 工程/构建路径**（与 `Docs/Architecture.md` §9.6 的建议一致），共享**纯逻辑、DTO、内容标识、后端契约**，不共享 HDRP 材质/Volume/灯光/场景。该决定**尚未获用户批准**，本报告不授权安装 URP 或创建第二工程。
3. **包体与首屏**是第二道硬约束：现有 Windows 构建的贴图流数据 `Builds/M2/Station_Data/sharedassets0.assets.resS` 已达 **160.64 MB**，字体 15.76 MB。按现状直搬浏览器，首包远超可接受范围，必须做资产分层与降级规格。

---

## 1. 平台支持矩阵（本工程视角）

| 管线 | WebGL | WebGPU | 本工程现状 | 依据 |
| --- | --- | --- | --- | --- |
| HDRP 17.3.0 | **不支持** | **不支持** | 正在使用（`GraphicsSettings.m_CustomRenderPipeline` guid `b9f3086da92434da0bc1518f19f0ce86`） | [Unity 6.3 渲染管线兼容表](https://docs.unity.com/en-us/engine/6000.3/manual/render-pipelines/choose-a-render-pipeline/feature-comparison)；`Docs/Architecture.md:281` |
| URP | 支持 | 6.3 中 WebGPU 仍为实验 | **未安装**（`Packages/manifest.json` 无 `com.unity.render-pipelines.universal`） | 同上 |
| Built-in | 支持（不推荐新项目） | — | 未使用 | 同上 |

Web 技术限制（托管线程、计时、网络）见 [Unity Web 技术概览](https://docs.unity.com/en-us/engine/6000.3/manual/platform-specific/webgl/intro/technical-overview)、[Unity Web 网络](https://docs.unity.com/en-us/engine/6000.3/manual/platform-specific/webgl/develop/networking)、[Unity Web 图形 API](https://docs.unity.com/en-us/engine/6000.3/manual/platform-specific/webgl/develop/graphics)。

---

## 2. 本地证据：为什么不是"改个 Build Profile 就行"

| 证据 | 实测 | 含义 |
| --- | --- | --- |
| HDRP 包内 compute shader | `Library/PackageCache/com.unity.render-pipelines.high-definition@2d37db618c5e` 下 **148 个 `.compute`**（`GPUCopy.compute`、`ClearBuffer2D.compute`、`EncodeBC6H.compute`、`CloudMapGenerator.compute`…） | HDRP 光照/阴影/后处理/反射都经过 compute；WebGL2 无 compute shader |
| HDRP 包内 WebGL 守卫 | `UNITY_WEBGL` 命中 **0** 处、`SHADER_API_GLES3` 命中 **0** 处 | 没有编译期降级路径；构建不会早期失败，而是在 IL2CPP + shader 编译很久之后才炸 |
| 相机数据 | `Assets/_Project/Prefabs/Player/M2Player.prefab` 的 `PlayerCamera` 挂 **`HDAdditionalCameraData`** | 连玩家相机都是 HDRP 类型，换管线必须重建 Prefab 组件 |
| 场景表现层 | `Assets/_Project/Scenes/Station.unity` 的 `GlobalVolume`（第 23664 行）引用 `Assets/_Project/Settings/StationNight.asset`（guid `563d790104b13e64d80e1b003d18f7ba`），内含 **7 个 HDRP Volume 组件**：`VisualEnvironment`、`GradientSky`、`Fog`、`Exposure`、`WhiteBalance`、`ColorAdjustments`、`Tonemapping` | 天空/雾/色调映射是 HDRP 类型，URP 需重做 |
| 材质 | `Assets/` 下 **73 个 `.mat`**，全部引用 HDRP shader | 不能在 URP 项目里沿用 |
| 高质量档特性 | `Assets/Settings/HDRP High Fidelity.asset`：`supportSSGI: 1`、`supportSubsurfaceScattering: 1`、`supportSSAO: 1`、`supportScreenSpaceLensFlare: 1`、`supportRayTracing: 0`、`msaaSampleCount: 1`、`colorBufferFormat: 48` | SSGI/SSS 等 HDRP 特性在浏览器路径无对应实现 |
| 场景负荷 | 场景自有 **60 MeshRenderer / 36 Light / 3 ReflectionProbe / 6 Camera**，另有 Prefab 展开内容（`LostAndFound` prefab 引用 307 次、`PlatformRailPanel` 630 次、`ArchiveCarton` 285 次） | 3 个实时反射探针 + 体积雾 + 26 个启用光源属于桌面级预算 |

**可复现命令**（本次实际执行）：

```powershell
$p='Library\PackageCache\com.unity.render-pipelines.high-definition@2d37db618c5e'
(Get-ChildItem $p -Recurse -Include *.compute | Measure-Object).Count                                   # 148
(Get-ChildItem $p -Recurse -Include *.cs,*.hlsl,*.shader,*.compute | Select-String 'UNITY_WEBGL' | Measure-Object).Count  # 0
```

---

## 3. 当前 WebGL Player 设置逐项审计

来源：`ProjectSettings/ProjectSettings.asset`（第 813–838 行）。

| 键 | 当前值 | 含义 | 判断 / 建议 |
| --- | --- | --- | --- |
| `webGLMemorySize` | 32 | 初始托管堆 32 MB | 与 `webGLInitialMemorySize` 重复；后续统一用 Initial/Maximum |
| `webGLInitialMemorySize` | 32 | WASM 初始内存 | 偏低；HDRP 级纹理量下会频繁扩容 |
| `webGLMaximumMemorySize` | 2048 | 内存上限 2 GB | 低端设备（≤4 GB RAM 笔记本/集成显卡）易 OOM，建议浏览器版 512–1024 |
| `webGLMemoryGrowthMode` | 2 | 几何增长（`GeometricGrowthStep 0.2`、`Cap 96`） | 合理 |
| `webGLCompressionFormat` | 0 | **Brotli** | 需服务器返回 `Content-Encoding: br`（见 §6） |
| `webGLDecompressionFallback` | 0 | **关闭**（浏览器原生解压） | 托管方不支持 br 时会**加载失败**；ModelScope 静态托管是否设置 `Content-Encoding` 未验证 → 建议先开 fallback 或改 Gzip |
| `webGLLinkerTarget` | 1 | WASM（非 asm.js） | 正确 |
| `webGLThreadsSupport` | 0 | 无线程（不需要 COOP/COEP 头） | 与"不使用托管线程"的约束一致，且降低托管复杂度；代价是不能用 `Task.Run`/阻塞等待 |
| `webGLAnalyzeBuildSize` | 0 | 不做体积分析 | 浏览器版必须开启一次，用于资产预算 |
| `webGLExceptionSupport` | 1 | 仅显式异常 | 合理（体积敏感） |
| `webGLDataCaching` | 1 | IndexedDB 缓存 | 降低二次加载，注意清理策略与隐私说明 |
| `webGLTemplate` | `APPLICATION:Default` | 默认模板 | 无 `Assets/WebGLTemplates/`（已核实不存在）；浏览器版需要自定义模板做中文 UI/加载条/pointer lock 提示 |
| `webGLEmscriptenArgs` / `webGLModulesDirectory` | 空 | 无自定义 | 无 |
| `webGLNameFilesAsHashes` | 0 | 文件名保留 | 便于排查 |
| `webGLPowerPreference` | 2 | 高性能 GPU | 笔记本双显卡/移动端可能触发功耗问题，建议浏览器版验证 1/2 |

其他相关设置：

- `stripEngineCode: 1`（引擎代码裁剪开）、`managedStrippingLevel: {}`、`il2cppCompilerConfiguration: {}`（**未显式设置**，用平台默认）。WebGL 必须 IL2CPP；其中 `il2cppCompilerConfiguration` 默认 Debug 会显著增大包体，发布构建应显式 Release。
- `m_BuildTargetGraphicsAPIs` 只为 Windows 指定了 D3D11+D3D12（第 532–534 行），WebGL 无覆盖 → 使用平台默认（WebGL2）。
- `m_DefaultShaderChunkSizeInMB: 16`（Player 设置）。
- `gcIncremental: 1`、`allowUnsafeCode: 0`。

---

## 4. 包体与内存预算（用真实构建反推）

| 项 | 实测 | 来源 |
| --- | --- | --- |
| Windows 构建（M2）总大小 | 438.9 MB | `Builds/M2` |
| 贴图流数据 | **160.64 MB** | `Builds/M2/Station_Data/sharedassets0.assets.resS` |
| 全局资源 | 50.24 MB | `globalgamemanagers.assets` |
| 场景资源流 | 30.14 MB | `level0.resS` |
| 场景序列化 | 22.93 MB | `sharedassets0.assets` |
| 字体 | 15.76 MB | `Assets/SourceHanSansSC-Regular.otf`（单个 OTF） |
| 源资产 | 188.3 MB / 743 文件 | `Assets/` |

**推算**：WebGL 包（Brotli）通常比桌面 Data 目录小 50–70%，但**初次下载 + 解压后内存**都要算。以 160 MB 贴图流计，即使压缩到 ~60 MB，浏览器首屏下载与 WASM 堆占用仍会触及 2 GB 上限的低端边界。

**必须做的降级（浏览器路径，不影响 Windows 主工程）**：

1. 贴图：`Mask/Normal` 类 2K → 1K 或 512，BC7/BC5 压缩，#mip 保留但限制 aniso ≤4；`Assets/_Project/Art/Textures/M1_5/*` 是主要目标（`Canvas/Mask.png` 10.67 MB 等）。
2. 字体：思源黑体子集化（仅 CJK 常用字 + 数字英文），或改静态 SDF atlas（TMP 已有 `TMP_SDF` 静态图集方案），目标 < 3 MB。
3. 场景：单场景 + 分块加载；3 个实时反射探针 → 1 个烘焙探针 + 屏幕空间反射替代；体积雾 → 距离雾或简单体积光；26 个启用光源 → 烘焙为主。
4. Shader：URP 下用 Lit/Unlit，去掉 SSGI/SSS/Decal；TMP 用 URP 变体（`Assets/TextMesh Pro/Shaders/TMP_SDF-URP Lit.shadergraph` 已存在，可直接用）。
5. 目标门槛（**建议值，需用户批准**）：首包 ≤ 40 MB（Brotli）、首屏可交互 ≤ 25 s（10 Mbps）、运行时 WASM 堆 ≤ 1 GB、60 s 内无泄漏增长。

---

## 5. 输入、中文与浏览器能力

| 项 | 现状 | 浏览器风险 |
| --- | --- | --- |
| 输入资产 | `Assets/InputSystem_Actions.inputactions`（41,005 B）：`Player`（Move/Look/Attack/Interact/Crouch/Jump/Previous/Next/Sprint）与 `UI`（Navigate/Submit/Cancel/Point/Click/RightClick/MiddleClick/ScrollWheel/TrackedDevicePosition/TrackedDeviceOrientation） | 绑定含 Gamepad/Keyboard/XR/Joystick，**无触摸绑定**（见 [GameplayModuleInventory.md](GameplayModuleInventory.md) §6）→ 桌面浏览器可用，移动端不可用 |
| 鼠标视角 | `M2Player` 用 `Cursor.lockState` 锁光标 | WebGL 需用户手势触发 pointer lock，Esc 解锁后需重新点击；`M2Player` 当前假定锁成功 |
| 中文 IME | 无文本输入框；HUD 为 `OnGUI` 只读文本 | 未来自由对话输入必须解决 WebGL IME（TMP_InputField 在 WebGL 有已知焦点/组合输入问题），建议自定义 HTML overlay 输入或 `WebGLInput` 类方案，需实测 |
| 音频 | 场景有 `AudioListener`，无 `AudioSource` 播放逻辑 | 浏览器要求用户手势后才能播放音频（autoplay 策略），须加"点击开始"门 |
| IMGUI | `M2InteractionHud` 用 `OnGUI` | WebGL 下 IMGUI 可用但性能差、不参与 UI 缩放，浏览器版应换 TMP UI |
| 屏幕/分辨率 | `defaultScreenWidth/Height 1024×768`，Web 960×600 | 浏览器版需按容器自适应（Canvas Scaler） |

---

## 6. 托管与网络（部署侧约束）

1. **压缩与 MIME**：`webGLCompressionFormat: 0`（Brotli）+ `webGLDecompressionFallback: 0` 要求服务器：
   - `.unityweb`/`.js.br`/`.wasm.br` 返回 `Content-Encoding: br`；
   - `.wasm` 的 `Content-Type: application/wasm`（否则 `instantiateStreaming` 回退，速度下降）；
   - 不能返回 `Content-Encoding: gzip` 给 br 文件。
   若托管方无法配置，则改用 `webGLDecompressionFallback = 1` 或 Gzip（但仍需 `Content-Encoding: gzip`）。
2. **无线程**：`webGLThreadsSupport: 0` → 不需要 `Cross-Origin-Opener-Policy`/`Cross-Origin-Embedder-Policy`。这一点简化了 iframe 嵌入（创空间通常以 iframe 展示）。
3. **网络**：客户端只能用 `UnityWebRequest`（浏览器 fetch），**不能**用 `HttpClient` 阻塞调用、原生 socket、`System.Threading.Timer` 做超时；需用非缩放时间 + 协程轮询 deadline（`Docs/Architecture.md:288` 已写）。
4. **后端地址**：浏览器不能启动本机 Python；必须 `RemoteWebConnection` 连 HTTPS 远端 FastAPI。**当前 `Server/` 为空壳**，所以浏览器版在 M5 之前没有可连的服务。
5. **CORS**：同源或精确 `Access-Control-Allow-Origin` + 预检；不能通配 + 凭据同用。

---

## 7. 风险登记表

| ID | 风险 | 概率 | 影响 | 缓解 | 归属 |
| --- | --- | --- | --- | --- | --- |
| W-01 | 直接对 HDRP 工程执行 WebGL 构建，长时间后失败 | **必然** | 阻塞 | 不做；另建 URP 路径（需批准） | Codex + 用户 |
| W-02 | 有人把"降低 HDRP 画质/换 Build Profile"当成 WebGL 适配并宣布成功 | 高 | 交付失真 | 本报告 + `Docs/Architecture.md:281` 已明确禁止；验收要求提供**可打开的 https 链接 + 浏览器控制台截图** | 全部 Agent |
| W-03 | 首包过大（>100 MB），加载失败或体验不可接受 | 高 | 高 | §4 资产降级 + `webGLAnalyzeBuildSize` 开启 + 预算脚本 | art-director + DSH |
| W-04 | 服务器未设置 `Content-Encoding: br`，页面 404/加载卡死 | 中 | 高 | 先开 decompressionFallback 验证，再改成原生 br | DSH（脚本） |
| W-05 | 无后端可连，浏览器版只能"看不能玩" | **必然（现状）** | 高 | M5 先做 MockAIProvider + 固定主线，浏览器版可离线走完固定路径 | ai-engineer |
| W-06 | 中文 IME 在 WebGL 输入不可用 | 中 | 高（AI 对话核心） | 候选方案：HTML overlay input + `WebGLInput` 桥；先做 5 分钟技术验证再定 UI | DSH 技术验证 + Codex 集成 |
| W-07 | Pointer Lock / 音频自动播放被浏览器拦截 | 中 | 中 | "点击进入"门控 + 提示文案；实测 Chrome/Edge/Safari | Codex |
| W-08 | 移动端/无键盘设备不可玩 | 高 | 中 | 声明"桌面浏览器"支持范围；或后加虚拟摇杆（需要新输入绑定） | 用户决策 |
| W-09 | IL2CPP + AOT 下 JSON 序列化被裁剪（如未来用 Newtonsoft/反射） | 中 | 中 | DTO 用显式字段 + `link.xml`；第三方库在 Web 构建实测 | DSH（DTO）+ Codex |
| W-10 | 3 个实时反射探针 + 体积雾在浏览器帧率崩 | 高 | 中 | 浏览器版改用烘焙探针 + 距离雾 | art-director |
| W-11 | 内存上限 2048 MB 在低端设备 OOM | 中 | 高 | 浏览器版 512–1024 MB + 纹理降级 | DSH + art-director |
| W-12 | 托管方（魔搭创空间静态/Docker）端口与体积限制未明 | 中 | 中 | 发布前实测；static 类型要求 `index.html` 在仓库根；Docker 类型需监听平台端口（第三方资料称 7860，**待官方确认**） | 用户/发布执行人 |
| W-13 | 无版本基线，浏览器工程与主工程分叉后无法回溯 | 高 | 高 | 先建 Git 基线（P-01） | Codex/Director |
| W-14 | 多人/多 Agent 同时改同一工程导致 Library 冲突 | 中 | 中 | 同一时刻只允许一个 Unity 实例打开工程；构建脚本探测 `Library/EditorInstance.json` | DSH（脚本） |

---

## 8. 建议的技术路线（供用户批准，不自行执行）

**路线 A（推荐）**：`EchoLostAndFound` 保持 HDRP 桌面主工程；新建独立 `EchoLostAndFound.Web`（URP）用于浏览器切片。共享层做成**不依赖任何渲染管线的程序集**（纯 C# + DTO + 内容 ID），三个工程/构建路径各自表现。

**路线 B（更省，但功能受限）**：在主工程旁建 `Assets/Web/` 子集 + 独立 URP 构建 Profile——**不推荐**：同一工程内同时存在 HDRP 与 URP 资产会让场景/Prefab 引用互相污染，且 `GraphicsSettings` 只能有一个默认管线。

**最小验证切片（无论 A/B，先做这个）**：

1. URP 新工程 + 单房间 + 一个 NPC 静态模型 + TMP 中文文本 + 一个按钮交互。
2. WebGL2 构建（Brotli，先开 fallback）→ 本机 `python -m http.server` 起静态服务 → Chrome/Edge/Firefox 打开，记录首包大小、首屏时间、FPS、内存峰值、控制台错误。
3. 加中文输入框（IME 验证）与一次 `UnityWebRequest` 到本地 FastAPI 的 Mock 接口。
4. 上传魔搭创空间 static 或 Docker 类型，记录真实限制与耗时。

只有第 2–3 步在**真实浏览器 + 真实构建**下通过，才能说"WebGL 可部署"。**本次审计未执行其中任何一步。**

---

## 9. 已执行验证

1. 读取 `ProjectSettings/ProjectSettings.asset` 第 813–838 行全部 `webGL*` 键与第 505–544 行渲染后端/GraphicsJobs 配置。
2. 统计 HDRP 包 `.compute`（148）与 `UNITY_WEBGL`（0）、`SHADER_API_GLES3`（0）。
3. 核对 `Assets/Settings/HDRP High Fidelity.asset` 的 `supportSSGI/SSAO/SSS/RayTracing/msaaSampleCount/colorBufferFormat`。
4. 核对 `PlayerCamera` 的 `HDAdditionalCameraData` 与 `StationNight.asset` 的 7 个 HDRP Volume 组件。
5. 场景类计数（60 MeshRenderer / 36 Light / 3 ReflectionProbe / 6 Camera）与 Prefab 引用次数。
6. `Builds/M2/Station_Data` 头部文件字节数；4 个 Windows 构建总大小；**确认无 WebGL 产物**。
7. 材质数（73 `.mat`）、字体（15.76 MB）、贴图导入设置样例（`maxTextureSize: 2048`、`textureFormat: -1`、`aniso: 8`）。
8. 输入资产绑定枚举（无触摸绑定）。
9. 检索 `Assets/WebGLTemplates`（不存在）、`Resources` 目录（仅 `Assets/TextMesh Pro/Resources`）。

## 10. 未验证事项

| 项 | 原因 |
| --- | --- |
| 任何 WebGL 构建 | 编辑器占用 + HDRP 不支持；**未执行，未声称成功** |
| 浏览器实测（Chrome/Edge/Firefox/Safari） | 无 WebGL 产物可测 |
| Brotli `Content-Encoding` 托管行为 | 无托管环境 |
| 魔搭创空间上传限制、端口、静态与 Docker 类型差异 | 仅第三方教程（[参考](https://datawhalechina.github.io/easy-vibe/zh-cn/stage-1/appendix-modelscope-static-site/)），官方限制未核验 |
| IME / pointer lock / 音频门控 | 需真实浏览器 |
| 首包体积估算的准确性 | 需一次真实 URP WebGL 构建对照 |
| `Assets/_Project/Art/Textures/M1_5/*` 降级后的视觉可接受度 | 需美术验收 |
