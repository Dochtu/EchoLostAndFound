# M4-C 移交给 Codex

- 阶段：M4-C（后端稳定性 + 第一章调查交互 + Unity↔FastAPI 联调 + WebGL 验收 + 魔搭预检）
- 执行者：DSH（本轮独立执行）
- 状态：C1–C5 全部完成并按矩阵标注；公网与真实模型相关项保留 UNVERIFIED
- 建议下一步：技术负责人验收 → 决策待裁定项 → 提交（本轮未提交）→ 进入 M5

---

## 1. 一眼看清做了什么

| 模块 | 变化 |
| --- | --- |
| 后端 `Server/app` | 会话隔离 + 容量上限；模型调用全异步（`httpx.AsyncClient`）；request_id 五态修正；请求体限制、日志脱敏、限流只打 API；新增同源静态站 |
| 后端测试 `Server/tests` | 77 → **123 passed**（+5 个新文件 / 改写 4 个文件） |
| Unity 脚本 | 新增 `StationTargets`、`StationInvestigationGates`、`StationApiClient`、`StationDialogueBridge`；`StationHud`/`StationPlayer` 改造；场景新增林遥/失物包/副联册/西窗 |
| Unity 测试 | EditMode 15/15（+9）、PlayMode 6/6（+3，在线离线各跑一遍） |
| WebGL | 构建 #3：21,364,584 B / 17 文件 / gzip；字体重烘 520 字 |
| 验收 | 5 组真实浏览器 E2E 全绿（含 RTX 4060 真实 GPU、离线、重启恢复、Docker 容器） |
| 部署 | `Deploy/` 统一镜像，本地 `docker build` + `docker run` + 容器内 E2E 已验证 |

---

## 2. 接手前必须知道的三件事

1. **`Packages/manifest.json` 多了一行** `"com.unity.modules.unitywebrequest": "1.0.0"`。
   这是 `UnityWebRequest` 能在 Unity 6 里编译的必要条件；不带这行提交，`StationApiClient.cs` 会 `CS1069` 编译失败。属于"为编译所必需的最小包清单变更"，未升级任何版本、未换管线。

2. **没有提交任何 Git 改动**（按 AGENTS 与任务要求）。当前 HEAD 仍是 `4c51712`，工作区 107 条改动（24 modified / 83 untracked），其中大部分是 M3-A/M4-A/M4-B 遗留。归属见 `M4C_FileChanges.md`。

3. **灰盒坐标是待裁定项**。`Docs/Chapter01ImplementationMap.md` §12 明确"驻点/热点/读单/交接锚点坐标 待确认"。当前林遥 `(-5.4,0,1.3)`、失物包 `(1.86,0.93,0.55)`、副联册 `(-1.5,1.03,1.0)` 等只是保证可达的灰盒摆位，不是美术定稿。

---

## 3. 代码怎么读（按优先级）

### 后端

1. `Server/app/sessions.py` —— 会话隔离与容量。重点看 `create()`（不再关闭他人会话）、`_make_room_locked()`（淘汰顺序）、`TERMINAL_RETENTION_SECONDS`。
2. `Server/app/providers/llm_provider.py` —— `AsyncClient` 惰性创建 + `aclose()`；超时/状态/传输错误映射保持原语义。
3. `Server/app/main.py` —— 中间件顺序 **CORS（最外）→ guard → BodySizeLimit → router**；`request.state.request_id_from_header` 是 body-only 修复的关键；限流只对 `/api/v1/*` 生效。
4. `Server/app/static_site.py` —— 同源托管；`.gz` 显式请求必须声明 `Content-Encoding`（Unity 对此极敏感）。
5. `Server/app/middleware.py`、`logging_utils.py` —— 体积限制与脱敏。

### Unity

1. `Assets/Station/StationHud.cs`（约 560 行）—— 交互总入口 `Interact(IInteractable)`、怀表五部位、失物包/副联册/维修柜菜单、自由输入行、`Present()` 后的披露镜像。
2. `Assets/Station/StationApiClient.cs` —— 协程 + 手工超时轮询（WebGL 上 `UnityWebRequest.timeout` 不可靠）。
3. `Assets/Station/StationDialogueBridge.cs` —— 在线状态机、版本校验、离线提示、`StationReply.Attribution`（区分 `external_model`/`mock`/`fallback`）。
4. `Assets/Station/StationInvestigationGates.cs` + `StationTargets.cs` —— 门槛与标签映射（测试与 UI 共用，别在 HUD 里再写一套判断）。

### 测试与证据

- `Server/tests/test_{isolation,request_id,concurrency,public_safety,static_site}.py`
- `Assets/Tests/Editor/M4CInvestigationTests.cs`、`Assets/Tests/PlayMode/M4C{Station,Online}PlayTests.cs`
- `M4C/Scripts/m4c-e2e.mjs`（端到端驱动）、`M4C/Logs/`、`M4C/E2E/`

---

## 4. 已知坑（省时间）

| 坑 | 说明 |
| --- | --- |
| PowerShell 5.1 + 中文 | `Get-Content`/`Set-Content` 管道改文件会把 UTF-8 中文读成 ANSI 造成不可逆乱码。**不要**用它改代码/脚本，用编辑工具；`.ps1` 需存 UTF-8 with BOM |
| `pwsh` 不存在 | 只能用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File …` |
| `$PSScriptRoot` 为空 | PS 5.1 `-File` 模式下可能为空，`Deploy/build.ps1` 已做三级回退 |
| Unity batchmode | 必须带 `-projectPath`；`-logFile` 不要复用同名文件（会截断证据）；同时只能有一个 Unity 实例持有工程 |
| Unity 6 内建模块 | 用 `UnityWebRequest` 必须在 `manifest.json` 显式声明模块 |
| WebGL 输入 | 无隐藏 DOM input；`Input.insertText` 无效，须逐字符 `dispatchKeyEvent {type:'char'}` |
| 有窗口 Chrome | 单次鼠标位移 > ~40 px 会被窗口边缘截断，自动化要分步（≤40 px） |
| Mock 超时 | `mock_provider` 是瞬时返回 `timeout` 行为，不是真挂起；真实超时未验证 |
| 静态资源与限流 | 一次页面加载 10+ 请求，限流必须排除静态资源，否则 429 `loader.js` |
| 测试 profile | E2E 必须复用同一 Chrome profile 才能验证持久化；旧代码 `existsSync` 回退会静默用新 profile |

---

## 5. 待裁定（需产品/Director 决策，不要自行拍板）

1. **灰盒锚点坐标**：是否按新美术布局重排（会影响 E2E 行走路径与 PlayMode 断言）。
2. **故障卡背面索引是否持久化**：现状是会话内标记（E05 证据本身持久化），刷新后要重读索引才能再取 E05。若要求"读过即永久"，改 `StationInvestigation` 快照结构 + 迁移旧存档。
3. **箱签文字 / 暂收回执版面 / A01、R01、R02**：地图未定稿，本轮未做。第一章完成判定（E01 + A02）因此未实现结算 UI。
4. **公网开放策略**：Mock 公开体验 vs 真实模型（需访问码/额度/告警），见 `M4C_ModelScope_Preflight.md` §4。
5. **提交策略**：是否连同 M3-A/M4-A/M4-B 遗留改动一起提交，或按阶段拆分提交。

---

## 6. 建议的下一步工作顺序

1. **验收本轮**：按 `M4C_CompletionMatrix.md` 逐条核对；重点复核 `Packages/manifest.json` 变更与 123 项后端测试。
2. **提交整理**：建议拆成 3 个提交（后端 C1 / Unity C2+C3 / 部署与证据 C5），`Deploy/context/` 已被 `Deploy/.gitignore` 排除。
3. **补齐第一章结算**：实现 A02 确认与"E01 + A02"完成度 UI；再考虑 A01/R01/R02。
4. **真实模型接入**：先在受控环境用真实 key 跑 `MODEL_PROVIDER=llm`，验证超时/限流/成本，再决定是否公网开放。
5. **美术替换灰盒**：保持交互体名字与 `StationTargets` 标签不变，PlayMode/E2E 断言可继续复用（行走路径需按新布局调整）。
6. **平台上线**：按 `M4C_ModelScope_Preflight.md` §5 清单执行，并复测 gzip 头与首屏。
7. **可选强化**：真实 IME 组合输入验证、压力测试、会话长跑回收、静态资源长效缓存。

---

## 7. 交付物索引

| 文件 | 用途 |
| --- | --- |
| `M4C_Delivery_Report.md` | 总览、逐任务说明、风险、UNVERIFIED |
| `M4C_CompletionMatrix.md` | 逐条状态矩阵（DONE/PARTIAL/UNVERIFIED） |
| `M4C_TestResults.md` | 全部测试与运行证据、复现命令 |
| `M4C_FileChanges.md` | 文件改动与归属、Git 状态说明 |
| `M4C_WebGL_Report.md` | 构建、响应头、浏览器验收、截图索引 |
| `M4C_ModelScope_Preflight.md` | 部署结构、已验证项、风险与上线清单 |
| `M4C_HandoffToCodex.md` | 本文件 |

证据目录：`M4C/Logs/`、`M4C/E2E/`、`M4C/Scripts/`；部署件：`Deploy/`。
