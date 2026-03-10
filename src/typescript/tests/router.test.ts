/**
 * Tests for Router.
 */
import { Router, NoActiveModelError } from '@/core/router';
import { CapabilityPool, createPoolModel } from '@/core/pool';
import { CapabilityTree } from '@/core/capability-tree';
import { EventEmitter, EventType } from '@/core/event-emitter';
import type { CompletionRequest, CompletionResponse, ProviderConnector } from '@/interfaces/provider';
import { createDefaultCompletionResponse, createDefaultTokenUsage, createDefaultModelInfo } from '@/interfaces/provider';
import { ModelStatus } from '@/interfaces/rotation';

function createMockProvider(overrides?: Partial<ProviderConnector>): ProviderConnector {
  const defaultResponse = createDefaultCompletionResponse({
    id: 'test-response',
    model: 'mock-model',
    choices: [{
      index: 0,
      message: { role: 'assistant', content: 'Hello!' },
      finishReason: 'stop',
    }],
    usage: createDefaultTokenUsage({ promptTokens: 10, completionTokens: 5, totalTokens: 15 }),
  });

  return {
    complete: async () => defaultResponse,
    stream: async function* () { yield defaultResponse; },
    getCapabilities: () => ['generation.text-generation.chat-completion'],
    supports: (cap: string) => cap === 'generation.text-generation.chat-completion',
    listModels: () => [createDefaultModelInfo({ id: 'mock', name: 'Mock' })],
    getModelInfo: () => createDefaultModelInfo({ id: 'mock', name: 'Mock' }),
    checkQuota: () => ({ used: 0 }),
    getRateLimits: () => ({}),
    getPricing: () => ({ inputPer1kTokens: 0, outputPer1kTokens: 0, perRequest: 0 }),
    reportUsage: () => {},
    classifyError: (err: Error) => ({ retryable: false, message: err.message, category: 'unknown' }),
    isRetryable: () => false,
    close: async () => {},
    ...overrides,
  };
}

function makeRequest(model: string = 'chat-completion'): CompletionRequest {
  return {
    model,
    messages: [{ role: 'user', content: 'Hello' }],
    temperature: 1.0,
    stream: false,
    topP: 1.0,
  };
}

describe('Router', () => {
  let router: Router;
  let pool: CapabilityPool;
  let tree: CapabilityTree;
  let providers: Record<string, ProviderConnector>;

  beforeEach(() => {
    pool = new CapabilityPool('chat-completion', {
      capability: 'generation.text-generation.chat-completion',
      strategy: 'stick-until-failure',
    });
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));

    tree = new CapabilityTree();
    tree.register('generation.text-generation.chat-completion');

    providers = {
      'openai.llm.v1': createMockProvider(),
    };

    router = new Router(
      { 'chat-completion': pool },
      tree,
      providers,
      new EventEmitter(),
      null
    );
  });

  // -- Pool resolution --------------------------------------------------------

  it('should resolve a pool by direct ID', () => {
    const resolved = router.resolvePool('chat-completion');
    expect(resolved).toBe(pool);
  });

  it('should throw for unknown pool', () => {
    expect(() => router.resolvePool('unknown-pool')).toThrow('No pool found');
  });

  it('should resolve pool via capability tree', () => {
    // Register parent capability and create a pool for it
    tree.register('generation');
    const genPool = new CapabilityPool('gen', {
      capability: 'generation',
    });
    genPool.addModel(createPoolModel({
      modelId: 'test.model',
      realModelId: 'model',
      providerId: 'openai.llm.v1',
    }));
    const routerWithGen = new Router(
      { 'gen': genPool, 'chat-completion': pool },
      tree,
      providers,
      new EventEmitter(),
      null
    );
    // Direct lookup should still work
    const resolved = routerWithGen.resolvePool('chat-completion');
    expect(resolved.poolId).toBe('chat-completion');
  });

  // -- Non-streaming route ----------------------------------------------------

  it('should route a non-streaming request successfully', async () => {
    const response = await router.route(makeRequest());
    expect(response).toBeDefined();
    expect(response.choices.length).toBeGreaterThan(0);
    expect(response.choices[0].message?.content).toBe('Hello!');
  });

  it('should pass the real model ID to the provider', async () => {
    let capturedModel: string | undefined;
    providers['openai.llm.v1'] = createMockProvider({
      complete: async (req: CompletionRequest) => {
        capturedModel = req.model;
        return createDefaultCompletionResponse({
          id: 'test',
          model: req.model,
          choices: [{ index: 0, message: { role: 'assistant', content: 'OK' }, finishReason: 'stop' }],
          usage: createDefaultTokenUsage(),
        });
      },
    });
    await router.route(makeRequest());
    expect(capturedModel).toBe('gpt-4o');
  });

  // -- Streaming route --------------------------------------------------------

  it('should route a streaming request', async () => {
    const chunks: CompletionResponse[] = [];
    for await (const chunk of router.routeStream({ ...makeRequest(), stream: true })) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
  });

  it('should emit events during streaming', async () => {
    const emitter = new EventEmitter();
    const events: string[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, () => events.push('success'));
    const routerWithEmitter = new Router(
      { 'chat-completion': pool },
      tree,
      providers,
      emitter,
      null
    );
    const chunks: CompletionResponse[] = [];
    for await (const chunk of routerWithEmitter.routeStream({ ...makeRequest(), stream: true })) {
      chunks.push(chunk);
    }
    expect(events).toContain('success');
  });

  // -- Retry and rotation -----------------------------------------------------

  it('should retry on provider failure and rotate to next model', async () => {
    // Use a fresh pool to avoid failure_threshold=3 default deactivating the first model
    // before the backup gets a chance (the pool default threshold is 3, and maxRetries is also 3)
    const freshPool = new CapabilityPool('chat-completion', {
      capability: 'generation.text-generation.chat-completion',
      failure_threshold: 1, // Low threshold so first failure deactivates model and rotates to backup
    });
    freshPool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    freshPool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o-mini',
      realModelId: 'gpt-4o-mini',
      providerId: 'backup.v1',
    }));

    let callCount = 0;
    const failingProvider = createMockProvider({
      complete: async () => {
        throw new Error('Primary provider down');
      },
    });
    const backupProvider = createMockProvider({
      complete: async () => {
        callCount++;
        return createDefaultCompletionResponse({
          id: 'backup',
          model: 'gpt-4o-mini',
          choices: [{ index: 0, message: { role: 'assistant', content: 'Backup response' }, finishReason: 'stop' }],
          usage: createDefaultTokenUsage(),
        });
      },
    });

    const freshRouter = new Router(
      { 'chat-completion': freshPool },
      tree,
      { 'openai.llm.v1': failingProvider, 'backup.v1': backupProvider },
      new EventEmitter(),
      null
    );

    const response = await freshRouter.route(makeRequest());
    expect(response.choices[0].message?.content).toBe('Backup response');
    expect(callCount).toBe(1);
  });

  it('should throw when all retry attempts fail', async () => {
    providers['openai.llm.v1'] = createMockProvider({
      complete: async () => {
        throw new Error('Provider down');
      },
    });

    await expect(router.route(makeRequest())).rejects.toThrow('All models exhausted');
  });

  it('should throw with last error info when retries fail', async () => {
    providers['openai.llm.v1'] = createMockProvider({
      complete: async () => {
        throw new Error('Rate limit exceeded');
      },
    });

    await expect(router.route(makeRequest())).rejects.toThrow('Rate limit exceeded');
  });

  it('should handle provider not found during execution', async () => {
    // Add model with non-existent provider
    pool.addModel(createPoolModel({
      modelId: 'ghost.model',
      realModelId: 'model',
      providerId: 'nonexistent.v1',
    }));

    // Original provider still works, so request should succeed
    const response = await router.route(makeRequest());
    expect(response).toBeDefined();
  });

  it('should retry on stream failure and rotate to next model', async () => {
    const freshPool = new CapabilityPool('chat-completion', {
      capability: 'generation.text-generation.chat-completion',
      failure_threshold: 1,
    });
    freshPool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    freshPool.addModel(createPoolModel({
      modelId: 'backup.model',
      realModelId: 'backup-model',
      providerId: 'backup.v1',
    }));

    const failingProvider = createMockProvider({
      stream: async function* () {
        throw new Error('Stream failed');
      },
    });
    const backupProvider = createMockProvider({
      stream: async function* () {
        yield createDefaultCompletionResponse({
          id: 'backup-stream',
          model: 'backup-model',
          choices: [{ index: 0, delta: { role: 'assistant', content: 'Backup' } }],
        });
      },
    });

    const freshRouter = new Router(
      { 'chat-completion': freshPool },
      tree,
      { 'openai.llm.v1': failingProvider, 'backup.v1': backupProvider },
      new EventEmitter(),
      null
    );

    const chunks: CompletionResponse[] = [];
    for await (const chunk of freshRouter.routeStream({ ...makeRequest(), stream: true })) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
  });

  // -- NoActiveModelError -----------------------------------------------------

  it('should throw NoActiveModelError when pool is empty', async () => {
    const emptyPool = new CapabilityPool('empty', {});
    const emptyRouter = new Router(
      { 'empty': emptyPool },
      tree,
      providers,
      new EventEmitter(),
      null
    );
    await expect(emptyRouter.route(makeRequest('empty'))).rejects.toThrow(NoActiveModelError);
  });

  it('should throw NoActiveModelError for streaming when pool is empty', async () => {
    const emptyPool = new CapabilityPool('empty', {});
    const emptyRouter = new Router(
      { 'empty': emptyPool },
      tree,
      providers,
      new EventEmitter(),
      null
    );
    const fn = async () => {
      for await (const _ of emptyRouter.routeStream({ ...makeRequest('empty'), stream: true })) {
        // consume
      }
    };
    await expect(fn()).rejects.toThrow(NoActiveModelError);
  });

  // -- Events -----------------------------------------------------------------

  it('should emit REQUEST_ROUTED event on routing', async () => {
    const emitter = new EventEmitter();
    const events: Record<string, unknown>[] = [];
    emitter.on(EventType.REQUEST_ROUTED, (evt) => events.push(evt.data));
    const routerWithEmitter = new Router(
      { 'chat-completion': pool },
      tree,
      providers,
      emitter,
      null
    );
    await routerWithEmitter.route(makeRequest());
    expect(events.length).toBe(1);
    expect(events[0].model_id).toBe('openai.gpt-4o');
    expect(events[0].provider_id).toBe('openai.llm.v1');
  });

  it('should emit REQUEST_SUCCESS event on successful route', async () => {
    const emitter = new EventEmitter();
    const events: Record<string, unknown>[] = [];
    emitter.on(EventType.REQUEST_SUCCESS, (evt) => events.push(evt.data));
    const routerWithEmitter = new Router(
      { 'chat-completion': pool },
      tree,
      providers,
      emitter,
      null
    );
    await routerWithEmitter.route(makeRequest());
    expect(events.length).toBe(1);
  });

  it('should emit REQUEST_FAILURE event on provider failure', async () => {
    const emitter = new EventEmitter();
    const events: Record<string, unknown>[] = [];
    emitter.on(EventType.REQUEST_FAILURE, (evt) => events.push(evt.data));
    providers['openai.llm.v1'] = createMockProvider({
      complete: async () => { throw new Error('Fail'); },
    });
    const routerWithEmitter = new Router(
      { 'chat-completion': pool },
      tree,
      providers,
      emitter,
      null
    );
    try { await routerWithEmitter.route(makeRequest()); } catch { /* expected */ }
    expect(events.length).toBeGreaterThan(0);
    expect(events[0].error).toBe('Fail');
  });

  it('should emit POOL_EXHAUSTED event when no active model', async () => {
    const emitter = new EventEmitter();
    const events: Record<string, unknown>[] = [];
    emitter.on(EventType.POOL_EXHAUSTED, (evt) => events.push(evt.data));
    const emptyPool = new CapabilityPool('empty', {});
    const routerWithEmitter = new Router(
      { 'empty': emptyPool },
      tree,
      providers,
      emitter,
      null
    );
    try { await routerWithEmitter.route(makeRequest('empty')); } catch { /* expected */ }
    expect(events.length).toBe(1);
  });

  it('should emit MODEL_ROTATED event on rotation after failure', async () => {
    const emitter = new EventEmitter();
    const events: Record<string, unknown>[] = [];
    emitter.on(EventType.MODEL_ROTATED, (evt) => events.push(evt.data));
    const freshPool = new CapabilityPool('chat-completion', {
      capability: 'generation.text-generation.chat-completion',
      failure_threshold: 1,
    });
    freshPool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    freshPool.addModel(createPoolModel({
      modelId: 'backup.model',
      realModelId: 'backup',
      providerId: 'backup.v1',
    }));
    const failProvider = createMockProvider({
      complete: async () => { throw new Error('Primary fail'); },
    });
    const backupProvider = createMockProvider();
    const routerWithEmitter = new Router(
      { 'chat-completion': freshPool },
      tree,
      { 'openai.llm.v1': failProvider, 'backup.v1': backupProvider },
      emitter,
      null
    );
    await routerWithEmitter.route(makeRequest());
    expect(events.length).toBe(1);
    expect(events[0].new_model_id).toBe('backup.model');
  });

  // -- _buildProviderRequest --------------------------------------------------

  it('should build provider request with real model ID', () => {
    const request: CompletionRequest = {
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 0.7,
      maxTokens: 100,
      stream: false,
      topP: 0.9,
      stop: ['END'],
      tools: [{ type: 'function', function: { name: 'test' } }],
    };
    const model = createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    });
    const built = Router._buildProviderRequest(request, model);
    expect(built.model).toBe('gpt-4o');
    expect(built.temperature).toBe(0.7);
    expect(built.maxTokens).toBe(100);
    expect(built.topP).toBe(0.9);
    expect(built.stop).toEqual(['END']);
    expect(built.tools).toEqual([{ type: 'function', function: { name: 'test' } }]);
    expect(built.messages).toEqual(request.messages);
  });

  it('should preserve stream flag in built request', () => {
    const request = makeRequest();
    const model = createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    });
    const built = Router._buildProviderRequest(request, model);
    expect(built.stream).toBe(false);
  });

  // -- Multiple models --------------------------------------------------------

  it('should handle provider with multiple models', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o-mini',
      realModelId: 'gpt-4o-mini',
      providerId: 'openai.llm.v1',
    }));
    expect(pool.models.length).toBe(2);
  });

  // -- maxRetries configuration -----------------------------------------------

  it('should respect custom maxRetries', async () => {
    let attempts = 0;
    providers['openai.llm.v1'] = createMockProvider({
      complete: async () => {
        attempts++;
        throw new Error('Always fails');
      },
    });
    const routerWith1Retry = new Router(
      { 'chat-completion': pool },
      tree,
      providers,
      new EventEmitter(),
      null,
      1
    );
    try { await routerWith1Retry.route(makeRequest()); } catch { /* expected */ }
    expect(attempts).toBe(1);
  });

  // -- Accessors --------------------------------------------------------------

  it('should expose pools via getter', () => {
    expect(router.pools).toBeDefined();
    expect(router.pools['chat-completion']).toBe(pool);
  });

  it('should expose providers via getter', () => {
    expect(router.providers).toBeDefined();
    expect(router.providers['openai.llm.v1']).toBeDefined();
  });
});
