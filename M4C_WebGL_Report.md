# M4-C WebGL 验收报告

工程：`G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL`（URP 17.3.0，Unity 6000.3.29f1）
构建产物：`F:\EchoBuilds\M4C-WebGL-03`
内容版本：`story-v1.0-phase2`

---

## 1. 构建

| 项 | 值 |
| --- | --- |
| 入口 | `EchoLostAndFound.Build.WebGLBuildEntry.Build`（`Assets/_Project/Editor/WebGLBuildEntry.cs`） |
| 压缩 | gzip 预压缩（`DSH_WEBGL_COMPRESSION=gzip`） |
| 线程 | `threadsSupport=false`，`decompressionFallback=false`（因此不需要 COOP/COEP） |
| 结果 | `WebGL build Succeeded: 21364584 bytes, 00:02:41.0864021, errors 0` |
| 日志 | `M4C\Logs\unity-webgl-build-3.log` |
| 总大小 | 21,364,584 B / 17 个文件 |

| 文件 | 字节 | 说明 |
| --- | --- | --- |
| `Build/M4C-WebGL-03.wasm.gz` | 11,148,016 | 代码段（gzip） |
| `Build/M4C-WebGL-03.data.gz` | 10,080,203 | 资源与场景数据（gzip，含 TMP 字体图集与 M3B JSON） |
| `Build/M4C-WebGL-03.framework.js.gz` | 89,825 | 运行框架（gzip） |
| `Build/M4C-WebGL-03.loader.js` | 26,983 | 加载器（未压缩） |
| `index.html` | 5,661 | 入口页 |
| `unity-logo-light.png` | 3,077 | 模板资源 |
| 其余 11 个 | ≈14.8 KB | 模板/样式/图标 |

版本演进（同一工程）：M4-A 构建 65,698,620 B（17 文件 / 21,270,890 B gzip） → M4-C 构建 #2 21,365,437 B → **#3 21,364,584 B**。体积差异来自 M4-A 记录口径不同（含未压缩中间文件统计）与本轮资源/脚本变化，构建方式一致。

字体资源：`Assets/_Project/Resources/M4A/StationChinese SDF.asset` = 2,369,239 B（**520 字**，`missing=none`、`uncovered=0`），源字体 `StationChinese.ttf` = 469,368 B。

---

## 2. 静态服务与响应头

服务实现：`Server/app/static_site.py`（同源托管）、`Tools/Build/serve-webgl.mjs`（纯静态调试）。

已验证的响应头（同源 8790 与容器 7860 均一致）：

| 请求 | 状态 | `Content-Type` | `Content-Encoding` | `Vary` |
| --- | --- | --- | --- | --- |
| `/` | 200 | `text/html; charset=utf-8` | — | `Accept-Encoding, Origin` |
| `Build/M4C-WebGL-03.wasm` | 200 | `application/wasm` | `gzip` | `Accept-Encoding, Origin` |
| `Build/M4C-WebGL-03.data` | 200 | `application/octet-stream` | `gzip` | 同上 |
| `Build/M4C-WebGL-03.framework.js` | 200 | `text/javascript` | `gzip` | 同上 |
| `Build/M4C-WebGL-03.loader.js` | 200 | `text/javascript` | — | 同上 |
| `Build/M4C-WebGL-03.data.gz`（显式请求预压缩文件名） | 200 | `application/octet-stream` | `gzip` | 同上 |

实现要点（E2E 暴露并已修复的两个真实缺陷）：

1. **显式 `*.gz` 文件名必须声明 gzip**。最初把 `…data.gz` 当普通文件送出（无 `Content-Encoding`），Unity 直接报
   `Failed to parse binary data file Build/M4C-WebGL-03.data.gz (with "Content-Type: application/octet-stream"), because it is still gzip-compressed.`。
   现在 `_pick()` 对 `.gz` 结尾的目标：客户端接受 gzip 时回 `(path, True)` 并带 `Content-Encoding: gzip`，MIME 取去掉 `.gz` 后的扩展名；不接受 gzip 时 404，绝不发压缩字节。
2. **静态资源不能被 API 限流**。一次页面加载会发 10+ 请求，原先会打满 `burst=20` 后 429 `loader.js`。现在限流只作用于 `/api/v1/*`（`/health` 除外）。
3. 目录穿越（`..`）返回 404；API 路由优先于静态挂载；`Cache-Control: no-store`。

---

## 3. 浏览器验收

驱动：`M4C\Scripts\m4c-e2e.mjs`（Node 零依赖，Chrome DevTools Protocol via `--remote-debugging-pipe`；`M4C_HEADED=1` 切到有窗口模式并启用 `--use-angle=d3d11`）。

| 运行 | 页面来源 | 渲染器 | 冷启动 | 刷新 | 结果 |
| --- | --- | --- | --- | --- | --- |
| `online-05` | `http://127.0.0.1:8790/`（同源） | headless + SwiftShader | 1.40 s | 1.03 s | 通过 |
| `gpu-02` | `http://127.0.0.1:8790/`（同源） | **headed + RTX 4060 D3D11** | 1.29 s | 0.67 s | 通过 |
| `container-01` | `http://127.0.0.1:7860/`（Docker 容器） | headless + SwiftShader | 1.73 s | 0.87 s | 通过 |
| `offline-03` | `http://127.0.0.1:8080/`（API 全停） | headless + SwiftShader | 1.35 s | — | 通过 |
| `resume-03` | `http://127.0.0.1:8790/`（重启后） | headless + SwiftShader | 1.68 s | — | 通过 |

WebGL 运行环境（页面自报）：

```
WebGL 2.0 (OpenGL ES 3.0 Chromium)
ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Laptop GPU (0x000028E0) Direct3D11 vs_5_0 ps_5_0, D3D11)   ← gpu-02
ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)                  ← 其余
Chrome/157.0.8103.79
```

### 3.1 通过判据（每轮全部满足）

- `completed: true`，`soft: []`（无软失败项）
- **0** `Runtime.exceptionThrown`，**0** JS 错误级 console，**0** HTTP ≥ 400（离线轮仅容忍预期的 `/api/v1/meta` 404）
- 剧情事件唯一性：`d01Events=1`、`d03Events=1`、`recEvents=1`
- 服务端镜像一致：`mirrorLogs=8`，全部 `M4C mirror ok …`，无 `disclosure mismatch`
- 在线三轮各 20 次 `/api/v1/*` 请求

### 3.2 覆盖的交互

| 验收点 | 结果 |
| --- | --- |
| 加载 + 进入车站 | 通过（冷启动 ~1.3–1.7 s） |
| WASD 移动 / 鼠标环视 / 指针锁定 | 通过 |
| 怀表五部位逐一查看 → E01（QH-283） | 通过 |
| 维修柜 → E02（正面卡） | 通过 |
| 维修柜 → 背面索引 → E05 | 通过 |
| 失物包 → E03 | 通过 |
| 副联册 → E04 | 通过 |
| 老周固定话题（问 / 再问站台照明、结束对话） | 通过 |
| 自由输入：中文提交 + Mock 回复 + 模拟标注 | 通过 |
| 自由输入：Mock 超时（`reason=timeout`，「模型回应超时」） | 通过 |
| 自由输入：未命中关键词（`unknown_intent` 兜底文案） | 通过 |
| 出示 E02 → D01（且只触发一次） | 通过 |
| 出示 E03/E04 → D02（老周与林遥各一条） | 通过 |
| 出示 E01+E05 → D03（保持 E01+E05 条件） | 通过 |
| 林遥 REC.engraving（四月十二…） | 通过 |
| 刷新后证据 persistence | 通过（`reloadMs` 内完成） |
| 服务停止 → 离线回退 | 通过 |
| 服务重启 → 在线恢复 + 会话重建 | 通过（`resume-03`） |
| 中文缺字 | 无（逐屏核对） |

### 3.3 关键截图

| 截图 | 内容 |
| --- | --- |
| `M4C\E2E\gpu-02\01-station.png` | 车站初始视角 + 中文 HUD（WASD 移动 / 鼠标 环视 / E 调查 / Esc 释放鼠标） |
| `M4C\E2E\gpu-02\06-watch-parts.png` | 怀表逐步查看（n/5 进度） |
| `M4C\E2E\gpu-02\09-package-e03.png` | 失物包 A-0641（E03 入口） |
| `M4C\E2E\gpu-02\14-cabinet-index.png` | 维修柜 · 背面索引 → 拾物与检点联 |
| `M4C\E2E\gpu-02\17-mock-reply-reply.png` | 中文自由输入 + Mock 回复 + 「（服务器模拟回复，非真实模型）」+ 7 个出示项 |
| `M4C\E2E\gpu-02\23-linyao-d02.png` | 林遥 D02（「沈禾，是我妈妈…」） |
| `M4C\E2E\offline-03\03-probe-offline.png` | 离线模式提示 + 固定选项仍可用 |
| `M4C\E2E\offline-03\07-offline-persisted.png` | 离线收集 E01 后刷新仍保留 |
| `M4C\E2E\resume-03\*.png` | 重启后证据仍保留、在线对话恢复 |

（`online-01` 中 `03-free-text-typed.png` 保留了文字注入失败的现场，用于对照说明 Unity WebGL 无隐藏 DOM input。）

---

## 4. 输入方式验证

Unity WebGL 不创建隐藏 DOM `<input>`：页面中 `document.querySelectorAll('input,textarea').length === 0`，`document.activeElement` 恒为 `CANVAS:unity-canvas`。因此：

- `Input.insertText`：**无效**（不触发输入框更新）。
- `Input.imeSetComposition` + `insertText`：**无效**。
- `Input.dispatchKeyEvent {type:'keyDown', key, code, text}`（ASCII）：**有效**。
- `Input.dispatchKeyEvent {type:'char', text}`（逐字符，ASCII 与中文均可）：**有效**——端到端脚本采用此方式。

结论：真实浏览器中键盘事件路径可用；**真实 OS 输入法组合窗口未验证（PARTIAL）**。

---

## 5. 限制与风险

| 项 | 说明 |
| --- | --- |
| 无长效缓存 | `Cache-Control: no-store`；21 MB gzip 每次冷加载约 1.3–1.7 s（本地）；魔搭可通过 CDN/缓存头优化 |
| 首次加载体积 | wasm 11.1 MB + data 10.1 MB（gzip 后）；慢网下首次进入体验需评估 |
| 线程关闭 | `threadsSupport=false`，无多线程 wasm；若未来开启需配置 COOP/COEP（`serve-webgl.mjs --coep`） |
| 灰盒画面 | 场景为程序化灰盒（M2/M4-A 起即为灰盒），非美术终版 |
| 字体子集 | TMP 字体为静态子集（520 字），新增中文文案必须重新烘焙，否则缺字 |
| 自动化鼠标位移 | 有窗口模式下单次超大位移会被窗口边缘截断，脚本改为 ≤40 px 分步（仅影响自动化，不影响玩家） |

---

## 6. 复现步骤

```powershell
# 1) 构建
$env:DSH_WEBGL_OUTPUT='F:\EchoBuilds\M4C-WebGL-03'
$env:DSH_WEBGL_COMPRESSION='gzip'
F:\software\unity\6000.3.29f1\Editor\Unity.exe -batchmode -quit `
  -projectPath G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL `
  -executeMethod EchoLostAndFound.Build.WebGLBuildEntry.Build `
  -logFile M4C\Logs\unity-webgl-build-3.log

# 2) 同源服务（页面 + API）
cd Server
$env:WEB_ROOT='F:\EchoBuilds\M4C-WebGL-03'; $env:MODEL_PROVIDER='mock'; $env:AI_TIMEOUT_MS='4000'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8790

# 3) 浏览器 E2E（headless）
$env:M4C_PROFILE='C:\Users\10509\.dsh\m4c-profile-03'
node M4C\Scripts\m4c-e2e.mjs "http://127.0.0.1:8790/" "M4C\E2E\online-06" online

# 4) 真实 GPU（有窗口）
$env:M4C_HEADED='1'
node M4C\Scripts\m4c-e2e.mjs "http://127.0.0.1:8790/" "M4C\E2E\gpu-03" online

# 5) 离线（只启动静态服务器，API 不启动）
$env:M4C_PROFILE='C:\Users\10509\.dsh\m4c-profile-03'
node M4C\Scripts\m4c-e2e.mjs "http://127.0.0.1:8080/" "M4C\E2E\offline-04" offline

# 6) 重启恢复（复用同一 profile，服务重新启动后）
node M4C\Scripts\m4c-e2e.mjs "http://127.0.0.1:8790/" "M4C\E2E\resume-04" resume
```
