---
layout: default
title: "System Configuration"
---

# System Configuration

**YAML configuration reference for ModelMesh Lite.** The system is configured declaratively via YAML, programmatically via API, or both. Configuration can be serialized to and deserialized from [storage connectors](ConnectorInterfaces.html#storage) for centralized management and sharing across instances. For the runtime objects that consume this configuration see [SystemServices.md](SystemServices.html).

---

## Top-Level Sections

| Section | Purpose |
| --- | --- |
| [`secrets`](#secrets) | Secret store backend and credential resolution |
| [`providers`](#providers) | Provider registration, authentication, quotas, and budgets |
| [`models`](#models) | Explicit model definitions (capabilities, delivery, features, constraints) |
| [`pools`](#pools) | Capability pool definitions with per-pool rotation and retry configuration |
| [`storage`](#storage) | Persistent storage backend and sync policy |
| [`observability`](#observability) | Routing events, request logging, and aggregate statistics |
| [`discovery`](#discovery) | Model registry sync and provider health monitoring |
| [`connectors`](#connectors) | Custom connector package loading |
| [`proxy`](#proxy) | OpenAI-compatible proxy deployment settings |

---

## Secrets

Configures the secret store backend. All credentials elsewhere in configuration are referenced by name (`${secrets:key-name}`) and resolved at initialization through the configured store.

| Attribute | Type | Description |
| --- | --- | --- |
| `store` | string | Secret store connector type. Pre-shipped: `modelmesh.env.v1` (default), `modelmesh.dotenv.v1`, `aws.secrets-manager.v1`, `google.secret-manager.v1`, `microsoft.key-vault.v1`, `1password.connect.v1`. |
| `path` | string | File path for `modelmesh.dotenv.v1` store. |
| `region` | string | Cloud region for cloud secret managers. |

Store-specific attributes (bucket, vault name, project ID, etc.) are passed through to the connector.

```yaml
secrets:
  store: aws.secrets-manager.v1
  region: us-east-1
```

See [ConnectorCatalogue.md — Secret Store](ConnectorCatalogue.html#secret-store-connectors) for pre-shipped stores and deployment patterns.

---

## Providers

Registers AI model providers and web API services. Each provider entry configures authentication, quota tracking, rate limits, budgets, and infrastructure capabilities. A provider can be enabled or disabled without removing its configuration.

| Attribute | Type | Description |
| --- | --- | --- |
| `enabled` | boolean | Enable or disable the provider. Default: `true`. |
| `api_key` | string | API key or token. Use secret references: `${secrets:key-name}`. |
| `base_url` | string | Custom API base URL (for self-hosted or proxy endpoints). |
| `connector` | string | Provider connector type. Defaults to provider name. |

### Authentication

| Attribute | Type | Description |
| --- | --- | --- |
| `auth.method` | string | Authentication method: `api_key`, `oauth`, `service_account`. |
| `auth.key_rotation` | boolean | Enable automatic key rotation. |

### Quota & Budgets

| Attribute | Type | Description |
| --- | --- | --- |
| `quota.query_current` | boolean | Provider API supports querying current usage. |
| `quota.query_remaining` | boolean | Provider API supports querying remaining capacity. |
| `quota.reset_schedule` | string | Quota reset frequency: `monthly`, `daily`, `rolling`. |
| `budget.daily_limit` | number | Daily spend cap in USD. |
| `budget.monthly_limit` | number | Monthly spend cap in USD. |

### Discovery

| Attribute | Type | Description |
| --- | --- | --- |
| `discovery.enumerate_models` | boolean | Auto-discover models at startup. |
| `discovery.model_details` | boolean | Query model metadata (context window, pricing). |
| `discovery.capability_query` | boolean | Query which capabilities models support. |

### Infrastructure

| Attribute | Type | Description |
| --- | --- | --- |
| `batch.supported` | boolean | Provider supports batch submissions. |
| `batch.max_items` | integer | Maximum requests per batch. |
| `files.upload` | boolean | Provider supports file uploads. |
| `files.max_size` | string | Maximum file size (e.g., `512MB`). |
| `fine_tuning.supported` | boolean | Provider supports fine-tuning. |

```yaml
providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:openai-api-key}
    budget:
      daily_limit: 5.00
      monthly_limit: 50.00
    discovery:
      enumerate_models: true

  huggingface.inference.v1:
    enabled: true
    api_key: ${secrets:hf-api-key}

  anthropic.llm.v1:
    enabled: false
```

See [ConnectorCatalogue.md — Provider](ConnectorCatalogue.html#provider-connectors) for pre-shipped provider connectors and capability matrix.

---

## Models

Explicit model definitions supplement auto-discovered models. Each entry is a capability contract declaring what an application can expect. Models register at leaf nodes of the [capability hierarchy](ModelCapabilities.html) and automatically join ancestor pools.

| Attribute | Type | Description |
| --- | --- | --- |
| `provider` | string | Provider that serves this model. |
| `capabilities` | list | Capability leaf nodes (e.g., `chat-completion`, `ocr`, `tool-calling`). |

### Delivery

| Attribute | Type | Description |
| --- | --- | --- |
| `delivery.synchronous` | boolean | Supports synchronous requests. |
| `delivery.streaming` | boolean | Supports streaming responses. |
| `delivery.batch` | boolean | Supports batch submissions. |

### Batch

| Attribute | Type | Description |
| --- | --- | --- |
| `batch.max_items` | integer | Maximum requests per batch. |
| `batch.max_payload` | string | Maximum total batch size. |
| `batch.completion_window` | duration | Expected turnaround time (e.g., `24h`). |
| `batch.cost_discount` | float | Batch pricing relative to sync (e.g., `0.5` = 50% off). |
| `batch.callback` | boolean | Supports webhook notification on completion. |
| `batch.polling` | boolean | Supports status polling. |
| `batch.partial_results` | boolean | Can return completed items before batch finishes. |

### Features

| Attribute | Type | Description |
| --- | --- | --- |
| `features.tool_calling` | boolean | Supports tool/function calling. |
| `features.structured_output` | boolean | Supports structured (JSON schema) output. |
| `features.json_mode` | boolean | Supports JSON mode. |
| `features.system_prompt` | boolean | Supports system prompts. |
| `features.grounding` | boolean | Supports grounded generation. |
| `features.logprobs` | boolean | Returns log probabilities. |
| `features.fine_tunable` | boolean | Can be fine-tuned. |

### Constraints

| Attribute | Type | Description |
| --- | --- | --- |
| `constraints.context_window` | integer | Maximum context window in tokens. |
| `constraints.max_output_tokens` | integer | Maximum output tokens per request. |
| `constraints.max_images` | integer | Maximum images per request. |
| `constraints.max_file_size` | string | Maximum input file size. |
| `constraints.supported_languages` | list | Supported languages (ISO codes). |

### Capability + Delivery Matrix

Not all delivery modes are available for every capability. The matrix below shows supported combinations.

| Capability         | Sync | Stream | Batch |
| ------------------ | ---- | ------ | ----- |
| chat-completion    | yes  | yes    | yes   |
| text-to-image      | yes  | —      | yes   |
| text-embeddings    | yes  | —      | yes   |
| speech-to-text     | yes  | —      | yes   |
| text-to-speech     | yes  | yes    | yes   |
| document-parsing   | yes  | —      | yes   |
| web-search         | yes  | —      | —     |
| content-moderation | yes  | —      | yes   |

### Model Schema Example

```yaml
models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
      - generation.structured-generation.json-generation
      - understanding.vision-understanding.image-captioning
      - interaction.tool-calling
    delivery:
      synchronous: true
      streaming: true
      batch: true
    batch:
      max_items: 50000
      completion_window: 24h
      cost_discount: 0.5
    features:
      tool_calling: true
      structured_output: true
      json_mode: true
      system_prompt: true
      fine_tunable: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384
      max_images: 20
```

---

## Pools

Defines capability pools and their per-pool rotation, selection, and retry configuration. Each pool targets a node in the [capability hierarchy](ModelCapabilities.html) and automatically includes all models registered at that node or its descendants.

> **Note:** The current implementation supports `capability`, `models`, `providers`, and `strategy` pool fields. Additional fields shown below are reserved for future releases.

| Attribute | Type | Description |
| --- | --- | --- |
| `capability` | string | Capability node to target (e.g., `generation.text-generation`). Defaults to the pool name. |
| `providers` | list | Restrict pool to specific providers. |
| `excluded_providers` | list | Exclude specific providers from pool. |
| `model_priority` | list | Ordered model preference list. |
| `provider_priority` | list | Ordered provider preference list. |

### Selection Strategy

| Attribute | Type | Description |
| --- | --- | --- |
| `strategy` | string | Model selection strategy. Pre-shipped: `modelmesh.stick-until-failure.v1` (default), `modelmesh.priority-selection.v1`, `modelmesh.round-robin.v1`, `modelmesh.cost-first.v1`, `modelmesh.latency-first.v1`, `modelmesh.session-stickiness.v1`, `modelmesh.rate-limit-aware.v1`, `modelmesh.load-balanced.v1`. |
| `fallback_strategy` | string | Strategy to use when primary list is exhausted. |
| `balance_mode` | string | For `modelmesh.load-balanced.v1`: distribute by `absolute` or `relative` capacity. |

### Deactivation Triggers

**Error-based:**

| Attribute | Type | Description |
| --- | --- | --- |
| `deactivation.retry_limit` | integer | Consecutive failures before deactivation. |
| `deactivation.error_rate_threshold` | float | Error rate over sliding window (0.0–1.0). |
| `deactivation.error_codes` | list | HTTP codes that count toward deactivation (e.g., `[429, 500, 503]`). |

**Request-count-based:**

| Attribute | Type | Description |
| --- | --- | --- |
| `deactivation.request_limit` | integer | Max requests before deactivation. |
| `deactivation.token_limit` | integer | Max tokens before deactivation. |
| `deactivation.budget_limit` | number | Max spend (USD) before deactivation. |

**Time-based:**

| Attribute | Type | Description |
| --- | --- | --- |
| `deactivation.quota_window` | string | Deactivate when quota period expires: `monthly`, `daily`. |
| `deactivation.maintenance_window` | string | Scheduled deactivation (cron expression). |

### Recovery Triggers

| Attribute | Type | Description |
| --- | --- | --- |
| `recovery.cooldown` | duration | Time before standby model is reconsidered (e.g., `60s`). |
| `recovery.probe_on_start` | boolean | Test standby models at library startup. |
| `recovery.probe_interval` | duration | Periodically test standby models (e.g., `300s`). |
| `recovery.on_quota_reset` | boolean | Reactivate when provider quota resets. |
| `recovery.quota_reset_schedule` | string | Calendar schedule for quota resets: `monthly`, `daily_utc`. |

### Intelligent Retry

| Attribute | Type | Description |
| --- | --- | --- |
| `retry.max_attempts` | integer | Retries on same model before rotating. |
| `retry.backoff` | string | Backoff strategy: `fixed`, `exponential_jitter`, `retry_after`. |
| `retry.initial_delay` | duration | First retry delay (e.g., `500ms`). |
| `retry.max_delay` | duration | Maximum backoff delay (e.g., `10s`). |
| `retry.retryable_codes` | list | HTTP codes eligible for retry (e.g., `[429, 500, 502, 503]`). |
| `retry.non_retryable_codes` | list | HTTP codes that skip retry and rotate immediately (e.g., `[400, 401, 403]`). |
| `retry.scope` | string | Retry scope: `same_model`, `same_provider`, `any`. |
| `retry.honor_retry_after` | boolean | Use provider's `Retry-After` header when present. |

### Rate-Limit Handling

| Attribute | Type | Description |
| --- | --- | --- |
| `rate_limit.threshold` | float | Switch models at this fraction of the limit (0.0–1.0, e.g., `0.8`). |
| `rate_limit.min_delta` | duration | Minimum time between requests to the same model. |
| `rate_limit.max_rpm` | integer | Max requests per minute before switching models. |

**Rate-limit-aware** switches models preemptively when usage approaches a configurable threshold (`rate_limit.threshold`), with no deactivation — just a proactive switch. **Load-balanced** distributes requests by rate-limit headroom: `absolute` mode distributes evenly across models; `relative` mode distributes proportionally to each model's known limit. Both use provider-reported rate data when available, falling back to local counting.

### Provider-Level Actions

Provider-level actions deactivate or reactivate all models from a provider across all pools simultaneously.

| Attribute               | Type | Description                                          |
| ----------------------- | --- | ---------------------------------------------------- |
| `provider_deactivation` | string | Deactivate all models of a provider across all pools. Values: `on_auth_failure`, `on_api_outage`. |
| `provider_recovery`     | string | Reactivate all models when provider recovers. Values: `on_probe_success`, `on_manual`. |

```yaml
pools:
  text-generation:
    strategy: modelmesh.cost-first.v1
    deactivation:
      retry_limit: 3
      error_codes: [429, 500, 503]
    recovery:
      cooldown: 60s
      on_quota_reset: true
    retry:
      max_attempts: 2
      backoff: exponential_jitter
      initial_delay: 500ms
      scope: same_provider

  image-generation:
    strategy: modelmesh.stick-until-failure.v1
    provider_priority: [huggingface.inference.v1, openrouter.gateway.v1, openai.llm.v1]

  code-review:
    capability: generation.text-generation.code-generation
    strategy: modelmesh.priority-selection.v1
    model_priority: [gpt-4o, claude-sonnet-4]
    fallback_strategy: modelmesh.cost-first.v1
```

See [ConnectorCatalogue.md — Rotation Policies](ConnectorCatalogue.html#rotation-policies) for pre-shipped strategies.

---

## Storage

Configures the persistent storage backend and sync policy. State, configuration, and observability logs flow through this connector.

| Attribute | Type | Description |
| --- | --- | --- |
| `connector` | string | Storage connector type. Pre-shipped: `modelmesh.local-file.v1` (default), `aws.s3.v1`, `google.drive.v1`, `redis.redis.v1`. |
| `sync_policy` | string | When to persist: `in-memory`, `sync-on-boundary`, `periodic`, `immediate`. |
| `sync_interval` | duration | Interval for `periodic` sync (e.g., `300s`). |

Connector-specific attributes (path, bucket, credentials, etc.) are passed through.

```yaml
storage:
  connector: modelmesh.local-file.v1
  path: ./mesh-state.json
  sync_policy: sync-on-boundary
```

```yaml
storage:
  connector: aws.s3.v1
  bucket: my-modelmesh-state
  key: state.json
  region: us-east-1
  sync_policy: periodic
  sync_interval: 300s
```

See [ConnectorCatalogue.md — Storage](ConnectorCatalogue.html#storage-connectors) for pre-shipped backends.

---

## Observability

Configures routing event export, request logging, and aggregate statistics. Each sub-section can use a different connector; multiple connectors can be active simultaneously.

### Routing Decisions

| Attribute | Type | Description |
| --- | --- | --- |
| `routing.connector` | string | Observability connector: `modelmesh.console.v1` (default), `modelmesh.local-file.v1`, `modelmesh.webhook.v1`. |
| `routing.url` | string | Webhook URL (for `modelmesh.webhook.v1` connector). |
| `routing.path` | string | File path (for `modelmesh.local-file.v1` connector). |

### Request Logging

| Attribute | Type | Description |
| --- | --- | --- |
| `logging.connector` | string | Observability connector type. |
| `logging.level` | string | Detail level: `metadata`, `summary`, `full`. |
| `logging.path` | string | File path (for `modelmesh.local-file.v1` connector). |

**Levels:**
- **`metadata`** — timestamps, model, provider, token counts, latency, status
- **`summary`** — metadata + truncated prompt/response
- **`full`** — metadata + complete payloads

### Aggregate Statistics

| Attribute | Type | Description |
| --- | --- | --- |
| `statistics.connector` | string | Observability connector type. |
| `statistics.path` | string | File path (for `modelmesh.local-file.v1` connector). |
| `statistics.flush_interval` | duration | Interval to flush buffered metrics (e.g., `60s`). |

**Recorded metrics** (per model, provider, and pool): `requests_total`, `requests_success`, `requests_failed`, `tokens_in`, `tokens_out`, `cost_total`, `latency_avg`, `latency_p95`, `downtime_total`, `standby_events`, `quota_resets`, `rotation_events`.

```yaml
observability:
  routing:
    connector: modelmesh.webhook.v1
    url: https://my-app.com/hooks/mesh
  logging:
    connector: modelmesh.local-file.v1
    level: metadata
    path: ./requests.jsonl
  statistics:
    connector: modelmesh.local-file.v1
    path: ./stats.json
    flush_interval: 60s
```

### Routing Decision Record

Each routing decision records: requested capability, resolved pool, selected model/provider, delivery mode, replaced provider (if rotated), rotation reason, fallback chain, and routing latency.

### Statistics API *(planned)*

> **Note:** The `mesh.stats()` API is planned for a future release. Statistics are currently available through the observability connector's raw output (JSONL records with `"type": "stats"`).

See [ConnectorCatalogue.md — Observability](ConnectorCatalogue.html#observability-connectors) for pre-shipped connectors.

---

## Discovery

Configures automatic model catalogue synchronization and provider health monitoring. Both run as background processes on configurable schedules.

### Registry Sync

| Attribute | Type | Description |
| --- | --- | --- |
| `sync.enabled` | boolean | Enable registry synchronization. |
| `sync.interval` | duration | Sync frequency (e.g., `1h`). |
| `sync.auto_register` | boolean | Automatically register discovered models. |
| `sync.providers` | list | Providers to sync (default: all enabled). |

### Health Monitor

| Attribute | Type | Description |
| --- | --- | --- |
| `health.enabled` | boolean | Enable health monitoring. |
| `health.interval` | duration | Probe frequency (e.g., `60s`). |
| `health.timeout` | duration | Probe timeout (e.g., `10s`). |
| `health.failure_threshold` | integer | Consecutive failures before deactivation. |
| `health.providers` | list | Providers to probe (default: all enabled). |

```yaml
discovery:
  sync:
    enabled: true
    interval: 1h
    auto_register: true
  health:
    enabled: true
    interval: 60s
    timeout: 10s
    failure_threshold: 3
```

See [ConnectorCatalogue.md — Discovery](ConnectorCatalogue.html#discovery-connectors) for pre-shipped connectors.

---

## Connectors

Configures custom connector loading. Connector packages are zip archives containing connector code, metadata, and configuration schema.

| Attribute | Type | Description |
| --- | --- | --- |
| `packages` | list | Paths or URLs to connector packages (zip archives). |

```yaml
connectors:
  packages:
    - ./connectors/my-custom-provider.zip
    - https://registry.example.com/connectors/pg-storage-1.0.zip
```

Custom connectors register in the same catalogue and receive the same treatment as pre-shipped ones. See [SystemConcept.md — Connector-Based Extensibility](SystemConcept.html#connector-based-extensibility).

---

## Proxy

Configures the OpenAI-compatible proxy deployment. The build script packages the library with selected connectors, policies, and this configuration into a Docker image.

| Attribute | Type | Description |
| --- | --- | --- |
| `host` | string | Bind address (e.g., `0.0.0.0`). |
| `port` | integer | Listen port (e.g., `8080`). |
| `endpoints` | list | OpenAI API endpoints to expose (e.g., `/v1/chat/completions`, `/v1/embeddings`). Default: all supported. |
| `auth` | object | Proxy-level authentication for incoming requests. |
| `cors` | object | CORS settings for browser clients. |

```yaml
proxy:
  host: 0.0.0.0
  port: 8080
  endpoints:
    - /v1/chat/completions
    - /v1/embeddings
    - /v1/audio/speech
  auth:
    method: bearer
    tokens:
      - ${secrets:proxy-token}
```

See [SystemConcept.md — OpenAI-Compatible Proxy](SystemConcept.html#openai-compatible-proxy) and [Deployment Modes](SystemConcept.html#deployment-modes).

---

## Full Example

```yaml
secrets:
  store: modelmesh.dotenv.v1
  path: ./.env

providers:
  openai.llm.v1:
    api_key: ${secrets:OPENAI_API_KEY}
    budget:
      daily_limit: 5.00
    discovery:
      enumerate_models: true
  huggingface.inference.v1:
    api_key: ${secrets:HF_API_KEY}
  deepseek.llm.v1:
    api_key: ${secrets:DEEPSEEK_API_KEY}

pools:
  text-generation:
    strategy: modelmesh.cost-first.v1
    deactivation:
      retry_limit: 3
    recovery:
      cooldown: 60s
      on_quota_reset: true
    retry:
      max_attempts: 2
      backoff: exponential_jitter
      scope: same_provider

  image-generation:
    strategy: modelmesh.round-robin.v1
    provider_priority: [huggingface.inference.v1, openai.llm.v1]

storage:
  connector: modelmesh.local-file.v1
  path: ./mesh-state.json
  sync_policy: sync-on-boundary

observability:
  routing:
    connector: modelmesh.console.v1
  logging:
    connector: modelmesh.local-file.v1
    level: metadata
    path: ./requests.jsonl
  statistics:
    connector: modelmesh.local-file.v1
    path: ./stats.json
    flush_interval: 60s

discovery:
  sync:
    enabled: true
    interval: 1h
    auto_register: true
  health:
    enabled: true
    interval: 60s
    timeout: 10s
    failure_threshold: 3
```

---

## Runtime API

Configuration is loaded at initialization. The runtime API provides read-only introspection of the mesh state.

```python
# Initialize with a configuration dict (typically loaded from YAML)
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

mesh.initialize(config)

# Introspect runtime state
mesh.pool_status()       # Per-pool health and model counts
mesh.active_providers()  # Currently active provider connectors
mesh.list_pools()        # Configured pool names and capabilities
mesh.list_models()       # All registered models with status
```

> **Planned (not yet implemented):** `ModelMesh.from_yaml()`, `mesh.add_provider()`, `mesh.save_config()`, `ModelMesh.from_storage()`, `mesh.export_state()`, `mesh.import_state()`, `mesh.stats()`. These APIs are reserved for future releases.

### Custom Connectors

Custom connectors are registered through the connector catalogue and referenced by ID in configuration. See [SystemConcept.md -- Connector-Based Extensibility](SystemConcept.html#connector-based-extensibility) and the [Connector Development Kit](cdk/Overview.html) for details.

```python
# Provider
class MyProvider(ProviderConnector):
    def complete(self, request): ...
    def check_quota(self): ...

# Secret store
class VaultStore(SecretStore):
    def get(self, name): ...

# Storage
class PgStorage(StorageConnector):
    def load(self): ...
    def save(self, data): ...
```

### Secrets CLI

```bash
modelmesh secrets set openai-api-key "sk-..." --store aws.secrets-manager.v1
modelmesh secrets import .env --store aws.secrets-manager.v1
modelmesh secrets list --store aws.secrets-manager.v1
```

### State Serialization *(planned)*

> **Note:** `mesh.export_state()` and `mesh.import_state()` are planned for a future release. State persistence is currently handled automatically through the configured storage connector and sync policy.

### Routing Pipeline Example

```
Request: "parse 500 invoice PDFs, return structured JSON"

1. Capability resolution     → document-understanding.document-parsing
2. Pool selection            → models at document-parsing leaf
3. Delivery mode filter      → batch-capable models on batch-capable providers only
4. Provider state filter     → exclude standby providers
5. Strategy application      → cost-first → Claude Sonnet (Anthropic)
6. Intelligent retry         → on transient failure, retry with backoff → rotate to GPT-4o (OpenAI)
```
