# ModelMesh Lite

**Capability-driven AI routing library for Python and JavaScript. A single integration point for multiple AI providers with automatic rotation to aggregate free tiers, minimize cost, and maintain service continuity.**

> Applications request capabilities. ModelMesh Lite manages providers, quotas, costs, and failover.

---

## Why

AI applications need *capabilities* (text generation, image generation, embeddings, speech) and do not care about specific providers. Coupling to one provider means quota exhaustion halts the app, rate limits cause interruptions, outages remove entire capabilities, and each provider needs its own integration code.

ModelMesh Lite separates **what the application needs** from **who delivers it**: provider rotation avoids downtime, free-tier aggregation combines quotas, capability-based routing prevents lock-in, and a unified API simplifies development.

---

## Architecture Overview

Each request resolves in two stages: **capability selection** (choose a pool matching the requested capability) and **model resolution** (select the best active model and its provider). Applications remain stable even when providers change.

**System layers:** Application → Router → Pool → Model → Provider. The application requests a capability; the router resolves it to a pool; the pool groups models that fulfill it; each model declares capabilities and constraints; providers expose models and manage quotas. The router selects the best active model, routes through its provider, and handles rotation on failure.

### Connector-Based Extensibility

Every integration point is a **connector**, a class or function implementing a defined interface (providers, rotation policies, secret stores, storage backends, observability outputs). Each connector type has a **connector catalogue**, a registry of available implementations with code, metadata, and a configuration schema.

Custom connectors are first-class citizens; they register in the same catalogue and receive the same treatment as pre-shipped ones. Connectors can be bundled with the application or loaded at runtime from connector packages (zip archives) referenced in configuration. The library ships with broad pre-built coverage ([Appendix G](APPENDICES.md#appendix-g--pre-shipped-connectors)); standard capabilities require zero configuration beyond API keys.

---

## Model Capability Hierarchy

Model capabilities form a **hierarchical tree**. Parent nodes are categories; leaf nodes are concrete, routable capabilities (full tree in [Appendix A](APPENDICES.md#appendix-a--model-capability-hierarchy)).

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

Capabilities and delivery modes are orthogonal: `chat-completion` supports sync, streaming, and batch, while `web-search` supports only sync. Full attribute reference in [Appendix C](APPENDICES.md#appendix-c--model-attribute-reference).

---

## Capability-Based Model Pools

A **capability pool** groups models that fulfill the same type of task. Pools are defined by a capability node, not by provider, and collect all models registered at that node or its descendants.

The library ships with predefined pools for common capabilities ([Appendix B](APPENDICES.md#appendix-b--predefined-capability-pools)). Users add custom pools (e.g., `code-review`, `medical-summarization`, `long-context-analysis`) with the same rotation and failover logic.

Pool membership is automatic: a model definition registered at `chat-completion`, `ocr`, and `tool-calling` leaf nodes joins the `text-generation`, `vision-understanding`, `interaction`, and all ancestor pools without manual assignment.

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

Infrastructure capabilities feed routing directly: discovery, quota, and pricing data inform model selection and proactive rotation. Providers report operational data; the pool's [rotation policy](#model-rotation-failover-and-state) acts on it. Details in [Appendix D](APPENDICES.md#appendix-d--provider-infrastructure-capabilities) and [Appendix E](APPENDICES.md#appendix-e--provider-schema-examples).

---

## Model Rotation, Failover, and State

Within each pool, every model is classified as **Active** (eligible for routing) or **Standby** (temporarily excluded). A **rotation policy** governs transitions through three components (deactivation, recovery, and selection), configured independently per pool. Rotation operates at model level (individual model moves to standby) or provider level (provider-wide issue deactivates all its models across all pools). The library tracks each model's state (failure counts, cooldown timers, quota usage) and persists it through [storage connectors](#persistent-storage). All policy attributes in [Appendix F](APPENDICES.md#appendix-f--per-pool-rotation-policy-attributes).

### Deactivation Triggers

A model moves to standby based on: **error-based** (failure count, error rate, specific HTTP codes), **request-count-based** (request cap, token limit, cost budget), or **time-based** (quota period expiry, maintenance window).

### Recovery Triggers

A standby model returns to active through: **startup probe**, **cooldown** (fixed delay), **calendar** (aligned with quota resets), **periodic probe**, or **manual** API command.

### Selection Strategies

Pre-shipped: `stick-until-failure` (default), `priority-selection`, `round-robin`, `cost-first`, `latency-first`, `session-stickiness`, `rate-limit-aware`, `load-balanced`. **Rate-limit-aware** switches models preemptively before hitting limits; **load-balanced** distributes requests proportionally to each model's rate-limit headroom. Strategy details in [Appendix F](APPENDICES.md#appendix-f--per-pool-rotation-policy-attributes).

### Intelligent Retry

Before rotating, the router retries the same model with configurable backoff (fixed, exponential with jitter, or provider `Retry-After`). Retryable errors (timeouts, 500, 503) are retried; non-retryable errors (400, 401, 403) trigger immediate rotation. Retry attempts count toward the deactivation threshold. Scope is configurable: same model, same provider, or cross-provider.

### Pre-shipped and Custom Policies

The library ships pre-built policy connectors for each component. Users can replace individual components or the entire policy, via [configuration](#configuration) or at runtime.

---

## Request Routing Pipeline

Each request passes through: capability resolution → pool selection → delivery mode filter → state filter (exclude standby models) → selection strategy → intelligent retry. The pipeline combines capability hierarchy, model attributes, pool state, and rotation policy to select the best available model. Example in [Appendix H](APPENDICES.md#appendix-h--configuration-and-api-examples).

---

## OpenAI-Compatible Interface

The library exposes an **OpenAI-compatible interface**. Applications interact with it using standard OpenAI SDK calls (`chat.completions`, `embeddings`, `audio.speech`, etc.). Requests use **virtual model names** that map to configured pools; a call to `text-generation` resolves to the best active real model and provider, with format translation, failover, and state management handled transparently.

The library provides a `ChatOpenAI`-compatible interface, so LangChain and LangGraph pipelines connect directly. The interface is not limited to AI models; web API services such as document parsing, content moderation, or search APIs can be wrapped as provider connectors, gaining rotation, quota management, and failover through the same unified interface.

---

## OpenAI-Compatible Proxy

The library comes with a **build script** that packages it with selected connectors, policies, and a YAML configuration into a Docker image. The resulting container exposes standard OpenAI API endpoints (`/v1/chat/completions`, `/v1/embeddings`, etc.) that any application or framework can connect to without embedding the library.

This decouples routing from application code: multiple applications (LangChain pipelines, IDE assistants, internal tools) share a single proxy with centralized configuration, credential management, and state. The proxy supports all library features and can be deployed alongside applications or as a shared service.

---

## Configuration

The system is configured declaratively via YAML, programmatically via API, or both. Configuration can be serialized to and deserialized from [persistent storage connectors](#persistent-storage), enabling centralized management and sharing across instances. Examples in [Appendix H](APPENDICES.md#appendix-h--configuration-and-api-examples); policy attributes in [Appendix F](APPENDICES.md#appendix-f--per-pool-rotation-policy-attributes).

---

## Credential Management

API keys and tokens must never be hardcoded in configuration or source code. **Secret store connectors** resolve credentials from secure backends (environment variables, cloud secret managers, vaults) at runtime. Configuration references secrets by name (`${secrets:openai-key}`); the library resolves them at initialization through the configured store. A **CLI utility** publishes and manages credentials across stores. Pre-shipped stores and deployment patterns in [Appendix G](APPENDICES.md#appendix-g--pre-shipped-connectors).

---

## Persistent Storage

**Storage connectors** serialize and deserialize library data to external backends. Three data types flow through them:

- **State**: model health, failure counts, cooldown timers, quota usage
- **Configuration**: providers, pools, policies, credential references
- **Observability logs**: routing decisions, request records, aggregate statistics

**Sync policies:** `in-memory` (no persistence), `sync-on-boundary` (load/save at startup/shutdown), `periodic` (configurable interval), `immediate` (every state change).

Pre-shipped connectors include `local-file`, `s3`, `google-drive`, and `redis` (full table in [Appendix G](APPENDICES.md#appendix-g--pre-shipped-connectors)). Custom connectors implement the same interface and register in the connector catalogue. Details in [Appendix H](APPENDICES.md#appendix-h--configuration-and-api-examples).

---

## Observability

Three levels of visibility into routing and provider behavior:

- **Routing decisions**: per-request provider selection, reason, fallback chain, rotation triggers
- **Request/response logging**: configurable detail (metadata only, truncated summary, or full payloads)
- **Aggregate statistics**: per-model, per-provider, per-pool request counts, token usage, cost, latency, downtime, rotation events

Data exports through pluggable **observability connectors**; multiple can be active simultaneously (e.g., webhook for alerts + file for dashboards). Full metrics, API, and configuration in [Appendix I](APPENDICES.md#appendix-i--observability-reference).

---

## Discovery Connectors

Two connectors keep the model catalogue accurate and provider health visible without manual intervention.

### Model Registry Sync

Synchronizes the local model catalogue with provider APIs on a configurable schedule. Detects **new models**, **deprecated models**, and **pricing changes**, updating the catalogue automatically. Sync frequency and auto-registration behavior are configurable per provider. Changes are logged through [observability connectors](#observability).

### Health Monitor

Background process that probes configured providers at a configurable interval. Records latency, success/failure, and error codes; maintains rolling availability scores; feeds results into the [rotation policy](#model-rotation-failover-and-state) for proactive deactivation. Probe frequency, timeout, and failure thresholds are configurable per provider.

Both are pluggable; pre-shipped implementations and extension points in [Appendix G](APPENDICES.md#appendix-g--pre-shipped-connectors).

---

## Documentation and Samples

ModelMesh Lite ships with a **User Manual** (integration, configuration, deployment), a **Developer Manual** (custom connectors, extending the hierarchy, contributing), and an extensive sample collection.

---

## Key Features

|                                  |                                                                                                            |
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
| **Cross-language**               | Python and JavaScript                                                                                      |

---

Appendices A–I (capability hierarchy, predefined pools, model attributes, provider infrastructure, provider schemas, rotation policy attributes, connector summary, configuration examples, observability reference) are in **[APPENDICES.md](APPENDICES.md)**. The full connector and provider catalogue is in **[ConnectorCatalogue.md](ConnectorCatalogue.md)**.
