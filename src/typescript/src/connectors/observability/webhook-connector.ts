/**
 * Webhook observability connector.
 *
 * Posts observability data to HTTP endpoints via POST requests.
 * Suitable for forwarding alerts to Slack, Discord, PagerDuty,
 * or any custom webhook receiver.
 *
 * Uses only Node.js built-in http/https modules -- zero external dependencies.
 *
 * Connector ID: modelmesh.webhook.v1
 */

import * as http from 'http';
import * as https from 'https';
import {
  AggregateStats,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  Severity,
  TraceEntry,
} from '../../interfaces/observability';

const SEVERITY_ORDER: Record<string, number> = {
  [Severity.DEBUG]: 0,
  [Severity.INFO]: 1,
  [Severity.WARNING]: 2,
  [Severity.ERROR]: 3,
  [Severity.CRITICAL]: 4,
};

export interface WebhookConnectorConfig {
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  minSeverity?: string;
  batchSize?: number;
  timeoutSeconds?: number;
}

export class WebhookConnector implements ObservabilityConnector {
  static readonly CONNECTOR_ID = 'modelmesh.webhook.v1';
  private readonly _config: Required<WebhookConnectorConfig>;
  private _batch: Record<string, unknown>[] = [];

  constructor(config?: WebhookConnectorConfig) {
    this._config = {
      url: config?.url ?? '',
      method: config?.method ?? 'POST',
      headers: config?.headers ?? {},
      minSeverity: config?.minSeverity ?? 'error',
      batchSize: config?.batchSize ?? 1,
      timeoutSeconds: config?.timeoutSeconds ?? 10,
    };
  }

  private _meetsSeverity(severity: string): boolean {
    const level = SEVERITY_ORDER[severity] ?? 0;
    const threshold = SEVERITY_ORDER[this._config.minSeverity] ?? 3;
    return level >= threshold;
  }

  private _enqueue(record: Record<string, unknown>): void {
    this._batch.push(record);
    if (this._batch.length >= this._config.batchSize) {
      this.flushBatch();
    }
  }

  flushBatch(): void {
    if (!this._batch.length || !this._config.url) return;

    const payload = this._batch.length > 1 ? this._batch : this._batch[0];
    this._batch = [];

    try {
      const body = JSON.stringify(payload);
      const url = new URL(this._config.url);
      const transport = url.protocol === 'https:' ? https : http;
      const options: http.RequestOptions = {
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: url.pathname + url.search,
        method: this._config.method,
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body).toString(),
          ...this._config.headers,
        },
        timeout: this._config.timeoutSeconds * 1000,
      };

      const req = transport.request(options);
      req.on('error', () => { /* silently discard */ });
      req.write(body);
      req.end();
    } catch {
      // Silently discard on failure
    }
  }

  private _makeRecord(
    recordType: string,
    severity: string,
    component: string,
    message: string,
    metadata?: Record<string, unknown>
  ): Record<string, unknown> {
    return {
      type: recordType,
      timestamp: new Date().toISOString(),
      severity,
      component,
      message,
      metadata: metadata ?? {},
    };
  }

  trace(entry: TraceEntry): void {
    if (!this._meetsSeverity(entry.severity)) return;
    const record = this._makeRecord(
      'trace',
      entry.severity,
      entry.component,
      entry.message,
      { ...(entry.metadata || {}), error: entry.error }
    );
    record.timestamp = entry.timestamp.toISOString();
    this._enqueue(record);
  }

  emit(event: RoutingEvent): void {
    const severity = Severity.INFO;
    if (!this._meetsSeverity(severity)) return;
    const record = this._makeRecord(
      'event',
      severity,
      'router',
      event.eventType,
      {
        modelId: event.modelId,
        providerId: event.providerId,
        poolId: event.poolId,
        ...(event.metadata || {}),
      }
    );
    record.timestamp = event.timestamp.toISOString();
    this._enqueue(record);
  }

  log(entry: RequestLogEntry): void {
    const severity = entry.error ? Severity.ERROR : Severity.INFO;
    if (!this._meetsSeverity(severity)) return;
    const record = this._makeRecord(
      'log',
      severity,
      'provider.' + entry.providerId,
      entry.capability + ' ' + entry.statusCode + ' ' + Math.round(entry.latencyMs) + 'ms',
      {
        modelId: entry.modelId,
        providerId: entry.providerId,
        latencyMs: entry.latencyMs,
        statusCode: entry.statusCode,
        tokensIn: entry.tokensIn,
        tokensOut: entry.tokensOut,
        cost: entry.cost,
        error: entry.error,
      }
    );
    record.timestamp = entry.timestamp.toISOString();
    this._enqueue(record);
  }

  flush(stats: Record<string, AggregateStats>): void {
    const severity = Severity.INFO;
    if (!this._meetsSeverity(severity)) return;
    for (const [entityId, agg] of Object.entries(stats)) {
      const record = this._makeRecord(
        'stats',
        severity,
        entityId,
        'stats flush: ' + agg.requestsTotal + ' requests',
        {
          requestsTotal: agg.requestsTotal,
          requestsSuccess: agg.requestsSuccess,
          requestsFailed: agg.requestsFailed,
          tokensIn: agg.tokensIn,
          tokensOut: agg.tokensOut,
          costTotal: agg.costTotal,
          latencyAvg: agg.latencyAvg,
          latencyP95: agg.latencyP95,
        }
      );
      this._enqueue(record);
    }
  }
}
