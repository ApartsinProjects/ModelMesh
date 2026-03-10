# ModelMesh Integration Guide for AI Coding Agents

**Audience:** AI coding agents (Claude Code, Cursor, Copilot, Aider, etc.) that need to install, configure, and integrate ModelMesh into a user's project.

**What is ModelMesh?** A capability-driven AI model routing library. One integration point for multiple AI providers (OpenAI, Anthropic, Gemini, Groq, DeepSeek, etc.) with automatic failover, free-tier aggregation, and OpenAI SDK compatibility. Available as Python package, TypeScript/npm package, or Docker proxy.

---

## Quick Decision Tree

Ask the user these questions (in order) to determine the integration path:

1. **What language/runtime?**
   - Python backend → [Python Integration](#python-integration)
   - TypeScript/Node.js backend → [TypeScript Backend Integration](#typescript-backend-integration)
   - Browser/frontend → [TypeScript Browser Integration](#typescript-browser-integration)
   - Language-agnostic / HTTP API → [Docker Proxy Integration](#docker-proxy-integration)
   - Multiple / microservices → Docker Proxy (exposes OpenAI-compatible REST API)

2. **How much control?**
   - Zero-config (just works) → Layer 0: `create("chat-completion")`
   - Filter providers/models → Layer 1: `create("chat-completion", providers=["openai"])`
   - Full config (pools, budgets, strategies) → Layer 2: `create(config="modelmesh.yaml")`

3. **Which providers?**
   - The user must have at least one API key. Common: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`.

---

## Environment Variables

ModelMesh auto-detects providers from environment variables. At minimum, one key is needed:

| Variable | Provider | Free tier? |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI (GPT-4o, GPT-4o-mini) | No |
| `ANTHROPIC_API_KEY` | Anthropic (Claude Sonnet, Haiku) | No |
| `GROQ_API_KEY` | Groq (Llama 3.3, Mixtral) | Yes |
| `GOOGLE_API_KEY` | Google (Gemini 2.0 Flash) | Yes |
| `DEEPSEEK_API_KEY` | DeepSeek (DeepSeek-Chat) | Limited |
| `MISTRAL_API_KEY` | Mistral (Mistral Large) | No |
| `TOGETHER_API_KEY` | Together AI (open-source models) | No |
| `OPENROUTER_API_KEY` | OpenRouter (multi-provider gateway) | No |
| `XAI_API_KEY` | xAI (Grok) | No |
| `COHERE_API_KEY` | Cohere (Command-R) | Yes |

**Best free-tier combo:** Set `GROQ_API_KEY` + `GOOGLE_API_KEY` for zero-cost chat completion with automatic failover.

---

## Python Integration

### Install

```bash
pip install modelmesh-lite          # core (zero dependencies)
pip install modelmesh-lite[yaml]    # + YAML config support
pip install modelmesh-lite[full]    # + all optional extras
```

For development (editable install from source):
```bash
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh
pip install -e ".[yaml,dev]"
```

### Layer 0 — Zero Config (Recommended Starting Point)

```python
import modelmesh

# Auto-detects all providers from env vars, creates a pool for the capability
client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

**Key behavior:** The `model` parameter is a *virtual model name* that maps to a capability pool. ModelMesh picks the best active provider, handles retries and failover automatically.

### Layer 1 — Filtered Auto-Detection

```python
client = modelmesh.create(
    "chat-completion",
    providers=["openai", "anthropic"],   # only use these providers
    strategy="cost-first",               # prefer cheapest model
)
```

### Layer 2 — Full YAML Configuration

```python
client = modelmesh.create(config="modelmesh.yaml")
```

See [YAML Configuration Reference](#yaml-configuration) below.

### Streaming

```python
stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
```

### Type Checking

ModelMesh ships with a `py.typed` marker (PEP 561) for full type checking support with mypy/pyright.

---

## TypeScript Backend Integration

### Install

```bash
npm install @nistrapa/modelmesh-core
```

For development from source:
```bash
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh/src/typescript
npm install
npm run build    # compiles to dist/
npm test         # run tests
```

### Layer 0 — Zero Config

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

const response = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Hello!' }],
});
console.log(response.choices[0].message.content);
```

### Layer 1 — Filtered

```typescript
const client = create('chat-completion', {
  providers: ['openai', 'anthropic'],
  strategy: 'cost-first',
});
```

### Layer 2 — Full Config

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create({ config: 'modelmesh.json' });
```

### Package Exports

```typescript
import { create, ModelMesh, MeshClient, MeshConfig } from '@nistrapa/modelmesh-core';

// Browser-specific provider base class (for frontend apps)
import { BrowserBaseProvider } from '@nistrapa/modelmesh-core/browser';
```

---

## TypeScript Browser Integration

For frontend applications that call AI APIs directly from the browser (through a CORS proxy or ModelMesh Docker proxy).

### Install

Same npm package:
```bash
npm install @nistrapa/modelmesh-core
```

### Usage with ModelMesh Proxy

The simplest browser approach: run the Docker proxy and call it via fetch():

```typescript
// Using the proxy running on localhost:8080
const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'text-generation',
    messages: [{ role: 'user', content: 'Hello!' }],
    stream: false,
  }),
});
const data = await response.json();
console.log(data.choices[0].message.content);
```

### Streaming from Browser

```typescript
const response = await fetch('http://localhost:8080/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'text-generation',
    messages: [{ role: 'user', content: 'Hello!' }],
    stream: true,
  }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  for (const line of text.split('\n')) {
    if (line.startsWith('data: ') && line !== 'data: [DONE]') {
      const chunk = JSON.parse(line.slice(6));
      const content = chunk.choices?.[0]?.delta?.content;
      if (content) process.stdout.write(content);
    }
  }
}
```

### BrowserBaseProvider (Advanced)

For building custom browser-compatible AI providers:

```typescript
import { BrowserBaseProvider, createBrowserProviderConfig } from '@nistrapa/modelmesh-core/browser';

class MyProvider extends BrowserBaseProvider {
  protected _getCompletionEndpoint(): string {
    return `${this._config.baseUrl}/v1/chat/completions`;
  }
}
```

---

## Docker Proxy Integration

The Docker proxy exposes the full OpenAI REST API. Any language/framework that can call HTTP APIs can use it.

### Prerequisites

- Docker and Docker Compose installed
- At least one API key

### Install

**Option A — Pre-built image (fastest):**
```bash
docker pull ghcr.io/apartsinprojects/modelmesh:latest
```

**Option B — Build from source:**
```bash
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh
```

### Setup

```bash
# Create .env with your API keys
cp .env.example .env
# Edit .env and add your keys: OPENAI_API_KEY=sk-..., etc.

# Start the proxy (from source)
docker compose up --build

# Or run the pre-built image directly
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="sk-..." \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  ghcr.io/apartsinprojects/modelmesh:latest \
  --host 0.0.0.0 --port 8080
```

The proxy runs on `http://localhost:8080`.

### Test

```bash
# List available models/pools
curl http://localhost:8080/v1/models

# Chat completion
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation","messages":[{"role":"user","content":"Hello!"}]}'

# Health check
curl http://localhost:8080/health
```

### Using from Any Language

Since the proxy speaks the OpenAI API, you can use any OpenAI SDK:

**Python (openai package):**
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8080/v1", api_key="unused")
response = client.chat.completions.create(
    model="text-generation",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

**TypeScript (openai package):**
```typescript
import OpenAI from 'openai';
const client = new OpenAI({ baseURL: 'http://localhost:8080/v1', apiKey: 'unused' });
const response = await client.chat.completions.create({
  model: 'text-generation',
  messages: [{ role: 'user', content: 'Hello!' }],
});
```

**curl / HTTP / any language:**
The proxy is a standard REST API. Use whatever HTTP client your language provides.

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/models` | List available pools and models |
| `POST` | `/v1/chat/completions` | Chat completion (streaming + non-streaming) |
| `POST` | `/v1/embeddings` | Text embeddings |
| `POST` | `/v1/audio/speech` | Text-to-speech |
| `POST` | `/v1/audio/transcriptions` | Speech-to-text |
| `GET` | `/health` | Health check |

---

## YAML Configuration

For Layer 2 (full control), create a `modelmesh.yaml`:

```yaml
secrets:
  store: modelmesh.env.v1          # read API keys from env vars

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00            # optional cost cap

  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}

models:
  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  claude-3-5-haiku:
    provider: anthropic.claude.v1
    capabilities:
      - generation.text-generation.chat-completion
    constraints:
      context_window: 200000
      max_output_tokens: 8192

pools:
  text-generation:
    strategy: modelmesh.stick-until-failure.v1
    capability: generation.text-generation
```

### Available Strategies

| Strategy | Behavior |
|---|---|
| `modelmesh.stick-until-failure.v1` | Stay with current model until it fails, then rotate |
| `modelmesh.round-robin.v1` | Cycle through models evenly |
| `modelmesh.cost-first.v1` | Prefer cheapest model |
| `modelmesh.latency-first.v1` | Prefer fastest model |
| `modelmesh.priority-selection.v1` | Follow priority order, failover on error |
| `modelmesh.rate-limit-aware.v1` | Route around rate limits |
| `modelmesh.load-balanced.v1` | Distribute by weight |
| `modelmesh.session-stickiness.v1` | Keep sessions on same model |

### Available Secret Stores

| Store | Config Key |
|---|---|
| `modelmesh.env.v1` | Read from environment variables |
| `modelmesh.dotenv.v1` | Read from .env file |
| `aws.secrets-manager.v1` | AWS Secrets Manager |
| `google.secret-manager.v1` | Google Cloud Secret Manager |
| `microsoft.key-vault.v1` | Azure Key Vault |
| `1password.connect.v1` | 1Password Connect |

### Capability Paths

| Short Name | Full Path |
|---|---|
| `chat-completion` | `generation.text-generation.chat-completion` |
| `text-generation` | `generation.text-generation` |
| `text-embeddings` | `representation.embeddings.text-embeddings` |
| `text-to-speech` | `generation.audio.text-to-speech` |
| `speech-to-text` | `understanding.audio.speech-to-text` |
| `text-to-image` | `generation.image.text-to-image` |
| `code-generation` | `generation.text-generation.code-generation` |

---

## Integration Patterns

### Pattern 1: Drop-In Replacement for OpenAI SDK

Replace the OpenAI client with ModelMesh — same API, automatic failover:

**Before:**
```python
from openai import OpenAI
client = OpenAI()
```

**After:**
```python
import modelmesh
client = modelmesh.create("chat-completion")
```

All `client.chat.completions.create()` calls work identically.

### Pattern 2: Multi-Capability Application

An app needing chat + embeddings + TTS:

```python
import modelmesh

chat_client = modelmesh.create("chat-completion")
embed_client = modelmesh.create("text-embeddings")
tts_client = modelmesh.create("text-to-speech")
```

### Pattern 3: Backend Proxy for Frontend

Run Docker proxy, have the frontend call it:

```
[Browser] --fetch()--> [ModelMesh Proxy :8080] ---> [OpenAI/Anthropic/Groq]
```

### Pattern 4: Microservices with Shared Proxy

Multiple services share one proxy instance:

```
[Service A] -\
[Service B] --> [ModelMesh Proxy :8080] --> [Providers]
[Service C] -/
```

---

## Project Structure

```
ModelMesh/
  src/
    python/modelmesh/        # Python package source
    typescript/src/          # TypeScript package source
  tests/                     # Python test suite (855 tests)
  src/typescript/tests/      # TypeScript test suite (511 tests)
  docs/                      # Full documentation
  samples/                   # Example code (quickstart, system, cdk, proxy)
  scripts/                   # Automation scripts
  Dockerfile                 # Docker image definition
  docker-compose.yaml        # Docker Compose config
  pyproject.toml             # Python package metadata
  src/typescript/package.json # TypeScript package metadata
  modelmesh.yaml             # Example proxy configuration
  .env.example               # API key template
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No providers detected` | No API key env vars set | Set at least one: `export OPENAI_API_KEY=sk-...` |
| `ModuleNotFoundError: yaml` | PyYAML not installed | `pip install modelmesh-lite[yaml]` |
| `Connection refused :8080` | Docker proxy not running | `docker compose up --build` |
| `CORS error in browser` | Proxy CORS not enabled | Proxy enables CORS by default; check origin |
| `401 Unauthorized` | Bearer token required | Set `--token` on proxy CLI, send `Authorization: Bearer <token>` |
| Import errors in TypeScript | Package not built | Run `npm run build` in `src/typescript/` |

---

## Testing the Integration

After integrating, verify with:

```python
# Python
import modelmesh
client = modelmesh.create("chat-completion")
print(client.describe())   # shows detected providers and pool
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Say 'ModelMesh works!'"}],
)
assert "works" in response.choices[0].message.content.lower()
```

```typescript
// TypeScript
import { create } from '@nistrapa/modelmesh-core';
const client = create('chat-completion');
const response = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: "Say 'ModelMesh works!'" }],
});
console.assert(response.choices[0].message.content.includes('works'));
```

```bash
# Docker proxy
curl -s http://localhost:8080/health | grep -q '"status":"ok"'
curl -s http://localhost:8080/v1/models | grep -q 'text-generation'
```

---

## Links

- **Repository:** https://github.com/ApartsinProjects/ModelMesh
- **Documentation:** https://apartsinprojects.github.io/ModelMesh/
- **System Concept:** [docs/SystemConcept.md](SystemConcept.md)
- **Configuration Reference:** [docs/SystemConfiguration.md](SystemConfiguration.md)
- **Connector Catalogue:** [docs/ConnectorCatalogue.md](ConnectorCatalogue.md)
- **Proxy Guide:** [docs/guides/ProxyGuide.md](guides/ProxyGuide.md)
- **CDK Overview:** [docs/cdk/Overview.md](cdk/Overview.md)
