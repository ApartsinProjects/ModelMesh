/**
 * Tests for Router.
 */
import { Router } from '@/core/router';
import { CapabilityPool, createPoolModel } from '@/core/pool';
import { CapabilityTree } from '@/core/capability-tree';
import { EventEmitter } from '@/core/event-emitter';
import type { CompletionRequest, CompletionResponse, ProviderConnector } from '@/interfaces/provider';
import { createDefaultCompletionResponse, createDefaultTokenUsage, createDefaultModelInfo } from '@/interfaces/provider';

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

  it('should resolve a pool by model name', () => {
    const resolved = router.resolvePool('chat-completion');
    expect(resolved).toBe(pool);
  });

  it('should throw for unknown pool', () => {
    expect(() => router.resolvePool('unknown-pool')).toThrow();
  });

  it('should route a non-streaming request successfully', async () => {
    const request: CompletionRequest = {
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: false,
      topP: 1.0,
    };
    const response = await router.route(request);
    expect(response).toBeDefined();
    expect(response.choices.length).toBeGreaterThan(0);
    expect(response.choices[0].message?.content).toBe('Hello!');
  });

  it('should route a streaming request', async () => {
    const request: CompletionRequest = {
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: true,
      topP: 1.0,
    };
    const chunks: CompletionResponse[] = [];
    for await (const chunk of router.routeStream(request)) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
  });

  it('should handle provider with multiple models', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o-mini',
      realModelId: 'gpt-4o-mini',
      providerId: 'openai.llm.v1',
    }));
    expect(pool.models.length).toBe(2);
  });

  it('should throw NoActiveModelError when pool is empty', async () => {
    const emptyPool = new CapabilityPool('empty', {});
    const emptyRouter = new Router(
      { 'empty': emptyPool },
      tree,
      providers,
      new EventEmitter(),
      null
    );
    await expect(emptyRouter.route({
      model: 'empty',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: false,
      topP: 1.0,
    })).rejects.toThrow();
  });
});
