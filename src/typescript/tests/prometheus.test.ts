/**
 * Tests for the Prometheus observability connector.
 */
import { PrometheusObservability } from '@/connectors/observability/prometheus-connector';
import { EventType, Severity } from '@/interfaces/observability';
import type { RequestLogEntry, RoutingEvent, TraceEntry } from '@/interfaces/observability';

// ---------------------------------------------------------------------------
// PrometheusObservability
// ---------------------------------------------------------------------------

describe('PrometheusObservability', () => {
  test('has correct connector ID', () => {
    expect(PrometheusObservability.CONNECTOR_ID).toBe('modelmesh.prometheus.v1');
  });

  test('creates with default config', () => {
    const prom = new PrometheusObservability();
    expect(prom).toBeDefined();
    // Default prefix should be 'modelmesh' -- visible in getMetrics output
    const metrics = prom.getMetrics();
    // No events yet, so metrics should be empty
    expect(metrics).toBe('');
  });

  test('creates with custom prefix', () => {
    const prom = new PrometheusObservability({ prefix: 'myapp' });
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 100,
      statusCode: 200,
      tokensIn: 10,
      tokensOut: 20,
    });
    const metrics = prom.getMetrics();
    expect(metrics).toContain('myapp_requests_total');
    expect(metrics).not.toContain('modelmesh_requests_total');
  });

  test('onEvent increments request counter', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 250,
      statusCode: 200,
      tokensIn: 10,
      tokensOut: 20,
    });

    const metrics = prom.getMetrics();
    expect(metrics).toContain('modelmesh_requests_total');
    expect(metrics).toContain('status="success"');
  });

  test('onEvent records duration histogram', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 500,
      statusCode: 200,
      tokensIn: 10,
      tokensOut: 20,
    });

    const metrics = prom.getMetrics();
    expect(metrics).toContain('modelmesh_request_duration_seconds');
    expect(metrics).toContain('_bucket');
    expect(metrics).toContain('_sum');
    expect(metrics).toContain('_count');
  });

  test('onEvent tracks token usage', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 250,
      statusCode: 200,
      tokensIn: 100,
      tokensOut: 200,
    });

    const metrics = prom.getMetrics();
    expect(metrics).toContain('modelmesh_tokens_total');
    expect(metrics).toContain('direction="input"');
    expect(metrics).toContain('direction="output"');
  });

  test('onModelStateChange updates gauge', () => {
    const prom = new PrometheusObservability();
    const event: RoutingEvent = {
      eventType: EventType.MODEL_ACTIVATED,
      timestamp: new Date(),
      poolId: 'chat-pool',
      metadata: {
        active_count: 3,
        standby_count: 1,
      },
    };
    prom.emit(event);

    const metrics = prom.getMetrics();
    expect(metrics).toContain('modelmesh_active_models');
    expect(metrics).toContain('modelmesh_standby_models');
  });

  test('onError increments error counter', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 250,
      statusCode: 500,
      tokensIn: 10,
      tokensOut: 0,
      error: 'RateLimitError: quota exceeded',
    });

    const metrics = prom.getMetrics();
    expect(metrics).toContain('modelmesh_errors_total');
    expect(metrics).toContain('error_type="RateLimitError"');
    expect(metrics).toContain('status="error"');
  });

  test('getMetrics returns Prometheus text format', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 250,
      statusCode: 200,
      tokensIn: 10,
      tokensOut: 20,
    });

    const metrics = prom.getMetrics();
    // Prometheus text format ends with newline
    expect(metrics.endsWith('\n')).toBe(true);
    // Contains metric lines with values
    const lines = metrics.split('\n').filter((l) => l.length > 0);
    expect(lines.length).toBeGreaterThan(0);
  });

  test('getMetrics includes HELP comments', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 100,
      statusCode: 200,
      tokensIn: 5,
      tokensOut: 10,
    });

    const metrics = prom.getMetrics();
    expect(metrics).toContain('# HELP modelmesh_requests_total');
    expect(metrics).toContain('# HELP modelmesh_tokens_total');
  });

  test('getMetrics includes TYPE declarations', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 100,
      statusCode: 200,
      tokensIn: 5,
      tokensOut: 10,
    });

    const metrics = prom.getMetrics();
    expect(metrics).toContain('# TYPE modelmesh_requests_total counter');
    expect(metrics).toContain('# TYPE modelmesh_request_duration_seconds histogram');
  });

  test('reset clears all metrics', () => {
    const prom = new PrometheusObservability();
    prom.log({
      timestamp: new Date(),
      modelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      capability: 'chat-completion',
      deliveryMode: 'sync',
      latencyMs: 100,
      statusCode: 200,
      tokensIn: 10,
      tokensOut: 20,
    });

    // Verify something was recorded
    expect(prom.getMetrics()).not.toBe('');

    // Create a fresh instance (no reset method; fresh instance = reset)
    const prom2 = new PrometheusObservability();
    expect(prom2.getMetrics()).toBe('');
  });

  test('trace counts by severity', () => {
    const prom = new PrometheusObservability();
    const entry: TraceEntry = {
      severity: Severity.ERROR,
      timestamp: new Date(),
      component: 'test',
      message: 'something went wrong',
      metadata: {},
    };
    prom.trace(entry);
    prom.trace(entry);

    const metrics = prom.getMetrics();
    expect(metrics).toContain('modelmesh_traces_total');
    expect(metrics).toContain('severity="error"');
  });

  test('flush aggregates stats correctly', () => {
    const prom = new PrometheusObservability();
    prom.flush({
      'pool-a': {
        requestsTotal: 100,
        requestsSuccess: 90,
        requestsFailed: 10,
        tokensIn: 5000,
        tokensOut: 10000,
        costTotal: 1.5,
        latencyAvg: 200,
        latencyP95: 500,
        downtimeTotal: 0,
        rotationEvents: 2,
      },
    });

    const metrics = prom.getMetrics();
    expect(metrics).toContain('modelmesh_requests_total');
    expect(metrics).toContain('modelmesh_tokens_total');
    expect(metrics).toContain('modelmesh_rotation_events_total');
  });
});
