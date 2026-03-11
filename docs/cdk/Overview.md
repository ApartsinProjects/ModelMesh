---
layout: default
title: "Connector Development Kit (CDK)"
---

# Connector Development Kit (CDK)

The Connector Development Kit (CDK) is the class library used to build both pre-shipped and custom connectors for ModelMesh Lite. It sits between the raw connector interfaces and the finished connectors that ship with the library, providing generic base classes with sensible default behavior, specialized classes pre-configured for common scenarios, and cross-cutting mixins for capabilities shared across connector types. The CDK exists so that building a new connector requires the minimum possible code: most connectors can be created with configuration alone, and even complex integrations only need to override the methods that differ from the defaults.

---

## Design Principles

1. **Ease of Use** -- The simplest connector should require no code at all. A YAML configuration block that references a specialized class and supplies an API key is a complete connector.

2. **Uniformity** -- Every connector type follows the same pattern: an abstract interface, a base class with default implementations, and specialized subclasses for common backends. Developers who learn one connector type can apply the same mental model to all six.

3. **Layered Complexity** -- Simple needs are met with simple tools. Configuration-only connectors cover the common case; base-class derivation handles intermediate needs; raw interface implementation is available for full control. Each layer builds on the one below it.

4. **Sensible Defaults** -- Base classes provide working default implementations for every method in the interface. Defaults are safe, correct, and production-ready (e.g., retry logic, error classification, caching) so that a subclass only needs to override what is genuinely different.

5. **Override, Don't Rewrite** -- Customization is always additive. Subclasses override individual methods and inherit everything else. There is never a reason to copy-paste an entire class just to change one behavior.

---

## Class Hierarchy

```
Convenience Layer (OpenAI-compatible entry point)
│
├── modelmesh.create()        ── returns OpenAI SDK-compatible MeshClient
├── MeshClient                ── drop-in replacement for openai.OpenAI()
└── QuickProvider             ── minimal provider (base_url + api_key only)
     │
     ▼
Interfaces (abstract contracts -- one per connector type)
│
├── ProviderConnector
├── DeactivationPolicy / RecoveryPolicy / SelectionStrategy
├── SecretStoreConnector
├── StorageConnector
├── ObservabilityConnector
└── DiscoveryConnector
     │
     ▼
Base Classes (default implementations -- one per connector type)
│
├── BaseProvider             ── Node.js provider (http/https transport)
├── BrowserBaseProvider      ── Browser/edge provider (fetch API, ReadableStream, CORS proxy)
├── BaseRotationPolicy
├── BaseSecretStore
├── BaseStorage
├── BaseObservability
└── BaseDiscovery
     │
     ▼
Specialized Classes (pre-configured for common backends)
│
├── HttpApiProvider          ── REST APIs with custom request/response formats
├── OpenAICompatibleProvider ── APIs that follow the OpenAI chat completions spec
├── ThresholdRotationPolicy  ── Deactivation/recovery driven by numeric thresholds
├── FileSecretStore          ── File-backed secret store (.env, JSON, TOML)
├── KeyValueStorage          ── Pluggable key-value storage (memory or file backend)
├── ConsoleObservability     ── ANSI-colored console output for development
├── FileObservability        ── Structured JSONL file output for logging
├── NullObservability        ── No-op connector that discards all output (zero overhead)
└── HttpHealthDiscovery      ── HTTP-based health probes against provider endpoints
     │
     ▼
Mixins (cross-cutting capabilities -- compose with any class)
│
├── RetryMixin               ── Configurable retry with exponential backoff
├── CacheMixin               ── In-memory TTL cache for secrets, catalogue data
├── RateLimiterMixin          ── Client-side rate limiting and request shaping
├── MetricsMixin              ── Automatic latency, error rate, and throughput tracking
└── SerializationMixin        ── JSON / YAML / MsgPack serialization helpers
```

---

## Four Ways to Use ModelMesh

The CDK supports four approaches, each suited to a different level of customization. The convenience layer lets you consume AI capabilities with no connector knowledge at all; the remaining three produce connectors that are indistinguishable from pre-shipped ones at runtime.

### 0. Use the Convenience Layer (Zero Code, OpenAI-Compatible)

If you just want to use AI capabilities, `modelmesh.create()` returns an OpenAI SDK-compatible client. No connectors, no YAML, no configuration objects needed.

```python
import modelmesh

client = modelmesh.create("chat-completion")
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

```typescript
import { create } from "modelmesh";

const client = create("chat-completion");
const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);
```

> **See also:** [ConvenienceLayer.md](ConvenienceLayer.md) for full API reference, auto-detection details, and advanced usage.

### 1. Use a Specialized Class with Configuration Only (Zero Code)

If an existing specialized class already does what you need, supply configuration and you are done. No Python or TypeScript is required.

```yaml
# modelmesh.yaml -- a complete custom provider, zero code
providers:
  my-openai-proxy:
    connector: openai-compatible
    config:
      base_url: "https://my-proxy.internal/v1"
      auth:
        method: api_key
        api_key: "${secrets:proxy-key}"
      models:
        - id: "gpt-4o"
          capabilities: ["generation.text-generation.chat-completion"]
          context_window: 128000
```

### 2. Derive from a Base Class and Override Methods

When you need behavior that no specialized class provides, derive from the appropriate base class and override only the methods that differ. Everything else is inherited.

```python
from modelmesh.cdk import BaseProvider, CompletionRequest, CompletionResponse

class MyCustomProvider(BaseProvider):
    """Provider for an internal ML service with a non-standard API."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Translate to the internal API format
        payload = self._translate_request(request)
        raw = await self._http_client.post("/inference", json=payload)
        return self._translate_response(raw)

    def _translate_request(self, request):
        return {"prompt": request.messages[-1]["content"],
                "max_length": request.max_tokens or 1024}

    def _translate_response(self, raw):
        return CompletionResponse(
            id=raw["request_id"],
            model=raw["model"],
            choices=[{"message": {"content": raw["output"]}}],
            usage=TokenUsage(
                prompt_tokens=raw["input_tokens"],
                completion_tokens=raw["output_tokens"],
                total_tokens=raw["input_tokens"] + raw["output_tokens"],
            ),
        )
    # All other methods (capabilities, catalogue, quota, cost,
    # error classification) use BaseProvider defaults.
```

### 3. Derive from an Existing Pre-Shipped Connector

When a pre-shipped connector is close to what you need but requires a small adjustment (different error handling, extra headers, modified pricing logic), derive from it directly.

```python
from modelmesh.connectors.openai import OpenAIProvider

class AzureOpenAIProvider(OpenAIProvider):
    """OpenAI connector adapted for Azure-hosted deployments."""

    def __init__(self, config):
        super().__init__(config)
        self._base_url = (
            f"https://{config['resource']}.openai.azure.com"
            f"/openai/deployments/{config['deployment']}"
        )

    def _get_headers(self):
        headers = super()._get_headers()
        headers["api-key"] = self._api_key  # Azure uses api-key header
        return headers

    # Everything else (completion, streaming, catalogue, retry,
    # error classification) is inherited from OpenAIProvider.
```

---

## When to Use What -- Decision Tree

Use the decision trees below to choose the right starting point for each connector type.

### Provider

```
Will this provider run in a web browser or edge runtime (Deno, Workers)?
├── Yes ──► BrowserBaseProvider (fetch-based, supports proxyUrl for CORS)
└── No
    Is the API OpenAI-compatible (chat completions format)?
    ├── Yes ──► OpenAICompatibleProvider (config only)
    └── No
        ├── Is it a standard REST API with JSON request/response?
        │   ├── Yes ──► HttpApiProvider (override translate methods)
        │   └── No ──► BaseProvider (override complete + stream)
        └── Need full control over every sub-interface?
            └── Yes ──► Implement ProviderConnector interface directly
```

### Rotation Policy

```
Are your rules based on numeric thresholds (error count, quota, cost)?
├── Yes ──► ThresholdRotationPolicy (config only)
└── No
    ├── Need custom selection logic (session affinity, geo-routing)?
    │   └── Yes ──► BaseRotationPolicy (override select)
    └── Need full control over deactivation + recovery + selection?
        └── Yes ──► Implement DeactivationPolicy / RecoveryPolicy /
                     SelectionStrategy interfaces directly
```

### Secret Store

```
Is the backend a local file (.env, JSON, TOML)?
├── Yes ──► FileSecretStore (config only)
└── No
    ├── Is it a key-value store with get/set/delete semantics?
    │   └── Yes ──► BaseSecretStore (override _resolve)
    └── Need full control?
        └── Yes ──► Implement SecretStoreConnector interface directly
```

### Storage

```
Does a key-value storage backend (memory or file) fit your needs?
├── Yes ──► KeyValueStorage (config only)
└── No
    ├── Is it a key-value or object store (S3, GCS, Redis)?
    │   └── Yes ──► BaseStorage (override load + save)
    └── Need full control over locking or inventory?
        └── Yes ──► Implement StorageConnector interface directly
```

### Observability

```
Do you need observability at all?
├── No ──► NullObservability (zero overhead, discards all output)
└── Yes
    ├── Do you want ANSI-colored console output for development?
    │   └── Yes ──► ConsoleObservability (config only)
    ├── Do you want structured JSONL file output?
    │   └── Yes ──► FileObservability (config only)
    ├── Is the output an HTTP endpoint (webhook, log aggregator)?
    │   └── Yes ──► BaseObservability (override _write)
    └── Need full control?
        └── Yes ──► Implement ObservabilityConnector interface directly
```

### Discovery

```
Does the provider expose an HTTP health endpoint?
├── Yes ──► HttpHealthDiscovery (config only)
└── No
    ├── Need custom sync logic or non-HTTP health probes?
    │   └── Yes ──► BaseDiscovery (override sync + probe)
    └── Need full control?
        └── Yes ──► Implement DiscoveryConnector interface directly
```

---

## CDK vs Raw Interfaces

The CDK dramatically reduces the amount of code required to build a connector. The table below compares approximate lines of code for representative scenarios.

| Scenario | Raw Interface | CDK (Base Class) | CDK (Specialized) | Reduction |
| --- | --- | --- | --- | --- |
| Simple AI API call (chat completion) | ~106 lines | N/A | ~4 lines (convenience) | ~96% |
| Custom provider (proprietary REST API) | ~700 lines | ~80 lines | -- | ~89% |
| OpenAI-compatible provider | ~700 lines | ~80 lines | ~10 lines (config) | ~99% |
| Threshold-based rotation policy | ~300 lines | ~50 lines | ~10 lines (config) | ~97% |
| Environment-variable secret store | ~100 lines | ~20 lines | ~5 lines (config) | ~95% |
| File-system storage backend | ~400 lines | ~60 lines | ~10 lines (config) | ~98% |
| JSON file observability output | ~250 lines | ~40 lines | ~10 lines (config) | ~96% |
| Polling-based discovery connector | ~350 lines | ~50 lines | ~10 lines (config) | ~97% |

**What the CDK provides for free** (inherited from base classes):

- Authentication handling (API key, OAuth, service account)
- Retry logic with configurable exponential backoff
- Error classification (retryable vs non-retryable HTTP codes)
- Quota and rate-limit tracking
- In-memory caching with TTL
- Serialization and deserialization (JSON, YAML, MsgPack)
- Metric collection (latency, error rate, throughput)
- Configuration validation and defaults

---

## Cross-References

| Document | Description |
| --- | --- |
| [ConvenienceLayer.md](ConvenienceLayer.md) | Convenience layer API: `modelmesh.create()`, `MeshClient`, `QuickProvider`, auto-detection |
| [BaseClasses.md](BaseClasses.md) | Detailed API reference for all six base classes |
| [Mixins.md](Mixins.md) | Cross-cutting mixins: Retry, Cache, RateLimiter, Metrics, Serialization |
| [Helpers.md](Helpers.md) | Utility functions and shared helpers |
| [Enums.md](Enums.md) | Consolidated enum reference for all CDK and interface enums |
| [DeveloperGuide.md](DeveloperGuide.md) | Step-by-step tutorial for building a custom connector |
| [interfaces/](../interfaces/) | Authoritative interface definitions for all six connector types |
| [ConnectorCatalogue.md](../ConnectorCatalogue.md) | Registry of all pre-shipped connector implementations |
| [SystemConcept.md](../SystemConcept.md) | System architecture and connector extensibility model |
