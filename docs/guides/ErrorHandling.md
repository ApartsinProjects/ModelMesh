# Error Handling

ModelMesh provides a structured exception hierarchy so you can catch failures at the right level of specificity. The [router](../SystemConcept.md) raises these exceptions during the request pipeline; [middleware](Middleware.md) can intercept them via `on_error` hooks.

## Exception Tree

```
ModelMeshError (base)
├── RoutingError
│   ├── NoActiveModelError        (retryable)
│   └── AllProvidersExhaustedError
├── ProviderError
│   ├── AuthenticationError
│   ├── RateLimitError            (retryable, has retry_after)
│   └── ProviderTimeoutError      (retryable)
├── ConfigurationError
└── BudgetExceededError
```

All exceptions inherit from `ModelMeshError`, so you can use a single broad catch or handle specific failure modes individually.

## Quick Start

### Python

```python
from modelmesh.exceptions import (
    ModelMeshError,
    NoActiveModelError,
    AllProvidersExhaustedError,
    RateLimitError,
    BudgetExceededError,
)

try:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello"}],
    )
except RateLimitError as e:
    print(f"Rate limited by {e.provider_id}, retry after {e.retry_after}s")
except NoActiveModelError:
    print("No models available — try again shortly")
except AllProvidersExhaustedError as e:
    print(f"All {e.attempts} attempts failed: {e.last_error}")
except BudgetExceededError as e:
    print(f"Budget exceeded: {e.limit_type} limit of {e.limit_value}")
except ModelMeshError as e:
    print(f"ModelMesh error: {e}")
```

### TypeScript

```typescript
import {
  ModelMeshError,
  NoActiveModelError,
  AllProvidersExhaustedError,
  RateLimitError,
  BudgetExceededError,
} from '@nistrapa/modelmesh-core';

try {
  const response = await client.chat.completions.create({
    model: 'chat-completion',
    messages: [{ role: 'user', content: 'Hello' }],
  });
} catch (e) {
  if (e instanceof RateLimitError) {
    console.log(`Rate limited, retry after ${e.retryAfter}s`);
  } else if (e instanceof NoActiveModelError) {
    console.log('No models available');
  } else if (e instanceof AllProvidersExhaustedError) {
    console.log(`All ${e.attempts} attempts failed`);
  } else if (e instanceof ModelMeshError) {
    console.log(`ModelMesh error: ${e.message}`);
  }
}
```

## Exception Details

Every ModelMesh exception carries structured metadata:

| Field | Type | Description |
|-------|------|-------------|
| `message` | `str` | Human-readable error description |
| `details` | `dict` | Arbitrary structured context |
| `retryable` | `bool` | Hint: may succeed on retry |

### Routing Exceptions

| Exception | Extra Fields | When Raised |
|-----------|-------------|-------------|
| `NoActiveModelError` | `pool_name` | All models in a pool are in standby |
| `AllProvidersExhaustedError` | `pool_name`, `attempts`, `last_error` | All retry/rotation attempts failed |

### Provider Exceptions

| Exception | Extra Fields | When Raised |
|-----------|-------------|-------------|
| `AuthenticationError` | `provider_id`, `model_id` | Invalid API key or credentials |
| `RateLimitError` | `provider_id`, `model_id`, `retry_after` | Rate limit or quota exceeded |
| `ProviderTimeoutError` | `provider_id`, `model_id`, `timeout_seconds` | Request timed out |

### Other Exceptions

| Exception | Extra Fields | When Raised |
|-----------|-------------|-------------|
| `ConfigurationError` | — | Invalid config, missing fields |
| `BudgetExceededError` | `limit_type`, `limit_value`, `actual_value` | Cost limit breached (see [budget controls](FAQ.md#6-how-do-i-prevent-surprise-ai-bills)) |

## Retry Guidance

Use the `retryable` field to decide whether to retry:

```python
try:
    response = client.chat.completions.create(...)
except ModelMeshError as e:
    if e.retryable:
        # Safe to retry — model may become available or rate limit may reset
        time.sleep(getattr(e, 'retry_after', 5))
        response = client.chat.completions.create(...)
    else:
        # Permanent failure — fix config, check credentials, or increase budget
        raise
```

## Backward Compatibility

The new exceptions maintain backward compatibility:

- `AllProvidersExhaustedError` inherits from `ModelMeshError` → `Error`
- `BudgetExceededError` inherits from `ModelMeshError` → `Error`
- Code catching base `Error` continues to work
- All new fields are additive — no existing behavior changed

---

See also: [FAQ](FAQ.md) · [Quick Start](QuickStart.md) · [System Configuration](../SystemConfiguration.md)
