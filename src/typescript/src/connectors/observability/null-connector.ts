/**
 * Null observability connector -- discards all output.
 *
 * This is the default observability connector used when no other connector
 * is configured. It implements all ObservabilityConnector methods as no-ops
 * for zero overhead.
 *
 * Connector ID: modelmesh.null.v1
 */

import {
  AggregateStats,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  TraceEntry,
} from '../../interfaces/observability';

export class NullObservabilityConnector implements ObservabilityConnector {
  static readonly CONNECTOR_ID = 'modelmesh.null.v1';

  emit(_event: RoutingEvent): void {
    // no-op
  }

  log(_entry: RequestLogEntry): void {
    // no-op
  }

  flush(_stats: Record<string, AggregateStats>): void {
    // no-op
  }

  trace(_entry: TraceEntry): void {
    // no-op
  }
}
