/**
 * Base observability implementation for the CDK.
 *
 * Provides sensible defaults for the ObservabilityConnector interface
 * with configurable log level, event filtering, and severity thresholds.
 * Subclasses override _write* methods to direct output to console,
 * files, webhooks, etc.
 */

import {
  AggregateStats,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  Severity,
  TraceEntry,
} from '../interfaces/observability';

export interface BaseObservabilityConfig {
  logLevel?: string;
  eventFilter?: string[];
  minSeverity?: string;
  redactSecrets?: boolean;
}

export class BaseObservability implements ObservabilityConnector {
  protected readonly _config: Required<BaseObservabilityConfig>;

  static readonly SEVERITY_ORDER: Record<string, number> = {
    debug: 0,
    info: 1,
    warning: 2,
    error: 3,
    critical: 4,
  };

  constructor(config?: BaseObservabilityConfig) {
    this._config = {
      logLevel: config?.logLevel ?? 'metadata',
      eventFilter: config?.eventFilter ?? [],
      minSeverity: config?.minSeverity ?? 'info',
      redactSecrets: config?.redactSecrets ?? true,
    };
  }

  emit(event: RoutingEvent): void {
    if (this._config.eventFilter.length > 0) {
      if (!this._config.eventFilter.includes(event.eventType)) return;
    }
  }

  log(_entry: RequestLogEntry): void {}
  flush(_stats: Record<string, AggregateStats>): void {}

  trace(entry: TraceEntry): void {
    const minLevel = BaseObservability.SEVERITY_ORDER[this._config.minSeverity] ?? 1;
    const entryLevel = BaseObservability.SEVERITY_ORDER[entry.severity] ?? 0;
    if (entryLevel < minLevel) return;
  }
}
