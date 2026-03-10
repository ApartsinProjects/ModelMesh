/**
 * Request router -- resolves capabilities to pools and executes requests.
 *
 * The router implements the full request pipeline: capability resolution,
 * pool selection, model selection, provider execution, and retry/rotation
 * on failure. It is the central orchestration component of ModelMesh Lite.
 */

import { CapabilityTree } from "./capability-tree";
import { EventEmitter, EventType } from "./event-emitter";
import { CapabilityPool } from "./pool";
import type { PoolModel } from "./pool";
import type {
  CompletionRequest,
  CompletionResponse,
  ProviderConnector,
} from "../interfaces/provider";
import type { ObservabilityConnector } from "../interfaces/observability";
import { Severity } from "../interfaces/observability";
import type { TraceEntry } from "../interfaces/observability";

/** Raised when no active model is available in a pool. */
export class NoActiveModelError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NoActiveModelError";
  }
}

/**
 * Routes requests through the capability resolution / model selection pipeline.
 *
 * The routing pipeline:
 *
 * 1. Resolve the virtual model name to a capability pool.
 * 2. Select the best active model from the pool using the pool's strategy.
 * 3. Build a provider-specific request with the real model name.
 * 4. Execute through the provider connector.
 * 5. On success, record the result and return.
 * 6. On failure, record the failure, attempt rotation, and retry.
 *
 * @param pools - Mapping of pool IDs to CapabilityPool instances.
 * @param capabilityTree - The capability hierarchy for path-based resolution.
 * @param providers - Mapping of connector IDs to ProviderConnector instances.
 * @param eventEmitter - Optional event emitter for observability.
 * @param maxRetries - Maximum retry attempts across rotation (default: 3).
 */
export class Router {
  private readonly _pools: Record<string, CapabilityPool>;
  private readonly _capabilityTree: CapabilityTree;
  private readonly _providers: Record<string, ProviderConnector>;
  private readonly _emitter: EventEmitter;
  private readonly _observability: ObservabilityConnector | null;
  private readonly _maxRetries: number;

  constructor(
    pools: Record<string, CapabilityPool>,
    capabilityTree: CapabilityTree,
    providers: Record<string, ProviderConnector>,
    eventEmitter?: EventEmitter,
    observability?: ObservabilityConnector | null,
    maxRetries: number = 3
  ) {
    this._pools = pools;
    this._capabilityTree = capabilityTree;
    this._providers = providers;
    this._emitter = eventEmitter ?? new EventEmitter();
    this._observability = observability ?? null;
    this._maxRetries = maxRetries;
  }

  private _trace(
    severity: Severity | string,
    component: string,
    message: string,
    error?: string | null,
    metadata?: Record<string, unknown>
  ): void {
    const sev =
      typeof severity === "string"
        ? (severity.toLowerCase() as Severity)
        : severity;
    const entry: TraceEntry = {
      severity: sev,
      timestamp: new Date(),
      component,
      message,
      metadata: metadata ?? {},
      error: error ?? undefined,
    };
    if (this._observability) {
      this._observability.trace(entry);
    }
  }

  /** Mapping of pool IDs to CapabilityPool instances. */
  get pools(): Record<string, CapabilityPool> {
    return this._pools;
  }

  /** Mapping of connector IDs to ProviderConnector instances. */
  get providers(): Record<string, ProviderConnector> {
    return this._providers;
  }

  /**
   * Route a non-streaming request through the full pipeline.
   *
   * @param request - The incoming completion request. The `model` field
   *     is treated as a virtual model name (pool ID).
   * @returns The completion response from the selected provider.
   * @throws NoActiveModelError if no active model is available.
   * @throws Error if no pool matches the virtual model name.
   */
  async route(request: CompletionRequest): Promise<CompletionResponse> {
    this._trace(Severity.DEBUG, "router", `Routing request for model '${request.model}'`, null, {
      model: request.model,
    });
    const pool = this.resolvePool(request.model);
    const model = pool.select(request);

    if (model === null) {
      this._emitter.emit(EventType.POOL_EXHAUSTED, {
        pool_id: pool.poolId,
      });
      this._trace(
        Severity.ERROR,
        "router",
        `No active model available in pool '${request.model}'`,
        `NoActiveModelError: pool '${request.model}'`,
        { pool_id: pool.poolId }
      );
      throw new NoActiveModelError(
        `No active model available in pool '${request.model}'`
      );
    }

    return this._executeWithRotation(request, pool, model);
  }

  /**
   * Route a streaming request through the full pipeline.
   *
   * Yields completion response chunks from the selected provider.
   * On failure during streaming, rotation is attempted and the
   * stream restarts with the next model.
   *
   * @param request - The incoming completion request with `stream=true`.
   * @yields CompletionResponse chunks.
   * @throws NoActiveModelError if no active model is available.
   * @throws Error if no pool matches the virtual model name.
   */
  async *routeStream(
    request: CompletionRequest
  ): AsyncIterableIterator<CompletionResponse> {
    this._trace(Severity.DEBUG, "router", `Streaming request for model '${request.model}'`, null, {
      model: request.model,
    });
    const pool = this.resolvePool(request.model);
    let currentModel = pool.select(request);

    if (currentModel === null) {
      this._emitter.emit(EventType.POOL_EXHAUSTED, {
        pool_id: pool.poolId,
      });
      this._trace(
        Severity.ERROR,
        "router",
        `No active model available in pool '${request.model}'`,
        `NoActiveModelError: pool '${request.model}'`,
        { pool_id: pool.poolId }
      );
      throw new NoActiveModelError(
        `No active model available in pool '${request.model}'`
      );
    }

    let attempts = 0;

    while (currentModel !== null && attempts < this._maxRetries) {
      const provider = this._providers[currentModel.providerId];
      if (!provider) {
        pool.recordFailure(
          currentModel.modelId,
          new Error("Provider not found")
        );
        currentModel = pool.select(request);
        attempts += 1;
        continue;
      }

      const providerRequest = Router._buildProviderRequest(
        request,
        currentModel
      );

      try {
        for await (const chunk of provider.stream(providerRequest)) {
          yield chunk;
        }
        pool.recordSuccess(currentModel.modelId);
        this._emitter.emit(EventType.REQUEST_SUCCESS, {
          pool_id: pool.poolId,
          model_id: currentModel.modelId,
          provider_id: currentModel.providerId,
        });
        return;
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e));
        this._trace(
          Severity.WARNING,
          "router",
          `Stream failure on '${currentModel.modelId}': ${err.message}`,
          err.message,
          {
            model_id: currentModel.modelId,
            provider_id: currentModel.providerId,
            attempt: attempts + 1,
          }
        );
        pool.recordFailure(currentModel.modelId, err);
        this._emitter.emit(EventType.REQUEST_FAILURE, {
          pool_id: pool.poolId,
          model_id: currentModel.modelId,
          error: err.message,
        });
        currentModel = pool.select(request);
        attempts += 1;
      }
    }

    this._trace(
      Severity.ERROR,
      "router",
      `All models exhausted in pool '${request.model}' after ${attempts} attempts`,
      "All models exhausted",
      { pool_id: pool.poolId, attempts }
    );
    throw new Error(
      `All models exhausted in pool '${request.model}' after ${attempts} attempts`
    );
  }

  /**
   * Resolve a virtual model name to a capability pool.
   *
   * Looks up by direct pool ID first, then falls back to resolving
   * the name through the capability tree (matching against pool
   * capability paths).
   *
   * @param modelName - The pool ID, capability path, or virtual model
   *     name from the request's `model` field.
   * @returns The matching CapabilityPool.
   * @throws Error if no pool matches.
   */
  resolvePool(modelName: string): CapabilityPool {
    // Direct pool ID lookup
    if (modelName in this._pools) {
      this._trace(Severity.DEBUG, "router", `Resolved pool '${modelName}' by direct ID`, null, {
        model_name: modelName,
      });
      return this._pools[modelName];
    }

    // Capability tree resolution: find leaf capabilities that match
    // and then locate a pool whose capability covers that path.
    const resolvedCaps = this._capabilityTree.resolve(modelName);
    if (resolvedCaps.length > 0) {
      const resolvedSet = new Set(resolvedCaps);
      for (const [poolId, pool] of Object.entries(this._pools)) {
        const poolCap =
          typeof pool.config.capability === "string"
            ? pool.config.capability
            : poolId;
        const poolLeaves = this._capabilityTree.resolve(poolCap);
        const hasOverlap = poolLeaves.some((leaf) => resolvedSet.has(leaf));
        if (hasOverlap) {
          this._trace(
            Severity.DEBUG,
            "router",
            `Resolved pool '${poolId}' for model '${modelName}' via capability tree`,
            null,
            { model_name: modelName, pool_id: poolId }
          );
          return pool;
        }
      }
    }

    this._trace(
      Severity.ERROR,
      "router",
      `No pool found for virtual model: ${modelName}`,
      `KeyError: ${modelName}`,
      { model_name: modelName }
    );
    throw new Error(`No pool found for virtual model: ${modelName}`);
  }

  /**
   * Execute a request with retry and rotation on failure.
   *
   * Tries the selected model first, then rotates through remaining
   * active models in the pool up to `maxRetries` attempts.
   *
   * @param request - The original completion request.
   * @param pool - The resolved capability pool.
   * @param model - The initially selected model.
   * @returns The completion response.
   * @throws Error if all retry attempts fail.
   */
  private async _executeWithRotation(
    request: CompletionRequest,
    pool: CapabilityPool,
    model: PoolModel
  ): Promise<CompletionResponse> {
    let attempts = 0;
    let currentModel: PoolModel | null = model;
    let lastError: Error | null = null;

    while (currentModel !== null && attempts < this._maxRetries) {
      const provider = this._providers[currentModel.providerId];
      if (!provider) {
        pool.recordFailure(
          currentModel.modelId,
          new Error("Provider not found")
        );
        currentModel = pool.select(request);
        attempts += 1;
        continue;
      }

      const providerRequest = Router._buildProviderRequest(
        request,
        currentModel
      );

      this._trace(
        Severity.DEBUG,
        "router",
        `Request routed to model '${currentModel.modelId}' via provider '${currentModel.providerId}'`,
        null,
        {
          model_id: currentModel.modelId,
          provider_id: currentModel.providerId,
          pool_id: pool.poolId,
          attempt: attempts + 1,
        }
      );

      this._emitter.emit(EventType.REQUEST_ROUTED, {
        pool_id: pool.poolId,
        model_id: currentModel.modelId,
        provider_id: currentModel.providerId,
        attempt: attempts + 1,
      });

      try {
        const response = await provider.complete(providerRequest);
        pool.recordSuccess(currentModel.modelId);
        this._emitter.emit(EventType.REQUEST_SUCCESS, {
          pool_id: pool.poolId,
          model_id: currentModel.modelId,
          provider_id: currentModel.providerId,
        });
        this._trace(
          Severity.INFO,
          "router",
          `Request succeeded on '${currentModel.modelId}'`,
          null,
          {
            model_id: currentModel.modelId,
            provider_id: currentModel.providerId,
            pool_id: pool.poolId,
          }
        );
        return response;
      } catch (e) {
        lastError = e instanceof Error ? e : new Error(String(e));
        this._trace(
          Severity.WARNING,
          "router",
          `Request failure on '${currentModel.modelId}' (attempt ${attempts + 1}): ${lastError.message}`,
          lastError.message,
          {
            model_id: currentModel.modelId,
            provider_id: currentModel.providerId,
            pool_id: pool.poolId,
            attempt: attempts + 1,
          }
        );
        pool.recordFailure(currentModel.modelId, lastError);
        this._emitter.emit(EventType.REQUEST_FAILURE, {
          pool_id: pool.poolId,
          model_id: currentModel.modelId,
          error: lastError.message,
        });

        // Attempt rotation
        currentModel = pool.select(request);
        if (currentModel !== null) {
          this._emitter.emit(EventType.MODEL_ROTATED, {
            pool_id: pool.poolId,
            new_model_id: currentModel.modelId,
            reason: lastError.message,
          });
        }
        attempts += 1;
      }
    }

    let errorMsg = `All models exhausted in pool '${request.model}' after ${attempts} attempts`;
    if (lastError) {
      errorMsg += `. Last error: ${lastError.message}`;
    }
    this._trace(Severity.ERROR, "router", errorMsg, lastError ? lastError.message : "All models exhausted", {
      pool_id: pool.poolId,
      attempts,
    });
    throw new Error(errorMsg);
  }

  /**
   * Build a provider-specific request with the real model name.
   *
   * Copies the original request but replaces the virtual model name
   * with the provider's actual model identifier.
   *
   * @param request - The original request with virtual model name.
   * @param model - The selected PoolModel with real model details.
   * @returns A new CompletionRequest with the real model name.
   */
  static _buildProviderRequest(
    request: CompletionRequest,
    model: PoolModel
  ): CompletionRequest {
    return {
      model: model.realModelId,
      messages: request.messages,
      temperature: request.temperature,
      maxTokens: request.maxTokens,
      stream: request.stream,
      tools: request.tools,
      topP: request.topP,
      stop: request.stop,
    };
  }
}
