/**
 * OpenTelemetry distributed tracing middleware for ModelMesh.
 *
 * Creates spans for each request with model, provider, pool, and usage
 * attributes. Propagates trace context through headers for end-to-end
 * distributed tracing across services.
 *
 * Requires the `@opentelemetry/api` package as an optional peer
 * dependency. If not installed, the middleware acts as a silent no-op.
 *
 * @example
 * ```ts
 * import { OpenTelemetryMiddleware } from '@modelmesh/core/middleware/opentelemetry';
 *
 * const client = create('chat-completion', {
 *   middleware: [new OpenTelemetryMiddleware()],
 * });
 *
 * // Custom tracer name
 * const client2 = create('chat-completion', {
 *   middleware: [new OpenTelemetryMiddleware({ tracerName: 'my-service' })],
 * });
 * ```
 */

import type { CompletionRequest, CompletionResponse } from '../interfaces/provider';
import { Middleware } from '../middleware';
import type { MiddlewareContext } from '../middleware';

// ---------------------------------------------------------------------------
// Optional OpenTelemetry imports -- graceful degradation
// ---------------------------------------------------------------------------

/** Minimal type stubs for the OpenTelemetry API surface we use. */
interface OtelSpan {
  setAttribute(key: string, value: string | number | boolean): void;
  setStatus(status: { code: number; message?: string }): void;
  recordException(error: Error): void;
  end(): void;
  spanContext(): { traceId: string; spanId: string; traceFlags: number };
}

interface OtelTracer {
  startSpan(name: string, options?: { attributes?: Record<string, string | number | boolean> }): OtelSpan;
}

interface OtelApi {
  trace: {
    getTracer(name: string): OtelTracer;
  };
  SpanStatusCode: {
    OK: number;
    ERROR: number;
  };
}

let otelApi: OtelApi | null = null;
let otelWarned = false;

try {
  // Attempt dynamic require for Node.js environments
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const api = require('@opentelemetry/api');
  otelApi = {
    trace: api.trace,
    SpanStatusCode: api.SpanStatusCode,
  };
} catch {
  // @opentelemetry/api not installed -- will act as no-op
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Configuration options for {@link OpenTelemetryMiddleware}. */
export interface OpenTelemetryMiddlewareOptions {
  /**
   * Name for the OpenTelemetry tracer.
   * @default "modelmesh"
   */
  tracerName?: string;

  /**
   * Whether to record exceptions as span events.
   * @default true
   */
  recordExceptions?: boolean;
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------

/**
 * Middleware that creates OpenTelemetry spans for each request.
 *
 * Each request creates a span with the following attributes:
 *
 * - `modelmesh.model` -- The model ID selected by routing.
 * - `modelmesh.provider` -- The provider connector ID.
 * - `modelmesh.pool` -- The pool / virtual model name.
 * - `modelmesh.attempt` -- The retry attempt number (1-based).
 * - `modelmesh.tokens.prompt` -- Prompt token count (on success).
 * - `modelmesh.tokens.completion` -- Completion token count (on success).
 * - `modelmesh.tokens.total` -- Total token count (on success).
 * - `modelmesh.latency_ms` -- Request latency in milliseconds.
 *
 * On error, the span status is set to `ERROR` and the exception is
 * recorded as a span event.
 *
 * If `@opentelemetry/api` is not installed, a warning is logged once
 * and the middleware becomes a transparent no-op.
 */
export class OpenTelemetryMiddleware extends Middleware {
  private readonly _tracer: OtelTracer | null;
  private readonly _recordExceptions: boolean;

  constructor(options?: OpenTelemetryMiddlewareOptions) {
    super();
    this._recordExceptions = options?.recordExceptions ?? true;

    if (otelApi) {
      this._tracer = otelApi.trace.getTracer(options?.tracerName ?? 'modelmesh');
    } else {
      this._tracer = null;
      if (!otelWarned) {
        otelWarned = true;
        if (typeof console !== 'undefined') {
          console.warn(
            '[ModelMesh] @opentelemetry/api is not installed. ' +
              'OpenTelemetryMiddleware will operate as a no-op. ' +
              'Install with: npm install @opentelemetry/api'
          );
        }
      }
    }
  }

  /**
   * Start a new span for the request.
   *
   * The span is stored in `context.metadata` so that
   * {@link afterResponse} and {@link onError} can finish it.
   */
  async beforeRequest(
    request: CompletionRequest,
    context: MiddlewareContext
  ): Promise<CompletionRequest> {
    if (!this._tracer) {
      return request;
    }

    const span = this._tracer.startSpan(`modelmesh.request ${context.poolName}`, {
      attributes: {
        'modelmesh.model': context.modelId,
        'modelmesh.provider': context.providerId,
        'modelmesh.pool': context.poolName,
        'modelmesh.attempt': context.attempt,
      },
    });

    // Store span and timing in context metadata for later hooks
    context.metadata['_otelSpan'] = span;
    context.metadata['_otelStartTime'] = performance.now();

    // Propagate trace context: store trace/span IDs in metadata
    const spanContext = span.spanContext();
    if (spanContext && spanContext.traceFlags !== 0) {
      context.metadata['traceId'] = spanContext.traceId;
      context.metadata['spanId'] = spanContext.spanId;
    }

    return request;
  }

  /**
   * Record usage attributes and close the span on success.
   */
  async afterResponse(
    response: CompletionResponse,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    const span = context.metadata['_otelSpan'] as OtelSpan | undefined;
    if (!span || !otelApi) {
      return response;
    }

    const startTime = context.metadata['_otelStartTime'] as number | undefined;
    if (startTime !== undefined) {
      const latencyMs = performance.now() - startTime;
      span.setAttribute('modelmesh.latency_ms', Math.round(latencyMs * 100) / 100);
    }

    if (response.usage) {
      span.setAttribute('modelmesh.tokens.prompt', response.usage.promptTokens);
      span.setAttribute('modelmesh.tokens.completion', response.usage.completionTokens);
      span.setAttribute('modelmesh.tokens.total', response.usage.totalTokens);
    }

    span.setStatus({ code: otelApi.SpanStatusCode.OK });
    span.end();

    return response;
  }

  /**
   * Set span status to ERROR and record the exception, then re-throw.
   */
  async onError(
    error: Error,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    const span = context.metadata['_otelSpan'] as OtelSpan | undefined;
    if (span && otelApi) {
      span.setStatus({
        code: otelApi.SpanStatusCode.ERROR,
        message: error.message,
      });
      if (this._recordExceptions) {
        span.recordException(error);
      }
      span.end();
    }

    throw error;
  }
}
