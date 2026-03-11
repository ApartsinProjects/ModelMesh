/**
 * Request Correlation ID middleware for ModelMesh.
 *
 * Automatically assigns a unique correlation ID to each request for
 * end-to-end tracing across services. The ID is stored in middleware
 * context metadata and propagated as an `X-Correlation-ID` header to
 * provider requests.
 *
 * @example
 * ```ts
 * import { CorrelationIdMiddleware } from '@modelmesh/core/middleware/correlation';
 *
 * const client = create('chat-completion', {
 *   middleware: [new CorrelationIdMiddleware()],
 * });
 *
 * // Custom ID generator
 * const client2 = create('chat-completion', {
 *   middleware: [new CorrelationIdMiddleware({ idGenerator: () => nanoid() })],
 * });
 * ```
 */

import type { CompletionRequest, CompletionResponse } from '../interfaces/provider';
import { Middleware } from '../middleware';
import type { MiddlewareContext } from '../middleware';

/**
 * Configuration options for {@link CorrelationIdMiddleware}.
 */
export interface CorrelationIdMiddlewareOptions {
  /**
   * Custom function to generate correlation IDs.
   * Defaults to a random hex string derived from `crypto.randomUUID()`
   * (or a fallback `Math.random()`-based generator).
   */
  idGenerator?: () => string;

  /**
   * HTTP header name used for propagation.
   * @default "X-Correlation-ID"
   */
  headerName?: string;
}

/**
 * Generate a default correlation ID.
 *
 * Uses `crypto.randomUUID()` when available (Node 19+, modern browsers),
 * falling back to a `Math.random()`-based hex string.
 */
function defaultIdGenerator(): string {
  if (typeof globalThis.crypto !== 'undefined' && typeof globalThis.crypto.randomUUID === 'function') {
    return globalThis.crypto.randomUUID().replace(/-/g, '');
  }
  // Fallback for older runtimes
  return Array.from({ length: 32 }, () =>
    Math.floor(Math.random() * 16).toString(16)
  ).join('');
}

/**
 * Middleware that assigns and propagates a correlation ID per request.
 *
 * Each request receives a unique correlation ID. The ID is stored in
 * `context.metadata.correlationId` so that downstream middleware and
 * application code can access it. The ID is also intended for injection
 * as an `X-Correlation-ID` header into provider requests for distributed
 * tracing.
 *
 * If the context already contains a `correlationId` in its metadata
 * (e.g. set by an upstream service), it is preserved rather than
 * overwritten.
 */
export class CorrelationIdMiddleware extends Middleware {
  private readonly _idGenerator: () => string;
  private readonly _headerName: string;

  constructor(options?: CorrelationIdMiddlewareOptions) {
    super();
    this._idGenerator = options?.idGenerator ?? defaultIdGenerator;
    this._headerName = options?.headerName ?? 'X-Correlation-ID';
  }

  /**
   * Assign a correlation ID and log the outgoing request.
   *
   * If `context.metadata` does not already contain a `correlationId`,
   * one is generated using the configured ID generator.
   */
  async beforeRequest(
    request: CompletionRequest,
    context: MiddlewareContext
  ): Promise<CompletionRequest> {
    if (!context.metadata['correlationId']) {
      context.metadata['correlationId'] = this._idGenerator();
    }

    // Store the header name for potential downstream use
    context.metadata['correlationHeader'] = this._headerName;

    const correlationId = context.metadata['correlationId'] as string;

    if (typeof console !== 'undefined') {
      console.debug(
        `[CorrelationId] Request [${correlationId}] model=${context.modelId} ` +
          `provider=${context.providerId} pool=${context.poolName} attempt=${context.attempt}`
      );
    }

    return request;
  }

  /**
   * Log the response with the correlation ID.
   */
  async afterResponse(
    response: CompletionResponse,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    const correlationId = (context.metadata['correlationId'] as string) ?? 'unknown';

    if (typeof console !== 'undefined') {
      console.debug(
        `[CorrelationId] Response [${correlationId}] model=${response.model} ` +
          `tokens=${response.usage?.totalTokens ?? 0}`
      );
    }

    return response;
  }

  /**
   * Log the error with the correlation ID, then re-throw.
   */
  async onError(
    error: Error,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    const correlationId = (context.metadata['correlationId'] as string) ?? 'unknown';

    if (typeof console !== 'undefined') {
      console.warn(
        `[CorrelationId] Error [${correlationId}] model=${context.modelId} ` +
          `provider=${context.providerId}: ${error.message}`
      );
    }

    throw error;
  }
}
