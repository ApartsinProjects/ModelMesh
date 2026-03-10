/**
 * Tests for MeshClient.
 */
import { MeshClient } from '@/client/mesh-client';
import { ModelMesh } from '@/core/mesh';
import { MeshConfig } from '@/config/mesh-config';
import type { ProviderConnector, CompletionResponse } from '@/interfaces/provider';
import { createDefaultCompletionResponse, createDefaultTokenUsage, createDefaultModelInfo } from '@/interfaces/provider';

function createMockProvider(overrides?: Partial<ProviderConnector>): ProviderConnector {
  const defaultResponse = createDefaultCompletionResponse({
    id: 'test-response',
    model: 'mock-model',
    choices: [{
      index: 0,
      message: { role: 'assistant', content: 'Hello from mock!' },
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

function createTestMesh(): ModelMesh {
  const mesh = new ModelMesh();
  const mockProvider = createMockProvider();

  mesh.initialize(new MeshConfig({
    providers: {
      'openai.llm.v1': {
        connector: 'openai.llm.v1',
        enabled: true,
        instance: mockProvider,
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
        strategy: 'stick-until-failure',
      },
    },
    observability: { connector: 'modelmesh.null.v1' },
  }));
  return mesh;
}

describe('MeshClient', () => {
  let mesh: ModelMesh;
  let client: MeshClient;

  beforeEach(() => {
    mesh = createTestMesh();
    client = new MeshClient(mesh);
  });

  // -- Namespaces ----------------------------------------------------------

  it('should expose chat namespace', () => {
    expect(client.chat).toBeDefined();
    expect(client.chat.completions).toBeDefined();
  });

  it('should expose embeddings namespace', () => {
    expect(client.embeddings).toBeDefined();
  });

  it('should expose models namespace', () => {
    expect(client.models).toBeDefined();
  });

  // -- chat.completions.create ---------------------------------------------

  it('should create a non-streaming completion', async () => {
    const response = await client.chat.completions.create({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
    }) as CompletionResponse;

    expect(response).toBeDefined();
    expect(response.choices.length).toBeGreaterThan(0);
    expect(response.choices[0].message?.content).toBe('Hello from mock!');
  });

  it('should create a streaming completion', async () => {
    const result = await client.chat.completions.create({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      stream: true,
    }) as AsyncIterableIterator<CompletionResponse>;

    const chunks: CompletionResponse[] = [];
    for await (const chunk of result) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
  });

  it('should pass temperature and maxTokens', async () => {
    const response = await client.chat.completions.create({
      model: 'chat-completion',
      messages: [{ role: 'user', content: 'Hello' }],
      temperature: 0.5,
      maxTokens: 100,
    }) as CompletionResponse;
    expect(response).toBeDefined();
  });

  // -- models.list ---------------------------------------------------------

  it('should list models', () => {
    const result = client.models.list();
    expect(result.object).toBe('list');
    expect(result.data.length).toBeGreaterThan(0);
    const ids = result.data.map((m) => m.id);
    expect(ids).toContain('openai.gpt-4o');
    expect(ids).toContain('openai.gpt-4o-mini');
  });

  it('should include owned_by in model entries', () => {
    const result = client.models.list();
    for (const entry of result.data) {
      expect(entry.owned_by).toBeDefined();
      expect(entry.object).toBe('model');
    }
  });

  // -- poolStatus ----------------------------------------------------------

  it('should return pool status for all pools', () => {
    const status = client.poolStatus();
    expect(status['chat-completion']).toBeDefined();
    expect(status['chat-completion'].total).toBe(2);
    expect(status['chat-completion'].active).toBeGreaterThan(0);
  });

  it('should return pool status for a specific pool', () => {
    const status = client.poolStatus('chat-completion');
    // When pool is specified, returns the bare status object (not wrapped)
    expect(status.total).toBe(2);
    expect(status.active).toBeGreaterThan(0);
  });

  it('should throw for unknown pool in poolStatus', () => {
    expect(() => client.poolStatus('nonexistent')).toThrow();
  });

  // -- activeProviders -----------------------------------------------------

  it('should return active providers', () => {
    const providers = client.activeProviders();
    expect(providers).toContain('openai.llm.v1');
  });

  // -- describe ------------------------------------------------------------

  it('should describe all pools', () => {
    const description = client.describe();
    expect(description).toContain('chat-completion');
    expect(description).toContain('openai.gpt-4o');
  });

  it('should describe a specific pool', () => {
    const description = client.describe('chat-completion');
    expect(description).toContain('chat-completion');
  });

  it('should throw for unknown pool in describe', () => {
    expect(() => client.describe('nonexistent')).toThrow();
  });

  // -- rotate --------------------------------------------------------------

  it('should rotate a pool', () => {
    const newModel = client.rotate('chat-completion');
    // After rotation, the second model should become current
    expect(newModel).toBe('openai.gpt-4o-mini');
  });

  // -- mesh accessor -------------------------------------------------------

  it('should expose the underlying mesh', () => {
    expect(client.mesh).toBe(mesh);
  });
});
