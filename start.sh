#!/bin/bash
set -e

echo "🧠 Starting Codebase Intelligence Engine..."

# Check .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env not found — creating from template"
    cp .env.example .env
    echo "📝 Edit .env with your API keys before continuing"
    exit 1
fi

# Create data directories
mkdir -p data/uploads data/indexes

# Start services
echo "🐳 Building and starting Docker containers..."
docker-compose up --build -d

echo ""
echo "✅ Services started!"
echo "   Backend API:  http://localhost:8000"
echo "   API Docs:     http://localhost:8000/docs"
echo "   Frontend UI:  http://localhost:8501"
echo ""
echo "📋 View logs: docker-compose logs -f"
echo "🛑 Stop:      docker-compose down"