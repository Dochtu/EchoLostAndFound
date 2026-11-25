# M5-C-A-R1 独立服务端部署候选说明

本目录是 `DeploymentCandidate.zip` 的补充说明，压缩包本身已包含 `app/`、`requirements.txt`、
两个 Dockerfile、`docker-compose.yml`、`.env.example` 与部署文档。压缩包在解压后不依赖
`Server/` 之外的任何文件。

## 1. 启动方式（两种，均只监听本机进程内状态）

```powershell
# 方式 A：直接运行（不依赖 Docker）
python -m pip install -r requirements.txt
$env:APP_ENTRY_MODE="mock"; $env:MODEL_PROVIDER="mock"
python -m app.server_entry          # 默认 0.0.0.0:7860，PORT/UVICORN_PORT 可覆盖

# 方式 B：容器
docker build -t echolostfound-npc-ai:r1 .
docker run --rm -p 7860:7860 -e APP_ENTRY_MODE=mock -e MODEL_PROVIDER=mock echolostfound-npc-ai:r1
```

`app.server_entry` 固定 `proxy_headers=False`、`forwarded_allow_ips=""`、`workers=1`：
客户端地址只能由应用层 `app/network.py:resolve_client_ip` 解释，Uvicorn 不再二次改写。
`workers=1` 是硬约束——会话、限流桶、熔断器都是**进程内**状态，多 worker 会各自为政。

## 2. 真实模型配置（本轮未启用）

```powershell
$env:APP_ENTRY_MODE="live"
$env:MODEL_PROVIDER="llm"
$env:LLM_BASE_URL="https://api-inference.modelscope.cn/v1"   # 不带尾斜杠
$env:LLM_MODEL="<owner/name>"                                # 不带 :Provider 后缀
$env:LLM_API_KEY="<服务端密钥>"                               # 只能来自环境变量/密钥注入
$env:LLM_REQUEST_LIMIT="30"; $env:LLM_REQUEST_LIMIT_PER_SESSION="8"
$env:LLM_TOKEN_LIMIT="60000"; $env:LLM_CONTEXT_MAX_TOKENS="1536"
$env:LLM_USAGE_PATH="/mnt/workspace/.local/llm-usage.sqlite3"
$env:LLM_LEDGER_EPOCH_PATH="/mnt/workspace/.local/epoch/ledger-epoch.json"
```

启动前必须先用 `python -m app.ledger_admin init --confirm ...` 生成台账与哨兵；缺任意一者
`APP_ENTRY_MODE=live` 会以非零码退出（`RuntimeError: APP_ENTRY_MODE=live refused: ...`），
不会静默降级、不会自动重建、不会自动清零预算。

## 3. 本候选已包含的行为保证

| 保证 | 实现位置 |
| --- | --- |
| 真实模型连接状态不因配置存在而宣称已连接 | `app/model_state.py`；health 的 `model.model_status` |
| 上下文/系统提示/证据/输出分类预算 | `app/knowledge.py:build_prompt` + `app/providers/llm_provider.py:_prompt_plan` |
| Token 预算保守预留与 unknown usage 记账 | `app/budget.py:reserve/finish` |
| 台账高水位 + 代次固定，防单文件回滚 | `app/budget.py:load`（`epoch_pin` 已在 live 启动路径生效） |
| 单一客户端地址责任层 | `app/server_entry.py` + `app/network.py` |
| 限流器内存有界 | `app/rate_limit.py`（`max_keys` + 有序淘汰） |

## 4. 平台限制（上线阻塞项，未解除）

1. ModelScope 创空间磁盘默认不持久，只有 `/mnt/workspace` 持久；台账与哨兵必须放在
   `/mnt/workspace`，且**创空间转移/改名后仍会丢失**。
2. 平台反向代理是否透传 `X-Forwarded-For` 无官方文档；`TRUSTED_PROXY_CIDRS` 必须保持为空，
   客户端地址按代理地址处理。
3. `Authorization` 头被平台占用，应用层令牌必须用自定义头（默认 `X-Dialogue-Token`）。
4. 免费 API-Inference 明确不提供 SLA，官方要求勿用于有 SLA 要求的线上任务。

详细取证见 `M5CAR1_ModelScope_Preflight.md`。
