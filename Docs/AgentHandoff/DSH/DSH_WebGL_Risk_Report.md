# DSH_WebGL_Risk_Report.md · Task 1 WebGL 风险登记册

**任务**：Task 1 之 WebGL 兼容性风险　**作者**：DSH　**日期**：2026-11-23
**配套**：`Docs/AgentHandoff/DSH/WebGLCompatibility.md`（技术论证与 W-01…W-14）、`Docs/AgentHandoff/DSH/BuildAndDeploymentPlan.md`（可执行流水线）
**评级**：可能性 L（高/中/低）× 影响 I（高/中/低），综合等级 P1（阻断）/P2（严重）/P3（可控）

---

## 0. 硬阻断（当前状态，不是风险，是事实）

| ID | 阻断 | 证据 | 解除条件 |
| --- | --- | --- | --- |
| B-01 | HDRP 不支持 WebGL/WebGPU | `GraphicsSettings.asset` 指向 HDRP guid `b9f3086da92434da0bc1518f19f0ce86`；HDRP 包内 148 个 `.compute`、`UNITY_WEBGL` 命中 0 | 用户批准 + 建 URP 浏览器工程（或改走非 Unity 网页端） |
| B-02 | 工程被 Unity 编辑器占用（PID 8272） | `Library/EditorInstance.json` | 关闭该编辑器实例 |
| B-03 | 磁盘剩余 15.1 GB | G: 盘 | 清理旧 `Builds/`（4 个共 1.7 GB）与 `Library/` |
| B-04 | 无 URP 包、无构建入口、无 `WebGLTemplates` | `Packages/manifest.json`、`Assets/` 无 `WebGLBuildEntry.cs` | Codex 落位（Packages 变更须授权） |

> **在 B-01 解除前，任何"WebGL 构建成功"的表述都是错误的。** 本轮 DSH **未执行任何构建**，预检脚本按设计在 B-01 处退出码 2。

---

## 1. 风险清单

### P1 · 阻断级

| ID | 风险 | L | I | 证据 | 缓解 | 责任 |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | 浏览器路线迟迟不决，导致赛事截止前无可用 Web 版本 | 高 | 高 | 本报告 §0 | 立即裁决路线 A/C；A 路线最小切片 4 步见 WebGLCompatibility §8 | 用户 + Director |
| R-02 | 在 HDRP 工程上"降画质/切 Build Profile"被当作适配，最终无法出包 | 中 | 高 | `Docs/Architecture.md:281` 明文禁止 | 预检脚本硬失败；评审时以此条为准 | Codex |
| R-03 | 首包体积超出可接受范围（WebGL 首屏 > 60 s 或直接 OOM） | 高 | 高 | 资产 166.9 MB；`sharedassets0.assets.resS` 160.64 MB；13 张 4–10 MB Mask/Normal；字体 15.76 MB | 贴图降规格、字体子集化、删模板/恢复场景、Addressables 分段；目标首包 ≤ 40 MB | Codex + Art |
| R-04 | 双工程（Windows HDRP + 浏览器 URP）内容漂移，剧情/线索两套实现 | 高 | 高 | 需同时维护两套场景与材质 | 内容数据单一来源（JSON/ScriptableObject 导出）+ 纯逻辑 asmdef 共享；禁止两处各写规则 | Codex + Narrative |

### P2 · 严重

| ID | 风险 | L | I | 证据 | 缓解 | 责任 |
| --- | --- | --- | --- | --- | --- | --- |
| R-05 | Brotli + 未开 `decompressionFallback` 的包在错误配置的托管端白屏 | 高 | 中 | `webGLCompressionFormat 0`、`DecompressionFallback 0` | 必须返 `Content-Encoding: br`；本地用 `Tools/Build/serve-webgl.mjs`；创空间若不支持则改 `-Compression disabled` | DSH + 部署 |
| R-06 | 移动端不可玩：无触摸绑定、`webGLMaximumMemorySize 2048` 超出 iOS Safari 常见上限 | 高 | 中 | `InputSystem_Actions.inputactions` 无 Touch；`ProjectSettings.asset` 内存键 | 明确"桌面浏览器"验收口径；或补 Touch 映射并把堆压到 512–1024 MB | Codex |
| R-07 | TMP 中文在 WebGL 下缺字/花屏（字体图集未嵌入或子集化错误） | 中 | 高 | 现有字体 15.76 MB `.otf`，TMP 走 SDF 图集 | 生成静态 SDF 图集 + 常用字子集；浏览器验收第 6 项专测 | Codex |
| R-08 | IMGUI（`M2InteractionHud`）在 WebGL 下高 DPI 缩放异常、无法做复杂 UI | 高 | 中 | `OnGUI` 硬编码 | 重写为 uGUI/TMP（D-03） | Codex |
| R-09 | IL2CPP + Managed Stripping 裁掉反射/JSON 路径，运行时 `MissingMethod` | 中 | 高 | `stripEngineCode 1`、`managedStrippingLevel {}` 未显式配置 | 显式设置 stripping 等级、`link.xml` 保留、DTO 用显式字段（禁反射） | Codex + DSH |
| R-10 | 后端不可达时玩法卡死（无降级路径） | 中 | 高 | 服务端零实现；`Docs/Architecture.md` §9.5 有降级表但无代码 | 客户端本地状态机 + 离线只读模式；"模型关闭仍可通章，规则服务停则停写" | DSH + AI Engineer |
| R-11 | API Key 泄漏进 WebGL 包（浏览器端可见一切） | 低 | 高 | AGENTS.md 硬约束 | 浏览器端禁止任何 LLM Key；所有模型调用经服务端代理；构建产物扫描 `manifest.json` 与 `.data` 字符串 | DSH（扫描）+ AI Engineer |

### P3 · 可控

| ID | 风险 | L | I | 证据 | 缓解 | 责任 |
| --- | --- | --- | --- | --- | --- | --- |
| R-12 | `webGLMemorySize 32 MB / Initial 32 MB` 过小，首次加载即崩 | 中 | 中 | `ProjectSettings.asset` | 提到 256/512 MB 并实测 | Codex |
| R-13 | IMGUI/输入在 iframe 内 pointer lock 受限 | 中 | 低 | 平台行为 | 独立页部署，不做 iframe 嵌入 | 部署 |
| R-14 | 输入法（中文自由对话）在 WebGL 文本框中失效 | 中 | 中 | Unity WebGL IME 支持有限 | 自由对话输入可用 DOM overlay 或预置问题选项降级 | Codex |
| R-15 | `Builds/` 产物与源码版本脱节（无清单/无 SHA） | 高 | 低 | 4 个历史产物无 `manifest.json` | `-Mode Package` 已生成路径/字节/SHA256 清单 | DSH |
| R-16 | 无 Git 基线导致任何回滚都不可行 | 高 | 高（已发生前提） | `git log` 0 提交 | 用户批准后建首个提交（含 `.gitattributes` + LFS 规则） | Director |
| R-17 | 磁盘写满导致构建中途损坏 | 中 | 中 | 15.1 GB 剩余 | 预检门槛 20 GB；构建前清理 | DSH |
| R-18 | 创空间静态空间的容量/单文件上限未知，上传失败 | 中 | 中 | 第三方资料未给出官方数值 | 上传前用 `manifest.json` 的 `totalMiB` 比对；先用最小包试探 | 部署 |
| R-19 | Docker 空间端口/健康检查要求未确认（第三方称 7860） | 中 | 低 | 无官方文档核实 | 首次部署以平台日志为准，`EXPOSE` 与 `uvicorn --port` 保持一致 | AI Engineer |
| R-20 | WebGPU 被误当作 HDRP 的 Web 出路 | 低 | 中 | Unity 6.3 中 WebGPU 仍实验且 HDRP 不支持 | 在评审中明确排除 | Director |

---

## 2. 风险与验收门槛的对应

浏览器版本验收前，下列条件必须**同时**满足，否则不予通过：

1. 由 URP 工程产出，`GraphicsSettings.m_CustomRenderPipeline` 指向 URP 资产（B-01 解除）；
2. `manifest.json` 显示首包 ≤ 40 MB，或 Director 书面同意放宽并给出加载等待方案；
3. 本地 `serve-webgl.mjs` 与真实托管端两种环境都能加载（R-05）；
4. 桌面 Chrome/Edge 通过 `BuildAndDeploymentPlan.md` §5 的 10 项清单；
5. 构建产物中扫描不到任何 API Key / 令牌字符串（R-11）；
6. 交付包附带 `manifest.json`（含 SHA256）与构建日志（R-15）。

## 3. 本轮已执行的验证

1. 执行 `Tools/Build/Invoke-WebGLBuild.ps1` → 3 FAIL / 5 WARN / 退出码 2；
2. 在 HDRP 包缓存（`Library/PackageCache/...high-definition@2d37db618c5e`）统计 148 个 `.compute`、`UNITY_WEBGL` 0 命中；
3. 核对 `ProjectSettings.asset` 全部 `webGL*` 键与 `Builds/M2` 实际大文件；
4. 实测 `Tools/Build/serve-webgl.mjs` 的 MIME 与 `Content-Encoding` 行为；
5. Web 检索确认 Unity `WebGLCompressionFormat` 语义与 ModelScope 创空间四种 SDK 类型。

## 4. 未验证事项

| 项 | 说明 |
| --- | --- |
| 真实 WebGL 首包体积 | 无产物 |
| 创空间对 `.br` 的响应头、容量上限、Docker 端口 | 需实测/官方文档 |
| URP 转换后场景视觉是否可接受 | 无 URP 工程 |
| WebGL 下 TMP 中文与 IME 的实际表现 | 无产物 |
| 移动浏览器可玩性 | 无触摸绑定，未测 |

## 5. 下一步

1. 用户裁决 B-01（路线 A 或 C）；
2. Codex 解除 B-02/B-03/B-04；
3. DSH 在 URP 工程上执行四步流水线并回填本报告 R-03/R-05 的实测值；
4. Director 按 §2 的 6 条门槛做验收裁定。
