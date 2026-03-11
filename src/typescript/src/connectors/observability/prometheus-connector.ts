/**
 * Prometheus observability connector.
 *
 * Exposes metrics in Prometheus text exposition format without requiring
 * any external libraries. All counters, gauges, and histograms are
 * maintained as plain data structures and rendered on demand via
 * `getMetrics()`.
 *
 * Connector ID: modelmesh.prometheus.v1
 */

import {
  AggregateStats,
  EventType,
  ObservabilityConnector,
  RequestLogEntry,
  RoutingEvent,
  TraceEntry,
} from '../../interfaces/observability';
import { RuntimeEnvironment } from '../../interfaces/runtime';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/** Configuration for the Prometheus observability connector. */
export interface PrometheusObservabilityConfig {
  /** Metric name prefix (default `"modelmesh"`). */
  readonly prefix?: string;
  /** Whether to include `model` labels on metrics. */
  readonly includeModelLabels?: boolean;
  /** Whether to include `provider` labels on metrics. */
  readonly includeProviderLabels?: boolean;
  /** Bucket boundaries for duration histograms (seconds). */
  readonly histogramBuckets?: number[];
}

// ---------------------------------------------------------------------------
// Default histogram bucket boundaries (seconds)
// ---------------------------------------------------------------------------

const DEFAULT_BUCKETS: number[] = [
  0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
];

// ---------------------------------------------------------------------------
// Internal metric primitives
// ---------------------------------------------------------------------------

/** Serialise a label dict to a string key for Map lookups. */
function labelsKey(labels: Record<string, string>): string {
  return Object.keys(labels)
    .sort()
    .map((k) => `${k}="${labels[k]}"`)
    .join(',');
}

/** Format a label dict as a Prometheus label string. */
function formatLabels(labels: Record<string, string>): string {
  const keys = Object.keys(labels).sort();
  if (keys.length === 0) return '';
  const parts = keys.map((k) => `${k}="${labels[k]}"`);
  return '{' + parts.join(',') + '}';
}

/** Thread-safe monotonically increasing counter with label sets. */
class Counter {
  private _values: Map<string, { labels: Record<string, string>; value: number }> = new Map();

  inc(labels: Record<string, string>, amount: number = 1.0): void {
    const key = labelsKey(labels);
    const existing = this._values.get(key);
    if (existing) {
      existing.value += amount;
    } else {
      this._values.set(key, { labels: { ...labels }, value: amount });
    }
  }

  items(): Array<{ labels: Record<string, string>; value: number }> {
    return Array.from(this._values.values());
  }
}

/** Thread-safe gauge that can go up and down. */
class Gauge {
  private _values: Map<string, { labels: Record<string, string>; value: number }> = new Map();

  set(labels: Record<string, string>, value: number): void {
    const key = labelsKey(labels);
    const existing = this._values.get(key);
    if (existing) {
      existing.value = value;
    } else {
      this._values.set(key, { labels: { ...labels }, value });
    }
  }

  inc(labels: Record<string, string>, amount: number = 1.0): void {
    const key = labelsKey(labels);
    const existing = this._values.get(key);
    if (existing) {
      existing.value += amount;
    } else {
      this._values.set(key, { labels: { ...labels }, value: amount });
    }
  }

  items(): Array<{ labels: Record<string, string>; value: number }> {
    return Array.from(this._values.values());
  }
}

/** Histogram with configurable buckets. */
class Histogram {
  private readonly _buckets: number[];
  private _data: Map<
    string,
    {
      labels: Record<string, string>;
      bucketCounts: number[];
      sum: number;
      count: number;
    }
  > = new Map();

  constructor(buckets: number[]) {
    this._buckets = [...buckets].sort((a, b) => a - b);
  }

  observe(labels: Record<string, string>, value: number): void {
    const key = labelsKey(labels);
    let entry = this._data.get(key);
    if (!entry) {
      entry = {
        labels: { ...labels },
        bucketCounts: new Array(this._buckets.length).fill(0),
        sum: 0,
        count: 0,
      };
      this._data.set(key, entry);
    }

    for (let i = 0; i < this._buckets.length; i++) {
      if (value <= this._buckets[i]) {
        entry.bucketCounts[i] += 1;
      }
    }
    entry.sum += value;
    entry.count += 1;
  }

  items(): Array<{
    labels: Record<string, string>;
    buckets: number[];
    bucketCounts: number[];
    sum: number;
    count: number;
  }> {
    return Array.from(this._data.values()).map((e) => ({
      labels: e.labels,
      buckets: [...this._buckets],
      bucketCounts: [...e.bucketCounts],
      sum: e.sum,
      count: e.count,
    }));
  }
}

// ---------------------------------------------------------------------------
// Prometheus text format helpers
// ---------------------------------------------------------------------------

function renderCounter(
  name: string,
  helpText: string,
  counter: Counter
): string[] {
  const items = counter.items();
  if (items.length === 0) return [];
  const lines: string[] = [
    `# HELP ${name} ${helpText}`,
    `# TYPE ${name} counter`,
  ];
  for (const { labels, value } of items) {
    lines.push(`${name}${formatLabels(labels)} ${value}`);
  }
  return lines;
}

function renderGauge(
  name: string,
  helpText: string,
  gauge: Gauge
): string[] {
  const items = gauge.items();
  if (items.length === 0) return [];
  const lines: string[] = [
    `# HELP ${name} ${helpText}`,
    `# TYPE ${name} gauge`,
  ];
  for (const { labels, value } of items) {
    lines.push(`${name}${formatLabels(labels)} ${value}`);
  }
  return lines;
}

function renderHistogram(
  name: string,
  helpText: string,
  histogram: Histogram
): string[] {
  const items = histogram.items();
  if (items.length === 0) return [];
  const lines: string[] = [
    `# HELP ${name} ${helpText}`,
    `# TYPE ${name} histogram`,
  ];

  for (const { labels, buckets, bucketCounts, sum, count } of items) {
    let cumulative = 0;
    for (let i = 0; i < buckets.length; i++) {
      cumulative += bucketCounts[i];
      const bucketLabels = { ...labels, le: String(buckets[i]) };
      lines.push(`${name}_bucket${formatLabels(bucketLabels)} ${cumulative}`);
    }
    const infLabels = { ...labels, le: '+Inf' };
    lines.push(`${name}_bucket${formatLabels(infLabels)} ${count}`);
    lines.push(`${name}_sum${formatLabels(labels)} ${sum}`);
    lines.push(`${name}_count${formatLabels(labels)} ${count}`);
  }
  return lines;
}

// ---------------------------------------------------------------------------
// PrometheusObservability
// ---------------------------------------------------------------------------

/**
 * Exposes metrics in Prometheus text exposition format.
 *
 * Implements the `ObservabilityConnector` interface and maintains
 * internal counters, gauges, and histograms. Call `getMetrics()` to
 * produce the text exposition string suitable for a `/metrics` HTTP
 * endpoint.
 *
 * No external dependencies are required; all metric storage is
 * handled with plain Maps.
 *
 * Connector ID: `modelmesh.prometheus.v1`
 *
 * Usage:
 *
 *   const connector = new PrometheusObservability({ prefix: 'myapp' });
 *   // ... events flow in via emit/log/flush/trace ...
 *   console.log(connector.getMetrics());
 */
export class PrometheusObservability implements ObservabilityConnector {
  static readonly CONNECTOR_ID = 'modelmesh.prometheus.v1';
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  private readonly _prefix: string;
  private readonly _includeModelLabels: boolean;
  private readonly _includeProviderLabels: boolean;

  // Counters
  private readonly _requestsTotal = new Counter();
  private readonly _tokensTotal = new Counter();
  private readonly _costDollarsTotal = new Counter();
  private readonly _rotationEventsTotal = new Counter();
  private readonly _errorsTotal = new Counter();
  private readonly _traceTotal = new Counter();

  // Histograms
  private readonly _requestDurationSeconds: Histogram;

  // Gauges
  private readonly _activeModels = new Gauge();
  private readonly _standbyModels = new Gauge();

  constructor(config?: PrometheusObservabilityConfig) {
    this._prefix = config?.prefix ?? 'modelmesh';
    this._includeModelLabels = config?.includeModelLabels ?? true;
    this._includeProviderLabels = config?.includeProviderLabels ?? true;
    this._requestDurationSeconds = new Histogram(
      config?.histogramBuckets ?? [...DEFAULT_BUCKETS]
    );
  }

  // -- Label helpers -------------------------------------------------------

  private _baseLabels(opts?: {
    model?: string;
    provider?: string;
    pool?: string;
  }): Record<string, string> {
    const labels: Record<string, string> = {};
    if (opts?.model && this._includeModelLabels) {
      labels.model = opts.model;
    }
    if (opts?.provider && this._includeProviderLabels) {
      labels.provider = opts.provider;
    }
    if (opts?.pool) {
      labels.pool = opts.pool;
    }
    return labels;
  }

  // -- ObservabilityConnector implementation --------------------------------

  /** Count trace entries by severity. */
  trace(entry: TraceEntry): void {
    this._traceTotal.inc({ severity: entry.severity });
  }

  /** Process routing events: count rotations, update model gauges. */
  emit(event: RoutingEvent): void {
    if (event.eventType === EventType.MODEL_ROTATED) {
      const labels = this._baseLabels({ pool: event.poolId });
      this._rotationEventsTotal.inc(labels);
    }

    // Update active/standby gauges from event metadata when provided.
    if (event.metadata) {
      const pool = event.poolId ?? '';
      if (event.metadata.active_count !== undefined) {
        this._activeModels.set(
          { pool },
          Number(event.metadata.active_count)
        );
      }
      if (event.metadata.standby_count !== undefined) {
        this._standbyModels.set(
          { pool },
          Number(event.metadata.standby_count)
        );
      }
    }
  }

  /** Update request counters, token counters, and duration histogram. */
  log(entry: RequestLogEntry): void {
    const status = entry.error == null ? 'success' : 'error';
    const labels = this._baseLabels({
      model: entry.modelId,
      provider: entry.providerId,
    });

    // requests_total
    this._requestsTotal.inc({ ...labels, status });

    // tokens_total
    if (entry.tokensIn > 0) {
      this._tokensTotal.inc(
        { ...labels, direction: 'input' },
        entry.tokensIn
      );
    }
    if (entry.tokensOut > 0) {
      this._tokensTotal.inc(
        { ...labels, direction: 'output' },
        entry.tokensOut
      );
    }

    // cost_dollars_total
    if (entry.cost != null && entry.cost > 0) {
      this._costDollarsTotal.inc(labels, entry.cost);
    }

    // request_duration_seconds
    this._requestDurationSeconds.observe(labels, entry.latencyMs / 1000.0);

    // errors_total
    if (entry.error != null) {
      const errorType = entry.error.split(':')[0] || 'unknown';
      this._errorsTotal.inc({ ...labels, error_type: errorType });
    }
  }

  /** Update metrics from aggregate statistics. */
  flush(stats: Record<string, AggregateStats>): void {
    for (const [key, agg] of Object.entries(stats)) {
      const labels = { source: key };

      this._requestsTotal.inc(
        { ...labels, status: 'success' },
        agg.requestsSuccess
      );
      this._requestsTotal.inc(
        { ...labels, status: 'error' },
        agg.requestsFailed
      );
      this._tokensTotal.inc(
        { ...labels, direction: 'input' },
        agg.tokensIn
      );
      this._tokensTotal.inc(
        { ...labels, direction: 'output' },
        agg.tokensOut
      );
      if (agg.costTotal > 0) {
        this._costDollarsTotal.inc(labels, agg.costTotal);
      }
      if (agg.rotationEvents > 0) {
        this._rotationEventsTotal.inc(labels, agg.rotationEvents);
      }
    }
  }

  // -- Rendering -----------------------------------------------------------

  /**
   * Render all metrics in Prometheus text exposition format.
   *
   * @returns A string suitable for serving at `/metrics` with
   *   content type `text/plain; version=0.0.4; charset=utf-8`.
   */
  getMetrics(): string {
    const p = this._prefix;
    const sections: string[][] = [];

    sections.push(
      renderCounter(
        `${p}_requests_total`,
        'Total number of requests processed.',
        this._requestsTotal
      )
    );
    sections.push(
      renderCounter(
        `${p}_tokens_total`,
        'Total tokens processed.',
        this._tokensTotal
      )
    );
    sections.push(
      renderCounter(
        `${p}_cost_dollars_total`,
        'Total cost in US dollars.',
        this._costDollarsTotal
      )
    );
    sections.push(
      renderHistogram(
        `${p}_request_duration_seconds`,
        'Request duration in seconds.',
        this._requestDurationSeconds
      )
    );
    sections.push(
      renderGauge(
        `${p}_active_models`,
        'Number of active models per pool.',
        this._activeModels
      )
    );
    sections.push(
      renderGauge(
        `${p}_standby_models`,
        'Number of standby models per pool.',
        this._standbyModels
      )
    );
    sections.push(
      renderCounter(
        `${p}_rotation_events_total`,
        'Total model rotation events.',
        this._rotationEventsTotal
      )
    );
    sections.push(
      renderCounter(
        `${p}_errors_total`,
        'Total errors by type.',
        this._errorsTotal
      )
    );
    sections.push(
      renderCounter(
        `${p}_traces_total`,
        'Total trace entries by severity.',
        this._traceTotal
      )
    );

    // Join non-empty sections separated by blank lines.
    const outputParts: string[] = [];
    for (const section of sections) {
      if (section.length > 0) {
        outputParts.push(section.join('\n'));
      }
    }

    return outputParts.length > 0 ? outputParts.join('\n\n') + '\n' : '';
  }
}
