# 部署说明（NPC AI 服务 M4-B）

本文覆盖本机、通用 Docker、反向代理 TLS 与 ModelScope 创空间四条路径。所有结论都标注了来源；外部平台政策可能变化，上线前以控制台与官方文档为准。

## 1. 部署形态与前提

服务是**无状态** FastAPI 进程：

- 内容随镜像发布（`app/content/*.json`，版本 `story-v1.0-phase2`）；
- 会话存在进程内存，重启即失效（符合 DataSchema “会话不持久化”约束）；
- 不需要数据库、不需要 GPU；真实模型通过 HTTPS 调用外部 API；
- 单进程即可运行；多副本部署时，会话粘滞不必要（会话丢失会安全地落到 404/410），但限流为**进程内**计数，多副本时每副本独立计数。

环境变量（完整清单见 `.env.example`）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `MODEL_PROVIDER` | `mock` | `mock` / `llm` / `disabled` |
| `LLM_BASE_URL` | 空 | OpenAI 兼容根地址，如 `https://api.example.com/v1` |
| `LLM_MODEL` | 空 | 模型名 |
| `LLM_API_KEY` | 空 | 仅服务端；不得提交到 Git、镜像层、命令行 |
| `LLM_PROVIDER_ID` | `external-llm` | 响应中的 provider id |
| `AI_TIMEOUT_MS` | `12000` | 上游模型超时 |
| `CORS_ALLOWED_ORIGINS` | 空 | 逗号分隔完整源，禁止 `*` |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_BURST` | `60` / `20` | 进程内滑动窗口 |
| `REQUEST_MAX_BYTES` | `32768` | 请求体上限 |
| `PLAYER_INPUT_MAX_CHARS` | `1000` | 玩家输入上限 |
| `SESSION_TTL_SECONDS` | `1800` | 会话有效期 |
| `MAX_SESSIONS` | `512` | 实例内会话数上限（1..10000）；超出时先清已结束会话，再淘汰最旧活跃会话 |
| `LOCAL_AUTH_TOKEN` / `LOCAL_AUTH_HEADER` | 空 / `X-Dialogue-Token` | 可选私网令牌 |
| `TRUST_FORWARDED_FOR` | `false` | 仅在可信代理后开启 |

## 2. 本机开发

```powershell
Set-Location G:\projects\EchoLostAndFound\Server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
$env:MODEL_PROVIDER = "mock"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:8080"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

验证：`curl.exe http://127.0.0.1:8787/api/v1/health`。

## 3. 通用 Docker

```bash
docker build -t echolostfound-npc-ai:local .
docker run --rm -p 7860:7860 \
  -e MODEL_PROVIDER=mock \
  -e CORS_ALLOWED_ORIGINS=http://localhost:8080 \
  echolostfound-npc-ai:local
```

或 `docker compose up --build`（`docker-compose.yml`）。

注意：

- 镜像以非 root 用户运行，仅暴露 7860；
- 健康检查访问 `/api/v1/health`；
- **镜像构建未在本机验证**（无 Docker 引擎），首次部署请先 `docker build` 并查看日志；
- 真实密钥通过编排平台的 secret 注入，不要写进 `Dockerfile`、`docker-compose.yml` 或镜像层；`docker run -e` 会把值暴露在进程环境与 `docker inspect` 中，生产环境请用编排 secret。

## 4. 反向代理与 TLS

公网必须 HTTPS，避免 WebGL 页面（HTTPS）调用混合内容。Nginx 示例：

```nginx
server {
    listen 443 ssl http2;
    server_name npc.example.com;
    ssl_certificate     /etc/letsencrypt/live/npc.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/npc.example.com/privkey.pem;

    location /api/ {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 20s;
        client_max_body_size 64k;
    }
}
```

- 在代理后设置 `TRUST_FORWARDED_FOR=true` 才能按真实客户端限流，且代理必须覆盖/清理该头。
- `CORS_ALLOWED_ORIGINS` 写 WebGL 页面源（如 `https://game.example.com`），不是服务自身域名。
- 建议在代理层再加一层全局速率限制（服务内限流只保护单进程）。

## 5. ModelScope 创空间（评估）

### 5.1 已核实的平台约束（官方文档）

来源：<https://www.modelscope.cn/docs/studios/docker>（Docker 创空间文档）与 <https://www.modelscope.cn/docs/studios/intro>（创空间介绍）。

- Docker 类型支持自定义后端（FastAPI 等），适合本服务。来源：官方 Docker Studio 文档。
- **必须监听 `0.0.0.0:7860`**，端口不可修改；`8080` 被平台占用。来源：官方 Docker Studio 文档。
- 平台占用 `Authorization`、`X-modelscope-*`、`X-studio-*` 请求头，不能用自己的 `Authorization` 鉴权。本服务默认 `X-Dialogue-Token` 正是为此；若设置 `LOCAL_AUTH_TOKEN` 且头名改成 `Authorization`，在创空间会与平台冲突。
- 运行期环境变量在创空间“设置”页注入，**不支持构建期变量**；密钥通过平台环境变量配置，不写入仓库。
- 只有 `/mnt/workspace` 跨重启持久；本服务无状态，不使用持久目录即可。
- 使用 Docker 创空间需要绑定阿里云账号并完成实名认证。来源：官方 Docker Studio 文档。
- 部署方式为推送仓库后在设置页“上线”；官方示例基础镜像使用 ModelScope Registry（`modelscope-registry.cn-beijing.cr.aliyuncs.com/...`）。本交付提供 `Dockerfile.modelscope`。

### 5.2 免费资源与成本（需以控制台为准）

社区资料（非官方承诺，可能变化）：

- 免费 CPU 实例通常为 8 核 / 32 GB，长期可用；免费 GPU（24 GB 显存）约 36 小时/月，CPU 基础环境长期免费（来源：<https://juejin.cn/post/7701250821648941066>）。
- 创空间资源与配额说明亦见社区问答：<https://developer.aliyun.com/ask/683474>。

本服务是轻量 CPU 服务：固定台词与 Mock 不调用模型；接真实模型时，**算力成本发生在外部模型 API**，创空间只承担 HTTP 转发，CPU 免费额度足够压测与试玩。需要弹性/独立域名/稳定 SLA 时，建议迁移到普通云主机或容器服务，而不是依赖免费创空间。

### 5.3 上线步骤

1. 在创空间选择 **Docker** 类型，仓库根目录使用 `Dockerfile.modelscope`（或把其内容作为 `Dockerfile`）。
2. 设置环境变量：`MODEL_PROVIDER`、`CORS_ALLOWED_ORIGINS`（WebGL 页面源）、按需 `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`；不要设置 `LOCAL_AUTH_HEADER=Authorization`。
3. 推送并上线；确认容器日志出现 `npc-ai ready`。
4. 打开创空间“服务地址”，访问 `https://<studio-host>/api/v1/health` 验证。
5. 用浏览器 `Origin` 验证 CORS：`curl -i -H "Origin: https://game.example.com" https://<studio-host>/api/v1/meta` 应返回对应 `Access-Control-Allow-Origin`。
6. 将 Unity 客户端的 `baseUrl` 指到该 HTTPS 地址（不要带尾部斜杠）。

> 创空间具体公网域名由平台在“服务地址”中分配，本文不臆造固定域名；上线时必须在该页面确认实际地址。

### 5.4 创空间限制与风险

- 免费实例可能休眠/重启；会话在内存中，重启后客户端需重建会话（410 → 新建）。这是可接受行为，但要在 UI 处理。
- 平台可能限制并发、带宽或请求体大小；本服务自身限制 32 KiB/请求，平台层限制以其文档为准。
- `Authorization` 被占用意味着不能透传用户令牌；若将来需要用户级鉴权，应在平台外部署或使用自定义头 + 服务端校验。
- 平台日志可能记录请求元数据；不要在 URL/请求体中放置密钥或敏感个人信息。

## 6. 真实模型接入

```bash
MODEL_PROVIDER=llm
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL=your-model
LLM_API_KEY=...        # 仅环境变量/secret
```

- 适配层按 OpenAI 兼容 `POST {LLM_BASE_URL}/chat/completions` 发送，`max_tokens=220`、`temperature=0.7`，并校验 JSON 输出。
- 失败一律转为 `fallback`：`timeout`、`model_unavailable`、`invalid_output`、`unsafe_output`。
- 上游 5xx 只记录状态码，不记录响应正文，避免泄漏。
- 上线前用真实 Key 做一次端到端冒烟；本次交付**未执行**真实模型调用（无 Key），因此不得把 Mock 结果当作真实模型验证。

## 7. 运维检查

- 日志：`npc-ai ready instance=... provider=... content_version=...`；未预期异常记录类型与堆栈，但不返回给客户端。
- 健康：`GET /api/v1/health` 的 `ready` 与 `content_version`；`model_available` 只表示真实模型配置已就绪，不代表可用。
- 监控建议：5xx 比例、429 比例、P95 延迟、fallback_rate（按 `fallback_reason` 分桶）、provider 延迟。
- 内容更新：替换 `app/content` 并重新部署；客户端必须校验 `content_version`，不一致时阻止对话。
- 密钥轮换：更新环境变量并重启；不在日志/镜像中留下旧值。

## 8. 故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| WebGL 报 CORS | `CORS_ALLOWED_ORIGINS` 不含页面源，或用了 `*` | 精确配置源并重启 |
| 422 unknown field | 客户端字段名与契约不一致 | 对照 `API_CONTRACT.md` |
| 410 | 会话过期/关闭/服务重启 | 重建会话 |
| 429 | 触发限流 | 按 `Retry-After` 退避或调高限额 |
| 401 | 开启了 `LOCAL_AUTH_TOKEN` 但头缺失 | 加 `X-Dialogue-Token` |
| 创空间启动失败 | 未监听 7860 或用了 `Authorization` | 用 `Dockerfile.modelscope`，改 `LOCAL_AUTH_HEADER` |
| `model_unavailable` | 未配置 Key/base URL、上游不可达 | 检查环境变量与网络；这是 fallback，不是崩溃 |
| 容器构建失败 | 无法访问 PyPI/基础镜像 | 配置镜像源或重试；本次未验证构建 |

## 9. 未验证声明

Docker 构建、创空间上线、HTTPS 证书与真实模型调用在本次交付中均**未验证**；相关步骤是部署指引而非已执行记录。已验证项见 `TEST_RESULTS.md`。
