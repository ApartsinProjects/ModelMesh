---
layout: default
title: "Convenience Layer"
---

# Convenience Layer

The convenience layer is a high-level entry point that makes ModelMesh Lite feel like a drop-in replacement for the OpenAI SDK. Instead of manually wiring providers, pools, and rotation policies, a single `modelmesh.create()` call auto-detects available providers from environment variables, builds the internal routing infrastructure, and returns a `MeshClient` -- an OpenAI SDK-compatible client with the same `client.chat.completions.create()` interface and the same response shape.

The goal is **progressive disclosure**: simple use cases require one line of setup; advanced use cases unlock the full configuration surface without changing the API.

> **Architecture:** The convenience layer sits on top of the core ModelMesh Lite system described in [SystemConcept.md](../SystemConcept.html). It does not replace any internal component -- it constructs them automatically from minimal input.

---

## Overview

### What the Convenience Layer Does

1. **Auto-detects providers** from environment variables (e.g., `OPENAI_API_KEY` present means OpenAI is available)
2. **Builds capability pools** for requested capabilities (e.g., `"chat-completion"`, `"text-embeddings"`)
3. **Configures rotation** with a default `stick-until-failure` strategy
4. **Returns a `MeshClient`** that mirrors the OpenAI SDK interface exactly

### OpenAI SDK vs ModelMesh -- Side-by-Side

There are exactly three differences between using the OpenAI SDK and using ModelMesh Lite: the import, the client creation call, and the model name.

**Python:**

| | OpenAI SDK | ModelMesh Lite |
| --- | --- | --- |
| **Import** | `from openai import OpenAI` | `import modelmesh` |
| **Create** | `client = OpenAI()` | `client = modelmesh.create("chat-completion")` |
| **Model** | `model="gpt-4o"` | `model="chat-completion"` |

```python
# OpenAI SDK
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)

# ModelMesh Lite -- same interface, capability-driven
import modelmesh
client = modelmesh.create("chat-completion")
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

**TypeScript:**

| | OpenAI SDK | ModelMesh Lite |
| --- | --- | --- |
| **Import** | `import OpenAI from "openai"` | `import modelmesh from "modelmesh"` |
| **Create** | `new OpenAI()` | `modelmesh.create("chat-completion")` |
| **Model** | `model: "gpt-4o"` | `model: "chat-completion"` |

```typescript
// OpenAI SDK
import OpenAI from "openai";
const client = new OpenAI();
const response = await client.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);

// ModelMesh Lite -- same interface, capability-driven
import modelmesh from "modelmesh";
const client = modelmesh.create("chat-completion");
const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);
```

Everything after client creation is identical. Existing code that uses the OpenAI SDK can migrate by changing two lines.

### Virtual Model Names

The capability name passed to `modelmesh.create()` becomes the **virtual model name** used in API calls. When the request reaches the router, the virtual name resolves to the best active real model in the corresponding pool (e.g., `"chat-completion"` may resolve to `gpt-4o`, `claude-sonnet-4-20250514`, or `gemini-2.0-flash` depending on provider availability).

The `response.model` field always reports the **actual model** used, so callers can inspect which provider handled each request.

---

## `modelmesh.create()` API Reference

### Python

```python
def create(
    *capabilities: str,                                     # positional: required capabilities
    pool: str | None = None,                                # predefined pool name
    providers: list[str] | None = None,                     # specific providers (optional filter)
    models: list[str] | None = None,                        # specific models (optional filter)
    strategy: str = "stick-until-failure",                   # rotation strategy
    api_keys: dict[str, str] | None = None,                 # override env var detection
    config: str | dict | MeshConfig | None = None,          # full config (file path, dict, or object)
) -> MeshClient:
```

### TypeScript

```typescript
function create(
    ...args: [...capabilities: string[], options?: CreateOptions]
): MeshClient;

interface CreateOptions {
    pool?: string;                                // predefined pool name
    providers?: string[];                         // specific providers (optional filter)
    models?: string[];                            // specific models (optional filter)
    strategy?: string;                            // rotation strategy, default "stick-until-failure"
    apiKeys?: Record<string, string>;             // override env var detection
    config?: string | Record<string, any> | MeshConfig;  // full config (file path, object, or MeshConfig)
}
```

### Parameters

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `capabilities` | positional `str` | -- | One or more capability names (e.g., `"chat-completion"`, `"text-embeddings"`). Each creates or joins a pool. |
| `pool` | `str \| None` | `None` | Name of a predefined pool (see [ModelCapabilities.md](../ModelCapabilities.html#predefined-capability-pools)). Mutually exclusive with positional capabilities. |
| `providers` | `list[str] \| None` | `None` | Restrict auto-detection to these providers only. Names match the [auto-detection registry](#auto-detection-registry). |
| `models` | `list[str] \| None` | `None` | Restrict pool membership to these specific model IDs only. |
| `strategy` | `str` | `"stick-until-failure"` | Rotation strategy name. Any pre-shipped or custom strategy is valid. |
| `api_keys` | `dict[str, str] \| None` | `None` | Explicit API keys keyed by provider name. Bypasses environment variable detection for the specified providers. |
| `config` | `str \| dict \| MeshConfig \| None` | `None` | Full configuration. A file path (YAML or JSON), a dict/object literal, or a `MeshConfig` instance. When provided, all other parameters are ignored except `strategy`. |

### Resolution Behavior

Parameters are resolved in priority order. The first matching rule applies:

| Priority | Condition | Behavior |
| --- | --- | --- |
| 1 | `config` is provided | Use the full configuration directly. This is the [Layer 2](#layer-2--full-configuration) shortcut. All auto-detection is skipped. |
| 2 | `pool` is provided | Look up the predefined pool by name. Auto-detect providers from environment variables (or `api_keys`). |
| 3 | `capabilities` are provided | Create pool(s) for the given capabilities. Auto-detect providers. Apply `providers` and `models` filters if given. |
| 4 | Nothing provided | Raise `ValueError("Specify capabilities, pool, or config")`. |

### Return Value

Returns a [`MeshClient`](#meshclient-class-reference) instance. The client is ready to use immediately -- provider connections, pool construction, and rotation policy initialization happen during `create()`.

---

## `MeshClient` Class Reference

`MeshClient` provides an OpenAI SDK-compatible interface. Code written for `openai.OpenAI()` works without modification when the client is swapped for a `MeshClient`.

### OpenAI-Compatible Interface

#### `client.chat.completions.create(...)`

Chat completions. Accepts all standard OpenAI parameters: `model`, `messages`, `temperature`, `max_tokens`, `tools`, `tool_choice`, `response_format`, `stream`, `stop`, `top_p`, `frequency_penalty`, `presence_penalty`, `seed`, `user`.

**Python:**

```python
response = client.chat.completions.create(
    model="chat-completion",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain capability-driven routing."},
    ],
    temperature=0.7,
    max_tokens=500,
)
```

**TypeScript:**

```typescript
const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Explain capability-driven routing." },
    ],
    temperature: 0.7,
    maxTokens: 500,
});
```

#### `client.embeddings.create(...)`

Text embeddings. Requires a pool with the `text-embeddings` capability.

**Python:**

```python
response = client.embeddings.create(
    model="text-embeddings",
    input="The quick brown fox jumps over the lazy dog.",
)
vector = response.data[0].embedding
```

**TypeScript:**

```typescript
const response = await client.embeddings.create({
    model: "text-embeddings",
    input: "The quick brown fox jumps over the lazy dog.",
});
const vector = response.data[0].embedding;
```

#### `client.audio.speech.create(...)`

Text-to-speech. Requires a pool with the `text-to-speech` capability.

**Python:**

```python
response = client.audio.speech.create(
    model="text-to-speech",
    input="Hello, welcome to ModelMesh Lite.",
    voice="alloy",
)
response.stream_to_file("output.mp3")
```

**TypeScript:**

```typescript
const response = await client.audio.speech.create({
    model: "text-to-speech",
    input: "Hello, welcome to ModelMesh Lite.",
    voice: "alloy",
});
const buffer = Buffer.from(await response.arrayBuffer());
```

#### `client.audio.transcriptions.create(...)`

Speech-to-text. Requires a pool with the `speech-to-text` capability.

**Python:**

```python
with open("recording.mp3", "rb") as f:
    response = client.audio.transcriptions.create(
        model="speech-to-text",
        file=f,
    )
print(response.text)
```

**TypeScript:**

```typescript
import fs from "fs";

const response = await client.audio.transcriptions.create({
    model: "speech-to-text",
    file: fs.createReadStream("recording.mp3"),
});
console.log(response.text);
```

#### `client.images.generate(...)`

Image generation. Requires a pool with the `text-to-image` capability.

**Python:**

```python
response = client.images.generate(
    model="text-to-image",
    prompt="A futuristic city skyline at sunset",
    n=1,
    size="1024x1024",
)
image_url = response.data[0].url
```

**TypeScript:**

```typescript
const response = await client.images.generate({
    model: "text-to-image",
    prompt: "A futuristic city skyline at sunset",
    n: 1,
    size: "1024x1024",
});
const imageUrl = response.data[0].url;
```

#### `client.models.list()`

List all models available across all configured pools.

**Python:**

```python
models = client.models.list()
for model in models.data:
    print(f"{model.id} -- owned by {model.owned_by}")
```

**TypeScript:**

```typescript
const models = await client.models.list();
for (const model of models.data) {
    console.log(`${model.id} -- owned by ${model.ownedBy}`);
}
```

### ModelMesh Extensions

These methods expose ModelMesh-specific functionality. They are not part of the OpenAI SDK interface and are available for progressive disclosure when deeper control is needed.

#### `client.mesh`

Access the underlying `ModelMesh` instance for full programmatic control.

**Python:**

```python
mesh = client.mesh
pools = mesh.list_pools()
for pool in pools:
    print(f"Pool: {pool.name}, models: {len(pool.models)}")
```

**TypeScript:**

```typescript
const mesh = client.mesh;
const pools = mesh.listPools();
for (const pool of pools) {
    console.log(`Pool: ${pool.name}, models: ${pool.models.length}`);
}
```

> **Reference:** The `ModelMesh` class is documented in [system/ModelMesh.md](../system/ModelMesh.html).

#### `client.pool_status()`

Return a summary of pool health: active model count, standby model count, and current selection for each pool.

**Python:**

```python
status = client.pool_status()
for pool_name, info in status.items():
    print(f"{pool_name}: {info.active}/{info.total} active, current={info.current_model}")
```

**TypeScript:**

```typescript
const status = client.poolStatus();
for (const [poolName, info] of Object.entries(status)) {
    console.log(`${poolName}: ${info.active}/${info.total} active, current=${info.currentModel}`);
}
```

#### `client.active_providers()`

Return a list of currently active provider names across all pools.

**Python:**

```python
providers = client.active_providers()
print(providers)  # ["openai", "anthropic", "google"]
```

**TypeScript:**

```typescript
const providers = client.activeProviders();
console.log(providers);  // ["openai", "anthropic", "google"]
```

#### `client.rotate(pool)`

Force an immediate rotation in the specified pool, moving the current model to standby and selecting the next active model.

**Python:**

```python
new_model = client.rotate("chat-completion")
print(f"Rotated to: {new_model}")
```

**TypeScript:**

```typescript
const newModel = client.rotate("chat-completion");
console.log(`Rotated to: ${newModel}`);
```

---

## Response Compatibility

Responses from `MeshClient` match the OpenAI `ChatCompletion` shape exactly. Existing code that destructures OpenAI responses works without modification.

### Response Structure

**Python:**

```python
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "What is 2 + 2?"}],
)

# Standard OpenAI response fields
response.id                                  # "chatcmpl-abc123..."
response.object                              # "chat.completion"
response.created                             # 1709123456
response.model                               # "gpt-4o" (actual model used)

# Choices
response.choices[0].index                    # 0
response.choices[0].message.role             # "assistant"
response.choices[0].message.content          # "2 + 2 equals 4."
response.choices[0].finish_reason            # "stop"

# Usage
response.usage.prompt_tokens                 # 14
response.usage.completion_tokens             # 8
response.usage.total_tokens                  # 22
```

**TypeScript:**

```typescript
const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "What is 2 + 2?" }],
});

// Standard OpenAI response fields
response.id;                                  // "chatcmpl-abc123..."
response.object;                              // "chat.completion"
response.created;                             // 1709123456
response.model;                               // "gpt-4o" (actual model used)

// Choices
response.choices[0].index;                    // 0
response.choices[0].message.role;             // "assistant"
response.choices[0].message.content;          // "2 + 2 equals 4."
response.choices[0].finishReason;             // "stop"

// Usage
response.usage.promptTokens;                 // 14
response.usage.completionTokens;             // 8
response.usage.totalTokens;                  // 22
```

### Key Observations

| Field | Value | Note |
| --- | --- | --- |
| `response.model` | Actual model ID (e.g., `"gpt-4o"`, `"claude-sonnet-4-20250514"`) | Always the real model, never the virtual name |
| `response.choices` | Array of choice objects | Identical structure to OpenAI |
| `response.usage` | Token counts | Reported by the underlying provider; accuracy depends on provider |

The virtual model name (`"chat-completion"`) is used only in the request. The response always contains the actual model that handled the request, enabling callers to log or audit which provider was selected.

---

## Streaming

Streaming works identically to the OpenAI SDK. Pass `stream=True` (Python) or `stream: true` (TypeScript) and iterate over chunks.

### Python

```python
stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Write a short poem about routing."}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content is not None:
        print(delta.content, end="", flush=True)
print()  # newline after stream completes
```

### TypeScript

```typescript
const stream = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Write a short poem about routing." }],
    stream: true,
});

for await (const chunk of stream) {
    const delta = chunk.choices[0].delta;
    if (delta.content) {
        process.stdout.write(delta.content);
    }
}
console.log();  // newline after stream completes
```

### Streaming Response Shape

Each chunk follows the OpenAI `ChatCompletionChunk` format:

| Field | Description |
| --- | --- |
| `chunk.id` | Same ID across all chunks in one response |
| `chunk.object` | `"chat.completion.chunk"` |
| `chunk.model` | Actual model ID |
| `chunk.choices[0].delta.role` | Present in first chunk only (`"assistant"`) |
| `chunk.choices[0].delta.content` | Token fragment (may be `None`/`null` or empty string) |
| `chunk.choices[0].finish_reason` | `None`/`null` until final chunk, then `"stop"` |

Streaming with tool calls, function calls, and structured output follows the same OpenAI conventions.

---

## Usage Patterns

The convenience layer supports four levels of configuration complexity. Each layer builds on the previous one -- choose the simplest layer that meets your needs.

### Layer 0 -- Capability Quick Start

Specify a single capability. Providers are auto-detected from environment variables. The default rotation strategy (`stick-until-failure`) is applied.

**Python:**

```python
import modelmesh

client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

**TypeScript:**

```typescript
import modelmesh from "modelmesh";

const client = modelmesh.create("chat-completion");

const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);
```

This is the minimal setup. If `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are both set, the pool contains models from both providers and rotates on failure.

### Layer 1 -- Multi-Capability with Providers

Request multiple capabilities, filter to specific providers, and choose a rotation strategy.

**Python:**

```python
import modelmesh

client = modelmesh.create(
    "chat-completion", "text-embeddings",
    providers=["openai", "anthropic"],
    strategy="cost-first",
)

# Chat -- routed through the chat-completion pool
chat = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Summarize this document."}],
)

# Embeddings -- routed through the text-embeddings pool
emb = client.embeddings.create(
    model="text-embeddings",
    input="Document text here...",
)
```

**TypeScript:**

```typescript
import modelmesh from "modelmesh";

const client = modelmesh.create(
    "chat-completion", "text-embeddings",
    {
        providers: ["openai", "anthropic"],
        strategy: "cost-first",
    },
);

// Chat -- routed through the chat-completion pool
const chat = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Summarize this document." }],
});

// Embeddings -- routed through the text-embeddings pool
const emb = await client.embeddings.create({
    model: "text-embeddings",
    input: "Document text here...",
});
```

Each capability creates a separate pool. The `providers` filter restricts which auto-detected providers are included. The `strategy` applies to all pools.

### Layer 1b -- Predefined Pool

Use a predefined pool from the capability hierarchy. Predefined pools come with pre-configured capability nodes, so you do not need to specify capabilities explicitly.

**Python:**

```python
import modelmesh

client = modelmesh.create(pool="text-generation")

response = client.chat.completions.create(
    model="text-generation",
    messages=[{"role": "user", "content": "Write a haiku about APIs."}],
)
```

**TypeScript:**

```typescript
import modelmesh from "modelmesh";

const client = modelmesh.create({ pool: "text-generation" });

const response = await client.chat.completions.create({
    model: "text-generation",
    messages: [{ role: "user", content: "Write a haiku about APIs." }],
});
```

> **Predefined pools:** The full list of predefined pools is in [ModelCapabilities.md -- Predefined Capability Pools](../ModelCapabilities.html#predefined-capability-pools).

### Layer 2 -- Full Configuration

Pass a complete configuration file, dictionary, or `MeshConfig` object. This bypasses all auto-detection and gives full control over providers, pools, models, rotation policies, secret stores, and observability.

**Python:**

```python
import modelmesh

# From a YAML file
client = modelmesh.create(config="modelmesh.yaml")

# From a dictionary
client = modelmesh.create(config={
    "providers": {
        "openai": {
            "connector": "openai.llm.v1",
            "config": {"api_key": "${secrets:openai-key}"},
        },
        "anthropic": {
            "connector": "anthropic.claude.v1",
            "config": {"api_key": "${secrets:anthropic-key}"},
        },
    },
    "pools": {
        "chat-completion": {
            "capability": "chat-completion",
            "strategy": "cost-first",
        },
    },
})

# From a MeshConfig object
from modelmesh import MeshConfig
cfg = MeshConfig.from_file("modelmesh.yaml")
client = modelmesh.create(config=cfg)
```

**TypeScript:**

```typescript
import modelmesh, { MeshConfig } from "modelmesh";

// From a YAML file
const client1 = modelmesh.create({ config: "modelmesh.yaml" });

// From an object literal
const client2 = modelmesh.create({
    config: {
        providers: {
            openai: {
                connector: "openai.llm.v1",
                config: { apiKey: "${secrets:openai-key}" },
            },
            anthropic: {
                connector: "anthropic.claude.v1",
                config: { apiKey: "${secrets:anthropic-key}" },
            },
        },
        pools: {
            "chat-completion": {
                capability: "chat-completion",
                strategy: "cost-first",
            },
        },
    },
});

// From a MeshConfig instance
const cfg = MeshConfig.fromFile("modelmesh.yaml");
const client3 = modelmesh.create({ config: cfg });
```

> **Configuration reference:** Full YAML schema and all configuration options are documented in [SystemConfiguration.md](../SystemConfiguration.html).

### Observability Configuration

By default, `modelmesh.create()` disables observability output by using the `modelmesh.null.v1` connector (zero overhead). To enable observability, pass an observability section in the `config` parameter.

**Python:**

```python
import modelmesh

# With file logging
client = modelmesh.create("chat-completion", config={
    "observability": {"connector": "modelmesh.file.v1"}
})

# With console output (colored, for development)
client = modelmesh.create("chat-completion", config={
    "observability": {"connector": "modelmesh.console.v1"}
})

# Explicitly disabled (default behavior)
client = modelmesh.create("chat-completion", config={
    "observability": {"connector": "modelmesh.null.v1"}
})
```

**TypeScript:**

```typescript
import modelmesh from "modelmesh";

// With file logging
const client = modelmesh.create("chat-completion", {
    config: {
        observability: { connector: "modelmesh.file.v1" },
    },
});

// With console output (colored, for development)
const client2 = modelmesh.create("chat-completion", {
    config: {
        observability: { connector: "modelmesh.console.v1" },
    },
});
```

| Connector ID | Description |
| --- | --- |
| `modelmesh.null.v1` | No-op connector, discards all output (default) |
| `modelmesh.console.v1` | ANSI-colored console output for development |
| `modelmesh.file.v1` | Structured JSONL file output |

> **Note:** When `modelmesh.create()` is called without a `config` parameter (Layers 0, 1, and 1b), observability defaults to `modelmesh.null.v1`. To enable observability in these layers, wrap the call with a config dict that includes both capabilities and an observability section.

---

## Auto-Detection Registry

When `modelmesh.create()` runs without an explicit `config`, it scans environment variables to discover which providers are available. Each provider maps to an environment variable, a provider name, and a connector ID.

| Environment Variable | Provider Name | Connector ID | Capabilities |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | `openai` | `openai.llm.v1` | chat, embeddings, audio, images |
| `ANTHROPIC_API_KEY` | `anthropic` | `anthropic.claude.v1` | chat |
| `GOOGLE_API_KEY` | `google` | `google.gemini.v1` | chat, embeddings |
| `GROQ_API_KEY` | `groq` | `groq.api.v1` | chat |
| `MISTRAL_API_KEY` | `mistral` | `mistral.api.v1` | chat, embeddings |
| `TOGETHER_API_KEY` | `together` | `together.api.v1` | chat, embeddings, images |
| `FIREWORKS_API_KEY` | `fireworks` | `fireworks.api.v1` | chat, embeddings |
| `OPENROUTER_API_KEY` | `openrouter` | `openrouter.gateway.v1` | chat |
| `HF_TOKEN` | `huggingface` | `huggingface.inference.v1` | chat, embeddings |

### Detection Rules

1. For each entry in the registry, check whether the environment variable is set and non-empty.
2. If `providers` is specified, include only providers whose name appears in the list.
3. If `api_keys` is specified, use the provided key instead of the environment variable for matching providers.
4. If no providers are detected, raise `RuntimeError("No API keys found. Set at least one provider API key as an environment variable.")`.

### Overriding Detection with `api_keys`

**Python:**

```python
import modelmesh

client = modelmesh.create(
    "chat-completion",
    api_keys={
        "openai": "sk-custom-key-here",
        "anthropic": "sk-ant-custom-key-here",
    },
)
```

**TypeScript:**

```typescript
import modelmesh from "modelmesh";

const client = modelmesh.create("chat-completion", {
    apiKeys: {
        openai: "sk-custom-key-here",
        anthropic: "sk-ant-custom-key-here",
    },
});
```

When `api_keys` is provided, only the listed providers are included (environment variables for unlisted providers are ignored). This is useful for testing, multi-tenant applications, or environments where environment variables are not available.

---

## `QuickProvider` Class

`QuickProvider` is a lightweight provider class designed for use with the convenience layer. It extends `BaseProvider` and can operate with an empty `models` list -- in that case, it auto-discovers available models by querying the provider's `/v1/models` endpoint at initialization.

> **Base class:** `QuickProvider` extends [BaseProvider](BaseClasses.html#baseprovider), inheriting all default behavior (OpenAI-format request translation, SSE streaming, retry logic, error classification).

### Constructor

**Python:**

```python
from modelmesh.cdk import QuickProvider

provider = QuickProvider(
    base_url="https://api.example.com",
    api_key="sk-example-key",
    # Optional overrides:
    models=[],                    # empty = auto-discover via /v1/models
    timeout=30.0,
    max_retries=3,
    capabilities=["generation.text-generation.chat-completion"],
)
```

**TypeScript:**

```typescript
import { QuickProvider } from "modelmesh/cdk";

const provider = new QuickProvider({
    baseUrl: "https://api.example.com",
    apiKey: "sk-example-key",
    // Optional overrides:
    models: [],                    // empty = auto-discover via /v1/models
    timeout: 30,
    maxRetries: 3,
    capabilities: ["generation.text-generation.chat-completion"],
});
```

### Auto-Discovery

When `models` is empty or omitted, `QuickProvider` sends a GET request to `{base_url}/v1/models` during initialization and populates its model catalogue from the response. This matches the behavior of providers that expose an OpenAI-compatible model listing endpoint.

### Using `QuickProvider` with `modelmesh.create()`

Pass a `QuickProvider` through the `config` parameter by constructing a configuration object that references it.

**Python:**

```python
import modelmesh
from modelmesh.cdk import QuickProvider

custom = QuickProvider(
    base_url="https://my-llm-gateway.internal/v1",
    api_key="sk-internal-key",
)

client = modelmesh.create(config={
    "providers": {
        "internal-gateway": {
            "instance": custom,
        },
    },
    "pools": {
        "chat-completion": {
            "capability": "chat-completion",
            "providers": ["internal-gateway"],
        },
    },
})
```

**TypeScript:**

```typescript
import modelmesh from "modelmesh";
import { QuickProvider } from "modelmesh/cdk";

const custom = new QuickProvider({
    baseUrl: "https://my-llm-gateway.internal/v1",
    apiKey: "sk-internal-key",
});

const client = modelmesh.create({
    config: {
        providers: {
            "internal-gateway": {
                instance: custom,
            },
        },
        pools: {
            "chat-completion": {
                capability: "chat-completion",
                providers: ["internal-gateway"],
            },
        },
    },
});
```

---

## LangChain / LangGraph Integration

`MeshClient` provides a `ChatOpenAI`-compatible interface, so LangChain and LangGraph pipelines connect directly without adapters or wrappers.

> **Reference:** See [SystemConcept.md](../SystemConcept.html) for the architectural relationship between ModelMesh Lite and higher-level AI frameworks.

**Python:**

```python
import modelmesh
from langchain_core.messages import HumanMessage

# Create a ModelMesh client
client = modelmesh.create("chat-completion")

# Use directly in LangChain -- MeshClient is ChatOpenAI-compatible
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    client=client.chat.completions,    # pass the completions interface
    model="chat-completion",
)

# Works in chains and agents
response = llm.invoke([HumanMessage(content="Explain AI routing.")])

# Works in LangGraph
from langgraph.graph import StateGraph
graph = StateGraph(...)
graph.add_node("llm", llm)
```

**TypeScript:**

```typescript
import modelmesh from "modelmesh";
import { ChatOpenAI } from "@langchain/openai";

// Create a ModelMesh client
const client = modelmesh.create("chat-completion");

// Use directly in LangChain -- MeshClient is ChatOpenAI-compatible
const llm = new ChatOpenAI({
    client: client.chat.completions,    // pass the completions interface
    model: "chat-completion",
});

// Works in chains and agents
const response = await llm.invoke([{ role: "user", content: "Explain AI routing." }]);
```

ModelMesh Lite handles provider rotation, failover, and quota management transparently beneath the LangChain abstraction. The LangChain pipeline does not need to know which provider is active -- it sees a standard `ChatOpenAI` interface.

---

## Cross-References

| Document | Description |
| --- | --- |
| [Overview.md](Overview.html) | CDK architecture, class hierarchy, and decision trees |
| [BaseClasses.md](BaseClasses.html) | API reference for all base classes, including `BaseProvider` |
| [DeveloperGuide.md](DeveloperGuide.html) | Step-by-step tutorials for building custom connectors |
| [SystemConcept.md](../SystemConcept.html) | System architecture, capability model, and routing pipeline |
| [ConnectorInterfaces.md](../ConnectorInterfaces.html) | Interface definitions for all connector types |
| [SystemConfiguration.md](../SystemConfiguration.html) | Full YAML configuration reference |
| [ModelCapabilities.md](../ModelCapabilities.html) | Capability hierarchy and predefined pools |
| [ConnectorCatalogue.md](../ConnectorCatalogue.html) | Registry of all pre-shipped connectors |
