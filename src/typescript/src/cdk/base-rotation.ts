/**
 * Base rotation policy implementation.
 *
 * Implements the three rotation policy sub-interfaces --
 * DeactivationPolicy, RecoveryPolicy, and SelectionStrategy -- with
 * threshold-based defaults: deactivate on consecutive failure count or
 * error rate, recover after a cooldown period, and select by lowest
 * error rate.
 */

import { CompletionRequest } from '../interfaces/provider';
import { RuntimeEnvironment } from '../interfaces/runtime';
import {
  DeactivationPolicy,
  DeactivationReason,
  ModelState,
  ModelStatus,
  RecoveryPolicy,
  SelectionStrategy,
} from '../interfaces/rotation';

export interface BaseRotationConfig {
  failureThreshold?: number;
  cooldownSeconds?: number;
  errorRateThreshold?: number;
  requestLimit?: number | null;
  tokenLimit?: number | null;
  budgetLimit?: number | null;
  modelPriority?: string[];
  providerPriority?: string[];
}

type ResolvedRotationConfig = {
  failureThreshold: number;
  cooldownSeconds: number;
  errorRateThreshold: number;
  requestLimit: number | null;
  tokenLimit: number | null;
  budgetLimit: number | null;
  modelPriority: string[];
  providerPriority: string[];
};

function resolveConfig(config?: BaseRotationConfig): ResolvedRotationConfig {
  return {
    failureThreshold: config?.failureThreshold ?? 3,
    cooldownSeconds: config?.cooldownSeconds ?? 60.0,
    errorRateThreshold: config?.errorRateThreshold ?? 0.5,
    requestLimit: config?.requestLimit ?? null,
    tokenLimit: config?.tokenLimit ?? null,
    budgetLimit: config?.budgetLimit ?? null,
    modelPriority: config?.modelPriority ?? [],
    providerPriority: config?.providerPriority ?? [],
  };
}

// -- Deactivation -----------------------------------------------------------

export class BaseDeactivationPolicy implements DeactivationPolicy {
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  protected readonly _config: ResolvedRotationConfig;

  constructor(config?: BaseRotationConfig) {
    this._config = resolveConfig(config);
  }

  shouldDeactivate(state: ModelState): boolean {
    return this.getReason(state) !== null;
  }

  getReason(state: ModelState): DeactivationReason | null {
    if (state.failureCount >= this._config.failureThreshold) {
      return DeactivationReason.ERROR_THRESHOLD;
    }

    if (state.errorRate >= this._config.errorRateThreshold) {
      return DeactivationReason.ERROR_THRESHOLD;
    }

    if (
      this._config.requestLimit !== null &&
      state.totalRequests >= this._config.requestLimit
    ) {
      return DeactivationReason.REQUEST_LIMIT;
    }

    if (
      this._config.tokenLimit !== null &&
      state.totalTokens >= this._config.tokenLimit
    ) {
      return DeactivationReason.TOKEN_LIMIT;
    }

    if (
      this._config.budgetLimit !== null &&
      state.totalCost >= this._config.budgetLimit
    ) {
      return DeactivationReason.BUDGET_EXCEEDED;
    }

    return null;
  }
}

// -- Recovery ---------------------------------------------------------------

export class BaseRecoveryPolicy implements RecoveryPolicy {
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  protected readonly _config: ResolvedRotationConfig;

  constructor(config?: BaseRotationConfig) {
    this._config = resolveConfig(config);
  }

  shouldRecover(state: ModelState): boolean {
    if (state.cooldownUntil == null) return true;
    return Date.now() >= state.cooldownUntil;
  }

  getRecoverySchedule(state: ModelState): number | null {
    if (state.status !== ModelStatus.STANDBY) return null;
    return Date.now() + this._config.cooldownSeconds * 1000;
  }
}

// -- Selection --------------------------------------------------------------

export class BaseSelectionStrategy implements SelectionStrategy {
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  protected readonly _config: ResolvedRotationConfig;

  constructor(config?: BaseRotationConfig) {
    this._config = resolveConfig(config);
  }

  select(candidates: ModelState[], request: CompletionRequest): ModelState | null {
    if (!candidates.length) return null;

    let best = candidates[0];
    let bestScore = this.score(best, request);

    for (let i = 1; i < candidates.length; i++) {
      const s = this.score(candidates[i], request);
      if (s > bestScore) {
        best = candidates[i];
        bestScore = s;
      }
    }

    return best;
  }

  score(state: ModelState, _request: CompletionRequest): number {
    if (this._config.modelPriority.includes(state.modelId)) {
      const idx = this._config.modelPriority.indexOf(state.modelId);
      return 1000.0 + (this._config.modelPriority.length - idx);
    }

    const providerId = state.providerId;
    if (providerId && this._config.providerPriority.includes(providerId)) {
      const idx = this._config.providerPriority.indexOf(providerId);
      return 500.0 + (this._config.providerPriority.length - idx);
    }

    return 1.0 - state.errorRate;
  }
}

// -- Combined Policy --------------------------------------------------------

export class BaseRotationPolicy
  implements DeactivationPolicy, RecoveryPolicy, SelectionStrategy
{
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  protected readonly _config: ResolvedRotationConfig;

  constructor(config?: BaseRotationConfig) {
    this._config = resolveConfig(config);
  }

  shouldDeactivate(state: ModelState): boolean {
    return this.getReason(state) !== null;
  }

  getReason(state: ModelState): DeactivationReason | null {
    if (state.failureCount >= this._config.failureThreshold) {
      return DeactivationReason.ERROR_THRESHOLD;
    }
    if (state.errorRate >= this._config.errorRateThreshold) {
      return DeactivationReason.ERROR_THRESHOLD;
    }
    if (
      this._config.requestLimit !== null &&
      state.totalRequests >= this._config.requestLimit
    ) {
      return DeactivationReason.REQUEST_LIMIT;
    }
    if (
      this._config.tokenLimit !== null &&
      state.totalTokens >= this._config.tokenLimit
    ) {
      return DeactivationReason.TOKEN_LIMIT;
    }
    if (
      this._config.budgetLimit !== null &&
      state.totalCost >= this._config.budgetLimit
    ) {
      return DeactivationReason.BUDGET_EXCEEDED;
    }
    return null;
  }

  shouldRecover(state: ModelState): boolean {
    if (state.cooldownUntil == null) return true;
    return Date.now() >= state.cooldownUntil;
  }

  getRecoverySchedule(state: ModelState): number | null {
    if (state.status !== ModelStatus.STANDBY) return null;
    return Date.now() + this._config.cooldownSeconds * 1000;
  }

  select(candidates: ModelState[], request: CompletionRequest): ModelState | null {
    if (!candidates.length) return null;
    let best = candidates[0];
    let bestScore = this.score(best, request);
    for (let i = 1; i < candidates.length; i++) {
      const s = this.score(candidates[i], request);
      if (s > bestScore) {
        best = candidates[i];
        bestScore = s;
      }
    }
    return best;
  }

  score(state: ModelState, _request: CompletionRequest): number {
    if (this._config.modelPriority.includes(state.modelId)) {
      const idx = this._config.modelPriority.indexOf(state.modelId);
      return 1000.0 + (this._config.modelPriority.length - idx);
    }
    const providerId = state.providerId;
    if (providerId && this._config.providerPriority.includes(providerId)) {
      const idx = this._config.providerPriority.indexOf(providerId);
      return 500.0 + (this._config.providerPriority.length - idx);
    }
    return 1.0 - state.errorRate;
  }
}
