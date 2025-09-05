#!/bin/bash

# AlsaniaMCP Docker Compose Stop Script

set -e

echo "🛑 Stopping Alsania Memory Control Plane..."

# Navigate to the docker directory
cd "$(dirname "$0")"

# Stop and remove containers
docker-compose down

echo "✅ All services stopped"
echo ""
echo "💡 To remove volumes as well, run: docker-compose down -v"
echo "💡 To remove images as well, run: docker-compose down --rmi all"
echo ""
