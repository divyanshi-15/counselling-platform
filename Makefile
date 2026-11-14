PYTHON ?= python3

.PHONY: up down seed test kb calibrate risk-report create-admin e2e

up:
	docker compose up --build -d

seed:
	docker compose run --build --rm api sh -c 'alembic -c backend/alembic.ini upgrade head && python -m backend.scripts.seed $(ARGS)'

create-admin:
	docker compose run --build --rm api sh -c 'alembic -c backend/alembic.ini upgrade head && python -m backend.scripts.create_admin "$(EMAIL)" "$(PASSWORD)"'

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

.PHONY: api-types
api-types:
	docker compose run --rm -T api python -c "import json; from backend.app.main import app; print(json.dumps(app.openapi()))" > frontend/openapi.json
	cd frontend && npm run gen:api

E2E_COMPOSE = docker compose -p cp-e2e -f docker-compose.yml -f docker-compose.e2e.yml

e2e:
	$(E2E_COMPOSE) down -v
	$(E2E_COMPOSE) up --build -d
	@status=1; \
	for i in $$(seq 1 60); do \
	  if $(E2E_COMPOSE) exec -T api python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then break; fi; sleep 2; \
	done; \
	$(E2E_COMPOSE) exec -T api sh -c 'alembic -c backend/alembic.ini upgrade head && python -m backend.scripts.seed' >/dev/null \
	  && (cd e2e && npm install --no-audit --no-fund >/dev/null && npx playwright install chromium >/dev/null && npx playwright test); \
	status=$$?; $(E2E_COMPOSE) down -v >/dev/null 2>&1; exit $$status
