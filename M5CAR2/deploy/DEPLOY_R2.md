# M5-C-A-R2 部署候选说明

本目录是**服务器部署候选**（源码 + 容器文件 + 文档），不是已部署实例，也不包含任何真实密钥。
本轮未调用真实模型、未消耗魔粒、未修改线上创空间。

## 1. 包内布局

```text
DeploymentCandidate.zip
├── app/                    # FastAPI 应用（含 content/ 与 providers/）
├── requirements.txt
├── Dockerfile
├── Dockerfile.modelscope
├── docker-compose.yml
├── .dockerignore
├── .env.example            # 只有占位值
├── DEPLOYMENT.md
├── README.md
├── API_CONTRACT.md
└── DEPLOY_R2.md            # 本文件
```

`ServerSource.zip` 是同一份源码的完整快照（含 `tests/`、`tools/`、`HANDOFF` 文档），
供恢复与审计；`DeploymentCandidate.zip` 只含运行所需文件。

## 2. 本机 Mock 启动（无模型、无魔粒）

```powershell
cd G:\projects\EchoLostAndFound\Server
$env:APP_ENTRY_MODE = "mock"
$env:MODEL_PROVIDER = "mock"
$env:WEB_ROOT = "G:\projects\EchoLostAndFound\M5CAR1\local_candidate\webgl"
.\.venv\Scripts\python.exe -m app.server_entry
# http://127.0.0.1:7860/  (容器约定端口) ; 本机联调也可用 uvicorn :8787
```

`WEB_ROOT` 让 WebGL 静态站与 `/api/v1` 同源；不设置时不挂载静态站。

## 3. 容器

```powershell
docker build -t echolostfound-npc-ai:r2 .
docker run --rm -p 7860:7860 echolostfound-npc-ai:r2
```

ModelScope Docker 创空间固定暴露 7860；`app.server_entry` 默认即为 7860，
`--no-proxy-headers` 语义见 `DEPLOYMENT.md`。

## 4. 真实模型（本轮未执行）

只有同时满足下列条件才允许切换 `APP_ENTRY_MODE=live`：

1. 用户明确授权，并已核对魔粒余额；
2. 平台持久化与代理拓扑两项前置已有结论（见 `M5CAR2_ModelScope_Preflight.md`）；
3. 密钥只通过平台"环境变量/密钥"注入 `LLM_API_KEY`，绝不写入本包任何文件；
4. 首轮不超过 5 次真实请求，逐次记录 `health.ledger` 与余额差；
5. 任一异常立即停服、改回 `APP_ENTRY_MODE=mock`、核对台账后上报。

## 5. 回滚

- 立即停止/下线创空间，避免继续消耗；
- 环境变量改回 `APP_ENTRY_MODE=mock`（`MODEL_PROVIDER=mock`）并重启；
- 代码回退到已验收基线 `4c51712c362e18bfcf9215cea766e61731773c74`；
- 核对 `GET /api/v1/health` 的 `ledger.tokens_used`、`global_used`、`epoch_fingerprint`；
- **不要**执行 `ledger_admin reset`；保留现场并上报。

## 6. 本轮核对结果

- 包内不含 `.env`、SQLite 台账、浏览器 profile、`.venv`、`__pycache__`；
- 与 `ServerSource.zip` 中的 `app/` 文件逐字节一致（见 `evidence/packages.json`）；
- 未部署、未对线上创空间做任何修改。
