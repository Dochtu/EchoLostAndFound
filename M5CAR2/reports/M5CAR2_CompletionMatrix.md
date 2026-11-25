# M5-C-A-R2 完成度矩阵

状态口径：**PASS**（有证据）、**PARTIAL**（部分完成/部分验证）、**NOT TESTED**（未执行）、**BLOCKED**（有明确阻塞）、**USER AUTH**（需用户授权）。

## 1. 任务要求逐项对照（m00001）

| # | 要求 | 状态 | 证据 / 说明 |
| --- | --- | --- | --- |
| 2.1 | 提交前检查分支、HEAD、工作区 | PASS | `evidence/git/status-all.txt`；分支 `m5c-a-dev`，HEAD `4c51712`，0 个已暂存 |
| 2.2 | 核查现有 146 文件提交清单 | PASS | `M5CAR1/evidence/git/commit_file_list.txt` 146 个路径全部存在，无缺失 |
| 2.3 | 检查密钥/私有库/缓存/无关修改 | PASS | 扫描 0 命中；私有 SQLite 台账 9 个已识别并排除；Unity/Deploy/M6C_Work 变更全部剔除 |
| 2.4 | 检查与 Codex M6-C 工作区冲突 | PASS | `M6C_Work/M6C_UserAuthorization.txt` 禁止 Codex 改根 `Server/` 与执行 Git；`Server/` 最新修改时间 12:33，早于 Codex 16:30 活动 |
| 2.5 | 保存可恢复源码快照 | PASS | `M5CAR2/packages/ServerSource.zip` + `source_sha256.txt` |
| 2.6 | 按精确路径 git add | PASS | `git add -- <commit_file_list.txt 中的路径>`，未使用 `-A` |
| 2.7 | 检查暂存列表、差异、敏感信息 | PASS | 暂存后 `git diff --cached --stat`、`--name-only` 与暂存内容扫描（见 Git 报告） |
| 2.8 | 本地 commit | PASS | 单一本地提交，未 push |
| 2.9 | 输出 commit hash、文件清单、提交后状态 | PASS（哈希见提交后记录） | `evidence/git/post-commit.txt`、`commit_file_list.txt`；因哈希无法包含自身，写在提交后生成的文件与最终答复中 |
| 3 | ServerSource.zip / DeploymentCandidate.zip | PASS | 见交付报告哈希 |
| 3 | evidence/packages.json | PASS | 包含四项产物、排除项、部署一致性结论 |
| 3 | evidence/git/status-all.txt | PASS | 提交前完整 `git status --porcelain -uall` |
| 3 | 最新源码 SHA256 清单 | PASS | `evidence/git/source_sha256.txt`（74 个文件） |
| 3 | WebGL 联调候选及哈希 | PASS | 目录 + zip + 源码构建三方一致；**M4C 构建，非 M6-C 候选** |
| 3 | 报告引用文件真实存在 | PASS | 本报告全部路径均已核对存在 |
| 3 | 归档文件与测试版本一致 | PASS | 源码快照取自测试通过的同一工作区；`requirements.txt` 与 R1 测试时一致 |
| 4.1 | 持久化目录及重启后预算恢复方案 | PARTIAL | 方案与判定门槛已写；**未在平台执行** |
| 4.2 | SQLite 台账与哨兵共同回滚风险 | PARTIAL | 风险机制与复现步骤已写；未在平台复现 |
| 4.3 | 独立可信预算记录可行性 | PARTIAL | 三个候选方案与结论已写；无可用的外部可信存储 |
| 4.4 | 代理拓扑与 XFF 可信范围 | BLOCKED | `TRUSTED_PROXY_CIDRS` 为空，平台拓扑无官方结论；未实测 |
| 4.5 | 服务端 API Key 安全注入 | PARTIAL | 方案（平台环境变量/密钥）已写；未在平台验证日志与镜像不含密钥 |
| 4.6 | 首轮 ≤5 次真实请求测试方案 | PASS（方案） | 逐次请求清单、记录项、停止条件已写；未执行 |
| 4.7 | 异常即停并回滚 Mock 方案 | PASS（方案） | 停止/回滚/核对台账步骤已写；未演练 |
| 4.8 | 不伪造平台结果 | PASS | 所有平台项均标注“未执行” |
| 4.9 | 不调用真实模型、不耗魔粒、不改线上 | PASS | E2E 使用本地 fake upstream；`real_model_called=false` |
| 5 | 只提供客户端集成需求文档 | PASS | `M5CAR2_ClientIntegrationContract.md`；未改 Unity/M6-C |
| 5 | 覆盖 7 项客户端要求 | PASS | API 基址、同源、404 恢复、429/503、Mock 降级、中文对话、刷新恢复 |
| 5 | 不把接口测试当 Unity 玩法测试 | PASS | 报告明确区分 |
| 6 | 重跑 278 项单元/接口测试 | PASS | 278/278，13.655 s |
| 6 | 重跑 25 项 E2E | PASS | 25/25 |
| 6 | 新增代码须有测试 | PASS（无新增业务代码） | 仅新增工具脚本，产物即其输出 |
| 6 | 重跑敏感信息扫描 | PASS | 284 候选 / 165 扫描 / 0 命中 |
| 6 | 不以删测试/降断言掩盖失败 | PASS | `same_test_ids=true`，removed 0，added 0 |
| 7 | 7 份报告 + `M5CAR2_Reports.zip` | PASS | 本目录 7 份 md；zip 在根目录 |
| 7 | 区分已实现/已验证/未验证/阻塞/需授权 | PASS | 交付报告 §4、本矩阵 |
| 7 | 完成后停止，不进入 M5-C-B | PASS | 无后续开发动作 |

## 2. 平台预检细分

| 场景 | 方案 | 平台实测 | 状态 |
| --- | --- | --- | --- |
| 持久目录 + 重启预算恢复 | 已写 | 未执行 | PARTIAL |
| 台账/哨兵共同回滚 | 已写 | 未执行 | PARTIAL |
| 独立可信预算记录 | 已写（含不可行结论） | 未执行 | PARTIAL |
| 代理拓扑 + XFF | 已写 | 无法执行（拓扑未知） | BLOCKED |
| API Key 注入 | 已写 | 未执行 | PARTIAL |
| ≤5 次真实请求 | 已写 | 未执行 | NOT TESTED |
| 异常停止 + Mock 回滚 | 已写 | 未演练 | NOT TESTED |

## 3. 需要用户授权才能推进的事项

1. 在 ModelScope 创建/修改创空间（含临时验证空间）并注入密钥。
2. 发起真实模型请求（首轮上限 5 次）并消耗魔粒。
3. 若需在平台侧确认代理头，可能需要在验证空间部署一个**仅回显请求头**的探针服务。
4. 修改 Unity 客户端（属 Codex M6-C 写权限），把集成契约落成代码。
5. 开启 `APP_ENTRY_MODE=live` 的任何线上变更。

## 4. 未验证清单（不得推断为通过）

- 平台持久化是否覆盖 SQLite 台账与 epoch 哨兵。
- 平台重启/迁移后 `ledger.global_used` 是否保持。
- 平台是否透传、覆盖或伪造 `X-Forwarded-For`。
- 平台密钥注入后镜像/日志/环境回显是否泄露。
- 真实模型首轮 5 次请求的 token/魔粒对应关系。
- WebGL 页面刷新后客户端会话恢复（需 M6-C 实现后验证）。
- 中文 IME 在真实 Chrome/WebGL 下的输入与字体覆盖。
