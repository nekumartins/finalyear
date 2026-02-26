# ──────────────────────────────────────────────────
# Debate Coach — Makefile convenience commands
# ──────────────────────────────────────────────────

.PHONY: dev prod down logs shell migrate ps help

## Start the full dev stack (hot-reload for both backend and frontend)
dev:
	docker compose up --build

## Start in detached dev mode
dev-d:
	docker compose up --build -d

## Build and start the production stack (single container)
prod:
	docker compose -f docker-compose.prod.yml up --build -d

## Stop all running containers (dev stack)
down:
	docker compose down

## Stop the production stack
prod-down:
	docker compose -f docker-compose.prod.yml down

## Tail logs for all services (or: make logs s=backend)
logs:
	docker compose logs -f $(s)

## Show container status
ps:
	docker compose ps

## Open a shell in the backend container
shell:
	docker compose exec backend bash

## Run Alembic migrations inside the backend container
migrate:
	docker compose exec backend alembic upgrade head

## Show this help message
help:
	@echo ""
	@echo "  Debate Coach — Docker commands"
	@echo ""
	@echo "  make dev       Start full dev stack (postgres + backend + frontend, hot-reload)"
	@echo "  make dev-d     Same but detached (background)"
	@echo "  make prod      Build and start production stack"
	@echo "  make down      Stop dev stack"
	@echo "  make prod-down Stop production stack"
	@echo "  make logs      Tail all logs  (make logs s=backend for one service)"
	@echo "  make ps        Show running containers"
	@echo "  make shell     Open bash in backend container"
	@echo "  make migrate   Run Alembic DB migrations"
	@echo ""
