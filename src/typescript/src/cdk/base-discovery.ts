/**
 * Base discovery connector implementation.
 *
 * Implements the DiscoveryConnector interface with configurable sync
 * and health probe intervals. Subclasses override probe() to implement
 * protocol-specific health checks.
 */

import {
  DiscoveryConnector,
  HealthReport,
  ProbeResult,
  SyncResult,
  SyncStatus,
} from '../interfaces/discovery';
import { createDefaultHealthReport } from '../interfaces/provider';

export interface BaseDiscoveryConfig {
  syncIntervalSeconds?: number;
  probeIntervalSeconds?: number;
  failureThreshold?: number;
  providers?: string[];
}

export class BaseDiscovery implements DiscoveryConnector {
  protected readonly _config: Required<BaseDiscoveryConfig>;
  protected _knownModels = new Map<string, string[]>();
  protected _healthReports = new Map<string, HealthReport>();
  protected _lastSync?: Date;
  protected _modelsSynced = 0;

  constructor(config?: BaseDiscoveryConfig) {
    this._config = {
      syncIntervalSeconds: config?.syncIntervalSeconds ?? 300,
      probeIntervalSeconds: config?.probeIntervalSeconds ?? 60,
      failureThreshold: config?.failureThreshold ?? 3,
      providers: config?.providers ?? [],
    };
  }

  async sync(providers?: string[]): Promise<SyncResult> {
    const result: SyncResult = {
      newModels: [],
      deprecatedModels: [],
      updatedModels: [],
      errors: [],
    };

    const targetProviders = providers ?? this._config.providers;
    for (const providerId of targetProviders) {
      try {
        const probe = await this.probe(providerId);
        this._healthReports.set(
          providerId,
          createDefaultHealthReport({
            providerId,
            available: probe.success,
            latencyMs: probe.latencyMs,
            statusCode: probe.statusCode,
            error: probe.error,
          })
        );
      } catch (err) {
        result.errors.push(`${providerId}: ${err}`);
      }
    }

    this._lastSync = new Date();
    this._modelsSynced = Array.from(this._knownModels.values()).reduce(
      (sum, models) => sum + models.length,
      0
    );

    return result;
  }

  async getSyncStatus(): Promise<SyncStatus> {
    const nextSync = this._lastSync
      ? new Date(this._lastSync.getTime() + this._config.syncIntervalSeconds * 1000)
      : undefined;

    return {
      lastSync: this._lastSync,
      nextSync,
      modelsSynced: this._modelsSynced,
      status: this._lastSync ? 'synced' : 'pending',
    };
  }

  async probe(providerId: string): Promise<ProbeResult> {
    // Base implementation returns a successful probe.
    // Subclasses override with HTTP, gRPC, or TCP health checks.
    return {
      providerId,
      success: true,
      latencyMs: 0,
    };
  }

  async getHealthReport(providerId?: string): Promise<HealthReport[]> {
    if (providerId) {
      const report = this._healthReports.get(providerId);
      return report ? [report] : [];
    }
    return Array.from(this._healthReports.values());
  }
}
