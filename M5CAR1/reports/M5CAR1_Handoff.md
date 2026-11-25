# M5-C-A-R1 交接

## 1. 当前状态

| 项 | 状态 |
| --- | --- |
| 分支 | `m5c-a-dev`，基线 HEAD `4c51712c362e18bfcf9215cea766e61731773c74` |
| 代码/测试 | 278 通过（`pytest -q`），25/25 进程级 E2E 通过 |
| 工作区 | `Server/` 与 `M5CAR1/` 绝大多数文件**未跟踪**；未执行任何 `git add/commit` |
| 真实模型 | 未调用；魔粒未消耗；线上创空间未触碰 |
| 待批准 | M5-C-B；以及本文第 2 节的本地提交授权 |

## 2. 需要授权才能执行的动作：本地 Git 提交

**未执行**。如果要提交，请用下面这一条（只添加预生成清单里的路径，不用 `-A`）：

```powershell
cd G:\projects\EchoLostAndFound
git add -- $(Get-Content M5CAR1\evidence\git\commit_file_list.txt |
            Where-Object { $_ -and -not $_.StartsWith('#') })
git status --short          # 先复核，再决定是否 commit
```

- 清单：`M5CAR1/evidence/git/commit_file_list.txt`（**146 个文件**，逐行可审）
- 清单由 `M5CAR1/tools/list_commit_files.py` 生成，规则固定、可复算
- 明确不加入：`Server/.venv/**`、`Server/.local/**`、`M5CAR1/evidence/e2e/state/*.sqlite3`、
  浏览器 profile、根目录 `*.zip`、`Builds/M5CAR1/**`、`Server/pytest-verbose.txt`
- 建议提交信息：`M5-C-A-R1: 安全补强（上下文预算/知识边界/状态真实性/代理责任层）与新增 72 项测试`
- **不要**执行 `git add -A`、`git push`、`git reset`、`git clean`（本轮任务书明确禁止）

已知注意点：`Server/` 目前只有 3 个文件被跟踪，本次提交会把整个 `Server/` 源码首次纳入版本管理，
请确认这是预期行为后再提交。

## 3. 人工联调清单（浏览器，需人工交互）

前置：

```powershell
cd G:\projects\EchoLostAndFound
$env:APP_ENTRY_MODE="mock"; $env:MODEL_PROVIDER="mock"
$env:WEB_ROOT="G:\projects\EchoLostAndFound\M5CAR1\local_candidate\webgl"
Server\.venv\Scripts\python.exe -m app.server_entry     # 监听 7860
# 客户端固化了 http://127.0.0.1:8787，若要真实联调请改用：
#   Server\.venv\Scripts\python.exe -m uvicorn app.entry:app --host 127.0.0.1 --port 8787 --no-proxy-headers
```

然后浏览器打开 `http://127.0.0.1:8787/`（或 7860，取决于是否改客户端基址）。

| # | 检查 | 通过标准 | 本轮状态 |
| --- | --- | --- | --- |
| 1 | 页面加载 | 出现 Unity 加载界面并进入游戏场景（非 0% 卡死） | 🟡 仅证明到资源加载与引擎启动 |
| 2 | 两名 NPC 对话 | 老周、林遥都能进入对话并返回符合人设的内容 | ❌ 未验证 |
| 3 | 中文输入 | 输入中文（含标点）能正常发送并得到中文回复 | ❌ 未验证 |
| 4 | 证据 E01–E05 | 五件证据都能出示，页面状态与 `GET /api/v1/sessions/{id}` 一致 | ❌ 未验证（服务端已验） |
| 5 | 披露 D01–D03 | 两种证据顺序都能触发对应披露 | ❌ 未验证（服务端已验） |
| 6 | 双路线结算 | 两条保管路线都能走到结算画面（Unity 侧） | ❌ 未验证（服务端前置已验） |
| 7 | 浏览器刷新恢复 | 刷新后能恢复当前会话；若服务端重启导致 404，客户端应给出可理解的提示并可重建会话 | ❌ 未验证（服务端 404 已验） |
| 8 | 降级仍可通关 | 模型超时/额度耗尽时，固定台词仍能支撑完整流程 | ❌ 未验证（服务端降级已验） |

记录建议：每一步截图 + `GET /api/v1/health` 的 `data` 原文 + 该次会话的 `GET /api/v1/sessions/{id}`。

## 4. 若要把浏览器联调做完整：Unity 客户端影响清单（**本轮未修改，仅列出**）

| 影响点 | 现状 | 建议改动 | 风险 |
| --- | --- | --- | --- |
| API 基址 | 构建内固化为 `http://127.0.0.1:8787` | 改为可运行时注入（`index.html` 里 `window.__API_BASE__` 或 query 参数） | 低；只影响初始化 |
| 鉴权头 | 未见 `X-Dialogue-Token` 使用 | 若启用本地令牌校验，需在客户端加自定义头 | 中；涉及请求封装 |
| 错误处理 | 未知 | 需要对 404（会话过期）、429（限流）、503（预算耗尽）给出可操作提示 | 中；涉及 UI |
| 会话恢复 | 未知 | 刷新后用本地保存的 `conversation_id` 调 `GET /sessions/{id}`，404 则重建 | 中；涉及存档 |
| 构建产物 | `Builds/M4C-Closeout-Player` | 若需重新构建，属于 Unity 工程写入，需 Game Director 授权并避开 M6-B | 高；需美术/程序协商 |

以上任何一项都需要**先取得跨模块授权**，本轮遵守边界未动 `Assets/`、`EchoLostAndFound_WebGL/`、`Builds/`。

## 5. 平台侧待确认（真实模型上线阻塞）

见 `M5CAR1_ModelScope_Preflight.md` 第 9 节，共 10 项。其中两项是硬阻塞：

1. `/mnt/workspace` 是否会与数据库一起被回滚；是否有平台侧独立审计。
2. 平台反代是否透传 `X-Forwarded-For`、代理网段范围。

## 6. 如何复算本次全部证据

```powershell
cd G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest -q --junitxml=..\M5CAR1\evidence\tests\junit_r1.xml   # 278 passed
cd ..
Server\.venv\Scripts\python.exe M5CAR1\e2e\run_e2e_r1.py                                   # 25/25, exit 0
Server\.venv\Scripts\python.exe M5CAR1\tools\scan_secrets.py                               # 0 hits
Server\.venv\Scripts\python.exe M5CAR1\tools\capture_prompt_samples.py                     # 生成脱敏 Prompt 样本
Server\.venv\Scripts\python.exe M5CAR1\tools\list_commit_files.py                          # 提交清单
powershell -NoProfile -File M5CAR1\deploy\build_candidate_r1.ps1                           # 安全组装候选
Server\.venv\Scripts\python.exe M5CAR1\tools\build_packages.py                             # 打三个包 + MANIFEST
```

浏览器探针（可选，需本机 Chrome）：`M5CAR1\tools\candidate_probe.py`、`render_probe.py`。

## 7. 建议的下一步

1. 复核本报告包与完成矩阵，确认 6 项"未验证/阻塞"的定性是否接受；
2. 授权第 2 节的本地提交；
3. 在人工会话中执行第 3 节清单，产出浏览器侧证据；
4. 取得平台侧两个答案后，再按 5 次请求方案做真实模型预检；
5. 批准后再进入 M5-C-B。
