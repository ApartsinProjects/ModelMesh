# Contributing to ModelMesh

Thank you for your interest in contributing! This guide will help you get set up.

## Prerequisites

- **Python 3.11+** — for the core library and tests
- **Node.js 18+** — for the TypeScript library and tests
- **Git** — for version control
- **Docker** (optional) — for proxy deployment testing

## Quick Setup

```bash
# 1. Clone the repository
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh

# 2. Install Python package (editable + dev dependencies)
pip install -e "./src/python[yaml,dev]"

# 3. Install TypeScript dependencies
cd src/typescript && npm install && cd ../..

# 4. Install sample dependencies (links the local TypeScript package)
npm install   # from the root — uses workspaces

# 5. Run the full test suite
./scripts/test-all.sh
```

## Running Tests

```bash
# All tests (Python + TypeScript)
./scripts/test-all.sh

# Python only (1,166 tests)
cd src/python && python -m pytest ../../tests/ -v

# TypeScript only (713 tests)
cd src/typescript && npm test
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
├── src/python/         # Python library source
├── src/typescript/     # TypeScript library source
├── tests/              # Python test suite
├── samples/            # Code samples (Python + TypeScript)
│   ├── quickstart/     # Getting started examples
│   ├── system/         # Multi-provider integration examples
│   ├── cdk/            # Connector Development Kit tutorials
│   └── connectors/     # Custom connector examples
├── docs/               # Documentation (GitHub Pages)
├── scripts/            # Automation scripts
└── .github/workflows/  # CI/CD pipelines
```

## Code Style

- **Python**: Follows [ruff](https://github.com/astral-sh/ruff) defaults, 120 char line length
- **TypeScript**: Strict mode, 2-space indent

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes with tests
3. Run the full test suite: `./scripts/test-all.sh`
4. Submit a PR against the `master` branch
5. Describe what changed and why in the PR description

## Adding a Custom Connector

See the [CDK Developer Guide](docs/cdk/DeveloperGuide.md) for tutorials on building:
- Custom providers
- Custom rotation policies
- Custom secret stores, storage, observability, and discovery connectors

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
