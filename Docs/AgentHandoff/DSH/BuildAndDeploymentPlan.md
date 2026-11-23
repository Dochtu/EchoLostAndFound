# WebGL 可重复构建与部署方案 · EchoLostAndFound

**作者**：DSH　**日期**：2026-11-23　**性质**：方案 + 已落地脚本
**状态**：**当前工程无法构建 WebGL**（HDRP）。本文给出可重复执行的构建/打包/浏览器验证/魔搭创空间部署流程，并明确每一步的当前真实状态。
**配套脚本**：`Tools/Build/Invoke-WebGLBuild.ps1`、`Tools/Build/serve-webgl.mjs`、`Tools/Build/WebGLBuildEntry.cs.txt`

---

## 1. 结论：现在能构建吗

**不能。** 预检脚本实测输出（`Tools/Build/Invoke-WebGLBuild.ps1`，2026-11-23 12:16，退出码 **2**）：

| 判定 | 项 | 证据 |
| --- | --- | --- |
| FAIL | 工程被编辑器占用（PID 8272） | `Library/EditorInstance.json` |
| FAIL | 渲染管线是 HDRP | `HDRenderPipelineAsset.asset`，guid `b9f3086da92434da0bc1518f19f0ce86` |
| FAIL | 磁盘剩余 15.1 GB < 门槛 20 GB | G: 盘 |
| WARN | 未安装 URP 包 | `Packages/manifest.json` 无 `com.unity.render-pipelines.universal` |
| WARN | 未开 `decompressionFallback` | 托管端必须正确返回 `Content-Encoding` |
| WARN | 无 `Assets/WebGLTemplates` | 用默认模板 |
| WARN | 无构建入口 `WebGLBuildEntry` | 需 Codex 落位 |
| OK | Unity `6000.3.29f1` + WebGL 模块 | `Data/PlaybackEngines/WebGLSupport` |

前 3 条是硬阻断。**只要渲染管线还是 HDRP，这个工程永远出不了 WebGL 包**——这不是设置问题，是平台支持矩阵问题（见 `WebGLCompatibility.md` §1）。

---

## 2. 三条可行路线

| 路线 | 内容 | 优点 | 代价/风险 | 建议 |
| --- | --- | --- | --- | --- |
| **A 独立 URP 浏览器工程** | 保留 `G:\projects\EchoLostAndFound` 为 HDRP Windows 主工程；另建 `EchoBrowser`（URP），复用纯逻辑/DTO/输入资产/FBX/Docs | 主工程零风险；浏览器包可控；符合 `Docs/Architecture.md:281` | 需用户批准新建工程 + 双份场景/材质维护 | **推荐**，须用户批准 |
| B 同工程双管线 | 同一工程内加 URP 资产 + 第二套材质，切管线构建 | 单一仓库 | HDRP Volume/材质/相机数据全部失效；两管线并存污染 Library 与包体；违反"不随意更换渲染管线" | 不推荐 |
| C 非 Unity 网页端 | 用 Web 前端（Three.js/自研）+ FastAPI 复刻调查玩法 | 包体最小、部署最简单 | 放弃 Unity 资产与工具链；与"Unity 3D 游戏"目标偏离 | 仅在赛事时限极紧时讨论 |

**任何路线都不允许**把"切换 Build Profile"或"把 HDRP 画质调低"当作 WebGL 适配（`Docs/Architecture.md:281` 原文要求）。

---

## 3. 构建流水线（可重复执行）

### 3.1 四步

```
① 预检  → ② 构建 → ③ 打包/清单 → ④ 本地浏览器验证 → ⑤ 上传创空间
```

```powershell
# ① 预检（无副作用，可随时跑；当前必然 FAIL）
powershell -NoProfile -ExecutionPolicy Bypass -File Tools\Build\Invoke-WebGLBuild.ps1

# ② 构建（需先关闭占用工程的 Unity 编辑器；当前因 HDRP 必然 FAIL）
powershell -NoProfile -ExecutionPolicy Bypass -File Tools\Build\Invoke-WebGLBuild.ps1 `
  -Mode Build -Compression brotli -OutputDir Builds\WebGL\20261123_r1

# ③ 打包 + 生成 manifest.json（路径/字节/SHA256）
powershell -NoProfile -ExecutionPolicy Bypass -File Tools\Build\Invoke-WebGLBuild.ps1 `
  -Mode Package -OutputDir Builds\WebGL\20261123_r1

# ④ 本地服务器（必须用它能补 Content-Encoding；python -m http.server 不行）
node Tools\Build\serve-webgl.mjs Builds\WebGL\20261123_r1 8080
```

退出码约定（便于 CI/人工判断）：`0` 通过；`2` 预检失败（未构建）；`3` Unity 退出码非 0 或缺 `index.html`；`4` 打包阶段找不到产物。

### 3.2 预检做了什么（10 项）

1. `Assets/` 与 `ProjectSettings/ProjectVersion.txt` 存在性 + 版本行；
2. `Unity.exe` 定位（优先 `Library/EditorInstance.json` 的 `app_path`）；
3. `Data/PlaybackEngines/WebGLSupport` 模块；
4. 编辑器锁（`EditorInstance.json` 的 `process_id` 是否存活）→ 占用即 FAIL；
5. `GraphicsSettings.asset` 的 `m_CustomRenderPipeline` guid → 反查 `.meta` → 读资产 `m_Script` guid 判定 HDRP（`0cf1dab834d4ec34195b920ea7bbf9ec`）→ FAIL；
6. `Packages/manifest.json` 是否有 URP（仅有则 WARN）；
7. `webGLCompressionFormat`/`DecompressionFallback`/`ThreadsSupport`/`AnalyzeBuildSize` 一致性；
8. `Assets/WebGLTemplates` 是否存在；
9. 构建入口 `WebGLBuildEntry` 是否已在 `Assets/` 中；
10. 磁盘剩余空间 ≥ `-MinFreeSpaceGb`（默认 20），且输出目录不在 `Assets/` 内。

### 3.3 构建入口契约（Codex 落位）

`Tools/Build/WebGLBuildEntry.cs.txt` → 目标 `Assets/_Project/Editor/WebGLBuildEntry.cs`：

- `public static void Build()`，供 `-executeMethod EchoLostAndFound.Build.WebGLBuildEntry.Build` 调用；
- 读 `DSH_WEBGL_OUTPUT`（绝对路径，禁止落在 `Assets/`）、`DSH_WEBGL_COMPRESSION`（brotli/gzip/disabled）；
- **运行时再判一次管线**：`GraphicsSettings.defaultRenderPipeline.GetType().FullName == "…HighDefinition.HDRenderPipelineAsset"` 直接抛错并 `EditorApplication.Exit(1)`；
- 只构建 `EditorBuildSettings` 中 `enabled` 的场景，并打印场景清单与产物 Top15 体积；
- 成功后校验 `index.html`。

> 该文件不能由 DSH 直接放入 `Assets/`：`Editor/` 属 Unity 工程架构范围，且新增 `.cs` 会生成 `.meta`，须 Codex 执行（AGENTS.md 写入范围）。

### 3.4 产物清单（`manifest.json`）

`-Mode Package` 生成：`generatedAtUtc`、`compression`、`fileCount`、`totalBytes`、`files[{path,bytes,sha256}]`，并打包同名 `.zip`。用途：与 `WebGLCompatibility.md` §4 的包体预算对照、上传前核对、复现构建。

---

## 4. 压缩与资源加载

### 4.1 当前设置

| 键 | 值 | 影响 |
| --- | --- | --- |
| `webGLCompressionFormat` | `0` Brotli | 产物 `.br`，必须 HTTPS + 正确 `Content-Encoding: br` |
| `webGLDecompressionFallback` | `0` | 不做 JS 内解压回退；服务器配错就白屏 |
| `webGLThreadsSupport` | `0` | 不需要 COOP/COEP，可被 iframe 直接嵌入（好消息） |
| `webGLMemorySize` / `Initial` | 32 / 32 MB | 首帧堆偏小 |
| `webGLMaximumMemorySize` | 2048 MB | 浏览器上限 2 GB；移动端可能 OOM |
| `webGLMemoryGrowthMode` | `2` | 几何增长（step 0.2，cap 96） |
| `webGLDataCaching` | `1` | IndexedDB 缓存，二次加载快 |
| `webGLLinkerTarget` | `1` WASM | 正常 |
| `webGLAnalysis` | 关 | 发布前建议开一次 |

### 4.2 服务器必须满足的映射

| 扩展名 | `Content-Type` | `Content-Encoding` |
| --- | --- | --- |
| `.wasm.br` | `application/wasm` | `br` |
| `.js.br` | `text/javascript` | `br` |
| `.data.br` / `.bundle.br` | `application/octet-stream` | `br` |
| `.gz` 系列 | 同上 | `gzip` |
| `.wasm`（Disabled 时） | `application/wasm` | 无 |

`Tools/Build/serve-webgl.mjs` 已实现该映射（含 `Content-Length`、`no-store`、目录越界拒绝）。**实测结果**（2026-11-23）：

```
GET /            -> 200, Content-Type: text/html; charset=utf-8
GET /app.wasm    -> 200, Content-Encoding: br, Content-Type: application/wasm（自动匹配 app.wasm.br）
GET /../secret   -> 404（越界未泄露）
```

> `--coep` 仅在开启多线程 WebGL 时才需要；默认不加，避免 `require-corp` 拦截子资源。

### 4.3 包体策略（浏览器版必须做）

当前 Windows 构建 `Builds/M2/Station_Data/sharedassets0.assets.resS` = **160.64 MB**，整个 `Station_Data` 约 300 MB；WebGL 首包必须压到 **≤ 40 MB**（详见 `WebGLCompatibility.md` §4）。手段（按收益排序）：

1. 贴图降规格 + 压缩：13 张 4–10 MB 的 Mask/Normal 是首要目标（导入分辨率 2048 + 未 crunched）；
2. 删除未使用资源与模板场景（`Assets/OutdoorsScene.unity`、`Assets/_Recovery/`）；
3. `stripEngineCode` 已开（1），继续靠 IL2CPP + Managed Stripping 收托管代码；开 strip 后必须实测反射路径；
4. 字体子集化（思源黑体 15.76 MB → 常用字 + SDF 图集）；
5. 分场景/分章节加载：**当前工程没有任何 Addressables/AssetBundle 分组**，浏览器版若需分段加载必须新建分组（属工程架构，Codex 定）；
6. 音频改流式 + 低码率（当前无音频资源，暂无压力）。

---

## 5. 浏览器验收清单（上传前逐项打勾）

| # | 检查项 | 判定方法 | 当前状态 |
| --- | --- | --- | --- |
| 1 | 页面加载出 Unity 进度条 | 打开 `http://127.0.0.1:8080/` | 未验证（无产物） |
| 2 | WASM 编译成功、无 MIME 报错 | DevTools Network/Console | 未验证 |
| 3 | 首帧 < 10 s（本机；创空间冷启动另计） | Performance 面板 | 未验证 |
| 4 | 指针锁定进入第一人称 | 点击画面后 `document.pointerLockElement` | 未验证 |
| 5 | 移动/视角/交互可用 | WASD + 鼠标 + E | 未验证 |
| 6 | 中文渲染正常（TMP SDF） | 看 UI 文案 | 未验证 |
| 7 | 输入法/文本输入（若做自由对话） | 中文输入框 | 未验证（当前无输入框） |
| 8 | 音频在用户手势后播放 | 点击后有声 | 未验证（无音频资源） |
| 9 | 刷新后存档可恢复（若接后端） | IndexedDB/后端 | 未验证 |
| 10 | 关闭标签页无未捕获异常 | Console 无红字 | 未验证 |

---

## 6. 魔搭创空间部署

### 6.1 方案一：静态空间（推荐给纯客户端切片）

1. 创空间 → 新建 → SDK 类型选 **Static**；
2. **`index.html` 必须位于仓库根目录**（不能放在 `Build/` 子目录里）；
3. 上传 `index.html` + `Build/` + `TemplateData/`；
4. 部署设置 → 部署 → 看构建日志；
5. 访问 `https://modelscope.cn/studios/<user>/<space>`。

**必须处理**：静态托管是否支持为 `.br` 返回 `Content-Encoding: br` **未确认**。若不支持，二选一：

- 构建时用 `-Compression disabled`（包体变大，但不会被错误解压）；
- 或保留 Brotli 但把 `decompressionFallback` 设为 1（Unity 会在 JS 内解压，首屏变慢）。

**已知约束**：国内站 `modelscope.cn` 与国际站 `modelscope.ai` 账号/令牌不互通；静态空间对单文件大小与总容量有上限（**具体数值待官方文档确认**，上传前先用 `manifest.json` 的 `totalMiB` 比对）。

### 6.2 方案二：Docker 空间（需要后端时的唯一选择）

Unity 包与 FastAPI 规则服务同源部署，避免 CORS：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY Server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY Server/app ./app
COPY Builds/WebGL/latest ./web
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

- 由 FastAPI 挂载 `web/` 为静态根，并为 `.br`/`.gz` 补 `Content-Encoding`（Starlette `StaticFiles` 默认不补，需要自定义中间件）；
- 端口以平台要求为准（第三方资料称 7860，**待官方确认**）；
- `MODELSCOPE_API_KEY` 只放服务端环境变量（AGENTS.md 硬约束），不得进镜像层与日志；
- 浏览器端 Unity 用 `UnityWebRequest` 异步调同源 `/api/v1/*`，不要启动本地进程（浏览器禁止），对应 `Docs/Architecture.md` 的 `RemoteWebConnection`。

### 6.3 不建议的做法

- 用 iframe 嵌到第三方页面：`pointer lock` 与全屏会被限制；
- 把 `index.html` 改成 `index.htm` 或放在子目录：静态空间找不到入口；
- 依赖 `python -m http.server` 验证 Brotli：不补 `Content-Encoding`，必然白屏。

---

## 7. 阻断与责任划分

| 阻断项 | 影响 | 解决方 |
| --- | --- | --- |
| HDRP 不支持 WebGL | 无法出包 | **用户批准** + Codex 建 URP 浏览器工程（路线 A） |
| 工程被编辑器占用（PID 8272） | 无法批处理构建 | 人工关闭本机编辑器（构建期间） |
| 磁盘 15.1 GB | IL2CPP/WebGL 中间产物可能写满 | 清理旧 `Builds/`（4 个共 1.7 GB）与 `Library/` 缓存 |
| 无 URP 包 | 浏览器工程缺前提 | Packages 变更须授权，Codex 执行 |
| 无构建入口脚本 | 预检 WARN、构建必失败 | Codex 按 §3.3 落位 |
| 无 `WebGLTemplates` | 无中文加载页/pointer lock 引导 | Codex/Art 决定是否新建（新增资源，属工程范围） |
| 服务端零实现 | 无存档/AI，浏览器切片刻只能做纯单机 | AI Engineer 实现 M5/M6（`Server/`） |

## 8. 已执行验证

1. **运行预检脚本**：真实执行，输出上表 3 FAIL + 5 WARN，退出码 `2`（未进入构建）。
2. **修正脚本缺陷**：Windows PowerShell 5.1 需 UTF-8 BOM（本机只有 `powershell.exe` 5.1，无 `pwsh`）；`$pid` 是只读自动变量，已改名 `$editorPid`；`"$Key:"` 被解析为驱动器语法，已改 `${Key}`；`$PSScriptRoot` 在参数默认值阶段为空，已移到脚本体计算。
3. **实测 `serve-webgl.mjs`**：启动本地服务器对临时目录发起 3 个请求，验证 MIME、`Content-Encoding: br`、越界 404（见 §4.2 输出）。
4. **核对** HDRP 包内 **148 个 `.compute`、`UNITY_WEBGL` 命中 0**，确认"不支持"不是配置开关问题。
5. **核对** `ProjectSettings.asset` 全部 `webGL*` 键值与 `Builds/M2` 实际体积。

## 9. 未验证事项

| 项 | 原因 |
| --- | --- |
| 真实 WebGL 构建能否成功 | HDRP 阻断 + 编辑器占用 + 磁盘不足，**未执行任何构建**，不得声称成功 |
| 产物实际首包体积 | 无产物；§4.3 的 40 MB 是目标值不是实测 |
| 创空间静态托管对 `.br` 的响应头处理 | 需实测上传一个最小 Unity 包 |
| 创空间容量/单文件上限、Docker 端口 | 第三方资料，**待官方确认** |
| CI 化（命令行自动预检） | 本机只有 Windows PowerShell 5.1，脚本已按 5.1 兼容编写但未接入 CI |

## 10. 下一步任务

1. （用户）批准路线 A，或明确要求改为路线 C；
2. （Codex）关闭占用编辑器、清理磁盘、按 §3.3 落位 `WebGLBuildEntry.cs`；
3. （Codex）新建 URP 浏览器工程并导入可迁移资产（清单见 `GameplayModuleInventory.md` §4）；
4. （DSH）在 URP 工程上首次跑通 §3.1 四步，产出 `manifest.json` 与首包预算实测；
5. （DSH）上传最小切片到 static 空间，实测 `.br` 响应头；
6. （AI Engineer）实现 `Server/`，再把 Docker 方案接上。
