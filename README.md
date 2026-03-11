<p align="center">
  <img src="docs/assets/banner.png?v=2" alt="ModelMesh" width="100%">
</p>

<p align="center">
  <strong>One integration point for all your AI providers.</strong><br>
  Automatic failover, free-tier aggregation, and capability-based routing.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/typescript-5.0%2B-blue" alt="TypeScript 5.0+">
  <img src="https://img.shields.io/badge/docker-supported-2496ED" alt="Docker">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/ApartsinProjects/ModelMesh/actions"><img src="https://img.shields.io/badge/tests-1%2C879%20passed-brightgreen" alt="Tests"></a>
  <a href="https://apartsinprojects.github.io/ModelMesh/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue" alt="Documentation"></a>
</p>

---

Your application requests a **capability** (e.g. "chat completion"). ModelMesh picks the best available provider, rotates on failure, and chains free quotas across providers -- all behind a standard OpenAI SDK interface.

## Install

**Python:**
```bash
pip install modelmesh-lite                # core (zero dependencies)
pip install modelmesh-lite[yaml]          # + YAML config support
```

**TypeScript / Node.js:**
```bash
npm install @nistrapa/modelmesh-core
```

**Docker Proxy (any language):**
```bash
# Option A: Pull pre-built image from GitHub Container Registry
docker pull ghcr.io/apartsinprojects/modelmesh:latest

# Option B: Build from source
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh
cp .env.example .env   # add your API keys
docker compose up --build
# Proxy at http://localhost:8080 — speaks the OpenAI REST API
```

## Quick Start

Set an API key and go:

```bash
export OPENAI_API_KEY="sk-..."
```

### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",          # virtual model name = capability pool
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";

const client = create("chat-completion");

const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);
```

## How It Works

```
client.chat.completions.create(model="chat-completion", ...)
       |
       v
  +-----------+     +-----------+     +----------+
  |  Router   | --> |   Pool    | --> |  Model   | --> Provider API
  +-----------+     +-----------+     +----------+
  Resolves the       Groups models     Selects best     Sends request,
  capability to      that can do       active model     handles retry
  a pool             the task          (rotation policy) and failover
```

**`"chat-completion"`** resolves to a pool containing all models that support chat. The pool's **rotation policy** picks the best active model. If it fails, the router retries with backoff, then rotates to the next model. When a provider's free quota runs out, rotation automatically moves to the next provider.

## Multi-Provider Failover

Add more API keys -- ModelMesh chains them automatically:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AI..."
```

```python
client = modelmesh.create("chat-completion")

# Inspect the providers behind the virtual model
print(client.describe())
# Pool "chat-completion" (strategy: stick-until-failure)
#   capability: generation.text-generation.chat-completion
#   → openai.gpt-4o [openai.llm.v1] (active)
#     openai.gpt-4o-mini [openai.llm.v1] (active)
#     anthropic.claude-sonnet-4 [anthropic.claude.v1] (active)
#     google.gemini-2.0-flash [google.gemini.v1] (active)
```

Same `client.chat.completions.create()` call -- but now if OpenAI is down or its quota is exhausted, the request routes to Anthropic, then Gemini.

## YAML Configuration

For full control, use a configuration file:

```yaml
# modelmesh.yaml
providers:
  openai.llm.v1:
    connector: openai.llm.v1
    config:
      api_key: "${secrets:OPENAI_API_KEY}"

  anthropic.claude.v1:
    connector: anthropic.claude.v1
    config:
      api_key: "${secrets:ANTHROPIC_API_KEY}"

models:
  openai.gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion

  anthropic.claude-sonnet-4:
    provider: anthropic.claude.v1
    capabilities:
      - generation.text-generation.chat-completion

pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: stick-until-failure
```

```python
client = modelmesh.create(config="modelmesh.yaml")
```

## Why ModelMesh

Ten reasons to add ModelMesh to your next project.

| # | Value | Feature | How It Delivers |
|---|---|---|---|
| **1** | **Integrate in two minutes, scale the configuration as you grow** | **[Progressive Configuration](docs/guides/FAQ.md#1-how-quickly-can-i-integrate-modelmesh-into-my-project)** | **Env vars** for instant start. **YAML** for providers, pools, strategies, budgets, secrets. **Programmatic** for dynamic setups. All three compose seamlessly |
| **2** | **One familiar API across every provider you will ever use** | **[Uniform OpenAI-Compatible API](docs/guides/FAQ.md#2-do-i-need-to-learn-a-new-api)** | Same `client.chat.completions.create()` for OpenAI, Anthropic, Gemini, DeepSeek, Mistral, Ollama, or custom models. Chat, embeddings, TTS, STT, image generation. Swap providers in config, never in code |
| **3** | **Chain free tiers so you never hit a quota wall** | **[Free-Tier Aggregation](docs/guides/FAQ.md#3-how-does-free-tier-aggregation-work)** | Set free API keys, call `create("chat")`. The library detects providers, pools them by capability, and rotates silently when a quota exhausts. Your code sees one provider; ModelMesh manages the rotation |
| **4** | **Provider goes down, your app stays up** | **[Resilient Routing](docs/guides/FAQ.md#4-what-happens-when-a-provider-goes-down)** | Multiple rotation strategies: cost-first, latency-first, round-robin, sticky, rate-limit-aware. On failure the router deactivates the model, selects the next candidate, and retries within the same request |
| **5** | **Request capabilities, not model names** | **[Capability Discovery](docs/guides/FAQ.md#5-what-does-request-capabilities-not-model-names-mean)** | Ask for `"chat-completion"`, not `"gpt-4o"`. ModelMesh resolves to the best available model. New models appear, old ones deprecate, your code stays the same |
| **6** | **Spending caps enforced before the overage, not after** | **[Budget Enforcement](docs/guides/FAQ.md#6-how-do-i-prevent-surprise-ai-bills)** | Real-time cost tracking per model and provider. Set daily or monthly limits in config. `BudgetExceededError` fires before the breaching request |
| **7** | **One library for Python backend, TypeScript frontend, Docker proxy** | **[Full-Stack Deployment](docs/guides/FAQ.md#7-can-i-use-modelmesh-with-my-existing-stack)** | `pip install`, `npm install`, or `docker run`. Each exposes the same API with zero core dependencies. One config file drives all deployment modes |
| **8** | **Test AI code like regular code** | **[Mock Client and Testing](docs/guides/FAQ.md#8-how-do-i-test-ai-code-without-burning-api-credits)** | `mock_client(responses=[...])` returns an identical API with zero network calls and millisecond execution. Typed exceptions carry structured metadata. `client.explain()` dry-runs routing decisions |
| **9** | **Production-grade observability without extra plumbing** | **[Observability Connectors](docs/guides/FAQ.md#9-what-observability-does-modelmesh-provide)** | Pre-built sinks for console, file, JSON-log, Prometheus, and webhooks. Structured traces across routing, failover, and budget events. Plug in custom callbacks for existing dashboards |
| **10** | **When pre-built doesn't fit, extend without forking** | **[CDK](docs/guides/FAQ.md#10-what-if-the-pre-built-connectors-dont-cover-my-use-case)** | Base classes for providers, rotation policies, secret stores, storage backends, and observability sinks. Inherit, override what you need, ship as a reusable package |

## Key Features

| Feature | Description |
|---|---|
| **OpenAI-compatible** | Drop-in replacement for any OpenAI SDK client |
| **Multi-provider routing** | OpenAI, Anthropic, Gemini, Groq, and more |
| **Automatic failover** | Retry with backoff, then rotate to next model |
| **Free-tier aggregation** | Chain quotas across providers |
| **Capability-based pools** | Request tasks, not specific providers |
| **8 rotation strategies** | Stick-until-failure, cost-first, latency-first, round-robin, and more |
| **Pluggable connectors** | Extend any integration point with the CDK |
| **Zero dependencies** | Core library has no external dependencies |

## Documentation

| Document | Description |
|---|---|
| **[System Concept](docs/SystemConcept.md)** | Architecture, design, and full feature overview |
| **[Model Capabilities](docs/ModelCapabilities.md)** | Capability hierarchy tree and predefined pools |
| **[System Configuration](docs/SystemConfiguration.md)** | Full YAML configuration reference |
| **[Connector Catalogue](docs/ConnectorCatalogue.md)** | All pre-shipped connectors with config schemas |
| **[Connector Interfaces](docs/ConnectorInterfaces.md)** | Interface definitions for all connector types |
| **[System Services](docs/SystemServices.md)** | Runtime objects: Router, Pool, Model, State |
| **[Proxy Guide](docs/guides/ProxyGuide.md)** | Deploy as OpenAI-compatible proxy: Docker, CLI, config, browser access |
| **[AI Agent Integration](docs/ForAIAgent.md)** | Guide for AI coding agents (Claude Code, Cursor, etc.) to integrate ModelMesh |

### CDK (Connector Development Kit)

| Document | Description |
|---|---|
| **[CDK Overview](docs/cdk/Overview.md)** | Architecture and class hierarchy |
| **[Base Classes](docs/cdk/BaseClasses.md)** | Reference for all CDK base classes |
| **[Developer Guide](docs/cdk/DeveloperGuide.md)** | Tutorials: build your own connectors |
| **[Convenience Layer](docs/cdk/ConvenienceLayer.md)** | QuickProvider and zero-config setup |
| **[Mixins](docs/cdk/Mixins.md)** | Cache, metrics, rate limiter, HTTP client |

### Samples

| Collection | Description |
|---|---|
| **[Quickstart](samples/quickstart/)** | 12 progressive examples in Python and TypeScript |
| **[System Integration](samples/system/)** | Multi-provider, streaming, embeddings, cost optimization |
| **[CDK Tutorials](samples/cdk/)** | Build providers, rotation policies, and more |
| **[Custom Connectors](samples/connectors/)** | Full custom connector examples for all 6 types |
| **[Proxy Test](samples/proxy-test/)** | Vanilla JS browser test page for the OpenAI proxy |

## Development

```bash
# Clone the repository
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh

# Run Python tests (1,166 tests)
pip install pytest
cd src/python && python -m pytest ../../tests/ -v

# Run TypeScript tests (713 tests)
cd src/typescript && npm install && npm test

# Or use the automation script
./scripts/test-all.sh
```

## Docker

```bash
# Pull pre-built image from GitHub Container Registry
docker pull ghcr.io/apartsinprojects/modelmesh:latest

# Run with your API keys
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="sk-..." \
  ghcr.io/apartsinprojects/modelmesh:latest

# Or build from source with Docker Compose
cp .env.example .env    # then add your API keys
docker compose up --build

# Test the running proxy
curl http://localhost:8080/v1/models
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"text-generation","messages":[{"role":"user","content":"Hello!"}]}'
```

See the **[Proxy Guide](docs/guides/ProxyGuide.md)** for full configuration, CLI reference, and browser access.

## Scripts

| Script | Description |
|---|---|
| `scripts/proxy-up.sh` | Build and start the Docker proxy |
| `scripts/proxy-down.sh` | Stop the Docker proxy |
| `scripts/proxy-test.sh` | Smoke-test a running proxy |
| `scripts/docker-build.sh` | Build the Docker image |
| `scripts/install-python.sh` | Install Python package (dev or prod) |
| `scripts/install-typescript.sh` | Install TypeScript package |
| `scripts/test-all.sh` | Run full test suite (Python + TypeScript) |

## License

[MIT](LICENSE)

---

<sub>Created by [Sasha Apartsin](https://www.apartsin.com)</sub>
