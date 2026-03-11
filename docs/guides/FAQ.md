# Frequently Asked Questions

Twenty-one questions developers ask before and after adopting ModelMesh, each answered with a short explanation and working code. For architecture details, see [System Concept](../SystemConcept.md). For the YAML reference, see [System Configuration](../SystemConfiguration.md).

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

**How does this work?** Setting `OPENAI_API_KEY` triggers auto-discovery: ModelMesh finds the OpenAI provider, registers its models, and groups them into **[capability pools](../SystemConcept.md#capability-based-model-pools)** by what each model can do. `create("chat-completion")` returns a client wired to the pool containing all chat-capable models. The shortcut `"chat-completion"` resolves to the full dot-notation path `generation.text-generation.chat-completion` automatically (see [Q5](#5-what-does-request-capabilities-not-model-names-mean)).

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

**How are pools formed?** Each provider registers its models with [capability tags](../ModelCapabilities.md) (e.g. `generation.text-generation.chat-completion`). ModelMesh groups all models sharing a capability into a single pool. When you call `create("chat-completion")`, you get a client backed by every chat-capable model across all discovered providers. Adding a new API key adds that provider's models to the existing pools automatically.

See the [Free-Tier Aggregation](QuickStart.md) guide.

---

## 4. What happens when a provider goes down?

ModelMesh retries with backoff, then [rotates](../SystemConcept.md) to the next model in the pool. All within the same request. Your code never sees the failure (see [Error Handling](ErrorHandling.md) for the full exception hierarchy).

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

Choose from 8 built-in rotation strategies:

| Strategy | Connector ID | Behaviour |
|---|---|---|
| Stick-until-failure | `modelmesh.stick-until-failure.v1` | Use current model until it errors (default) |
| Cost-first | `modelmesh.cost-first.v1` | Always pick the model with lowest accumulated cost |
| Latency-first | `modelmesh.latency-first.v1` | Always pick the model with lowest observed latency |
| Round-robin | `modelmesh.round-robin.v1` | Cycle through models in sequence |
| Priority | `modelmesh.priority-selection.v1` | Follow an ordered preference list with fallback |
| Session-stickiness | `modelmesh.session-stickiness.v1` | Route same-session requests to the same model |
| Rate-limit-aware | `modelmesh.rate-limit-aware.v1` | Track per-model quotas, switch before exhaustion |
| Load-balanced | `modelmesh.load-balanced.v1` | Distribute requests using weighted round-robin |

Switch strategies in YAML:

```yaml
pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: modelmesh.cost-first.v1
```

Or pass a pre-built strategy instance via API:

```python
from modelmesh.connectors import CostFirstPolicy

mesh.initialize(MeshConfig(raw={
    "pools": {
        "chat": {
            "capability": "generation.text-generation.chat-completion",
            "strategy_instance": CostFirstPolicy(),  # direct injection
        }
    },
    # ...
}))
```

Need a custom strategy? See [Q10](#10-what-if-the-pre-built-connectors-dont-cover-my-use-case).

See the [Resilient Routing](ErrorHandling.md) guide and [Connector Catalogue](../ConnectorCatalogue.md) for full config reference.

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

**Shortcuts vs dot-notation:** Every capability has a full dot-notation path reflecting its position in the [hierarchy tree](../ModelCapabilities.md) (e.g. `generation.text-generation.chat-completion`). Shortcuts like `"chat-completion"` are leaf-node aliases that resolve automatically. Both forms work everywhere: `create("chat-completion")` and `create("generation.text-generation.chat-completion")` are equivalent. Providers tag their models with full paths; you use whichever form is convenient.

When a new model launches or an old one is deprecated, update your config. Your application code stays the same.

See the [Capability Discovery](Capabilities.md) guide.

---

## 6. How do I prevent surprise AI bills?

Set daily or monthly spending limits in your [configuration](../SystemConfiguration.md#providers). ModelMesh tracks cost per request in real time and raises [`BudgetExceededError`](ErrorHandling.md) before the breaching request is sent.

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

**Budget-aware rotation:** Instead of raising an error when a model exceeds its budget, configure the pool to automatically rotate to the next available model:

```yaml
pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: modelmesh.stick-until-failure.v1
    on_budget_exceeded: rotate   # "rotate" or "error" (default: "error")
```

With `on_budget_exceeded: rotate`, when a model's budget limit is reached, the router deactivates that model and silently retries with the next candidate — no code changes needed.

See the [Budget Enforcement](QuickStart.md#usage-tracking) guide and [System Configuration](../SystemConfiguration.md) for the full YAML schema.

---

## 7. Can I use ModelMesh with my existing stack?

Yes. ModelMesh ships as a Python library, a TypeScript library, and a [Docker proxy](ProxyGuide.md). Each exposes the same OpenAI-compatible API. Pick the one that fits your stack.

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

All three share the same [YAML configuration format](../SystemConfiguration.md). Zero core dependencies in the Python and TypeScript libraries. For browser usage with TypeScript, see the [Browser Guide](BrowserUsage.md).

See the [Full-Stack Deployment](QuickStart.md) guide and [Proxy Guide](ProxyGuide.md).

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

## 9. How do I configure infrastructure connectors (observability, storage, secrets)?

ModelMesh has **6 connector types**. Providers and rotation are covered in Q1-Q4. This section covers the remaining infrastructure connectors. Each can be configured via YAML or injected as a pre-built instance via API.

| Connector Type | What It Does | Pre-shipped | CDK Base Class |
|---|---|---|---|
| **Provider** | Calls AI APIs (chat, embeddings, TTS, STT, search) | 22 connectors | `BaseProvider` |
| **Rotation** | Selects which model to use and when to rotate | 8 strategies | `BaseRotationPolicy` |
| **Secret Store** | Resolves API keys and credentials | 7 stores | `BaseSecretStore` |
| **Storage** | Persists model state, stats, and cost data | 6 backends | `BaseStorage` |
| **Observability** | Events, logging, metrics, tracing | 7 sinks | `BaseObservability` |
| **Discovery** | Auto-discovers provider models and health checks | 1 connector | `BaseDiscovery` |

→ Full list of every connector and its config: [Connector Catalogue](../ConnectorCatalogue.md)
→ Interface specs for all 6 types: [Connector Interfaces](../ConnectorInterfaces.md)

### Observability

7 built-in sinks:

| Connector ID | Use Case |
|---|---|
| `modelmesh.null.v1` | No-op (default, zero overhead) |
| `modelmesh.console.v1` | ANSI-colored console output for development |
| `modelmesh.file.v1` | JSONL file with rotation support |
| `modelmesh.json-log.v1` | JSON Lines for log aggregation pipelines |
| `modelmesh.webhook.v1` | HTTP POST to alerting endpoints |
| `modelmesh.callback.v1` | Python callable for in-process dashboards |
| `modelmesh.prometheus.v1` | Prometheus text exposition format |

```yaml
# YAML configuration
observability:
  connector: modelmesh.console.v1
  config:
    log_level: summary
    use_color: true
```

```python
# Or inject a pre-built instance via API
from modelmesh.cdk import CallbackObservability, CallbackObservabilityConfig

obs = CallbackObservability(CallbackObservabilityConfig(
    callback=lambda event: my_dashboard.send(event),
))

mesh.initialize(MeshConfig(raw={
    "observability": {"instance": obs},
    # ...
}))
```

### Secret stores

7 built-in stores:

| Connector ID | Use Case |
|---|---|
| `modelmesh.env.v1` | Environment variables (production default) |
| `modelmesh.dotenv.v1` | `.env` file (local development) |
| `modelmesh.json-secrets.v1` | JSON file with dot-notation path support |
| `modelmesh.memory-secrets.v1` | In-memory dictionary (testing) |
| `modelmesh.encrypted-file.v1` | AES-256-GCM encrypted JSON file |
| `modelmesh.keyring.v1` | OS keyring (macOS Keychain, Windows Credential Locker) |
| `modelmesh.browser-secrets.v1` | localStorage-backed (TypeScript browser only) |

```yaml
secrets:
  store: modelmesh.env.v1
  config:
    prefix: MODELMESH_   # only read env vars starting with this prefix
```

```python
# Or inject via API
from modelmesh.connectors import EncryptedFileSecretStore

store = EncryptedFileSecretStore({"path": "secrets.enc", "password": "..."})
mesh.initialize(MeshConfig(raw={
    "secrets": {"instance": store},
    # ...
}))
```

### Storage

6 built-in backends:

| Connector ID | Use Case |
|---|---|
| `modelmesh.local-file.v1` | JSON file (single-process, development) |
| `modelmesh.sqlite.v1` | SQLite database (queryable, single-process) |
| `modelmesh.memory.v1` | In-memory (ephemeral, testing) |
| `modelmesh.localstorage.v1` | Browser localStorage (TS only) |
| `modelmesh.sessionstorage.v1` | Browser sessionStorage (TS only) |
| `modelmesh.indexeddb.v1` | Browser IndexedDB (TS only) |

```yaml
storage:
  connector: modelmesh.sqlite.v1
  config:
    path: ./mesh-state.db
```

Traces include severity levels (DEBUG, INFO, WARNING, ERROR) with component context (router, pool, provider) so you can filter by the subsystem you care about.

See the [Connector Catalogue](../ConnectorCatalogue.md) for full config reference and [System Configuration](../SystemConfiguration.md) for the complete YAML schema.

---

## 10. What if the pre-built connectors don't cover my use case?

Use the **CDK (Connector Development Kit)**. Each of the 6 connector types has a base class you inherit from. Override only the methods you need, then plug the connector in via API or YAML.

### Extension reference

| What to Extend | Base Class (Python) | Base Class (TypeScript) | Key Override Methods |
|---|---|---|---|
| **Provider** | `BaseProvider` | `BaseProvider` | `_build_request_payload()`, `_parse_response()`, `_build_headers()` |
| **Rotation** | `BaseRotationPolicy` | `BaseRotationPolicy` | `select()`, `should_deactivate()`, `should_recover()` |
| **Secret Store** | `BaseSecretStore` | `BaseSecretStore` | `_resolve(name)` |
| **Storage** | `BaseStorage` | `BaseStorage` | `load()`, `save()`, `list()`, `delete()` |
| **Observability** | `BaseObservability` | `BaseObservability` | `_write(line)`, `_format_event()` |
| **Discovery** | `BaseDiscovery` | `BaseDiscovery` | `probe()`, `_discover_provider_models()` |

> Interface specs: [Connector Interfaces](../ConnectorInterfaces.md) | Pre-shipped list: [Connector Catalogue](../ConnectorCatalogue.md)

### Where to place custom connector code

Three deployment options, depending on your project structure:

**1. Same project** — define your class anywhere in your codebase and pass a pre-built instance:

```python
from my_app.connectors import VaultSecretStore

store = VaultSecretStore({"vault_url": "https://vault.corp"})
mesh.initialize(MeshConfig(raw={
    "secrets": {"instance": store},
    # ...
}))
```

**2. Shared package** — publish your connector as a PyPI/npm package and import normally:

```python
# pip install my-modelmesh-connectors
from my_modelmesh_connectors import VaultSecretStore
```

```typescript
// npm install @corp/modelmesh-connectors
import { VaultSecretStore } from "@corp/modelmesh-connectors";
```

**3. Runtime registration** — register the class in the global `CONNECTOR_REGISTRY` so YAML configs can reference it by connector ID:

```python
from modelmesh import register_connector
from my_app.connectors import VaultSecretStore

register_connector("corp.vault-secrets.v1", VaultSecretStore)
```

```typescript
import { registerConnector } from "@nistrapa/modelmesh-core";
import { VaultSecretStore } from "./connectors/vault-store";

registerConnector("corp.vault-secrets.v1", VaultSecretStore);
```

After registration, your YAML config can reference it by ID:

```yaml
secrets:
  store: corp.vault-secrets.v1
  config:
    vault_url: https://vault.corp
```

### Custom provider

When your API follows the OpenAI format, use the quick shortcut:

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

When your API uses a different format, inherit from `BaseProvider` and override four hook methods. BaseProvider handles HTTP transport, retries, and error classification; you only translate request and response formats.

<details>
<summary>Python — custom provider for non-OpenAI API</summary>

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
```

</details>

<details>
<summary>TypeScript — custom provider for non-OpenAI API</summary>

```typescript
import { BaseProvider, createBaseProviderConfig } from "@nistrapa/modelmesh-core";
import type { CompletionRequest, CompletionResponse } from "@nistrapa/modelmesh-core";

class CorpLLMProvider extends BaseProvider {
  protected _getCompletionEndpoint(): string {
    return `${this._config.baseUrl.replace(/\/$/, "")}/api/generate`;
  }

  protected _buildHeaders(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      "X-Corp-Token": this._config.apiKey,
    };
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, unknown> {
    return {
      prompt: request.messages[request.messages.length - 1].content,
      model_name: request.model,
      params: { temperature: request.temperature ?? 0.7 },
    };
  }

  protected _parseResponse(data: Record<string, unknown>): CompletionResponse {
    return {
      id: (data.request_id as string) ?? "",
      model: (data.model as string) ?? "",
      choices: [{
        index: 0,
        message: { role: "assistant", content: data.output as string },
        finishReason: "stop",
      }],
      usage: {
        promptTokens: (data.tokens_in as number) ?? 0,
        completionTokens: (data.tokens_out as number) ?? 0,
        totalTokens: ((data.tokens_in as number) ?? 0) + ((data.tokens_out as number) ?? 0),
      },
    };
  }
}
```

</details>

Override only what differs: `_get_completion_endpoint()` for the URL path, `_build_headers()` for authentication, `_build_request_payload()` to translate the request format, and `_parse_response()` to translate the response back. For streaming, also override `_parse_sse_chunk()`.

### Custom rotation policy

Inherit from `BaseRotationPolicy` and override `select()` to control how models are chosen, `should_deactivate()` to control when a model is taken offline, or `should_recover()` to control when it comes back.

<details>
<summary>Python — custom rotation policy</summary>

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
        return min(candidates, key=lambda c: (c.total_cost, c.error_rate))
```

</details>

<details>
<summary>TypeScript — custom rotation policy</summary>

```typescript
import { BaseSelectionStrategy } from "@nistrapa/modelmesh-core";
import type { ModelState, CompletionRequest } from "@nistrapa/modelmesh-core";

class CostAwareStrategy extends BaseSelectionStrategy {
  select(candidates: ModelState[], request: CompletionRequest): ModelState | null {
    if (candidates.length === 0) return null;
    return candidates.reduce((cheapest, c) =>
      c.totalCost < cheapest.totalCost ? c : cheapest
    );
  }
}
```

</details>

Register via YAML or inject as an instance:

```yaml
pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: corp.cost-aware.v1   # after register_connector()
```

```python
mesh.initialize(MeshConfig(raw={
    "pools": {
        "chat": {
            "capability": "generation.text-generation.chat-completion",
            "strategy_instance": CostAwarePolicy(BaseRotationConfig(
                failure_threshold=5, cooldown_seconds=120,
            )),
        }
    },
}))
```

### Custom secret store

Override `_resolve(name)` to fetch secrets from your backend. The base class handles caching, TTL, and fail-on-missing logic.

<details>
<summary>Python — custom secret store</summary>

```python
from modelmesh.cdk import BaseSecretStore, BaseSecretStoreConfig

class VaultSecretStore(BaseSecretStore):
    """Resolve secrets from HashiCorp Vault."""

    def __init__(self, config: dict):
        super().__init__(BaseSecretStoreConfig(
            cache_enabled=True,
            cache_ttl_ms=60_000,
        ))
        self._vault_url = config["vault_url"]

    def _resolve(self, name: str) -> str | None:
        # Your Vault API call here
        import requests
        resp = requests.get(
            f"{self._vault_url}/v1/secret/data/{name}",
            headers={"X-Vault-Token": self._vault_token},
        )
        if resp.ok:
            return resp.json()["data"]["data"]["value"]
        return None
```

</details>

<details>
<summary>TypeScript — custom secret store</summary>

```typescript
import { BaseSecretStore } from "@nistrapa/modelmesh-core";
import type { BaseSecretStoreConfig } from "@nistrapa/modelmesh-core";

class VaultSecretStore extends BaseSecretStore {
  private _vaultUrl: string;

  constructor(config: { vault_url: string }) {
    super({ cacheEnabled: true, cacheTtlMs: 60_000 });
    this._vaultUrl = config.vault_url;
  }

  protected _resolve(name: string): string | null {
    // Your Vault API call here (sync or use cached approach)
    return null; // Replace with actual implementation
  }
}
```

</details>

### Custom storage backend

Override `load()`, `save()`, `list()`, and `delete()` to persist model state to your backend.

<details>
<summary>Python — custom storage backend</summary>

```python
from modelmesh.cdk import BaseStorage, BaseStorageConfig

class RedisStorage(BaseStorage):
    """Persist model state to Redis."""

    def __init__(self, config: dict):
        super().__init__(BaseStorageConfig())
        import redis
        self._client = redis.Redis(host=config.get("host", "localhost"))

    def load(self, key: str):
        data = self._client.get(f"modelmesh:{key}")
        if data:
            import json
            return json.loads(data)
        return None

    def save(self, key: str, entry) -> None:
        import json
        self._client.set(f"modelmesh:{key}", json.dumps(entry))

    def list(self, prefix: str | None = None) -> list[str]:
        pattern = f"modelmesh:{prefix}*" if prefix else "modelmesh:*"
        return [k.decode().removeprefix("modelmesh:") for k in self._client.keys(pattern)]

    def delete(self, key: str) -> bool:
        return self._client.delete(f"modelmesh:{key}") > 0
```

</details>

<details>
<summary>TypeScript — custom storage backend</summary>

```typescript
import { BaseStorage } from "@nistrapa/modelmesh-core";
import type { StorageEntry } from "@nistrapa/modelmesh-core";

class RedisStorage extends BaseStorage {
  private _client: RedisClient;

  constructor(config: { host?: string }) {
    super({});
    this._client = createRedisClient(config.host ?? "localhost");
  }

  async load(key: string): Promise<StorageEntry | null> {
    const data = await this._client.get(`modelmesh:${key}`);
    return data ? JSON.parse(data) : null;
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    await this._client.set(`modelmesh:${key}`, JSON.stringify(entry));
  }

  async list(prefix?: string): Promise<string[]> {
    const pattern = prefix ? `modelmesh:${prefix}*` : "modelmesh:*";
    const keys = await this._client.keys(pattern);
    return keys.map((k: string) => k.replace("modelmesh:", ""));
  }

  async delete(key: string): Promise<boolean> {
    return (await this._client.del(`modelmesh:${key}`)) > 0;
  }
}
```

</details>

### Custom observability sink

Override `_write(line)` to send formatted trace data to your monitoring system. The base class handles event filtering, severity levels, secret redaction, and formatting.

<details>
<summary>Python — custom observability sink</summary>

```python
from modelmesh.cdk import BaseObservability, BaseObservabilityConfig

class DatadogObservability(BaseObservability):
    """Send traces and events to Datadog."""

    def __init__(self, config: dict):
        super().__init__(BaseObservabilityConfig(
            log_level="metadata",
            min_severity="info",
        ))
        self._dd_api_key = config["api_key"]

    def _write(self, line: str) -> None:
        # Send to Datadog Logs API
        import requests
        requests.post(
            "https://http-intake.logs.datadoghq.com/api/v2/logs",
            headers={"DD-API-KEY": self._dd_api_key},
            json={"message": line, "service": "modelmesh"},
        )
```

</details>

### Plugging custom connectors in

Every custom connector can be used in two ways:

**Instance injection (API)** — pass a pre-built object directly in config:

```python
mesh.initialize(MeshConfig(raw={
    "providers": {"my-llm": {"connector": "custom.v1", "instance": my_provider}},
    "observability": {"instance": my_observability},
    "storage": {"instance": my_storage},
    "secrets": {"instance": my_secret_store},
    "pools": {
        "chat": {
            "capability": "generation.text-generation.chat-completion",
            "strategy_instance": my_rotation_policy,
        }
    },
}))
```

**Registry + YAML** — register the class, then reference it by connector ID:

```python
from modelmesh import register_connector

register_connector("corp.vault-secrets.v1", VaultSecretStore)
register_connector("corp.redis-storage.v1", RedisStorage)
register_connector("corp.datadog-obs.v1", DatadogObservability)
register_connector("corp.cost-aware.v1", CostAwarePolicy)
```

```yaml
secrets:
  store: corp.vault-secrets.v1
  config:
    vault_url: https://vault.corp
storage:
  connector: corp.redis-storage.v1
  config:
    host: redis.corp
observability:
  connector: corp.datadog-obs.v1
  config:
    api_key: "${secrets:DD_API_KEY}"
pools:
  chat:
    capability: generation.text-generation.chat-completion
    strategy: corp.cost-aware.v1
```

See the [Connector Catalogue](../ConnectorCatalogue.md) for all pre-shipped connectors and [Connector Interfaces](../ConnectorInterfaces.md) for interface specifications.

---

## 11. How do I intercept requests and responses with middleware?

Use the `Middleware` base class. Override `before_request` to modify or log outgoing requests, `after_response` to enrich or cache responses, and `on_error` to provide fallback responses when a provider fails.

**Python:**

```python
import modelmesh
from modelmesh import Middleware, MiddlewareContext
from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse

class LoggingMiddleware(Middleware):
    async def before_request(
        self, request: CompletionRequest, context: MiddlewareContext,
    ) -> CompletionRequest:
        print(f">>> {context.pool_name} → {context.model_id} (attempt {context.attempt})")
        return request

    async def after_response(
        self, response: CompletionResponse, context: MiddlewareContext,
    ) -> CompletionResponse:
        tokens = response.usage.total_tokens if response.usage else 0
        print(f"<<< {context.model_id}: {tokens} tokens")
        return response

    async def on_error(
        self, error: Exception, context: MiddlewareContext,
    ) -> CompletionResponse:
        print(f"!!! {context.model_id}: {error}")
        raise error  # re-raise to let the router handle rotation

client = modelmesh.create("chat-completion", middleware=[LoggingMiddleware()])
```

**TypeScript:**

```typescript
import { create, Middleware, MiddlewareContext } from "@nistrapa/modelmesh-core";
import type { CompletionRequest, CompletionResponse } from "@nistrapa/modelmesh-core";

class LoggingMiddleware extends Middleware {
  async beforeRequest(request: CompletionRequest, context: MiddlewareContext): Promise<CompletionRequest> {
    console.log(`>>> ${context.poolName} → ${context.modelId}`);
    return request;
  }

  async afterResponse(response: CompletionResponse, context: MiddlewareContext): Promise<CompletionResponse> {
    console.log(`<<< ${context.modelId}: ${response.usage?.totalTokens} tokens`);
    return response;
  }
}

const client = create("chat-completion", { middleware: [new LoggingMiddleware()] });
```

Middleware runs in **onion order**: `before_request` hooks fire first-registered-first, `after_response` hooks fire in reverse order. Multiple middlewares compose naturally — add logging, caching, and rate limiting as separate classes.

See the [Middleware](Middleware.md) guide.

---

## 12. How do I handle errors and retries?

ModelMesh has a structured [exception hierarchy](ErrorHandling.md). Catch specific exceptions for fine-grained control, or catch the base `ModelMeshError` for broad handling.

```python
from modelmesh.exceptions import (
    ModelMeshError,
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
except BudgetExceededError as e:
    print(f"Budget: {e.limit_type} limit ${e.limit_value} reached")
except AllProvidersExhaustedError as e:
    print(f"All {e.attempts} providers failed: {e.last_error}")
except ModelMeshError as e:
    if e.retryable:
        # Safe to retry — transient failure
        import time
        time.sleep(getattr(e, "retry_after", 5))
```

```typescript
import {
  ModelMeshError, RateLimitError, BudgetExceededError, AllProvidersExhaustedError,
} from "@nistrapa/modelmesh-core";

try {
  const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hello" }],
  });
} catch (e) {
  if (e instanceof RateLimitError) {
    console.log(`Rate limited, retry after ${e.retryAfter}s`);
  } else if (e instanceof BudgetExceededError) {
    console.log(`Budget: ${e.limitType} limit $${e.limitValue} reached`);
  } else if (e instanceof AllProvidersExhaustedError) {
    console.log(`All ${e.attempts} attempts failed`);
  }
}
```

Every exception carries a `retryable` flag — check it to decide whether retrying makes sense. The router already retries internally per its configured policy; these exceptions surface only when all retry/rotation attempts are exhausted.

See the [Error Handling](ErrorHandling.md) guide.

---

## 13. How do I deploy ModelMesh as an HTTP proxy?

Run the [Docker proxy](ProxyGuide.md) and point any OpenAI SDK client at it. The proxy speaks the standard OpenAI REST API with full ModelMesh routing behind it.

**Docker Compose:**

```yaml
# docker-compose.yml
services:
  modelmesh:
    image: ghcr.io/apartsinprojects/modelmesh:latest
    ports:
      - "8080:8080"
    env_file: .env
    volumes:
      - ./modelmesh.yaml:/app/modelmesh.yaml:ro
```

```bash
docker compose up -d
```

**Any language can now call it:**

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-proxy-token" \
  -d '{"model":"chat-completion","messages":[{"role":"user","content":"Hello"}]}'
```

**Python client pointing at the proxy:**

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="my-proxy-token")
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello"}],
)
```

**Proxy-specific YAML settings:**

```yaml
proxy:
  port: 8080
  host: "0.0.0.0"
  token: "my-proxy-token"         # Bearer token for proxy auth
  cors:
    enabled: true
    allowed_origins: ["*"]
```

See the [Proxy Guide](ProxyGuide.md) for authentication, CORS, streaming, and production deployment.

---

## 14. How do I persist model state across restarts?

Configure a [storage backend](../SystemConfiguration.md#storage). ModelMesh saves model health scores, cost accumulators, and rotation state so pools resume from where they left off.

```yaml
storage:
  connector: modelmesh.sqlite.v1
  config:
    path: ./mesh-state.db
```

```python
import modelmesh

# State persists to SQLite — restarts pick up where they left off
client = modelmesh.create(config="modelmesh.yaml")

# Check stored state
print(client.usage.total_cost)      # Accumulated across restarts
print(client.pool_status())         # Model health scores preserved
```

6 built-in backends (see [Q9](#9-how-do-i-configure-infrastructure-connectors-observability-storage-secrets) for the full table):

| Backend | Best for |
|---------|----------|
| `modelmesh.sqlite.v1` | Production single-process (recommended) |
| `modelmesh.local-file.v1` | Simple JSON file |
| `modelmesh.memory.v1` | Testing (ephemeral) |
| `modelmesh.localstorage.v1` | Browser (TypeScript) |
| `modelmesh.sessionstorage.v1` | Browser sessions (TypeScript) |
| `modelmesh.indexeddb.v1` | Browser persistent (TypeScript) |

For a custom backend (Redis, PostgreSQL), see [Q10](#10-what-if-the-pre-built-connectors-dont-cover-my-use-case).

---

## 15. How do I add production observability (logging, metrics, traces)?

Configure an [observability connector](../SystemConfiguration.md#observability). Every routing decision, model selection, error, and cost event flows through the observability pipeline.

```yaml
observability:
  connector: modelmesh.console.v1
  config:
    log_level: metadata        # "silent" | "summary" | "metadata" | "full"
    min_severity: info         # "debug" | "info" | "warning" | "error"
    use_color: true
```

**Structured JSON logs (for log aggregation):**

```yaml
observability:
  connector: modelmesh.json-log.v1
  config:
    log_level: metadata
    min_severity: info
```

**Webhook alerts (PagerDuty, Slack):**

```yaml
observability:
  connector: modelmesh.webhook.v1
  config:
    url: https://hooks.slack.com/services/T.../B.../xxx
    min_severity: warning      # Only alert on warnings and errors
```

**Prometheus metrics:**

```yaml
observability:
  connector: modelmesh.prometheus.v1
  config:
    port: 9090
    path: /metrics
```

**Custom observability via API:**

```python
from modelmesh.cdk import BaseObservability, BaseObservabilityConfig

class DatadogSink(BaseObservability):
    def _write(self, line: str) -> None:
        # Send to your monitoring system
        requests.post("https://api.datadoghq.com/v2/logs", ...)

mesh.initialize(MeshConfig(raw={
    "observability": {"instance": DatadogSink(BaseObservabilityConfig())},
}))
```

Traces include severity levels (DEBUG, INFO, WARNING, ERROR) with component context (router, pool, provider) so you can filter by the subsystem you care about. See [Q9](#9-how-do-i-configure-infrastructure-connectors-observability-storage-secrets) for the full connector table.

---

## 16. How do I stream responses?

Set `stream=True` in the request. ModelMesh streams chunks from the selected provider. If the provider fails mid-stream, the router rotates to the next provider and restarts the stream.

**Python:**

```python
import modelmesh

client = modelmesh.create("chat-completion")

stream = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Write a poem about AI"}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta
    if delta and delta.content:
        print(delta.content, end="", flush=True)
print()  # newline at the end
```

**TypeScript:**

```typescript
import { create } from "@nistrapa/modelmesh-core";

const client = create("chat-completion");

const stream = await client.chat.completions.create({
  model: "chat-completion",
  messages: [{ role: "user", content: "Write a poem about AI" }],
  stream: true,
});

for await (const chunk of stream) {
  const delta = chunk.choices[0]?.delta;
  if (delta?.content) {
    process.stdout.write(delta.content);
  }
}
```

Streaming works with all rotation strategies and [budget-aware rotation](FAQ.md#6-how-do-i-prevent-surprise-ai-bills). The router applies the same failover logic to streaming as to non-streaming requests.

---

## 17. How does auto-discovery work?

Set API keys as environment variables. ModelMesh detects available providers, enumerates their models, and builds pools automatically — no YAML file needed.

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
```

```python
import modelmesh

# Auto-discovery runs at create() time
client = modelmesh.create("chat-completion")

# See what was discovered
print(modelmesh.capabilities.list_all())
# ['chat-completion', 'code-generation', 'text-embeddings', ...]

print(client.pool_status())
# {'chat-completion': {'active': 8, 'standby': 0, 'total': 8}}
```

**For explicit control over discovery:**

```yaml
discovery:
  connector: modelmesh.auto-discovery.v1
  config:
    providers: ["openai", "anthropic"]     # Only discover these
    include_patterns: ["gpt-4*", "claude-*"]
    exclude_patterns: ["*-mini"]
```

Auto-discovery checks for known environment variable patterns (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, etc.) and registers models with their full [capability paths](../ModelCapabilities.md).

---

## 18. Can I define multiple pools with different strategies?

Yes. Each pool targets a [capability node](../ModelCapabilities.md) and can have its own rotation strategy, failure threshold, and budget policy.

```yaml
pools:
  # Fast responses — pick the lowest latency model
  chat-fast:
    capability: generation.text-generation.chat-completion
    strategy: modelmesh.latency-first.v1

  # Cost-sensitive batch — pick the cheapest model
  chat-cheap:
    capability: generation.text-generation.chat-completion
    strategy: modelmesh.cost-first.v1
    on_budget_exceeded: rotate

  # Code review — priority ordering with specific models
  code-review:
    capability: generation.text-generation.code-generation
    strategy: modelmesh.priority-selection.v1

  # Embeddings — round-robin across providers
  embeddings:
    capability: representation.embeddings.text-embeddings
    strategy: modelmesh.round-robin.v1
```

```python
import modelmesh

client = modelmesh.create(config="modelmesh.yaml")

# Each pool is addressed by its name
fast = client.chat.completions.create(model="chat-fast", messages=[...])
cheap = client.chat.completions.create(model="chat-cheap", messages=[...])
review = client.chat.completions.create(model="code-review", messages=[...])
```

Pools sharing the same capability can have different models if providers are filtered. Use `providers` to restrict which providers contribute models to a pool:

```yaml
pools:
  chat-openai-only:
    capability: generation.text-generation.chat-completion
    providers: ["openai"]
    strategy: modelmesh.stick-until-failure.v1
```

---

## 19. Can I reload configuration without restarting?

Yes. Use `ConfigWatcher` for automatic file-based reloading, or call `reconfigure()` programmatically.

**File-based auto-reload:**

```python
from modelmesh.config.hot_reload import ConfigWatcher

mesh = modelmesh.ModelMesh()
mesh.initialize(MeshConfig.from_yaml("modelmesh.yaml"))

watcher = ConfigWatcher("modelmesh.yaml", mesh, interval=5.0)
watcher.start()

# Edit modelmesh.yaml while running — changes apply within 5 seconds
# watcher.stop() when shutting down
```

**Programmatic reload:**

```python
from modelmesh.config.hot_reload import reconfigure
from modelmesh.config import MeshConfig

new_config = MeshConfig.from_yaml("modelmesh-v2.yaml")
errors = reconfigure(mesh, new_config)
if errors:
    print(f"Reload failed: {errors}")
else:
    print("Configuration reloaded successfully")
```

Hot-reload is atomic: the mesh remains functional during the swap. Pools are rebuilt, secrets re-resolved, and connectors re-registered from the new configuration. In-flight requests complete with the old config; new requests use the updated config.

---

## 20. How do I use ModelMesh in the browser?

Use the TypeScript library with `BrowserBaseProvider`. Browser-compatible connectors use the Fetch API and `ReadableStream` instead of Node.js `http`.

**Direct access (provider supports CORS):**

```typescript
import { create } from "@nistrapa/modelmesh-core";

// Anthropic allows direct browser access with a special header
const client = create("chat-completion", {
  providers: [{
    connector: "anthropic.llm.v1",
    config: { apiKey: userEnteredKey },
  }],
});

const response = await client.chat.completions.create({
  model: "chat-completion",
  messages: [{ role: "user", content: "Hello from the browser!" }],
});
```

**With CORS proxy (when the provider blocks browser requests):**

```typescript
import { BrowserBaseProvider, createBrowserProviderConfig } from "@nistrapa/modelmesh-core";

const provider = new BrowserBaseProvider(createBrowserProviderConfig({
  baseUrl: "https://api.openai.com",
  apiKey: userEnteredKey,
  proxyUrl: "http://localhost:3000/proxy/",  // Your CORS proxy
}));
```

**Browser-compatible storage and secrets:**

```yaml
storage:
  connector: modelmesh.localstorage.v1    # Browser localStorage

secrets:
  store: modelmesh.browser-secrets.v1     # Browser localStorage for keys
```

For bundling, ModelMesh is tree-shakeable — only browser-compatible connectors are included. See the [Browser Usage](BrowserUsage.md) guide for the CORS proxy setup and security considerations.

---

## 21. Can I use TypeScript without a CORS proxy?

Yes — in two scenarios where CORS restrictions don't apply:

**1. Node.js / Deno / Bun server-side:**

No CORS restrictions exist outside the browser. Use the standard `BaseProvider`:

```typescript
import { create } from "@nistrapa/modelmesh-core";

// Server-side — no CORS, no proxy needed
const client = create("chat-completion");

const response = await client.chat.completions.create({
  model: "chat-completion",
  messages: [{ role: "user", content: "Hello from Node.js" }],
});
```

**2. Chrome Extension with host permissions:**

Chrome extensions can call any API directly if the manifest declares `host_permissions`:

```json
// manifest.json (Manifest V3)
{
  "manifest_version": 3,
  "permissions": ["storage"],
  "host_permissions": [
    "https://api.openai.com/*",
    "https://api.anthropic.com/*",
    "https://generativelanguage.googleapis.com/*"
  ]
}
```

```typescript
// background.ts or content script
import { create, BrowserBaseProvider, createBrowserProviderConfig } from "@nistrapa/modelmesh-core";

const provider = new BrowserBaseProvider(createBrowserProviderConfig({
  baseUrl: "https://api.openai.com",
  apiKey: await chrome.storage.local.get("apiKey"),
  // No proxyUrl needed — extension has host_permissions
}));

const client = create("chat-completion", {
  providers: [{ connector: "openai", instance: provider }],
  storage: { connector: "modelmesh.localstorage.v1" },
  secrets: { store: "modelmesh.browser-secrets.v1" },
});
```

The `BrowserBaseProvider` uses the Fetch API internally, which works in both browser contexts and Chrome extension service workers. No Node.js dependencies are required.

See the [Browser Usage](BrowserUsage.md) guide for security considerations and the [Proxy Guide](ProxyGuide.md) for when you do need a CORS proxy.

---

## Reference

| Document | What it covers |
|----------|---------------|
| [System Concept](../SystemConcept.md) | Architecture overview — routing pipeline, pools, providers |
| [Model Capabilities](../ModelCapabilities.md) | Complete capability hierarchy tree |
| [System Configuration](../SystemConfiguration.md) | YAML schema reference for all sections |
| [System Services](../SystemServices.md) | Runtime objects — Router, Pool, Model, StateManager |
| [Connector Catalogue](../ConnectorCatalogue.md) | All 54 pre-shipped connectors with config schemas |
| [Connector Interfaces](../ConnectorInterfaces.md) | Interface specs for all 6 connector types |
| [Quick Start](QuickStart.md) | 5-minute hands-on tutorial |
| [Error Handling](ErrorHandling.md) | Exception hierarchy and retry guidance |
| [Middleware](Middleware.md) | Request/response interception patterns |
| [Testing](Testing.md) | Mock client for unit tests |
| [Capabilities](Capabilities.md) | Capability discovery API |
| [Secret Stores](SecretStores.md) | Secret store configuration and usage |
| [Browser Usage](BrowserUsage.md) | Browser-specific setup and CORS |
| [Proxy Guide](ProxyGuide.md) | Docker proxy deployment |
