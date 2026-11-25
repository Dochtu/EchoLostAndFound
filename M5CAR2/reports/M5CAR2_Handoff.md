# M5-C-A-R2 交接说明

## 1. 本轮结束状态

- 服务端代码与 R1 相同（无业务逻辑变更）；本轮新增的是 `M5CAR2/` 下的证据、工具、报告与包。
- 回归：278 单元/接口 + 25 E2E 全通过；敏感信息扫描 0 命中；未调用真实模型。
- Git：已按精确路径完成一次**本地提交**（未 push、未 reset、未 clean）。提交哈希与提交后状态见 `M5CAR2/evidence/git/post-commit.txt` 与最终答复。
- 平台：仅输出预检方案，未部署、未改线上创空间。
- 客户端：仅输出集成契约，未改 Unity/M6-C。

## 2. 产物索引

| 产物 | 位置 | 说明 |
| --- | --- | --- |
| 源码快照 | `M5CAR2/packages/ServerSource.zip` | 74 文件，含 tests/tools |
| 部署候选 | `M5CAR2/packages/DeploymentCandidate.zip` | 40 文件，`app/**` 与源码逐字节一致 |
| 包清单 | `M5CAR2/evidence/packages.json` | 含四项哈希、排除项、一致性断言 |
| 源码哈希 | `M5CAR2/evidence/git/source_sha256.txt` | ServerSource 逐文件 |
| Git 状态快照 | `M5CAR2/evidence/git/status-all.txt` | 提交前 `git status --porcelain -uall` |
| 提交清单 | `M5CAR2/evidence/git/commit_file_list.txt` | `git add --` 的精确路径 |
| 提交后记录 | `M5CAR2/evidence/git/post-commit.txt` | 哈希、文件数、提交后状态 |
| 测试 | `M5CAR2/evidence/tests/` | JUnit、控制台、汇总 |
| E2E | `M5CAR2/evidence/e2e/` | 25 项结果、日志 |
| 扫描 | `M5CAR2/evidence/security/` | JSON + 控制台 |
| WebGL 清单 | `M5CAR2/evidence/browser/build_manifest.sha256` | 17 文件逐文件哈希 |
| 报告 | `M5CAR2/reports/*.md` | 7 份 |
| 报告包 | `M5CAR2_Reports.zip` | 根目录 |
| 部署说明 | `M5CAR2/deploy/DEPLOY_R2.md` | 也在 DeploymentCandidate.zip 内 |

## 3. 复现命令

```powershell
cd G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest -q --junitxml=..\M5CAR2\evidence\tests\junit_r2.xml
cd ..
Server\.venv\Scripts\python.exe M5CAR2\e2e\run_e2e_r2.py
Server\.venv\Scripts\python.exe M5CAR2\tools\summarize_tests.py
Server\.venv\Scripts\python.exe M5CAR2\tools\scan_secrets_r2.py
Server\.venv\Scripts\python.exe M5CAR2\tools\list_commit_files_r2.py
Server\.venv\Scripts\python.exe M5CAR2\tools\build_packages_r2.py
```

注意：

- pytest 必须在 `Server` 目录运行；仓库根目录会因 `testpaths` 相对路径产生大量收集错误。
- 包构建脚本拒绝覆盖已有产物；重建前先移走 `M5CAR2/packages/*.zip` 和根 `M5CAR2_Reports.zip`。
- 含中文的文件不要用 PowerShell `Get-Content`/`Set-Content` 往返（会损坏编码）；用 Python `encoding='utf-8'`。

## 4. 关键决策与理由

1. **R2 包放 `M5CAR2/packages/`，不覆盖根目录 R1 包**：覆盖会使 `M5CAR1/evidence/packages.json` 记录的哈希失效，破坏 R1 的可审计性。根目录只新增 `M5CAR2_Reports.zip` 与 `M5CAR2_Package_SHA256.txt`。
2. **WebGL 不重建，只核对**：Unity/M6-C 属 Codex 写权限；R2 复用 `M5CAR1/local_candidate/webgl`（M4C 构建）验证“同源静态站”能力，并逐字节追溯 `Builds/M4C-Closeout-Player`。它不是 M6-C 候选。
3. **提交范围**：Server 全部源码/测试/工具 + `M5CAR1` 报告/工具/E2E/证据 + `M5CAR2` 报告/工具/证据 + 根 `.gitignore` 加固补丁。排除：Unity 工程修改（Codex M6-C）、`Deploy/`、`M6C_Work/`、`Builds/`、根 `*.zip`/`*.sha256`、私有 SQLite 台账、浏览器 profile、缓存。
4. **`.gitignore` 纳入提交**：它包含本项目自己加的忽略规则（`/*.zip`、`/Server/.local/`、`*/M5CA/evidence/` 等），是防止私有台账与包误入库的一部分；其余 24 个已修改的 Unity 文件均不提交。
5. **不进入 M5-C-B**：按任务要求在本轮结束。

## 5. 遗留与下一步（需授权）

| 事项 | 状态 | 需要谁 |
| --- | --- | --- |
| 平台持久化/重启预算恢复实测 | 未执行 | 用户授权 + 临时创空间 |
| 平台代理拓扑与 XFF 可信范围 | 阻塞 | 用户/平台结论，或部署只读头回显探针 |
| 独立可信预算记录 | 无可行外部方案 | 产品决策（接受残余风险或引入外部存储） |
| 首轮 ≤5 次真实模型请求 | 未执行 | 用户授权 + 余额确认 |
| API Key 平台注入与镜像扫描 | 方案已有，未实测 | 用户授权 |
| 客户端 7 项集成落地 | 仅契约 | Codex M6-C |
| 客户端刷新恢复/中文 IME 实测 | 未验证 | Codex M6-C + 真实浏览器 |

## 6. 给下一位接手者的提醒

- 不要执行 `ledger_admin reset`；不要手工改台账或 epoch。
- 不要在 `Server` 目录外运行 pytest，也不要在仓库根 `git add -A`。
- 真实模型一旦开启，先看 `GET /api/v1/health` 的 `ledger`、`model_ready`、`is_synthetic`。
- 任何“接口测试通过”都不能替代 Unity 实机玩法验证。
