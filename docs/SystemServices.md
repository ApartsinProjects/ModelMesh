---
layout: default
title: "System Services"
---

# System Services

**Runtime objects and services that implement the ModelMesh Lite architecture.** This document describes the classes, state objects, and services that orchestrate capability-based routing, model lifecycle, and provider management. Individual service documentation with full code definitions is in [system/](system/Overview.html). For the conceptual architecture see [SystemConcept.md](SystemConcept.html); for YAML configuration see [SystemConfiguration.md](SystemConfiguration.html); for connector API contracts see [ConnectorInterfaces.md](ConnectorInterfaces.html).

---

## Library Facade

### ModelMesh

Top-level entry point for the library. Initializes all subsystems, loads configuration, resolves secrets, registers connectors, and wires dependencies. Applications interact with this object to obtain a router, reload configuration, or shut down gracefully.

**Key methods:**

| Method | Description |
| --- | --- |
| `initialize(config)` | Load YAML or programmatic configuration, resolve secrets, register connectors, build pools, start background services (discovery, health monitor, statistics flush). |
| `shutdown()` | Flush pending state and statistics, stop background services, release storage locks. |
| `get_router()` | Return the configured Router instance. |
| `get_client()` | Return an OpenAIClient wired to the router. |
| `get_registry()` | Return the ModelRegistry. |
| `reload_config(config)` | Hot-reload configuration without full restart. Re-resolves secrets, updates pools, re-registers connectors. |

**Configuration:** All top-level YAML sections ([SystemConfiguration.md](SystemConfiguration.html)).

**Depends on:** Router, ModelRegistry, ConnectorRegistry, SecretResolver, StateManager, EventEmitter.

---

## Routing

### Router

Central request orchestrator. Receives capability requests from the application (through OpenAIClient or ProxyServer), executes the routing pipeline, and returns the result. Handles retry and rotation transparently.

**Key methods:**

| Method | Description |
| --- | --- |
| `route(capability, options)` | Execute the routing pipeline and return a resolved model and provider. |
| `complete(capability, request)` | Route and execute a synchronous completion request. |
| `stream(capability, request)` | Route and execute a streaming request. |
| `batch(capability, requests)` | Route and submit a batch request. |
| `get_pool(name)` | Return a specific CapabilityPool by name. |
| `list_pools()` | Return all registered pools. |

**Depends on:** RoutingPipeline, CapabilityPool, EventEmitter, RequestLogger.

---

### RoutingPipeline

Ordered sequence of stages that process each request. The default pipeline runs: capability resolution, pool selection, delivery mode filter, state filter, selection strategy, and intelligent retry. Stages are composable; custom stages can be inserted or replaced.

**Key methods:**

| Method | Description |
| --- | --- |
| `execute(request)` | Run all stages in order and return the routing decision. |
| `add_stage(stage, position)` | Insert a custom stage at a specific position. |
| `remove_stage(name)` | Remove a stage by name. |
| `get_stages()` | Return the ordered list of stages. |

**Default stages:**

| Order | Stage | Purpose |
| --- | --- | --- |
| 1 | CapabilityResolver | Map requested capability to matching pools |
| 2 | Pool selection | Choose pool (single match or priority-based) |
| 3 | DeliveryFilter | Exclude models that do not support the requested delivery mode |
| 4 | StateFilter | Exclude standby models and deactivated providers |
| 5 | SelectionStrategy | Choose the best model from remaining candidates |
| 6 | RetryPolicy | On failure, retry or rotate to next candidate |

---

### CapabilityResolver

Maps a capability name to matching pools using the capability hierarchy. Traverses the tree to find pools targeting the requested node or any of its ancestors.

**Key methods:**

| Method | Description |
| --- | --- |
| `resolve(capability)` | Return all pools matching the capability, ordered by specificity (leaf pools first). |
| `get_matching_pools(node)` | Return pools registered at a specific hierarchy node. |

**Depends on:** CapabilityTree, CapabilityPool.

---

### DeliveryFilter

Pipeline stage that filters candidate models by the requested delivery mode (synchronous, streaming, or batch). Models that do not support the requested mode are excluded from selection.

**Key methods:**

| Method | Description |
| --- | --- |
| `filter(candidates, delivery_mode)` | Return only candidates supporting the requested delivery mode. |

---

### StateFilter

Pipeline stage that excludes standby models and models from deactivated providers. Ensures only healthy, active models reach the selection stage.

**Key methods:**

| Method | Description |
| --- | --- |
| `filter(candidates)` | Return only candidates with active status and available providers. |

---

### RetryPolicy

Configurable retry logic applied before rotation. On failure, determines whether to retry the same model (with backoff) or rotate to the next candidate. Retry attempts count toward the deactivation threshold.

**Key methods:**

| Method | Description |
| --- | --- |
| `should_retry(error, attempt)` | Return whether the error is retryable and attempts remain. |
| `get_delay(attempt)` | Return the backoff delay for the given attempt number. |
| `classify_error(error)` | Classify an error as retryable or non-retryable. |

**Configuration** ([SystemConfiguration.md — Pools](SystemConfiguration.html#pools)):

| Parameter | Type | Description |
| --- | --- | --- |
| `retry.max_attempts` | integer | Retries on same model before rotating. |
| `retry.backoff` | string | Backoff strategy: `fixed`, `exponential_jitter`, `retry_after`. |
| `retry.initial_delay` | duration | First retry delay (e.g., `500ms`). |
| `retry.max_delay` | duration | Maximum backoff delay (e.g., `10s`). |
| `retry.scope` | string | Retry scope: `same_model`, `same_provider`, `any`. |

---

## Pools and Models

### CapabilityPool

Groups models that fulfill the same capability. Manages active and standby model lists, delegates lifecycle decisions to its rotation policy, and provides the selection interface for the router.

Pool membership is automatic: models registered at a capability leaf node join all pools targeting that node or its ancestors. Pools can be static (YAML-defined) or dynamic (custom selection function).

**Key methods:**

| Method | Description |
| --- | --- |
| `get_active_models()` | Return all models currently eligible for routing. |
| `get_standby_models()` | Return all models currently excluded from routing. |
| `add_model(model)` | Add a model to the pool (triggered by registration or discovery). |
| `remove_model(model)` | Remove a model from the pool. |
| `select(request)` | Delegate to the selection strategy and return the best candidate. |
| `deactivate(model, reason)` | Move a model to standby with a recorded reason. |
| `recover(model)` | Move a model from standby back to active. |
| `get_state()` | Return the pool's aggregate state (active/standby counts, rotation history). |

**Configuration** ([SystemConfiguration.md — Pools](SystemConfiguration.html#pools)):

| Parameter | Type | Description |
| --- | --- | --- |
| `hierarchy_node` | string | Capability node this pool targets. |
| `allowed_providers` | list | Restrict pool to specific providers. |
| `excluded_providers` | list | Exclude specific providers from pool. |
| `model_priority` | list | Ordered model preference list. |
| `provider_priority` | list | Ordered provider preference list. |
| `strategy` | string | Selection strategy connector ID. |

**Depends on:** Model, RotationPolicy, EventEmitter.

---

### Model

Runtime representation of a model definition combined with its current state. The static definition declares capabilities, delivery modes, features, and constraints; the dynamic state tracks health, quotas, and cooldowns. A model belongs to one provider and participates in one or more pools.

**Key methods:**

| Method | Description |
| --- | --- |
| `get_capabilities()` | Return the model's registered capability leaf nodes. |
| `get_delivery_modes()` | Return supported delivery modes (sync, streaming, batch). |
| `get_features()` | Return supported features (tool calling, structured output, etc.). |
| `get_constraints()` | Return operational constraints (context window, max output tokens, etc.). |
| `get_state()` | Return the current ModelState. |
| `update_state(result)` | Update state after a request (success/failure, latency, tokens used). |
| `reset_state()` | Reset failure counts and cooldown timers. |

**Configuration** ([SystemConfiguration.md — Models](SystemConfiguration.html#models)):

| Parameter | Type | Description |
| --- | --- | --- |
| `provider` | string | Provider this model belongs to. |
| `capabilities` | list | Capability leaf nodes (e.g., `[chat-completion, tool-calling]`). |
| `delivery` | string | Default delivery mode: `sync`, `streaming`. |
| `batch` | boolean | Supports batch delivery. |
| `features` | map | Feature flags (tool_calling, structured_output, json_mode, etc.). |
| `constraints` | map | Operational limits (context_window, max_output_tokens, etc.). |

**Depends on:** Provider, ModelState.

---

### Provider

Runtime representation of a configured provider. Wraps the provider connector (which handles API communication) with operational state tracking: quota consumption, rate-limit headroom, and health status. A provider manages one or more models.

**Key methods:**

| Method | Description |
| --- | --- |
| `execute(model, request)` | Execute a request through the provider connector. |
| `check_quota()` | Query current quota usage from the provider API (if supported). |
| `get_rate_limits()` | Return current rate-limit headroom. |
| `get_health()` | Return the provider's health status and availability score. |
| `is_available()` | Return whether the provider is operational (auth valid, not deactivated). |
| `get_models()` | Return all models registered under this provider. |

**Configuration** ([SystemConfiguration.md — Providers](SystemConfiguration.html#providers)):

| Parameter | Type | Description |
| --- | --- | --- |
| `enabled` | boolean | Enable or disable the provider. |
| `api_key` | string | API key or secret reference (`${secrets:name}`). |
| `base_url` | string | Custom API endpoint URL. |
| `connector` | string | Provider connector ID. |
| `auth.*` | map | Authentication configuration. |
| `quota.*` | map | Quota tracking configuration. |
| `budget.*` | map | Spend cap configuration. |

**Depends on:** ProviderConnector, ProviderState, SecretResolver.

---

### ModelState

Per-model health and usage tracking. Updated after each request and persisted through the StateManager. Serializable for storage and recovery across restarts.

**Fields:**

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Current status: `active` or `standby`. |
| `failure_count` | integer | Consecutive failures since last success. |
| `error_rate` | float | Error rate over sliding window (0.0–1.0). |
| `cooldown_remaining` | duration | Time remaining before recovery eligibility. |
| `quota_used` | integer | Requests consumed in current quota period. |
| `tokens_used` | integer | Tokens consumed in current quota period. |
| `cost_accumulated` | number | Cost accumulated in current budget period (USD). |
| `latency_history` | list | Recent request latencies for scoring. |
| `last_request` | timestamp | Time of last successful request. |
| `last_failure` | timestamp | Time of last failure. |
| `deactivation_reason` | string | Reason for standby status (if applicable). |

---

### ProviderState

Per-provider aggregate health tracking. Provider-level issues (authentication failure, API outage) trigger deactivation of all the provider's models across all pools.

**Fields:**

| Field | Type | Description |
| --- | --- | --- |
| `available` | boolean | Provider is operational. |
| `auth_valid` | boolean | Authentication is valid. |
| `last_probe` | timestamp | Time of last health probe. |
| `availability_score` | float | Rolling availability score (0.0–1.0). |
| `active_model_count` | integer | Number of active models from this provider. |
| `total_quota_used` | integer | Aggregate quota consumption across all models. |
| `total_cost` | number | Aggregate cost across all models (USD). |

---

## Rotation

### RotationPolicy

Composite object governing model lifecycle within a pool. Contains three independently replaceable components: deactivation, recovery, and selection. Each component receives the current model state and makes decisions accordingly. Operates at model level (individual model to standby) or provider level (all models from a provider deactivated across pools).

**Key methods:**

| Method | Description |
| --- | --- |
| `evaluate_deactivation(model)` | Delegate to DeactivationEvaluator; return whether the model should move to standby. |
| `evaluate_recovery(model)` | Delegate to RecoveryEvaluator; return whether the model should return to active. |
| `select_model(candidates, request)` | Delegate to SelectionStrategy; return the best candidate. |

**Configuration** ([SystemConfiguration.md — Pools](SystemConfiguration.html#pools)): Strategy, deactivation, and recovery parameters are configured per pool.

**Depends on:** DeactivationEvaluator, RecoveryEvaluator, SelectionStrategy.

---

### DeactivationEvaluator

Evaluates whether an active model should move to standby. Triggered after each request or on state change (quota exhausted, error threshold reached, maintenance window entered).

**Key methods:**

| Method | Description |
| --- | --- |
| `should_deactivate(snapshot)` | Return `true` if the model should move to standby. |
| `get_reason(snapshot)` | Return the deactivation reason (error threshold, quota exhausted, budget exceeded, maintenance). |

**Configuration** ([SystemConfiguration.md — Pools](SystemConfiguration.html#pools)):

| Parameter | Type | Description |
| --- | --- | --- |
| `deactivation.retry_limit` | integer | Consecutive failures before deactivation. |
| `deactivation.error_rate_threshold` | float | Error rate threshold (0.0–1.0). |
| `deactivation.error_codes` | list | HTTP codes that count toward deactivation. |
| `deactivation.request_limit` | integer | Max requests before deactivation (free-tier cap). |
| `deactivation.token_limit` | integer | Max tokens before deactivation. |
| `deactivation.budget_limit` | number | Max spend (USD) before deactivation. |
| `deactivation.quota_window` | string | Deactivate on quota period expiry: `monthly`, `daily`. |
| `deactivation.maintenance_window` | string | Scheduled deactivation (cron expression). |

---

### RecoveryEvaluator

Evaluates whether a standby model should return to active. Triggered on timer expiry, calendar event, probe result, or manual command.

**Key methods:**

| Method | Description |
| --- | --- |
| `should_recover(snapshot)` | Return `true` if the model should return to active. |
| `get_recovery_schedule(snapshot)` | Return the next scheduled recovery time. |

**Configuration** ([SystemConfiguration.md — Pools](SystemConfiguration.html#pools)):

| Parameter | Type | Description |
| --- | --- | --- |
| `recovery.cooldown` | duration | Time from deactivation before recovery eligibility. |
| `recovery.probe_on_start` | boolean | Test standby models at library startup. |
| `recovery.probe_interval` | duration | Periodically test standby models. |
| `recovery.on_quota_reset` | boolean | Reactivate when provider quota resets. |
| `recovery.quota_reset_schedule` | string | Calendar schedule for quota resets: `monthly`, `daily_utc`. |

---

### SelectionStrategy

Chooses the best model from active candidates for a given request. Pluggable with eight pre-shipped strategies and custom implementations.

**Key methods:**

| Method | Description |
| --- | --- |
| `select(candidates, request)` | Return the best candidate for the request. |
| `score(candidate, request)` | Return a numeric score for a single candidate (used for ranking). |

**Pre-shipped strategies:**

| Strategy | Behavior |
| --- | --- |
| `modelmesh.stick-until-failure.v1` | Use the same model until it fails, then rotate (default). |
| `modelmesh.priority-selection.v1` | Always prefer the highest-priority available model. |
| `modelmesh.round-robin.v1` | Cycle through active models in order. |
| `modelmesh.cost-first.v1` | Select the cheapest available model. |
| `modelmesh.latency-first.v1` | Select the model with lowest recent latency. |
| `modelmesh.session-stickiness.v1` | Route all requests in a session to the same model. |
| `modelmesh.rate-limit-aware.v1` | Switch models preemptively before hitting rate limits. |
| `modelmesh.load-balanced.v1` | Distribute requests proportionally to rate-limit headroom. |

**Configuration** ([SystemConfiguration.md — Pools](SystemConfiguration.html#pools)):

| Parameter | Type | Description |
| --- | --- | --- |
| `strategy` | string | Selection strategy connector ID. |
| `model_priority` | list | Ordered model preference list. |
| `provider_priority` | list | Ordered provider preference list. |
| `fallback_strategy` | string | Strategy after priority list exhausted. |
| `balance_mode` | string | For load-balanced: `absolute` or `relative`. |
| `rate_limit.threshold` | float | Switch models at this fraction of the limit (0.0–1.0). |
| `rate_limit.min_delta` | duration | Minimum time between requests to the same model. |
| `rate_limit.max_rpm` | integer | Max requests per minute before switching. |

---

## Registries

### ModelRegistry

Local cache of known model definitions. Source of truth for pool membership and capability resolution. Updated by discovery sync (automatic) and manual registration (API). Persisted through the StateManager.

**Key methods:**

| Method | Description |
| --- | --- |
| `register(model_definition)` | Register a model and update pool memberships. |
| `unregister(model_name)` | Remove a model and update pool memberships. |
| `get_model(name)` | Return a model by name. |
| `list_models()` | Return all registered models. |
| `find_by_capability(capability)` | Return models registered at a capability node or its descendants. |
| `find_by_provider(provider)` | Return all models from a specific provider. |
| `refresh()` | Trigger re-evaluation of pool memberships after model changes. |

**Depends on:** CapabilityTree, CapabilityPool.

---

### ConnectorRegistry

Catalogue of available connector implementations. Loads built-in connectors at initialization and custom connectors from packages referenced in configuration. All connector types (provider, rotation, secret store, storage, observability, discovery) register here.

**Key methods:**

| Method | Description |
| --- | --- |
| `register(connector_id, implementation)` | Register a connector implementation by its naming-convention ID. |
| `get_connector(connector_id)` | Return a connector implementation by ID. |
| `list_connectors(type)` | Return all registered connectors, optionally filtered by type. |
| `load_package(path)` | Load a connector package (zip archive) and register its connectors. |

**Configuration** ([SystemConfiguration.md — Connectors](SystemConfiguration.html#connectors)):

| Parameter | Type | Description |
| --- | --- | --- |
| `connectors` | list | Paths or URLs to connector packages. |

---

### CapabilityTree

In-memory representation of the capability hierarchy defined in [ModelCapabilities.md](ModelCapabilities.html). Provides traversal operations for capability resolution and pool membership. The default tree includes seven categories (generation, understanding, transformation, representation, retrieval, interaction, evaluation) with pre-defined leaf nodes. Users extend the tree with custom categories and leaves.

**Key methods:**

| Method | Description |
| --- | --- |
| `get_node(path)` | Return a node by its hierarchy path (e.g., `generation.chat-completion`). |
| `get_ancestors(node)` | Return all ancestor nodes from node to root. |
| `get_descendants(node)` | Return all descendant nodes (subcategories and leaves). |
| `get_leaves(node)` | Return only leaf descendants (routable capabilities). |
| `add_node(parent, name)` | Add a custom node under an existing parent. |
| `is_ancestor_of(ancestor, descendant)` | Return whether one node is an ancestor of another. |
| `list_categories()` | Return all top-level category nodes. |

---

## External Interfaces

### OpenAIClient

Drop-in replacement for the OpenAI SDK. Translates standard OpenAI API calls into capability-based routing through virtual model names. Applications use this client exactly as they would use the official OpenAI SDK; the library resolves virtual names to real models and providers transparently.

**Key methods:**

| Method | Description |
| --- | --- |
| `chat.completions.create(model, messages, ...)` | Route to a pool matching the virtual model name and execute a chat completion. |
| `embeddings.create(model, input, ...)` | Route and execute an embedding request. |
| `audio.speech.create(model, input, ...)` | Route and execute a text-to-speech request. |
| `audio.transcriptions.create(model, file, ...)` | Route and execute a speech-to-text request. |
| `images.generate(model, prompt, ...)` | Route and execute an image generation request. |

**Virtual model names** map to configured pools. A call to `chat.completions.create(model="text-generation", ...)` resolves to the best active model in the `text-generation` pool.

**Depends on:** Router.

---

### ProxyServer

Standalone HTTP server exposing standard OpenAI API endpoints. Wraps the Router for deployment as a shared service. Multiple applications (LangChain pipelines, IDE assistants, internal tools) connect to a single proxy with centralized configuration, credential management, and state.

**Key methods:**

| Method | Description |
| --- | --- |
| `start()` | Start the HTTP server on the configured host and port. |
| `stop()` | Gracefully shut down the server, flushing state and statistics. |
| `get_status()` | Return server status (uptime, active connections, request counts). |

**Endpoints:**

| Endpoint | Description |
| --- | --- |
| `POST /v1/chat/completions` | Chat completion (sync and streaming). |
| `POST /v1/embeddings` | Embedding generation. |
| `POST /v1/audio/speech` | Text-to-speech. |
| `POST /v1/audio/transcriptions` | Speech-to-text. |
| `POST /v1/images/generations` | Image generation. |
| `GET /v1/models` | List available virtual model names and their pools. |

**Configuration** ([SystemConfiguration.md — Proxy](SystemConfiguration.html#proxy)):

| Parameter | Type | Description |
| --- | --- | --- |
| `proxy.host` | string | Bind address (e.g., `0.0.0.0`). |
| `proxy.port` | integer | Listen port (e.g., `8080`). |
| `proxy.endpoints` | list | Enabled endpoint paths. |
| `proxy.auth.enabled` | boolean | Require authentication for proxy requests. |
| `proxy.auth.tokens` | list | Allowed bearer tokens. |
| `proxy.cors.enabled` | boolean | Enable CORS headers. |
| `proxy.cors.origins` | list | Allowed origins. |

**Depends on:** Router, ModelMesh.

---

## Observability Services

### EventEmitter

Publishes routing events to all active observability connectors. Events include model activation, deactivation, rotation, recovery, and provider health changes. Multiple connectors can subscribe simultaneously (e.g., webhook for alerts and file for dashboards).

**Key methods:**

| Method | Description |
| --- | --- |
| `emit(event)` | Publish a RoutingEvent to all subscribed observability connectors. |
| `subscribe(connector)` | Register an observability connector to receive events. |
| `unsubscribe(connector)` | Remove an observability connector. |

**Event types:**

| Event | Triggered when |
| --- | --- |
| `model_activated` | A model moves from standby to active. |
| `model_deactivated` | A model moves from active to standby. |
| `model_rotated` | A request is rerouted from one model to another. |
| `provider_health_changed` | Provider availability score changes significantly. |
| `provider_deactivated` | All models from a provider are deactivated. |
| `provider_recovered` | A deactivated provider returns to service. |
| `pool_membership_changed` | Models are added to or removed from a pool. |
| `discovery_models_updated` | Registry sync detects new or deprecated models. |

**Configuration** ([SystemConfiguration.md — Observability](SystemConfiguration.html#observability)):

| Parameter | Type | Description |
| --- | --- | --- |
| `observability.routing.connector` | string | Observability connector for routing events. |
| `observability.routing.events` | list | Event types to emit. Default: all. |

---

### RequestLogger

Records request and response data at a configurable detail level through observability connectors. Supports three detail levels to balance visibility against payload size.

**Key methods:**

| Method | Description |
| --- | --- |
| `log(entry)` | Record a RequestLogEntry with routing decision and response metadata. |
| `set_level(level)` | Change the detail level at runtime. |

**Detail levels:**

| Level | Content |
| --- | --- |
| `metadata` | Timestamps, model, provider, token counts, latency, status code. |
| `summary` | Metadata plus truncated request/response (first N characters). |
| `full` | Complete request and response payloads. |

**Configuration** ([SystemConfiguration.md — Observability](SystemConfiguration.html#observability)):

| Parameter | Type | Description |
| --- | --- | --- |
| `observability.logging.connector` | string | Observability connector for request logs. |
| `observability.logging.level` | string | Detail level: `metadata`, `summary`, `full`. |
| `observability.logging.redact` | boolean | Redact API keys and tokens from logged payloads. |
| `observability.logging.max_payload_size` | integer | Truncate logged payloads exceeding this byte count. |

---

### StatisticsCollector

Buffers aggregate metrics and flushes on a configurable schedule through observability connectors. Queryable through the statistics API for programmatic access to operational data.

**Key methods:**

| Method | Description |
| --- | --- |
| `record(model_id, provider_id, pool_id, metrics)` | Record metrics from a completed request. |
| `flush()` | Push buffered metrics to all observability connectors. |
| `query(scope, name)` | Return aggregate statistics for a model, provider, or pool. |
| `reset()` | Clear all buffered statistics. |

**Query API:**

| Method | Returns |
| --- | --- |
| `stats.model(name)` | Per-model: requests, tokens, cost, latency, rotation events. |
| `stats.provider(name)` | Per-provider: requests, cost, availability, active models. |
| `stats.pool(name)` | Per-pool: requests, active/standby counts, rotation events. |

**Configuration** ([SystemConfiguration.md — Observability](SystemConfiguration.html#observability)):

| Parameter | Type | Description |
| --- | --- | --- |
| `observability.statistics.connector` | string | Observability connector for statistics. |
| `observability.statistics.flush_interval` | duration | Interval to flush buffered metrics (e.g., `60s`). |
| `observability.statistics.retention` | duration | In-memory retention window (e.g., `7d`). |
| `observability.statistics.scopes` | list | Aggregation scopes: `model`, `provider`, `pool`. |

---

## Infrastructure Services

### SecretResolver

Resolves `${secrets:name}` references in configuration through the configured secret store connector. Caches resolved values in memory with configurable TTL. Re-resolves secrets on provider rotation when a new provider is activated.

**Key methods:**

| Method | Description |
| --- | --- |
| `resolve(reference)` | Return the secret value for a `${secrets:name}` reference. |
| `resolve_all(config)` | Resolve all secret references in a configuration object. |
| `invalidate(name)` | Remove a cached secret, forcing re-resolution on next access. |
| `reload()` | Re-resolve all cached secrets from the store. |

**Configuration** ([SystemConfiguration.md — Secrets](SystemConfiguration.html#secrets)):

| Parameter | Type | Description |
| --- | --- | --- |
| `secrets.store` | string | Secret store connector ID. |
| `secrets.cache_ttl` | duration | Cache lifetime for resolved secrets. |
| `secrets.reload_on_rotation` | boolean | Re-resolve secrets when a new provider is activated. |

**Depends on:** SecretStoreConnector.

---

### StateManager

Coordinates persistence of runtime state (ModelState, ProviderState, pool memberships) through the configured storage connector. Manages the sync policy lifecycle: loading state at startup, saving on shutdown, and syncing periodically or immediately depending on policy.

**Key methods:**

| Method | Description |
| --- | --- |
| `load()` | Load persisted state from the storage backend. Called at initialization. |
| `save()` | Persist current state to the storage backend. Called at shutdown and on sync boundaries. |
| `sync()` | Execute a sync cycle according to the configured policy. |
| `get_sync_status()` | Return last sync time, pending changes, and lock status. |
| `acquire_lock()` | Acquire advisory lock for multi-instance coordination. |
| `release_lock()` | Release advisory lock. |

**Sync policies:**

| Policy | Behavior |
| --- | --- |
| `in-memory` | No persistence. State is lost on shutdown. |
| `sync-on-boundary` | Load at startup, save at shutdown. |
| `periodic` | Sync at configurable intervals (e.g., every 5 minutes). |
| `immediate` | Persist every state change. Requires locking for multi-instance. |

**Configuration** ([SystemConfiguration.md — Storage](SystemConfiguration.html#storage)):

| Parameter | Type | Description |
| --- | --- | --- |
| `storage.connector` | string | Storage connector ID. |
| `storage.persistence.sync_policy` | string | Sync policy: `in-memory`, `sync-on-boundary`, `periodic`, `immediate`. |
| `storage.persistence.sync_interval` | duration | Interval for `periodic` sync (e.g., `300s`). |

**Depends on:** StorageConnector.
