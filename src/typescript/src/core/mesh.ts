/**
 * ModelMesh -- library facade.
 *
 * The ModelMesh class is the central orchestration object. It manages
 * providers, capability pools, routing, state tracking, and event emission.
 * Applications typically interact through the MeshClient returned by
 * getClient() rather than calling ModelMesh directly.
 */

import { CapabilityTree } from "./capability-tree";
import { EventEmitter } from "./event-emitter";
import { CapabilityPool, createPoolModel } from "./pool";
import type { PoolModel } from "./pool";
import { Router } from "./router";
import { StateManager } from "./state-manager";
import type { MeshClient } from "../client/mesh-client";
import type {
  CompletionRequest,
  CompletionResponse,
  ProviderConnector,
} from "../interfaces/provider";
import type { ObservabilityConnector, TraceEntry } from "../interfaces/observability";
import { Severity } from "../interfaces/observability";
import { ModelStatus } from "../interfaces/rotation";
import { MeshConfig } from "../config/mesh-config";
import { NullObservabilityConnector } from "../connectors/observability/null-connector";
import { CONNECTOR_REGISTRY } from "../connectors";

/**
 * Library facade. Manages providers, pools, routing, and state.
 *
 * Lifecycle:
 *
 *   const mesh = new ModelMesh();
 *   mesh.initialize(config);
 *   const router = mesh.getRouter();
 *   // ... use router ...
 *   mesh.shutdown();
 *
 * The facade is intentionally thin: it delegates routing to Router,
 * state tracking to StateManager, and event publishing to EventEmitter.
 */
export class ModelMesh {
  private _config: MeshConfig | null = null;
  private _router: Router | null = null;
  private _pools: Record<string, CapabilityPool> = {};
  private _providers: Record<string, ProviderConnector> = {};
  private _stateManager = new StateManager();
  private _eventEmitter = new EventEmitter();
  private _capabilityTree = new CapabilityTree();
  private _observability: ObservabilityConnector | null = null;
  private _initialized = false;

  // -- Lifecycle -----------------------------------------------------------

  /**
   * Initialize the mesh from a MeshConfig.
   *
   * Sets up providers, pools, the capability tree, the router, and
   * the observability connector. Must be called before getRouter() or route().
   *
   * @param config - Fully resolved MeshConfig object.
   */
  initialize(config: MeshConfig): void {
    this._config = config;

    // Resolve observability connector from config (if not pre-set)
    if (!this._observability) {
      this._resolveObservability();
    }

    this._setupProviders();
    this._setupPools();
    this._router = new Router(
      this._pools,
      this._capabilityTree,
      this._providers,
      this._eventEmitter,
      this._observability
    );
    this._initialized = true;
    this._trace(
      Severity.INFO,
      "mesh",
      `Initialized: ${Object.keys(this._providers).length} provider(s), ` +
        `${Object.keys(this._pools).length} pool(s)`
    );
  }

  /**
   * Return the underlying Router instance.
   *
   * @returns The Router that handles request routing.
   * @throws Error if initialize() has not been called.
   */
  getRouter(): Router {
    if (!this._initialized) {
      throw new Error(
        "ModelMesh not initialized. Call initialize() first."
      );
    }
    return this._router!;
  }

  /**
   * Return an OpenAI SDK-compatible MeshClient backed by this mesh.
   *
   * @returns A MeshClient ready for use.
   * @throws Error if initialize() has not been called.
   */
  getClient(): MeshClient {
    this._checkInitialized();
    // Lazy import to avoid circular dependency at module level.
    // Uses dynamic import() for ESM compatibility; falls back to
    // require() in CommonJS environments.
    const mod = require("../client/mesh-client") as { MeshClient: new (mesh: ModelMesh) => MeshClient };
    return new mod.MeshClient(this);
  }

  /** All configured capability pools, keyed by pool ID. */
  get pools(): Record<string, CapabilityPool> {
    return { ...this._pools };
  }

  /** All registered provider connectors, keyed by connector ID. */
  get providers(): Record<string, ProviderConnector> {
    return { ...this._providers };
  }

  /**
   * Graceful shutdown.
   *
   * Marks the mesh as uninitialized. Future calls to route() or
   * getRouter() will throw.
   */
  shutdown(): void {
    this._trace(Severity.INFO, "mesh", "ModelMesh shut down");
    this._initialized = false;
    this._router = null;
  }

  // -- Routing -------------------------------------------------------------

  /**
   * Route a non-streaming request through the pipeline.
   *
   * @param request - The completion request. The `model` field is
   *     treated as a virtual model name (pool ID).
   * @returns The completion response from the selected provider.
   * @throws Error if the mesh is not initialized or no model is available.
   */
  async route(request: CompletionRequest): Promise<CompletionResponse> {
    this._checkInitialized();
    return this._router!.route(request);
  }

  /**
   * Route a streaming request through the pipeline.
   *
   * @param request - The completion request with stream=true.
   * @yields CompletionResponse chunks.
   * @throws Error if the mesh is not initialized.
   */
  async *routeStream(
    request: CompletionRequest
  ): AsyncIterableIterator<CompletionResponse> {
    this._checkInitialized();
    yield* this._router!.routeStream(request);
  }

  // -- Introspection -------------------------------------------------------

  /**
   * Return health status for all pools.
   *
   * @returns Dict mapping pool IDs to status dicts with active,
   *     standby, total, and currentModel keys.
   */
  poolStatus(): Record<
    string,
    { active: number; standby: number; total: number; currentModel: string | null }
  > {
    const result: Record<
      string,
      { active: number; standby: number; total: number; currentModel: string | null }
    > = {};
    for (const [poolId, pool] of Object.entries(this._pools)) {
      result[poolId] = pool.status();
    }
    return result;
  }

  /**
   * Return the list of active provider connector IDs.
   *
   * A provider is considered active if at least one of its models
   * is in active status across any pool.
   */
  activeProviders(): string[] {
    const activeProviderIds = new Set<string>();
    for (const pool of Object.values(this._pools)) {
      for (const model of pool.activeModels) {
        activeProviderIds.add(model.providerId);
      }
    }
    return [...activeProviderIds].sort();
  }

  /** Return all configured capability pools. */
  listPools(): CapabilityPool[] {
    return Object.values(this._pools);
  }

  /**
   * Return metadata for all models across all pools.
   *
   * @returns List of objects with id, owned_by, and object keys
   *     matching the OpenAI /v1/models shape.
   */
  listModels(): Array<{ id: string; object: string; owned_by: string }> {
    const seen = new Set<string>();
    const models: Array<{ id: string; object: string; owned_by: string }> = [];
    for (const pool of Object.values(this._pools)) {
      for (const model of pool.models) {
        if (!seen.has(model.modelId)) {
          seen.add(model.modelId);
          const vendor = model.modelId.includes(".")
            ? model.modelId.split(".")[0]
            : "unknown";
          models.push({
            id: model.modelId,
            object: "model",
            owned_by: vendor,
          });
        }
      }
    }
    return models;
  }

  /**
   * Force an immediate rotation in a pool.
   *
   * Deactivates the current model and selects the next active one.
   *
   * @param poolId - The pool to rotate.
   * @returns The model ID of the newly selected model, or null if no
   *     alternative is available.
   * @throws Error if the pool does not exist.
   */
  rotate(poolId: string): string | null {
    if (!(poolId in this._pools)) {
      throw new Error(`Pool '${poolId}' not found`);
    }
    const pool = this._pools[poolId];
    const newModel = pool.rotate();
    if (newModel) {
      this._trace(
        Severity.INFO,
        "mesh",
        `Rotated pool '${poolId}' to model '${newModel.modelId}'`,
        {
          pool_id: poolId,
          new_model_id: newModel.modelId,
        }
      );
    } else {
      this._trace(Severity.WARNING, "mesh", `No alternative model available in pool '${poolId}'`, {
        pool_id: poolId,
      });
    }
    return newModel ? newModel.modelId : null;
  }

  /** The event emitter for subscribing to routing events. */
  get eventEmitter(): EventEmitter {
    return this._eventEmitter;
  }

  /** The state manager for inspecting model state. */
  get stateManager(): StateManager {
    return this._stateManager;
  }

  /** The capability tree for inspecting the hierarchy. */
  get capabilityTree(): CapabilityTree {
    return this._capabilityTree;
  }

  /**
   * The observability connector for tracing and monitoring.
   *
   * Never returns null -- lazily creates a NullObservabilityConnector
   * if none was configured.
   */
  get observability(): ObservabilityConnector {
    if (!this._observability) {
      this._observability = new NullObservabilityConnector();
    }
    return this._observability;
  }

  /** Set the observability connector (must be set before initialize). */
  set observability(connector: ObservabilityConnector | null) {
    this._observability = connector;
  }

  private _trace(
    severity: Severity,
    component: string,
    message: string,
    metadata?: Record<string, unknown>
  ): void {
    const entry: TraceEntry = {
      severity,
      timestamp: new Date(),
      component,
      message,
      metadata: metadata ?? {},
    };
    if (this._observability) {
      this._observability.trace(entry);
    }
  }

  // -- Internal setup ------------------------------------------------------

  /**
   * Resolve observability connector from config.
   *
   * Reads config.raw["observability"]["connector"], looks it up in the
   * CONNECTOR_REGISTRY, and instantiates it. Falls back to
   * NullObservabilityConnector if not found.
   */
  private _resolveObservability(): void {
    try {
      const obsCfg = this._config?.raw?.observability as
        | Record<string, unknown>
        | undefined;
      if (obsCfg) {
        const connectorId = obsCfg.connector as string | undefined;
        if (connectorId && connectorId in CONNECTOR_REGISTRY) {
          const ConnectorClass = CONNECTOR_REGISTRY[connectorId];
          this._observability = new ConnectorClass(obsCfg.config ?? {});
          return;
        }
      }
    } catch {
      // Fall through to null connector
    }
    this._observability = new NullObservabilityConnector();
  }

  /** Raise if the mesh is not initialized. */
  private _checkInitialized(): void {
    if (!this._initialized) {
      throw new Error(
        "ModelMesh not initialized. Call initialize() first."
      );
    }
  }

  /**
   * Configure providers from the MeshConfig.
   *
   * Iterates config.raw["providers"], resolving connector IDs to provider
   * instances. Concrete connector instantiation is delegated to the CDK
   * layer; this method stores any pre-built "instance" references and
   * creates placeholder entries for connectors that will be resolved later.
   */
  private _setupProviders(): void {
    const providersCfg =
      (this._config!.raw.providers as Record<
        string,
        Record<string, unknown>
      >) ?? {};

    for (const [providerName, providerDef] of Object.entries(providersCfg)) {
      // Skip disabled providers
      if (providerDef.enabled === false) {
        continue;
      }

      // If an instance is provided directly (e.g. from QuickProvider),
      // use it as-is.
      if ("instance" in providerDef && providerDef.instance) {
        const connectorId =
          (providerDef.connector as string) ?? `${providerName}.v1`;
        this._providers[connectorId] =
          providerDef.instance as ProviderConnector;
        this._trace(
          Severity.DEBUG,
          "mesh",
          `Registered pre-built provider '${providerName}' as '${connectorId}'`,
          { provider_name: providerName, connector_id: connectorId }
        );
        continue;
      }

      // Otherwise, register a stub entry. The CDK layer will
      // provide a connector factory that maps connector IDs to
      // concrete implementations.
      const connectorId =
        (providerDef.connector as string) ?? providerName;
      const enabled = providerDef.enabled !== false;
      if (!enabled) {
        continue;
      }

      this._trace(
        Severity.DEBUG,
        "mesh",
        `Registered provider config '${providerName}' (connector: ${connectorId})`,
        { provider_name: providerName, connector_id: connectorId }
      );
    }
  }

  /**
   * Resolve capabilities for a model: config first, then provider.
   *
   * Priority:
   *   1. Config modelDef["capabilities"] (explicit override).
   *   2. Provider's per-model ModelInfo.capabilities (via listModels()).
   *   3. Provider's getCapabilities() (provider-level fallback).
   *
   * @returns List of capability tree paths.
   */
  private _resolveModelCapabilities(
    modelId: string,
    modelDef: Record<string, unknown>
  ): string[] {
    // 1. Config override
    const configCaps = modelDef.capabilities as string[] | undefined;
    if (configCaps && configCaps.length > 0) {
      return [...configCaps];
    }

    // 2. Query provider connector instance
    const providerId = (modelDef.provider as string) ?? "";
    const provider = this._providers[providerId];
    if (!provider) {
      return [];
    }

    // Try per-model capabilities from provider's model list
    try {
      const parts = modelId.split(".");
      const bareName = parts.length > 1 ? parts.slice(1).join(".") : modelId;
      for (const modelInfo of provider.listModels()) {
        if (modelInfo.id === modelId || modelInfo.id === bareName) {
          if (modelInfo.capabilities.length > 0) {
            return [...modelInfo.capabilities];
          }
        }
      }
    } catch {
      // Provider may not support listModels
    }

    // 3. Provider-level fallback
    try {
      const caps = provider.getCapabilities();
      if (caps.length > 0) {
        return [...caps];
      }
    } catch {
      // ignore
    }

    return [];
  }

  /**
   * Configure capability pools from the MeshConfig.
   *
   * Iterates config.raw["pools"], creates CapabilityPool objects,
   * and populates them with models from config.raw["models"].
   *
   * Pools support three definition modes:
   *
   * 1. Capability-based -- "capability" field matches models whose
   *    capabilities overlap with the target.
   * 2. Explicit models -- "models" list names specific model IDs to include.
   * 3. Hybrid -- both "capability" and "models" are given.
   */
  private _setupPools(): void {
    const poolsCfg =
      (this._config!.raw.pools as Record<
        string,
        Record<string, unknown>
      >) ?? {};
    const modelsCfg =
      (this._config!.raw.models as Record<
        string,
        Record<string, unknown>
      >) ?? {};

    // Resolve capabilities for every model
    const resolvedCaps: Record<string, string[]> = {};
    for (const [modelId, modelDef] of Object.entries(modelsCfg)) {
      const resolved = this._resolveModelCapabilities(modelId, modelDef);
      resolvedCaps[modelId] = resolved;
      for (const cap of resolved) {
        this._capabilityTree.register(cap);
      }
    }

    // Build pools
    for (const [poolId, poolDef] of Object.entries(poolsCfg)) {
      const pool = new CapabilityPool(poolId, poolDef, this._observability);

      const addedModelIds = new Set<string>();
      const targetCapability = poolDef.capability as string | undefined;
      const explicitModels = poolDef.models as string[] | undefined;

      // --- Capability-based matching ---
      if (targetCapability !== undefined && targetCapability !== null) {
        this._capabilityTree.register(targetCapability);
        const matchingCaps = this._capabilityTree.resolve(targetCapability);
        const poolProviders = poolDef.providers as string[] | undefined;

        for (const [modelId, modelDef] of Object.entries(modelsCfg)) {
          const modelCaps = new Set(
            resolvedCaps[modelId] ??
              (modelDef.capabilities as string[]) ??
              []
          );
          const matchingSet = new Set(matchingCaps);
          let hasOverlap = false;
          for (const cap of modelCaps) {
            if (matchingSet.has(cap)) {
              hasOverlap = true;
              break;
            }
          }
          if (!hasOverlap) {
            continue;
          }

          const providerId = (modelDef.provider as string) ?? "";
          if (poolProviders && !poolProviders.includes(providerId)) {
            continue;
          }

          const parts = modelId.split(".");
          const realModelId =
            parts.length > 1 ? parts.slice(1).join(".") : modelId;

          pool.addModel(
            createPoolModel({
              modelId,
              realModelId,
              providerId,
            })
          );
          addedModelIds.add(modelId);
        }
      }

      // --- Explicit model list ---
      if (explicitModels !== undefined && explicitModels !== null) {
        for (const modelId of explicitModels) {
          if (addedModelIds.has(modelId)) {
            continue;
          }
          const modelDef = modelsCfg[modelId] ?? {};
          const providerId = (modelDef.provider as string) ?? "";

          const parts = modelId.split(".");
          const realModelId =
            parts.length > 1 ? parts.slice(1).join(".") : modelId;

          pool.addModel(
            createPoolModel({
              modelId,
              realModelId,
              providerId,
            })
          );
          addedModelIds.add(modelId);
        }
      }

      // --- Fallback: use pool_id as capability if nothing matched ---
      if (
        targetCapability === undefined &&
        explicitModels === undefined
      ) {
        this._capabilityTree.register(poolId);
        const matchingCaps = this._capabilityTree.resolve(poolId);
        const matchingSet = new Set(matchingCaps);

        for (const [modelId, modelDef] of Object.entries(modelsCfg)) {
          const modelCaps = new Set(
            resolvedCaps[modelId] ??
              (modelDef.capabilities as string[]) ??
              []
          );
          let hasOverlap = false;
          for (const cap of modelCaps) {
            if (matchingSet.has(cap)) {
              hasOverlap = true;
              break;
            }
          }
          if (!hasOverlap) {
            continue;
          }

          const providerId = (modelDef.provider as string) ?? "";
          const parts = modelId.split(".");
          const realModelId =
            parts.length > 1 ? parts.slice(1).join(".") : modelId;

          pool.addModel(
            createPoolModel({
              modelId,
              realModelId,
              providerId,
            })
          );
        }
      }

      this._pools[poolId] = pool;
      this._trace(Severity.DEBUG, "mesh", `Pool '${poolId}' configured with ${pool.models.length} model(s)`, {
        pool_id: poolId,
        model_count: pool.models.length,
      });
    }
  }
}
