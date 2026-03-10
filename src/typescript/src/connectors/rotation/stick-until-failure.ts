/**
 * Stick-until-failure rotation policy connector.
 *
 * Bundles deactivation, recovery, and selection policies into a single
 * connector with unified configuration.
 *
 * Connector ID: modelmesh.stick-until-failure.v1
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface StickUntilFailureConfig {
  failureThreshold?: number;
  cooldownSeconds?: number;
  errorRateThreshold?: number;
  requestLimit?: number;
  tokenLimit?: number;
  budgetLimit?: number;
  modelPriority?: string[];
}

export class StickUntilFailurePolicy {
  static readonly CONNECTOR_ID = 'modelmesh.stick-until-failure.v1';
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;
  readonly config: Required<StickUntilFailureConfig>;

  constructor(config?: StickUntilFailureConfig) {
    this.config = {
      failureThreshold: config?.failureThreshold ?? 3,
      cooldownSeconds: config?.cooldownSeconds ?? 60,
      errorRateThreshold: config?.errorRateThreshold ?? 0.5,
      requestLimit: config?.requestLimit ?? 0,
      tokenLimit: config?.tokenLimit ?? 0,
      budgetLimit: config?.budgetLimit ?? 0,
      modelPriority: config?.modelPriority ?? [],
    };
  }

  /**
   * Determine whether a model should be deactivated based on its state.
   */
  shouldDeactivate(state: {
    consecutiveFailures: number;
    errorRate: number;
    totalRequests: number;
    totalTokens: number;
    totalCost: number;
  }): boolean {
    if (state.consecutiveFailures >= this.config.failureThreshold) return true;
    if (state.errorRate > this.config.errorRateThreshold && state.totalRequests > 0) return true;
    if (this.config.requestLimit > 0 && state.totalRequests >= this.config.requestLimit) return true;
    if (this.config.tokenLimit > 0 && state.totalTokens >= this.config.tokenLimit) return true;
    if (this.config.budgetLimit > 0 && state.totalCost >= this.config.budgetLimit) return true;
    return false;
  }

  /**
   * Determine whether a standby model should be recovered.
   */
  shouldRecover(state: {
    deactivatedAt?: Date;
  }): boolean {
    if (!state.deactivatedAt) return false;
    const elapsed = (Date.now() - state.deactivatedAt.getTime()) / 1000;
    return elapsed >= this.config.cooldownSeconds;
  }

  /**
   * Select the best candidate from active models.
   */
  select<T extends { modelId: string; errorRate: number }>(
    candidates: T[]
  ): T | null {
    if (candidates.length === 0) return null;

    // Try priority list first
    if (this.config.modelPriority.length > 0) {
      for (const priorityId of this.config.modelPriority) {
        const match = candidates.find((c) => c.modelId === priorityId);
        if (match) return match;
      }
    }

    // Fallback: lowest error rate
    return candidates.reduce((best, c) =>
      c.errorRate < best.errorRate ? c : best
    );
  }
}
