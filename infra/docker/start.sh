#!/bin/bash

# AlsaniaMCP Unified Startup Script
# Now using a single docker-compose.yml (no core.yml)

set -e

echo "🚀 Starting Alsania Memory Control Plane (Unified)..."

# ---- Check Docker ----
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

if ! command -v docker-compose > /dev/null 2>&1; then
    echo "❌ docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# ---- Navigate to docker dir ----
cd "$(dirname "$0")"

# ---- Ensure persistent directories ----
echo "📂 Ensuring persistent directories exist..."
mkdir -p \
  ../backend/logs ../backend/data ../backend/state ../backend/memory \
  ../backend/echo_core/logs ../backend/echo_core/memory ../backend/echo_core/state ../backend/echo_core/learning \
  ../backend/echo_agents/cypher/workspace ../backend/echo_agents/cypher/logs \
  ../backend/echo_agents/scribe/workspace ../backend/echo_agents/scribe/logs \
  ../backend/echo_agents/sentinel/workspace ../backend/echo_agents/sentinel/logs \
  ../backend/telemetry/logs ../backend/telemetry/data ../backend/telemetry/metrics \
  ../backend/snapshot_manager/storage ../backend/snapshot_manager/backups ../backend/snapshot_manager/logs ../backend/snapshot_manager/recovery \
  ../backend/agent_registry/data ../backend/agent_registry/templates

# ---- Generate API keys ----
echo "🔑 Checking and generating API keys if needed..."
python3 ../../scripts/gen_api_keys.py -f || echo "⚠️ Could not generate API keys (continuing...)"

# ---- Build and start everything ----
echo "📦 Building and starting all services..."
docker-compose pull
docker-compose up --build -d

# ---- Health checks ----
echo "⏳ Waiting for core services to be healthy..."

# PostgreSQL
echo "🐘 Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Qdrant
echo "🔍 Waiting for Qdrant..."
until docker-compose exec -T qdrant bash -c "</dev/tcp/localhost/6333" > /dev/null 2>&1; do
    sleep 2
done
echo "✅ Qdrant is ready"

# Ollama
echo "🤖 Waiting for Ollama..."
until curl -sf http://localhost:11435/api/version > /dev/null 2>&1; do
    sleep 5
done
echo "✅ Ollama is ready"

# Backend
echo "⚡ Waiting for Backend (app)..."
until curl -sf http://localhost:8050/health > /dev/null 2>&1; do
    sleep 2
done
echo "✅ Backend (app) is ready"

echo ""
echo "🎉 Alsania Memory Control Plane is now running!"
echo ""
echo "📊 Services:"
echo "  • Frontend:        http://localhost:8080"
echo "  • Backend (MCP):   http://localhost:8050"
echo "  • Echo-Core:       http://localhost:8060"
echo "  • Agent Registry:  http://localhost:8090"
echo "  • Qdrant:          http://localhost:6333"
echo "  • PostgreSQL:      localhost:5432"
echo "  • Ollama:          http://localhost:11435"
echo ""
echo "📝 Logs: docker-compose logs -f"
echo "🛑 Stop: docker-compose down"
echo ""
