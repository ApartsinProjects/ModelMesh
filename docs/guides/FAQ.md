# Frequently Asked Questions

Ten questions developers ask before adopting ModelMesh, each answered with a short explanation and working code.

---

## 1. How quickly can I integrate ModelMesh into my project?

**Two minutes.** Set an env var, install the package, and call `create()`. No config files, no boilerplate.

```bash
export OPENAI_API_KEY="sk-..."
pip install modelmesh-lite
```

```python
import modelmesh

client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

**How does this work?** Setting `OPENAI_API_KEY` triggers auto-discovery: ModelMesh finds the OpenAI provider, registers its models, and groups them into **capability pools** by what each model can do. `create("chat-completion")` returns a client wired to the pool containing all chat-capable models. The shortcut `"chat-completion"` resolves to the full dot-notation path `generation.text-generation.chat-completion` automatically (see [Q5](#5-what-does-request-capabilities-not-model-names-mean)).

When you need more control, add a YAML file or pass options programmatically. All three layers compose: env vars for secrets, YAML for topology, code for runtime overrides.

```python
# YAML-driven
client = modelmesh.create(config="modelmesh.yaml")

# Programmatic
client = modelmesh.create(
    "chat-completion",
    providers=["openai", "anthropic"],
    strategy="cost-first",
)
```

See the [Progressive Configuration](../index.md) guide for the full reference.

---

## 2. Do I need to learn a new API?

**No.** ModelMesh uses the same `client.chat.completions.create()` interface you already know from the OpenAI SDK. Same parameters, same response shape.

```python
import modelmesh

client = modelmesh.create("chat-completion")

# Identical to openai.OpenAI().chat.completions.create()
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Summarize this"}],
    temperature=0.7,
    max_tokens=500,
)

print(response.choices[0].message.content)
print(response.usage.total_tokens)
```

```typescript
import { create } from "@nistrapa/modelmesh-core";

const client = create("chat-completion");

const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Summarize this" }],
});
```

The same call shape works for chat, embeddings, TTS, STT, and image generation regardless of which provider handles the request.

See the [Uniform OpenAI-Compatible API](Capabilities.md) guide.

---

## 3. How does free-tier aggregation work?

Set multiple free API keys. ModelMesh detects them, groups models by capability, and rotates silently when one provider's quota runs out.

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export GOOGLE_API_KEY="AI..."
```

```python
import modelmesh

client = modelmesh.create("chat-completion")

# This single call may use OpenAI, Anthropic, Groq, or Gemini
# depending on which provider has remaining quota
for i in range(100):
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": f"Request {i}"}],
    )
    print(f"Request {i}: served by {response.model}")
```

Your code makes the same call every time. The library handles detection, pooling, and rotation internally.

**How are pools formed?** Each provider registers its models with capability tags (e.g. `generation.text-generation.chat-completion`). ModelMesh groups all models sharing a capability into a single pool. When you call `create("chat-completion")`, you get a client backed by every chat-capable model across all discovered providers. Adding a new API key adds that provider's models to the existing pools automatically.

See the [Free-Tier Aggregation](QuickStart.md) guide.

---

## 4. What happens when a provider goes down?

ModelMesh retries with backoff, then rotates to the next model in the pool. All within the same request. Your code never sees the failure.

```python
import modelmesh

client = modelmesh.create("chat-completion")

# If OpenAI times out, ModelMesh automatically tries Anthropic,
# then Gemini. The caller receives the first successful response.
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello"}],
)

# Inspect the pool to see which providers are active
print(client.pool_status())
# {'chat-completion': {'active': 3, 'standby': 1, 'total': 4}}

# See exactly which model was selected and why
print(client.describe())
```

Choose from multiple rotation strategies in your YAML config:

```yaml
pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: cost-first       # or: latency-first, round-robin,
                               #     stick-until-failure, rate-limit-aware
```

See the [Resilient Routing](ErrorHandling.md) guide.

---

## 5. What does "request capabilities, not model names" mean?

Instead of hardcoding `"gpt-4o"` in your application, you request the capability you need (e.g. `"chat-completion"`). ModelMesh resolves it to the best available model at runtime.

```python
import modelmesh

# Discover what capabilities exist
caps = modelmesh.capabilities.list_all()
# ['chat-completion', 'code-generation', 'text-embeddings',
#  'text-to-speech', 'speech-to-text', 'text-to-image', ...]

# Resolve a short alias to its full path
path = modelmesh.capabilities.resolve("chat-completion")
# 'generation.text-generation.chat-completion'

# Search by keyword
matches = modelmesh.capabilities.search("text")
# ['text-embeddings', 'text-generation', 'text-to-image', 'text-to-speech']

# Use the alias directly when creating a client
client = modelmesh.create("chat-completion")
```

**Shortcuts vs dot-notation:** Every capability has a full dot-notation path reflecting its position in the hierarchy tree (e.g. `generation.text-generation.chat-completion`). Shortcuts like `"chat-completion"` are leaf-node aliases that resolve automatically. Both forms work everywhere: `create("chat-completion")` and `create("generation.text-generation.chat-completion")` are equivalent. Providers tag their models with full paths; you use whichever form is convenient.

When a new model launches or an old one is deprecated, update your config. Your application code stays the same.

See the [Capability Discovery](Capabilities.md) guide.

---

## 6. How do I prevent surprise AI bills?

Set daily or monthly spending limits in your configuration. ModelMesh tracks cost per request in real time and raises `BudgetExceededError` before the breaching request is sent.

```yaml
providers:
  openai.llm.v1:
    connector: openai.llm.v1
    config:
      api_key: "${secrets:OPENAI_API_KEY}"
    budget:
      daily_limit: 10.00
      monthly_limit: 100.00
      alert_threshold: 0.8
      enforce: true
```

```python
import modelmesh
from modelmesh.exceptions import BudgetExceededError

client = modelmesh.create(config="modelmesh.yaml")

try:
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello"}],
    )
except BudgetExceededError as e:
    print(f"Blocked: {e.limit_type} limit of ${e.limit_value} reached")

# Check current spend at any time
print(f"Total cost: ${client.usage.total_cost:.4f}")
print(f"By model:   {client.usage.by_model}")
```

See the [Budget Enforcement](QuickStart.md#usage-tracking) guide.

---

## 7. Can I use ModelMesh with my existing stack?

Yes. ModelMesh ships as a Python library, a TypeScript library, and a Docker image. Each exposes the same OpenAI-compatible API. Pick the one that fits your stack.

**Python backend:**
```bash
pip install modelmesh-lite
```

**TypeScript / Node.js frontend or backend:**
```bash
npm install @nistrapa/modelmesh-core
```

**Docker proxy (any language, any HTTP client):**
```bash
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="sk-..." \
  ghcr.io/apartsinprojects/modelmesh:latest
```

```bash
# Any language can now call the proxy
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"chat-completion","messages":[{"role":"user","content":"Hello"}]}'
```

All three share the same YAML configuration format. Zero core dependencies in the Python and TypeScript libraries.

See the [Full-Stack Deployment](QuickStart.md) guide.

---

## 8. How do I test AI code without burning API credits?

Use the built-in mock client. It returns pre-configured responses, records every call for assertions, and runs in milliseconds with zero network calls.

```python
from modelmesh.testing import mock_client, MockResponse

client = mock_client(responses=[
    MockResponse(content="Hello!", model="gpt-4o", tokens=10),
    MockResponse(content="World!", model="claude-3", tokens=15),
])

# Use exactly like the real client
resp = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hi"}],
)
assert resp.choices[0].message.content == "Hello!"

# Second call returns the next response
resp2 = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hey"}],
)
assert resp2.choices[0].message.content == "World!"

# Inspect what was sent
assert len(client.calls) == 2
assert client.calls[0].messages[0]["content"] == "Hi"
```

```typescript
import { mockClient } from "@nistrapa/modelmesh-core/testing";

const client = mockClient({
    responses: [{ content: "Hello!", model: "gpt-4o", tokens: 10 }],
});

const resp = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hi" }],
});
expect(resp.choices[0].message.content).toBe("Hello!");
expect(client.calls.length).toBe(1);
```

Debug routing decisions without making API calls:

```python
explanation = client.explain(model="chat-completion")
print(explanation["selected_model"])   # Which model would be selected
print(explanation["reason"])           # Why
```

See the [Mock Client and Testing](Testing.md) guide.

---

## 9. What observability does ModelMesh provide?

Pre-built connectors for console, file, JSON-log, Prometheus, and webhooks. Structured traces cover routing decisions, failover events, and budget alerts.

```yaml
observability:
  connector: modelmesh.console.v1
  config:
    log_level: summary
    use_color: true
    redact_secrets: true
```

For production, switch to Prometheus or webhook export:

```yaml
observability:
  connector: modelmesh.prometheus.v1
  config:
    endpoint: /metrics
    port: 9090
```

Plug in a custom callback for existing dashboards:

```python
from modelmesh.cdk import CallbackObservability, CallbackObservabilityConfig

def on_event(event):
    my_dashboard.send(event.event_type, event.model_id, event.timestamp)

obs = CallbackObservability(CallbackObservabilityConfig(
    callback=on_event,
))
```

Traces include severity levels (DEBUG, INFO, WARNING, ERROR) with component context (router, pool, provider) so you can filter by the subsystem you care about.

See the [Observability Connectors](../ConnectorCatalogue.md) reference.

---

## 10. What if the pre-built connectors don't cover my use case?

Use the CDK (Connector Development Kit). Each connector type has a base class you can inherit from. Override only the methods you need.

**Custom provider (10 lines):**

```python
from modelmesh.cdk import OpenAICompatibleProvider, OpenAICompatibleConfig
from modelmesh.interfaces.provider import ModelInfo

provider = OpenAICompatibleProvider(OpenAICompatibleConfig(
    base_url="https://my-internal-proxy.corp/v1",
    api_key="internal-key",
    models=[
        ModelInfo(
            id="internal-llm",
            name="Internal LLM",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=32_000,
        ),
    ],
))
```

**Custom rotation policy:**

```python
from modelmesh.cdk import ThresholdRotationPolicy, ThresholdRotationConfig

policy = ThresholdRotationPolicy(ThresholdRotationConfig(
    failure_count_threshold=5,
    error_rate_threshold=0.3,
    cooldown_seconds=120,
))
```

**Custom provider for a non-OpenAI API:**

When your API doesn't follow the OpenAI format, inherit from `BaseProvider` and override four hook methods. BaseProvider handles HTTP transport, retries, and error classification; you only translate the request and response formats.

```python
from modelmesh.cdk import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    ModelInfo, CompletionRequest, CompletionResponse,
    CompletionChoice, ChatMessage, TokenUsage,
)

class CorpLLMProvider(BaseProvider):
    """Provider for a custom internal API."""

    def _get_completion_endpoint(self) -> str:
        return f"{self._config.base_url.rstrip('/')}/api/generate"

    def _build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Corp-Token": self._config.api_key,
        }

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        return {
            "prompt": request.messages[-1]["content"],
            "model_name": request.model,
            "params": {"temperature": request.temperature or 0.7},
        }

    def _parse_response(self, data: dict) -> CompletionResponse:
        return CompletionResponse(
            id=data.get("request_id", ""),
            model=data.get("model", ""),
            choices=[CompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=data["output"]),
                finish_reason="stop",
            )],
            usage=TokenUsage(
                prompt_tokens=data.get("tokens_in", 0),
                completion_tokens=data.get("tokens_out", 0),
                total_tokens=data.get("tokens_in", 0) + data.get("tokens_out", 0),
            ),
        )

provider = CorpLLMProvider(BaseProviderConfig(
    base_url="https://llm.corp.internal",
    api_key="corp-token-123",
    models=[
        ModelInfo(
            id="corp.internal-llm",
            name="Internal LLM",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=32_000,
        ),
    ],
))
```

Override only what differs: `_get_completion_endpoint()` for the URL path, `_build_headers()` for authentication, `_build_request_payload()` to translate the request format, and `_parse_response()` to translate the response back. For streaming, also override `_parse_sse_chunk()`.

**Custom rotation policy:**

Inherit from `BaseRotationPolicy` and override `select()` to control how models are chosen, `should_deactivate()` to control when a model is taken offline, or `should_recover()` to control when it comes back.

```python
from modelmesh.cdk import BaseRotationPolicy, BaseRotationConfig
from modelmesh.interfaces.rotation import ModelState
from modelmesh.interfaces.provider import CompletionRequest
from typing import Optional

class CostAwarePolicy(BaseRotationPolicy):
    """Pick the cheapest model that hasn't exceeded its error threshold."""

    def select(
        self,
        candidates: list[ModelState],
        request: CompletionRequest,
    ) -> Optional[ModelState]:
        if not candidates:
            return None
        # Sort by cost (lowest first), break ties by error rate
        return min(candidates, key=lambda c: (c.total_cost, c.error_rate))
```

Register the policy in YAML by pointing `strategy` at your custom class, or pass it programmatically:

```yaml
pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: my_app.policies.CostAwarePolicy
```

```python
# Or register programmatically
from modelmesh.cdk import ThresholdRotationPolicy, ThresholdRotationConfig

policy = CostAwarePolicy(BaseRotationConfig(
    failure_threshold=5,
    cooldown_seconds=120,
))
```

Six connector types are extensible this way: providers, rotation policies, secret stores, storage backends, observability sinks, and discovery connectors.

See the [CDK](../ConnectorCatalogue.md) reference and [CDK Developer Guide](../cdk/DeveloperGuide.md).
