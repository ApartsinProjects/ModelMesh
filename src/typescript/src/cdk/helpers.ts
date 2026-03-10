/**
 * CDK testing helpers.
 *
 * Provides factory functions and test doubles for writing connector unit
 * tests without real HTTP traffic or live AI providers.
 */

import {
  ChatMessage,
  CompletionChoice,
  CompletionRequest,
  CompletionResponse,
  TokenUsage,
  createDefaultCompletionRequest,
  createDefaultCompletionResponse,
  createDefaultTokenUsage,
} from '../interfaces/provider';
import {
  ModelState,
  ModelStatus,
  createDefaultModelState,
} from '../interfaces/rotation';

// ---------------------------------------------------------------------------
// Mock factories
// ---------------------------------------------------------------------------

/**
 * Create a minimal CompletionRequest for testing.
 *
 * @param overrides - Fields to override from the defaults.
 * @returns A ready-to-use CompletionRequest.
 *
 * @example
 * const req = mockCompletionRequest();
 * const custom = mockCompletionRequest({ model: 'gpt-4o' });
 */
export function mockCompletionRequest(
  overrides?: Partial<CompletionRequest>
): CompletionRequest {
  return createDefaultCompletionRequest({
    model: 'test-model',
    messages: [{ role: 'user', content: 'Hello' }],
    ...overrides,
  });
}

/**
 * Create a ModelState snapshot for rotation policy testing.
 *
 * @param overrides - Fields to override from the defaults.
 * @returns A ModelState instance ready for use in tests.
 *
 * @example
 * const healthy = mockModelSnapshot();
 * const failing = mockModelSnapshot({ failureCount: 5, errorRate: 0.8 });
 * const standby = mockModelSnapshot({ status: ModelStatus.STANDBY });
 */
export function mockModelSnapshot(
  overrides?: Partial<ModelState>
): ModelState {
  return createDefaultModelState({
    modelId: 'test.model-a',
    providerId: 'test.v1',
    ...overrides,
  });
}

// ---------------------------------------------------------------------------
// MockHttpClient
// ---------------------------------------------------------------------------

export interface MockHttpResponse {
  statusCode: number;
  headers: Record<string, string>;
  body: string;
}

function createDefaultMockResponse(
  overrides?: Partial<MockHttpResponse>
): MockHttpResponse {
  return {
    statusCode: 200,
    headers: {},
    body: '{}',
    ...overrides,
  };
}

export interface HttpCall {
  method: string;
  url: string;
  headers?: Record<string, string>;
  json?: unknown;
}

/**
 * HTTP client double that records calls and returns canned responses.
 *
 * @example
 * const client = new MockHttpClient();
 * client.addResponse({ statusCode: 200, body: '{"ok":true}' });
 * const response = await client.post('https://api.example.com/v1/chat');
 */
export class MockHttpClient {
  private _responses: MockHttpResponse[] = [];
  public calls: HttpCall[] = [];

  addResponse(response: Partial<MockHttpResponse>): void {
    this._responses.push(createDefaultMockResponse(response));
  }

  async post(
    url: string,
    options?: { headers?: Record<string, string>; json?: unknown }
  ): Promise<MockHttpResponse> {
    this.calls.push({
      method: 'POST',
      url,
      headers: options?.headers,
      json: options?.json,
    });
    if (this._responses.length > 0) {
      return this._responses.shift()!;
    }
    return createDefaultMockResponse();
  }

  async get(
    url: string,
    options?: { headers?: Record<string, string> }
  ): Promise<MockHttpResponse> {
    this.calls.push({
      method: 'GET',
      url,
      headers: options?.headers,
    });
    if (this._responses.length > 0) {
      return this._responses.shift()!;
    }
    return createDefaultMockResponse();
  }
}

// ---------------------------------------------------------------------------
// ConnectorTestHarness
// ---------------------------------------------------------------------------

export interface HarnessCall {
  method: string;
  request: CompletionRequest;
}

/**
 * Lightweight test harness for connector instances.
 *
 * Wraps a connector and provides convenience methods for exercising
 * its lifecycle without a full ModelMesh setup.
 *
 * @example
 * const harness = new ConnectorTestHarness(myProvider);
 * const response = await harness.complete(mockCompletionRequest());
 * assert(response.choices.length > 0);
 */
export class ConnectorTestHarness {
  public calls: HarnessCall[] = [];

  constructor(
    public readonly connector: {
      complete(request: CompletionRequest): Promise<CompletionResponse>;
      stream(request: CompletionRequest): AsyncIterableIterator<CompletionResponse>;
    }
  ) {}

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    this.calls.push({ method: 'complete', request });
    return this.connector.complete(request);
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionResponse> {
    this.calls.push({ method: 'stream', request });
    yield* this.connector.stream(request);
  }
}
