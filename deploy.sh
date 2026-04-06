#!/usr/bin/env bash
# Deploy Tuesday to production
# Usage: ssh your-droplet './deploy.sh'
set -e

cd "$(dirname "$0")"

echo "Pulling latest changes..."
git pull origin main

echo "Rebuilding and restarting..."
docker compose up -d --build

echo "Waiting for startup..."
sleep 5

if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "Deployed successfully."
else
    echo "Warning: Health check failed. Check logs with: docker compose logs -f"
fi
