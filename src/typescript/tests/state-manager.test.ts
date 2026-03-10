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

  // -- getOrCreate ------------------------------------------------------------

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

  it('should return different states for different model IDs', () => {
    const state1 = sm.getOrCreate('model-1');
    const state2 = sm.getOrCreate('model-2');
    expect(state1).not.toBe(state2);
    expect(state1.modelId).toBe('model-1');
    expect(state2.modelId).toBe('model-2');
  });

  it('should initialize with zero error rate', () => {
    const state = sm.getOrCreate('model-1');
    expect(state.errorRate).toBe(0);
  });

  it('should initialize with zero tokens and cost', () => {
    const state = sm.getOrCreate('model-1');
    expect(state.totalTokens).toBe(0);
    expect(state.totalCost).toBe(0);
  });

  // -- get --------------------------------------------------------------------

  it('should return null for unknown model via get', () => {
    const state = sm.get('unknown');
    expect(state).toBeNull();
  });

  it('should return state via get after getOrCreate', () => {
    sm.getOrCreate('model-1');
    const state = sm.get('model-1');
    expect(state).not.toBeNull();
    expect(state!.modelId).toBe('model-1');
  });

  // -- recordSuccess ----------------------------------------------------------

  it('should record success', () => {
    sm.recordSuccess('model-1', 100);
    const state = sm.getOrCreate('model-1');
    expect(state.totalRequests).toBe(1);
    expect(state.failureCount).toBe(0);
    expect(state.totalTokens).toBe(100);
    expect(state.lastSuccessAt).toBeDefined();
  });

  it('should record success with zero tokens by default', () => {
    sm.recordSuccess('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.totalTokens).toBe(0);
    expect(state.totalRequests).toBe(1);
  });

  it('should reset failure count on success', () => {
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    expect(sm.getOrCreate('model-1').failureCount).toBe(2);
    sm.recordSuccess('model-1', 100);
    expect(sm.getOrCreate('model-1').failureCount).toBe(0);
  });

  it('should reset error rate on success', () => {
    sm.recordFailure('model-1');
    expect(sm.getOrCreate('model-1').errorRate).toBeGreaterThan(0);
    sm.recordSuccess('model-1');
    expect(sm.getOrCreate('model-1').errorRate).toBe(0);
  });

  it('should accumulate tokens across successes', () => {
    sm.recordSuccess('model-1', 50);
    sm.recordSuccess('model-1', 100);
    sm.recordSuccess('model-1', 25);
    const state = sm.getOrCreate('model-1');
    expect(state.totalTokens).toBe(175);
  });

  // -- recordFailure ----------------------------------------------------------

  it('should record failure', () => {
    sm.recordFailure('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.totalRequests).toBe(1);
    expect(state.failureCount).toBe(1);
    expect(state.lastFailureAt).toBeDefined();
  });

  it('should increment failure count on multiple failures', () => {
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    expect(sm.getOrCreate('model-1').failureCount).toBe(3);
  });

  it('should update error rate on failure', () => {
    sm.recordFailure('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.errorRate).toBe(1.0); // 1 failure / 1 total
  });

  it('should compute error rate correctly', () => {
    sm.recordSuccess('model-1');
    sm.recordFailure('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.errorRate).toBeCloseTo(0.5, 1);
  });

  it('should compute error rate after mixed operations', () => {
    sm.recordSuccess('model-1');
    sm.recordSuccess('model-1');
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    // After recordFailure, failureCount is 2 but error rate = failureCount/totalRequests
    // Note: recordSuccess resets failureCount to 0
    // So after: S, S (failureCount=0, total=2), F (failureCount=1, total=3), F (failureCount=2, total=4)
    const state = sm.getOrCreate('model-1');
    expect(state.totalRequests).toBe(4);
    expect(state.failureCount).toBe(2);
    expect(state.errorRate).toBeCloseTo(0.5, 1);
  });

  // -- accumulate request counts ----------------------------------------------

  it('should accumulate request counts', () => {
    sm.recordSuccess('model-1', 50);
    sm.recordSuccess('model-1', 100);
    sm.recordFailure('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.totalRequests).toBe(3);
    expect(state.totalTokens).toBe(150);
    expect(state.failureCount).toBe(1);
  });

  // -- deactivate / activate --------------------------------------------------

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

  it('should reset error rate on activation', () => {
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    expect(sm.getOrCreate('model-1').errorRate).toBeGreaterThan(0);
    sm.activate('model-1');
    expect(sm.getOrCreate('model-1').errorRate).toBe(0);
  });

  it('should deactivate an already active model', () => {
    sm.getOrCreate('model-1');
    sm.deactivate('model-1');
    expect(sm.getOrCreate('model-1').status).toBe(ModelStatus.STANDBY);
  });

  it('should activate an already active model (no-op)', () => {
    sm.getOrCreate('model-1');
    sm.activate('model-1');
    expect(sm.getOrCreate('model-1').status).toBe(ModelStatus.ACTIVE);
  });

  it('should create state on deactivate for unknown model', () => {
    sm.deactivate('new-model');
    const state = sm.get('new-model');
    expect(state).not.toBeNull();
    expect(state!.status).toBe(ModelStatus.STANDBY);
  });

  // -- activeModels / standbyModels -------------------------------------------

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

  it('should return empty arrays when no models', () => {
    expect(sm.activeModels()).toEqual([]);
    expect(sm.standbyModels()).toEqual([]);
  });

  it('should correctly categorize models between active and standby', () => {
    sm.getOrCreate('a');
    sm.getOrCreate('b');
    sm.getOrCreate('c');
    sm.deactivate('b');
    expect(sm.activeModels()).toEqual(expect.arrayContaining(['a', 'c']));
    expect(sm.activeModels()).not.toContain('b');
    expect(sm.standbyModels()).toEqual(['b']);
  });

  // -- allStates --------------------------------------------------------------

  it('should track all states', () => {
    sm.getOrCreate('model-1');
    sm.getOrCreate('model-2');
    const allStates = sm.allStates();
    expect(Object.keys(allStates)).toContain('model-1');
    expect(Object.keys(allStates)).toContain('model-2');
  });

  it('should return empty object when no states', () => {
    expect(sm.allStates()).toEqual({});
  });

  // -- reset ------------------------------------------------------------------

  it('should reset a model', () => {
    sm.recordFailure('model-1');
    sm.recordFailure('model-1');
    sm.deactivate('model-1');
    sm.reset('model-1');
    const state = sm.getOrCreate('model-1');
    expect(state.status).toBe(ModelStatus.ACTIVE);
    expect(state.failureCount).toBe(0);
    expect(state.totalRequests).toBe(0);
    expect(state.totalTokens).toBe(0);
    expect(state.errorRate).toBe(0);
    expect(state.totalCost).toBe(0);
  });

  it('should reset an unknown model to defaults', () => {
    sm.reset('new-model');
    const state = sm.get('new-model');
    expect(state).not.toBeNull();
    expect(state!.status).toBe(ModelStatus.ACTIVE);
    expect(state!.failureCount).toBe(0);
  });

  // -- clear ------------------------------------------------------------------

  it('should clear all state', () => {
    sm.getOrCreate('model-1');
    sm.getOrCreate('model-2');
    sm.clear();
    expect(sm.get('model-1')).toBeNull();
    expect(sm.get('model-2')).toBeNull();
  });

  it('should mark as dirty after clear', () => {
    sm.clear();
    expect(sm.isDirty).toBe(true);
  });

  // -- dirty tracking ---------------------------------------------------------

  it('should track dirty state on recordSuccess', () => {
    sm.recordSuccess('model-1', 100);
    expect(sm.isDirty).toBe(true);
  });

  it('should track dirty state on recordFailure', () => {
    sm.recordFailure('model-1');
    expect(sm.isDirty).toBe(true);
  });

  it('should track dirty state on deactivate', () => {
    sm.deactivate('model-1');
    expect(sm.isDirty).toBe(true);
  });

  it('should track dirty state on activate', () => {
    sm.activate('model-1');
    expect(sm.isDirty).toBe(true);
  });

  it('should track dirty state on reset', () => {
    sm.reset('model-1');
    expect(sm.isDirty).toBe(true);
  });

  it('should start clean', () => {
    expect(sm.isDirty).toBe(false);
  });

  it('should markClean', () => {
    sm.recordSuccess('model-1', 100);
    expect(sm.isDirty).toBe(true);
    sm.markClean();
    expect(sm.isDirty).toBe(false);
  });

  it('should become dirty again after markClean and mutation', () => {
    sm.recordSuccess('model-1');
    sm.markClean();
    expect(sm.isDirty).toBe(false);
    sm.recordFailure('model-1');
    expect(sm.isDirty).toBe(true);
  });

  // -- constructor with syncPolicy --------------------------------------------

  it('should accept syncPolicy parameter', () => {
    const manager = new StateManager('sync-on-boundary');
    expect(manager).toBeDefined();
  });

  it('should accept storage parameter', () => {
    const mockStorage = {
      save: async () => {},
      load: async () => null,
      delete: async () => false,
      list: async () => [],
      exists: async () => false,
      stat: async () => null,
    };
    const manager = new StateManager('immediate', mockStorage as any);
    expect(manager).toBeDefined();
  });

  // -- timestamp precision ----------------------------------------------------

  it('should record timestamps as Unix epoch seconds', () => {
    const beforeTime = Date.now() / 1000;
    sm.recordSuccess('model-1');
    const afterTime = Date.now() / 1000;
    const state = sm.getOrCreate('model-1');
    expect(state.lastSuccessAt).toBeGreaterThanOrEqual(beforeTime);
    expect(state.lastSuccessAt).toBeLessThanOrEqual(afterTime);
  });

  it('should update failure timestamp on each failure', () => {
    sm.recordFailure('model-1');
    const firstTimestamp = sm.getOrCreate('model-1').lastFailureAt;
    sm.recordFailure('model-1');
    const secondTimestamp = sm.getOrCreate('model-1').lastFailureAt;
    expect(secondTimestamp).toBeGreaterThanOrEqual(firstTimestamp!);
  });
});
