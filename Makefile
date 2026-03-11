.PHONY: help install install-python install-typescript test test-python test-typescript test-integration test-benchmarks lint lint-python lint-typescript format coverage build docs docker-build docker-up docker-down clean pre-commit check-licenses

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: install-python install-typescript ## Install all dependencies
	npm install

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

test-integration: ## Run integration tests
	cd src/python && python -m pytest ../../tests/integration/ -v

test-benchmarks: ## Run performance benchmarks
	cd src/python && python -m pytest ../../tests/benchmarks/ -v

lint: lint-python lint-typescript ## Run all linters

lint-python: ## Lint Python (ruff + mypy)
	cd src/python && python -m ruff check .
	cd src/python && python -m mypy modelmesh --ignore-missing-imports --no-error-summary || true

lint-typescript: ## Lint TypeScript (tsc + eslint)
	cd src/typescript && npm run lint

format: ## Format code (ruff + prettier)
	cd src/python && python -m ruff format .
	cd src/typescript && npm run format 2>/dev/null || true

coverage: ## Generate test coverage reports
	cd src/python && python -m pytest ../../tests/ --cov=modelmesh --cov-report=term-missing -v
	cd src/typescript && npx jest --coverage

build: ## Build TypeScript dist
	cd src/typescript && npm run build

docs: ## Generate API documentation
	cd src/typescript && npm run docs 2>/dev/null || echo "Install typedoc: npm i -D typedoc"

docker-build: ## Build Docker image
	docker build -t modelmesh .

docker-up: ## Start proxy via Docker Compose
	docker compose up --build -d

docker-down: ## Stop proxy
	docker compose down

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

check-licenses: ## Check license headers in source files
	./scripts/check-licenses.sh

clean: ## Remove build artifacts
	cd src/typescript && npm run clean 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name coverage -exec rm -rf {} + 2>/dev/null || true
	rm -rf docs/api/ 2>/dev/null || true
