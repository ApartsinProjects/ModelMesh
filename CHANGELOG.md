# Changelog

All notable changes to ModelMesh are documented here.

## [0.2.0] — 2026-03-11

### Added
- **21-question FAQ** covering all major library features (middleware, error handling, proxy, storage, observability, streaming, discovery, multi-pool, hot-reload, browser usage)
- **Programmatic connector registration** — all 6 connector types support `"instance"` injection via API
- **`register_connector()`** function for runtime registration of custom connector classes
- **Budget-aware rotation** — `on_budget_exceeded: rotate` pool config option
- **CONTRIBUTING.md** — contributor setup guide
- **Makefile** — unified task runner (`make install`, `make test`, `make lint`, `make docker-up`)
- **`modelmesh.example.yaml`** — annotated config template for Docker/YAML setup
- **Root `package.json`** with npm workspaces for monorepo support
- **Samples `package.json` + `tsconfig.json`** — TypeScript samples can now be run directly
- **`.editorconfig`** — consistent formatting across editors
- **`scripts/bump-version.sh`** — atomic version sync between Python and TypeScript
- Docker healthcheck in Dockerfile and docker-compose.yaml
- **GitHub Issue Templates** — structured bug report and feature request forms
- **GitHub Pull Request Template** — checklist for tests, docs, changelog
- **SECURITY.md** — vulnerability disclosure policy
- **VS Code Dev Container** (`.devcontainer/`) — one-click dev environment
- **Dependabot** — automated dependency updates for Python, npm, Docker, Actions
- **CodeQL security scanning** — weekly + PR security analysis
- **Test coverage reporting** — pytest-cov + Jest coverage → Codecov CI workflow
- **Prettier + ESLint** — TypeScript code formatting and linting
- **mypy type checking** — Python type checking in CI
- **TypeDoc configuration** — auto-generated TypeScript API docs
- **Troubleshooting Guide** (`docs/guides/Troubleshooting.md`)
- **npm publish workflow** — GitHub Actions → npm with provenance
- **PyPI publish workflow** — GitHub Actions → PyPI with trusted publishing
- **GitHub Release workflow** — auto-create releases from tags with assets
- **Docker multi-platform build** — linux/amd64 + linux/arm64 images
- **Integration test suite** (`tests/integration/`) — end-to-end routing tests
- **Performance benchmark suite** (`tests/benchmarks/`) — routing latency tests
- **Pre-commit hooks** (`.pre-commit-config.yaml`) — ruff, prettier, gitleaks
- **Starter templates** (`tools/starter-template/`) — Python and TypeScript project starters
- **License compliance check** (`scripts/check-licenses.sh`)

### Fixed
- Dockerfile `COPY` path corrected (was referencing root-level `pyproject.toml`)
- `install-python.sh` now runs `pip install` from correct directory
- `test-all.sh` now runs `npm install` before TypeScript tests
- `.env.example` clarified — only one provider key required (not all three)
- 553 internal doc links fixed (`.html` → `.md` extension consistency)
- Cross-reference audit: all docs have proper "See also" links

### Changed
- FAQ expanded from 10 to 21 questions
- Docker Compose now includes healthcheck and restart policy
- README expanded with "Running Samples" section and CONTRIBUTING link

## [0.1.0] — 2026-03-06

### Added
- Initial release of ModelMesh Lite
- Python and TypeScript libraries with zero core dependencies
- OpenAI-compatible API interface
- 8 rotation strategies (stick-until-failure, round-robin, cost-first, latency-first, etc.)
- 22 pre-shipped provider connectors
- Capability-based routing with hierarchical taxonomy
- Budget enforcement with daily/monthly limits
- Mock client for testing
- Docker proxy deployment
- 54 pre-shipped connectors across 6 types
- CDK (Connector Development Kit) with base classes
- Comprehensive documentation suite (14 docs + 5 CDK docs + 8 guides)
- 1,879 tests (1,166 Python + 713 TypeScript)
