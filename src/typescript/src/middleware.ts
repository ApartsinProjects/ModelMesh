/**
 * Request/response middleware for ModelMesh.
 *
 * Provides an interception layer around provider calls so that users can
 * add logging, request transforms, response enrichment, caching, or
 * custom error handling without modifying library internals.
 *
 * @example
 * ```ts
 * import { Middleware, create } from '@modelmesh/core';
 *
 * class LoggingMiddleware extends Middleware {
 *   async beforeRequest(request, context) {
 *     console.log(`Routing to ${context.modelId}`);
 *     return request;
 *   }
 *   async afterResponse(response, context) {
 *     console.log(`Tokens: ${response.usage?.totalTokens}`);
 *     return response;
 *   }
 * }
 *
 * const client = create('chat', { middleware: [new LoggingMiddleware()] });
 * ```
 */

import type { CompletionRequest, CompletionResponse } from './interfaces/provider';

/**
 * Context passed to middleware hooks for each request.
 *
 * Provides metadata about the current routing decision so
 * middleware can make context-aware decisions.
 */
export interface MiddlewareContext {
  /** The real model identifier selected for this attempt. */
  modelId: string;
  /** Connector ID of the provider being used. */
  providerId: string;
  /** The virtual model / pool name from the request. */
  poolName: string;
  /** Current retry attempt number (1-based). */
  attempt: number;
  /** Unix timestamp (seconds since epoch) when the request was initiated. */
  timestamp: number;
  /** Arbitrary key-value metadata for middleware chaining. */
  metadata: Record<string, unknown>;
}

/**
 * Create a MiddlewareContext with sensible defaults.
 *
 * Auto-populates `timestamp` (current time) and `metadata` (empty object)
 * if not provided, matching the Python dataclass behavior.
 */
export function createMiddlewareContext(
  overrides: Omit<MiddlewareContext, 'timestamp' | 'metadata'> &
    Partial<Pick<MiddlewareContext, 'timestamp' | 'metadata'>>
): MiddlewareContext {
  return {
    timestamp: Date.now() / 1000,
    metadata: {},
    ...overrides,
  };
}

/**
 * Base class for request/response middleware.
 *
 * Subclass and override any of the three hooks. All hooks have
 * default no-op implementations, so you only override what you need.
 */
export class Middleware {
  /**
   * Called before the request is sent to the provider.
   *
   * Override to inspect or transform the request. Return the
   * (possibly modified) request to proceed.
   */
  async beforeRequest(
    request: CompletionRequest,
    context: MiddlewareContext
  ): Promise<CompletionRequest> {
    return request;
  }

  /**
   * Called after a successful provider response.
   *
   * Override to inspect, log, or enrich the response. Return the
   * (possibly modified) response.
   */
  async afterResponse(
    response: CompletionResponse,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    return response;
  }

  /**
   * Called when the provider raises an error.
   *
   * Override to handle errors, return a fallback response, or
   * re-throw (possibly with wrapping). The default implementation
   * re-throws the original error.
   */
  async onError(
    error: Error,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    throw error;
  }
}

/**
 * Ordered collection of middleware that executes as a pipeline.
 *
 * `beforeRequest` hooks run in order (first registered = first called).
 * `afterResponse` hooks run in reverse order (onion model).
 * `onError` hooks run in order until one returns a response.
 */
export class MiddlewareStack {
  private _middlewares: Middleware[];

  constructor(middlewares?: Middleware[]) {
    this._middlewares = [...(middlewares ?? [])];
  }

  /** Append a middleware to the stack. */
  add(middleware: Middleware): void {
    this._middlewares.push(middleware);
  }

  /** Return the list of registered middleware instances. */
  get middlewares(): Middleware[] {
    return [...this._middlewares];
  }

  get length(): number {
    return this._middlewares.length;
  }

  /**
   * Run all `beforeRequest` hooks in order.
   *
   * Each middleware receives the request returned by the previous
   * one, enabling request transformation chains.
   */
  async runBeforeRequest(
    request: CompletionRequest,
    context: MiddlewareContext
  ): Promise<CompletionRequest> {
    let current = request;
    for (const mw of this._middlewares) {
      current = await mw.beforeRequest(current, context);
    }
    return current;
  }

  /**
   * Run all `afterResponse` hooks in reverse order (onion model).
   */
  async runAfterResponse(
    response: CompletionResponse,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    let current = response;
    for (let i = this._middlewares.length - 1; i >= 0; i--) {
      current = await this._middlewares[i].afterResponse(current, context);
    }
    return current;
  }

  /**
   * Run `onError` hooks until one returns a fallback response.
   *
   * If no middleware handles the error, the original error is re-thrown.
   */
  async runOnError(
    error: Error,
    context: MiddlewareContext
  ): Promise<CompletionResponse> {
    for (const mw of this._middlewares) {
      try {
        return await mw.onError(error, context);
      } catch {
        // This middleware didn't handle it; try next
        continue;
      }
    }
    throw error;
  }
}
