/**
 * Usage tracking facade for ModelMesh.
 *
 * Exposes cost and token usage data from the internal CostTracker
 * through a clean, read-only API suitable for application dashboards
 * and monitoring.
 */

import type { ModelMesh } from './core/mesh';

/** Usage breakdown for a single model. */
export interface ModelUsage {
  modelId: string;
  totalCost: number;
  totalRequests: number;
}

/** Usage breakdown for a single provider. */
export interface ProviderUsage {
  providerId: string;
  totalCost: number;
}

/** Budget status snapshot. */
export interface BudgetStatus {
  dailyUsed: number;
  dailyLimit: number | null;
  dailyRemaining: number | null;
  monthlyUsed: number;
  monthlyLimit: number | null;
  monthlyRemaining: number | null;
  exceeded: boolean;
  alert: boolean;
}

/**
 * Read-only facade over ModelMesh cost and usage tracking.
 *
 * Wraps the internal CostTracker (if budget is configured)
 * to provide clean usage queries.
 */
export class UsageTracker {
  private _mesh: ModelMesh;

  constructor(mesh: ModelMesh) {
    this._mesh = mesh;
  }

  private _getCostTracker(): any | null {
    return (this._mesh as any)._costTracker ?? null;
  }

  /** Total cost accumulated across all models and providers. */
  get totalCost(): number {
    const tracker = this._getCostTracker();
    if (!tracker) return 0;
    const summary = tracker.summary();
    return summary.totalCost ?? 0;
  }

  /** Cost accumulated today (UTC). */
  get dailyCost(): number {
    const tracker = this._getCostTracker();
    if (!tracker) return 0;
    return tracker.getDailyCost();
  }

  /** Cost accumulated this month (UTC). */
  get monthlyCost(): number {
    const tracker = this._getCostTracker();
    if (!tracker) return 0;
    return tracker.getMonthlyCost();
  }

  /** Total tokens consumed across all requests. */
  get totalTokens(): number {
    const tracker = this._getCostTracker();
    if (!tracker) return 0;
    const records = tracker._records ?? [];
    return records.reduce(
      (sum: number, r: any) => sum + (r.promptTokens ?? 0) + (r.completionTokens ?? 0),
      0
    );
  }

  /** Usage breakdown by model ID. */
  get byModel(): Record<string, ModelUsage> {
    const tracker = this._getCostTracker();
    if (!tracker) return {};
    const summary = tracker.summary();
    const byModelCost = summary.byModel ?? {};
    const result: Record<string, ModelUsage> = {};
    for (const [modelId, cost] of Object.entries(byModelCost)) {
      result[modelId] = {
        modelId,
        totalCost: cost as number,
        totalRequests: 0,
      };
    }
    return result;
  }

  /** Usage breakdown by provider connector ID. */
  get byProvider(): Record<string, ProviderUsage> {
    const tracker = this._getCostTracker();
    if (!tracker) return {};
    const summary = tracker.summary();
    const byProviderCost = summary.byProvider ?? {};
    const result: Record<string, ProviderUsage> = {};
    for (const [providerId, cost] of Object.entries(byProviderCost)) {
      result[providerId] = {
        providerId,
        totalCost: cost as number,
      };
    }
    return result;
  }

  /** Current budget status, or null if no budget is configured. */
  get budgetStatus(): BudgetStatus | null {
    const tracker = this._getCostTracker();
    if (!tracker) return null;
    return tracker.checkBudget();
  }

  /** Reset all usage counters. */
  reset(): void {
    const tracker = this._getCostTracker();
    if (tracker) {
      tracker.resetDaily();
      tracker.resetMonthly();
    }
  }

  /** Return a comprehensive usage summary. */
  summary(): Record<string, unknown> {
    const tracker = this._getCostTracker();
    if (!tracker) {
      return {
        totalCost: 0,
        dailyCost: 0,
        monthlyCost: 0,
        totalTokens: 0,
        byModel: {},
        byProvider: {},
        budgetStatus: null,
      };
    }
    const result = tracker.summary();
    result.totalTokens = this.totalTokens;
    return result;
  }
}
