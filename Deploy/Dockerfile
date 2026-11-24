# 统一部署镜像：同一个容器同时提供 WebGL 页面与 FastAPI /api/v1
#
# 构建上下文由 Deploy/build.ps1 组装：
#   context/server/   <- 仓库 Server/（app + requirements.txt）
#   context/webgl/    <- Unity WebGL 构建产物（index.html + Build/*.gz）
#
# 运行时要求：
#   * 监听 0.0.0.0:7860（魔搭 Docker 创空间固定端口，不可修改）
#   * 模型密钥只通过平台环境变量注入，绝不写入镜像层
#   * 未配置真实模型时 MODEL_PROVIDER=mock 即可完整单机试玩
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_PROVIDER=mock \
    WEB_ROOT=/app/web \
    PORT=7860

WORKDIR /app

COPY server/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

COPY server/app /app/app
COPY webgl /app/web

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/api/v1/health', timeout=3).status == 200 else 1)"

# 单进程即可：会话与限流都在进程内，创空间免费实例按 1 副本运行。
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--no-access-log"]
