/**
 * Tests for CapabilityPool.
 */
import { CapabilityPool, createPoolModel } from '@/core/pool';
import { ModelStatus } from '@/interfaces/rotation';
import type { CompletionRequest } from '@/interfaces/provider';

const dummyRequest: CompletionRequest = {
  model: 'test',
  messages: [{ role: 'user', content: 'hello' }],
  temperature: 1.0,
  stream: false,
  topP: 1.0,
};

describe('CapabilityPool', () => {
  let pool: CapabilityPool;

  beforeEach(() => {
    pool = new CapabilityPool('chat', {
      capability: 'generation.text-generation.chat-completion',
      strategy: 'stick-until-failure',
    });
  });

  it('should create an empty pool', () => {
    expect(pool.models).toEqual([]);
    const status = pool.status();
    expect(status.total).toBe(0);
    expect(status.active).toBe(0);
  });

  it('should add models with active status', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    expect(pool.models.length).toBe(1);
    expect(pool.models[0].status).toBe(ModelStatus.ACTIVE);
  });

  it('should select the first active model', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.addModel(createPoolModel({
      modelId: 'anthropic.claude',
      realModelId: 'claude',
      providerId: 'anthropic.claude.v1',
    }));
    const selected = pool.select(dummyRequest);
    expect(selected).not.toBeNull();
    expect(selected!.modelId).toBe('openai.gpt-4o');
  });

  it('should rotate to next model', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.addModel(createPoolModel({
      modelId: 'anthropic.claude',
      realModelId: 'claude',
      providerId: 'anthropic.claude.v1',
    }));
    const rotated = pool.rotate();
    expect(rotated).not.toBeNull();
    expect(rotated!.modelId).toBe('anthropic.claude');
  });

  it('should report correct status', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.addModel(createPoolModel({
      modelId: 'anthropic.claude',
      realModelId: 'claude',
      providerId: 'anthropic.claude.v1',
    }));
    const status = pool.status();
    expect(status.total).toBe(2);
    expect(status.active).toBe(2);
    expect(status.standby).toBe(0);
  });

  it('should record success', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordSuccess('openai.gpt-4o');
    const selected = pool.select(dummyRequest);
    expect(selected!.modelId).toBe('openai.gpt-4o');
  });

  it('should return null from empty pool', () => {
    const emptyPool = new CapabilityPool('empty', {});
    const selected = emptyPool.select(dummyRequest);
    expect(selected).toBeNull();
  });

  it('should get active models', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    expect(pool.activeModels.length).toBe(1);
    expect(pool.activeModels[0].modelId).toBe('openai.gpt-4o');
  });

  it('should have poolId and config', () => {
    expect(pool.poolId).toBe('chat');
    expect(pool.config).toBeDefined();
  });

  it('should handle multiple adds and rotations', () => {
    pool.addModel(createPoolModel({ modelId: 'a', realModelId: 'a', providerId: 'p1' }));
    pool.addModel(createPoolModel({ modelId: 'b', realModelId: 'b', providerId: 'p2' }));
    pool.addModel(createPoolModel({ modelId: 'c', realModelId: 'c', providerId: 'p3' }));
    expect(pool.models.length).toBe(3);

    pool.rotate(); // skip a, select b
    pool.rotate(); // skip b, select c
    const selected = pool.select(dummyRequest);
    expect(selected).not.toBeNull();
    expect(selected!.modelId).toBe('c');
  });

  it('should record failure and deactivate after threshold', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    expect(pool.models[0].status).toBe(ModelStatus.STANDBY);
  });

  it('should throw when adding duplicate model', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    expect(() => pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }))).toThrow();
  });

  it('should remove a model', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.removeModel('openai.gpt-4o');
    expect(pool.models.length).toBe(0);
  });

  it('should reactivate a standby model', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.rotate(); // deactivates it
    expect(pool.models[0].status).toBe(ModelStatus.STANDBY);
    pool.reactivate('openai.gpt-4o');
    expect(pool.models[0].status).toBe(ModelStatus.ACTIVE);
  });

  // -- status() shape -------------------------------------------------------

  it('should return status with currentModel (camelCase) for active pool', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.addModel(createPoolModel({
      modelId: 'anthropic.claude',
      realModelId: 'claude',
      providerId: 'anthropic.claude.v1',
    }));

    const status = pool.status();

    // Verify the shape has exactly the expected keys
    expect(status).toHaveProperty('active');
    expect(status).toHaveProperty('standby');
    expect(status).toHaveProperty('total');
    expect(status).toHaveProperty('currentModel');

    // Verify values
    expect(status.active).toBe(2);
    expect(status.standby).toBe(0);
    expect(status.total).toBe(2);
    expect(status.currentModel).toBe('openai.gpt-4o');
  });

  it('should return null currentModel when all models are standby', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    // Force the model to standby by recording enough failures
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));

    const status = pool.status();

    expect(status.active).toBe(0);
    expect(status.standby).toBe(1);
    expect(status.total).toBe(1);
    expect(status.currentModel).toBeNull();
  });
});
