# API Quick Reference

A one-page cheat sheet for ModelMesh. Covers client creation, completions, pool inspection, usage tracking, exceptions, rotation strategies, capability aliases, environment variables, YAML config skeleton, and mock testing. For detailed explanations, follow the links to the full guides.

## Client Creation

| Python | TypeScript |
|--------|------------|
| `import modelmesh` | `import { create } from '@nistrapa/modelmesh-core';` |
| `client = modelmesh.create("chat-completion")` | `const client = create('chat-completion');` |
| `client = modelmesh.create("chat", middleware=[m])` | `const client = create('chat', { middleware: [m] });` |

### `modelmesh.create()` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `capability` | `str` | *(required)* | Capability alias or full dotted path |
| `config` | `dict` / `str` | Auto-detect | Config dict, YAML file path, or `None` for env auto-detect |
| `middleware` | `list` | `None` | List of `Middleware` instances |

### Context Manager

| Python | TypeScript |
|--------|------------|
| `with modelmesh.create("chat") as c:` | `try { ... } finally { client.close(); }` |
| `async with modelmesh.create("chat") as c:` | |

## Chat Completions

| Python | TypeScript |
|--------|------------|
| `client.chat.completions.create(...)` | `await client.chat.completions.create({...})` |

### Common Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | Pool name (virtual model ID) |
| `messages` | `list[dict]` | Conversation messages with `role` and `content` |
| `temperature` | `float` | Sampling temperature (0.0 - 2.0) |
| `max_tokens` | `int` | Maximum tokens in response |
| `stream` | `bool` | Enable token-by-token streaming |
| `top_p` | `float` | Nucleus sampling threshold |
| `stop` | `str / list` | Stop sequences |
| `tools` | `list` | Tool/function definitions |
| `response_format` | `dict` | Response format (e.g., `{"type": "json_object"}`) |

### Response Shape

```python
response.choices[0].message.content   # Assistant reply text
response.choices[0].message.role      # "assistant"
response.choices[0].finish_reason     # "stop", "length", "tool_calls"
response.model                        # Model ID that served the request
response.usage.prompt_tokens          # Input token count
response.usage.completion_tokens      # Output token count
response.usage.total_tokens           # Total token count
```

## Pool Inspection

| Method | Python | TypeScript |
|--------|--------|------------|
| Describe pool | `client.describe()` | `client.describe()` |
| Pool status | `client.pool_status()` | `client.poolStatus()` |
| Active providers | `client.active_providers()` | `client.activeProviders()` |
| Explain routing | `client.explain(model="chat")` | `client.explain({ model: 'chat' })` |

### `client.describe()` Output

```
Pool "chat-completion" (strategy: stick-until-failure)
  -> gpt-4o [openai.llm.v1] (active)
     claude-3-5-sonnet [anthropic.claude.v1] (active)
     llama-3.3-70b [groq.api.v1] (standby)
```

### `client.explain()` Fields

| Field | Description |
|-------|-------------|
| `pool_name` | Resolved pool name |
| `strategy` | Active rotation strategy |
| `selected_model` | Model that would serve the request |
| `candidates` | All candidate models with status |
| `reason` | Why this model was selected |

## Usage Tracking

| Python | TypeScript |
|--------|------------|
| `client.usage.total_cost` | `client.usage.totalCost` |
| `client.usage.total_tokens` | `client.usage.totalTokens` |
| `client.usage.total_requests` | `client.usage.totalRequests` |
| `client.usage.by_model` | `client.usage.byModel` |
| `client.usage.budget_status` | `client.usage.budgetStatus` |

## Exceptions

All exceptions inherit from `ModelMeshError`. See [Error Handling](ErrorHandling.md) for details.

| Exception | Retryable | Description |
|-----------|-----------|-------------|
| `ModelMeshError` | varies | Base exception for all ModelMesh errors |
| `RoutingError` | varies | Base for routing failures |
| `NoActiveModelError` | yes | All models in the pool are in standby |
| `AllProvidersExhaustedError` | no | All retry/rotation attempts failed |
| `ProviderError` | varies | Base for provider failures |
| `AuthenticationError` | no | Invalid API key or credentials |
| `RateLimitError` | yes | Provider rate limit hit (has `retry_after`) |
| `ProviderTimeoutError` | yes | Request timed out |
| `ConfigurationError` | no | Invalid YAML config or missing fields |
| `BudgetExceededError` | no | Daily or monthly spend limit breached |

### Import

```python
from modelmesh.exceptions import ModelMeshError, RateLimitError, BudgetExceededError
```

```typescript
import { ModelMeshError, RateLimitError, BudgetExceededError } from '@nistrapa/modelmesh-core';
```

## Rotation Strategies

| Strategy | Connector ID | Behavior |
|----------|-------------|----------|
| Stick-until-failure | `modelmesh.stick-until-failure.v1` | Use one model until it fails, then rotate |
| Round-robin | `modelmesh.round-robin.v1` | Cycle through models in order |
| Cost-first | `modelmesh.cost-first.v1` | Pick model with lowest accumulated cost |
| Latency-first | `modelmesh.latency-first.v1` | Pick model with lowest observed latency |
| Priority | `modelmesh.priority-selection.v1` | Follow ordered preference list with fallback |
| Session-stickiness | `modelmesh.session-stickiness.v1` | Route same-session requests to same model |
| Rate-limit-aware | `modelmesh.rate-limit-aware.v1` | Switch before quota exhaustion |
| Load-balanced | `modelmesh.load-balanced.v1` | Weighted round-robin distribution |

## Capability Aliases

| Alias | Full Path |
|-------|-----------|
| `chat-completion` | `generation.text-generation.chat-completion` |
| `text-generation` | `generation.text-generation` |
| `code-generation` | `generation.text-generation.code-generation` |
| `text-embeddings` | `representation.embeddings.text-embeddings` |
| `text-to-speech` | `generation.audio.text-to-speech` |
| `speech-to-text` | `understanding.audio.speech-to-text` |
| `text-to-image` | `generation.image.text-to-image` |
| `image-to-text` | `representation.image.image-to-text` |

See [Capabilities Guide](Capabilities.md) for the full hierarchy and discovery API.

## Environment Variables

| Variable | Provider |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GROQ_API_KEY` | Groq |
| `GOOGLE_API_KEY` | Google Gemini |
| `DEEPSEEK_API_KEY` | DeepSeek |
| `MISTRAL_API_KEY` | Mistral |
| `TOGETHER_API_KEY` | Together AI |
| `OPENROUTER_API_KEY` | OpenRouter |
| `XAI_API_KEY` | xAI (Grok) |
| `COHERE_API_KEY` | Cohere |
| `HF_API_KEY` | Hugging Face |

When no YAML config is provided, ModelMesh auto-detects providers from these environment variables.

## YAML Config Skeleton

```yaml
secrets:
  store: modelmesh.env.v1             # env, dotenv, aws, gcp, azure, 1password

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 10.00
      monthly_limit: 200.00

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

pools:
  chat-completion:
    strategy: modelmesh.stick-until-failure.v1
    deactivation:
      retry_limit: 3
    recovery:
      cooldown: 60s
    retry:
      max_attempts: 2
      backoff: exponential_jitter

storage:
  connector: modelmesh.local-file.v1
  path: ./mesh-state.json

observability:
  routing:
    connector: modelmesh.console.v1
  logging:
    connector: modelmesh.local-file.v1
    level: metadata
    path: ./requests.jsonl
```

See [System Configuration](../SystemConfiguration.md) for all options.

## Mock Testing

| Python | TypeScript |
|--------|------------|
| `from modelmesh.testing import mock_client, MockResponse` | `import { mockClient } from '@nistrapa/modelmesh-core/testing';` |

### Create Mock

```python
client = mock_client(responses=[
    MockResponse(content="Hello!", model="gpt-4o", tokens=10),
])
```

```typescript
const client = mockClient({
  responses: [{ content: 'Hello!', model: 'gpt-4o', tokens: 10 }],
});
```

### Assert Calls

```python
assert len(client.calls) == 1
assert client.calls[0].messages[0]["content"] == "Hi"
```

```typescript
expect(client.calls.length).toBe(1);
expect(client.calls[0].messages[0].content).toBe('Hi');
```

### MockResponse Fields

| Field | Default | Description |
|-------|---------|-------------|
| `content` | `"Mock response"` | Assistant reply |
| `model` | `"mock-model"` | Model ID |
| `tokens` | `10` | Total tokens |
| `finish_reason` | `"stop"` | Stop reason |

See [Testing Guide](Testing.md) for error simulation, response cycling, and pytest fixtures.

## Proxy CLI

```bash
python -m modelmesh.proxy [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | Auto-detect | YAML configuration file |
| `--host HOST` | `0.0.0.0` | Bind address |
| `--port PORT` | `8080` | Listen port |
| `--token TOKEN` | None | Bearer token for authentication |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

See [Proxy Guide](ProxyGuide.md) for full proxy documentation.

## Middleware Hooks

| Hook | Signature | Called |
|------|-----------|--------|
| `before_request` | `(request, context) -> request` | Before provider call |
| `after_response` | `(response, context) -> response` | After successful response |
| `on_error` | `(error, context) -> response` | On provider error |

See [Middleware Guide](Middleware.md) for patterns and examples.

---

See also: [Quick Start](QuickStart.md) · [System Configuration](../SystemConfiguration.md) · [Connector Catalogue](../ConnectorCatalogue.md) · [FAQ](FAQ.md)
