/**
 * JSON Lines observability connector.
 *
 * Writes traces, events, request logs, and aggregate statistics as
 * JSON Lines (one JSON object per line) to a file. Supports file
 * rotation when the file exceeds a configurable size limit.
 *
 * Connector ID: modelmesh.jsonlog.v1
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  AggregateStats,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  Severity,
  TraceEntry,
} from '../../interfaces/observability';

export interface JsonLogConnectorConfig {
  filePath?: string;
  append?: boolean;
  maxSizeMb?: number;
}

export class JsonLogConnector implements ObservabilityConnector {
  static readonly CONNECTOR_ID = 'modelmesh.jsonlog.v1';
  private readonly _config: Required<JsonLogConnectorConfig>;
  private _fd: number | null = null;

  constructor(config?: JsonLogConnectorConfig) {
    this._config = {
      filePath: config?.filePath ?? 'modelmesh_events.jsonl',
      append: config?.append ?? true,
      maxSizeMb: config?.maxSizeMb ?? 0,
    };
    this._openFile();
  }

  private _openFile(): void {
    const dir = path.dirname(this._config.filePath);
    if (dir) fs.mkdirSync(dir, { recursive: true });
    this._fd = fs.openSync(this._config.filePath, this._config.append ? 'a' : 'w');
  }

  private _writeLine(record: Record<string, unknown>): void {
    if (this._fd === null) this._openFile();

    if (this._config.maxSizeMb > 0) {
      try {
        const maxBytes = this._config.maxSizeMb * 1024 * 1024;
        if (fs.fstatSync(this._fd!).size >= maxBytes) this._rotate();
      } catch { /* ignore */ }
    }

    const line = JSON.stringify(record);
    fs.writeSync(this._fd!, line + '\n');
  }

  private _rotate(): void {
    if (this._fd !== null) { fs.closeSync(this._fd); this._fd = null; }
    const rotated = this._config.filePath + '.1';
    try {
      if (fs.existsSync(rotated)) fs.unlinkSync(rotated);
      fs.renameSync(this._config.filePath, rotated);
    } catch { /* ignore */ }
    this._openFile();
  }

  emit(event: RoutingEvent): void {
    this._writeLine({
      type: 'event',
      timestamp: event.timestamp.toISOString(),
      severity: Severity.INFO,
      component: 'router',
      message: event.eventType,
      metadata: {
        modelId: event.modelId,
        providerId: event.providerId,
        poolId: event.poolId,
        ...(event.metadata || {}),
      },
    });
  }

  log(entry: RequestLogEntry): void {
    const severity = entry.error ? Severity.ERROR : Severity.INFO;
    this._writeLine({
      type: 'log',
      timestamp: entry.timestamp.toISOString(),
      severity,
      component: 'provider.' + entry.providerId,
      message: entry.capability + ' ' + entry.statusCode + ' ' + Math.round(entry.latencyMs) + 'ms',
      metadata: {
        modelId: entry.modelId,
        providerId: entry.providerId,
        capability: entry.capability,
        deliveryMode: entry.deliveryMode,
        latencyMs: entry.latencyMs,
        statusCode: entry.statusCode,
        tokensIn: entry.tokensIn,
        tokensOut: entry.tokensOut,
        cost: entry.cost,
        error: entry.error,
      },
    });
  }

  flush(stats: Record<string, AggregateStats>): void {
    const now = new Date().toISOString();
    for (const [entityId, agg] of Object.entries(stats)) {
      this._writeLine({
        type: 'stats',
        timestamp: now,
        severity: Severity.INFO,
        component: entityId,
        message: 'stats flush: ' + agg.requestsTotal + ' requests',
        metadata: {
          requestsTotal: agg.requestsTotal,
          requestsSuccess: agg.requestsSuccess,
          requestsFailed: agg.requestsFailed,
          tokensIn: agg.tokensIn,
          tokensOut: agg.tokensOut,
          costTotal: agg.costTotal,
          latencyAvg: agg.latencyAvg,
          latencyP95: agg.latencyP95,
          downtimeTotal: agg.downtimeTotal,
          rotationEvents: agg.rotationEvents,
        },
      });
    }
  }

  trace(entry: TraceEntry): void {
    this._writeLine({
      type: 'trace',
      timestamp: entry.timestamp.toISOString(),
      severity: entry.severity,
      component: entry.component,
      message: entry.message,
      metadata: entry.metadata || {},
      error: entry.error,
    });
  }

  close(): void {
    if (this._fd !== null) { fs.closeSync(this._fd); this._fd = null; }
  }
}
