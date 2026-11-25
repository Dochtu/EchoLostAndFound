# Generic container image for the NPC AI service.
# Verified locally (M5-C-A) by building the independent candidate in
# Deploy/../M5CA/deploy and running the Docker acceptance driver; the
# ModelScope platform image itself is still represented by the frozen M5-A
# candidate in Builds/. M5-C-A does NOT approve a live-model online trial.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENTRY_MODE=mock \
    MODEL_PROVIDER=mock \
    CONTENT_DIR=/app/app/content \
    LLM_USAGE_PATH=/app/.local/llm-usage.sqlite3 \
    LLM_LEDGER_EPOCH_PATH=/app/.local/epoch/ledger-epoch.json

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/.local/epoch \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/api/v1/health', timeout=3).status == 200 else 1)"

# ``app.entry`` imports the app once and therefore fails fast when live mode is
# requested without a usable ledger. Single worker only: sessions, limiters and
# the circuit breaker are in-process state.
# ``app.server_entry`` disables Uvicorn's own ``--proxy-headers`` rewriting so
# the application stays the single owner of client-address resolution (see
# ``app/server_entry.py``). 7860 is ModelScope's fixed Studio port; use -e PORT
# for other hosts. Never pass real keys on the command line (they leak into
# `ps`); inject them as environment variables or secrets.
CMD ["python", "-m", "app.server_entry"]
