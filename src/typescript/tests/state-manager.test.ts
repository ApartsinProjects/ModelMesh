/**
 * Tests for StateManager.
 */
import { StateManager } from '@/core/state-manager';
import { ModelStatus } from '@/interfaces/rotation';

describe('StateManager', () => {
  let sm: StateManager;

  beforeEach(() => {
    sm = new StateManager();
  });

  it('should create new state on getOrCreate', () => {
    const state = sm.getOrCreate('model-1');
    expect(state).toBeDefined();
    expect(state.failureCount).toBe(0);
    expect(state.totalRequests).toBe(0);
    expect(state.modelId).toBe('model-1');
    expect(state.status).toBe(ModelStatus.ACTIVE);
  });

  it('should return same state for same model ID', () => {
    const state1 = sm.getOrCreate('model-1');
    const state2 = sm.getOrCreate('model-1');
    expect(state1).toBe(state2);
  });

  it('should record success', () => {
    sm.recordSuccess('model-1', 100);
    const state = sm.getOrCreate('model-1');
    expect(state.totalRequests).toBe(1);
    expect(state.failureCount).toBe(0);
    expect(state.totalTokens).toBe(100);
    expect(state.lastSuccessAt).toBeDefined();
  });

  it('should record failure', () => {
    sm.recordFailure('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.totalRequests).toBe(1);
    expect(state.failureCount).toBe(1);
    expect(state.lastFailureAt).toBeDefined();
  });

  it('should reset failure count on success', () => {
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    expect(sm.getOrCreate('model-1').failureCount).toBe(2);
    sm.recordSuccess('model-1', 100);
    expect(sm.getOrCreate('model-1').failureCount).toBe(0);
  });

  it('should track all states', () => {
    sm.getOrCreate('model-1');
    sm.getOrCreate('model-2');
    const allStates = sm.allStates();
    expect(Object.keys(allStates)).toContain('model-1');
    expect(Object.keys(allStates)).toContain('model-2');
  });

  it('should return null for unknown model via get', () => {
    const state = sm.get('unknown');
    expect(state).toBeNull();
  });

  it('should track dirty state', () => {
    sm.recordSuccess('model-1', 100);
    expect(sm.isDirty).toBe(true);
    sm.markClean();
    expect(sm.isDirty).toBe(false);
  });

  it('should accumulate request counts', () => {
    sm.recordSuccess('model-1', 50);
    sm.recordSuccess('model-1', 100);
    sm.recordFailure('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.totalRequests).toBe(3);
    expect(state.totalTokens).toBe(150);
    expect(state.failureCount).toBe(1);
  });

  it('should deactivate a model', () => {
    sm.deactivate('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.status).toBe(ModelStatus.STANDBY);
  });

  it('should activate a model', () => {
    sm.deactivate('model-1');
    sm.activate('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.status).toBe(ModelStatus.ACTIVE);
    expect(state.failureCount).toBe(0);
  });

  it('should list active models', () => {
    sm.getOrCreate('model-1');
    sm.getOrCreate('model-2');
    sm.deactivate('model-2');
    expect(sm.activeModels()).toContain('model-1');
    expect(sm.activeModels()).not.toContain('model-2');
  });

  it('should list standby models', () => {
    sm.getOrCreate('model-1');
    sm.deactivate('model-1');
    expect(sm.standbyModels()).toContain('model-1');
  });

  it('should reset a model', () => {
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    sm.deactivate('model-1');
    sm.reset('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.status).toBe(ModelStatus.ACTIVE);
    expect(state.failureCount).toBe(0);
    expect(state.totalRequests).toBe(0);
  });

  it('should clear all state', () => {
    sm.getOrCreate('model-1');
    sm.getOrCreate('model-2');
    sm.clear();
    expect(sm.get('model-1')).toBeNull();
    expect(sm.get('model-2')).toBeNull();
  });

  it('should compute error rate', () => {
    sm.recordSuccess('model-1');
    sm.recordFailure('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.errorRate).toBeCloseTo(0.5, 1);
  });
});
