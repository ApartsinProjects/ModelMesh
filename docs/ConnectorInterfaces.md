# Connector Interfaces

**Interface overview for every ModelMesh Lite connector type.** Each section describes the connector's purpose and the interfaces it exposes. This is a conceptual overview, not a full specification. Full interface definitions with code are in [interfaces/](interfaces/Provider.md). Pre-shipped implementations are listed in [ConnectorCatalogue.md](ConnectorCatalogue.md).

> **CDK:** Base classes with sensible defaults for each interface are available in the [Connector Development Kit](cdk/Overview.md). See [cdk/BaseClasses.md](cdk/BaseClasses.md) for implementations.

---

## Provider

A provider connector exposes one or more AI models (or web API services) through a uniform, OpenAI-compatible API. It bridges the gap between the library's abstract capability model and the provider's concrete API: translating requests, managing authentication, tracking usage, and reporting operational data that drives routing and rotation decisions.

**Interfaces:**

| Interface | Purpose | Key methods |
| --- | --- | --- |
| **Model Execution** | Execute requests through an OpenAI-compatible API (chat, embeddings, audio, images). Handle authentication, format translation, and streaming. | `complete`, `stream` |
| **Capabilities** | Declare which capabilities, delivery modes, and features the provider supports. The router uses this to match requests to eligible providers. | `get_capabilities`, `supports` |
| **Model Catalogue** | List available models with their attributes (context window, pricing, supported modalities). Feeds pool membership and model definitions. | `list_models`, `get_model_info` |
| **Quota & Rate Limits** | Report current usage, remaining capacity, and rate-limit headroom. Enables proactive rotation before limits are hit. | `check_quota`, `get_rate_limits` |
| **Cost & Pricing** | Provide per-token and per-request cost metadata. Feeds cost-first selection and budget-based deactivation. | `get_pricing`, `report_usage` |
| **Error Classification** | Classify provider errors as retryable (timeout, 500, 503) or non-retryable (400, 401, 403). Feeds intelligent retry and rotation decisions. | `classify_error`, `is_retryable` |
| **Infrastructure** *(optional)* | Batch processing, file upload, fine-tuning, and model discovery. Not all providers support these; connectors declare which are available. | `submit_batch`, `upload_file`, `create_fine_tune`, `discover_models` |

### Infrastructure Capability Categories

| Category             | Examples                                             |
| -------------------- | ---------------------------------------------------- |
| **Discovery**        | enumerate models, query model details                |
| **Quota & Usage**    | query current quota, usage history, remaining budget |
| **Pricing**          | query model pricing, batch discounts                 |
| **Batch Operations** | submit, cancel, query status, retrieve results       |
| **File Management**  | upload, list, delete files                           |
| **Fine-Tuning**      | create job, monitor training, deploy                 |
| **Authentication**   | API key, OAuth, service account                      |

**Routing integration:** `enumerate_models` feeds auto-discovery at startup; `query_current_quota` enables proactive rotation; `query_pricing` drives cost-first strategy; `batch.supported` enables batch-only routing; `files.upload` supports document workflows.

### Common Configuration

Parameters shared by all provider connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md](ConnectorCatalogue.md#provider-connectors)).

| Parameter | Type | Description |
| --- | --- | --- |
| `provider.execution.base_url` | string | Custom API endpoint URL. Overrides the default for self-hosted or proxy deployments. |
| `provider.execution.timeout` | duration | Request timeout (e.g., `30s`). Applied to all API calls. |
| `provider.execution.max_retries` | integer | Provider-level retries before reporting failure to the router. |
| `provider.auth.method` | string | Authentication method: `api_key`, `oauth`, `service_account`. |
| `provider.auth.api_key` | string | API key or secret reference (`${secrets:key-name}`). |
| `provider.auth.key_rotation` | boolean | Enable automatic key rotation. |
| `provider.catalogue.auto_discover` | boolean | Enumerate models from the provider API at startup. |
| `provider.catalogue.refresh_interval` | duration | Re-sync model catalogue on this schedule (e.g., `1h`). |
| `provider.quota.query_current` | boolean | Provider API supports querying current usage. |
| `provider.quota.query_remaining` | boolean | Provider API supports querying remaining capacity. |
| `provider.quota.reset_schedule` | string | Quota reset frequency: `monthly`, `daily`, `rolling`. |
| `provider.budget.daily_limit` | number | Daily spend cap in USD. Triggers deactivation when exceeded. |
| `provider.budget.monthly_limit` | number | Monthly spend cap in USD. |
| `provider.pricing.query` | boolean | Provider API supports pricing queries. |
| `provider.error.retryable_codes` | list | HTTP status codes eligible for retry (e.g., `[429, 500, 502, 503]`). |
| `provider.error.non_retryable_codes` | list | HTTP codes that skip retry and trigger immediate rotation (e.g., `[400, 401, 403]`). |
| `provider.infrastructure.batch` | boolean | Provider supports batch submissions. |
| `provider.infrastructure.files` | boolean | Provider supports file upload/management. |
| `provider.infrastructure.fine_tuning` | boolean | Provider supports fine-tuning. |
| `provider.enabled` | boolean | Enable or disable the provider. Default: `true`. |

---

## Rotation Policy

A rotation policy governs model lifecycle within a pool through three independently replaceable components. Rotation operates at model level (individual model moves to standby) or provider level (all models from a provider deactivated across pools). Each component receives the current model state (failure counts, cooldown timers, quota usage, latency history) and makes decisions accordingly.

**Interfaces:**

| Interface | Purpose | Key methods |
| --- | --- | --- |
| **Deactivation** | Evaluate whether an active model should move to standby. Triggered after each request or on state change (quota exhausted, error threshold, maintenance window). | `should_deactivate`, `get_reason` |
| **Recovery** | Evaluate whether a standby model should return to active. Triggered on timer, calendar event, probe result, or manual command. | `should_recover`, `get_recovery_schedule` |
| **Selection** | Choose the best model from active candidates for a given request. Considers cost, latency, rate-limit headroom, session affinity, or custom scoring. | `select`, `score` |

### Common Configuration

Parameters shared by all rotation policies. Configured per pool; policies receive these through the pool context. Full YAML reference in [SystemConfiguration.md — Pools](SystemConfiguration.md#pools).

| Parameter | Type | Description |
| --- | --- | --- |
| `rotation.deactivation.retry_limit` | integer | Consecutive failures before deactivation. |
| `rotation.deactivation.error_rate_threshold` | float | Error rate over sliding window (0.0–1.0) before deactivation. |
| `rotation.deactivation.error_codes` | list | HTTP codes that count toward deactivation (e.g., `[429, 500, 503]`). |
| `rotation.deactivation.request_limit` | integer | Max requests before deactivation (free-tier cap). |
| `rotation.deactivation.token_limit` | integer | Max tokens before deactivation. |
| `rotation.deactivation.budget_limit` | number | Max spend (USD) before deactivation. |
| `rotation.deactivation.quota_window` | string | Deactivate when quota period expires: `monthly`, `daily`. |
| `rotation.deactivation.maintenance_window` | string | Scheduled deactivation (cron expression). |
| `rotation.recovery.cooldown` | duration | Time from deactivation before reactivation (e.g., `60s`). |
| `rotation.recovery.probe_on_start` | boolean | Test standby models at library startup. |
| `rotation.recovery.probe_interval` | duration | Periodically test standby models (e.g., `300s`). |
| `rotation.recovery.on_quota_reset` | boolean | Reactivate when provider quota resets. |
| `rotation.recovery.quota_reset_schedule` | string | Calendar schedule for quota resets: `monthly`, `daily_utc`. |
| `rotation.selection.model_priority` | list | Ordered model preference list. |
| `rotation.selection.provider_priority` | list | Ordered provider preference list. |
| `rotation.selection.fallback_strategy` | string | Strategy after priority list exhausted. |
| `rotation.selection.balance_mode` | string | For load-balanced: `absolute` or `relative` distribution. |
| `rotation.selection.rate_limit.threshold` | float | Switch models at this fraction of the limit (0.0–1.0). |
| `rotation.selection.rate_limit.min_delta` | duration | Minimum time between requests to the same model. |
| `rotation.selection.rate_limit.max_rpm` | integer | Max requests per minute before switching models. |
| `rotation.provider_deactivation` | string | Deactivate all models of a provider across all pools: `on_auth_failure`, `on_api_outage`. |
| `rotation.provider_recovery` | string | Reactivate all models when provider recovers: `on_probe_success`, `on_manual`. |

---

## Secret Store

A secret store connector resolves API keys and tokens from a secure backend at runtime. Configuration references secrets by name (`${secrets:openai-key}`); the library resolves them through the configured store at initialization and on rotation (when a new provider is activated).

**Interfaces:**

| Interface | Purpose | Key methods |
| --- | --- | --- |
| **Resolution** | Retrieve a secret value by name. The only required interface — all stores must support this. | `get` |
| **Management** *(optional)* | Store, list, and remove secrets. Used by the CLI utility for credential provisioning across environments. | `set`, `list`, `delete` |

### Common Configuration

Parameters shared by all secret store connectors. Individual stores may add connector-specific parameters (see [ConnectorCatalogue.md](ConnectorCatalogue.md#secret-store-connectors)).

| Parameter | Type | Description |
| --- | --- | --- |
| `secret-store.resolution.cache_enabled` | boolean | Cache resolved secrets in memory. Default: `true`. |
| `secret-store.resolution.cache_ttl` | duration | Time-to-live for cached secrets (e.g., `300s`). |
| `secret-store.resolution.reload_on_rotation` | boolean | Re-resolve secrets when a new provider is activated during rotation. Default: `true`. |
| `secret-store.resolution.fail_on_missing` | boolean | Fail initialization if a referenced secret is not found. Default: `true`. |

---

## Storage

A storage connector serializes and deserializes library data to an external backend. Three data types flow through it: **state** (model health, failure counts, cooldown timers, quota usage), **configuration** (providers, pools, policies, credential references), and **observability logs** (routing decisions, request records, statistics). Sync policies control when persistence occurs: `in-memory`, `sync-on-boundary`, `periodic`, or `immediate`.

**Interfaces:**

| Interface | Purpose | Key methods |
| --- | --- | --- |
| **Persistence** | Read and write serialized data. The connector handles format and transport; the library handles serialization logic. | `load`, `save` |
| **Inventory** | Enumerate and remove stored entries. Used for cleanup, migration, and administrative tooling. | `list`, `delete` |
| **Stat Query** | Query metadata about stored entries (existence, size, last modified) without loading full content. Used for cache validation and change detection. | `stat`, `exists` |
| **Locking** | Acquire and release advisory locks on stored entries. Prevents concurrent writes in multi-instance deployments. Required for `periodic` and `immediate` sync policies. | `acquire`, `release`, `is_locked` |

### Common Configuration

Parameters shared by all storage connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md](ConnectorCatalogue.md#storage-connectors)).

| Parameter | Type | Description |
| --- | --- | --- |
| `storage.persistence.sync_policy` | string | When to persist: `in-memory`, `sync-on-boundary`, `periodic`, `immediate`. |
| `storage.persistence.sync_interval` | duration | Interval for `periodic` sync (e.g., `300s`). |
| `storage.persistence.format` | string | Serialization format: `json` (default), `yaml`, `msgpack`. |
| `storage.persistence.compression` | boolean | Compress serialized data before writing. Default: `false`. |
| `storage.persistence.encryption` | boolean | Encrypt data at rest using the configured secret store. Default: `false`. |
| `storage.locking.enabled` | boolean | Enable advisory locking for concurrent access. Default: `true` for multi-instance sync policies. |
| `storage.locking.timeout` | duration | Maximum time to wait for a lock (e.g., `30s`). |
| `storage.locking.retry_interval` | duration | Interval between lock acquisition attempts (e.g., `1s`). |

---

## Observability

An observability connector exports routing activity to an external output. Multiple connectors can be active simultaneously (e.g., webhook for alerts + file for dashboards). The library pushes data through the connector at four levels of detail.

**Interfaces:**

| Interface | Purpose | Key methods |
| --- | --- | --- |
| **Events** | Publish routing decisions and state changes (model activated, deactivated, rotated, provider health change). | `emit` |
| **Logging** | Record request/response data at a configurable detail level (metadata only, truncated summary, or full payloads). | `log` |
| **Statistics** | Buffer and flush aggregate metrics (request counts, token usage, cost, latency, downtime per model/provider/pool). | `flush` |
| **Tracing** | Structured trace reporting with severity levels. All core components (Router, Pool, Mesh, BaseProvider) emit traces through this interface. | `trace` |

### Common Configuration

Parameters shared by all observability connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md](ConnectorCatalogue.md#observability-connectors)).

| Parameter | Type | Description |
| --- | --- | --- |
| `observability.events.filter` | list | Event types to emit (e.g., `[rotation, deactivation, recovery, health]`). Default: all. |
| `observability.events.include_metadata` | boolean | Include model and provider metadata in event payloads. Default: `true`. |
| `observability.logging.level` | string | Detail level: `metadata`, `summary`, `full`. Default: `metadata`. |
| `observability.logging.redact_secrets` | boolean | Redact API keys and tokens from logged payloads. Default: `true`. |
| `observability.logging.max_payload_size` | integer | Truncate logged payloads exceeding this byte count. |
| `observability.tracing.min_severity` | string | Minimum severity level for trace entries: `debug`, `info`, `warning`, `error`, `critical`. Default: `info`. Entries below this threshold are discarded. |
| `observability.statistics.flush_interval` | duration | Interval to flush buffered metrics (e.g., `60s`). |
| `observability.statistics.retention` | duration | Retention window for in-memory statistics (e.g., `7d`). |
| `observability.statistics.scopes` | list | Aggregation scopes: `model`, `provider`, `pool`. Default: all. |

---

## Discovery

A discovery connector keeps the model catalogue accurate and provider health visible without manual intervention. Discovery connectors run as background processes on configurable schedules and feed results into the [rotation policy](SystemConcept.md#model-rotation-failover-and-state) for proactive deactivation.

**Interfaces:**

| Interface | Purpose | Key methods |
| --- | --- | --- |
| **Registry Sync** | Synchronize the local model catalogue with provider APIs. Detect new models, deprecated models, and pricing changes. | `sync`, `get_sync_status` |
| **Health Monitoring** | Probe provider availability and performance. Record latency, error codes, and rolling availability scores. | `probe`, `get_health_report` |

### Common Configuration

Parameters shared by all discovery connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md](ConnectorCatalogue.md#discovery-connectors)).

| Parameter | Type | Description |
| --- | --- | --- |
| `discovery.sync.enabled` | boolean | Enable registry synchronization. Default: `true`. |
| `discovery.sync.interval` | duration | Sync frequency (e.g., `1h`). |
| `discovery.sync.auto_register` | boolean | Automatically register newly discovered models. Default: `true`. |
| `discovery.sync.providers` | list | Providers to sync. Default: all enabled providers. |
| `discovery.sync.on_new_model` | string | Action on new model: `register`, `notify`, `ignore`. Default: `register`. |
| `discovery.sync.on_deprecated_model` | string | Action on deprecated model: `deactivate`, `notify`, `ignore`. Default: `notify`. |
| `discovery.health.enabled` | boolean | Enable health monitoring. Default: `true`. |
| `discovery.health.interval` | duration | Probe frequency (e.g., `60s`). |
| `discovery.health.timeout` | duration | Probe timeout (e.g., `10s`). |
| `discovery.health.failure_threshold` | integer | Consecutive failures before deactivation. |
| `discovery.health.providers` | list | Providers to probe. Default: all enabled providers. |
