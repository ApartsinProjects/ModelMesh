# ModelMesh Test Skill

## Purpose
Run the ModelMesh test suite and verify integration correctness.

## Running Tests

### Python Tests (855 tests)

```bash
cd ModelMesh

# Install dev dependencies
pip install -e ".[yaml,dev]"

# Run all Python tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_mesh.py -v

# Run with coverage
python -m pytest tests/ --cov=modelmesh --cov-report=term-missing
```

### TypeScript Tests (511 tests)

```bash
cd ModelMesh/src/typescript

# Install dependencies
npm install

# Run all TypeScript tests
npm test

# Run in watch mode
npm run test:watch

# Run specific test file
npx jest tests/connectors.test.ts --verbose
```

### All Tests

```bash
# Use the automation script
./scripts/test-all.sh

# Python only
./scripts/test-all.sh --python

# TypeScript only
./scripts/test-all.sh --ts
```

### Docker Infrastructure Tests

```bash
# Tests that verify Docker files, configs, and scripts (no Docker required)
python -m pytest tests/test_docker.py -v
```

### Proxy Smoke Tests (Requires Running Proxy)

```bash
# Start proxy first
docker compose up --build -d

# Run smoke tests
./scripts/proxy-test.sh

# Full cycle: build + start + test + stop
./scripts/proxy-test.sh --full
```

## Test Structure

| File | Tests | Covers |
|---|---|---|
| `tests/test_mesh.py` | ~100 | Core ModelMesh: Router, Pool, Model lifecycle |
| `tests/test_config.py` | ~80 | Configuration: YAML, auto-detect, validation |
| `tests/test_providers.py` | ~120 | Provider connectors: all 22 providers |
| `tests/test_rotation.py` | ~80 | Rotation strategies: all 8 policies |
| `tests/test_cdk.py` | ~100 | CDK base classes and specialized connectors |
| `tests/test_client.py` | ~60 | MeshClient: OpenAI compatibility |
| `tests/test_docker.py` | ~80 | Docker infrastructure and proxy |
| `tests/test_secret_stores.py` | ~50 | Secret store connectors |
| `tests/test_storage.py` | ~50 | Storage backends |
| `src/typescript/tests/*.test.ts` | 511 | TypeScript parallel implementations |

## Writing Integration Tests

After integrating ModelMesh into a project, add a basic smoke test:

### Python

```python
import pytest
import os

def test_modelmesh_integration():
    """Verify ModelMesh creates a working client."""
    import modelmesh

    # Skip if no API keys available
    if not any(os.getenv(k) for k in [
        'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GROQ_API_KEY'
    ]):
        pytest.skip("No API keys available")

    client = modelmesh.create("chat-completion")

    # Verify client has expected methods
    assert hasattr(client, 'chat')
    assert hasattr(client.chat, 'completions')

    # Test actual API call (optional, requires valid key)
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Say 'test passed'"}],
        max_tokens=10,
    )
    assert response.choices[0].message.content is not None
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

describe('ModelMesh Integration', () => {
  it('creates a working client', () => {
    // Will throw if no providers detected
    const hasKey = process.env.OPENAI_API_KEY ||
                   process.env.ANTHROPIC_API_KEY ||
                   process.env.GROQ_API_KEY;
    if (!hasKey) return; // skip

    const client = create('chat-completion');
    expect(client).toBeDefined();
    expect(client.chat).toBeDefined();
    expect(client.chat.completions).toBeDefined();
  });
});
```

### Docker Proxy

```bash
#!/bin/bash
# test-proxy-integration.sh

BASE="http://localhost:8080"

# Health
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
[ "$STATUS" = "200" ] || { echo "FAIL: health"; exit 1; }

# Models
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/models")
[ "$STATUS" = "200" ] || { echo "FAIL: models"; exit 1; }

# Chat
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation","messages":[{"role":"user","content":"test"}]}')
[ "$STATUS" = "200" ] || { echo "FAIL: chat"; exit 1; }

echo "All proxy integration tests passed."
```

## Troubleshooting Tests

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: modelmesh` | Install: `pip install -e ".[yaml,dev]"` |
| `No providers detected` | Set at least one API key env var |
| TypeScript test imports fail | Run `npm install` in `src/typescript/` |
| Docker tests fail | Install Docker Desktop and ensure `docker` is in PATH |
| Proxy tests connection refused | Start proxy first: `docker compose up --build -d` |
