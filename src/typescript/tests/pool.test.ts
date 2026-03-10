/**
 * Tests for CapabilityPool.
 */
import { CapabilityPool, createPoolModel, poolModelToModelState } from '@/core/pool';
import { ModelStatus } from '@/interfaces/rotation';
import type { ModelState, SelectionStrategy } from '@/interfaces/rotation';
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

  // -- Creation and basic state -----------------------------------------------

  it('should create an empty pool', () => {
    expect(pool.models).toEqual([]);
    const status = pool.status();
    expect(status.total).toBe(0);
    expect(status.active).toBe(0);
  });

  it('should have poolId and config', () => {
    expect(pool.poolId).toBe('chat');
    expect(pool.config).toBeDefined();
    expect(pool.config.capability).toBe('generation.text-generation.chat-completion');
  });

  it('should default failure_threshold to 3', () => {
    pool.addModel(createPoolModel({
      modelId: 'm1', realModelId: 'm1', providerId: 'p1',
    }));
    // 2 failures should not deactivate
    pool.recordFailure('m1', new Error('fail'));
    pool.recordFailure('m1', new Error('fail'));
    expect(pool.models[0].status).toBe(ModelStatus.ACTIVE);
    // 3rd failure should deactivate
    pool.recordFailure('m1', new Error('fail'));
    expect(pool.models[0].status).toBe(ModelStatus.STANDBY);
  });

  it('should respect custom failure_threshold from config', () => {
    const customPool = new CapabilityPool('custom', { failure_threshold: 5 });
    customPool.addModel(createPoolModel({
      modelId: 'm1', realModelId: 'm1', providerId: 'p1',
    }));
    // 4 failures should not deactivate
    for (let i = 0; i < 4; i++) {
      customPool.recordFailure('m1', new Error('fail'));
    }
    expect(customPool.models[0].status).toBe(ModelStatus.ACTIVE);
    // 5th should deactivate
    customPool.recordFailure('m1', new Error('fail'));
    expect(customPool.models[0].status).toBe(ModelStatus.STANDBY);
  });

  // -- Adding and removing models ---------------------------------------------

  it('should add models with active status', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    expect(pool.models.length).toBe(1);
    expect(pool.models[0].status).toBe(ModelStatus.ACTIVE);
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
    }))).toThrow("already exists");
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

  it('should throw when removing non-existent model', () => {
    expect(() => pool.removeModel('nonexistent')).toThrow("not found");
  });

  it('should maintain correct state after adding multiple models', () => {
    pool.addModel(createPoolModel({ modelId: 'a', realModelId: 'a', providerId: 'p1' }));
    pool.addModel(createPoolModel({ modelId: 'b', realModelId: 'b', providerId: 'p2' }));
    pool.addModel(createPoolModel({ modelId: 'c', realModelId: 'c', providerId: 'p3' }));
    expect(pool.models.length).toBe(3);
    expect(pool.activeModels.length).toBe(3);
  });

  it('should return a copy of models array', () => {
    pool.addModel(createPoolModel({ modelId: 'a', realModelId: 'a', providerId: 'p1' }));
    const models1 = pool.models;
    const models2 = pool.models;
    expect(models1).not.toBe(models2);
    expect(models1).toEqual(models2);
  });

  // -- Selection --------------------------------------------------------------

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

  it('should return null from empty pool', () => {
    const emptyPool = new CapabilityPool('empty', {});
    const selected = emptyPool.select(dummyRequest);
    expect(selected).toBeNull();
  });

  it('should skip standby models during selection', () => {
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
    // Deactivate first model via failures
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    const selected = pool.select(dummyRequest);
    expect(selected).not.toBeNull();
    expect(selected!.modelId).toBe('anthropic.claude');
  });

  it('should return null when all models are standby', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    const selected = pool.select(dummyRequest);
    expect(selected).toBeNull();
  });

  it('should support custom selection strategy', () => {
    const reverseStrategy: SelectionStrategy = {
      select(candidates: ModelState[]): ModelState | null {
        const active = candidates.filter(c => c.status === ModelStatus.ACTIVE);
        return active.length > 0 ? active[active.length - 1] : null;
      },
      score(state: ModelState): number {
        return state.status === ModelStatus.ACTIVE ? 1.0 : 0.0;
      },
    };
    pool.setStrategy(reverseStrategy);
    pool.addModel(createPoolModel({ modelId: 'first', realModelId: 'first', providerId: 'p1' }));
    pool.addModel(createPoolModel({ modelId: 'last', realModelId: 'last', providerId: 'p2' }));
    const selected = pool.select(dummyRequest);
    expect(selected).not.toBeNull();
    expect(selected!.modelId).toBe('last');
  });

  // -- Rotation ---------------------------------------------------------------

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

  it('should return null when rotating last active model', () => {
    pool.addModel(createPoolModel({
      modelId: 'only-model',
      realModelId: 'only',
      providerId: 'p1',
    }));
    const rotated = pool.rotate();
    expect(rotated).toBeNull();
  });

  it('should return null when rotating empty pool', () => {
    const rotated = pool.rotate();
    expect(rotated).toBeNull();
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

  it('should rotate through all models and exhaust pool', () => {
    pool.addModel(createPoolModel({ modelId: 'a', realModelId: 'a', providerId: 'p1' }));
    pool.addModel(createPoolModel({ modelId: 'b', realModelId: 'b', providerId: 'p2' }));
    pool.rotate(); // a -> standby, returns b
    const last = pool.rotate(); // b -> standby, returns null
    expect(last).toBeNull();
    expect(pool.activeModels.length).toBe(0);
    expect(pool.standbyModels.length).toBe(2);
  });

  // -- recordSuccess ----------------------------------------------------------

  it('should record success and reset failure count', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    expect(pool.models[0].failureCount).toBe(2);
    pool.recordSuccess('openai.gpt-4o');
    expect(pool.models[0].failureCount).toBe(0);
    expect(pool.models[0].totalRequests).toBe(3);
  });

  it('should update lastSuccessAt on success', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordSuccess('openai.gpt-4o');
    expect(pool.models[0].lastSuccessAt).toBeDefined();
    expect(typeof pool.models[0].lastSuccessAt).toBe('number');
  });

  it('should silently ignore success for unknown model', () => {
    expect(() => pool.recordSuccess('nonexistent')).not.toThrow();
  });

  // -- recordFailure ----------------------------------------------------------

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

  it('should not deactivate below threshold', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    expect(pool.models[0].status).toBe(ModelStatus.ACTIVE);
    expect(pool.models[0].failureCount).toBe(2);
  });

  it('should update lastFailureAt on failure', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    expect(pool.models[0].lastFailureAt).toBeDefined();
    expect(typeof pool.models[0].lastFailureAt).toBe('number');
  });

  it('should increment totalRequests on failure', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    expect(pool.models[0].totalRequests).toBe(1);
  });

  it('should silently ignore failure for unknown model', () => {
    expect(() => pool.recordFailure('nonexistent', new Error('fail'))).not.toThrow();
  });

  // -- reactivate -------------------------------------------------------------

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
    expect(pool.models[0].failureCount).toBe(0);
  });

  it('should throw when reactivating unknown model', () => {
    expect(() => pool.reactivate('nonexistent')).toThrow("not found");
  });

  it('should reactivate model deactivated by failures', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    pool.recordFailure('openai.gpt-4o', new Error('fail'));
    expect(pool.models[0].status).toBe(ModelStatus.STANDBY);
    pool.reactivate('openai.gpt-4o');
    expect(pool.models[0].status).toBe(ModelStatus.ACTIVE);
    expect(pool.models[0].failureCount).toBe(0);
  });

  // -- status() ---------------------------------------------------------------

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

  it('should return status with currentModel for active pool', () => {
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
    expect(status).toHaveProperty('active');
    expect(status).toHaveProperty('standby');
    expect(status).toHaveProperty('total');
    expect(status).toHaveProperty('currentModel');
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
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));
    pool.recordFailure('openai.gpt-4o', new Error('timeout'));

    const status = pool.status();
    expect(status.active).toBe(0);
    expect(status.standby).toBe(1);
    expect(status.total).toBe(1);
    expect(status.currentModel).toBeNull();
  });

  it('should update status after rotation', () => {
    pool.addModel(createPoolModel({ modelId: 'a', realModelId: 'a', providerId: 'p1' }));
    pool.addModel(createPoolModel({ modelId: 'b', realModelId: 'b', providerId: 'p2' }));
    pool.rotate();
    const status = pool.status();
    expect(status.active).toBe(1);
    expect(status.standby).toBe(1);
    expect(status.currentModel).toBe('b');
  });

  // -- activeModels and standbyModels -----------------------------------------

  it('should get active models', () => {
    pool.addModel(createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    }));
    expect(pool.activeModels.length).toBe(1);
    expect(pool.activeModels[0].modelId).toBe('openai.gpt-4o');
  });

  it('should get standby models', () => {
    pool.addModel(createPoolModel({ modelId: 'a', realModelId: 'a', providerId: 'p1' }));
    pool.rotate();
    expect(pool.standbyModels.length).toBe(1);
    expect(pool.standbyModels[0].modelId).toBe('a');
  });

  it('should separate active and standby models', () => {
    pool.addModel(createPoolModel({ modelId: 'a', realModelId: 'a', providerId: 'p1' }));
    pool.addModel(createPoolModel({ modelId: 'b', realModelId: 'b', providerId: 'p2' }));
    pool.rotate(); // a becomes standby
    expect(pool.activeModels.length).toBe(1);
    expect(pool.standbyModels.length).toBe(1);
    expect(pool.activeModels[0].modelId).toBe('b');
    expect(pool.standbyModels[0].modelId).toBe('a');
  });
});

// -- createPoolModel ----------------------------------------------------------

describe('createPoolModel', () => {
  it('should create model with default values', () => {
    const model = createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
    });
    expect(model.status).toBe(ModelStatus.ACTIVE);
    expect(model.failureCount).toBe(0);
    expect(model.totalRequests).toBe(0);
    expect(model.totalTokens).toBe(0);
    expect(model.lastFailureAt).toBeUndefined();
    expect(model.lastSuccessAt).toBeUndefined();
  });

  it('should allow overriding default values', () => {
    const model = createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      status: ModelStatus.STANDBY,
      failureCount: 5,
      totalRequests: 100,
    });
    expect(model.status).toBe(ModelStatus.STANDBY);
    expect(model.failureCount).toBe(5);
    expect(model.totalRequests).toBe(100);
  });
});

// -- poolModelToModelState ----------------------------------------------------

describe('poolModelToModelState', () => {
  it('should convert PoolModel to ModelState', () => {
    const model = createPoolModel({
      modelId: 'openai.gpt-4o',
      realModelId: 'gpt-4o',
      providerId: 'openai.llm.v1',
      totalRequests: 10,
      totalTokens: 500,
      failureCount: 2,
    });
    const state = poolModelToModelState(model);
    expect(state.modelId).toBe('openai.gpt-4o');
    expect(state.status).toBe(ModelStatus.ACTIVE);
    expect(state.failureCount).toBe(2);
    expect(state.totalRequests).toBe(10);
    expect(state.totalTokens).toBe(500);
    expect(state.errorRate).toBe(0);
    expect(state.totalCost).toBe(0);
    expect(state.providerId).toBe('openai.llm.v1');
  });

  it('should preserve timestamps in conversion', () => {
    const now = Date.now() / 1000;
    const model = createPoolModel({
      modelId: 'm1',
      realModelId: 'm1',
      providerId: 'p1',
      lastSuccessAt: now,
      lastFailureAt: now - 100,
    });
    const state = poolModelToModelState(model);
    expect(state.lastSuccessAt).toBe(now);
    expect(state.lastFailureAt).toBe(now - 100);
  });
});
