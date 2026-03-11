/**
 * Testing utilities for ModelMesh.
 *
 * Provides a mock client that behaves like the real MeshClient but
 * returns pre-configured responses instead of calling live APIs.
 *
 * @example
 * ```ts
 * import { mockClient, MockResponse } from '@modelmesh/core/testing';
 *
 * const client = mockClient({
 *   responses: [
 *     { content: 'Hello!', model: 'gpt-4o', tokens: 10 },
 *     { content: 'World!', model: 'claude-3', tokens: 15 },
 *   ],
 * });
 *
 * const resp = await client.chat.completions.create({
 *   model: 'test-pool',
 *   messages: [{ role: 'user', content: 'Hi' }],
 * });
 * assert(resp.choices[0].message.content === 'Hello!');
 * assert(client.calls.length === 1);
 * ```
 */

import type { CompletionResponse } from './interfaces/provider';

/** Pre-configured response for the mock client. */
export interface MockResponse {
  /** The text content of the assistant's reply. */
  content?: string;
  /** Model identifier to include in the response. */
  model?: string;
  /** Total token count to simulate. */
  tokens?: number;
  /** Prompt token count (defaults to tokens / 3). */
  promptTokens?: number;
  /** Completion token count (auto-calculated). */
  completionTokens?: number;
  /** Stop reason (default: "stop"). */
  finishReason?: string;
  /**
   * When set, this error is thrown instead of returning a response.
   * Useful for simulating provider failures.
   */
  error?: Error;
  /**
   * Seconds to wait before returning or throwing, simulating
   * network latency. Uses `setTimeout` internally.
   */
  delay?: number;
  /**
   * HTTP status code to simulate (informational only).
   * @default 200
   */
  statusCode?: number;
}

/** Record of a call made to the mock client. */
export interface MockCall {
  /** The model / pool name requested. */
  model: string;
  /** The messages sent. */
  messages: Record<string, unknown>[];
  /** Additional parameters. */
  kwargs: Record<string, unknown>;
  /** The response that was returned. */
  response: CompletionResponse;
}

function toCompletionResponse(mock: MockResponse): CompletionResponse {
  const tokens = mock.tokens ?? 10;
  const promptTokens = mock.promptTokens ?? Math.floor(tokens / 3);
  const completionTokens = mock.completionTokens ?? (tokens - promptTokens);
  return {
    id: `mock-${Math.random().toString(36).slice(2, 10)}`,
    model: mock.model ?? 'mock-model',
    choices: [
      {
        index: 0,
        message: {
          role: 'assistant',
          content: mock.content ?? 'Mock response',
        },
        finishReason: mock.finishReason ?? 'stop',
      },
    ],
    usage: {
      promptTokens,
      completionTokens,
      totalTokens: promptTokens + completionTokens,
    },
    created: Math.floor(Date.now() / 1000),
    object: 'chat.completion',
  };
}

class MockChatCompletions {
  private _responses: MockResponse[];
  private _calls: MockCall[];
  private _index = 0;
  private _failureRate: number;

  constructor(responses: MockResponse[], calls: MockCall[], failureRate = 0) {
    this._responses = responses;
    this._calls = calls;
    this._failureRate = failureRate;
  }

  async create(params: {
    model: string;
    messages?: Record<string, unknown>[];
    stream?: boolean;
    [key: string]: unknown;
  }): Promise<CompletionResponse> {
    const messages = params.messages ?? [];
    const mock =
      this._index < this._responses.length
        ? this._responses[this._index++]
        : this._responses[this._responses.length - 1] ?? {};

    // Apply per-response delay
    if (mock.delay && mock.delay > 0) {
      await new Promise((resolve) => setTimeout(resolve, mock.delay! * 1000));
    }

    // Apply global random failure rate (chaos testing)
    if (this._failureRate > 0 && Math.random() < this._failureRate) {
      throw new Error('Simulated random failure (chaos testing)');
    }

    // Apply per-response error injection
    if (mock.error) {
      throw mock.error;
    }

    const response = toCompletionResponse(mock);
    const { model, messages: _msgs, stream: _s, ...kwargs } = params;
    this._calls.push({ model, messages, kwargs, response });
    return response;
  }
}

class MockChatNamespace {
  readonly completions: MockChatCompletions;

  constructor(responses: MockResponse[], calls: MockCall[], failureRate = 0) {
    this.completions = new MockChatCompletions(responses, calls, failureRate);
  }
}

class MockModelsNamespace {
  list() {
    return { data: [], object: 'list' };
  }
}

/**
 * A mock MeshClient for testing.
 *
 * Behaves like the real MeshClient but returns pre-configured
 * responses. Records all calls for assertion.
 */
export class MockClient {
  /** List of recorded calls. */
  readonly calls: MockCall[] = [];
  readonly chat: MockChatNamespace;
  readonly models: MockModelsNamespace;

  constructor(responses?: MockResponse[], failureRate = 0) {
    const resps = responses ?? [{}];
    this.chat = new MockChatNamespace(resps, this.calls, failureRate);
    this.models = new MockModelsNamespace();
  }

  /** Close the mock client (no-op, for API parity with real MeshClient). */
  close(): void {
    // No-op — nothing to clean up in the mock client.
  }

  poolStatus(pool?: string | null): Record<string, unknown> {
    return {
      'mock-pool': {
        active: 1,
        standby: 0,
        total: 1,
        currentModel: 'mock-model',
      },
    };
  }

  activeProviders(): string[] {
    return ['mock-provider'];
  }

  describe(pool?: string | null): string {
    return 'Pool "mock-pool" (strategy: mock)\n  -> mock-model [mock-provider] (active)';
  }

  explain(params?: { model?: string; [key: string]: unknown }): Record<string, unknown> {
    return {
      poolName: 'mock-pool',
      strategy: 'mock',
      capability: 'mock',
      selectedModel: 'mock-model',
      candidates: [
        { modelId: 'mock-model', providerId: 'mock-provider', status: 'active' },
      ],
      reason: 'Mock selection',
    };
  }
}

/**
 * Create a mock MeshClient for testing.
 *
 * @param options - Configuration for the mock client.
 * @param options.responses - Pre-configured responses to cycle through.
 *   Individual responses can specify `error`, `delay`, or `statusCode`
 *   for per-request behavior simulation.
 * @param options.failureRate - Probability (0.0 to 1.0) that any request
 *   randomly throws an Error for chaos testing. Applied before
 *   per-response error checks.
 * @returns A MockClient that can be used in place of a real MeshClient.
 *
 * @example
 * ```ts
 * // Simulate errors
 * const client = mockClient({
 *   responses: [
 *     { content: 'OK' },
 *     { error: new Error('Rate limited') },
 *     { content: 'Recovered' },
 *   ],
 * });
 *
 * // Chaos testing (20% random failures)
 * const client2 = mockClient({
 *   responses: [{ content: 'Response' }],
 *   failureRate: 0.2,
 * });
 * ```
 */
export function mockClient(options?: {
  responses?: MockResponse[];
  failureRate?: number;
}): MockClient {
  return new MockClient(options?.responses, options?.failureRate);
}
