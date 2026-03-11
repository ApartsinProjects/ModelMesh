# Troubleshooting Guide

Common issues and solutions when working with ModelMesh.

---

## Installation Issues

### Python: `ModuleNotFoundError: No module named 'modelmesh'`

**Cause:** Package not installed or wrong Python environment.

```bash
# Verify installation
pip show modelmesh-lite

# Install if missing
pip install modelmesh-lite

# For development (editable install)
pip install -e "./src/python[yaml,dev]"
```

### TypeScript: `Cannot find module '@nistrapa/modelmesh-core'`

**Cause:** Package not installed or workspace not linked.

```bash
# Install from npm
npm install @nistrapa/modelmesh-core

# For development (from repo root)
npm install   # links workspace packages
```

### Python: `ImportError: No module named 'yaml'`

**Cause:** YAML extra not installed.

```bash
pip install modelmesh-lite[yaml]
```

---

## Configuration Issues

### `ConfigurationError: No providers configured`

**Cause:** No API keys found and no YAML config loaded.

**Solution:** Set at least one provider API key:
```bash
export OPENAI_API_KEY="sk-..."
# OR
export ANTHROPIC_API_KEY="sk-ant-..."
# OR
export GOOGLE_API_KEY="AI..."
```

Or load a YAML config:
```python
client = modelmesh.create(config="modelmesh.yaml")
```

### `NoActiveModelError: No active models in pool`

**Cause:** All models in the pool are deactivated (failed or budget-exceeded).

**Solutions:**
1. Check that your API keys are valid
2. Check provider status (OpenAI, Anthropic, etc.)
3. Add more providers for failover
4. Check budget limits in your config

```python
# Debug: see what models are available
client = modelmesh.create("chat-completion")
print(client.describe())
```

### YAML config not loading

**Cause:** File path wrong or YAML syntax error.

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('modelmesh.yaml'))"
```

---

## Runtime Issues

### `BudgetExceededError`

**Cause:** A model's daily or monthly budget limit was reached.

**Solutions:**
1. Increase budget limits in config
2. Add `on_budget_exceeded: rotate` to auto-switch to next provider
3. Add more providers with separate budgets

```yaml
pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: stick-until-failure
    on_budget_exceeded: rotate
```

### Slow responses / high latency

**Possible causes:**
1. Provider API is slow — check provider status page
2. Wrong rotation strategy — `cost-first` may pick slower providers

```yaml
pools:
  chat:
    strategy: latency-first   # prioritize speed
```

### `ProviderError: 429 Rate Limited`

**Cause:** Too many requests to a single provider.

**Solutions:**
1. Add more providers for load distribution
2. Use `round-robin` or `rate-limit-aware` rotation
3. Implement request queuing in your application

---

## Docker Issues

### `docker build` fails

**Common fixes:**
```bash
# Ensure you're in the repo root
cd ModelMesh

# Build with no cache
docker build --no-cache -t modelmesh .

# Check Docker is running
docker info
```

### Proxy returns 500 errors

**Debug steps:**
```bash
# Check container logs
docker compose logs modelmesh-proxy

# Verify config is mounted
docker compose exec modelmesh-proxy cat /app/modelmesh.yaml

# Test health endpoint
curl http://localhost:8080/v1/models
```

---

## Testing Issues

### Python tests fail with `asyncio` errors

**Cause:** Missing `pytest-asyncio` or wrong asyncio mode.

```bash
pip install pytest-asyncio
```

The project uses `asyncio_mode = "auto"` in `pyproject.toml`.

### TypeScript tests fail with `MODULE_NOT_FOUND`

**Cause:** Dependencies not installed.

```bash
cd src/typescript
npm install
npm test
```

### Running samples fails

**Python samples:**
```bash
pip install -e "./src/python[yaml]"
python samples/quickstart/python/00_hello.py
```

**TypeScript samples:**
```bash
npm install          # from repo root
npx tsx samples/quickstart/typescript/00_hello.ts
```

---

## Development Issues

### Version mismatch between Python and TypeScript

**Cause:** Versions bumped in one package but not the other.

```bash
# Check current versions
grep '^version' src/python/pyproject.toml
node -p "require('./src/typescript/package.json').version"

# Sync versions
./scripts/bump-version.sh 0.2.1
```

### Pre-commit hooks not running

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

---

## Still Stuck?

1. Check the [FAQ](FAQ.md) for answers to common questions
2. Search [GitHub Issues](https://github.com/ApartsinProjects/ModelMesh/issues)
3. Open a [Bug Report](https://github.com/ApartsinProjects/ModelMesh/issues/new?template=bug_report.yml)

See also: [Quick Start](QuickStart.md) | [System Configuration](../SystemConfiguration.md) | [FAQ](FAQ.md)
