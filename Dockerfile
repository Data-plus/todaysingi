FROM mcr.microsoft.com/playwright/python:v1.61.0-noble@sha256:a9731514f24121d1dcd25d58d0a38146646d290a5998fd80d3e533e7b5e21c69

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TMPDIR=/tmp/todaysingi \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

COPY scripts/requirements.txt /tmp/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk ca-certificates \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /tmp/todaysingi \
    && chown -R appuser:appuser /tmp/todaysingi

COPY --chown=appuser:appuser worker ./worker
COPY --chown=appuser:appuser scripts ./scripts

USER appuser

CMD ["python", "-m", "worker.cloud_main", "--drain"]
