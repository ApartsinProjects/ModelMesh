# Middleware

ModelMesh middleware lets you intercept requests and responses without modifying library internals. Use middleware for logging, request transforms, response enrichment, caching, or custom [error handling](ErrorHandling.html). Middleware runs inside the [router's](../SystemConcept.html) request pipeline, after pool selection and before/after provider execution.

## Quick Start

### Python

```python
import modelmesh
from modelmesh import Middleware, MiddlewareContext
from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse


class LoggingMiddleware(Middleware):
    async def before_request(self, request, context):
        print(f"Routing to {context.model_id}")
        return request

    async def after_response(self, response, context):
        print(f"Got {response.usage.total_tokens} tokens")
        return response


client = modelmesh.create("chat", middleware=[LoggingMiddleware()])
```

### TypeScript

```typescript
import { create, Middleware, MiddlewareContext } from '@nistrapa/modelmesh-core';

class LoggingMiddleware extends Middleware {
  async beforeRequest(request, context) {
    console.log(`Routing to ${context.modelId}`);
    return request;
  }

  async afterResponse(response, context) {
    console.log(`Got ${response.usage?.totalTokens} tokens`);
    return response;
  }
}

const client = create('chat', { middleware: [new LoggingMiddleware()] });
```

## How It Works

Middleware hooks are called in a pipeline around each provider call:

```
beforeRequest (A → B → C)    ← forward order
    │
    ▼
  provider.complete()
    │
    ▼
afterResponse (C → B → A)    ← reverse order (onion model)
```

If the provider throws an error:

```
onError (A → B → C)          ← forward order, first handler wins
```

## Middleware Hooks

Override any combination of these three hooks:

### `before_request(request, context) → request`

Called before the provider receives the request. Return the (possibly modified) request to proceed.

### `after_response(response, context) → response`

Called after a successful response. Return the (possibly modified) response.

### `on_error(error, context) → response`

Called when the provider raises an error. Either:
- **Return** a fallback `CompletionResponse` to suppress the error
- **Raise** the error (or a new one) to let the router retry/rotate

## MiddlewareContext

Every hook receives a context object with metadata about the current routing decision:

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | `str` | Real model identifier selected |
| `provider_id` | `str` | Connector ID of the provider |
| `pool_name` | `str` | Virtual model / pool name |
| `attempt` | `int` | Current retry attempt (1-based) |
| `timestamp` | `float` | When the request was initiated |
| `metadata` | `dict` | Arbitrary key-value store for chaining |

## Common Patterns

### Request Transform

Add custom headers or modify parameters:

```python
class AddMetadata(Middleware):
    async def before_request(self, request, context):
        # Add a custom field to the request
        context.metadata["request_id"] = str(uuid.uuid4())
        return request
```

### Response Enrichment

Add computed fields to responses:

```python
class TimingMiddleware(Middleware):
    async def before_request(self, request, context):
        context.metadata["start_time"] = time.time()
        return request

    async def after_response(self, response, context):
        elapsed = time.time() - context.metadata["start_time"]
        context.metadata["latency_ms"] = elapsed * 1000
        return response
```

### Error Fallback

Return a cached or default response on failure:

```python
class FallbackMiddleware(Middleware):
    def __init__(self, default_response):
        self._default = default_response

    async def on_error(self, error, context):
        if context.attempt >= 3:
            return self._default  # Return fallback after 3 failures
        raise error  # Let the router retry
```

### Multiple Middleware

Stack multiple middleware — they execute in registration order:

```python
client = modelmesh.create("chat", middleware=[
    AuthMiddleware(),       # Runs first (before_request)
    LoggingMiddleware(),    # Runs second (before_request)
    CachingMiddleware(),    # Runs third (before_request)
])
# after_response runs in reverse: Caching → Logging → Auth
```

## MiddlewareStack

For advanced use, you can create a `MiddlewareStack` directly:

```python
from modelmesh import MiddlewareStack

stack = MiddlewareStack()
stack.add(LoggingMiddleware())
stack.add(CachingMiddleware())

# Use programmatically
result = await stack.run_before_request(request, context)
result = await stack.run_after_response(response, context)
result = await stack.run_on_error(error, context)
```

## Backward Compatibility

Middleware is entirely optional. Existing code that doesn't use middleware continues to work identically. The `middleware` parameter defaults to `None`, and the router skips middleware hooks when none are configured.

---

See also: [FAQ](FAQ.html) · [Quick Start](QuickStart.html) · [System Configuration](../SystemConfiguration.html)
