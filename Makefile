# Development targets. Everything runs through uv — no global installs needed.

.DEFAULT_GOAL := help

.PHONY: help install install-dev lint lint-fix format typecheck test test-live coverage check build clean mcp mcp-http docker docker-run

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime dependencies
	uv sync

install-dev: ## Install runtime + dev dependencies
	uv sync --extra dev

lint: ## Ruff format check + lint
	uv run ruff format --check .
	uv run ruff check .

lint-fix: ## Auto-fix lint violations
	uv run ruff check --fix .

format: ## Apply ruff formatting
	uv run ruff format .

typecheck: ## mypy --strict over the package
	uv run mypy

test: ## Offline test suite (live tests skipped)
	uv run pytest -v

test-live: ## Full suite including live Google Hotels tests
	uv run pytest -v --live -m live

coverage: ## Offline suite with branch coverage report
	uv run pytest --cov --cov-report=term-missing --cov-report=html

check: lint typecheck test ## Everything CI runs

build: ## Build sdist + wheel into dist/
	uv build

clean: ## Remove build artifacts and caches
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

mcp: ## Run the stdio MCP server locally
	uv run ghotels mcp

mcp-http: ## Run the streamable-HTTP MCP server on :8000
	uv run ghotels mcp-http

docker: ## Build the Docker image
	docker build -t ghotels:dev .

docker-run: ## Run the Docker image (HTTP MCP on :8000)
	docker run --rm -p 8000:8000 ghotels:dev
