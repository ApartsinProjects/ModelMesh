<p align="center">
  <img src="docs/assets/banner.png?v=2" alt="ModelMesh" width="100%">
</p>

<p align="center">
  <strong>One integration point for all your AI providers.</strong><br>
  Automatic failover, free-tier aggregation, and capability-based routing.
</p>

<p align="center">
  <a href="https://pypi.org/project/modelmesh-lite/"><img src="https://img.shields.io/pypi/v/modelmesh-lite?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/modelmesh-lite/"><img src="https://img.shields.io/pypi/pyversions/modelmesh-lite" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/ApartsinProjects/ModelMesh/actions"><img src="https://img.shields.io/badge/tests-579%20passed-brightgreen" alt="Tests"></a>
</p>

---

Your application requests a **capability** (e.g. "chat completion"). ModelMesh picks the best available provider, rotates on failure, and chains free quotas across providers -- all behind a standard OpenAI SDK interface.

## Install

```bash
pip install modelmesh-lite
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
import { ModelMesh } from "@modelmesh/core";

const mesh = new ModelMesh();
await mesh.initialize({ providers: ["openai"] });
const client = mesh.getClient();

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
export GEMINI_API_KEY="AI..."
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
| **[Quickstart](samples/quickstart/)** | 6 progressive examples in Python and TypeScript |
| **[System Integration](samples/system/)** | Multi-provider, streaming, embeddings, cost optimization |
| **[CDK Tutorials](samples/cdk/)** | Build providers, rotation policies, and more |
| **[Custom Connectors](samples/connectors/)** | Full custom connector examples for all 6 types |

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

[MIT](LICENSE)

---

<sub>Created by [Sasha Apartsin](https://www.apartsin.com)</sub>
