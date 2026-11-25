# M5-C-A 文件变更清单

基线：`4c51712c362e18bfcf9215cea766e61731773c74`（分支 `m5c-a-dev`）
说明：
- 本仓库基线从未把 `Server/` 纳入索引（仅 `Server/requirements.txt` 为已跟踪修改），因此 `Server` 下源码在 Git 中显示为 untracked；下表按"本轮新增/本轮修改"标注，而不是按 Git 状态标注。
- 未执行 `git add/commit/push`。完整提交候选清单见 `evidence/git/status-m5ca.txt`。
- 未修改任何 Unity 资源、Scene、Prefab 或 `Assets/_Project/Art`（Codex 工作区）。

---

## 1. 新增源码（Server）

| 文件 | 行数 | 职责 |
| --- | ---: | --- |
| `Server/app/budget.py` | 479 | SQLite 额度账本：初始化、加载校验、原子预留、完成回写、耗尽/损坏/只读 fail-closed、epoch sentinel |
| `Server/app/breaker.py` | 66 | 上游连续错误熔断（closed/open/half-open，单探测，可注入时钟） |
| `Server/app/network.py` | 39 | 可信代理拓扑下的客户端地址解析，忽略不可信 XFF |
| `Server/app/entry.py` | 12 | 统一启动入口 `app.entry:app`，导入期完成模式/账本校验 |
| `Server/app/ledger_admin.py` | 165 | 账本管理 CLI：`init` / `reset` / `verify`，需显式 `--confirm` |
| `Server/tools/fake_llm_server.py` | 173 | 本地 OpenAI 兼容假上游：正常/401/429/500/badjson/truncate/unsafe/leak/timeout/slow 与统计接口 |

## 2. 修改源码（Server）

| 文件 | 行数 | 变更 |
| --- | ---: | --- |
| `Server/app/config.py` | 271 | 新增 `entry_mode`、可信代理 CIDR、账本/token/并发/熔断/四类限流字段；`validate()` 模式与参数强校验；`from_env()` 读取全部新变量 |
| `Server/app/main.py` | 520 | live 启动时加载账本（失败即拒绝）；四类限流器与可信客户端地址；health 增加 `entry_mode/game_ready/model_ready/model_mode/is_synthetic/ledger/breaker`；lifespan 关闭账本 |
| `Server/app/providers/llm_provider.py` | 350 | 接入熔断、并发信号量、账本预留/完成、token 用量、截断检测、单次请求不重试；`fallback_reason` 区分预算/账本原因 |
| `Server/app/providers/base.py` | 78 | `ProviderRequest.session_id`；`ProviderResult.fallback_reason` 保留本地原因 |
| `Server/app/providers/factory.py` | 29 | 按 `entry_mode` 构建 Mock/Llm；llm 无账本时返回 DisabledProvider，绝不静默降级 |
| `Server/app/policy.py` | 382 | 模型文本二次校验；请求携带 `session_id` 以隔离会话额度 |
| `Server/app/security.py` | 106 | 抽出 `validate_bridge_text()`，解析层与 Policy 层共用 |

## 3. 修改测试（Server/tests）

| 文件 | 行数 | 变更 |
| --- | ---: | --- |
| `Server/tests/test_llm.py` | 138 | 改用逐用例临时账本；覆盖正常/超时/401/429/500/非法 JSON/截断/未配置 |
| `Server/tests/test_concurrency.py` | 179 | 懒加载用例补 live 配置与账本 |
| `Server/tests/test_public_safety.py` | 149 | 密钥不出现在 health/meta 的用例补 live 配置与账本 |

## 4. 新增测试（Server/tests）

| 文件 | 行数 | 用例数 | 覆盖 |
| --- | ---: | ---: | --- |
| `Server/tests/test_budget.py` | 251 | 16 | 预留/失败计数/token/全局/会话/并发/崩溃/缺失/损坏/代次/回滚/篡改/只读/重置/高水位 |
| `Server/tests/test_entry_mode.py` | 210 | 22 | 默认 mock、非法模式、live 参数拒绝、账本三类拒绝、health 字段、mock 零外呼 |
| `Server/tests/test_rate_limit_m5ca.py` | 153 | 13 | 四类限流、静态资源豁免、可信代理解析、配置拒绝、并发窗口 |
| `Server/tests/test_story_safety.py` | 190 | 11 | 改证据/改进度/伪造编号/越权披露/提示词泄露/标记注入/非结构输出 |
| `Server/tests/test_llm_transport.py` | 285 | 16 | 上游状态码、超时、连接失败、非法/截断 JSON、token 落账、payload 上限、额度耗尽、账本删除、熔断 |
| `Server/tests/test_ledger_admin.py` | 118 | 5 | init/reset/verify 的确认、幂等、损坏与代次缺失退出码 |

## 5. 部署与文档（Server）

| 文件 | 变更 |
| --- | --- |
| `Server/Dockerfile` | 改为非 root、`app.entry:app`、`--workers 1`、`/app/.local` 权限、mock 安全默认 |
| `Server/.env.example` | 重写为完整 M5-C-A 变量表，仅占位值，无真实密钥 |
| `Server/DEPLOYMENT.md` | 追加 M5-C-A 部署、账本初始化、模式切换、阻塞项 |
| `Server/API_CONTRACT.md` | 追加 health 字段、fallback 原因、限流桶与兼容性说明 |
| `Server/README.md` | 追加 M5-C-A 摘要与测试数字 |
| `Server/requirements.txt` | 已跟踪修改（基线阶段引入，本轮未新增依赖） |
| `.gitignore` | 追加 14 条安全规则（浏览器配置、pkg、sqlite、zip、临时目录、evidence） |

## 6. 独立部署候选

| 路径 | 说明 |
| --- | --- |
| `M5CA/deploy/Dockerfile` | 候选镜像：python 3.12-slim，uid 10001，健康检查，单 worker |
| `M5CA/deploy/docker-compose.mock.yml` | 项目 `m5ca`，18080，纯 mock |
| `M5CA/deploy/docker-compose.live.yml` | 项目 `m5ca-live`，18081 + fake 19000，30/8 额度 |
| `M5CA/deploy/docker-compose.tight.yml` | 项目 `m5ca-tight`，18082 + fake 19001，6/2 额度、并发 2、短超时 |
| `M5CA/deploy/build_candidate.ps1` | 组装 `Builds/M5CA/candidate`（源码 + 部署 + e2e），生成候选 MANIFEST |
| `M5CA/e2e/run_e2e.py` | 端到端验收驱动：mock/live/tight/lifecycle 四个阶段，21 项检查 |
| `M5CA/scan_secrets.py` | 敏感信息扫描，输出 `evidence/git/secret-scan.json` |
| `Builds/M5CA/candidate/` | 34 文件独立候选（未提交、未部署线上） |

## 7. 证据与报告

| 路径 | 内容 |
| --- | --- |
| `M5CA/evidence/tests/pytest-verbose.txt` | 206 passed 完整输出 |
| `M5CA/evidence/e2e/e2e_results.json` / `e2e_run.log` | 21/21 检查与运行日志 |
| `M5CA/evidence/entry_mode/*.txt` | live 缺配置/缺账本拒绝、mock 默认启动 |
| `M5CA/evidence/git/*` | 全量状态、本轮状态、diffstat、历史敏感文件检查、密钥扫描 |
| `M5CA/reports/*.md` | 本目录下的八份交付报告 |

## 8. 明确未修改

- `EchoLostAndFound_WebGL/`、`Assets/`、`ProjectSettings/`、`Packages/`：无改动。
- `Builds/M4D-Dev/M5A/candidate`：未覆盖。
- `M5B/` 下既有报告与证据：未改动（仅 `.gitignore` 引用）。
- 线上部署、创空间：未触碰。
- 无新增 Python 依赖；`requirements.txt` 无新增包。

## 9. 统计

- 新增生产源码：5 个文件 + 1 个工具，合计约 934 行。
- 修改生产源码：8 个文件。
- 测试：6 个新文件 + 3 个修改文件；全量 206 passed。
- 部署/验收脚本：7 个文件；Docker E2E 21/21 passed。
