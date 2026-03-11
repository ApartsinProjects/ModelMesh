---
layout: default
title: "System Services Overview"
---

# System Services Overview

ModelMesh Lite is composed of a set of cooperating runtime services that together implement capability-based routing, model lifecycle management, provider abstraction, and observability. This document describes the overall architecture, initialization sequence, request flow, and service groupings. For conceptual foundations see [SystemConcept.md](../SystemConcept.md); for YAML configuration see [SystemConfiguration.md](../SystemConfiguration.md).

---

## Service Dependency Diagram

```
ModelMesh (facade)
├── Router
│   ├── RoutingPipeline
│   │   ├── CapabilityResolver → CapabilityTree
│   │   ├── DeliveryFilter
│   │   ├── StateFilter
│   │   └── SelectionStrategy
│   ├── RetryPolicy
│   └── CapabilityPool[]
│       ├── Model[] → ModelState
│       ├── Provider[] → ProviderState
│       └── RotationPolicy
│           ├── DeactivationEvaluator
│           ├── RecoveryEvaluator
│           └── SelectionStrategy
├── ModelRegistry
├── ConnectorRegistry
├── OpenAIClient → Router
├── ProxyServer → Router
├── EventEmitter → ObservabilityConnector[]
├── RequestLogger → ObservabilityConnector[]
├── StatisticsCollector → ObservabilityConnector[]
├── SecretResolver → SecretStoreConnector
└── StateManager → StorageConnector
```

---

## Initialization Sequence

The following steps execute in order when `ModelMesh.initialize(config)` is called:

1. **Parse configuration** -- Load YAML or programmatic configuration into the internal `MeshConfig` structure.
2. **Register connectors** -- Instantiate the `ConnectorRegistry` and load all built-in and custom connector packages.
3. **Resolve secrets** -- Initialize the `SecretResolver` with the configured secret store connector. Resolve all `${secrets:name}` references in the configuration.
4. **Load persisted state** -- Initialize the `StateManager` with the configured storage connector. Call `load()` to restore `ModelState`, `ProviderState`, and pool memberships from the previous session.
5. **Build capability tree** -- Construct the `CapabilityTree` from the default hierarchy plus any custom extensions declared in configuration.
6. **Register models and providers** -- Populate the `ModelRegistry` with model definitions from configuration. Instantiate `Provider` wrappers for each configured provider.
7. **Build capability pools** -- Create `CapabilityPool` instances for each configured pool, assign models based on capability node membership, and attach `RotationPolicy` components.
8. **Wire the routing pipeline** -- Assemble the `RoutingPipeline` with default stages (CapabilityResolver, pool selection, DeliveryFilter, StateFilter, SelectionStrategy, RetryPolicy).
9. **Initialize the router** -- Create the `Router` with the assembled pipeline and pool set.
10. **Start observability services** -- Initialize `EventEmitter`, `RequestLogger`, and `StatisticsCollector` with their configured observability connectors.
11. **Start background services** -- Launch discovery sync, health monitor probes, periodic state sync, and statistics flush timers.

---

## Request Flow

A typical synchronous completion request follows this path:

1. The application calls `OpenAIClient.chat.completions.create(model="text-generation", messages=[...])` or sends an HTTP request to `ProxyServer` at `POST /v1/chat/completions`.
2. The virtual model name `"text-generation"` is passed to `Router.complete()` as the capability identifier.
3. The `Router` invokes `RoutingPipeline.execute()`, which runs each stage in sequence:
   - **CapabilityResolver** maps `"text-generation"` to matching `CapabilityPool` instances using the `CapabilityTree`.
   - **Pool selection** chooses the target pool (single match or priority-based).
   - **DeliveryFilter** excludes models that do not support the requested delivery mode (sync, streaming, or batch).
   - **StateFilter** excludes standby models and models from deactivated providers.
   - **SelectionStrategy** scores remaining candidates and selects the best model.
4. The `Router` sends the request to the selected `Provider.execute()`, which delegates to the underlying provider connector.
5. On success, the response flows back through the `Router`. `RequestLogger` records the request, `StatisticsCollector` buffers metrics, and `ModelState` is updated.
6. On failure, `RetryPolicy` determines whether to retry the same model (with backoff) or rotate to the next candidate. If deactivation thresholds are reached, the `RotationPolicy` moves the model to standby and `EventEmitter` publishes a `model_deactivated` event.

---

## Service Groupings

| Group | Services | Purpose |
| --- | --- | --- |
| **Facade** | [ModelMesh](ModelMesh.md) | Library entry point; initializes and wires all subsystems |
| **Routing** | [Router](Router.md), [RoutingPipeline](RoutingPipeline.md), [CapabilityResolver](CapabilityResolver.md), [DeliveryFilter](DeliveryFilter.md), [StateFilter](StateFilter.md), [RetryPolicy](RetryPolicy.md) | Request orchestration, pipeline stages, and retry logic |
| **Pools & Models** | [CapabilityPool](CapabilityPool.md), [Model](Model.md), [ProviderService](ProviderService.md), [ModelState](ModelState.md), [ProviderState](ProviderState.md) | Model grouping, runtime state, and provider abstraction |
| **Rotation** | [RotationPolicyService](RotationPolicyService.md), [DeactivationEvaluator](DeactivationEvaluator.md), [RecoveryEvaluator](RecoveryEvaluator.md), [SelectionStrategy](SelectionStrategy.md) | Deactivation, recovery, and selection governance |
| **Registries** | [ModelRegistry](ModelRegistry.md), [ConnectorRegistry](ConnectorRegistry.md), [CapabilityTree](CapabilityTree.md) | Model catalogue, connector catalogue, capability hierarchy |
| **External Interfaces** | [OpenAIClient](OpenAIClient.md), [ProxyServer](ProxyServer.md) | Application-facing API surfaces |
| **Observability** | [EventEmitter](EventEmitter.md), [RequestLogger](RequestLogger.md), [StatisticsCollector](StatisticsCollector.md) | Events, logging, and metrics |
| **Infrastructure** | [SecretResolver](SecretResolver.md), [StateManager](StateManager.md) | Secret resolution and state persistence |

---

## Cross-References

- [SystemConcept.md](../SystemConcept.md) -- Conceptual architecture, design principles, and capability model
- [SystemConfiguration.md](../SystemConfiguration.md) -- Full YAML configuration reference
- [SystemServices.md](../SystemServices.md) -- Consolidated service reference (source for individual docs)
- [ConnectorInterfaces.md](../ConnectorInterfaces.md) -- Connector API contracts
