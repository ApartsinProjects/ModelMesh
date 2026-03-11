# Contributing to ModelMesh

Thank you for your interest in contributing! This guide will help you get set up.

## Prerequisites

- **Python 3.11+** — for the core library and tests
- **Node.js 18+** — for the TypeScript library and tests
- **Git** — for version control
- **Docker** (optional) — for proxy deployment testing
- **pre-commit** (optional) — for automated code quality checks

## Quick Setup

```bash
# 1. Clone the repository
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh

# 2. Install everything with make
make install

# 3. Set up pre-commit hooks (recommended)
pip install pre-commit
pre-commit install

# 4. Run the full test suite
make test
```

### Manual Setup (without make)

```bash
# Install Python package (editable + dev dependencies)
pip install -e "./src/python[yaml,dev]"

# Install TypeScript dependencies
cd src/typescript && npm install && cd ../..

# Install workspace dependencies (links local packages)
npm install

# Run tests
./scripts/test-all.sh
```

### VS Code Dev Container

If you use VS Code, the repo includes a **Dev Container** configuration:

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the repo in VS Code
3. Click "Reopen in Container" when prompted
4. Everything is pre-installed and ready to go

## Running Tests

```bash
# All tests (Python + TypeScript)
make test

# Python only
make test-python

# TypeScript only
make test-typescript

# Integration tests
make test-integration

# Performance benchmarks
make test-benchmarks

# Test coverage report
make coverage
```

## Running Samples

**Python samples** require the package to be installed:

```bash
pip install -e "./src/python[yaml]"
python samples/quickstart/python/00_hello.py
```

**TypeScript samples** require workspace setup:

```bash
npm install                                          # from repo root
npx tsx samples/quickstart/typescript/00_hello.ts    # from repo root
```

## Project Structure

```
ModelMesh/
├── src/python/            # Python library source
├── src/typescript/        # TypeScript library source
├── tests/                 # Python test suite
│   ├── integration/       # End-to-end integration tests
│   └── benchmarks/        # Performance benchmarks
├── samples/               # Code samples (Python + TypeScript)
│   ├── quickstart/        # Getting started examples
│   ├── system/            # Multi-provider integration examples
│   ├── cdk/               # Connector Development Kit tutorials
│   └── connectors/        # Custom connector examples
├── docs/                  # Documentation (GitHub Pages)
├── scripts/               # Automation scripts
├── tools/                 # Developer tools
│   └── starter-template/  # Project starter templates
├── .devcontainer/         # VS Code Dev Container config
└── .github/               # CI/CD, issue templates, Dependabot
    ├── workflows/         # GitHub Actions
    ├── ISSUE_TEMPLATE/    # Bug report & feature request forms
    └── PULL_REQUEST_TEMPLATE.md
```

## Code Style

- **Python**: Follows [ruff](https://github.com/astral-sh/ruff) defaults, 120 char line length. Type hints checked with mypy.
- **TypeScript**: Strict mode, 2-space indent. ESLint + Prettier for formatting.

### Formatting & Linting

```bash
# Lint everything
make lint

# Auto-format code
make format

# Run pre-commit on all files
make pre-commit
```

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes with tests
3. Run the full test suite: `make test`
4. Run linters: `make lint`
5. Update CHANGELOG.md if the change is user-facing
6. Submit a PR against the `master` branch
7. Fill out the PR template (checklist, description, breaking changes)

The CI pipeline will automatically run:
- Lint (ruff, mypy, tsc --noEmit, version consistency)
- Python tests on 3.11, 3.12, 3.13
- TypeScript tests on Node 18, 20
- Docker build verification
- CodeQL security analysis

## Adding a Custom Connector

See the [CDK Developer Guide](docs/cdk/DeveloperGuide.md) for tutorials on building:
- Custom providers
- Custom rotation policies
- Custom secret stores, storage, observability, and discovery connectors

## Releasing a New Version

```bash
# Bump version in both Python and TypeScript
./scripts/bump-version.sh 0.3.0

# Commit, tag, and push
git add -A && git commit -m "chore: bump to v0.3.0"
git tag v0.3.0
git push origin master --tags
```

GitHub Actions will automatically:
- Create a GitHub Release with changelog and build artifacts
- Publish to npm (if NPM_TOKEN secret is set)
- Publish to PyPI (if PyPI environment is configured)
- Build and push multi-platform Docker images

## Useful Make Targets

| Target | Description |
|---|---|
| `make help` | Show all available targets |
| `make install` | Install all dependencies |
| `make test` | Run full test suite |
| `make lint` | Run all linters |
| `make format` | Auto-format code |
| `make coverage` | Generate coverage reports |
| `make docs` | Generate API documentation |
| `make docker-build` | Build Docker image |
| `make clean` | Remove build artifacts |

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
