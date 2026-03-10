/**
 * State manager for model health, usage counters, and lifecycle metadata.
 *
 * Tracks per-model state that drives rotation, recovery, and observability.
 * State can be persisted through storage connectors using configurable sync
 * policies.
 */

import { ModelStatus } from "../interfaces/rotation";
import type { ModelState } from "../interfaces/rotation";
import type { StorageConnector } from "../interfaces/storage";

/**
 * Centralized state tracker for model health and usage.
 *
 * Maintains an in-memory dictionary of ModelState objects keyed by
 * model ID. Optionally syncs to a StorageConnector using a
 * configurable sync policy.
 *
 * @param syncPolicy - Persistence mode. One of "in-memory" (default),
 *     "sync-on-boundary" (load at startup, save at shutdown),
 *     "periodic", or "immediate".
 * @param storage - Storage connector for persistence. Required for all
 *     policies except "in-memory".
 */
export class StateManager {
  private _states: Map<string, ModelState> = new Map();
  private _syncPolicy: string;
  private _storage: StorageConnector | null;
  private _dirty = false;

  constructor(
    syncPolicy: string = "in-memory",
    storage: StorageConnector | null = null
  ) {
    this._syncPolicy = syncPolicy;
    this._storage = storage;
  }

  /**
   * Retrieve the state for a model, or null if not tracked.
   *
   * @param modelId - Dot-notated model identifier.
   */
  get(modelId: string): ModelState | null {
    return this._states.get(modelId) ?? null;
  }

  /**
   * Retrieve or initialize state for a model.
   *
   * If the model has not been tracked yet, creates a new
   * ModelState with default values.
   *
   * @param modelId - Dot-notated model identifier.
   */
  getOrCreate(modelId: string): ModelState {
    if (!this._states.has(modelId)) {
      this._states.set(modelId, {
        modelId,
        status: ModelStatus.ACTIVE,
        failureCount: 0,
        errorRate: 0,
        totalRequests: 0,
        totalTokens: 0,
        totalCost: 0,
      });
    }
    return this._states.get(modelId)!;
  }

  /**
   * Record a successful request.
   *
   * Resets failure count, updates counters, and marks the model as
   * recently successful.
   *
   * @param modelId - Dot-notated model identifier.
   * @param tokens - Total tokens consumed in the request.
   */
  recordSuccess(modelId: string, tokens: number = 0): void {
    const state = this.getOrCreate(modelId);
    state.failureCount = 0;
    state.errorRate = 0;
    state.totalRequests += 1;
    state.totalTokens += tokens;
    state.lastSuccessAt = Date.now() / 1000;
    this._dirty = true;
  }

  /**
   * Record a failed request.
   *
   * Increments failure count and updates error rate.
   *
   * @param modelId - Dot-notated model identifier.
   */
  recordFailure(modelId: string): void {
    const state = this.getOrCreate(modelId);
    state.failureCount += 1;
    state.totalRequests += 1;
    state.lastFailureAt = Date.now() / 1000;
    if (state.totalRequests > 0) {
      state.errorRate = state.failureCount / state.totalRequests;
    }
    this._dirty = true;
  }

  /**
   * Move a model to standby status.
   *
   * @param modelId - Dot-notated model identifier.
   */
  deactivate(modelId: string): void {
    const state = this.getOrCreate(modelId);
    state.status = ModelStatus.STANDBY;
    this._dirty = true;
  }

  /**
   * Move a model to active status and reset failure counters.
   *
   * @param modelId - Dot-notated model identifier.
   */
  activate(modelId: string): void {
    const state = this.getOrCreate(modelId);
    state.status = ModelStatus.ACTIVE;
    state.failureCount = 0;
    state.errorRate = 0;
    this._dirty = true;
  }

  /** Return a copy of all tracked model states. */
  allStates(): Record<string, ModelState> {
    const result: Record<string, ModelState> = {};
    for (const [key, value] of this._states) {
      result[key] = value;
    }
    return result;
  }

  /** Return IDs of all models currently in active status. */
  activeModels(): string[] {
    const result: string[] = [];
    for (const [modelId, state] of this._states) {
      if (state.status === ModelStatus.ACTIVE) {
        result.push(modelId);
      }
    }
    return result;
  }

  /** Return IDs of all models currently in standby status. */
  standbyModels(): string[] {
    const result: string[] = [];
    for (const [modelId, state] of this._states) {
      if (state.status === ModelStatus.STANDBY) {
        result.push(modelId);
      }
    }
    return result;
  }

  /**
   * Reset all state for a model to defaults.
   *
   * @param modelId - Dot-notated model identifier.
   */
  reset(modelId: string): void {
    this._states.set(modelId, {
      modelId,
      status: ModelStatus.ACTIVE,
      failureCount: 0,
      errorRate: 0,
      totalRequests: 0,
      totalTokens: 0,
      totalCost: 0,
    });
    this._dirty = true;
  }

  /** Remove all tracked state. */
  clear(): void {
    this._states.clear();
    this._dirty = true;
  }

  /** True if state has changed since last sync. */
  get isDirty(): boolean {
    return this._dirty;
  }

  /** Mark the state as synchronized (no pending changes). */
  markClean(): void {
    this._dirty = false;
  }
}
