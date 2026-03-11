---
layout: default
title: ModelMesh Lite
---

<p align="center">
  <img src="assets/banner.png?v=2" alt="ModelMesh" width="100%">
</p>

<p align="center">
  <strong>One integration point for all your AI providers.</strong><br>
  Automatic failover, free-tier aggregation, and capability-based routing.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/typescript-5.0%2B-blue" alt="TypeScript 5.0+">
  <img src="https://img.shields.io/badge/docker-supported-2496ED" alt="Docker">
  <a href="https://github.com/ApartsinProjects/ModelMesh/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/ApartsinProjects/ModelMesh/actions"><img src="https://img.shields.io/badge/tests-1%2C879%20passed-brightgreen" alt="Tests"></a>
  <a href="https://apartsinprojects.github.io/ModelMesh/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue" alt="Documentation"></a>
  <a href="guides/FAQ.html"><img src="https://img.shields.io/badge/FAQ-10%20questions-orange" alt="FAQ"></a>
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
| **1** | **Integrate in two minutes, scale the configuration as you grow** | **[Progressive Configuration](guides/FAQ.md#1-how-quickly-can-i-integrate-modelmesh-into-my-project)** | **Env vars** for instant start. **YAML** for providers, pools, strategies, budgets, secrets. **Programmatic** for dynamic setups. All three compose seamlessly |
| **2** | **One familiar API across every provider you will ever use** | **[Uniform OpenAI-Compatible API](guides/FAQ.md#2-do-i-need-to-learn-a-new-api)** | Same `client.chat.completions.create()` for OpenAI, Anthropic, Gemini, DeepSeek, Mistral, Ollama, or custom models. Chat, embeddings, TTS, STT, image generation. Swap providers in config, never in code |
| **3** | **Chain free tiers so you never hit a quota wall** | **[Free-Tier Aggregation](guides/FAQ.md#3-how-does-free-tier-aggregation-work)** | Set free API keys, call `create("chat")`. The library detects providers, pools them by capability, and rotates silently when a quota exhausts. Your code sees one provider; ModelMesh manages the rotation |
| **4** | **Provider goes down, your app stays up** | **[Resilient Routing](guides/FAQ.md#4-what-happens-when-a-provider-goes-down)** | Multiple rotation strategies: cost-first, latency-first, round-robin, sticky, rate-limit-aware. On failure the router deactivates the model, selects the next candidate, and retries within the same request |
| **5** | **Request capabilities, not model names** | **[Capability Discovery](guides/FAQ.md#5-what-does-request-capabilities-not-model-names-mean)** | Ask for `"chat-completion"`, not `"gpt-4o"`. ModelMesh resolves to the best available model. New models appear, old ones deprecate, your code stays the same |
| **6** | **Spending caps enforced before the overage, not after** | **[Budget Enforcement](guides/FAQ.md#6-how-do-i-prevent-surprise-ai-bills)** | Real-time cost tracking per model and provider. Set daily or monthly limits in config. `BudgetExceededError` fires before the breaching request |
| **7** | **One library for Python backend, TypeScript frontend, Docker proxy** | **[Full-Stack Deployment](guides/FAQ.md#7-can-i-use-modelmesh-with-my-existing-stack)** | `pip install`, `npm install`, or `docker run`. Each exposes the same API with zero core dependencies. One config file drives all deployment modes |
| **8** | **Test AI code like regular code** | **[Mock Client and Testing](guides/FAQ.md#8-how-do-i-test-ai-code-without-burning-api-credits)** | `mock_client(responses=[...])` returns an identical API with zero network calls and millisecond execution. Typed exceptions carry structured metadata. `client.explain()` dry-runs routing decisions |
| **9** | **Production-grade observability without extra plumbing** | **[Observability Connectors](guides/FAQ.md#9-what-observability-does-modelmesh-provide)** | Pre-built sinks for console, file, JSON-log, Prometheus, and webhooks. Structured traces across routing, failover, and budget events. Plug in custom callbacks for existing dashboards |
| **10** | **When pre-built doesn't fit, extend without forking** | **[CDK](guides/FAQ.md#10-what-if-the-pre-built-connectors-dont-cover-my-use-case)** | Base classes for providers, rotation policies, secret stores, storage backends, and observability sinks. Inherit, override what you need, ship as a reusable package |

## Documentation

### Getting Started

| Document | Description |
|---|---|
| **[FAQ](guides/FAQ.md)** | Ten questions developers ask before adopting, each with a working code tutorial |
| **[Developer Quick Start](guides/QuickStart.md)** | Get productive in 5 minutes: all features walkthrough with cheat sheet |

### Core Concepts

| Document | Description |
|---|---|
| **[System Concept](SystemConcept.md)** | Architecture, design, and full feature overview |
| **[Model Capabilities](ModelCapabilities.md)** | Capability hierarchy tree and predefined pools |
| **[System Configuration](SystemConfiguration.md)** | Full YAML configuration reference |
| **[Connector Catalogue](ConnectorCatalogue.md)** | All pre-shipped connectors with config schemas |

### Developer Guides

| Document | Description |
|---|---|
| **[Error Handling](guides/ErrorHandling.md)** | Exception hierarchy, catch patterns, retry guidance |
| **[Middleware](guides/Middleware.md)** | Write custom middleware: logging, transforms, caching, error fallbacks |
| **[Testing](guides/Testing.md)** | Unit testing with `mock_client()` — no API keys needed |
| **[Capabilities](guides/Capabilities.md)** | Discover, resolve, and search capability aliases |
| **[Audio (TTS/STT)](ConnectorInterfaces.md#audio)** | AudioRequest/AudioResponse types, `client.audio` namespace |

### Deployment

| Document | Description |
|---|---|
| **[Proxy Guide](guides/ProxyGuide.md)** | Deploy as OpenAI-compatible proxy: Docker, CLI, config, browser access |
| **[Browser Usage](guides/BrowserUsage.md)** | BrowserBaseProvider, CORS proxy setup, and browser-specific patterns |
| **[AI Agent Integration](ForAIAgent.md)** | Guide for AI coding agents (Claude Code, Cursor, etc.) to integrate ModelMesh |

### API Reference

| Document | Description |
|---|---|
| **[Connector Interfaces](ConnectorInterfaces.md)** | Interface definitions for all connector types |
| **[Provider](interfaces/Provider.md)** | Provider connector interface spec |
| **[Rotation Policy](interfaces/RotationPolicy.md)** | Rotation policy interface spec |
| **[Secret Store](interfaces/SecretStore.md)** | Secret store interface spec |
| **[Storage](interfaces/Storage.md)** | Storage backend interface spec |
| **[Observability](interfaces/Observability.md)** | Observability connector interface spec |
| **[Discovery](interfaces/Discovery.md)** | Discovery connector interface spec |

### Runtime Services

| Document | Description |
|---|---|
| **[Overview](system/Overview.md)** | Runtime architecture and object graph |
| **[System Services](SystemServices.md)** | Router, Pool, Model, and State runtime objects |
| **[Router](system/Router.md)** | Request routing and retry logic |
| **[Capability Pool](system/CapabilityPool.md)** | Pool lifecycle and model selection |
| **[State Manager](system/StateManager.md)** | State persistence and recovery |
| **[Event Emitter](system/EventEmitter.md)** | Event system for routing, failover, and budget events |

### Extending ModelMesh (CDK)

| Document | Description |
|---|---|
| **[CDK Overview](cdk/Overview.md)** | Architecture and class hierarchy |
| **[Base Classes](cdk/BaseClasses.md)** | Reference for all CDK base classes |
| **[Developer Guide](cdk/DeveloperGuide.md)** | Tutorials: build your own connectors |
| **[Convenience Layer](cdk/ConvenienceLayer.md)** | QuickProvider and zero-config setup |
| **[Mixins](cdk/Mixins.md)** | Cache, metrics, rate limiter, HTTP client |

### Samples

| Collection | Description |
|---|---|
| **[Quickstart](https://github.com/ApartsinProjects/ModelMesh/tree/master/samples/quickstart/)** | 12 progressive examples in Python and TypeScript |
| **[System Integration](https://github.com/ApartsinProjects/ModelMesh/tree/master/samples/system/)** | Multi-provider, streaming, embeddings, cost optimization |
| **[CDK Tutorials](https://github.com/ApartsinProjects/ModelMesh/tree/master/samples/cdk/)** | Build providers, rotation policies, and more |
| **[Custom Connectors](https://github.com/ApartsinProjects/ModelMesh/tree/master/samples/connectors/)** | Full custom connector examples for all 6 types |
| **[Proxy Test](https://github.com/ApartsinProjects/ModelMesh/tree/master/samples/proxy-test/)** | Vanilla JS browser test page for the OpenAI proxy |

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/ApartsinProjects/ModelMesh.git
cd ModelMesh

# Run tests
pip install pytest
cd src/python && python -m pytest ../../tests/ -v
```

## License

[MIT](https://github.com/ApartsinProjects/ModelMesh/blob/master/LICENSE)

---

<sub>Created by [Sasha Apartsin](https://www.apartsin.com)</sub>
