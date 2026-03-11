.PHONY: help install install-python install-typescript test test-python test-typescript lint build docker-build docker-up docker-down clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: install-python install-typescript ## Install all dependencies

install-python: ## Install Python package (editable + dev + yaml)
	pip install -e "./src/python[yaml,dev]"

install-typescript: ## Install TypeScript dependencies
	cd src/typescript && npm install

test: ## Run full test suite (Python + TypeScript)
	./scripts/test-all.sh

test-python: ## Run Python tests only
	cd src/python && python -m pytest ../../tests/ -v

test-typescript: ## Run TypeScript tests only
	cd src/typescript && npm test

lint: ## Run linters (ruff + tsc)
	cd src/python && python -m ruff check .
	cd src/typescript && npm run lint

build: ## Build TypeScript dist
	cd src/typescript && npm run build

docker-build: ## Build Docker image
	docker build -t modelmesh .

docker-up: ## Start proxy via Docker Compose
	docker compose up --build -d

docker-down: ## Stop proxy
	docker compose down

clean: ## Remove build artifacts
	cd src/typescript && npm run clean 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
