/**
 * Console observability connector.
 *
 * Connector ID: modelmesh.console.v1
 */

import {
  AggregateStats,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  Severity,
  TraceEntry,
} from '../../interfaces/observability';
import { RuntimeEnvironment } from '../../interfaces/runtime';

const Colors = {
  RESET: '[0m',
  BOLD: '[1m',
  DIM: '[2m',
  RED: '[31m',
  GREEN: '[32m',
  YELLOW: '[33m',
  BLUE: '[34m',
  MAGENTA: '[35m',
  CYAN: '[36m',
  WHITE: '[37m',
  BG_RED: '[41m',
} as const;

const EVENT_COLORS: Record<string, string> = {
  model_activated: Colors.GREEN,
  provider_recovered: Colors.GREEN,
  model_deactivated: Colors.RED,
  provider_deactivated: Colors.RED,
  model_rotated: Colors.YELLOW,
  provider_health_changed: Colors.YELLOW,
  pool_membership_changed: Colors.CYAN,
  discovery_models_updated: Colors.BLUE,
};

const SEVERITY_COLORS: Record<string, string> = {
  debug: Colors.DIM,
  info: Colors.BLUE,
  warning: Colors.YELLOW,
  error: Colors.RED,
  critical: Colors.BG_RED + Colors.WHITE,
};

const SEVERITY_ORDER: Record<string, number> = {
  [Severity.DEBUG]: 0,
  [Severity.INFO]: 1,
  [Severity.WARNING]: 2,
  [Severity.ERROR]: 3,
  [Severity.CRITICAL]: 4,
};

export interface ConsoleConnectorConfig {
  useColor?: boolean;
  showTimestamp?: boolean;
  prefix?: string;
  logLevel?: string;
  minSeverity?: string;
}

export class ConsoleObservabilityConnector implements ObservabilityConnector {
  static readonly CONNECTOR_ID = 'modelmesh.console.v1';
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;
  private readonly _config: Required<ConsoleConnectorConfig>;

  constructor(config?: ConsoleConnectorConfig) {
    this._config = {
      useColor: config?.useColor ?? true,
      showTimestamp: config?.showTimestamp ?? true,
      prefix: config?.prefix ?? '[ModelMesh]',
      logLevel: config?.logLevel ?? 'metadata',
      minSeverity: config?.minSeverity ?? 'info',
    };
  }

  emit(event: RoutingEvent): void {
    const parts: string[] = [];
    if (this._config.showTimestamp) parts.push(this.dim(this.fmtTime(event.timestamp)));
    if (this._config.prefix) parts.push(this._config.prefix);
    const color = EVENT_COLORS[event.eventType] ?? Colors.WHITE;
    parts.push(this.colorize('EVENT:' + event.eventType, color, true));
    const d: string[] = [];
    if (event.modelId) d.push('model=' + event.modelId);
    if (event.providerId) d.push('provider=' + event.providerId);
    if (event.poolId) d.push('pool=' + event.poolId);
    if (event.metadata) Object.entries(event.metadata).forEach(([k,v]) => d.push(k + '=' + v));
    if (d.length) parts.push(this.dim(d.join(' ')));
    console.log(parts.join(' '));
  }

  log(entry: RequestLogEntry): void {
    const parts: string[] = [];
    if (this._config.showTimestamp) parts.push(this.dim(this.fmtTime(entry.timestamp)));
    if (this._config.prefix) parts.push(this._config.prefix);
    let sc: string = Colors.GREEN;
    if (entry.statusCode >= 500) sc = Colors.RED;
    else if (entry.statusCode >= 400) sc = Colors.YELLOW;
    parts.push(this.colorize('LOG', Colors.BLUE, true));
    parts.push(this.colorize(String(entry.statusCode), sc));
    parts.push(Math.round(entry.latencyMs) + 'ms');
    parts.push('model=' + entry.modelId);
    parts.push('provider=' + entry.providerId);
    if (this._config.logLevel === 'summary' || this._config.logLevel === 'full') {
      parts.push('in=' + entry.tokensIn);
      parts.push('out=' + entry.tokensOut);
      if (entry.cost != null) parts.push('cost=$' + entry.cost.toFixed(6));
    }
    if (this._config.logLevel === 'full' && entry.error) parts.push(this.colorize('error=' + entry.error, Colors.RED));
    console.log(parts.join(' '));
  }

  flush(stats: Record<string, AggregateStats>): void {
    if (!Object.keys(stats).length) return;
    const hdr = 'Scope'.padEnd(30) + ' ' + 'Reqs'.padStart(8) + ' ' + 'OK'.padStart(8) + ' ' +
      'Fail'.padStart(8) + ' ' + 'Tok In'.padStart(10) + ' ' + 'Tok Out'.padStart(10) + ' ' +
      'Cost'.padStart(10) + ' ' + 'Avg ms'.padStart(8) + ' ' + 'P95 ms'.padStart(8) + ' ' + 'Rotations'.padStart(10);
    const sep = '-'.repeat(hdr.length);
    const tp: string[] = [];
    if (this._config.prefix) tp.push(this._config.prefix);
    tp.push(this.colorize('STATS', Colors.MAGENTA, true));
    console.log(tp.join(' '));
    console.log(this.colorize(sep, Colors.DIM));
    console.log(this.colorize(hdr, Colors.BOLD));
    console.log(this.colorize(sep, Colors.DIM));
    for (const [id, a] of Object.entries(stats)) {
      console.log(id.padEnd(30) + ' ' + String(a.requestsTotal).padStart(8) + ' ' +
        String(a.requestsSuccess).padStart(8) + ' ' + String(a.requestsFailed).padStart(8) + ' ' +
        String(a.tokensIn).padStart(10) + ' ' + String(a.tokensOut).padStart(10) + ' ' +
        a.costTotal.toFixed(4).padStart(10) + ' ' +
        a.latencyAvg.toFixed(1).padStart(8) + ' ' + a.latencyP95.toFixed(1).padStart(8) + ' ' +
        String(a.rotationEvents).padStart(10));
    }
    console.log(this.colorize(sep, Colors.DIM));
  }

  trace(entry: TraceEntry): void {
    const minLvl = SEVERITY_ORDER[this._config.minSeverity] ?? 1;
    const entLvl = SEVERITY_ORDER[entry.severity] ?? 0;
    if (entLvl < minLvl) return;
    const parts: string[] = [];
    if (this._config.showTimestamp) parts.push(this.dim(this.fmtTime(entry.timestamp)));
    if (this._config.prefix) parts.push(this._config.prefix);
    const sc = SEVERITY_COLORS[entry.severity] ?? Colors.WHITE;
    parts.push(this.colorize('TRACE:' + entry.severity.toUpperCase(), sc, true));
    parts.push(this.dim('[' + entry.component + ']'));
    parts.push(entry.message);
    if (entry.error) parts.push(this.colorize('error=' + entry.error, Colors.RED));
    if (entry.metadata) Object.entries(entry.metadata).forEach(([k,v]) => parts.push(this.dim(k + '=' + v)));
    console.log(parts.join(' '));
  }

  private fmtTime(d: Date): string {
    return String(d.getHours()).padStart(2,'0') + ':' +
      String(d.getMinutes()).padStart(2,'0') + ':' +
      String(d.getSeconds()).padStart(2,'0') + '.' +
      String(d.getMilliseconds()).padStart(3,'0');
  }

  private colorize(text: string, color: string, bold = false): string {
    if (!this._config.useColor) return text;
    return (bold ? Colors.BOLD + color : color) + text + Colors.RESET;
  }

  private dim(text: string): string {
    if (!this._config.useColor) return text;
    return Colors.DIM + text + Colors.RESET;
  }
}
