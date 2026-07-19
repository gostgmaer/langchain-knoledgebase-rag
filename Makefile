dev:
	docker compose -f docker/compose/docker-compose.dev.yml up -d

prod:
	docker compose -f docker/compose/docker-compose.prod.yml up -d

stop:
	docker compose down

build:
	docker compose build

rebuild:
	docker compose build --no-cache

logs:
	docker compose logs -f

api:
	docker compose exec api bash

worker:
	docker compose exec worker bash

db:
	docker compose exec postgres psql -U postgres

redis:
	docker compose exec redis redis-cli

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate