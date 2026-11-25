# 统一部署（WebGL 页面 + FastAPI `/api/v1` 同源）

本目录是 M4-C 的魔搭（ModelScope）部署预检产物：把「浏览器点开即玩」所需的
两半——Unity WebGL 静态页面与 FastAPI 对话服务——放进同一个容器、同一个端口，
从而避免跨域、避免把模型密钥放进客户端，也让 Mock 形态可以直接试玩。

**当前状态：配置已就绪；容器构建与运行 UNVERIFIED（本机 Docker 引擎未启动）。**
同源统一服务（不经容器）已在本机用 `WEB_ROOT` 实测通过，见
`M4C_ModelScope_Preflight.md`。

## 目录

| 文件 | 作用 |
| --- | --- |
| `Dockerfile` | 统一镜像：装 Python 依赖、复制 `server/app` 与 `webgl/`、以非 root 用户监听 `0.0.0.0:7860` |
| `docker-compose.yml` | 本地等价运行方式（端口 7860，默认 Mock） |
| `build.ps1` | 组装构建上下文 `Deploy/context`（server + webgl），可选 `-Build` 直接构建 |
| `.dockerignore` | 上下文忽略清单（缓存与本地日志，不排除 `server/`、`webgl/`） |
| `context/` | 中间产物，由 `build.ps1` 生成，不进入版本库 |

## 为什么是「同源单容器」

1. Unity WebGL 构建产物必须通过 HTTP 提供；把静态站与服务放进同一个端口后，
   客户端 `StationApiClient.ResolveBaseUrl()` 直接使用页面 origin，无需 `?api=`
   参数，也不需要额外的 CORS 配置。
2. 真实模型密钥只在服务端环境变量中存在；镜像里 `MODEL_PROVIDER=mock`，
   没有密钥时游戏仍能完整试玩第一章。
3. gzip 预压缩资源由 `Server/app/static_site.py` 以正确的 `Content-Type` 与
   `Content-Encoding: gzip` 返回（Unity 构建启用了 gzip，且未启用线程，
   因此不需要 COOP/COEP 头）。

## 构建与本地运行

```powershell
# 1) 组装上下文（默认取最新的 WebGL 构建目录）
pwsh -File Deploy/build.ps1 -WebBuild F:\EchoBuilds\M4C-WebGL-03

# 2) 构建镜像
pwsh -File Deploy/build.ps1 -WebBuild F:\EchoBuilds\M4C-WebGL-03 -Build
# 等价于：
docker build -t echolostfound-unified:local Deploy/context

# 3) 运行
docker run --rm -p 7860:7860 -e MODEL_PROVIDER=mock echolostfound-unified:local
# 打开 http://127.0.0.1:7860/ 即可开始游戏
```

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MODEL_PROVIDER` | `mock` | `mock` 完整试玩；`llm` 接外部模型；`disabled` 关闭自由对话 |
| `WEB_ROOT` | `/app/web` | 静态站根目录；为空时只提供 API |
| `LLM_BASE_URL` / `LLM_MODEL` | 空 | 仅 `MODEL_PROVIDER=llm` 时使用 |
| `LLM_API_KEY` | 空 | 只从运行环境注入，禁止写入镜像、仓库或客户端 |
| `AI_TIMEOUT_MS` | `12000` | 上游模型超时；超时后回落为固定剧情，不阻塞其他会话 |
| `SESSION_TTL_SECONDS` / `MAX_SESSIONS` | `1800` / `512` | 会话过期与实例内会话上限，防止公开访问无限增长 |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_BURST` | `60` / `20` | 每 IP 滑动窗口限流 |
| `CORS_ALLOWED_ORIGINS` | 本机来源 | 同源部署时保持默认即可；不要把 `*` 放进生产 |

## 魔搭创空间（Docker）注意事项

- 创空间 Docker 运行只暴露一个端口（本配置为 `7860`），不要改成 8000/8080。
- 平台提供的是「无认证公网访问」：任何人打开页面都能消耗模型调用额度。
  正式上线前至少做到：保持 `MODEL_PROVIDER=mock` 或为真实模型配置服务端配额与限流，
  不要在公开演示环境使用个人付费密钥。
- WebGL 产物约 21 MB（gzip），冷启动需要几秒；`index.html` 已由构建管线生成，
  入口页面直接进入游戏场景。
