#!/usr/bin/env bash
# One-command update: git pull, build, up -d, migrate, health check.
set -euo pipefail
cd "$(dirname "$0")"
git pull --ff-only origin main
docker compose up -d --build
for i in $(seq 1 30); do
  docker compose exec -T api python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health', timeout=3)" >/dev/null 2>&1 && break
  [ "$i" = 30 ] && { echo "api did not become healthy"; docker compose logs --tail=30 api; exit 1; }
  sleep 2
done
docker compose exec -T api alembic -c backend/alembic.ini upgrade head
docker compose ps
echo "deploy OK"
