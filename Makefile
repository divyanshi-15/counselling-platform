PYTHON ?= python3

.PHONY: up down seed test kb calibrate risk-report

up:
	docker compose up --build -d

seed:
	$(PYTHON) backend/scripts/seed.py

kb:
	docker compose run --build --rm api sh -c 'alembic -c backend/alembic.ini upgrade head && python -m backend.scripts.load_kb'

calibrate:
	docker compose run --build --rm api sh -c 'alembic -c backend/alembic.ini upgrade head && python -m backend.scripts.calibrate_rag'

risk-report:
	docker compose run --build --rm -v "$(CURDIR):/app" api python -m backend.scripts.risk_report

test:
	docker compose exec -T postgres sh -lc 'db_exists=$$(psql -U "$$POSTGRES_USER" -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '\''counselling_test'\''"); if [ "$$db_exists" != "1" ]; then createdb -U "$$POSTGRES_USER" counselling_test; fi'
	docker compose run --build --rm -v "$(CURDIR):/app" -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/counselling_test api pytest -q

down:
	docker compose down -v
