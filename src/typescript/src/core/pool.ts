/**
 * Capability pool -- groups models that fulfill a capability.
 *
 * A CapabilityPool collects models registered at a capability node (or its
 * descendants), manages their lifecycle state, and delegates model selection
 * to a pluggable SelectionStrategy.
 */

import { ModelStatus } from "../interfaces/rotation";
import type { ModelState, SelectionStrategy } from "../interfaces/rotation";
import type { CompletionRequest } from "../interfaces/provider";
import type { ObservabilityConnector } from "../interfaces/observability";
import { Severity } from "../interfaces/observability";
import type { TraceEntry } from "../interfaces/observability";

/**
 * A model entry within a capability pool.
 *
 * @property modelId - Dot-notated model identifier (e.g. "openai.gpt-4o").
 * @property realModelId - Vendor-specific model name (e.g. "gpt-4o").
 * @property providerId - Connector ID for the provider (e.g. "openai.llm.v1").
 * @property status - Current lifecycle status (ACTIVE or STANDBY).
 * @property failureCount - Consecutive failures since last success.
 * @property totalRequests - Lifetime request count.
 * @property totalTokens - Lifetime token consumption.
 * @property lastFailureAt - Timestamp of last failure, or undefined.
 * @property lastSuccessAt - Timestamp of last success, or undefined.
 */
export interface PoolModel {
  modelId: string;
  realModelId: string;
  providerId: string;
  status: ModelStatus;
  failureCount: number;
  totalRequests: number;
  totalTokens: number;
  lastFailureAt?: number;
  lastSuccessAt?: number;
}

/** Creates a PoolModel with default values. */
export function createPoolModel(
  overrides: Partial<PoolModel> &
    Pick<PoolModel, "modelId" | "realModelId" | "providerId">
): PoolModel {
  return {
    status: ModelStatus.ACTIVE,
    failureCount: 0,
    totalRequests: 0,
    totalTokens: 0,
    ...overrides,
  };
}

/** Convert a PoolModel to a ModelState for use with rotation policies. */
export function poolModelToModelState(model: PoolModel): ModelState {
  return {
    modelId: model.modelId,
    status: model.status,
    failureCount: model.failureCount,
    errorRate: 0,
    totalRequests: model.totalRequests,
    totalTokens: model.totalTokens,
    totalCost: 0,
    lastFailureAt: model.lastFailureAt,
    lastSuccessAt: model.lastSuccessAt,
    providerId: model.providerId,
  };
}

/**
 * Default selection strategy: stick with the first active model.
 *
 * Returns the first active candidate in insertion order. This is the
 * built-in fallback when no explicit strategy is configured.
 */
class StickUntilFailureStrategy implements SelectionStrategy {
  select(
    candidates: ModelState[],
    _request: CompletionRequest
  ): ModelState | null {
    const active = candidates.filter(
      (c) => c.status === ModelStatus.ACTIVE
    );
    return active.length > 0 ? active[0] : null;
  }

  score(state: ModelState, _request: CompletionRequest): number {
    return state.status === ModelStatus.ACTIVE ? 1.0 : 0.0;
  }
}

/**
 * Groups models that fulfill a capability.
 *
 * Manages model lifecycle (active/standby), delegates selection to a
 * pluggable strategy, and records success/failure events for rotation
 * decisions.
 *
 * @param poolId - Dot-notated pool identifier
 *                 (e.g. "generation.text-generation").
 * @param config - Pool configuration dict from MeshConfig.
 */
export class CapabilityPool {
  private readonly _id: string;
  private readonly _config: Record<string, unknown>;
  private readonly _models: PoolModel[] = [];
  private readonly _modelsById: Map<string, PoolModel> = new Map();
  private _strategy: SelectionStrategy = new StickUntilFailureStrategy();
  private readonly _failureThreshold: number;
  private readonly _observability: ObservabilityConnector | null;

  constructor(
    poolId: string,
    config: Record<string, unknown>,
    observability: ObservabilityConnector | null = null
  ) {
    this._id = poolId;
    this._config = config;
    this._failureThreshold =
      typeof config.failure_threshold === "number"
        ? config.failure_threshold
        : 3;
    this._observability = observability;
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

  /** The pool's dot-notated identifier. */
  get poolId(): string {
    return this._id;
  }

  /** The pool's configuration dict. */
  get config(): Record<string, unknown> {
    return this._config;
  }

  /** All models in this pool (both active and standby). */
  get models(): PoolModel[] {
    return [...this._models];
  }

  /** Only the active models in this pool. */
  get activeModels(): PoolModel[] {
    return this._models.filter((m) => m.status === ModelStatus.ACTIVE);
  }

  /** Only the standby models in this pool. */
  get standbyModels(): PoolModel[] {
    return this._models.filter((m) => m.status === ModelStatus.STANDBY);
  }

  /**
   * Replace the selection strategy for this pool.
   *
   * @param strategy - A SelectionStrategy implementation.
   */
  setStrategy(strategy: SelectionStrategy): void {
    this._strategy = strategy;
  }

  /**
   * Add a model to the pool.
   *
   * @param model - The PoolModel to add.
   * @throws Error if a model with the same ID already exists.
   */
  addModel(model: PoolModel): void {
    if (this._modelsById.has(model.modelId)) {
      throw new Error(
        `Model '${model.modelId}' already exists in pool '${this._id}'`
      );
    }
    this._models.push(model);
    this._modelsById.set(model.modelId, model);
    this._trace(
      Severity.DEBUG,
      `pool.${this._id}`,
      `Model '${model.modelId}' added to pool`,
      null,
      { model_id: model.modelId, provider_id: model.providerId }
    );
  }

  /**
   * Remove a model from the pool by ID.
   *
   * @param modelId - Dot-notated model identifier.
   * @throws Error if the model is not in this pool.
   */
  removeModel(modelId: string): void {
    if (!this._modelsById.has(modelId)) {
      throw new Error(
        `Model '${modelId}' not found in pool '${this._id}'`
      );
    }
    const model = this._modelsById.get(modelId)!;
    this._modelsById.delete(modelId);
    const idx = this._models.indexOf(model);
    if (idx !== -1) {
      this._models.splice(idx, 1);
    }
  }

  /**
   * Select the best active model for a request.
   *
   * Delegates to the configured selection strategy. Returns null if
   * no active model is available.
   *
   * @param request - The incoming completion request.
   * @returns The selected PoolModel, or null.
   */
  select(request: CompletionRequest): PoolModel | null {
    const candidates = this._models.map(poolModelToModelState);
    const selected = this._strategy.select(candidates, request);
    if (selected === null) {
      return null;
    }
    return this._modelsById.get(selected.modelId) ?? null;
  }

  /**
   * Record a successful request for a model.
   *
   * Resets the consecutive failure count and updates counters.
   *
   * @param modelId - Dot-notated model identifier.
   */
  recordSuccess(modelId: string): void {
    const model = this._modelsById.get(modelId);
    if (!model) {
      return;
    }
    model.failureCount = 0;
    model.totalRequests += 1;
    model.lastSuccessAt = Date.now() / 1000;
    this._trace(
      Severity.DEBUG,
      `pool.${this._id}`,
      `Request succeeded for model '${modelId}'`,
      null,
      { model_id: modelId, total_requests: model.totalRequests }
    );
  }

  /**
   * Record a failed request for a model.
   *
   * Increments the failure count and may deactivate the model if the
   * failure threshold is reached.
   *
   * @param modelId - Dot-notated model identifier.
   * @param error - The exception that caused the failure.
   */
  recordFailure(modelId: string, error: Error): void {
    const model = this._modelsById.get(modelId);
    if (!model) {
      return;
    }
    model.failureCount += 1;
    model.totalRequests += 1;
    model.lastFailureAt = Date.now() / 1000;

    this._trace(
      Severity.WARNING,
      `pool.${this._id}`,
      `Failure recorded for model '${modelId}' ` +
        `(count: ${model.failureCount}/${this._failureThreshold})`,
      String(error),
      {
        model_id: modelId,
        failure_count: model.failureCount,
        threshold: this._failureThreshold,
      }
    );

    if (model.failureCount >= this._failureThreshold) {
      model.status = ModelStatus.STANDBY;
      this._trace(
        Severity.ERROR,
        `pool.${this._id}`,
        `Model '${modelId}' deactivated after ` +
          `${model.failureCount} consecutive failures`,
        String(error),
        { model_id: modelId, failure_count: model.failureCount }
      );
    }
  }

  /**
   * Force rotation: deactivate the current model and return the next.
   *
   * Moves the first active model to standby and returns the next
   * active model (if any).
   *
   * @returns The next active PoolModel, or null if no alternative exists.
   */
  rotate(): PoolModel | null {
    const active = this.activeModels;
    const oldModelId = active.length > 0 ? active[0].modelId : null;
    if (active.length > 0) {
      active[0].status = ModelStatus.STANDBY;
    }
    const remaining = this.activeModels;
    const newModel = remaining.length > 0 ? remaining[0] : null;
    this._trace(
      Severity.INFO,
      `pool.${this._id}`,
      `Manual rotation: '${oldModelId}' -> ` +
        `'${newModel ? newModel.modelId : null}'`,
      null,
      {
        old_model_id: oldModelId,
        new_model_id: newModel ? newModel.modelId : null,
      }
    );
    return newModel;
  }

  /**
   * Manually reactivate a standby model.
   *
   * @param modelId - Dot-notated model identifier.
   * @throws Error if the model is not in this pool.
   */
  reactivate(modelId: string): void {
    const model = this._modelsById.get(modelId);
    if (!model) {
      throw new Error(
        `Model '${modelId}' not found in pool '${this._id}'`
      );
    }
    model.status = ModelStatus.ACTIVE;
    model.failureCount = 0;
    this._trace(
      Severity.INFO,
      `pool.${this._id}`,
      `Model '${modelId}' reactivated`,
      null,
      { model_id: modelId }
    );
  }

  /**
   * Return a summary of pool health.
   *
   * @returns Object with active, standby, total, and currentModel keys.
   */
  status(): {
    active: number;
    standby: number;
    total: number;
    currentModel: string | null;
  } {
    const active = this.activeModels;
    return {
      active: active.length,
      standby: this.standbyModels.length,
      total: this._models.length,
      currentModel: active.length > 0 ? active[0].modelId : null,
    };
  }
}
