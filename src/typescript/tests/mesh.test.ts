/**
 * Tests for ModelMesh facade.
 */
import { ModelMesh } from '@/core/mesh';
import { MeshConfig } from '@/config/mesh-config';
import type { CompletionRequest, CompletionResponse, ProviderConnector } from '@/interfaces/provider';
import { createDefaultCompletionResponse, createDefaultTokenUsage, createDefaultModelInfo } from '@/interfaces/provider';
import type { ObservabilityConnector, TraceEntry } from '@/interfaces/observability';
import { NullObservabilityConnector } from '@/connectors/observability/null-connector';

function createStubProvider(overrides?: Partial<ProviderConnector>): ProviderConnector {
  return {
    async complete(): Promise<CompletionResponse> {
      return createDefaultCompletionResponse({
        id: 'test',
        model: 'stub',
        choices: [{
          index: 0,
          message: { role: 'assistant', content: 'Hello from stub' },
          finishReason: 'stop',
        }],
        usage: createDefaultTokenUsage({ promptTokens: 5, completionTokens: 3, totalTokens: 8 }),
      });
    },
    async *stream(): AsyncIterableIterator<CompletionResponse> {
      yield createDefaultCompletionResponse({
        id: 'test-stream',
        model: 'stub',
        choices: [{
          index: 0,
          delta: { role: 'assistant', content: 'Hi' },
        }],
      });
    },
    getCapabilities: () => ['generation.text-generation.chat-completion'],
    supports: (cap: string) => cap === 'generation.text-generation.chat-completion',
    listModels: () => [
      createDefaultModelInfo({
        id: 'stub-model',
        name: 'Stub Model',
        capabilities: ['generation.text-generation.chat-completion'],
      }),
    ],
    getModelInfo: () => createDefaultModelInfo({ id: 'stub-model', name: 'Stub Model' }),
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

function createMeshWithStub() {
  const mesh = new ModelMesh();
  mesh.initialize(new MeshConfig({
    providers: {
      'openai.llm.v1': {
        connector: 'openai.llm.v1',
        enabled: true,
        instance: createStubProvider(),
      },
    },
    models: {
      'openai.gpt-4o': {
        provider: 'openai.llm.v1',
        capabilities: ['generation.text-generation.chat-completion'],
      },
    },
    pools: {
      'chat-completion': {
        capability: 'generation.text-generation.chat-completion',
        strategy: 'stick-until-failure',
      },
    },
  }));
  return mesh;
}

describe('ModelMesh', () => {
  // -- Initialization ---------------------------------------------------------

  it('should initialize with config', () => {
    const mesh = createMeshWithStub();
    expect(Object.keys(mesh.pools)).toContain('chat-completion');
  });

  it('should throw if getRouter called before initialize', () => {
    const mesh = new ModelMesh();
    expect(() => mesh.getRouter()).toThrow('not initialized');
  });

  it('should throw if getClient called before initialize', () => {
    const mesh = new ModelMesh();
    expect(() => mesh.getClient()).toThrow('not initialized');
  });

  it('should throw if route called before initialize', async () => {
    const mesh = new ModelMesh();
    await expect(mesh.route({
      model: 'chat',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: false,
      topP: 1.0,
    })).rejects.toThrow('not initialized');
  });

  it('should initialize with empty config', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({ providers: {}, models: {}, pools: {} }));
    expect(Object.keys(mesh.pools)).toEqual([]);
    expect(Object.keys(mesh.providers)).toEqual([]);
  });

  it('should return a router after initialization', () => {
    const mesh = createMeshWithStub();
    const router = mesh.getRouter();
    expect(router).toBeDefined();
    expect(router).not.toBeNull();
  });

  // -- Routing ----------------------------------------------------------------

  it('should route a non-streaming request', async () => {
    const mesh = createMeshWithStub();
    const response = await mesh.route({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: false,
      topP: 1.0,
    });
    expect(response).toBeDefined();
    expect(response.choices.length).toBeGreaterThan(0);
    expect(response.choices[0].message?.content).toBe('Hello from stub');
  });

  it('should route a streaming request', async () => {
    const mesh = createMeshWithStub();
    const chunks: CompletionResponse[] = [];
    for await (const chunk of mesh.routeStream({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: true,
      topP: 1.0,
    })) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
  });

  it('should throw when routing to unknown pool', async () => {
    const mesh = createMeshWithStub();
    await expect(mesh.route({
      model: 'nonexistent-pool',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: false,
      topP: 1.0,
    })).rejects.toThrow('No pool found');
  });

  // -- Pools and Models -------------------------------------------------------

  it('should list pools', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {},
      models: {},
      pools: {
        'chat': { capability: 'generation.text-generation.chat-completion' },
        'embed': { capability: 'representation.embeddings.text-embeddings' },
      },
    }));
    const pools = mesh.listPools();
    expect(pools.length).toBe(2);
  });

  it('should return pool status', () => {
    const mesh = createMeshWithStub();
    const status = mesh.poolStatus();
    expect(status['chat-completion']).toBeDefined();
    expect(status['chat-completion'].total).toBe(1);
    expect(status['chat-completion'].active).toBe(1);
  });

  it('should return empty pool status for empty pools', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {},
      models: {},
      pools: { 'empty': { capability: 'something' } },
    }));
    const status = mesh.poolStatus();
    expect(status['empty'].total).toBe(0);
    expect(status['empty'].active).toBe(0);
    expect(status['empty'].currentModel).toBeNull();
  });

  it('should list active providers', () => {
    const mesh = createMeshWithStub();
    const active = mesh.activeProviders();
    expect(active).toContain('openai.llm.v1');
  });

  it('should return empty active providers when no models', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({ providers: {}, models: {}, pools: {} }));
    expect(mesh.activeProviders()).toEqual([]);
  });

  it('should list models', () => {
    const mesh = createMeshWithStub();
    const models = mesh.listModels();
    expect(models.length).toBe(1);
    expect(models[0].id).toBe('openai.gpt-4o');
    expect(models[0].owned_by).toBe('openai');
  });

  it('should list models with correct object field', () => {
    const mesh = createMeshWithStub();
    const models = mesh.listModels();
    expect(models[0].object).toBe('model');
  });

  it('should deduplicate models across pools', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'openai.llm.v1': {
          connector: 'openai.llm.v1',
          enabled: true,
          instance: createStubProvider(),
        },
      },
      models: {
        'openai.gpt-4o': {
          provider: 'openai.llm.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
      },
      pools: {
        'pool1': { models: ['openai.gpt-4o'] },
        'pool2': { models: ['openai.gpt-4o'] },
      },
    }));
    const models = mesh.listModels();
    expect(models.length).toBe(1);
  });

  it('should handle model without dot in name for owned_by', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {},
      models: {
        'standalone-model': {
          provider: 'some-provider',
          capabilities: ['generation.text-generation.chat-completion'],
        },
      },
      pools: {
        'test-pool': { models: ['standalone-model'] },
      },
    }));
    const models = mesh.listModels();
    expect(models[0].owned_by).toBe('unknown');
  });

  // -- Rotation ---------------------------------------------------------------

  it('should rotate a pool', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'openai.llm.v1': {
          connector: 'openai.llm.v1',
          enabled: true,
          instance: createStubProvider(),
        },
      },
      models: {
        'openai.gpt-4o': {
          provider: 'openai.llm.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
        'openai.gpt-4o-mini': {
          provider: 'openai.llm.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
      },
      pools: {
        'chat-completion': {
          capability: 'generation.text-generation.chat-completion',
        },
      },
    }));
    const newModel = mesh.rotate('chat-completion');
    expect(newModel).not.toBeNull();
  });

  it('should return null when rotating pool with single model', () => {
    const mesh = createMeshWithStub();
    const result = mesh.rotate('chat-completion');
    // After rotating, the single model goes to standby, no alternative
    expect(result).toBeNull();
  });

  it('should throw for rotating unknown pool', () => {
    const mesh = createMeshWithStub();
    expect(() => mesh.rotate('nonexistent')).toThrow("Pool 'nonexistent' not found");
  });

  // -- Shutdown ---------------------------------------------------------------

  it('should shutdown cleanly', () => {
    const mesh = createMeshWithStub();
    mesh.shutdown();
    expect(() => mesh.getRouter()).toThrow('not initialized');
  });

  it('should throw on route after shutdown', async () => {
    const mesh = createMeshWithStub();
    mesh.shutdown();
    await expect(mesh.route({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 1.0,
      stream: false,
      topP: 1.0,
    })).rejects.toThrow('not initialized');
  });

  it('should allow re-initialization after shutdown', () => {
    const mesh = createMeshWithStub();
    mesh.shutdown();
    mesh.initialize(new MeshConfig({ providers: {}, models: {}, pools: {} }));
    expect(() => mesh.getRouter()).not.toThrow();
  });

  // -- Capability auto-discovery ----------------------------------------------

  it('should auto-discover capabilities from provider', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'openai.llm.v1': {
          connector: 'openai.llm.v1',
          enabled: true,
          instance: createStubProvider(),
        },
      },
      models: {
        'openai.stub-model': {
          provider: 'openai.llm.v1',
          // No capabilities - should be auto-discovered from provider
        },
      },
      pools: {
        'chat-completion': {
          capability: 'generation.text-generation.chat-completion',
        },
      },
    }));
    const status = mesh.poolStatus();
    expect(status['chat-completion']).toBeDefined();
  });

  it('should prefer config capabilities over provider', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'openai.llm.v1': {
          connector: 'openai.llm.v1',
          enabled: true,
          instance: createStubProvider(),
        },
      },
      models: {
        'openai.gpt-4o': {
          provider: 'openai.llm.v1',
          capabilities: ['custom.capability'],
        },
      },
      pools: {
        'custom-pool': {
          capability: 'custom.capability',
        },
      },
    }));
    const status = mesh.poolStatus();
    expect(status['custom-pool'].total).toBe(1);
  });

  // -- Accessors --------------------------------------------------------------

  it('should expose event emitter', () => {
    const mesh = createMeshWithStub();
    expect(mesh.eventEmitter).toBeDefined();
  });

  it('should expose state manager', () => {
    const mesh = createMeshWithStub();
    expect(mesh.stateManager).toBeDefined();
  });

  it('should expose capability tree', () => {
    const mesh = createMeshWithStub();
    expect(mesh.capabilityTree).toBeDefined();
    expect(mesh.capabilityTree.contains('generation.text-generation.chat-completion')).toBe(true);
  });

  it('should return copies from pools getter', () => {
    const mesh = createMeshWithStub();
    const pools1 = mesh.pools;
    const pools2 = mesh.pools;
    expect(pools1).not.toBe(pools2);
    expect(pools1).toEqual(pools2);
  });

  it('should return copies from providers getter', () => {
    const mesh = createMeshWithStub();
    const providers1 = mesh.providers;
    const providers2 = mesh.providers;
    expect(providers1).not.toBe(providers2);
  });

  // -- Disabled providers -----------------------------------------------------

  it('should handle disabled providers', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'disabled.v1': {
          connector: 'disabled.v1',
          enabled: false,
          instance: createStubProvider(),
        },
      },
      models: {},
      pools: {},
    }));
    expect(Object.keys(mesh.providers)).not.toContain('disabled.v1');
  });

  // -- Observability ----------------------------------------------------------

  it('should return observability connector', () => {
    const mesh = createMeshWithStub();
    const obs = mesh.observability;
    expect(obs).toBeDefined();
  });

  it('should lazily create NullObservabilityConnector if none set', () => {
    const mesh = new ModelMesh();
    const obs = mesh.observability;
    expect(obs).toBeInstanceOf(NullObservabilityConnector);
  });

  it('should allow setting observability connector before initialize', () => {
    const mesh = new ModelMesh();
    const traces: TraceEntry[] = [];
    const customObs: ObservabilityConnector = {
      emit: () => {},
      log: () => {},
      flush: () => {},
      trace: (entry: TraceEntry) => { traces.push(entry); },
    };
    mesh.observability = customObs;
    mesh.initialize(new MeshConfig({ providers: {}, models: {}, pools: {} }));
    expect(traces.length).toBeGreaterThan(0);
    expect(traces.some(t => t.message.includes('Initialized'))).toBe(true);
  });

  it('should allow setting observability to null', () => {
    const mesh = new ModelMesh();
    mesh.observability = null;
    expect(mesh.observability).toBeInstanceOf(NullObservabilityConnector);
  });

  // -- Pool configuration modes -----------------------------------------------

  it('should setup pools with explicit model list', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'openai.llm.v1': {
          connector: 'openai.llm.v1',
          enabled: true,
          instance: createStubProvider(),
        },
      },
      models: {
        'openai.gpt-4o': {
          provider: 'openai.llm.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
        'openai.gpt-4o-mini': {
          provider: 'openai.llm.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
      },
      pools: {
        'my-pool': { models: ['openai.gpt-4o'] },
      },
    }));
    const status = mesh.poolStatus();
    expect(status['my-pool'].total).toBe(1);
  });

  it('should setup pools with hybrid capability + explicit models', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'openai.llm.v1': {
          connector: 'openai.llm.v1',
          enabled: true,
          instance: createStubProvider(),
        },
      },
      models: {
        'openai.gpt-4o': {
          provider: 'openai.llm.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
        'openai.gpt-4o-mini': {
          provider: 'openai.llm.v1',
          capabilities: ['other.capability'],
        },
      },
      pools: {
        'hybrid-pool': {
          capability: 'generation.text-generation.chat-completion',
          models: ['openai.gpt-4o-mini'],
        },
      },
    }));
    const status = mesh.poolStatus();
    // Should include gpt-4o by capability match + gpt-4o-mini by explicit list
    expect(status['hybrid-pool'].total).toBe(2);
  });

  // -- Multiple providers -----------------------------------------------------

  it('should support multiple different providers', () => {
    const mesh = new ModelMesh();
    mesh.initialize(new MeshConfig({
      providers: {
        'openai.llm.v1': {
          connector: 'openai.llm.v1',
          enabled: true,
          instance: createStubProvider(),
        },
        'anthropic.claude.v1': {
          connector: 'anthropic.claude.v1',
          enabled: true,
          instance: createStubProvider(),
        },
      },
      models: {
        'openai.gpt-4o': {
          provider: 'openai.llm.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
        'anthropic.claude-sonnet': {
          provider: 'anthropic.claude.v1',
          capabilities: ['generation.text-generation.chat-completion'],
        },
      },
      pools: {
        'chat': {
          capability: 'generation.text-generation.chat-completion',
        },
      },
    }));
    const status = mesh.poolStatus();
    expect(status['chat'].total).toBe(2);
    const active = mesh.activeProviders();
    expect(active).toContain('openai.llm.v1');
    expect(active).toContain('anthropic.claude.v1');
  });

  // -- getClient --------------------------------------------------------------

  it('should return a MeshClient from getClient', () => {
    const mesh = createMeshWithStub();
    const client = mesh.getClient();
    expect(client).toBeDefined();
  });
});
