---
layout: default
title: "Proxy Guide"
---

# Proxy Guide

**Deploy ModelMesh as an OpenAI-compatible HTTP proxy.** The proxy exposes a standard OpenAI REST API on a configurable port. Internally it leverages all ModelMesh capabilities: multi-provider routing, automatic failover, pool strategies, budget controls, and free-tier aggregation. Any OpenAI SDK client, `curl`, or plain `fetch()` call can talk to the proxy without modification.

---

## Overview

```
Browser / SDK / curl
        |
        v  (OpenAI REST API)
  +-----------+
  |   Proxy   |  port 8080 (default)
  +-----------+
        |
        v  (ModelMesh routing)
  +-----------+     +-----------+     +----------+
  |  Router   | --> |   Pool    | --> |  Model   | --> Provider API
  +-----------+     +-----------+     +----------+
```

The proxy translates incoming requests to ModelMesh routing calls. When the client sends `model: "text-generation"`, ModelMesh resolves the pool, picks the best active model using the configured rotation strategy, retries with backoff on failure, and rotates to the next provider when one is down or rate-limited.

---

## Quick Start

### 1. Install

**Python (pip):**
```bash
pip install modelmesh-lite[yaml]
```

**From source:**
```bash
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh
pip install -e ".[yaml]"
```

### 2. Set API Keys

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
```

### 3. Start the Proxy (Auto-detect Mode)

With no config file, the proxy auto-detects providers from environment variables:

```bash
python -m modelmesh.proxy
```

The proxy starts on `http://localhost:8080` and creates a default `chat-completion` pool from all detected providers.

### 4. Test

```bash
# List available models (pool IDs)
curl http://localhost:8080/v1/models

# Send a chat completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chat-completion",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## Configuration

For full control over providers, models, pools, and strategies, use a YAML configuration file.

### Minimal Configuration

```yaml
# modelmesh.yaml
secrets:
  store: modelmesh.env.v1        # Read API keys from environment variables

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}

models:
  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion

pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: stick-until-failure
```

### Multi-Provider Configuration

```yaml
# modelmesh.yaml
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00

  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}
    budget:
      daily_limit: 5.00

  groq.api.v1:
    api_key: ${secrets:GROQ_API_KEY}

models:
  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      structured_output: true
      json_mode: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  claude-3-5-haiku:
    provider: anthropic.claude.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 200000
      max_output_tokens: 8192

  llama-3.3-70b:
    provider: groq.api.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 131072
      max_output_tokens: 32768

pools:
  text-generation:
    strategy: modelmesh.stick-until-failure.v1
    capability: generation.text-generation
```

Start with config:
```bash
python -m modelmesh.proxy --config modelmesh.yaml
```

### Configuration Sections

| Section | Purpose | Reference |
|---------|---------|-----------|
| `secrets` | Secret store backend (env vars, dotenv, cloud vaults) | [SystemConfiguration](../SystemConfiguration.html#secrets) |
| `providers` | Provider registration, API keys, budgets, rate limits | [SystemConfiguration](../SystemConfiguration.html#providers) |
| `models` | Model definitions with capabilities, features, constraints | [SystemConfiguration](../SystemConfiguration.html#models) |
| `pools` | Capability pools with rotation strategies | [SystemConfiguration](../SystemConfiguration.html#pools) |

### Available Providers

| Connector ID | Provider | Capabilities |
|---|---|---|
| `openai.llm.v1` | OpenAI | Chat, embeddings, audio |
| `anthropic.claude.v1` | Anthropic | Chat |
| `groq.api.v1` | Groq | Chat (fast inference) |
| `google.gemini.v1` | Google Gemini | Chat |
| `deepseek.api.v1` | DeepSeek | Chat |
| `mistral.api.v1` | Mistral | Chat, embeddings |
| `together.api.v1` | Together AI | Chat |
| `openrouter.api.v1` | OpenRouter | Chat (multi-model gateway) |
| `xai.api.v1` | xAI (Grok) | Chat |
| `cohere.api.v1` | Cohere | Chat, embeddings |

See [ConnectorCatalogue](../ConnectorCatalogue.html) for all connectors and config schemas.

### Rotation Strategies

| Strategy | Connector ID | Behaviour |
|---|---|---|
| Stick-until-failure | `modelmesh.stick-until-failure.v1` | Use one model until it fails, then rotate |
| Round-robin | `modelmesh.round-robin.v1` | Distribute requests evenly |
| Cost-first | `modelmesh.cost-first.v1` | Prefer cheapest model |
| Latency-first | `modelmesh.latency-first.v1` | Prefer fastest model |
| Random | `modelmesh.random.v1` | Random selection |
| Priority | `modelmesh.priority.v1` | Explicit priority ordering |
| Weighted | `modelmesh.weighted.v1` | Weighted random distribution |
| Quota-aware | `modelmesh.quota-aware.v1` | Prefer models with remaining quota |

### Secret Stores

| Store | Connector ID | Source |
|---|---|---|
| Environment variables | `modelmesh.env.v1` | `process.env` / `os.environ` |
| Dotenv file | `modelmesh.dotenv.v1` | `.env` file |
| AWS Secrets Manager | `aws.secrets-manager.v1` | AWS cloud |
| Google Secret Manager | `google.secret-manager.v1` | GCP cloud |
| Azure Key Vault | `microsoft.key-vault.v1` | Azure cloud |
| 1Password Connect | `1password.connect.v1` | 1Password vault |

---

## CLI Reference

```bash
python -m modelmesh.proxy [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | *(auto-detect)* | Path to YAML configuration file |
| `--host HOST` | `0.0.0.0` | Bind address |
| `--port PORT` | `8080` | Listen port |
| `--token TOKEN` | *(none)* | Bearer token for authentication |
| `--log-level LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

**Examples:**

```bash
# Auto-detect providers from env vars
python -m modelmesh.proxy

# Custom config, port, and auth token
python -m modelmesh.proxy --config modelmesh.yaml --port 9090 --token my-secret

# Debug logging
python -m modelmesh.proxy --config modelmesh.yaml --log-level DEBUG
```

---

## REST API Endpoints

All endpoints follow the OpenAI REST API specification.

### GET /v1/models

List available models (pool IDs exposed as virtual model names).

```bash
curl http://localhost:8080/v1/models
```

Response:
```json
{
  "object": "list",
  "data": [
    { "id": "text-generation", "object": "model", "created": 1710000000, "owned_by": "modelmesh" }
  ]
}
```

### POST /v1/chat/completions

Send a chat completion request. Use the pool ID as the `model` parameter.

**Non-streaming:**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-generation",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is ModelMesh?"}
    ],
    "temperature": 0.7,
    "max_tokens": 512
  }'
```

**Streaming:**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-generation",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

Streaming responses use Server-Sent Events (SSE) with chunked transfer encoding. Each chunk is a `data: {json}\n\n` line, terminated by `data: [DONE]`.

### POST /v1/embeddings

```bash
curl -X POST http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "embeddings", "input": "Hello world"}'
```

### POST /v1/audio/speech

```bash
curl -X POST http://localhost:8080/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts", "input": "Hello world"}'
```

### POST /v1/audio/transcriptions

```bash
curl -X POST http://localhost:8080/v1/audio/transcriptions \
  -H "Content-Type: application/json" \
  -d '{"model": "stt", "text": "audio data..."}'
```

### GET /health

Server health and status.

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "running": true,
  "host": "0.0.0.0",
  "port": 8080,
  "uptime_seconds": 120.5,
  "active_connections": 0,
  "total_requests": 42
}
```

### Authentication

When the proxy is started with `--token`, all requests must include a bearer token:

```bash
curl -H "Authorization: Bearer my-secret" http://localhost:8080/v1/models
```

### CORS

The proxy includes full CORS support (`Access-Control-Allow-Origin: *`) for browser access. No additional CORS proxy is needed.

---

## Docker Deployment

### Prerequisites

- Docker Engine 20.10+
- Docker Compose v2+

### Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.12-slim image with ModelMesh + PyYAML |
| `docker-compose.yaml` | Service definition with port mapping and config mount |
| `modelmesh.yaml` | Pool and provider configuration |
| `.env` | API keys (gitignored, never committed) |

### Build and Run

**Option A: Pull pre-built image from GHCR (fastest):**

```bash
docker pull ghcr.io/apartsinprojects/modelmesh:latest

# Run with environment variables
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="sk-..." \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  ghcr.io/apartsinprojects/modelmesh:latest \
  --host 0.0.0.0 --port 8080

# Or run with config file and env file
docker run -p 8080:8080 \
  --env-file .env \
  -v ./modelmesh.yaml:/app/modelmesh.yaml:ro \
  ghcr.io/apartsinprojects/modelmesh:latest \
  --config /app/modelmesh.yaml --host 0.0.0.0 --port 8080
```

**Option B: Docker Compose (recommended for development):**

```bash
# 1. Create .env with your API keys
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
EOF

# 2. Build and start
docker compose up --build

# 3. Or run in background
docker compose up --build -d

# 4. View logs
docker compose logs -f

# 5. Stop
docker compose down
```

**Option C: Build Docker image locally:**

```bash
# Build
docker build -t modelmesh-proxy .

# Run
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="sk-..." \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -v ./modelmesh.yaml:/app/modelmesh.yaml:ro \
  modelmesh-proxy \
  --config /app/modelmesh.yaml --host 0.0.0.0 --port 8080
```

### Using Automation Scripts

```bash
# Build + run (interactive, Ctrl+C to stop)
./scripts/proxy-up.sh

# Build + run in background
./scripts/proxy-up.sh --detach

# Stop
./scripts/proxy-down.sh

# Run smoke tests against running proxy
./scripts/proxy-test.sh

# Full cycle: build, start, test, stop
./scripts/proxy-test.sh --full
```

### Verify

```bash
# Health check
curl http://localhost:8080/health

# List models
curl http://localhost:8080/v1/models

# Chat completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation","messages":[{"role":"user","content":"Hi"}]}'
```

### Docker Compose Configuration

```yaml
# docker-compose.yaml
services:
  modelmesh-proxy:
    build: .
    ports:
      - "8080:8080"
    env_file: .env
    volumes:
      - ./modelmesh.yaml:/app/modelmesh.yaml:ro
    command: ["--config", "/app/modelmesh.yaml", "--host", "0.0.0.0", "--port", "8080"]
```

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY src/python/ ./
COPY pyproject.toml ./
RUN pip install . && pip install pyyaml>=6.0
EXPOSE 8080
ENTRYPOINT ["python", "-m", "modelmesh.proxy"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
```

---

## Browser Usage

The proxy includes CORS support, so you can call it directly from browser JavaScript using `fetch()`.

### Vanilla JS Example

A complete browser test page is provided at [`samples/proxy-test/index.html`](https://github.com/ApartsinProjects/ModelMesh/tree/master/samples/proxy-test/index.html). Open it directly in a browser (no build step needed).

**Non-streaming request:**

```javascript
const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'text-generation',
    messages: [{ role: 'user', content: 'Hello!' }],
  }),
});
const data = await response.json();
console.log(data.choices[0].message.content);
```

**Streaming request:**

```javascript
const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'text-generation',
    messages: [{ role: 'user', content: 'Hello!' }],
    stream: true,
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });

  const lines = buffer.split('\n');
  buffer = lines.pop();

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed === 'data: [DONE]') break;
    if (!trimmed.startsWith('data: ')) continue;
    const chunk = JSON.parse(trimmed.slice(6));
    const token = chunk.choices?.[0]?.delta?.content;
    if (token) process.stdout.write(token); // or append to DOM
  }
}
```

### OpenAI SDK Compatibility

Any OpenAI SDK client works with the proxy by changing the base URL:

**Python (openai SDK):**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed",  # or your proxy token
)

response = client.chat.completions.create(
    model="text-generation",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

**TypeScript (openai SDK):**
```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:8080/v1',
  apiKey: 'not-needed',
});

const response = await client.chat.completions.create({
  model: 'text-generation',
  messages: [{ role: 'user', content: 'Hello!' }],
});
console.log(response.choices[0].message.content);
```

---

## Programmatic Usage

You can also embed the proxy server in your own Python application:

```python
from modelmesh.proxy.server import ProxyServer

# Start in background
server = ProxyServer(
    config="modelmesh.yaml",
    host="0.0.0.0",
    port=8080,
    token="my-secret",
)
server.start(block=False)

# Check status
print(server.get_status())

# Stop
server.stop()
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: yaml` | PyYAML not installed | `pip install pyyaml` or use `pip install modelmesh-lite[yaml]` |
| `Connection refused` | Proxy not running or wrong port | Check `docker compose logs` or start with `--log-level DEBUG` |
| `502 Routing error` | All providers failed | Check API keys in `.env`, verify provider connectivity |
| `401 Invalid token` | Bearer token mismatch | Pass correct `--token` or remove auth requirement |
| CORS error in browser | Proxy not reachable | Verify proxy URL and that the proxy is running |
| `Empty request body` | Missing Content-Type header | Add `-H "Content-Type: application/json"` to curl |
| Streaming not working | Client not reading SSE | Use `ReadableStream` API, not `response.json()` |
