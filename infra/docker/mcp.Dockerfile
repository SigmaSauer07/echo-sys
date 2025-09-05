# ================================================
# AlsaniaMCP MCP Service Dockerfile
# ================================================
FROM python:3.11-slim
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

# Expose port
EXPOSE 8050

# Healthcheck endpoint
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD \
    curl -f http://localhost:8050/health || exit 1

# Run MCP (Main Control Plane)
CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8050"]
