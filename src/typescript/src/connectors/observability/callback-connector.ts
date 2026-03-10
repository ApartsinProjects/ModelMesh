/**
 * Callback observability connector.
 *
 * Invokes user-provided functions for each observability event type.
 * Useful for testing, custom integrations, and in-process event processing.
 *
 * Connector ID: modelmesh.callback.v1
 */

import {
  AggregateStats,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  TraceEntry,
} from '../../interfaces/observability';
import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface CallbackConnectorConfig {
  onTrace?: (entry: TraceEntry) => void;
  onEvent?: (event: RoutingEvent) => void;
  onLog?: (entry: RequestLogEntry) => void;
  onStats?: (stats: Record<string, AggregateStats>) => void;
}

export class CallbackConnector implements ObservabilityConnector {
  static readonly CONNECTOR_ID = 'modelmesh.callback.v1';
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;
  private readonly _config: CallbackConnectorConfig;

  constructor(config?: CallbackConnectorConfig) {
    this._config = config ?? {};
  }

  trace(entry: TraceEntry): void {
    if (this._config.onTrace) {
      this._config.onTrace(entry);
    }
  }

  emit(event: RoutingEvent): void {
    if (this._config.onEvent) {
      this._config.onEvent(event);
    }
  }

  log(entry: RequestLogEntry): void {
    if (this._config.onLog) {
      this._config.onLog(entry);
    }
  }

  flush(stats: Record<string, AggregateStats>): void {
    if (this._config.onStats) {
      this._config.onStats(stats);
    }
  }
}
