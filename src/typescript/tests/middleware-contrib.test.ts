/**
 * Tests for contributed middleware: CorrelationId, OpenTelemetry.
 */
import { CorrelationIdMiddleware } from '@/middleware/correlation';
import { OpenTelemetryMiddleware } from '@/middleware/opentelemetry';
import { createMiddlewareContext } from '@/middleware';
import type { MiddlewareContext } from '@/middleware';
import type { CompletionRequest, CompletionResponse } from '@/interfaces/provider';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRequest(): CompletionRequest {
  return {
    model: 'test-pool',
    messages: [{ role: 'user', content: 'Hello' }],
    temperature: 1.0,
    stream: false,
    topP: 1.0,
  };
}

function makeContext(overrides?: Partial<MiddlewareContext>): MiddlewareContext {
  return createMiddlewareContext({
    modelId: 'gpt-4o',
    providerId: 'openai.llm.v1',
    poolName: 'chat-completion',
    attempt: 1,
    ...overrides,
  });
}

function makeResponse(): CompletionResponse {
  return {
    id: 'test-resp-1',
    model: 'gpt-4o',
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: 'Hi there!' },
        finishReason: 'stop',
      },
    ],
    usage: {
      promptTokens: 5,
      completionTokens: 3,
      totalTokens: 8,
    },
    created: Math.floor(Date.now() / 1000),
    object: 'chat.completion',
  };
}

// ---------------------------------------------------------------------------
// CorrelationIdMiddleware
// ---------------------------------------------------------------------------

describe('CorrelationIdMiddleware', () => {
  test('generates unique correlation IDs', async () => {
    const mw = new CorrelationIdMiddleware();
    // Suppress debug output
    jest.spyOn(console, 'debug').mockImplementation();

    const ctx1 = makeContext();
    const ctx2 = makeContext();

    await mw.beforeRequest(makeRequest(), ctx1);
    await mw.beforeRequest(makeRequest(), ctx2);

    const id1 = ctx1.metadata['correlationId'] as string;
    const id2 = ctx2.metadata['correlationId'] as string;

    expect(id1).toBeDefined();
    expect(id2).toBeDefined();
    expect(id1).not.toBe(id2);
    expect(typeof id1).toBe('string');
    expect(id1.length).toBeGreaterThan(0);

    (console.debug as jest.Mock).mockRestore();
  });

  test('preserves existing correlation ID', async () => {
    const mw = new CorrelationIdMiddleware();
    jest.spyOn(console, 'debug').mockImplementation();

    const ctx = makeContext();
    ctx.metadata['correlationId'] = 'existing-id-123';

    await mw.beforeRequest(makeRequest(), ctx);

    expect(ctx.metadata['correlationId']).toBe('existing-id-123');

    (console.debug as jest.Mock).mockRestore();
  });

  test('uses custom ID generator', async () => {
    let counter = 0;
    const mw = new CorrelationIdMiddleware({
      idGenerator: () => `custom-${++counter}`,
    });
    jest.spyOn(console, 'debug').mockImplementation();

    const ctx = makeContext();
    await mw.beforeRequest(makeRequest(), ctx);

    expect(ctx.metadata['correlationId']).toBe('custom-1');

    (console.debug as jest.Mock).mockRestore();
  });

  test('uses custom header name', async () => {
    const mw = new CorrelationIdMiddleware({
      headerName: 'X-Request-ID',
    });
    jest.spyOn(console, 'debug').mockImplementation();

    const ctx = makeContext();
    await mw.beforeRequest(makeRequest(), ctx);

    expect(ctx.metadata['correlationHeader']).toBe('X-Request-ID');

    (console.debug as jest.Mock).mockRestore();
  });

  test('handles errors without losing correlation ID', async () => {
    const mw = new CorrelationIdMiddleware();
    jest.spyOn(console, 'debug').mockImplementation();
    jest.spyOn(console, 'warn').mockImplementation();

    const ctx = makeContext();
    await mw.beforeRequest(makeRequest(), ctx);
    const correlationId = ctx.metadata['correlationId'];

    const testError = new Error('test failure');
    await expect(mw.onError(testError, ctx)).rejects.toThrow('test failure');

    // Correlation ID should still be intact after error
    expect(ctx.metadata['correlationId']).toBe(correlationId);

    (console.debug as jest.Mock).mockRestore();
    (console.warn as jest.Mock).mockRestore();
  });

  test('afterResponse passes through response', async () => {
    const mw = new CorrelationIdMiddleware();
    jest.spyOn(console, 'debug').mockImplementation();

    const ctx = makeContext();
    ctx.metadata['correlationId'] = 'test-id';
    const response = makeResponse();
    const result = await mw.afterResponse(response, ctx);

    expect(result).toBe(response);

    (console.debug as jest.Mock).mockRestore();
  });
});

// ---------------------------------------------------------------------------
// OpenTelemetryMiddleware
// ---------------------------------------------------------------------------

describe('OpenTelemetryMiddleware', () => {
  test('acts as no-op when otel not installed', async () => {
    // @opentelemetry/api is not installed in this project, so the
    // middleware should act as a transparent no-op.
    jest.spyOn(console, 'warn').mockImplementation();

    const mw = new OpenTelemetryMiddleware();
    const ctx = makeContext();
    const request = makeRequest();

    // beforeRequest should return the request unchanged
    const result = await mw.beforeRequest(request, ctx);
    expect(result).toBe(request);

    // No span should be stored in context
    expect(ctx.metadata['_otelSpan']).toBeUndefined();

    (console.warn as jest.Mock).mockRestore();
  });

  test('before_request populates context metadata', async () => {
    // Without otel installed, metadata should remain untouched
    jest.spyOn(console, 'warn').mockImplementation();

    const mw = new OpenTelemetryMiddleware();
    const ctx = makeContext();

    await mw.beforeRequest(makeRequest(), ctx);

    // Since otel is not installed, _otelSpan should not be set
    expect(ctx.metadata['_otelSpan']).toBeUndefined();
    // The middleware context already has modelId, providerId etc. from creation
    expect(ctx.modelId).toBe('gpt-4o');
    expect(ctx.providerId).toBe('openai.llm.v1');

    (console.warn as jest.Mock).mockRestore();
  });

  test('after_response completes without error', async () => {
    jest.spyOn(console, 'warn').mockImplementation();

    const mw = new OpenTelemetryMiddleware();
    const ctx = makeContext();
    const response = makeResponse();

    // Should pass through the response when otel not available
    const result = await mw.afterResponse(response, ctx);
    expect(result).toBe(response);

    (console.warn as jest.Mock).mockRestore();
  });

  test('on_error re-raises original error', async () => {
    jest.spyOn(console, 'warn').mockImplementation();

    const mw = new OpenTelemetryMiddleware();
    const ctx = makeContext();
    const err = new Error('provider timeout');

    await expect(mw.onError(err, ctx)).rejects.toThrow('provider timeout');

    (console.warn as jest.Mock).mockRestore();
  });

  test('constructor accepts options', () => {
    jest.spyOn(console, 'warn').mockImplementation();

    const mw = new OpenTelemetryMiddleware({
      tracerName: 'my-service',
      recordExceptions: false,
    });
    expect(mw).toBeDefined();

    (console.warn as jest.Mock).mockRestore();
  });
});
