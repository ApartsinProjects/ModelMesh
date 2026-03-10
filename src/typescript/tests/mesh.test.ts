/**
 * Tests for ModelMesh facade.
 */
import { ModelMesh } from '@/core/mesh';
import { MeshConfig } from '@/config/mesh-config';
import type { CompletionRequest, CompletionResponse, ProviderConnector } from '@/interfaces/provider';
import { createDefaultCompletionResponse, createDefaultTokenUsage, createDefaultModelInfo } from '@/interfaces/provider';

function createStubProvider(): ProviderConnector {
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
  it('should initialize with config', () => {
    const mesh = createMeshWithStub();
    expect(Object.keys(mesh.pools)).toContain('chat-completion');
  });

  it('should throw if not initialized', () => {
    const mesh = new ModelMesh();
    expect(() => mesh.getRouter()).toThrow('not initialized');
  });

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

  it('should list active providers', () => {
    const mesh = createMeshWithStub();
    const active = mesh.activeProviders();
    expect(active).toContain('openai.llm.v1');
  });

  it('should list models', () => {
    const mesh = createMeshWithStub();
    const models = mesh.listModels();
    expect(models.length).toBe(1);
    expect(models[0].id).toBe('openai.gpt-4o');
    expect(models[0].owned_by).toBe('openai');
  });

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

  it('should throw for rotating unknown pool', () => {
    const mesh = createMeshWithStub();
    expect(() => mesh.rotate('nonexistent')).toThrow();
  });

  it('should shutdown cleanly', () => {
    const mesh = createMeshWithStub();
    mesh.shutdown();
    expect(() => mesh.getRouter()).toThrow('not initialized');
  });

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
});
