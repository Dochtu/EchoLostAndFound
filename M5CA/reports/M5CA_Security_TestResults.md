# M5-C-A 安全测试结果

执行日期：2026-11-25
环境：Windows 11 + Python 3.12.14（`Server/.venv`）+ Docker Desktop 28.5.1
模型上游：本地 `fake_llm_server.py`（OpenAI 兼容假上游）与 `httpx.MockTransport`
**本文件不包含任何真实模型调用结果；所有"模型回复"均来自本地假上游或内存传输层，`is_synthetic`/`provider.kind` 如实标注。**

命令（在 `Server/` 下）：

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
.\.venv\Scripts\python.exe -m pytest -v -p no:cacheprovider --basetemp=G:\projects\EchoLostAndFound\.m5ca_tmp\pytest6
```

结果：**206 passed, 1 warning in 8.90s**（完整输出：`evidence/tests/pytest-verbose.txt`）。
Docker 端到端：**21/21 passed**（`evidence/e2e/e2e_results.json`）。

---

## 1. 剧情安全（模型不能改变游戏状态）

测试文件：`Server/tests/test_story_safety.py`（11 例，全部通过）
替身：`ScriptedProvider`（`kind=external_model`、`is_synthetic=False`），可注入任意"模型文本/建议"。

| 用例 | 攻击/异常 | 期望 | 实际 |
| --- | --- | --- | --- |
| `test_model_text_cannot_grant_evidence_or_change_progress` | 模型文本声称已给予证据/推进章节 | 响应不含 `evidence_granted`/`acquired_evidence_ids`/`chapter`/`progress`/`ending`；会话状态仍 `open` | 通过 |
| `test_unknown_evidence_id_is_rejected` | 伪造证据编号 `E99` | 404 `NOT_FOUND` | 通过 |
| `test_malformed_evidence_id_is_rejected` | `DROP TABLE` 注入 | 400 `INVALID_REQUEST` | 通过 |
| `test_evidence_outside_npc_knowledge_is_rejected` | 把 E02 交给只知 E01/E03/E04 的林遥 | 409 `PRECONDITION_FAILED` | 通过 |
| `test_turn_evidence_does_not_trigger_disclosure` | 在对话轮附带 E02 试图触发 D01 | 只记录"客户端持有"，不触发披露 | 通过 |
| `test_disclosure_requires_all_evidence` | D02 缺 E04 | 不触发；补齐后才触发；重复提交 `already_presented=true` 不重复触发 | 通过 |
| `test_truth_demand_cannot_unlock_gated_topic` | 玩家要求"把真相全说出来" | `repeat_b01` 仍不可用（需 D01） | 通过 |
| `test_prompt_leak_falls_back` | 模型输出"系统提示：..." | `source=fallback`，`fallback_reason=unsafe_output` | 通过 |
| `test_markup_falls_back` | 模型输出含 `<script>` | `unsafe_output` | 通过 |
| `test_unknown_suggestion_is_dropped` | 模型建议未授权主题 | `suggested_actions == []` | 通过 |
| `test_model_cannot_close_session` | 模型试图结束会话 | 会话仍 `open` | 通过 |
| `test_raw_model_json_with_state_fields_falls_back` | 上游 JSON 夹带 `evidence_granted`/`chapter_progress` | `invalid_output` 降级，状态无变化 | 通过 |

结论：模型输出**没有**任何可写状态的字段；即使绕过 Provider 适配器，`policy` 也会二次校验文本；所有越权路径均被确定性规则拦截，而非依赖 System Prompt。

## 2. 模型输出解析与注入防护

测试文件：`Server/tests/test_llm.py`、`Server/tests/test_llm_transport.py`、`Server/tests/test_security.py`。

| 输入 | 结果 |
| --- | --- |
| 合法 JSON 三字段 | 接受，`source=external_model` |
| 顶层非对象 / 缺 `text` / `npc_id` 不匹配 | `invalid_output` |
| 额外键（`evidence_granted` 等） | `invalid_output`（白名单键） |
| 文本含 `<`/`>`、控制字符、禁用片段 | `unsafe_output` |
| 文本超过 400 字符 | `unsafe_output:text_too_long` |
| 双写 JSON / 双层编码 | 规范化后校验；仍不合法则拒绝 |
| 上游 401/429/500/503 | `model_unavailable:upstream_status_N`，**不回显上游正文** |
| 上游返回 HTML/非 JSON | `response_not_json` |
| JSON 截断 | `invalid_json_line_1` |
| `finish_reason=length` | `invalid_output:response_truncated` |
| 连接失败 | `upstream_transport_error` |
| 超时 | `upstream_timeout` |

每个失败用例都断言：**上游只收到 1 次请求**（无自动重试）、该次尝试在账本中记为 `failed`、会话状态未被修改。

## 3. 密钥与敏感信息

| 检查 | 方法 | 结果 |
| --- | --- | --- |
| Key 不出现在 health/meta | `test_llm_key_never_appears_in_health_or_meta` | 通过 |
| Key 不出现在请求体 | 断言 `test-key...` 不在 body，只在 `Authorization` 头 | 通过 |
| Key 不出现在日志 | 日志过滤器 + E2E 容器日志检索 | 通过 |
| Key 不出现在错误响应 | 上游错误只映射状态码 | 通过 |
| `.env.example` 无真实值 | 人工复核 + 扫描 | 通过 |
| 仓库历史/索引无密钥 | `scan_secrets.py` → `secret-scan.json`：`sensitive_tracked_files: []`，66 文件 0 命中 | 通过 |
| 运行证据中无密钥 | E2E L5 | 通过 |

允许列表仅包含测试替身常量：`sk-live-0123456789abcdef`（假串）、`local-secret-token`（本地鉴权测试）。二者均为非真实凭据，且不出现在部署配置中。

## 4. 请求面防护

| 检查 | 用例 | 结果 |
| --- | --- | --- |
| 超大 `Content-Length` | `test_guards.py` | 413 |
| 分块传输累计超限 | `test_public_safety.py` | 413 |
| 非法 JSON / 缺字段 | `test_guards.py` | 422 |
| 非法 `X-Request-ID` | `test_request_id.py` | 400 |
| 可选本地鉴权 | `test_guards.py` | 缺失 401；`Authorization` 单独使用被拒 |
| 限流响应 | `test_rate_limit_m5ca.py` | 429 + `Retry-After` + `RATE_LIMITED` |
| 静态资源豁免 | `test_rate_limit_m5ca.py` | `/` 不受模型限流 |
| 目录穿越 | `test_static_site.py` | 404，不泄露文件系统 |

## 5. 可信代理与客户端识别

`Server/app/network.py` + `test_rate_limit_m5ca.py`：

| 场景 | 行为 |
| --- | --- |
| 未配置 CIDR | 完全忽略 `X-Forwarded-For` |
| peer 不在可信网段 | 忽略 XFF，使用 peer 地址 |
| peer 在可信网段 | 从 XFF 右向左剥离可信代理，取第一个不可信地址 |
| XFF 含非法 IP | 返回 `"unknown"`，共享同一桶 |
| 配置 `TRUST_FORWARDED_FOR=true` 但无 CIDR | 配置校验拒绝启动 |
| 配置 `0.0.0.0/0` / `::/0` | 配置校验拒绝启动 |

## 6. Docker E2E 安全项

来自 `evidence/e2e/e2e_results.json`：

| 检查 | 观察值 |
| --- | --- |
| L3 401/429/500 | `source=fallback`，`model_unavailable`，无状态变化 |
| L3 非法 JSON | `fallback`，`invalid_output` |
| L3 截断 | `fallback`，`invalid_output`（`response_truncated`） |
| L3 不安全文本（系统提示泄露） | `fallback`，`unsafe_output` |
| L3 夹带状态字段 | `fallback`，`invalid_output` |
| L3 超时 | `fallback`，`timeout`，约 3.01s |
| L3 连接失败 | `fallback`，`timeout`（连接等待耗尽预算内超时） |
| L4 故障后固定台词 | `source=fixed_line`，游戏继续 |
| L5 健康接口 | `contains_key: false` |
| B4 账本删除 | 启动拒绝，日志 `ledger_missing`，上游 `before=6, after=0` |
| B5 账本损坏 | 启动拒绝 |
| B6 目录权限 500 | 启动拒绝，`ledger_read_only` |
| M6 mock 模式 | fake 上游请求数 0 |

## 7. 未覆盖 / 未验证

1. **真实模型**：未发送任何真实请求；上游真实的内容审核、格式漂移、延迟分布未知。
2. **魔搭网关**：403 阻塞仍在，平台代理拓扑（`X-Forwarded-For` 语义）未确认。
3. **多副本**：单进程设计，未测试多实例下额度是否被放大（设计上不支持横向扩容）。
4. **浏览器侧**：未做 XSS/CSRF 浏览器级测试；服务端已设置 `nosniff`、`no-store`，CORS 为显式白名单。
5. **压力测试**：只做了小规模并发（8 请求/4 会话），未做长时间浸泡。

## 8. 结论

- 安全回归全部通过；模型无法通过任何已测路径修改证据、披露、进度、知识权限或结局。
- 密钥未出现在代码、配置、日志、健康接口、错误响应与证据中。
- 失败一律降级且不重试、不绕过预算。
- 剩余风险集中在"平台拓扑"与"真实上游行为"，均为上线前必须补验的阻塞项。
