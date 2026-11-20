# Deploy notes

Server: `/opt/app` (user `deploy`), Docker Compose, Caddy terminates HTTPS. Secrets live only in `/opt/app/.env` (chmod 600).

- **Update:** `ssh deploy@HOST`, then `/opt/app/deploy.sh` (pull, build, up, migrate, health check).
- **Logs:** `cd /opt/app && docker compose logs -f --tail=100 api` (also `caddy`, `postgres`). Docker rotates logs (10 MB x 3).
- **Backups:** nightly 02:30 UTC via cron (`/opt/app/backup.sh`) into `/opt/backups`, 7 days kept. Verify: `/opt/app/backup.sh --test-restore`.
- **Restore:** `gunzip -c /opt/backups/db-<ts>.sql.gz | docker compose exec -T postgres psql -U postgres -d counselling` into an empty database (drop and recreate it first, with `CREATE EXTENSION vector`). Uploads: `docker compose exec -T api tar -C /data/uploads -xzf - < /opt/backups/uploads-<ts>.tar.gz`.
- **Rotate the API key:** edit `ANTHROPIC_API_KEY` in `/opt/app/.env`, then `docker compose up -d api`. Revoke the old key in the Anthropic console.
- **Switch to a real domain:** point its A record at the server, set `DOMAIN` and `PUBLIC_BASE_URL` in `.env`, then `docker compose up -d`. Caddy issues the certificate automatically (ports 80/443 must be open).
- **Seeded accounts:** `python -m backend.scripts.rotate_seed_passwords` rotates any account still on a seeded default password.
