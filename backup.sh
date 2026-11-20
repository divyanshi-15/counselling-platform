#!/usr/bin/env bash
# Nightly: pg_dump + uploads tar into /opt/backups, keep 7 days. `backup.sh --test-restore` restores the latest dump into a temp DB.
set -euo pipefail
cd "$(dirname "$0")"
DEST=/opt/backups
if [ "${1:-}" = "--test-restore" ]; then
  f=$(ls -1t "$DEST"/db-*.sql.gz | head -1)
  docker compose exec -T postgres psql -U postgres -c "DROP DATABASE IF EXISTS restore_test" -c "CREATE DATABASE restore_test" >/dev/null
  docker compose exec -T postgres psql -U postgres -d restore_test -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null
  gunzip -c "$f" | docker compose exec -T postgres psql -U postgres -d restore_test -v ON_ERROR_STOP=1 -q >/dev/null
  n=$(docker compose exec -T postgres psql -U postgres -d restore_test -Atc "select count(*) from users")
  docker compose exec -T postgres psql -U postgres -c "DROP DATABASE restore_test" >/dev/null
  [ "$n" -gt 0 ] && echo "RESTORE PASS ($f, users=$n)" || { echo "RESTORE FAIL ($f)"; exit 1; }
  exit 0
fi
ts=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T postgres pg_dump -U postgres -d counselling | gzip > "$DEST/db-$ts.sql.gz"
docker compose exec -T api tar -C /data/uploads -czf - . > "$DEST/uploads-$ts.tar.gz"
find "$DEST" -maxdepth 1 -type f \( -name 'db-*.sql.gz' -o -name 'uploads-*.tar.gz' \) -mtime +7 -delete
echo "backup $ts OK"
