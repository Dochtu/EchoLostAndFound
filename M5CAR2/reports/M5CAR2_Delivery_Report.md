# M5-C-A-R2 交付报告（工程归档与上线预检）

- 轮次：M5-C-A-R2
- 日期：2026-11-25（Asia/Shanghai）
- 基线：M5-C-A-R1 `CONDITIONAL PASS`，服务端安全补强成果接受，不重新设计 Provider / Token 预算 / SQLite 台账 / NPC 知识权限 / 限流架构
- 本轮性质：工程归档、交付补全、平台上线预检方案；**未新增或修改任何服务端业务代码**
- 真实模型调用：**0 次**；魔粒消耗：**0**；线上创空间：**未改动**

## 1. 本轮做了什么

| 工作 | 结果 | 证据 |
| --- | --- | --- |
| 回归测试 | 278/278 通过，测试 ID 与 R1 完全一致 | `evidence/tests/junit_r2.xml`、`tests_summary.json` |
| 进程级 E2E | 25/25 检查通过 | `evidence/e2e/e2e_r2_results.json` |
| 敏感信息扫描 | 284 个候选，扫描 165 个文本文件，命中 0 | `evidence/security/secret_scan.json` |
| 源码快照 | `M5CAR2/packages/ServerSource.zip`（74 文件） | `evidence/git/source_sha256.txt` |
| 部署候选 | `M5CAR2/packages/DeploymentCandidate.zip`（40 文件） | `evidence/packages.json` |
| WebGL 候选核对 | 目录/压缩包/源码构建三方一致 | `evidence/browser/build_manifest.sha256` |
| Git 本地归档 | 按精确路径提交（见 `evidence/git/post-commit.txt`） | `evidence/git/commit_file_list.txt` |
| 平台预检方案 | 7 个场景的验证方案与判定门槛 | `M5CAR2_ModelScope_Preflight.md` |
| 客户端集成契约 | 需求文档，未触碰 Unity/M6-C 工程 | `M5CAR2_ClientIntegrationContract.md` |

本轮**没有**新增功能、没有改接口、没有改测试断言；`Server/` 的文件修改时间仍停留在 R1 的 2026-11-25 12:33 之前（`requirements.txt` 的版本钉住属于 R1 成果）。

## 2. 交付物与哈希

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `M5CAR2/packages/ServerSource.zip` | 163,583 | `9ae2c2b41c2c062ace0c3ac7d0fea10114ef08015e71ecec4c71f47e2d05d9c5` |
| `M5CAR2/packages/DeploymentCandidate.zip` | 91,956 | `511cea99af444df89a2c3d7f04650a095f28368c301e5dbcddcf80b0f17a3db3` |
| `M5CAR1_LocalWebGLCandidate_20261125-1400.zip` | 20,861,535 | `0e408df23251b1e4bdc56bdb6bfd44d83e8a41c3693f86dbfa0e87b8d2ae9bb2` |
| `M5CAR2_Reports.zip` | 见 `evidence/packages.json` 的 `reports` 字段 | 同左 |

根目录 `M5CAR2_Package_SHA256.txt` 汇总上述四项哈希；`evidence/git/source_sha256.txt` 是 `ServerSource.zip` 内 74 个文件的逐文件哈希。

**未覆盖 R1 根目录交付包**：`ServerSource.zip`、`DeploymentCandidate.zip`、`M5CAR1_Reports.zip` 保持原样，避免破坏 `M5CAR1/evidence/packages.json` 记录的哈希。R2 包放在 `M5CAR2/packages/`，文件名与要求一致。

## 3. 如何复现

```powershell
cd G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest -q --junitxml=..\M5CAR2\evidence\tests\junit_r2.xml
cd ..
Server\.venv\Scripts\python.exe M5CAR2\e2e\run_e2e_r2.py
Server\.venv\Scripts\python.exe M5CAR2\tools\summarize_tests.py
Server\.venv\Scripts\python.exe M5CAR2\tools\scan_secrets_r2.py
Server\.venv\Scripts\python.exe M5CAR2\tools\build_packages_r2.py
```

包构建脚本会拒绝覆盖已存在的产物；如需重建，先移走 `M5CAR2/packages/*.zip` 与根目录 `M5CAR2_Reports.zip`。

## 4. 已实现 / 已验证 / 未验证 / 阻塞 / 需授权

- **已实现**：R2 证据链（测试、E2E、扫描、快照、部署候选、Git 清单、客户端契约、平台预检方案）。
- **已验证**：278 项单元/接口测试、25 项 E2E、扫描 0 命中、部署候选 `app/` 与源码逐字节一致、WebGL 候选压缩包与目录一致且可追溯到 `Builds/M4C-Closeout-Player`。
- **未验证**：ModelScope 平台上的持久化、代理拓扑、密钥注入、真实模型首轮 5 次请求——本轮按指示**未上平台实测**；Unity/M6-C 客户端集成效果；真实浏览器中文对话与刷新恢复。
- **阻塞**：平台侧持久化与代理拓扑没有结论前，真实模型不应开启；`TRUSTED_PROXY_CIDRS` 为空，平台注入的 `X-Forwarded-For` 不可信。
- **需用户授权**：在平台部署 / 修改线上创空间、真实模型请求与魔粒消耗、修改 Unity 工程（属 Codex M6-C 范围）。

## 5. 已知问题与风险

1. `M5CAR1/local_candidate/webgl` 是 **M4C** 构建，不是 M6-C 候选；只能用于“服务端 + 静态站同源”联调，不能作为最终客户端。
2. WebGL 候选的 `index.html` 没有任何 API 基址注入点，运行时只能靠 `?api=` 或同源推导；M6-C 需要在客户端侧补配置入口。
3. 现有 `StationDialogueBridge` 在 404/410 后直接把会话置空并停用在线对话，不自动重建会话；与 M6-C 的“刷新恢复”要求存在差距，已写入集成契约。
4. 服务端会话在内存中，进程重启后旧 `conversation_id` 必然 404；E2E 的 R2 用例已证明该行为。
5. 平台只保证 `/mnt/workspace` 持久；若创空间迁移/重命名会丢持久盘，台账与哨兵会一起丢失，存在预算回滚风险（见预检文档）。

## 6. 结论

R2 的工程归档与交付补全已完成，测试与扫描结果与 R1 一致且可复现；平台真实上线仍被“持久化 + 代理拓扑”两项前置阻塞，需用户授权后才能进入真实模型验证。完成本轮后停止，不进入 M5-C-B。
