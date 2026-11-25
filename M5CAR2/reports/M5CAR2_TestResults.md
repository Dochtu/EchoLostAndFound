# M5-C-A-R2 回归测试与证据核对

## 1. 环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11（10.0.26200） |
| Python | 3.12.14（`Server\.venv`） |
| pytest | 9.2.0 |
| 工作目录 | `G:\projects\EchoLostAndFound\Server`（必须；仓库根目录会因相对 testpaths 产生约 250 个收集错误） |
| 服务端代码版本 | 与 R1 相同，本轮未修改业务代码 |
| 真实模型 | 未调用；E2E 使用本地 fake upstream |

## 2. 单元 / 接口测试

```powershell
cd G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest -q --junitxml=..\M5CAR2\evidence\tests\junit_r2.xml
```

结果（`evidence/tests/junit_r2.xml`）：

- **278 passed, 0 failed, 0 errors, 0 skipped**，13.655 s；
- 控制台 `evidence/tests/pytest_r2.txt`：进度点 + 1 条 `StarletteDeprecationWarning`（`fastapi/testclient.py` 提示改用 `httpx2`），与 R1 `pytest_r1.txt` 形态一致；
- 测试文件 27 个，覆盖接口契约、鉴权、限流、代理头、预算/台账、故障注入、知识权限、NPC 披露、静态站、Provider 等。

### 2.1 证明“没有删测试或降断言”

`M5CAR2/tools/summarize_tests.py` 以 `classname::name` 为键解析 R1、R2 两份 JUnit XML：

| 项 | R1 | R2 |
| --- | ---: | ---: |
| tests | 278 | 278 |
| failures / errors / skipped | 0 / 0 / 0 | 0 / 0 / 0 |
| 耗时 | 13.143 s | 13.655 s |
| 测试 ID 集合 | 基准 | **完全相同** |

`same_test_ids: true`，`removed_test_ids: []`，`added_test_ids: []`。本轮没有新增测试，也没有删除、改名或跳过任何用例。汇总见 `evidence/tests/tests_summary.json`。

## 3. 进程级 E2E

```powershell
Server\.venv\Scripts\python.exe M5CAR2\e2e\run_e2e_r2.py
```

- **25/25 检查通过**，退出码 0；证据 `evidence/e2e/e2e_r2_results.json`、控制台 `e2e_r2_console.txt`、服务日志 `logs/`；
- 驱动由 R1 驱动复制而来（928 行），端口 19100，`fake_upstream = Server/tools/fake_llm_server.py`（本地 socket，**不是真实模型**），结果中 `real_model_called: false`；
- 覆盖组：
  - **M**：mock 入口、health 字段与 `is_synthetic`、E01–E05 证据、D01–D03 + REC.engraving、两个普通 HTTP 客户端读同一会话（注意：不是浏览器刷新）、会话隔离、固定台词、证据顺序无关。
  - **L**：live 台账可启动、配置未证明时 readiness、fake 上游仍标 synthetic、响应不含密钥、上游失败只调用一次不重试、超时确定性计数、失败后固定内容仍可用、台账结算。
  - **R**：进程重启后用量保持（R1）、旧会话重启后 404（R2）、新会话可用（R3）。
  - **B**：紧预算启动、全局上限、token 预算在调用上游前拒绝、损坏台账拒绝 live 启动（`RuntimeError: APP_ENTRY_MODE=live refused: budget ledger unusable (ledger_corrupt)`）。
  - **P**：伪造 `X-Forwarded-For` 不能买到新桶（200 后 429）、新会话预算按会话生效（201, 201, 429, 429）。
- 限制：E2E 是**服务端接口级**验证，不等于 Unity 玩法测试，也不等于浏览器端完整对话验证。

## 4. 敏感信息扫描

```powershell
Server\.venv\Scripts\python.exe M5CAR2\tools\scan_secrets_r2.py
```

- `files_considered = 284`，`scanned_files = 165`，`credential_hit_count = 0`；
- 扫描根：`Server/`、`M5CAR1/`、`M5CAR2/`、`Deploy/` 与根配置；跳过 `.venv`、缓存、二进制、私有台账；
- 识别出的私有状态（仅记录，不打包、不入库）：
  - `M5CAR1/evidence/e2e/state/{broken,dbg-tokens,live,tight,tokens}.sqlite3`
  - `M5CAR2/evidence/e2e/state/{broken,live,tight,tokens}.sqlite3`
- 结果 `evidence/security/secret_scan.json`；命中 0 不代表凡密钥都已被识别，提交前仍做了暂存内容复核（见 Git 报告）。

## 5. 交付包一致性核对

`build_packages_r2.py` 的断言全部通过：

| 检查 | 结果 |
| --- | --- |
| `ServerSource.zip` 文件数 / 大小 | 74 / 163,583 B |
| `DeploymentCandidate.zip` 文件数 / 大小 | 40 / 91,956 B |
| 部署包 `app/**` 与源码 `Server/app/**` 逐文件哈希 | 完全一致 |
| WebGL 候选目录文件数 | 17（21,412,143 B） |
| WebGL zip 哈希 | `0e408df2…9bb2`，与 R1 记录一致 |
| WebGL zip 成员哈希 vs 目录 | 完全一致 |
| WebGL 目录 vs `Builds/M4C-Closeout-Player` | 17/17 字节一致 |

## 6. 未执行项（不得视为通过）

- Docker 镜像在 R2 **未重新构建**；R1 曾构建并运行，本轮仅保留其结论，未重复验证。
- 真实模型请求、魔粒结算、平台持久化、平台代理头：未执行。
- Unity EditMode/PlayMode、Chrome 实机玩法、WebGL 刷新恢复：不在本轮范围。
- 浏览器端 UI 手测：未执行。

## 7. 失败处置记录

- 首次复制 E2E 驱动时用 PowerShell `Get-Content -Raw` / `Set-Content` 造成中文损坏（`SyntaxError: unterminated string literal`，第 529 行）。改用 venv Python 以 UTF-8 读写后修复，并加 `ast.parse` 校验；此后所有中文文件均用 Python 或 write 工具处理。
- 首次打包时源码/部署包 `app/` 比对的键前缀写错（`Server/` vs `Server/app/`），脚本报错退出；修正后重建，未产生不完整产物入库。
