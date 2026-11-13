PYTHON ?= python3

.PHONY: up down seed test

up:
	docker compose up --build -d

seed:
	$(PYTHON) backend/scripts/seed.py

test:
	pytest -q

down:
	docker compose down -v
