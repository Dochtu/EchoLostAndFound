# M4-C 魔搭（ModelScope）部署预检

> 本轮**没有**上线公网、**没有**使用用户魔搭账号、**没有**购买任何资源或开通付费服务。本文给出统一部署结构、已本地验证的配置，以及尚未验证的边界。

---

## 1. 目标结构

一个 Docker 容器同时承担两件事，同源部署：

```
浏览器 ──▶ https://<创空间域名>/
              ├── GET /                → index.html（WebGL 入口，点开即玩）
              ├── GET /Build/*.gz      → 预压缩资源（Content-Encoding: gzip）
              └── /api/v1/*            → FastAPI（会话、回合、出示、取消、meta、health）
```

同源的理由：

1. 免 CORS 预检，少一轮往返；WebGL 前端可直接用页面 origin 作为 API 地址（`StationApiClient.ResolveBaseUrl()` 第二优先级）。
2. 模型密钥只存在服务端环境变量，前端与构建产物中不含任何 key。
3. 单容器单进程即可满足创空间免费实例（`threadsSupport=false`，无需多线程 wasm 与 COOP/COEP）。

### 1.1 推荐目录

```
G:\projects\EchoLostAndFound\
├── Server\                 # 现有 FastAPI 源码（app/、requirements.txt）
├── Deploy\
│   ├── Dockerfile          # 统一镜像
│   ├── build.ps1           # 组装 context/server + context/webgl
│   ├── .dockerignore
│   ├── .gitignore          # 忽略生成的 context/
│   ├── docker-compose.yml  # 本地等价编排
│   ├── README.md
│   └── context\            # 生成物（中间目录，不入库）
│       ├── server\{app,requirements.txt}
│       ├── webgl\{index.html,Build\*.gz,…}
│       ├── Dockerfile
│       └── .dockerignore
└── (Unity 工程) EchoLostAndFound_WebGL\   # 构建产物输出到 F:\EchoBuilds\M4C-WebGL-03 等
```

### 1.2 Dockerfile（实际内容摘要）

```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    MODEL_PROVIDER=mock WEB_ROOT=/app/web PORT=7860
WORKDIR /app
COPY server/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY server/app /app/app
COPY webgl /app/web
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 7860
HEALTHCHECK ... CMD python -c "...urlopen('http://127.0.0.1:7860/api/v1/health')..."
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","7860","--no-access-log"]
```

关键点：

- 固定监听 **0.0.0.0:7860**（魔搭 Docker 创空间的约定端口），`PORT` 仅作记录用途。
- 以非 root（uid 10001）运行。
- 内置 HEALTHCHECK，便于平台探活。
- `MODEL_PROVIDER=mock` 为默认值：**没有真实密钥也能完整游玩第一章**。
- 镜像层内**没有**任何 key；真实 key 仅由平台在运行时注入环境变量。

---

## 2. 已本地验证的部分（DONE）

| 检查 | 结果 |
| --- | --- |
| 构建上下文组装 | `webgl_files=17 webgl_bytes=21364584`、`server_bytes=262335` |
| `docker build` | exit 0，manifest `sha256:68ab62e02497defd23f01f6e83d288fccd4ad4cf846611fdab176592487e838e`（Docker Desktop 28.5.1，linux 容器） |
| 容器启动 | `docker run -d -p 7860:7860 -e MODEL_PROVIDER=mock` → `Up (healthy)` |
| `GET /` | 200，`text/html; charset=utf-8`，5,661 B（入口即游戏页） |
| `GET /api/v1/health` | 200，`ready=true`、`provider.kind=mock`、`is_synthetic=true`、`content_version=story-v1.0-phase2` |
| `GET /Build/M4C-WebGL-03.wasm` | 200，`Content-Encoding: gzip`，`Content-Type: application/wasm`，`Vary: Accept-Encoding, Origin` |
| `GET /Build/M4C-WebGL-03.data.gz` | 200，`Content-Encoding: gzip`，`Content-Type: application/octet-stream` |
| 容器内完整第一章 E2E | `M4C\E2E\container-01`：`completed=true`，0 异常、0 HTTP≥400、D01/D03/REC 各 1 次、8 条镜像一致日志 |
| 无密钥运行 | 全程未设置 `LLM_API_KEY`，Mock 路径完整可玩 |

镜像体积参考：基础 `python:3.12-slim` + 依赖 + 21 MB WebGL 产物。

---

## 3. 尚未验证的部分（UNVERIFIED）

| 项 | 说明 |
| --- | --- |
| 真实创空间部署 | 未上传镜像、未创建/更新创空间、未使用用户账号 |
| 平台反向代理下的 gzip 行为 | 本地验证了服务端头；平台若二次压缩或改写 `Content-Encoding`，需实测确认（Unity 对 `Content-Encoding` 与 `Content-Type` 很敏感） |
| HTTPS/TLS 与域名 | 平台提供，未验证证书与混合内容 |
| 平台冷启动/休眠策略 | 免费实例可能休眠，首次进入延迟未测 |
| 资源限额（CPU/内存/出网） | 未获取平台当前配额；10 MB 级内存与 ~21 MB 静态资源体量预计无压力，但未实测 |
| 平台日志/监控接入 | 未验证 |
| 真实模型 Provider 在该网络出口下的连通性 | 未验证（无可用的真实 key） |
| 并发/压测 | 仅功能级并发与限流单测，无压力基准 |

---

## 4. 安全与成本（公网无认证场景）

公开访问意味着任何人可消耗模型调用。当前缓解措施与建议：

| 风险 | 现有缓解 | 建议 |
| --- | --- | --- |
| 模型费用被刷 | 默认 `MODEL_PROVIDER=mock`（不计费）；固定剧情不调用模型 | **公开体验保持 mock**；真实模型仅在受控环境/白名单开放 |
| 请求频率 | 滑动窗口限流（默认 60/min、burst 20，仅 `/api/v1/*`） | 按 IP 收口（`TRUST_FORWARDED_FOR` + 平台真实 IP 头），需要时下调阈值 |
| 内存增长 | `MAX_SESSIONS=512`，终态保留 300 s，超限淘汰 | 公网可下调至 128 或更小 |
| 单次请求体过大 | `REQUEST_MAX_BYTES=32768`，含 chunked 校验 | 保持 |
| 输入长度滥用 | `PLAYER_INPUT_MAX_CHARS=1000`，客户端 200 字上限 | 保持 |
| 模型超时拖住资源 | `AI_TIMEOUT_MS=12000`（异步，不阻塞其他会话） | 公网可降至 8000 |
| 密钥泄露 | 仅环境变量注入；日志脱敏；`.dockerignore` 排除 `.env` | 使用平台 Secret 管理，不写进镜像与仓库 |
| 滥用内容 | `security.validate_model_reply` 过滤控制字符/危险片段/超长 | 保持 |
| 无认证 | 本轮不做认证（演示定位） | 若开放真实模型，必须加：一次性口令 / 访问码 / 每日额度 / 告警 |

成本估算（真实模型启用时，示意）：每次自由输入最多 220 输出 token；若按 60 次/分钟持续滥用，一小时可达 3600 次调用——因此**公开环境默认 mock** 是硬性建议，而不是可选项。

---

## 5. 授权后上线检查清单（供技术负责人执行）

1. 本地重跑：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File Deploy\build.ps1 -WebBuild F:\EchoBuilds\M4C-WebGL-03`（可选 `-Build`）。
2. 打标签并推送镜像到平台要求的仓库（或在创空间使用 Dockerfile 构建）。
3. 创空间设置：端口 **7860**、环境变量 `MODEL_PROVIDER=mock`、`WEB_ROOT=/app/web`、`AI_TIMEOUT_MS=8000`、`MAX_SESSIONS=128`、`CORS_ALLOWED_ORIGINS=<平台域名>`。
4. 真实模型（如获授权）：仅在 Secret 中注入 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`，并 `MODEL_PROVIDER=llm`；同时确认费用告警与额度上限。
5. 上线后必测：页面首屏、`.wasm`/`.data` 的 `Content-Type`+`Content-Encoding`、`/api/v1/health`、一次自由输入（Mock 标注可见）、一次断网离线回退。
6. 若平台代理改写了压缩头，退回方案：构建时用 `DSH_WEBGL_COMPRESSION=disabled`（体积变大但无 `Content-Encoding` 依赖），或让静态层显式按 `Accept-Encoding` 二次协商。

---

## 6. 本轮结论

- 统一部署结构可行，且已在**本地真实 Docker 容器**中端到端验证（页面 + API 同源、Mock 全流程、gzip 头正确）。
- 公网发布、平台代理行为、真实模型链路、配额与成本仍未验证，全部标记 **UNVERIFIED**；未进行任何上线动作。
