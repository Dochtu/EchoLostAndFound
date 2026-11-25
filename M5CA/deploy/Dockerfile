# M5-C-A independent deployment candidate.
# Source is copied into the build context by ../build_candidate.ps1; the image
# runs exactly one uvicorn worker (the budget/breaker/limiter design is
# single-process by contract).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/.local/epoch \
    && chown -R appuser:appuser /app/.local /app

USER appuser

ENV APP_ENTRY_MODE=mock \
    MODEL_PROVIDER=mock \
    CONTENT_DIR=/app/app/content \
    LLM_USAGE_PATH=/app/.local/llm-usage.sqlite3 \
    LLM_LEDGER_EPOCH_PATH=/app/.local/epoch/ledger-epoch.json \
    LLM_REQUEST_LIMIT=30 \
    LLM_REQUEST_LIMIT_PER_SESSION=8 \
    AI_TIMEOUT_MS=12000 \
    LOG_LEVEL=INFO

EXPOSE 7860

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:7860/api/v1/health', timeout=3)"

# One process, one worker: the in-memory sessions, budget lock and circuit
# breaker are process-local by design.
CMD ["uvicorn", "app.entry:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
