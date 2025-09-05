# ================================================
# AlsaniaMCP Backend Multi-Stage Dockerfile
# ================================================

# Base stage with common dependencies
FROM python:3.11-slim as base
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create required directories
RUN mkdir -p /app/logs /app/state /app/memory /app/data/backups /app/data/snapshots

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev netcat-openbsd curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        redis psycopg2-binary qdrant-client fastapi uvicorn

# Copy backend code modules
COPY backend/core/ ./core/
COPY backend/agents/ ./agents/

# MCP Service Stage
FROM base as mcp
EXPOSE 8050
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD \
    curl -f http://localhost:8050/health || exit 1
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8050"]

# API Service Stage
FROM base as api
EXPOSE 8051
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD \
    curl -f http://localhost:8051/health || exit 1
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8051"]
