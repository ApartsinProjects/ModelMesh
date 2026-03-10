/**
 * File observability connector.
 * Connector ID: modelmesh.file.v1
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  AggregateStats,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  TraceEntry,
} from '../../interfaces/observability';
import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface FileConnectorConfig {
  filePath?: string;
  append?: boolean;
  maxSizeMb?: number;
}

export class FileObservabilityConnector implements ObservabilityConnector {
  static readonly CONNECTOR_ID = 'modelmesh.file.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private readonly _config: Required<FileConnectorConfig>;
  private fd: number | null = null;

  constructor(config?: FileConnectorConfig) {
    this._config = {
      filePath: config?.filePath ?? 'modelmesh.log',
      append: config?.append ?? true,
      maxSizeMb: config?.maxSizeMb ?? 0,
    };
    this.openFile();
  }

  private openFile(): void {
    const dir = path.dirname(this._config.filePath);
    if (dir) fs.mkdirSync(dir, { recursive: true });
    this.fd = fs.openSync(this._config.filePath, this._config.append ? 'a' : 'w');
  }

  private writeLine(line: string): void {
    if (this.fd === null) this.openFile();
    if (this._config.maxSizeMb > 0) {
      try {
        if (fs.fstatSync(this.fd!).size >= this._config.maxSizeMb * 1024 * 1024) this.rotate();
      } catch { /* ignore */ }
    }
    fs.writeSync(this.fd!, line + '\n');
  }

  private rotate(): void {
    if (this.fd !== null) { fs.closeSync(this.fd); this.fd = null; }
    const rotated = this._config.filePath + '.1';
    try {
      if (fs.existsSync(rotated)) fs.unlinkSync(rotated);
      fs.renameSync(this._config.filePath, rotated);
    } catch { /* ignore */ }
    this.openFile();
  }

  emit(event: RoutingEvent): void {
    const d: string[] = [];
    if (event.modelId) d.push('model=' + event.modelId);
    if (event.providerId) d.push('provider=' + event.providerId);
    if (event.poolId) d.push('pool=' + event.poolId);
    this.writeLine(event.timestamp.toISOString() + ' EVENT:' + event.eventType + ' ' + d.join(' '));
  }

  log(entry: RequestLogEntry): void {
    let line = entry.timestamp.toISOString() + ' LOG ' + entry.statusCode + ' ';
    line += Math.round(entry.latencyMs) + 'ms model=' + entry.modelId;
    line += ' provider=' + entry.providerId + ' in=' + entry.tokensIn + ' out=' + entry.tokensOut;
    if (entry.cost != null) line += ' cost=$' + entry.cost.toFixed(6);
    if (entry.error) line += ' error=' + entry.error;
    this.writeLine(line);
  }

  flush(stats: Record<string, AggregateStats>): void {
    const now = new Date().toISOString();
    for (const [id, a] of Object.entries(stats)) {
      let line = now + ' STATS ' + id + ': requests=' + a.requestsTotal;
      line += ' success=' + a.requestsSuccess + ' failed=' + a.requestsFailed;
      line += ' tokensIn=' + a.tokensIn + ' tokensOut=' + a.tokensOut;
      line += ' cost=' + a.costTotal.toFixed(4);
      line += ' latencyAvg=' + a.latencyAvg.toFixed(1) + 'ms';
      line += ' latencyP95=' + a.latencyP95.toFixed(1) + 'ms';
      line += ' rotations=' + a.rotationEvents;
      this.writeLine(line);
    }
  }

  trace(entry: TraceEntry): void {
    let line = entry.timestamp.toISOString() + ' TRACE:' + entry.severity.toUpperCase();
    line += ' [' + entry.component + '] ' + entry.message;
    if (entry.error) line += ' error=' + entry.error;
    this.writeLine(line);
  }

  close(): void {
    if (this.fd !== null) { fs.closeSync(this.fd); this.fd = null; }
  }
}