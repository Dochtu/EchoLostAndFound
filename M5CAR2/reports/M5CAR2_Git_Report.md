# M5-C-A-R2 Git 报告

- 阶段：M5-C-A-R2 工程归档与上线预检
- 日期：2026-11-25
- 范围：仅本地 Git 归档（技术负责人已批准本地 commit）。未执行 push、reset、clean、add -A。
- 结论：**本地提交已完成**，提交对象只包含 `Server/` 源码、`M5CAR1/` 与 `M5CAR2/` 的证据和报告，以及根 `.gitignore` 的 M5-C-A 保护规则。Unity 工程、`Deploy/`、`M6C_Work/`、`Builds/`、归档 zip、SQLite 账本与运行日志均未进入提交。

> 提交完成后的权威证据见 `M5CAR2/evidence/git/post-commit.txt`（由 `git log -1`、`git show --stat`、`git status --porcelain=v1 -uall` 原样生成）。本报告中的暂存统计取自提交前最后一次 `git diff --cached` 检查。

## 1. 执行前基线

| 项目 | 值 |
| --- | --- |
| 工作目录 | `G:\projects\EchoLostAndFound` |
| 当前分支 | `m5c-a-dev` |
| HEAD | `4c51712c362e18bfcf9215cea766e61731773c74`（`Baseline HDRP, M3-A WebGL and M3-B before M4-A integration`） |
| 暂存区初始状态 | 0 个文件（`git diff --cached --name-only` 为空） |
| 工作区初始状态 | 25 个已跟踪文件被修改（24 个 Unity 工程文件 + `.gitignore` + `Server/requirements.txt` 中的 Unity 部分），142 个未跟踪路径 |
| `git status --porcelain=v1 -uall` | 167 行（随后因 M6-C 工作区活动增长到 251 行，见 `status-all.txt`） |

基线与 R1 交接文档一致，说明 R1 结束时没有遗留暂存内容；本次提交不存在"混入他人暂存区"的前提。

## 2. 与其他 Agent 的冲突核验

1. **暂存区**：提交前 `git diff --cached` 为空。Codex 的 M6-C 授权文件（`M6C_Work/M6C_UserAuthorization.txt`）明确禁止其执行 `git add`、`commit`、`push`、`reset`、`clean`，因此暂存区没有 Codex 的改动可混入。
2. **工作区**：25 个已修改的已跟踪文件全部是 Unity 工程（`EchoLostAndFound_WebGL/Assets/**`、`Packages/`、`ProjectSettings/`、`Tests/Editor/M3A.EditMode.asmdef`）与 `.gitignore`、`Server/requirements.txt`。它们与 M6-C 的 Unity 升级工作重叠，**不属于本轮服务端归档范围，全部留在工作区未提交**。
3. **服务端**：`Server/` 最新修改时间为 2026-11-25 12:33（R1 收尾），Codex 的 M6-C 活动时间为 16:30 之后；`M6C_Work/Baseline/git-status.txt` 与当前 Unity 修改一致，未见 `Server/` 业务文件改动。M6-C 授权同时禁止 Codex 修改根 `Server/`、Provider、安全策略与接口协议，故服务端不存在跨 Agent 冲突。
4. **目录边界**：`Deploy/`（Codex 的部署上下文副本，含旧 `server/` 与 `webgl/`）、`M6C_Work/`、`Builds/` 均为其他工作的未跟踪目录，未纳入提交。

## 3. 可恢复源码快照

- `M5CAR2/packages/ServerSource.zip`：提交范围内 `Server/` 全部 74 个源文件（已排除 `.venv`、缓存、账本、日志与本地 `.env`），163,583 B，SHA-256 `9ae2c2b41c2c062ace0c3ac7d0fea10114ef08015e71ecec4c71f47e2d05d9c5`。
- `M5CAR2/evidence/git/source_sha256.txt`：上述每个源文件的 SHA-256 明细，可用于逐文件还原校验。
- 两者与提交对象中的 `Server/` 内容一致（`build_packages_r2.py` 以工作区同一份文件生成，且 `DeploymentCandidate.zip` 的 `app/**` 哈希与 `Server/app/**` 逐一相等）。

## 4. 提交文件清单与统计

提交由 `M5CAR2/tools/list_commit_files_r2.py` 生成的**精确路径清单**驱动（保留 R1 的 146 条路径，追加 `M5CAR2/{reports,tools,e2e,deploy,evidence,packages}` 与根 `.gitignore`，并沿用 R1 的排除规则）。暂存命令只使用逐路径形式：

```
git add -- <清单中的精确路径>
```

未使用 `git add -A`、`git add .` 或 `-f`。

提交前暂存区检查结果：

| 项目 | 结果 |
| --- | --- |
| 暂存文件数 | 141 |
| 分类 | `Server/` 71；`M5CAR1/` 44；`M5CAR2/` 25；根 `.gitignore` 1 |
| 行数变化 | 55,871 insertions, 1 deletion |
| 禁止类型核验 | 无 `.sqlite3`/`.db`/`.zip`/`.pyc`；无 `EchoLostAndFound_WebGL/`、`M6C_Work/`、`Deploy/`、`Builds/` 路径 |

说明两处清单与实际差异，均为预期行为：

1. **2 个 `.gitkeep` 不产生差异**：`Server/app/.gitkeep`、`Server/tests/.gitkeep` 已在 HEAD 中以空 blob 跟踪（`e69de29b…`），`git add` 后内容不变，故 `git diff --cached` 为 141 而非路径清单的 143（非日志路径）。
2. **40 个 `*.log` 被根 `.gitignore` 拒绝**：E2E 与浏览器探测日志（`M5CAR1/evidence/e2e/logs/`、`M5CAR2/evidence/e2e/logs/`、`M5CAR1/evidence/browser/**` 等）命中忽略规则，`git add` 报 "paths are ignored" 并跳过。**未使用 `-f` 强行加入**：日志保留在工作区，并完整包含在 `M5CAR2_Reports.zip` 与各证据目录中，只是不进入 Git 历史。因此提交对象为 141 个文件，而非清单中的 181 条路径。

## 5. 敏感信息检查

1. **R2 扫描器**（`M5CAR2/tools/scan_secrets_r2.py`）：覆盖 `Server/`、`M5CAR1/`、`M5CAR2/`、`Deploy/` 与根配置，共 271 个候选、156 个文本文件，**凭据命中 0**。
2. **暂存索引正则检查**（`git grep --cached`）：对 `sk-…`、`ms-…`、`AKIA…`、`BEGIN … PRIVATE KEY` 的硬凭据模式命中 0（grep 退出码 1）。
3. **占位符复核**：`LLM_API_KEY=…`、`api_key=…`、`password=…` 的命中仅出现在 `.env.example`、部署文档与日志脱敏说明中，均为占位值或文档文本，不含真实密钥。
4. **私有账本**：`M5CAR1/evidence/e2e/state/*.sqlite3` 与 `M5CAR2/evidence/e2e/state/*.sqlite3` 存在于磁盘，但被清单排除规则与 `.gitignore` 双重拦截，未进入暂存区。
5. **本地环境文件**：`Server/.env` 不存在；`Server/.env.example` 仅含占位值。

## 6. 提交命令与信息

```
git add -- <M5CAR2/evidence/git/commit_file_list.txt 中的精确路径>
git commit -m "M5-C-A R2: archive server source and R1/R2 acceptance evidence"
```

提交只发生在本地 `m5c-a-dev` 分支，未推送、未改写历史、未清理工作区。

## 7. 提交后核验

提交后由 `M5CAR2/evidence/git/post-commit.txt` 记录：

- `git log -1 --format=fuller`（commit hash、作者、时间、message）；
- `git show --stat --oneline HEAD`；
- `git show --name-only --format="" HEAD`（提交文件清单）；
- `git status --porcelain=v1 -uall`（提交后工作区状态，预期仍保留 24 个 Unity 修改、`Deploy/`、`M6C_Work/`、`Builds/` 等未跟踪内容）。

**注意**：`post-commit.txt` 只能在提交产生 hash 之后生成，因此它本身不在提交内，也不在提交前构建的 `M5CAR2_Reports.zip` 内；这是有意的顺序约束，不是遗漏。

## 8. 风险与未执行项

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 远程推送 | 未执行 | 任务明确禁止 `git push` |
| 历史改写 / 清理 | 未执行 | 未使用 `reset`、`clean`、`--amend` |
| Unity 修改入库 | 未执行 | 属 Codex M6-C 范围，等待其独立交付 |
| `Deploy/` 入库 | 未执行 | Codex 部署上下文，非本阶段服务端归档对象 |
| 日志入库 | 主动排除 | 命中 `.gitignore`；证据保留在磁盘与报告 zip |
| 提交后工作区是否干净 | 否（预期） | 仍有他人未跟踪目录与 Unity 修改 |

## 9. 结论

- 本地提交满足"精确路径、无 `add -A`、无敏感文件、无跨 Agent 混入"的要求。
- 提交内容 = `Server/` 服务端源码（含 R1 安全补强）+ R1/R2 全部验收证据与报告 + `.gitignore` 保护规则。
- 服务端归档与 R1 通过的测试版本一致（`ServerSource.zip` 的 SHA-256 清单可复核）。
- 下一步需要用户/技术负责人授权的是**推送**与 **M5-C-B 阶段**，本轮不自动执行。
