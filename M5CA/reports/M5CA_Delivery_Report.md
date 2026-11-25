# M5-C-A 交付报告

项目：EchoLostAndFound《回声失物招领处：末班车之后》
阶段：M5-C-A（显式 AI 模式、额度保护、限流、剧情安全的本地开发与验收）
日期：2026-11-25
分支：`m5c-a-dev`，基线 HEAD `4c51712c362e18bfcf9215cea766e61731773c74`
状态：**本地开发与验收完成，等待技术负责人验收；未进入真实模型线上试运行。**

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 源码 | 完成：模式入口、账本、熔断、可信代理、四类限流、Provider 接入、账本管理 CLI |
| 自动化测试 | **206 passed**（新增 83 例 M5-C-A 专项） |
| Docker 端到端 | **21/21 passed**（mock 6 + live 5 + 预算/并发 6 + 生命周期 4） |
| 真实模型请求 | 0（受约束禁止） |
| 线上部署 | 未修改 |
| 平台阻塞 | 2 项：魔搭代理拓扑未确认；平台持久化未验证 |
| 是否可上线 live | **否**，在上述阻塞关闭前禁止 |

---

## 2. 交付内容

### 2.1 代码

- 新增：`Server/app/budget.py`、`breaker.py`、`network.py`、`entry.py`、`ledger_admin.py`、`Server/tools/fake_llm_server.py`。
- 修改：`config.py`、`main.py`、`providers/{base,factory,llm_provider}.py`、`policy.py`、`security.py`。
- 测试：新增 `test_budget.py`、`test_entry_mode.py`、`test_rate_limit_m5ca.py`、`test_story_safety.py`、`test_llm_transport.py`、`test_ledger_admin.py`；修改 `test_llm.py`、`test_concurrency.py`、`test_public_safety.py`。

### 2.2 独立部署候选

`Builds/M5CA/candidate/`（34 文件）：
- `app/`：完整后端源码（不含测试）
- `Dockerfile`、`docker-compose.mock.yml`、`docker-compose.live.yml`、`docker-compose.tight.yml`
- `fake_llm/`：本地假上游
- `e2e/run_e2e.py`：验收驱动
- `MANIFEST.txt`：候选文件 SHA256 清单
- 端口：mock 18080；live 18081/上游 19000；tight 18082/上游 19001
- 项目名隔离：`m5ca`、`m5ca-live`、`m5ca-tight`

### 2.3 报告与证据

见第 6 节与 `MANIFEST.txt`。

---

## 3. 实现要点

### 3.1 显式模式（`APP_ENTRY_MODE`）

- 唯一入口 `uvicorn app.entry:app --workers 1`，导入期校验，失败即退出。
- mock 路径**从不构造** `LlmProvider`，从代码结构上排除外呼；`test_mock_mode_makes_zero_network_calls` 用"禁止性替身"证明零调用。
- live 要求 provider 配置 + API Key + 合法预算参数 + 可用账本，缺一即拒绝，并给出具体原因。
- health 同时给出 `game_ready` 与 `model_ready`，二者独立。

### 3.2 额度账本

- SQLite + 独立 epoch sentinel；`BEGIN IMMEDIATE` 内原子检查并预留；先记账后请求；失败也计数。
- 加载时执行 8 项校验（存在性、完整性、schema、代次、计数一致、高水位、目录可写、SQLite 可提交）。
- 首次初始化与重置只能通过 `python -m app.ledger_admin init|reset --confirm`；服务永不自动补额度。
- 账本丢失/损坏/只读/代次不符/回滚/篡改 → live 拒绝启动。

### 3.3 限流

- 四类业务限流 + 上游并发信号量；静态 WebGL 资源豁免。
- 客户端地址仅在可信代理 CIDR 内解析 XFF，拒绝全网段信任，默认完全忽略 XFF。

### 3.4 剧情安全

- 四层：严格 JSON 白名单 → 文本校验 → Policy 二次校验 → 确定性状态规则。
- 模型输出无状态字段；建议主题必须在当前 NPC 可用集合内；证据/披露只能走 `/evidence` 与批准内容。
- 11 个专项攻击用例覆盖：泄露真相、伪造编号、改状态、泄露提示词、越权披露、标记注入、非结构输出。

### 3.5 上游接入

- OpenAI 兼容 `/chat/completions`，单次请求不重试，超时/状态码/非法 JSON/截断/连接失败全部映射为可区分的降级原因。
- token 用量落账；输入/输出上限可配。

---

## 4. 测试结果

### 4.1 测试规模

| 文件 | 通过数 |
| --- | ---: |
| `test_budget.py` | 16 |
| `test_entry_mode.py` | 22 |
| `test_rate_limit_m5ca.py` | 13 |
| `test_story_safety.py` | 11 |
| `test_llm_transport.py` | 16 |
| `test_ledger_admin.py` | 5 |
| 既有回归（14 文件） | 123 |
| **合计** | **206** |

### 4.2 Docker E2E（21/21）

| 阶段 | 检查 |
| --- | --- |
| Mock | M1 健康契约、M2 E01–E05+D01–D03+REC、M3 两条保管路线前置、M4 刷新恢复、M5 会话隔离、M6 零外呼 |
| Live | L1 就绪分离、L2 中文非合成回复、L3 九类故障降级、L4 固定台词兜底、L5 无密钥泄露 |
| Tight | B1 6/2 额度、B2 并发不超发（6/6/2）、B3 耗尽后继续、B4 账本删除拒绝、B5 损坏拒绝、B6 权限异常拒绝 |
| Lifecycle | R1 重启保额、R2 删除重建保额、R3 旧会话干净 404、R4 上游可达 |

关键数值：
- 并发：8 请求 / 4 会话 → 上游 6 次、账本 6 次、拒绝 2 次、最大上游并发 2。
- 重启：账本已用 11 → 11；删除重建 11 → 11。
- L3 超时 3.01s 内降级；所有失败用例状态零变化。

---

## 5. 开发过程中发现并修复的问题

| 问题 | 根因 | 修复 |
| --- | --- | --- |
| 账本初始化 `cannot commit - no transaction is active` | `isolation_level=None` 下 schema 语句未显式开启事务 | 建表前 `BEGIN` |
| 并发下所有请求 `upstream_busy` | `asyncio.wait_for(sem.acquire(), timeout=0)` 会取消已就绪的获取 | 先判 `locked()` 再 `acquire()`；后续改为正超时等待 |
| E2E 会话跨线程 SQLite 报错 | TestClient portal 线程与创建线程不同 | `check_same_thread=False` + 锁串行化 |
| 熔断测试时钟不生效 | `CircuitBreaker` 未接收注入时钟 | 传入 `clock=self._clock` |
| 账本删除后仍显示可用 | `usage().persistent` 恒为 True | 改为 `_unavailable is None` |
| `chmod 500` 目录仍能启动 | ROLLBACK 写入不创建 journal，SQLite 探针无效 | 增加文件系统写探针 + 真实 COMMIT |
| tight 启动即失败 | 先 `compose up` 后 `ledger_admin init` | 调整为先初始化再启动 |
| `--append` 重跑旧阶段 | 合并了历史 stages | 按请求阶段运行，按 check id 去重 |

---

## 6. 交付物清单

| 文件 | 说明 |
| --- | --- |
| `M5CA/reports/M5CA_Delivery_Report.md` | 本报告 |
| `M5CA/reports/M5CA_CompletionMatrix.md` | 逐条需求完成矩阵 |
| `M5CA/reports/M5CA_Architecture.md` | 架构与数据流 |
| `M5CA/reports/M5CA_FileChanges.md` | 文件级变更 |
| `M5CA/reports/M5CA_Security_TestResults.md` | 安全测试结果 |
| `M5CA/reports/M5CA_Budget_TestResults.md` | 额度/持久化测试结果 |
| `M5CA/reports/M5CA_ModelScope_ConfigGuide.md` | 魔搭配置与运维 |
| `M5CA/reports/M5CA_HandoffToCodex.md` | 客户端移交说明 |
| `M5CA/evidence/` | 测试输出、E2E JSON/日志、启动拒绝、Git 与密钥扫描 |
| `MANIFEST.txt` | 报告包内文件 SHA256 |
| `M5CA_Reports.zip` | 打包产物 |
| `M5CA_Package_SHA256.txt` | 压缩包整体 SHA256（外部记录） |

---

## 7. 未完成 / 未验证（诚实清单）

1. **真实模型**：0 次真实请求；真实上游的格式、审核、延迟、token 计费口径未验证。
2. **魔搭平台**：未部署；网关 403 仍阻塞；代理拓扑未知；账本持久化未证明。
3. **Unity 结算界面**：本轮未重建 WebGL；E2E 验证的是服务端前置条件与第一章 API 流程，不是最终画面结算。
4. **浏览器级安全**：未做 XSS/CSRF 浏览器测试；服务端已加 `nosniff`/`no-store`/CORS 白名单。
5. **压力/浸泡**：仅小规模并发；未做长时间与磁盘写满测试。
6. **多副本**：不支持，也未测试。

## 8. 上线阻塞项（必须先关闭）

| # | 阻塞 | 关闭条件 |
| --- | --- | --- |
| 1 | 魔搭代理拓扑未确认 | 取得可信代理 CIDR，开启 `TRUST_FORWARDED_FOR` 并复测客户端限流 |
| 2 | 平台账本持久化未验证 | 在魔搭实测重启/重建/迁移后账本与哨兵不丢、代次不变 |
| 3 | 真实上游未试运行 | 技术负责人另行批准后，用小额度、可回滚方式试运行并核对 token 计费 |
| 4 | 正式额度未确认 | 业务方确认 30/8 或给出正式值 |

## 9. 复现方式

```powershell
# 1. 单元/集成
cd G:\projects\EchoLostAndFound\Server
.\.venv\Scripts\python.exe -m pytest -v -p no:cacheprovider --basetemp=G:\projects\EchoLostAndFound\.m5ca_tmp\pytest

# 2. 组装候选
powershell -ExecutionPolicy Bypass -File G:\projects\EchoLostAndFound\M5CA\deploy\build_candidate.ps1

# 3. 完整 E2E（mock + live + tight + lifecycle）
cd G:\projects\EchoLostAndFound\Builds\M5CA\candidate
G:\projects\EchoLostAndFound\Server\.venv\Scripts\python.exe e2e\run_e2e.py --candidate-dir .
```

---

## 10. 请求验收

请技术负责人验收以下内容：

1. 206 个自动化测试与 21 项 Docker E2E 的结果真实性（可复现命令见第 9 节）。
2. 模式切换与 fail-closed 行为是否符合预期。
3. 额度账本设计（先记账、原子预留、代次哨兵、显式初始化）是否满足成本控制要求。
4. 剧情安全边界是否足够（模型零状态写入）。
5. 两项上线阻塞的处置方式。

**本阶段到此停止。** 未获授权前不部署魔搭、不配置真实 Key、不发起真实模型请求、不公开创空间。
