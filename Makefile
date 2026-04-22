.PHONY: setup dev test lint typecheck migrate clean infra-up infra-down

setup:
	@command -v uv >/dev/null || (echo "uv not found; install with: curl -LsSf https://astral.sh/uv/install.sh | sh" && exit 1)
	@command -v pnpm >/dev/null || (echo "pnpm not found; install with: npm i -g pnpm" && exit 1)
	uv sync --all-packages
	pnpm install
	@[ -f .env ] || cp .env.example .env
	@mkdir -p workspace
	@echo "Setup complete. Next: 'make infra-up && make migrate && make dev'"

infra-up:
	docker compose -f infra/docker/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker/docker-compose.yml down

dev:
	@echo "Start the API (apps/api) and web (apps/web) in separate terminals:"
	@echo "  uv run uvicorn orchestra_api.main:app --reload --host 0.0.0.0 --port 8000"
	@echo "  pnpm dev:web"

test:
	uv run pytest -q

test-integration:
	uv run pytest -q -m integration --override-ini="addopts="

lint:
	uv run ruff check .
	pnpm lint:web

typecheck:
	uv run mypy packages apps/api

migrate:
	uv run alembic -c infra/migrations/alembic.ini upgrade head

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
