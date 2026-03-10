/**
 * Comprehensive tests for BrowserBaseProvider, BrowserProviderConfig,
 * and BrowserHttpError from the browser-compatible provider module.
 */
import {
  BrowserBaseProvider,
  BrowserHttpError,
  BrowserProviderConfig,
  createBrowserProviderConfig,
} from '@/cdk/browser-provider';
import type {
  CompletionRequest,
  CompletionResponse,
  ModelInfo,
} from '@/interfaces/provider';
import {
  createDefaultCompletionRequest,
  createDefaultModelInfo,
} from '@/interfaces/provider';

// ---------------------------------------------------------------------------
// Test subclass that exposes protected methods for unit testing
// ---------------------------------------------------------------------------

class TestBrowserProvider extends BrowserBaseProvider {
  public resolveUrl(url: string): string {
    return this._resolveUrl(url);
  }

  public buildHeaders(): Record<string, string> {
    return this._buildHeaders();
  }

  public buildRequestPayload(request: CompletionRequest): Record<string, any> {
    return this._buildRequestPayload(request);
  }

  public parseResponse(data: Record<string, any>): CompletionResponse {
    return this._parseResponse(data);
  }

  public parseSseChunk(line: string): CompletionResponse | null {
    return this._parseSseChunk(line);
  }

  public getCompletionEndpoint(): string {
    return this._getCompletionEndpoint();
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeModel(id: string, name?: string): ModelInfo {
  return createDefaultModelInfo({
    id,
    name: name ?? id,
    capabilities: ['generation.text-generation.chat-completion'],
  });
}

function makeRequest(overrides?: Partial<CompletionRequest>): CompletionRequest {
  return createDefaultCompletionRequest({
    model: 'test-model',
    messages: [{ role: 'user', content: 'Hello' }],
    ...overrides,
  });
}

/**
 * Build a minimal OpenAI-format API response JSON object.
 */
function makeApiResponse(overrides?: Record<string, any>): Record<string, any> {
  return {
    id: 'chatcmpl-test-123',
    model: 'test-model',
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: 'Hi there!' },
        finish_reason: 'stop',
      },
    ],
    usage: {
      prompt_tokens: 5,
      completion_tokens: 10,
      total_tokens: 15,
    },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Global fetch mock management
// ---------------------------------------------------------------------------

let originalFetch: typeof globalThis.fetch;

beforeAll(() => {
  originalFetch = globalThis.fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

// ===========================================================================
// 1. BrowserProviderConfig
// ===========================================================================

describe('BrowserProviderConfig', () => {
  it('creates config with sensible defaults', () => {
    const config = createBrowserProviderConfig();
    expect(config.baseUrl).toBe('');
    expect(config.apiKey).toBe('');
    expect(config.models).toEqual([]);
    expect(config.timeout).toBe(30);
    expect(config.maxRetries).toBe(3);
    expect(config.authMethod).toBe('api_key');
    expect(config.retryableCodes).toEqual([429, 500, 502, 503]);
    expect(config.nonRetryableCodes).toEqual([400, 401, 403]);
    expect(config.capabilities).toEqual([
      'generation.text-generation.chat-completion',
    ]);
  });

  it('creates config with custom overrides', () => {
    const models = [makeModel('gpt-4o')];
    const config = createBrowserProviderConfig({
      baseUrl: 'https://api.openai.com',
      apiKey: 'sk-test',
      models,
      timeout: 60,
      maxRetries: 5,
      authMethod: 'oauth',
      capabilities: ['embedding'],
    });
    expect(config.baseUrl).toBe('https://api.openai.com');
    expect(config.apiKey).toBe('sk-test');
    expect(config.models).toEqual(models);
    expect(config.timeout).toBe(60);
    expect(config.maxRetries).toBe(5);
    expect(config.authMethod).toBe('oauth');
    expect(config.capabilities).toEqual(['embedding']);
  });

  it('proxyUrl is undefined by default', () => {
    const config = createBrowserProviderConfig();
    expect(config.proxyUrl).toBeUndefined();
  });

  it('proxyUrl can be set explicitly', () => {
    const config = createBrowserProviderConfig({
      proxyUrl: 'http://localhost:3000/proxy/',
    });
    expect(config.proxyUrl).toBe('http://localhost:3000/proxy/');
  });
});

// ===========================================================================
// 2. BrowserHttpError
// ===========================================================================

describe('BrowserHttpError', () => {
  it('sets statusCode, responseBody, and headers', () => {
    const headers = { 'content-type': 'application/json' };
    const err = new BrowserHttpError(404, 'Not found', headers);
    expect(err.statusCode).toBe(404);
    expect(err.responseBody).toBe('Not found');
    expect(err.headers).toEqual(headers);
  });

  it('message includes the HTTP status code', () => {
    const err = new BrowserHttpError(502, 'Bad gateway');
    expect(err.message).toContain('502');
    expect(err.message).toContain('Bad gateway');
  });

  it('name is BrowserHttpError', () => {
    const err = new BrowserHttpError(500, 'Internal server error');
    expect(err.name).toBe('BrowserHttpError');
  });

  it('is an instance of Error', () => {
    const err = new BrowserHttpError(401, 'Unauthorized');
    expect(err).toBeInstanceOf(Error);
  });

  it('defaults headers to an empty object', () => {
    const err = new BrowserHttpError(400, 'Bad request');
    expect(err.headers).toEqual({});
  });

  it('truncates long response bodies in message', () => {
    const longBody = 'x'.repeat(500);
    const err = new BrowserHttpError(500, longBody);
    // The constructor truncates responseBody to first 200 chars in the message
    expect(err.message.length).toBeLessThan(300);
    // But the full body is still accessible
    expect(err.responseBody.length).toBe(500);
  });
});

// ===========================================================================
// 3. URL Resolution
// ===========================================================================

describe('URL Resolution (_resolveUrl)', () => {
  it('returns URL unchanged when no proxyUrl is set', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.example.com' })
    );
    const url = 'https://api.example.com/v1/chat/completions';
    expect(provider.resolveUrl(url)).toBe(url);
  });

  it('prepends proxyUrl when set', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.example.com',
        proxyUrl: 'http://localhost:3000/proxy',
      })
    );
    expect(provider.resolveUrl('https://api.example.com/v1/chat/completions')).toBe(
      'http://localhost:3000/proxy/https://api.example.com/v1/chat/completions'
    );
  });

  it('strips trailing slashes from proxyUrl', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        proxyUrl: 'http://localhost:3000/proxy/',
      })
    );
    expect(provider.resolveUrl('https://api.example.com')).toBe(
      'http://localhost:3000/proxy/https://api.example.com'
    );
  });

  it('strips multiple trailing slashes from proxyUrl', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        proxyUrl: 'http://localhost:3000/proxy///',
      })
    );
    expect(provider.resolveUrl('https://api.example.com/v1')).toBe(
      'http://localhost:3000/proxy/https://api.example.com/v1'
    );
  });
});

// ===========================================================================
// 4. Request Building
// ===========================================================================

describe('Request Building (_buildRequestPayload)', () => {
  let provider: TestBrowserProvider;

  beforeEach(() => {
    provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.example.com' })
    );
  });

  it('includes model and messages', () => {
    const request = makeRequest();
    const payload = provider.buildRequestPayload(request);
    expect(payload.model).toBe('test-model');
    expect(payload.messages).toEqual([{ role: 'user', content: 'Hello' }]);
  });

  it('includes temperature when set', () => {
    const request = makeRequest({ temperature: 0.7 });
    const payload = provider.buildRequestPayload(request);
    expect(payload.temperature).toBe(0.7);
  });

  it('includes maxTokens as max_tokens when set', () => {
    const request = makeRequest({ maxTokens: 256 });
    const payload = provider.buildRequestPayload(request);
    expect(payload.max_tokens).toBe(256);
  });

  it('includes tools when array is non-empty', () => {
    const tools = [{ type: 'function', function: { name: 'get_weather' } }];
    const request = makeRequest({ tools });
    const payload = provider.buildRequestPayload(request);
    expect(payload.tools).toEqual(tools);
  });

  it('omits tools when array is empty', () => {
    const request = makeRequest({ tools: [] });
    const payload = provider.buildRequestPayload(request);
    expect(payload.tools).toBeUndefined();
  });

  it('includes stream flag when set', () => {
    const request = makeRequest({ stream: true });
    const payload = provider.buildRequestPayload(request);
    expect(payload.stream).toBe(true);
  });

  it('omits stream when false', () => {
    const request = makeRequest({ stream: false });
    const payload = provider.buildRequestPayload(request);
    expect(payload.stream).toBeUndefined();
  });

  it('omits temperature when undefined', () => {
    const request = makeRequest({ temperature: undefined });
    const payload = provider.buildRequestPayload(request);
    expect(payload.temperature).toBeUndefined();
  });

  it('omits maxTokens when undefined', () => {
    const request = makeRequest({ maxTokens: undefined });
    const payload = provider.buildRequestPayload(request);
    expect(payload.max_tokens).toBeUndefined();
  });
});

// ===========================================================================
// 5. Response Parsing
// ===========================================================================

describe('Response Parsing (_parseResponse)', () => {
  let provider: TestBrowserProvider;

  beforeEach(() => {
    provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.example.com' })
    );
  });

  it('extracts choices, usage, id, and model', () => {
    const data = makeApiResponse();
    const result = provider.parseResponse(data);

    expect(result.id).toBe('chatcmpl-test-123');
    expect(result.model).toBe('test-model');
    expect(result.choices.length).toBe(1);
    expect(result.choices[0].message).toBeDefined();
    expect(result.choices[0].message!.role).toBe('assistant');
    expect(result.choices[0].message!.content).toBe('Hi there!');
    expect(result.choices[0].finishReason).toBe('stop');
    expect(result.usage.promptTokens).toBe(5);
    expect(result.usage.completionTokens).toBe(10);
    expect(result.usage.totalTokens).toBe(15);
  });

  it('returns defaults for empty response', () => {
    const result = provider.parseResponse({});
    expect(result.id).toBe('');
    expect(result.model).toBe('');
    expect(result.choices).toEqual([]);
    expect(result.usage.promptTokens).toBe(0);
    expect(result.usage.completionTokens).toBe(0);
    expect(result.usage.totalTokens).toBe(0);
  });

  it('handles missing fields gracefully', () => {
    const data = {
      id: 'test-id',
      choices: [{ index: 0 }],
    };
    const result = provider.parseResponse(data);
    expect(result.id).toBe('test-id');
    expect(result.model).toBe('');
    expect(result.choices.length).toBe(1);
    expect(result.choices[0].message).toBeUndefined();
    expect(result.choices[0].finishReason).toBeUndefined();
    expect(result.usage.promptTokens).toBe(0);
  });

  it('handles multiple choices', () => {
    const data = makeApiResponse({
      choices: [
        { index: 0, message: { role: 'assistant', content: 'A' }, finish_reason: 'stop' },
        { index: 1, message: { role: 'assistant', content: 'B' }, finish_reason: 'stop' },
      ],
    });
    const result = provider.parseResponse(data);
    expect(result.choices.length).toBe(2);
    expect(result.choices[0].message!.content).toBe('A');
    expect(result.choices[1].message!.content).toBe('B');
  });
});

// ===========================================================================
// 6. SSE Chunk Parsing
// ===========================================================================

describe('SSE Chunk Parsing (_parseSseChunk)', () => {
  let provider: TestBrowserProvider;

  beforeEach(() => {
    provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.example.com' })
    );
  });

  it('parses valid JSON with delta content', () => {
    const chunk = JSON.stringify({
      id: 'chatcmpl-stream-1',
      model: 'gpt-4o',
      choices: [
        { index: 0, delta: { role: 'assistant', content: 'Hi' }, finish_reason: null },
      ],
    });

    const result = provider.parseSseChunk(chunk);
    expect(result).not.toBeNull();
    expect(result!.id).toBe('chatcmpl-stream-1');
    expect(result!.model).toBe('gpt-4o');
    expect(result!.choices.length).toBe(1);
    expect(result!.choices[0].delta).toBeDefined();
    expect(result!.choices[0].delta!.role).toBe('assistant');
    expect(result!.choices[0].delta!.content).toBe('Hi');
  });

  it('returns null for invalid JSON', () => {
    const result = provider.parseSseChunk('not valid json {{{');
    expect(result).toBeNull();
  });

  it('returns null for empty choices', () => {
    const chunk = JSON.stringify({
      id: 'chatcmpl-stream-2',
      model: 'gpt-4o',
      choices: [],
    });
    expect(provider.parseSseChunk(chunk)).toBeNull();
  });

  it('extracts delta content correctly from multiple choices', () => {
    const chunk = JSON.stringify({
      id: 'chatcmpl-stream-3',
      model: 'gpt-4o',
      choices: [
        { index: 0, delta: { role: 'assistant', content: 'Hello' }, finish_reason: null },
        { index: 1, delta: { role: 'assistant', content: 'World' }, finish_reason: null },
      ],
    });

    const result = provider.parseSseChunk(chunk);
    expect(result).not.toBeNull();
    expect(result!.choices.length).toBe(2);
    expect(result!.choices[0].delta!.content).toBe('Hello');
    expect(result!.choices[1].delta!.content).toBe('World');
  });

  it('handles missing delta gracefully', () => {
    const chunk = JSON.stringify({
      id: 'chatcmpl-stream-4',
      model: 'gpt-4o',
      choices: [{ index: 0, finish_reason: 'stop' }],
    });

    const result = provider.parseSseChunk(chunk);
    expect(result).not.toBeNull();
    expect(result!.choices[0].delta).toBeUndefined();
    expect(result!.choices[0].finishReason).toBe('stop');
  });

  it('returns null for no choices key at all', () => {
    const chunk = JSON.stringify({ id: 'chatcmpl-stream-5', model: 'gpt-4o' });
    expect(provider.parseSseChunk(chunk)).toBeNull();
  });
});

// ===========================================================================
// 7. Headers
// ===========================================================================

describe('Headers (_buildHeaders)', () => {
  it('includes Content-Type application/json', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.example.com' })
    );
    const headers = provider.buildHeaders();
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('includes Authorization Bearer token when API key is set', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.example.com',
        apiKey: 'sk-test-key',
      })
    );
    const headers = provider.buildHeaders();
    expect(headers['Authorization']).toBe('Bearer sk-test-key');
  });

  it('omits Authorization header when no API key', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.example.com',
        apiKey: '',
      })
    );
    const headers = provider.buildHeaders();
    expect(headers['Authorization']).toBeUndefined();
  });
});

// ===========================================================================
// 8. Error Classification
// ===========================================================================

describe('Error Classification', () => {
  let provider: TestBrowserProvider;

  beforeEach(() => {
    provider = new TestBrowserProvider(createBrowserProviderConfig());
  });

  it('classifies BrowserHttpError with status code', () => {
    const err = new BrowserHttpError(500, 'Internal server error');
    const classification = provider.classifyError(err);
    expect(classification.errorCode).toBe(500);
  });

  it('classifies non-BrowserHttpError as non-retryable unknown', () => {
    const err = new Error('network failure');
    const classification = provider.classifyError(err);
    expect(classification.retryable).toBe(false);
    expect(classification.category).toBe('unknown');
  });

  describe('retryable codes', () => {
    it.each([429, 500, 502, 503])('classifies %d as retryable', (code) => {
      const err = new BrowserHttpError(code, 'error');
      const classification = provider.classifyError(err);
      expect(classification.retryable).toBe(true);
    });
  });

  describe('non-retryable codes', () => {
    it.each([400, 401, 403])('classifies %d as non-retryable', (code) => {
      const err = new BrowserHttpError(code, 'error');
      const classification = provider.classifyError(err);
      expect(classification.retryable).toBe(false);
    });
  });

  describe('auth error categorization', () => {
    it('categorizes 401 as auth', () => {
      const err = new BrowserHttpError(401, 'Unauthorized');
      const classification = provider.classifyError(err);
      expect(classification.category).toBe('auth');
    });

    it('categorizes 403 as auth', () => {
      const err = new BrowserHttpError(403, 'Forbidden');
      const classification = provider.classifyError(err);
      expect(classification.category).toBe('auth');
    });
  });

  it('categorizes 429 as rate_limit', () => {
    const err = new BrowserHttpError(429, 'Too many requests');
    const classification = provider.classifyError(err);
    expect(classification.category).toBe('rate_limit');
  });

  it('categorizes 500 as server', () => {
    const err = new BrowserHttpError(500, 'Internal server error');
    const classification = provider.classifyError(err);
    expect(classification.category).toBe('server');
  });

  it('categorizes 400 as client', () => {
    const err = new BrowserHttpError(400, 'Bad request');
    const classification = provider.classifyError(err);
    expect(classification.category).toBe('client');
  });

  it('categorizes unknown status code as unknown', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        retryableCodes: [],
        nonRetryableCodes: [],
      })
    );
    const err = new BrowserHttpError(418, "I'm a teapot");
    const classification = provider.classifyError(err);
    expect(classification.category).toBe('unknown');
    expect(classification.retryable).toBe(false);
  });

  it('isRetryable delegates to classifyError', () => {
    const retryable = new BrowserHttpError(429, 'Rate limited');
    const nonRetryable = new BrowserHttpError(401, 'Unauthorized');
    expect(provider.isRetryable(retryable)).toBe(true);
    expect(provider.isRetryable(nonRetryable)).toBe(false);
  });
});

// ===========================================================================
// 9. Model Management
// ===========================================================================

describe('Model Management', () => {
  const models = [
    makeModel('gpt-4o', 'GPT-4o'),
    makeModel('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
  ];
  let provider: TestBrowserProvider;

  beforeEach(() => {
    provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.example.com',
        models,
      })
    );
  });

  it('listModels returns all configured models', () => {
    const listed = provider.listModels();
    expect(listed.length).toBe(2);
    expect(listed[0].id).toBe('gpt-4o');
    expect(listed[1].id).toBe('gpt-3.5-turbo');
  });

  it('listModels returns a copy (not a reference)', () => {
    const listed = provider.listModels();
    listed.push(makeModel('extra'));
    expect(provider.listModels().length).toBe(2);
  });

  it('getModelInfo returns model by ID', () => {
    const info = provider.getModelInfo('gpt-4o');
    expect(info.id).toBe('gpt-4o');
    expect(info.name).toBe('GPT-4o');
  });

  it('getModelInfo throws for unknown model', () => {
    expect(() => provider.getModelInfo('nonexistent')).toThrow('Model not found: nonexistent');
  });

  it('getCapabilities returns capabilities list', () => {
    const caps = provider.getCapabilities();
    expect(caps).toEqual(['generation.text-generation.chat-completion']);
  });

  it('getCapabilities returns a copy (not a reference)', () => {
    const caps = provider.getCapabilities();
    caps.push('extra');
    expect(provider.getCapabilities().length).toBe(1);
  });

  it('supports returns true for included capability', () => {
    expect(
      provider.supports('generation.text-generation.chat-completion')
    ).toBe(true);
  });

  it('supports returns false for missing capability', () => {
    expect(provider.supports('embedding')).toBe(false);
  });
});

// ===========================================================================
// 10. Quota & Usage
// ===========================================================================

describe('Quota & Usage', () => {
  let provider: TestBrowserProvider;

  beforeEach(() => {
    provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.example.com' })
    );
  });

  it('checkQuota returns initial request count of 0', () => {
    const quota = provider.checkQuota();
    expect(quota.used).toBe(0);
  });

  it('reportUsage increments request count', () => {
    provider.reportUsage('test-model', {
      promptTokens: 10,
      completionTokens: 5,
      totalTokens: 15,
    });
    expect(provider.checkQuota().used).toBe(1);
  });

  it('reportUsage increments counters cumulatively', () => {
    provider.reportUsage('m1', { promptTokens: 10, completionTokens: 5, totalTokens: 15 });
    provider.reportUsage('m2', { promptTokens: 20, completionTokens: 10, totalTokens: 30 });
    provider.reportUsage('m3', { promptTokens: 5, completionTokens: 3, totalTokens: 8 });
    expect(provider.checkQuota().used).toBe(3);
  });

  it('getRateLimits returns an empty object', () => {
    const limits = provider.getRateLimits();
    expect(limits).toEqual({});
  });
});

// ===========================================================================
// 11. Completion Endpoint
// ===========================================================================

describe('Completion Endpoint (_getCompletionEndpoint)', () => {
  it('builds correct URL from baseUrl', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.openai.com' })
    );
    expect(provider.getCompletionEndpoint()).toBe(
      'https://api.openai.com/v1/chat/completions'
    );
  });

  it('strips trailing slashes from baseUrl', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://api.openai.com/' })
    );
    expect(provider.getCompletionEndpoint()).toBe(
      'https://api.openai.com/v1/chat/completions'
    );
  });

  it('prepends proxyUrl when set', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.openai.com',
        proxyUrl: 'http://localhost:3000/proxy',
      })
    );
    expect(provider.getCompletionEndpoint()).toBe(
      'http://localhost:3000/proxy/https://api.openai.com/v1/chat/completions'
    );
  });

  it('handles proxyUrl with trailing slash', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.openai.com',
        proxyUrl: 'http://localhost:3000/proxy/',
      })
    );
    expect(provider.getCompletionEndpoint()).toBe(
      'http://localhost:3000/proxy/https://api.openai.com/v1/chat/completions'
    );
  });

  it('uses baseUrl directly when no proxyUrl', () => {
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({ baseUrl: 'https://custom-api.example.com' })
    );
    expect(provider.getCompletionEndpoint()).toBe(
      'https://custom-api.example.com/v1/chat/completions'
    );
  });
});

// ===========================================================================
// 12. Integration-style tests (mocked fetch)
// ===========================================================================

describe('Integration: complete() with mocked fetch', () => {
  let provider: TestBrowserProvider;
  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = jest.fn();
    (globalThis as any).fetch = mockFetch;

    provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.example.com',
        apiKey: 'sk-test',
        models: [makeModel('test-model')],
        maxRetries: 2,
        timeout: 10,
      })
    );
  });

  it('returns parsed response on successful fetch', async () => {
    const apiResponse = makeApiResponse();

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(apiResponse),
      headers: new Map(),
    });

    const request = makeRequest();
    const result = await provider.complete(request);

    expect(result.id).toBe('chatcmpl-test-123');
    expect(result.model).toBe('test-model');
    expect(result.choices.length).toBe(1);
    expect(result.choices[0].message!.content).toBe('Hi there!');
    expect(result.usage.totalTokens).toBe(15);

    // Verify fetch was called with correct endpoint
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe('https://api.example.com/v1/chat/completions');
    expect(options.method).toBe('POST');
    expect(options.headers['Authorization']).toBe('Bearer sk-test');
    expect(options.headers['Content-Type']).toBe('application/json');
  });

  it('reports usage after successful completion', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(makeApiResponse()),
      headers: new Map(),
    });

    expect(provider.checkQuota().used).toBe(0);
    await provider.complete(makeRequest());
    expect(provider.checkQuota().used).toBe(1);
  });

  it('retries on retryable error and eventually succeeds', async () => {
    // Patch _sleep to avoid real delays in tests
    (provider as any)._sleep = jest.fn().mockResolvedValue(undefined);

    // First call: 500 error (retryable)
    const failHeaders = new Map([['content-type', 'text/plain']]);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => 'Internal Server Error',
      headers: {
        forEach: (cb: (v: string, k: string) => void) => {
          failHeaders.forEach((v, k) => cb(v, k));
        },
      },
    });

    // Second call: success
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(makeApiResponse()),
      headers: new Map(),
    });

    const result = await provider.complete(makeRequest());
    expect(result.id).toBe('chatcmpl-test-123');
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('does not retry on non-retryable error', async () => {
    const failHeaders = new Map([['content-type', 'text/plain']]);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      text: async () => 'Unauthorized',
      headers: {
        forEach: (cb: (v: string, k: string) => void) => {
          failHeaders.forEach((v, k) => cb(v, k));
        },
      },
    });

    await expect(provider.complete(makeRequest())).rejects.toThrow(BrowserHttpError);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('throws after exhausting all retries', async () => {
    (provider as any)._sleep = jest.fn().mockResolvedValue(undefined);

    const failHeaders = new Map([['content-type', 'text/plain']]);
    const makeFailResponse = () => ({
      ok: false,
      status: 503,
      text: async () => 'Service Unavailable',
      headers: {
        forEach: (cb: (v: string, k: string) => void) => {
          failHeaders.forEach((v, k) => cb(v, k));
        },
      },
    });

    // maxRetries is 2, so initial + 2 retries = 3 total attempts
    mockFetch.mockResolvedValueOnce(makeFailResponse());
    mockFetch.mockResolvedValueOnce(makeFailResponse());
    mockFetch.mockResolvedValueOnce(makeFailResponse());

    await expect(provider.complete(makeRequest())).rejects.toThrow(BrowserHttpError);
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  it('respects retry-after header', async () => {
    const sleepSpy = jest.fn().mockResolvedValue(undefined);
    (provider as any)._sleep = sleepSpy;

    const failHeaders = new Map([
      ['content-type', 'text/plain'],
      ['retry-after', '5'],
    ]);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 429,
      text: async () => 'Rate limited',
      headers: {
        forEach: (cb: (v: string, k: string) => void) => {
          failHeaders.forEach((v, k) => cb(v, k));
        },
      },
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(makeApiResponse()),
      headers: new Map(),
    });

    await provider.complete(makeRequest());
    expect(sleepSpy).toHaveBeenCalledWith(5000); // 5 seconds * 1000
  });
});

describe('Integration: stream() with mocked fetch', () => {
  let provider: TestBrowserProvider;
  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = jest.fn();
    (globalThis as any).fetch = mockFetch;

    provider = new TestBrowserProvider(
      createBrowserProviderConfig({
        baseUrl: 'https://api.example.com',
        apiKey: 'sk-test',
        models: [makeModel('test-model')],
        timeout: 10,
      })
    );
  });

  it('yields parsed chunks from SSE stream', async () => {
    const sseLines = [
      'data: {"id":"s1","model":"test-model","choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}',
      '',
      'data: {"id":"s2","model":"test-model","choices":[{"index":0,"delta":{"role":"assistant","content":" world"},"finish_reason":null}]}',
      '',
      'data: {"id":"s3","model":"test-model","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
      '',
      'data: [DONE]',
    ].join('\n');

    // Simulate a response with no body (fallback path: reads entire text)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: null,
      text: async () => sseLines,
      headers: new Map(),
    });

    const request = makeRequest({ stream: true });
    const chunks: CompletionResponse[] = [];
    for await (const chunk of provider.stream(request)) {
      chunks.push(chunk);
    }

    expect(chunks.length).toBe(3);
    expect(chunks[0].choices[0].delta!.content).toBe('Hello');
    expect(chunks[1].choices[0].delta!.content).toBe(' world');
    expect(chunks[2].choices[0].finishReason).toBe('stop');
  });

  it('skips non-data lines in SSE stream', async () => {
    const sseLines = [
      ': this is a comment',
      '',
      'event: message',
      'data: {"id":"s1","model":"test-model","choices":[{"index":0,"delta":{"role":"assistant","content":"OK"},"finish_reason":null}]}',
      '',
      'data: [DONE]',
    ].join('\n');

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: null,
      text: async () => sseLines,
      headers: new Map(),
    });

    const chunks: CompletionResponse[] = [];
    for await (const chunk of provider.stream(makeRequest({ stream: true }))) {
      chunks.push(chunk);
    }

    expect(chunks.length).toBe(1);
    expect(chunks[0].choices[0].delta!.content).toBe('OK');
  });

  it('stream sends request with stream flag in payload', async () => {
    const sseLines = 'data: [DONE]\n';

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: null,
      text: async () => sseLines,
      headers: new Map(),
    });

    const chunks: CompletionResponse[] = [];
    for await (const chunk of provider.stream(makeRequest())) {
      chunks.push(chunk);
    }

    const [, options] = mockFetch.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(body.stream).toBe(true);
  });

  it('throws BrowserHttpError on non-ok stream response', async () => {
    const failHeaders = new Map([['content-type', 'text/plain']]);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => 'Internal Server Error',
      headers: {
        forEach: (cb: (v: string, k: string) => void) => {
          failHeaders.forEach((v, k) => cb(v, k));
        },
      },
    });

    const iterator = provider.stream(makeRequest({ stream: true }));

    await expect(iterator.next()).rejects.toThrow(BrowserHttpError);
  });
});

// ===========================================================================
// 13. Pricing
// ===========================================================================

describe('Pricing', () => {
  it('getPricing returns model pricing when configured', () => {
    const models: ModelInfo[] = [
      createDefaultModelInfo({
        id: 'gpt-4o',
        name: 'GPT-4o',
        pricing: { inputPer1kTokens: 0.005, outputPer1kTokens: 0.015, perRequest: 0 },
      }),
    ];
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({ models })
    );
    const pricing = provider.getPricing('gpt-4o');
    expect(pricing.inputPer1kTokens).toBe(0.005);
    expect(pricing.outputPer1kTokens).toBe(0.015);
  });

  it('getPricing throws when model has no pricing', () => {
    const models: ModelInfo[] = [makeModel('gpt-4o')];
    const provider = new TestBrowserProvider(
      createBrowserProviderConfig({ models })
    );
    expect(() => provider.getPricing('gpt-4o')).toThrow(
      'No pricing configured for model: gpt-4o'
    );
  });

  it('getPricing throws for unknown model', () => {
    const provider = new TestBrowserProvider(createBrowserProviderConfig());
    expect(() => provider.getPricing('nonexistent')).toThrow('Model not found: nonexistent');
  });
});

// ===========================================================================
// 14. close() method
// ===========================================================================

describe('close()', () => {
  it('resolves without error', async () => {
    const provider = new TestBrowserProvider(createBrowserProviderConfig());
    await expect(provider.close()).resolves.toBeUndefined();
  });
});
