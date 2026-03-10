/**
 * Console observability for the CDK.
 *
 * Extends BaseObservability with ANSI-colored console output for
 * development and debugging. Events, logs, and statistics are printed
 * to stdout with color coding by type.
 */

import { BaseObservability, BaseObservabilityConfig } from '../base-observability';
import {
  AggregateStats,
  RequestLogEntry,
  RoutingEvent,
  Severity,
  TraceEntry,
} from '../../interfaces/observability';

// ANSI color codes
const Colors = {
  RESET: '\x1b[0m',
  BOLD: '\x1b[1m',
  DIM: '\x1b[2m',
  RED: '\x1b[31m',
  GREEN: '\x1b[32m',
  YELLOW: '\x1b[33m',
  BLUE: '\x1b[34m',
  MAGENTA: '\x1b[35m',
  CYAN: '\x1b[36m',
  WHITE: '\x1b[37m',
  BG_RED: '\x1b[41m',
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

export interface ConsoleObservabilityConfig extends BaseObservabilityConfig {
  useColor?: boolean;
  showTimestamp?: boolean;
  prefix?: string;
}

/**
 * Observability connector with ANSI-colored console output.
 *
 * Designed for development and debugging. Prints routing events,
 * request/response logs, and aggregate statistics to stdout with
 * color coding.
 *
 * @example
 * const obs = new ConsoleObservability({
 *   logLevel: 'summary',
 *   useColor: true,
 * });
 */
export class ConsoleObservability extends BaseObservability {
  private readonly _consoleConfig: Required<ConsoleObservabilityConfig>;

  constructor(config?: ConsoleObservabilityConfig) {
    super(config);
    this._consoleConfig = {
      logLevel: config?.logLevel ?? 'metadata',
      eventFilter: config?.eventFilter ?? [],
      minSeverity: config?.minSeverity ?? 'info',
      redactSecrets: config?.redactSecrets ?? true,
      useColor: config?.useColor ?? true,
      showTimestamp: config?.showTimestamp ?? true,
      prefix: config?.prefix ?? '[ModelMesh]',
    };
  }

  private _colorize(text: string, color: string, bold = false): string {
    if (!this._consoleConfig.useColor) return text;
    const prefix = bold ? Colors.BOLD + color : color;
    return `${prefix}${text}${Colors.RESET}`;
  }

  private _dim(text: string): string {
    if (!this._consoleConfig.useColor) return text;
    return `${Colors.DIM}${text}${Colors.RESET}`;
  }

  private _formatTimestamp(date: Date): string {
    const h = String(date.getHours()).padStart(2, '0');
    const m = String(date.getMinutes()).padStart(2, '0');
    const s = String(date.getSeconds()).padStart(2, '0');
    const ms = String(date.getMilliseconds()).padStart(3, '0');
    return `${h}:${m}:${s}.${ms}`;
  }

  emit(event: RoutingEvent): void {
    if (this._config.eventFilter.length > 0) {
      if (!this._config.eventFilter.includes(event.eventType)) return;
    }

    const eventName = event.eventType;
    const color = EVENT_COLORS[eventName] ?? Colors.WHITE;
    const parts: string[] = [];

    if (this._consoleConfig.showTimestamp) {
      parts.push(this._dim(this._formatTimestamp(event.timestamp)));
    }
    if (this._consoleConfig.prefix) {
      parts.push(this._consoleConfig.prefix);
    }
    parts.push(this._colorize(`EVENT:${eventName}`, color, true));

    const details: string[] = [];
    if (event.modelId) details.push(`model=${event.modelId}`);
    if (event.providerId) details.push(`provider=${event.providerId}`);
    if (event.poolId) details.push(`pool=${event.poolId}`);
    if (event.metadata) {
      for (const [k, v] of Object.entries(event.metadata)) {
        details.push(`${k}=${v}`);
      }
    }
    if (details.length) parts.push(this._dim(details.join(' ')));

    console.log(parts.join(' '));
  }

  log(entry: RequestLogEntry): void {
    const parts: string[] = [];

    if (this._consoleConfig.showTimestamp) {
      parts.push(this._dim(this._formatTimestamp(entry.timestamp)));
    }
    if (this._consoleConfig.prefix) {
      parts.push(this._consoleConfig.prefix);
    }

    let statusColor: string;
    if (entry.statusCode >= 500) statusColor = Colors.RED;
    else if (entry.statusCode >= 400) statusColor = Colors.YELLOW;
    else statusColor = Colors.GREEN;

    parts.push(this._colorize('LOG', Colors.BLUE, true));
    parts.push(this._colorize(String(entry.statusCode), statusColor));
    parts.push(`${entry.latencyMs.toFixed(0)}ms`);
    parts.push(`model=${entry.modelId}`);
    parts.push(`provider=${entry.providerId}`);

    if (['summary', 'full'].includes(this._consoleConfig.logLevel)) {
      parts.push(`in=${entry.tokensIn}`);
      parts.push(`out=${entry.tokensOut}`);
      if (entry.cost != null) parts.push(`cost=$${entry.cost.toFixed(6)}`);
    }
    if (this._consoleConfig.logLevel === 'full' && entry.error) {
      parts.push(this._colorize(`error=${entry.error}`, Colors.RED));
    }

    console.log(parts.join(' '));
  }

  flush(stats: Record<string, AggregateStats>): void {
    if (!Object.keys(stats).length) return;

    const parts: string[] = [];
    if (this._consoleConfig.prefix) parts.push(this._consoleConfig.prefix);
    parts.push(this._colorize('STATS', Colors.MAGENTA, true));
    console.log(parts.join(' '));

    for (const [scopeId, agg] of Object.entries(stats)) {
      console.log(
        `  ${scopeId}: reqs=${agg.requestsTotal} ok=${agg.requestsSuccess} ` +
        `fail=${agg.requestsFailed} cost=$${agg.costTotal.toFixed(4)} ` +
        `avg=${agg.latencyAvg.toFixed(1)}ms p95=${agg.latencyP95.toFixed(1)}ms`
      );
    }
  }

  trace(entry: TraceEntry): void {
    const minLevel = BaseObservability.SEVERITY_ORDER[this._config.minSeverity] ?? 1;
    const entryLevel = BaseObservability.SEVERITY_ORDER[entry.severity] ?? 0;
    if (entryLevel < minLevel) return;

    const parts: string[] = [];
    if (this._consoleConfig.showTimestamp) {
      parts.push(this._dim(this._formatTimestamp(entry.timestamp)));
    }
    if (this._consoleConfig.prefix) parts.push(this._consoleConfig.prefix);

    const sevColor = SEVERITY_COLORS[entry.severity] ?? Colors.WHITE;
    parts.push(this._colorize(`TRACE:${entry.severity.toUpperCase()}`, sevColor, true));
    parts.push(this._dim(`[${entry.component}]`));
    parts.push(entry.message);

    if (entry.error) parts.push(this._colorize(`error=${entry.error}`, Colors.RED));
    if (entry.metadata) {
      for (const [k, v] of Object.entries(entry.metadata)) {
        parts.push(this._dim(`${k}=${v}`));
      }
    }

    console.log(parts.join(' '));
  }
}
