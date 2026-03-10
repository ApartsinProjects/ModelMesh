/**
 * Tests for pre-shipped connectors.
 */
import { NullObservabilityConnector } from '@/connectors/observability/null-connector';
import { ConsoleObservabilityConnector } from '@/connectors/observability/console-connector';
import { MemoryStorage } from '@/connectors/storage/memory-storage';
import { EnvSecretStore } from '@/connectors/secret-stores/env-store';
import { StickUntilFailurePolicy } from '@/connectors/rotation/stick-until-failure';
import { BaseProvider, createBaseProviderConfig } from '@/cdk/base-provider';
import { EventType } from '@/interfaces/observability';
import type { RoutingEvent, RequestLogEntry, TraceEntry } from '@/interfaces/observability';
import type { StorageEntry } from '@/interfaces/storage';
import type { CompletionResponse } from '@/interfaces/provider';

/**
 * Test harness that exposes protected BaseProvider methods for unit testing.
 */
class TestableProvider extends BaseProvider {
  public parseResponse(data: Record<string, any>): CompletionResponse {
    return this._parseResponse(data);
  }

  public parseSseChunk(line: string): CompletionResponse | null {
    return this._parseSseChunk(line);
  }
}

// ---------------------------------------------------------------------------
// NullObservabilityConnector
// ---------------------------------------------------------------------------

describe('NullObservabilityConnector', () => {
  it('should have correct connector ID', () => {
    expect(NullObservabilityConnector.CONNECTOR_ID).toBe('modelmesh.null.v1');
  });

  it('should not throw on any method', () => {
    const conn = new NullObservabilityConnector();
    const event: RoutingEvent = {
      eventType: EventType.MODEL_ACTIVATED,
      timestamp: new Date(),
      metadata: {},
    };
    expect(() => conn.emit(event)).not.toThrow();
    expect(() => conn.log({} as RequestLogEntry)).not.toThrow();
    expect(() => conn.flush({})).not.toThrow();
    expect(() => conn.trace({} as TraceEntry)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// ConsoleObservabilityConnector
// ---------------------------------------------------------------------------

describe('ConsoleObservabilityConnector', () => {
  it('should have correct connector ID', () => {
    expect(ConsoleObservabilityConnector.CONNECTOR_ID).toBe('modelmesh.console.v1');
  });

  it('should create with default config', () => {
    const conn = new ConsoleObservabilityConnector();
    expect(conn).toBeDefined();
  });

  it('should emit events to console', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation();
    const conn = new ConsoleObservabilityConnector({ useColor: false });
    conn.emit({
      eventType: EventType.MODEL_ACTIVATED,
      timestamp: new Date(),
      modelId: 'test-model',
      metadata: {},
    });
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  it('should log requests to console', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation();
    const conn = new ConsoleObservabilityConnector({ useColor: false });
    conn.log({
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
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// MemoryStorage
// ---------------------------------------------------------------------------

describe('MemoryStorage', () => {
  let storage: MemoryStorage;

  beforeEach(() => {
    storage = new MemoryStorage();
  });

  it('should have correct connector ID', () => {
    expect(MemoryStorage.CONNECTOR_ID).toBe('modelmesh.memory.v1');
  });

  it('should save and load entries', async () => {
    const entry: StorageEntry = {
      key: 'test-key',
      data: Buffer.from('hello world'),
      metadata: { version: 1 },
    };
    await storage.save('test-key', entry);
    const loaded = await storage.load('test-key');
    expect(loaded).not.toBeNull();
    expect(loaded!.data.toString()).toBe('hello world');
    expect(loaded!.metadata).toEqual({ version: 1 });
  });

  it('should return null for missing keys', async () => {
    const loaded = await storage.load('nonexistent');
    expect(loaded).toBeNull();
  });

  it('should list all keys', async () => {
    await storage.save('k1', { key: 'k1', data: Buffer.from('a'), metadata: {} });
    await storage.save('k2', { key: 'k2', data: Buffer.from('b'), metadata: {} });
    await storage.save('k3', { key: 'k3', data: Buffer.from('c'), metadata: {} });
    const keys = await storage.list();
    expect(keys.length).toBe(3);
    expect(keys).toContain('k1');
    expect(keys).toContain('k2');
    expect(keys).toContain('k3');
  });

  it('should list keys with prefix filter', async () => {
    await storage.save('state:model-1', { key: 'state:model-1', data: Buffer.from('a'), metadata: {} });
    await storage.save('state:model-2', { key: 'state:model-2', data: Buffer.from('b'), metadata: {} });
    await storage.save('config:main', { key: 'config:main', data: Buffer.from('c'), metadata: {} });
    const stateKeys = await storage.list('state:');
    expect(stateKeys.length).toBe(2);
    expect(stateKeys).toContain('state:model-1');
    expect(stateKeys).toContain('state:model-2');
  });

  it('should delete existing keys', async () => {
    await storage.save('k1', { key: 'k1', data: Buffer.from('a'), metadata: {} });
    const deleted = await storage.delete('k1');
    expect(deleted).toBe(true);
    expect(await storage.load('k1')).toBeNull();
  });

  it('should return false when deleting non-existent key', async () => {
    const deleted = await storage.delete('missing');
    expect(deleted).toBe(false);
  });

  it('should check existence', async () => {
    await storage.save('k1', { key: 'k1', data: Buffer.from('a'), metadata: {} });
    expect(await storage.exists('k1')).toBe(true);
    expect(await storage.exists('missing')).toBe(false);
  });

  it('should return stat metadata', async () => {
    await storage.save('k1', { key: 'k1', data: Buffer.from('hello'), metadata: {} });
    const stat = await storage.stat('k1');
    expect(stat).not.toBeNull();
    expect(stat!.key).toBe('k1');
    expect(stat!.size).toBe(5);
    expect(stat!.lastModified).toBeInstanceOf(Date);
    expect(stat!.contentType).toBe('application/octet-stream');
  });

  it('should return null stat for missing key', async () => {
    const stat = await storage.stat('missing');
    expect(stat).toBeNull();
  });

  it('should overwrite existing entries', async () => {
    await storage.save('k1', { key: 'k1', data: Buffer.from('old'), metadata: {} });
    await storage.save('k1', { key: 'k1', data: Buffer.from('new'), metadata: { updated: true } });
    const loaded = await storage.load('k1');
    expect(loaded!.data.toString()).toBe('new');
    expect(loaded!.metadata).toEqual({ updated: true });
  });
});

// ---------------------------------------------------------------------------
// EnvSecretStore
// ---------------------------------------------------------------------------

describe('EnvSecretStore', () => {
  it('should have correct connector ID', () => {
    expect(EnvSecretStore.CONNECTOR_ID).toBe('modelmesh.env.v1');
  });

  it('should read environment variables', () => {
    process.env.TEST_MODELMESH_SECRET = 'test-value-123';
    const store = new EnvSecretStore();
    expect(store.get('TEST_MODELMESH_SECRET')).toBe('test-value-123');
    delete process.env.TEST_MODELMESH_SECRET;
  });

  it('should return empty string for missing keys', () => {
    const store = new EnvSecretStore();
    expect(store.get('DEFINITELY_NOT_SET_XYZ_12345')).toBe('');
  });

  it('should throw when failOnMissing is true', () => {
    const store = new EnvSecretStore({ failOnMissing: true });
    expect(() => store.get('DEFINITELY_NOT_SET_XYZ_12345')).toThrow();
  });

  it('should support prefix', () => {
    process.env.MM_TEST_KEY = 'prefixed-value';
    const store = new EnvSecretStore({ prefix: 'MM_' });
    expect(store.get('TEST_KEY')).toBe('prefixed-value');
    delete process.env.MM_TEST_KEY;
  });
});

// ---------------------------------------------------------------------------
// StickUntilFailurePolicy
// ---------------------------------------------------------------------------

describe('StickUntilFailurePolicy', () => {
  it('should have correct connector ID', () => {
    expect(StickUntilFailurePolicy.CONNECTOR_ID).toBe('modelmesh.stick-until-failure.v1');
  });

  it('should create with default config', () => {
    const policy = new StickUntilFailurePolicy();
    expect(policy.config.failureThreshold).toBe(3);
    expect(policy.config.cooldownSeconds).toBe(60);
    expect(policy.config.errorRateThreshold).toBe(0.5);
  });

  it('should deactivate after failure threshold', () => {
    const policy = new StickUntilFailurePolicy({ failureThreshold: 3 });
    expect(policy.shouldDeactivate({
      consecutiveFailures: 3,
      errorRate: 0,
      totalRequests: 10,
      totalTokens: 0,
      totalCost: 0,
    })).toBe(true);
  });

  it('should not deactivate below threshold', () => {
    const policy = new StickUntilFailurePolicy({ failureThreshold: 3 });
    expect(policy.shouldDeactivate({
      consecutiveFailures: 2,
      errorRate: 0,
      totalRequests: 10,
      totalTokens: 0,
      totalCost: 0,
    })).toBe(false);
  });

  it('should deactivate on high error rate', () => {
    const policy = new StickUntilFailurePolicy({ errorRateThreshold: 0.5 });
    expect(policy.shouldDeactivate({
      consecutiveFailures: 0,
      errorRate: 0.6,
      totalRequests: 10,
      totalTokens: 0,
      totalCost: 0,
    })).toBe(true);
  });

  it('should deactivate on request limit', () => {
    const policy = new StickUntilFailurePolicy({ requestLimit: 100 });
    expect(policy.shouldDeactivate({
      consecutiveFailures: 0,
      errorRate: 0,
      totalRequests: 100,
      totalTokens: 0,
      totalCost: 0,
    })).toBe(true);
  });

  it('should recover after cooldown', () => {
    const policy = new StickUntilFailurePolicy({ cooldownSeconds: 60 });
    const pastDate = new Date(Date.now() - 120_000);
    expect(policy.shouldRecover({ deactivatedAt: pastDate })).toBe(true);
  });

  it('should not recover before cooldown', () => {
    const policy = new StickUntilFailurePolicy({ cooldownSeconds: 60 });
    const recentDate = new Date(Date.now() - 10_000);
    expect(policy.shouldRecover({ deactivatedAt: recentDate })).toBe(false);
  });

  it('should not recover without deactivation time', () => {
    const policy = new StickUntilFailurePolicy();
    expect(policy.shouldRecover({})).toBe(false);
  });

  it('should select by priority', () => {
    const policy = new StickUntilFailurePolicy({
      modelPriority: ['model-b', 'model-a'],
    });
    const candidates = [
      { modelId: 'model-a', errorRate: 0 },
      { modelId: 'model-b', errorRate: 0.1 },
    ];
    const selected = policy.select(candidates);
    expect(selected!.modelId).toBe('model-b');
  });

  it('should select by lowest error rate when no priority match', () => {
    const policy = new StickUntilFailurePolicy();
    const candidates = [
      { modelId: 'model-a', errorRate: 0.3 },
      { modelId: 'model-b', errorRate: 0.1 },
    ];
    const selected = policy.select(candidates);
    expect(selected!.modelId).toBe('model-b');
  });

  it('should return null for empty candidates', () => {
    const policy = new StickUntilFailurePolicy();
    expect(policy.select([])).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// BaseProvider._parseResponse()
// ---------------------------------------------------------------------------

describe('BaseProvider._parseResponse()', () => {
  let provider: TestableProvider;

  beforeEach(() => {
    provider = new TestableProvider(createBaseProviderConfig({
      baseUrl: 'https://api.example.com',
      apiKey: 'test-key',
    }));
  });

  it('should extract message with role and content from OpenAI-format response', () => {
    const data = {
      id: 'chatcmpl-abc123',
      model: 'gpt-4o',
      choices: [
        {
          index: 0,
          message: { role: 'assistant', content: 'Hello, world!' },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: 10,
        completion_tokens: 5,
        total_tokens: 15,
      },
    };

    const result = provider.parseResponse(data);

    expect(result.id).toBe('chatcmpl-abc123');
    expect(result.model).toBe('gpt-4o');
    expect(result.choices.length).toBe(1);
    expect(result.choices[0].message).toBeDefined();
    expect(result.choices[0].message!.role).toBe('assistant');
    expect(result.choices[0].message!.content).toBe('Hello, world!');
    expect(result.choices[0].finishReason).toBe('stop');
    expect(result.usage.promptTokens).toBe(10);
    expect(result.usage.completionTokens).toBe(5);
    expect(result.usage.totalTokens).toBe(15);
  });

  it('should handle missing message gracefully', () => {
    const data = {
      id: 'chatcmpl-xyz',
      model: 'gpt-4o',
      choices: [
        {
          index: 0,
          finish_reason: 'stop',
          // no "message" key
        },
      ],
      usage: {
        prompt_tokens: 5,
        completion_tokens: 0,
        total_tokens: 5,
      },
    };

    const result = provider.parseResponse(data);

    expect(result.choices.length).toBe(1);
    expect(result.choices[0].message).toBeUndefined();
    expect(result.choices[0].finishReason).toBe('stop');
  });
});

// ---------------------------------------------------------------------------
// BaseProvider._parseSseChunk()
// ---------------------------------------------------------------------------

describe('BaseProvider._parseSseChunk()', () => {
  let provider: TestableProvider;

  beforeEach(() => {
    provider = new TestableProvider(createBaseProviderConfig({
      baseUrl: 'https://api.example.com',
      apiKey: 'test-key',
    }));
  });

  it('should extract delta with role and content from streaming response', () => {
    const chunk = JSON.stringify({
      id: 'chatcmpl-stream-1',
      model: 'gpt-4o',
      choices: [
        {
          index: 0,
          delta: { role: 'assistant', content: 'Hi' },
          finish_reason: null,
        },
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

  it('should handle missing delta', () => {
    const chunk = JSON.stringify({
      id: 'chatcmpl-stream-2',
      model: 'gpt-4o',
      choices: [
        {
          index: 0,
          // no "delta" key
          finish_reason: 'stop',
        },
      ],
    });

    const result = provider.parseSseChunk(chunk);

    expect(result).not.toBeNull();
    expect(result!.choices.length).toBe(1);
    expect(result!.choices[0].delta).toBeUndefined();
    expect(result!.choices[0].finishReason).toBe('stop');
  });

  it('should return null for invalid JSON', () => {
    const result = provider.parseSseChunk('not valid json {{{');
    expect(result).toBeNull();
  });

  it('should return null for empty choices', () => {
    const chunk = JSON.stringify({
      id: 'chatcmpl-stream-3',
      model: 'gpt-4o',
      choices: [],
    });

    const result = provider.parseSseChunk(chunk);
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// AzureSpeechProvider
// ---------------------------------------------------------------------------

import {
  AzureSpeechProvider,
  createAzureSpeechProviderConfig,
} from '@/connectors/providers/azure-speech-provider';
import { OllamaProvider, createOllamaProviderConfig } from '@/connectors/providers/ollama-provider';
import { LMStudioProvider, createLMStudioProviderConfig } from '@/connectors/providers/lmstudio-provider';
import { VLLMProvider, createVLLMProviderConfig } from '@/connectors/providers/vllm-provider';
import { LocalAIProvider, createLocalAIProviderConfig } from '@/connectors/providers/localai-provider';
import { RuntimeEnvironment } from '@/interfaces/runtime';
import { MemorySecretStore } from '@/connectors/secret-stores/memory-store';

describe('AzureSpeechProvider', () => {
  it('should have correct connector ID', () => {
    expect(AzureSpeechProvider.CONNECTOR_ID).toBe('azure.tts.v1');
  });

  it('should default to eastus region', () => {
    const config = createAzureSpeechProviderConfig({ apiKey: 'key' });
    expect(config.region).toBe('eastus');
  });

  it('should derive base URL from region', () => {
    const config = createAzureSpeechProviderConfig({ apiKey: 'key' });
    expect(config.baseUrl).toBe('https://eastus.tts.speech.microsoft.com');
  });

  it('should update base URL when region changes', () => {
    const config = createAzureSpeechProviderConfig({
      apiKey: 'key',
      region: 'westeurope',
    });
    expect(config.baseUrl).toBe(
      'https://westeurope.tts.speech.microsoft.com'
    );
  });

  it('should use Ocp-Apim-Subscription-Key header', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'az-test' });
    const headers = (provider as any)._buildHeaders();
    expect(headers['Ocp-Apim-Subscription-Key']).toBe('az-test');
    expect(headers['Authorization']).toBeUndefined();
  });

  it('should set SSML content type', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    const headers = (provider as any)._buildHeaders();
    expect(headers['Content-Type']).toBe('application/ssml+xml');
  });

  it('should set X-Microsoft-OutputFormat header', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    const headers = (provider as any)._buildHeaders();
    expect(headers['X-Microsoft-OutputFormat']).toBe(
      'audio-24khz-48kbitrate-mono-mp3'
    );
  });

  it('should set User-Agent header', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    const headers = (provider as any)._buildHeaders();
    expect(headers['User-Agent']).toBeDefined();
  });

  it('should return correct endpoint', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    const endpoint = (provider as any)._getCompletionEndpoint();
    expect(endpoint).toBe(
      'https://eastus.tts.speech.microsoft.com/cognitiveservices/v1'
    );
  });

  it('should have default TTS models', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    const models = provider.listModels();
    const ids = models.map((m) => m.id);
    expect(ids).toContain('en-US-JennyNeural');
    expect(ids).toContain('en-US-AndrewNeural');
  });

  it('should have TTS capability on all models', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    for (const model of provider.listModels()) {
      expect(
        model.capabilities.some((c) => c.includes('text-to-speech'))
      ).toBe(true);
    }
  });

  it('should build SSML payload', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    const payload = (provider as any)._buildRequestPayload({
      model: 'en-US-JennyNeural',
      messages: [{ role: 'user', content: 'Hello world' }],
    });
    const ssml: string = payload.__ssml_body;
    expect(ssml).toContain('<speak');
    expect(ssml).toContain('<voice');
    expect(ssml).toContain('en-US-JennyNeural');
    expect(ssml).toContain('Hello world');
  });

  it('should escape XML special characters in payload', () => {
    const provider = new AzureSpeechProvider({ apiKey: 'key' });
    const payload = (provider as any)._buildRequestPayload({
      model: 'en-US-JennyNeural',
      messages: [{ role: 'user', content: 'A & B < C' }],
    });
    const ssml: string = payload.__ssml_body;
    expect(ssml).toContain('A &amp; B &lt; C');
    expect(ssml).not.toContain('A & B < C');
  });

  it('should default voice to en-US-JennyNeural', () => {
    const config = createAzureSpeechProviderConfig({ apiKey: 'key' });
    expect(config.voice).toBe('en-US-JennyNeural');
  });

  it('should default language to en-US', () => {
    const config = createAzureSpeechProviderConfig({ apiKey: 'key' });
    expect(config.language).toBe('en-US');
  });
});

// ---------------------------------------------------------------------------
// OllamaProvider
// ---------------------------------------------------------------------------

describe('OllamaProvider', () => {
  test('connector ID', () => {
    expect(OllamaProvider.CONNECTOR_ID).toBe('ollama.local.v1');
  });

  test('default base URL', () => {
    const cfg = createOllamaProviderConfig();
    expect(cfg.baseUrl).toBe('http://localhost:11434');
  });

  test('empty API key', () => {
    const cfg = createOllamaProviderConfig();
    expect(cfg.apiKey).toBe('');
  });

  test('default models', () => {
    const cfg = createOllamaProviderConfig();
    expect(cfg.models.length).toBe(4);
  });

  test('chat-completion capability', () => {
    const cfg = createOllamaProviderConfig();
    expect(cfg.capabilities).toContain('generation.text-generation.chat-completion');
  });

  test('endpoint', () => {
    const p = new OllamaProvider();
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });

  test('runtime metadata', () => {
    expect(OllamaProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });

  test('custom host override', () => {
    const cfg = createOllamaProviderConfig({ baseUrl: 'http://myhost:9999' });
    expect(cfg.baseUrl).toBe('http://myhost:9999');
  });
});

// ---------------------------------------------------------------------------
// LMStudioProvider
// ---------------------------------------------------------------------------

describe('LMStudioProvider', () => {
  test('connector ID', () => {
    expect(LMStudioProvider.CONNECTOR_ID).toBe('lmstudio.local.v1');
  });

  test('default base URL', () => {
    const cfg = createLMStudioProviderConfig();
    expect(cfg.baseUrl).toBe('http://localhost:1234');
  });

  test('empty API key', () => {
    const cfg = createLMStudioProviderConfig();
    expect(cfg.apiKey).toBe('');
  });

  test('default models (empty)', () => {
    const cfg = createLMStudioProviderConfig();
    expect(cfg.models.length).toBe(0);
  });

  test('chat-completion capability', () => {
    const cfg = createLMStudioProviderConfig();
    expect(cfg.capabilities).toContain('generation.text-generation.chat-completion');
  });

  test('endpoint', () => {
    const p = new LMStudioProvider();
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });

  test('runtime metadata', () => {
    expect(LMStudioProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });

  test('custom host override', () => {
    const cfg = createLMStudioProviderConfig({ baseUrl: 'http://myhost:5555' });
    expect(cfg.baseUrl).toBe('http://myhost:5555');
  });
});

// ---------------------------------------------------------------------------
// VLLMProvider
// ---------------------------------------------------------------------------

describe('VLLMProvider', () => {
  test('connector ID', () => {
    expect(VLLMProvider.CONNECTOR_ID).toBe('vllm.local.v1');
  });

  test('default base URL', () => {
    const cfg = createVLLMProviderConfig();
    expect(cfg.baseUrl).toBe('http://localhost:8000');
  });

  test('empty API key', () => {
    const cfg = createVLLMProviderConfig();
    expect(cfg.apiKey).toBe('');
  });

  test('default models (empty)', () => {
    const cfg = createVLLMProviderConfig();
    expect(cfg.models.length).toBe(0);
  });

  test('chat-completion capability', () => {
    const cfg = createVLLMProviderConfig();
    expect(cfg.capabilities).toContain('generation.text-generation.chat-completion');
  });

  test('endpoint', () => {
    const p = new VLLMProvider();
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });

  test('runtime metadata', () => {
    expect(VLLMProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });

  test('custom host override', () => {
    const cfg = createVLLMProviderConfig({ baseUrl: 'http://myhost:7777' });
    expect(cfg.baseUrl).toBe('http://myhost:7777');
  });
});

// ---------------------------------------------------------------------------
// LocalAIProvider
// ---------------------------------------------------------------------------

describe('LocalAIProvider', () => {
  test('connector ID', () => {
    expect(LocalAIProvider.CONNECTOR_ID).toBe('localai.local.v1');
  });

  test('default base URL', () => {
    const cfg = createLocalAIProviderConfig();
    expect(cfg.baseUrl).toBe('http://localhost:8080');
  });

  test('empty API key', () => {
    const cfg = createLocalAIProviderConfig();
    expect(cfg.apiKey).toBe('');
  });

  test('default models (empty)', () => {
    const cfg = createLocalAIProviderConfig();
    expect(cfg.models.length).toBe(0);
  });

  test('chat-completion capability', () => {
    const cfg = createLocalAIProviderConfig();
    expect(cfg.capabilities).toContain('generation.text-generation.chat-completion');
  });

  test('endpoint', () => {
    const p = new LocalAIProvider();
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });

  test('runtime metadata', () => {
    expect(LocalAIProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });

  test('custom host override', () => {
    const cfg = createLocalAIProviderConfig({ baseUrl: 'http://myhost:3000' });
    expect(cfg.baseUrl).toBe('http://myhost:3000');
  });
});

// ---------------------------------------------------------------------------
// RuntimeEnvironment
// ---------------------------------------------------------------------------

describe('RuntimeEnvironment', () => {
  test('NODE_ONLY value', () => {
    expect(RuntimeEnvironment.NODE_ONLY).toBe('node');
  });

  test('BROWSER_ONLY value', () => {
    expect(RuntimeEnvironment.BROWSER_ONLY).toBe('browser');
  });

  test('UNIVERSAL value', () => {
    expect(RuntimeEnvironment.UNIVERSAL).toBe('universal');
  });

  test('BaseProvider is NODE_ONLY', () => {
    expect(BaseProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });

  test('MemoryStorage is UNIVERSAL', () => {
    expect(MemoryStorage.RUNTIME).toBe(RuntimeEnvironment.UNIVERSAL);
  });

  test('MemorySecretStore is UNIVERSAL', () => {
    expect(MemorySecretStore.RUNTIME).toBe(RuntimeEnvironment.UNIVERSAL);
  });
});

// ---------------------------------------------------------------------------
// Cloud Provider Tests
// ---------------------------------------------------------------------------

import { OpenAIProvider, createOpenAIProviderConfig } from '@/connectors/providers/openai-provider';
import { AnthropicProvider, createAnthropicProviderConfig } from '@/connectors/providers/anthropic-provider';
import { GeminiProvider, createGeminiProviderConfig } from '@/connectors/providers/gemini-provider';
import { GroqProvider, createGroqProviderConfig } from '@/connectors/providers/groq-provider';
import { DeepSeekProvider, createDeepSeekProviderConfig } from '@/connectors/providers/deepseek-provider';
import { MistralProvider, createMistralProviderConfig } from '@/connectors/providers/mistral-provider';
import { TogetherProvider, createTogetherProviderConfig } from '@/connectors/providers/together-provider';
import { OpenRouterProvider, createOpenRouterProviderConfig } from '@/connectors/providers/openrouter-provider';
import { XAIProvider, createXAIProviderConfig } from '@/connectors/providers/xai-provider';
import { CohereProvider, createCohereProviderConfig } from '@/connectors/providers/cohere-provider';
import { PerplexityProvider, createPerplexityProviderConfig } from '@/connectors/providers/perplexity-provider';
import { ElevenLabsProvider, createElevenLabsProviderConfig } from '@/connectors/providers/elevenlabs-provider';
import { TavilyProvider, createTavilyProviderConfig } from '@/connectors/providers/tavily-provider';
import { SerperProvider, createSerperProviderConfig } from '@/connectors/providers/serper-provider';
import { JinaProvider, createJinaProviderConfig } from '@/connectors/providers/jina-provider';
import { FirecrawlProvider, createFirecrawlProviderConfig } from '@/connectors/providers/firecrawl-provider';
import { AssemblyAIProvider, createAssemblyAIProviderConfig } from '@/connectors/providers/assemblyai-provider';
import { CONNECTOR_REGISTRY } from '@/connectors/index';
import { detectRuntime, assertRuntimeCompatible } from '@/core/runtime-guard';

describe('OpenAIProvider', () => {
  test('connector ID', () => {
    expect(OpenAIProvider.CONNECTOR_ID).toBe('openai.llm.v1');
  });
  test('default base URL', () => {
    const cfg = createOpenAIProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.openai.com');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(OpenAIProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createOpenAIProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('capabilities include chat-completion', () => {
    const cfg = createOpenAIProviderConfig({ apiKey: 'k' });
    expect(cfg.capabilities).toContain('generation.text-generation.chat-completion');
  });
  test('endpoint', () => {
    const p = new OpenAIProvider(createOpenAIProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('AnthropicProvider', () => {
  test('connector ID', () => {
    expect(AnthropicProvider.CONNECTOR_ID).toBe('anthropic.claude.v1');
  });
  test('default base URL', () => {
    const cfg = createAnthropicProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.anthropic.com');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(AnthropicProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createAnthropicProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new AnthropicProvider(createAnthropicProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/messages');
  });
});

describe('GeminiProvider', () => {
  test('connector ID', () => {
    expect(GeminiProvider.CONNECTOR_ID).toBe('google.gemini.v1');
  });
  test('default base URL', () => {
    const cfg = createGeminiProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://generativelanguage.googleapis.com');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(GeminiProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createGeminiProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new GeminiProvider(createGeminiProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('generateContent');
  });
});

describe('GroqProvider', () => {
  test('connector ID', () => {
    expect(GroqProvider.CONNECTOR_ID).toBe('groq.api.v1');
  });
  test('default base URL', () => {
    const cfg = createGroqProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.groq.com/openai');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(GroqProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createGroqProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new GroqProvider(createGroqProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('DeepSeekProvider', () => {
  test('connector ID', () => {
    expect(DeepSeekProvider.CONNECTOR_ID).toBe('deepseek.api.v1');
  });
  test('default base URL', () => {
    const cfg = createDeepSeekProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.deepseek.com');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(DeepSeekProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createDeepSeekProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new DeepSeekProvider(createDeepSeekProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('MistralProvider', () => {
  test('connector ID', () => {
    expect(MistralProvider.CONNECTOR_ID).toBe('mistral.api.v1');
  });
  test('default base URL', () => {
    const cfg = createMistralProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.mistral.ai');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(MistralProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createMistralProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new MistralProvider(createMistralProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('TogetherProvider', () => {
  test('connector ID', () => {
    expect(TogetherProvider.CONNECTOR_ID).toBe('together.api.v1');
  });
  test('default base URL', () => {
    const cfg = createTogetherProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.together.xyz');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(TogetherProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createTogetherProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new TogetherProvider(createTogetherProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('OpenRouterProvider', () => {
  test('connector ID', () => {
    expect(OpenRouterProvider.CONNECTOR_ID).toBe('openrouter.gateway.v1');
  });
  test('default base URL', () => {
    const cfg = createOpenRouterProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://openrouter.ai/api');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(OpenRouterProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createOpenRouterProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new OpenRouterProvider(createOpenRouterProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('XAIProvider', () => {
  test('connector ID', () => {
    expect(XAIProvider.CONNECTOR_ID).toBe('xai.grok.v1');
  });
  test('default base URL', () => {
    const cfg = createXAIProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.x.ai');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(XAIProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createXAIProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new XAIProvider(createXAIProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('CohereProvider', () => {
  test('connector ID', () => {
    expect(CohereProvider.CONNECTOR_ID).toBe('cohere.nlp.v1');
  });
  test('default base URL', () => {
    const cfg = createCohereProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.cohere.com');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(CohereProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createCohereProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new CohereProvider(createCohereProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v2/chat');
  });
});

describe('PerplexityProvider', () => {
  test('connector ID', () => {
    expect(PerplexityProvider.CONNECTOR_ID).toBe('perplexity.search.v1');
  });
  test('default base URL', () => {
    const cfg = createPerplexityProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.perplexity.ai');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(PerplexityProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createPerplexityProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new PerplexityProvider(createPerplexityProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/chat/completions');
  });
});

describe('ElevenLabsProvider', () => {
  test('connector ID', () => {
    expect(ElevenLabsProvider.CONNECTOR_ID).toBe('elevenlabs.tts.v1');
  });
  test('default base URL', () => {
    const cfg = createElevenLabsProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.elevenlabs.io');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(ElevenLabsProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createElevenLabsProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new ElevenLabsProvider(createElevenLabsProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/text-to-speech');
  });
});

describe('TavilyProvider', () => {
  test('connector ID', () => {
    expect(TavilyProvider.CONNECTOR_ID).toBe('tavily.search.v1');
  });
  test('default base URL', () => {
    const cfg = createTavilyProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.tavily.com');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(TavilyProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createTavilyProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new TavilyProvider(createTavilyProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/search');
  });
});

describe('SerperProvider', () => {
  test('connector ID', () => {
    expect(SerperProvider.CONNECTOR_ID).toBe('serper.search.v1');
  });
  test('default base URL', () => {
    const cfg = createSerperProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://google.serper.dev');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(SerperProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('endpoint', () => {
    const p = new SerperProvider(createSerperProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/search');
  });
});

describe('JinaProvider', () => {
  test('connector ID', () => {
    expect(JinaProvider.CONNECTOR_ID).toBe('jina.ai.v1');
  });
  test('default base URL', () => {
    const cfg = createJinaProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.jina.ai');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(JinaProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createJinaProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new JinaProvider(createJinaProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/embeddings');
  });
});

describe('FirecrawlProvider', () => {
  test('connector ID', () => {
    expect(FirecrawlProvider.CONNECTOR_ID).toBe('firecrawl.scrape.v1');
  });
  test('default base URL', () => {
    const cfg = createFirecrawlProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.firecrawl.dev');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(FirecrawlProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createFirecrawlProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new FirecrawlProvider(createFirecrawlProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v1/scrape');
  });
});

describe('AssemblyAIProvider', () => {
  test('connector ID', () => {
    expect(AssemblyAIProvider.CONNECTOR_ID).toBe('assemblyai.stt.v1');
  });
  test('default base URL', () => {
    const cfg = createAssemblyAIProviderConfig({ apiKey: 'k' });
    expect(cfg.baseUrl).toBe('https://api.assemblyai.com');
  });
  test('RUNTIME is NODE_ONLY', () => {
    expect(AssemblyAIProvider.RUNTIME).toBe(RuntimeEnvironment.NODE_ONLY);
  });
  test('has default models', () => {
    const cfg = createAssemblyAIProviderConfig({ apiKey: 'k' });
    expect(cfg.models.length).toBeGreaterThan(0);
  });
  test('endpoint', () => {
    const p = new AssemblyAIProvider(createAssemblyAIProviderConfig({ apiKey: 'k' }));
    expect((p as any)._getCompletionEndpoint()).toContain('/v2/transcript');
  });
});

// ---------------------------------------------------------------------------
// CONNECTOR_REGISTRY count
// ---------------------------------------------------------------------------

describe('CONNECTOR_REGISTRY', () => {
  test('should have 42 registered connectors', () => {
    expect(Object.keys(CONNECTOR_REGISTRY).length).toBe(42);
  });

  test('should include all cloud providers', () => {
    expect(CONNECTOR_REGISTRY['openai.llm.v1']).toBe(OpenAIProvider);
    expect(CONNECTOR_REGISTRY['anthropic.claude.v1']).toBe(AnthropicProvider);
    expect(CONNECTOR_REGISTRY['google.gemini.v1']).toBe(GeminiProvider);
    expect(CONNECTOR_REGISTRY['groq.api.v1']).toBe(GroqProvider);
    expect(CONNECTOR_REGISTRY['deepseek.api.v1']).toBe(DeepSeekProvider);
    expect(CONNECTOR_REGISTRY['mistral.api.v1']).toBe(MistralProvider);
    expect(CONNECTOR_REGISTRY['together.api.v1']).toBe(TogetherProvider);
    expect(CONNECTOR_REGISTRY['openrouter.gateway.v1']).toBe(OpenRouterProvider);
    expect(CONNECTOR_REGISTRY['xai.grok.v1']).toBe(XAIProvider);
    expect(CONNECTOR_REGISTRY['cohere.nlp.v1']).toBe(CohereProvider);
    expect(CONNECTOR_REGISTRY['perplexity.search.v1']).toBe(PerplexityProvider);
    expect(CONNECTOR_REGISTRY['elevenlabs.tts.v1']).toBe(ElevenLabsProvider);
    expect(CONNECTOR_REGISTRY['tavily.search.v1']).toBe(TavilyProvider);
    expect(CONNECTOR_REGISTRY['serper.search.v1']).toBe(SerperProvider);
    expect(CONNECTOR_REGISTRY['jina.ai.v1']).toBe(JinaProvider);
    expect(CONNECTOR_REGISTRY['firecrawl.scrape.v1']).toBe(FirecrawlProvider);
    expect(CONNECTOR_REGISTRY['assemblyai.stt.v1']).toBe(AssemblyAIProvider);
    expect(CONNECTOR_REGISTRY['azure.tts.v1']).toBe(AzureSpeechProvider);
  });

  test('should include all local providers', () => {
    expect(CONNECTOR_REGISTRY['ollama.local.v1']).toBe(OllamaProvider);
    expect(CONNECTOR_REGISTRY['lmstudio.local.v1']).toBe(LMStudioProvider);
    expect(CONNECTOR_REGISTRY['vllm.local.v1']).toBe(VLLMProvider);
    expect(CONNECTOR_REGISTRY['localai.local.v1']).toBe(LocalAIProvider);
  });
});

// ---------------------------------------------------------------------------
// Runtime Guard
// ---------------------------------------------------------------------------

describe('Runtime Guard', () => {
  test('detectRuntime returns NODE_ONLY in Node.js', () => {
    expect(detectRuntime()).toBe(RuntimeEnvironment.NODE_ONLY);
  });

  test('assertRuntimeCompatible passes for NODE_ONLY in Node.js', () => {
    expect(() => assertRuntimeCompatible('test.node', RuntimeEnvironment.NODE_ONLY)).not.toThrow();
  });

  test('assertRuntimeCompatible passes for UNIVERSAL', () => {
    expect(() => assertRuntimeCompatible('test.universal', RuntimeEnvironment.UNIVERSAL)).not.toThrow();
  });

  test('assertRuntimeCompatible throws for BROWSER_ONLY in Node.js', () => {
    expect(() => assertRuntimeCompatible('test.browser', RuntimeEnvironment.BROWSER_ONLY)).toThrow();
  });
});
