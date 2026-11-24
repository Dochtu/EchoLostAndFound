# Generic container image for the NPC AI service.
# Tested locally with Python 3.12; the image build itself is NOT verified in
# this delivery because Docker is not available on the development machine.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_PROVIDER=mock \
    CONTENT_DIR=/app/app/content

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/api/v1/health', timeout=3).status == 200 else 1)"

# 7860 is ModelScope's fixed Studio port; use -e PORT / command override for
# other hosts. Never pass real keys on the command line (they leak into `ps`);
# inject them as environment variables or secrets.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
