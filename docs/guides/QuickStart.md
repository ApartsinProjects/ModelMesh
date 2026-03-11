# Developer Quick Start

Get productive with ModelMesh in 5 minutes. This guide covers everything a developer needs for day-to-day usage: making requests, [handling errors](ErrorHandling.html), [testing](Testing.html), debugging routing, and tracking costs. For the full [YAML configuration reference](../SystemConfiguration.html), see the configuration docs.

## 1. First Request

### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

### TypeScript

```typescript
import { create } from '@nistrapa/modelmesh-core';

const client = create('chat-completion');

const response = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Hello!' }],
});
console.log(response.choices[0].message?.content);
```

The `model` parameter is a **virtual model name** — it maps to a capability pool, not a specific provider model. ModelMesh routes it to the best available provider automatically.

## 2. Context Manager (Resource Cleanup)

Always use a context manager for production code to ensure clean shutdown:

### Python

```python
import modelmesh

# Sync
with modelmesh.create("chat-completion") as client:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello!"}],
    )
# shutdown() called automatically

# Async
async with modelmesh.create("chat-completion") as client:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello!"}],
    )
```

### TypeScript

```typescript
const client = create('chat-completion');
try {
  const response = await client.chat.completions.create({ ... });
} finally {
  client.close();
}
```

## 3. Error Handling

ModelMesh provides structured exceptions so you can handle specific failure modes:

### Python

```python
from modelmesh.exceptions import (
    ModelMeshError,
    NoActiveModelError,
    RateLimitError,
    AllProvidersExhaustedError,
    BudgetExceededError,
)

try:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello"}],
    )
except RateLimitError as e:
    print(f"Rate limited by {e.provider_id}, retry in {e.retry_after}s")
except NoActiveModelError:
    print("No models available right now")
except AllProvidersExhaustedError as e:
    print(f"All {e.attempts} attempts failed: {e.last_error}")
except BudgetExceededError as e:
    print(f"Over budget: {e.limit_type} limit ${e.limit_value}")
except ModelMeshError as e:
    if e.retryable:
        print("Transient error, safe to retry")
    else:
        print(f"Permanent error: {e}")
```

### TypeScript

```typescript
import {
  ModelMeshError,
  RateLimitError,
  NoActiveModelError,
} from '@nistrapa/modelmesh-core';

try {
  const response = await client.chat.completions.create({ ... });
} catch (e) {
  if (e instanceof RateLimitError) {
    console.log(`Rate limited, retry in ${e.retryAfter}s`);
  } else if (e instanceof NoActiveModelError) {
    console.log('No models available');
  } else if (e instanceof ModelMeshError) {
    console.log(`Error (retryable: ${e.retryable}): ${e.message}`);
  }
}
```

See [Error Handling Guide](ErrorHandling.html) for the full exception hierarchy.

## 4. Middleware

Add logging, transforms, or caching without modifying library internals:

### Python

```python
from modelmesh import Middleware

class LoggingMiddleware(Middleware):
    async def before_request(self, request, context):
        print(f"→ {context.model_id} via {context.provider_id}")
        return request

    async def after_response(self, response, context):
        print(f"← {response.usage.total_tokens} tokens")
        return response

client = modelmesh.create("chat", middleware=[LoggingMiddleware()])
```

### TypeScript

```typescript
import { Middleware, create } from '@nistrapa/modelmesh-core';

class LoggingMiddleware extends Middleware {
  async beforeRequest(request, context) {
    console.log(`→ ${context.modelId} via ${context.providerId}`);
    return request;
  }
  async afterResponse(response, context) {
    console.log(`← ${response.usage?.totalTokens} tokens`);
    return response;
  }
}

const client = create('chat', { middleware: [new LoggingMiddleware()] });
```

See [Middleware Guide](Middleware.html) for advanced patterns.

## 5. Testing

Use the built-in mock client for unit tests — no API keys needed:

### Python

```python
from modelmesh.testing import mock_client, MockResponse

client = mock_client(responses=[
    MockResponse(content="Hello!", model="gpt-4o", tokens=10),
])

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hi"}],
)
assert response.choices[0].message.content == "Hello!"
assert len(client.calls) == 1
assert client.calls[0].messages[0]["content"] == "Hi"
```

### TypeScript

```typescript
import { mockClient } from '@nistrapa/modelmesh-core/testing';

const client = mockClient({
  responses: [{ content: 'Hello!', model: 'gpt-4o', tokens: 10 }],
});

const response = await client.chat.completions.create({
  model: 'chat-completion',
  messages: [{ role: 'user', content: 'Hi' }],
});
expect(response.choices[0].message?.content).toBe('Hello!');
expect(client.calls.length).toBe(1);
```

See [Testing Guide](Testing.html) for full mock client API.

## 6. Routing Explanation

Debug routing decisions without making actual API calls:

### Python

```python
explanation = client.explain(model="chat-completion")
print(explanation["pool_name"])        # "chat-completion"
print(explanation["strategy"])         # "stick-until-failure"
print(explanation["selected_model"])   # "gpt-4o"
print(explanation["candidates"])       # [CandidateInfo(...), ...]
print(explanation["reason"])           # Why this model was selected
```

### TypeScript

```typescript
const explanation = client.explain({ model: 'chat-completion' });
console.log(explanation.poolName);       // "chat-completion"
console.log(explanation.strategy);       // "stick-until-failure"
console.log(explanation.selectedModel);  // "gpt-4o"
```

## 7. Capability Discovery

Don't memorize capability paths — use the discovery API:

### Python

```python
import modelmesh

# List all capabilities
caps = modelmesh.capabilities.list_all()
# ['chat-completion', 'code-generation', 'image-to-text', ...]

# Resolve alias to full path
path = modelmesh.capabilities.resolve("chat-completion")
# 'generation.text-generation.chat-completion'

# Search by keyword
matches = modelmesh.capabilities.search("text")
# ['text-embeddings', 'text-generation', 'text-to-image', 'text-to-speech']

# View hierarchy
tree = modelmesh.capabilities.tree()
# {'generation': {'text-generation': {'chat-completion': {}, ...}, ...}}
```

### TypeScript

```typescript
import * as capabilities from '@nistrapa/modelmesh-core/capabilities';

const caps = capabilities.listAll();
const path = capabilities.resolve('chat-completion');
const matches = capabilities.search('text');
const tree = capabilities.tree();
```

## 8. Usage Tracking

Monitor costs and tokens in real time:

### Python

```python
client = modelmesh.create("chat")
# ... after some requests ...

print(f"Total cost: ${client.usage.total_cost:.4f}")
print(f"Total tokens: {client.usage.total_tokens}")

# Breakdown by model
for model_id, usage in client.usage.by_model.items():
    print(f"  {model_id}: ${usage.total_cost:.4f}")

# Check budget
status = client.usage.budget_status
if status and status.exceeded:
    print("Budget exceeded!")
```

### TypeScript

```typescript
console.log(`Total cost: $${client.usage.totalCost.toFixed(4)}`);
console.log(`Total tokens: ${client.usage.totalTokens}`);
```

## 9. Inspect Active Providers

See what's behind the virtual model:

```python
# Human-readable summary
print(client.describe())
# Pool "chat-completion" (strategy: stick-until-failure)
#   → gpt-4o [openai.llm.v1] (active)
#     claude-sonnet-4 [anthropic.claude.v1] (active)

# Structured pool status
status = client.pool_status()
# {'chat-completion': {'active': 2, 'standby': 0, 'total': 2, ...}}

# Provider list
providers = client.active_providers()
# ['openai.llm.v1', 'anthropic.claude.v1']
```

## API Cheat Sheet

| Task | Python | TypeScript |
|------|--------|------------|
| Create client | `modelmesh.create("chat")` | `create('chat')` |
| Chat completion | `client.chat.completions.create(...)` | `client.chat.completions.create(...)` |
| Streaming | `stream=True` | `stream: true` |
| Context manager | `with client:` / `async with client:` | `client.close()` |
| Error handling | `except ModelMeshError` | `catch (e) { if (e instanceof ModelMeshError) }` |
| Middleware | `middleware=[MyMiddleware()]` | `middleware: [new MyMiddleware()]` |
| Mock testing | `mock_client(responses=[...])` | `mockClient({ responses: [...] })` |
| Explain routing | `client.explain(model="...")` | `client.explain({ model: '...' })` |
| Capabilities | `modelmesh.capabilities.list_all()` | `capabilities.listAll()` |
| Usage tracking | `client.usage.total_cost` | `client.usage.totalCost` |
| Pool status | `client.pool_status()` | `client.poolStatus()` |
| Describe | `client.describe()` | `client.describe()` |

## Next Steps

- [FAQ](FAQ.html) — 10 questions developers ask before adopting ModelMesh
- [Error Handling Guide](ErrorHandling.html) — Full exception hierarchy reference
- [Middleware Guide](Middleware.html) — Write custom middleware
- [Testing Guide](Testing.html) — Mock client deep dive
- [System Configuration](../SystemConfiguration.html) — YAML config reference
- [Connector Catalogue](../ConnectorCatalogue.html) — All supported providers
