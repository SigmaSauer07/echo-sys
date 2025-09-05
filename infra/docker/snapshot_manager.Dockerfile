# ================================================
# AlsaniaMCP Snapshot Manager Dockerfile
# ================================================
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/logs /app/snapshots /app/backups /app/recovery

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fastapi uvicorn

COPY backend/snapshot_manager/ ./snapshot_manager/
COPY backend/shared/ ./shared/
COPY backend/config/ ./config/

EXPOSE 8100
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD curl -f http://localhost:8100/health || exit 1

CMD ["uvicorn", "snapshot_manager.main:app", "--host", "0.0.0.0", "--port", "8100"]
