# Migration Guide

Migrate to ModelMesh from the OpenAI SDK, LangChain, or LiteLLM. ModelMesh provides an OpenAI SDK-compatible interface with multi-provider routing, automatic failover, and budget enforcement built in. For initial setup, see the [Quick Start](QuickStart.md). For the full configuration reference, see [System Configuration](../SystemConfiguration.md).

## From OpenAI SDK

The `MeshClient` returned by `modelmesh.create()` is a drop-in replacement for the OpenAI client. The `client.chat.completions.create()` signature is identical. Change two lines and you get automatic failover across every provider you configure.

### Python

**Before (OpenAI SDK):**

```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=0.7,
    max_tokens=512,
)
print(response.choices[0].message.content)
```

**After (ModelMesh):**

```python
import modelmesh

client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=0.7,
    max_tokens=512,
)
print(response.choices[0].message.content)
```

### TypeScript

**Before (OpenAI SDK):**

```typescript
import OpenAI from 'openai';

const client = new OpenAI({ apiKey: 'sk-...' });

const response = await client.chat.completions.create({
  model: 'gpt-4o',
  messages: [{ role: 'user', content: 'Hello!' }],
  temperature: 0.7,
  max_tokens: 512,
});
console.log(response.choices[0].message?.content);
```

**After (ModelMesh):**

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

const response = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Hello!' }],
  temperature: 0.7,
  max_tokens: 512,
});
console.log(response.choices[0].message?.content);
```

### What Changes

| Concern | OpenAI SDK | ModelMesh |
|---------|-----------|-----------|
| Import | `from openai import OpenAI` | `import modelmesh` |
| Client creation | `OpenAI(api_key="sk-...")` | `modelmesh.create("chat-completion")` |
| Model parameter | Literal model ID (`"gpt-4o"`) | Virtual pool name (`"chat-completion"`) |
| API key | Passed to constructor or env var | Resolved via [secret stores](SecretStores.md) |
| Streaming | `stream=True` | `stream=True` (identical) |
| Response shape | `ChatCompletion` object | Same `ChatCompletion` shape |
| Error types | `openai.APIError` | `ModelMeshError` hierarchy (see [Error Handling](ErrorHandling.md)) |

### Streaming Migration

Streaming works the same way. The response is an iterator of chunks with `delta.content`:

```python
# OpenAI SDK — streaming
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
for chunk in stream:
    token = chunk.choices[0].delta.content or ""
    print(token, end="")

# ModelMesh — identical call, but routes across providers
stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
for chunk in stream:
    token = chunk.choices[0].delta.content or ""
    print(token, end="")
```

### Keeping OpenAI as Fallback

You can still use the OpenAI SDK alongside ModelMesh. Point the OpenAI SDK at the ModelMesh proxy for routing benefits while keeping direct access for edge cases:

```python
from openai import OpenAI

# Route through ModelMesh proxy
routed_client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed",
)

# Direct OpenAI access (bypass routing)
direct_client = OpenAI(api_key="sk-...")
```

## From LangChain

ModelMesh provides a LangChain-compatible chat model wrapper. Use it as the LLM backend in any LangChain chain, agent, or pipeline.

### Python

**Before (LangChain with OpenAI):**

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o", api_key="sk-...")

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}"),
])
chain = prompt | llm
result = chain.invoke({"input": "What is ModelMesh?"})
print(result.content)
```

**After (LangChain with ModelMesh):**

```python
from modelmesh.integrations.langchain import ChatModelMesh
from langchain_core.prompts import ChatPromptTemplate

llm = ChatModelMesh(capability="chat-completion")

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}"),
])
chain = prompt | llm
result = chain.invoke({"input": "What is ModelMesh?"})
print(result.content)
```

### TypeScript

**Before (LangChain.js with OpenAI):**

```typescript
import { ChatOpenAI } from '@langchain/openai';
import { ChatPromptTemplate } from '@langchain/core/prompts';

const llm = new ChatOpenAI({ model: 'gpt-4o', apiKey: 'sk-...' });

const prompt = ChatPromptTemplate.fromMessages([
  ['system', 'You are a helpful assistant.'],
  ['user', '{input}'],
]);
const chain = prompt.pipe(llm);
const result = await chain.invoke({ input: 'What is ModelMesh?' });
console.log(result.content);
```

**After (LangChain.js with ModelMesh):**

```typescript
import { ChatModelMesh } from '@nistrapa/modelmesh-langchain';
import { ChatPromptTemplate } from '@langchain/core/prompts';

const llm = new ChatModelMesh({ capability: 'chat-completion' });

const prompt = ChatPromptTemplate.fromMessages([
  ['system', 'You are a helpful assistant.'],
  ['user', '{input}'],
]);
const chain = prompt.pipe(llm);
const result = await chain.invoke({ input: 'What is ModelMesh?' });
console.log(result.content);
```

### LangChain Integration Details

The `ChatModelMesh` wrapper supports:

| Feature | Support |
|---------|---------|
| `invoke()` / `ainvoke()` | Synchronous and async invocation |
| `stream()` / `astream()` | Token-by-token streaming |
| `batch()` / `abatch()` | Batch invocations |
| Tool calling | Pass tools via `bind_tools()` |
| Structured output | Use `with_structured_output()` |
| Callbacks | LangChain callback handlers |

The wrapper delegates to `MeshClient.chat.completions.create()` internally, so all ModelMesh routing, failover, and budget controls apply transparently.

## From LiteLLM

LiteLLM and ModelMesh both solve multi-provider routing. The migration is conceptual rather than a drop-in swap. Here is how key concepts map between the two libraries.

### Concept Mapping

| LiteLLM | ModelMesh | Notes |
|---------|-----------|-------|
| `litellm.completion()` | `client.chat.completions.create()` | ModelMesh uses an OpenAI-compatible client object |
| `model="openai/gpt-4o"` | `model="chat-completion"` | ModelMesh uses virtual pool names, not provider-prefixed model IDs |
| `fallbacks=["gpt-4o", "claude-3"]` | YAML pool with rotation strategy | ModelMesh separates routing config from code |
| `litellm.Router()` | `modelmesh.create()` | Both return a routing client |
| `max_budget` | `budget.daily_limit` / `budget.monthly_limit` | ModelMesh supports per-provider and per-pool budgets |
| `set_callbacks(["langfuse"])` | `observability` config section | ModelMesh has built-in observability connectors |
| Environment variable keys | Same env var names | Both read `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. |

### Python

**Before (LiteLLM):**

```python
import litellm

response = litellm.completion(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
    fallbacks=["anthropic/claude-3-5-sonnet-20241022"],
)
print(response.choices[0].message.content)
```

**After (ModelMesh):**

```python
import modelmesh

client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

Fallback behavior is configured in YAML rather than in code:

```yaml
providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
  anthropic.claude.v1:
    api_key: ${secrets:ANTHROPIC_API_KEY}

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities: [generation.text-generation.chat-completion]
  claude-3-5-sonnet:
    provider: anthropic.claude.v1
    capabilities: [generation.text-generation.chat-completion]

pools:
  chat-completion:
    strategy: modelmesh.priority-selection.v1
    model_priority: [gpt-4o, claude-3-5-sonnet]
```

### TypeScript

**Before (LiteLLM via API):**

```typescript
const response = await fetch('http://localhost:4000/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'openai/gpt-4o',
    messages: [{ role: 'user', content: 'Hello!' }],
  }),
});
const data = await response.json();
console.log(data.choices[0].message.content);
```

**After (ModelMesh):**

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

const response = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Hello!' }],
});
console.log(response.choices[0].message?.content);
```

### What ModelMesh Adds Over LiteLLM

| Feature | LiteLLM | ModelMesh |
|---------|---------|-----------|
| Provider routing | Model-prefix routing (`openai/gpt-4o`) | Capability-based pools with 8 rotation strategies |
| Configuration | Python dicts / env vars | Declarative YAML with env-specific overrides |
| Extensibility | Custom provider classes | CDK with typed connector interfaces |
| Budget enforcement | Global max budget | Per-provider, per-pool, daily/monthly limits |
| Secret management | Env vars only | 7 secret store backends (env, dotenv, AWS, GCP, Azure, 1Password, encrypted file) |
| Observability | Callback-based | Built-in connectors (console, file, webhook, Prometheus) |
| Deployment | Python proxy | Embedded library, proxy, or Docker |
| Mock testing | Not built-in | `mock_client()` with call inspection |
| TypeScript SDK | API proxy only | Native TypeScript client library |

## Feature Comparison Table

| Feature | OpenAI SDK | LiteLLM | ModelMesh |
|---------|-----------|---------|-----------|
| OpenAI-compatible API | Native | Yes | Yes |
| Multi-provider routing | No | Yes | Yes |
| Automatic failover | No | Yes (fallbacks) | Yes (8 strategies) |
| Capability-based pools | No | No | Yes |
| Budget enforcement | No | Global limit | Per-provider/pool/model |
| Secret store backends | No | Env vars | 7 backends |
| CDK extensibility | No | Limited | Full connector SDK |
| Mock testing | No | No | Built-in `mock_client()` |
| Native TypeScript SDK | Yes | Proxy only | Yes |
| Streaming | Yes | Yes | Yes |
| Tool calling | Yes | Yes | Yes |
| Structured output | Yes | Yes | Yes |
| LangChain integration | Native | Via proxy | `ChatModelMesh` wrapper |
| Observability | No | Callbacks | 7 connectors |
| YAML configuration | No | Limited | Full declarative config |

## Migration Checklist

1. Install ModelMesh: `pip install modelmesh-lite[yaml]` or `npm install @nistrapa/modelmesh-core`
2. Set API keys as environment variables (same variable names as before)
3. Replace client creation with `modelmesh.create("chat-completion")`
4. Change `model=` parameter from literal model IDs to pool names
5. Replace provider-specific error handling with [ModelMesh exceptions](ErrorHandling.md)
6. Move fallback/routing logic from code to [YAML configuration](../SystemConfiguration.md)
7. Add [middleware](Middleware.md) for logging, caching, or request transforms
8. Set up [budget controls](../SystemConfiguration.md#providers) to prevent surprise bills
9. Replace test mocks with `mock_client()` (see [Testing Guide](Testing.md))

---

See also: [Quick Start](QuickStart.md) · [Error Handling](ErrorHandling.md) · [System Configuration](../SystemConfiguration.md) · [Connector Catalogue](../ConnectorCatalogue.md)
