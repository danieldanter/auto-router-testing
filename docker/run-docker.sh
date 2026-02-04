#!/bin/bash
# ============================================
# Query Router - Local Docker Development
# ============================================
# Nur für lokale Entwicklung!
# Für Production: Kubernetes/Cloud Run

set -e

cd "$(dirname "$0")/.."

echo "🔨 Building Query Router Docker Image..."
docker build -t 506/query-router:dev -f docker/Dockerfile .

echo "🚀 Starting Query Router Container..."
# No credentials volume needed - credentials come from Secrets Service via .env
docker run -it --rm \
    -p 8000:8000 \
    --env-file .env \
    --name query-router \
    506/query-router:dev

echo "✅ Query Router stopped."
