---
layout: default
title: "ModelMesh Lite"
---

# ModelMesh Lite

**Capability-driven AI routing library for Python and TypeScript. A single integration point for multiple AI providers with automatic rotation to aggregate free tiers, minimize cost, and maintain service continuity.**

> Applications request capabilities. ModelMesh Lite manages providers, quotas, costs, and failover.

---

## Why

AI applications need *capabilities* (text generation, image generation, embeddings, speech) and do not care about specific providers. Coupling to one provider means quota exhaustion halts the app, rate limits cause interruptions, outages remove entire capabilities, and each provider needs its own integration code.

ModelMesh Lite separates **what the application needs** from **who delivers it**: provider rotation avoids downtime, free-tier aggregation combines quotas, capability-based routing prevents lock-in, and a unified API simplifies development.

ModelMesh Lite does not replace high-level AI frameworks such as LangChain or LangGraph. It operates one layer below, providing the infrastructure for efficient, reliable access to the cloud APIs that those frameworks depend on. Provider rotation, quota aggregation, failover, and credential management become shared plumbing that any framework or application can build upon.

---

## Architecture Overview

Each request resolves in two stages: **capability resolution** (choose a pool matching the requested capability) and **model selection** (select the best active model and its provider). Applications remain stable even when providers change.

**System layers:** Application → Router → Pool → Model → Provider. The application requests a capability; the router resolves it to a pool; the pool groups models that fulfill it; each model declares capabilities and constraints; providers expose models and manage quotas. The router selects the best active model, routes through its provider, and handles rotation on failure.

### Connector-Based Extensibility

Every integration point is a **connector**, a class or function implementing a defined interface (providers, rotation policies, secret stores, storage backends, observability outputs, discovery). Each connector type has a **connector catalogue**, a registry of available implementations with code, metadata, and a configuration schema. Interface definitions are in [ConnectorInterfaces.md](ConnectorInterfaces.md).

Custom connectors are first-class citizens; they register in the same catalogue and receive the same treatment as pre-shipped ones. Connectors can be bundled with the application or loaded at runtime from connector packages (zip archives) referenced in configuration. The library ships with broad pre-built coverage (full catalogue in [ConnectorCatalogue.md](ConnectorCatalogue.md)); standard capabilities require zero configuration beyond API keys.

| Connector type | Function | Interface | Pre-shipped |
| --- | --- | --- | --- |
| **Provider** | Expose AI models and web APIs through an OpenAI-compatible interface | complete, check_quota, report_usage, list_models | `openai.llm.v1`, `google.gemini.v1`, `huggingface.inference.v1`, `openrouter.gateway.v1`, `cloudflare.workers-ai.v1` |
| **Rotation policy** | Govern model lifecycle: deactivation, recovery, selection | deactivate, recover, select | `modelmesh.stick-until-failure.v1`, `modelmesh.priority-selection.v1`, `modelmesh.round-robin.v1`, `modelmesh.cost-first.v1`, `modelmesh.latency-first.v1`, `modelmesh.session-stickiness.v1`, `modelmesh.rate-limit-aware.v1`, `modelmesh.load-balanced.v1` |
| **Secret store** | Resolve API keys and tokens from secure backends | get, set, list, delete | `modelmesh.env.v1`, `modelmesh.dotenv.v1`, `aws.secrets-manager.v1`, `google.secret-manager.v1`, `microsoft.key-vault.v1`, `1password.connect.v1` |
| **Storage** | Persist state, configuration, and logs to external backends | load, save, list, delete, stat, exists, acquire, release | `modelmesh.local-file.v1`, `aws.s3.v1`, `google.drive.v1`, `redis.redis.v1` |
| **Observability** | Export routing decisions, request logs, and statistics | emit, log, flush | `modelmesh.console.v1`, `modelmesh.local-file.v1`, `modelmesh.webhook.v1` |
| **Discovery** | Sync model catalogues and monitor provider health | sync, probe | `modelmesh.registry-sync.v1`, `modelmesh.health-monitor.v1` |

### Connector Development Kit (CDK)

The **Connector Development Kit** is the class library used to build both pre-shipped and custom connectors. It provides generic base classes with sensible default behavior for each connector type, so a new connector can be created with minimal code. Users who need specialized behavior can derive from an existing connector and override only the methods that differ, inheriting everything else. The same CDK classes that the library uses internally are available to users, making custom connectors indistinguishable from pre-shipped ones. CDK architecture, base classes, and tutorials are in [cdk/Overview.md](cdk/Overview.md).

### Object Identification — Dot-Notated ID Strings

Every object in the system has a **unique dot-notated ID string** that establishes its identity, scope, and lineage. Dot-notation ensures global uniqueness across object types, makes relationships explicit, and provides a human-readable namespace. The general form is `scope.name` or `scope.name.qualifier`, where each segment narrows the context from left to right.

| Object type | Pattern | Examples |
| --- | --- | --- |
| **Model** | `vendor.model-name` | `openai.gpt-4o`, `anthropic.claude-sonnet-4`, `google.gemini-2.0-flash`, `deepseek.deepseek-chat` |
| **Provider connector** | `vendor.service.version` | `openai.llm.v1`, `google.gemini.v1`, `anthropic.claude.v1`, `huggingface.inference.v1` |
| **Rotation policy** | `vendor.policy-name.version` | `modelmesh.stick-until-failure.v1`, `modelmesh.cost-first.v1`, `modelmesh.round-robin.v1` |
| **Secret store** | `vendor.store-type.version` | `modelmesh.env.v1`, `aws.secrets-manager.v1`, `google.secret-manager.v1` |
| **Storage** | `vendor.backend.version` | `modelmesh.local-file.v1`, `aws.s3.v1`, `redis.redis.v1` |
| **Observability** | `vendor.output.version` | `modelmesh.console.v1`, `modelmesh.webhook.v1`, `modelmesh.local-file.v1` |
| **Discovery** | `vendor.strategy.version` | `modelmesh.registry-sync.v1`, `modelmesh.health-monitor.v1` |
| **Capability** | `category.subcategory.leaf` | `generation.text-generation.chat-completion`, `representation.embeddings.text-embeddings` |
| **Pool** | `category.subcategory` or `category.leaf` | `generation.text-generation`, `representation.embeddings`, `understanding.vision-understanding` |
| **System service** | `system.service-name` | `system.router`, `system.state-manager`, `system.capability-resolver`, `system.event-emitter` |
| **Configuration section** | `config.section.subsection` | `config.providers`, `config.pools.rotation`, `config.observability.routing` |

**Rules:**

1. **Globally unique.** No two objects of the same type share an ID string. Objects of different types may share a prefix (e.g., model `openai.gpt-4o` and connector `openai.llm.v1` both start with `openai`), but the type context disambiguates them.
2. **Vendor-scoped.** The first segment is the vendor or organization that owns the object (`openai`, `google`, `modelmesh`, `aws`). Custom objects use the user's organization name (e.g., `acmecorp.internal-llm.v1`).
3. **Version-qualified for connectors.** All connector IDs end with a version segment (`.v1`, `.v2`). This enables side-by-side versioning: `openai.llm.v1` and `openai.llm.v2` can coexist in the catalogue.
4. **Hierarchy-scoped for capabilities and pools.** Capability IDs mirror the capability tree path. Pool IDs default to the capability node they target — a pool targeting `generation.text-generation` has ID `generation.text-generation`.
5. **Case and characters.** IDs are lowercase with hyphens separating words within a segment. Dots separate segments. Valid characters: `[a-z0-9\-\.]`. Examples: `openai.gpt-4o-mini`, `modelmesh.rate-limit-aware.v1`.
6. **Referencing.** Configuration, logs, and API responses always use the full dot-notated ID to reference objects. Abbreviated forms are never used in machine-readable contexts.

---

## Model Capability Hierarchy

Model capabilities form a **hierarchical tree**. Parent nodes are categories; leaf nodes are concrete, routable capabilities (full tree in [ModelCapabilities.md](ModelCapabilities.md)).

| Category           | Produces            | Example leaves                                  |
| ------------------ | ------------------- | ----------------------------------------------- |
| **generation**     | new content         | chat-completion, text-to-image, text-to-speech  |
| **understanding**  | analysis of input   | summarization, ocr, speech-to-text              |
| **transformation** | converted content   | translation, background-removal, voice-cloning  |
| **representation** | encoded data        | text-embeddings, image-embeddings               |
| **retrieval**      | found information   | semantic-search, grounded-generation, reranking |
| **interaction**    | multi-step behavior | tool-calling, agent-execution                   |
| **evaluation**     | quality assessment  | content-moderation, factuality-checking         |

**Rules:** Models register at leaf nodes. Pools can target any node and include all descendants. Requesting `understanding` matches all understanding models; requesting `ocr` matches only that leaf. A model with multiple leaves appears in multiple ancestor pools automatically.

The hierarchy is extensible. Users can add custom categories, subcategories, and leaf nodes (e.g., `compliance` → `pii-detection`, `regulatory-review`). Custom nodes follow the same routing, pooling, and inheritance rules as pre-shipped ones.

---

## Model Definitions

A model definition is a **capability contract**, a declaration of what an application can expect when routing through that model. Attributes fall into four categories:

- **Capability**: what tasks the model performs (e.g., chat-completion, ocr)
- **Delivery**: how results arrive (synchronous, streaming, or batch)
- **Feature**: optional behaviors (e.g., tool calling, structured output, grounding)
- **Constraint**: operational limits (e.g., context window, max output tokens)

Capabilities and delivery modes are orthogonal: `chat-completion` supports sync, streaming, and batch, while `web-search` supports only sync. Full attribute reference in [SystemConfiguration.md — Models](SystemConfiguration.md#models).

---

## Capability-Based Model Pools

A **capability pool** groups models that fulfill the same type of task. Pools are defined by a capability node, not by provider, and collect all models registered at that node or its descendants.

The library ships with predefined pools for common capabilities ([ModelCapabilities.md — Predefined Pools](ModelCapabilities.md#predefined-capability-pools)). Users add custom pools (e.g., `code-review`, `medical-summarization`, `long-context-analysis`) with the same rotation and failover logic.

Pool membership is automatic: a model definition registered at `chat-completion`, `ocr`, and `tool-calling` leaf nodes joins the `generation`, `understanding`, `interaction`, and all ancestor pools without manual assignment.

### Static and Dynamic Pool Definitions

Pools can be defined in two ways:

- **Static**: specify a capability node, optionally filter by providers or models, and list additional requirements. Defined via YAML or API.
- **Dynamic**: provide a selection function that scores each candidate model based on any combination of attributes (capabilities, delivery modes, features, constraints, provider properties).

---

## Providers

A provider exposes one or more models through a specific API via a **provider connector** that implements a uniform, OpenAI-compatible interface. The model definition describes *what the AI can do*; the provider connector describes *how it is accessed and managed*: authentication, quota, rate limits, cost, availability. A provider registers a single connector for all its models (the default) or per-model connectors when distinct handling is required.

**Two responsibility areas:**

- **Model operations**: authentication, request execution, error reporting, quota tracking, rate-limit monitoring, cost metadata
- **Infrastructure capabilities**: model discovery, batch operations, file management, fine-tuning

Infrastructure capabilities feed routing directly: discovery, quota, and pricing data inform model selection and proactive rotation. Providers report operational data; the pool's [rotation policy](#model-rotation-failover-and-state) acts on it. Details in [ConnectorInterfaces.md — Provider](ConnectorInterfaces.md#provider) and [Provider Interface](interfaces/Provider.md).

---

## Model Rotation, Failover, and State

Within each pool, every model is classified as **Active** (eligible for routing) or **Standby** (temporarily excluded). A **rotation policy** governs transitions through three components (deactivation, recovery, and selection), configured independently per pool. Rotation operates at model level (individual model moves to standby) or provider level (provider-wide issue deactivates all its models across all pools). The library tracks each model's state (failure counts, cooldown timers, quota usage) and persists it through [storage connectors](#persistent-storage). All policy attributes in [SystemConfiguration.md — Pools](SystemConfiguration.md#pools).

### Deactivation Triggers

A model moves to standby based on: **error-based** (failure count, error rate, specific HTTP codes), **request-count-based** (request cap, token limit, cost budget), or **time-based** (quota period expiry, maintenance window). Request-count-based triggers enable **free-tier aggregation**: when one provider's free quota is exhausted, rotation selects the next active provider, chaining quotas automatically.

### Recovery Triggers

A standby model returns to active through: **startup probe**, **cooldown** (fixed delay), **calendar** (aligned with quota resets), **periodic probe**, or **manual** API command.

### Selection Strategies

Pre-shipped: `modelmesh.stick-until-failure.v1` (default), `modelmesh.priority-selection.v1`, `modelmesh.round-robin.v1`, `modelmesh.cost-first.v1`, `modelmesh.latency-first.v1`, `modelmesh.session-stickiness.v1`, `modelmesh.rate-limit-aware.v1`, `modelmesh.load-balanced.v1`. **Rate-limit-aware** switches models preemptively before hitting limits; **load-balanced** distributes requests proportionally to each model's rate-limit headroom. Strategy details in [SystemConfiguration.md — Pools](SystemConfiguration.md#pools).

### Intelligent Retry

Before rotating, the router retries the same model with configurable backoff (fixed, exponential with jitter, or provider `Retry-After`). Retryable errors (timeouts, 500, 503) are retried; non-retryable errors (400, 401, 403) trigger immediate rotation. Retry attempts count toward the deactivation threshold. Scope is configurable: same model, same provider, or cross-provider.

### Pre-shipped and Custom Policies

The library ships pre-built policy connectors for each component. Users can replace individual components or the entire policy, via [configuration](#configuration) or at runtime.

---

## Request Routing Pipeline

Each request passes through: capability resolution → pool selection → delivery mode filter → state filter (exclude standby models) → selection strategy → intelligent retry. The pipeline combines capability hierarchy, model attributes, pool state, and rotation policy to select the best available model. Example in [SystemConfiguration.md — Routing Pipeline](SystemConfiguration.md#routing-pipeline-example).

---

## OpenAI-Compatible Interface

The library exposes an **OpenAI-compatible interface**. Applications interact with it using standard OpenAI SDK calls (`chat.completions`, `embeddings`, `audio.speech`, etc.). Requests use **virtual model names** that map to configured pools; a call to `text-generation` resolves to the best active real model and provider, with format translation, failover, and state management handled transparently.

The library provides a `ChatOpenAI`-compatible interface, so LangChain and LangGraph pipelines connect directly. The interface is not limited to AI models; web API services such as document parsing, content moderation, or search APIs can be wrapped as provider connectors, gaining rotation, quota management, and failover through the same unified interface.

---

## OpenAI-Compatible Proxy

The library comes with a **build script** that packages it with selected connectors, policies, and a YAML configuration into a Docker image. The resulting container exposes standard OpenAI API endpoints (`/v1/chat/completions`, `/v1/embeddings`, etc.) that any application or framework can connect to without embedding the library.

This decouples routing from application code: multiple applications (LangChain pipelines, IDE assistants, internal tools) share a single proxy with centralized configuration, credential management, and state. The proxy supports all library features and can be deployed alongside applications or as a shared service.

---

## Deployment Modes

| Mode | Description | Best for |
| --- | --- | --- |
| **Embedded library** | Server-side or desktop. Calls provider APIs and exposes a drop-in OpenAI SDK replacement. | backends, CLI tools, desktop apps, LangChain/LangGraph pipelines |
| **Client library** | Browser client. Calls provider APIs directly with client-side routing. | single-page apps, browser-based tools |
| **OpenAI-compatible proxy** | Standalone Docker container exposing standard OpenAI API endpoints. Any OpenAI SDK or REST client connects without embedding the library. | multi-app environments, IDE integrations, shared infrastructure |

---

## Browser Compatibility

ModelMesh Lite runs in web browsers via the **BrowserBaseProvider** class and a dedicated browser entry point. `BrowserBaseProvider` mirrors the full `BaseProvider` interface but uses the Fetch API and `ReadableStream` instead of Node.js `http`/`https` modules and Node streams. The same protected hooks (`_buildHeaders`, `_buildRequestPayload`, `_parseResponse`, `_parseSseChunk`, `_getCompletionEndpoint`) are available for subclassing, so browser providers are built with the same patterns as server-side providers.

### CORS Proxy Support

Most AI provider APIs do not send CORS headers, so browsers block direct requests. `BrowserBaseProvider` accepts an optional `proxyUrl` configuration field. When set, all API URLs are prefixed with the proxy URL, routing requests through a lightweight CORS proxy that adds the required headers. The library ships with a minimal transparent CORS proxy in `tools/cors-proxy/` (Node.js script, Docker Compose included).

### Two Modes

| Mode | When to use | Configuration |
| --- | --- | --- |
| **With CORS proxy** | Standard web pages calling any AI provider API | Set `proxyUrl` in `BrowserBaseProvider` config |
| **Direct access** | Browser extensions with `host_permissions`, providers that send CORS headers (e.g., Anthropic), non-browser runtimes | Omit `proxyUrl` |

### Browser Entry Point

For bundlers (Webpack, Vite, esbuild), import from `@nistrapa/modelmesh-core/browser` to exclude Node.js-dependent modules (`ProxyServer`, `FileSecretStore`, `HttpHealthDiscovery`, file-backed `KeyValueStorage`). The `createBrowser()` convenience function provides a browser-optimized equivalent of `modelmesh.create()`.

Full browser usage guide in [guides/BrowserUsage.md](guides/BrowserUsage.md).

---

## Configuration

The system is configured declaratively via YAML, programmatically via API, or both. Configuration can be serialized to and deserialized from [persistent storage connectors](#persistent-storage), enabling centralized management and sharing across instances. Full YAML reference in [SystemConfiguration.md](SystemConfiguration.md).

---

## Credential Management

API keys and tokens must never be hardcoded in configuration or source code. **Secret store connectors** resolve credentials from secure backends (environment variables, cloud secret managers, vaults) at runtime. Configuration references secrets by name (`${secrets:openai-key}`); the library resolves them at initialization through the configured store. A **CLI utility** publishes and manages credentials across stores. Pre-shipped stores and deployment patterns in [ConnectorCatalogue.md](ConnectorCatalogue.md).

---

## Persistent Storage

**Storage connectors** serialize and deserialize library data to external backends. Three data types flow through them:

- **State**: model health, failure counts, cooldown timers, quota usage
- **Configuration**: providers, pools, policies, credential references
- **Observability logs**: routing decisions, request records, aggregate statistics

**Sync policies:** `in-memory` (no persistence), `sync-on-boundary` (load/save at startup/shutdown), `periodic` (configurable interval), `immediate` (every state change).

Pre-shipped connectors include `modelmesh.local-file.v1`, `aws.s3.v1`, `google.drive.v1`, and `redis.redis.v1` (full table in [ConnectorCatalogue.md](ConnectorCatalogue.md)). Custom connectors implement the same interface and register in the connector catalogue. Details in [SystemConfiguration.md](SystemConfiguration.md).

---

## Observability

Three levels of visibility into routing and provider behavior:

- **Routing decisions**: per-request provider selection, reason, fallback chain, rotation triggers
- **Request/response logging**: configurable detail (metadata only, truncated summary, or full payloads)
- **Aggregate statistics**: per-model, per-provider, per-pool request counts, token usage, cost, latency, downtime, rotation events

Data exports through pluggable **observability connectors**; multiple can be active simultaneously (e.g., webhook for alerts + file for dashboards). Full metrics, API, and configuration in [SystemConfiguration.md — Observability](SystemConfiguration.md#observability).

---

## Discovery

Two connectors keep the model catalogue accurate and provider health visible without manual intervention.

### Model Registry Sync

Synchronizes the local model catalogue with provider APIs on a configurable schedule. Detects **new models**, **deprecated models**, and **pricing changes**, updating the catalogue automatically. Sync frequency and auto-registration behavior are configurable per provider. Changes are logged through [observability connectors](#observability).

### Health Monitor

Background process that probes configured providers at a configurable interval. Records latency, success/failure, and error codes; maintains rolling availability scores; feeds results into the [rotation policy](#model-rotation-failover-and-state) for proactive deactivation. Probe frequency, timeout, and failure thresholds are configurable per provider.

Both are pluggable; pre-shipped implementations and extension points in [ConnectorCatalogue.md](ConnectorCatalogue.md).

---

## Documentation and Samples

ModelMesh Lite ships with a **User Manual** (integration, configuration, deployment), a **Developer Manual** (custom connectors, extending the hierarchy, contributing), and an extensive sample collection.

---

## Key Features

| Feature                          | Description                                                                                                |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **OpenAI-compatible interface**  | drop-in replacement for any OpenAI SDK client; virtual model names abstract pools, policies, and providers |
| **Unified API**                  | single integration point for multiple providers                                                            |
| **Model capability hierarchy**   | structured, extensible AI task taxonomy                                                                    |
| **Capability-based model pools** | group models by capability, static or dynamic membership                                                   |
| **Model rotation policies**      | pluggable per-pool lifecycle: deactivation, recovery, and selection with model- and provider-level actions |
| **Rate-limit-aware selection**   | proactive throttling avoidance and load balancing across models by absolute or relative capacity           |
| **Intelligent retry**            | configurable backoff before rotation; reduces false rotations on transient errors                          |
| **Discovery connectors**         | automatic model catalogue sync and continuous provider health monitoring                                   |
| **Delivery modes**               | synchronous, streaming, batch                                                                              |
| **Free-tier aggregation**        | combine free quotas across providers                                                                       |
| **Declarative configuration**    | YAML + runtime API with per-pool policies                                                                  |
| **Credential management**        | pluggable secure API key and token resolution                                                              |
| **Persistent storage**           | pluggable backends for state, configuration, and logs (local, S3, Google Drive, Redis)                     |
| **Pluggable architecture**       | extensible connector interfaces at every point, with runtime package loading                               |
| **OpenAI-compatible proxy**      | build script packages library and configuration into a Docker container exposing standard OpenAI API       |
| **Observability**                | routing decisions, logging, aggregate statistics                                                           |
| **Documentation and samples**    | user manual, developer manual, and extensive sample collection                                             |
| **Connector Development Kit**    | base classes, mixins, and test utilities for building custom connectors with minimal code                   |
| **Cross-language**               | Python and TypeScript                                                                                      |

---

The capability taxonomy and predefined pools are in **[ModelCapabilities.md](ModelCapabilities.md)**. Runtime objects and services (Router, CapabilityPool, Model, Provider, and others) are in **[SystemServices.md](SystemServices.md)** with individual service docs in **[system/](system/Overview.md)**. Connector interface definitions are in **[ConnectorInterfaces.md](ConnectorInterfaces.md)** with full interface specifications in **[interfaces/](interfaces/Provider.md)**. The full connector and provider catalogue is in **[ConnectorCatalogue.md](ConnectorCatalogue.md)** with individual connector docs in **[connectors/](connectors/openai-llm.md)**. YAML configuration reference is in **[SystemConfiguration.md](SystemConfiguration.md)**. The Connector Development Kit documentation is in **[cdk/Overview.md](cdk/Overview.md)** with base class reference in **[cdk/BaseClasses.md](cdk/BaseClasses.md)** and tutorials in **[cdk/DeveloperGuide.md](cdk/DeveloperGuide.md)**.

For a hands-on introduction with working code samples, see the **[FAQ](guides/FAQ.md)** and **[Quick Start](guides/QuickStart.md)** guides.
