# ================================================
# AlsaniaMCP Echo-Core Dockerfile
# ================================================
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/logs /app/memory /app/state /app/learning

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev netcat-openbsd curl git \
    && rm -rf /var/lib/apt/lists/*

COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir redis psycopg2-binary qdrant-client fastapi uvicorn

COPY backend/echo_core/ ./echo_core/
COPY backend/core/ ./core/
COPY backend/config/ ./config/
COPY backend/shared/ ./shared/

EXPOSE 8060
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD curl -f http://localhost:8060/health || exit 1

CMD ["uvicorn", "echo_core.main:app", "--host", "0.0.0.0", "--port", "8060"]
