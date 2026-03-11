/**
 * Developer Experience Feature Tests
 * ===================================
 *
 * Covers all 7 new developer experience features:
 *   1. Structured exception hierarchy
 *   2. Request/response middleware
 *   3. Async context manager / close()
 *   4. Usage tracking facade
 *   5. Testing mock client
 *   6. Capability discovery API
 *   7. Routing explanation / debug API
 */

import {
  ModelMeshError,
  RoutingError,
  NoActiveModelError,
  AllProvidersExhaustedError,
  ProviderError,
  AuthenticationError,
  RateLimitError,
  ProviderTimeoutError,
  ConfigurationError,
  BudgetExceededError,
} from '@/exceptions';

import {
  Middleware,
  MiddlewareStack,
  createMiddlewareContext,
} from '@/middleware';
import type { MiddlewareContext } from '@/middleware';

import {
  MockClient,
  mockClient,
} from '@/testing';
import type { MockResponse, MockCall } from '@/testing';

import * as capabilities from '@/capabilities';

import { UsageTracker } from '@/usage';
import type { ModelUsage, ProviderUsage, BudgetStatus } from '@/usage';

import type { CompletionRequest, CompletionResponse } from '@/interfaces/provider';

// ==========================================================================
// Feature 1: Structured Exception Hierarchy
// ==========================================================================

describe('Exception Hierarchy', () => {
  // -- Inheritance ---------------------------------------------------------

  it('ModelMeshError extends Error', () => {
    const err = new ModelMeshError('test');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err.message).toBe('test');
  });

  it('RoutingError extends ModelMeshError', () => {
    const err = new RoutingError('route fail');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err).toBeInstanceOf(RoutingError);
  });

  it('NoActiveModelError extends RoutingError', () => {
    const err = new NoActiveModelError('no model', { poolName: 'chat' });
    expect(err).toBeInstanceOf(RoutingError);
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err.poolName).toBe('chat');
    expect(err.retryable).toBe(true);
  });

  it('AllProvidersExhaustedError extends RoutingError', () => {
    const inner = new Error('timeout');
    const err = new AllProvidersExhaustedError('exhausted', {
      poolName: 'chat',
      attempts: 3,
      lastError: inner,
    });
    expect(err).toBeInstanceOf(RoutingError);
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err.attempts).toBe(3);
    expect(err.lastError).toBe(inner);
    expect(err.retryable).toBe(false);
  });

  it('ProviderError extends ModelMeshError', () => {
    const err = new ProviderError('fail', { providerId: 'openai', modelId: 'gpt-4' });
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err.providerId).toBe('openai');
    expect(err.modelId).toBe('gpt-4');
  });

  it('AuthenticationError extends ProviderError', () => {
    const err = new AuthenticationError('bad key', { providerId: 'openai' });
    expect(err).toBeInstanceOf(ProviderError);
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err.retryable).toBe(false);
  });

  it('RateLimitError extends ProviderError', () => {
    const err = new RateLimitError('rate limited', { retryAfter: 30, providerId: 'openai' });
    expect(err).toBeInstanceOf(ProviderError);
    expect(err.retryable).toBe(true);
    expect(err.retryAfter).toBe(30);
  });

  it('ProviderTimeoutError extends ProviderError', () => {
    const err = new ProviderTimeoutError('timeout', { timeoutSeconds: 60 });
    expect(err).toBeInstanceOf(ProviderError);
    expect(err.retryable).toBe(true);
    expect(err.timeoutSeconds).toBe(60);
  });

  it('ConfigurationError extends ModelMeshError', () => {
    const err = new ConfigurationError('bad config');
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err.retryable).toBe(false);
  });

  it('BudgetExceededError extends ModelMeshError', () => {
    const err = new BudgetExceededError('over budget', {
      limitType: 'daily',
      limitValue: 10.0,
      actualValue: 12.5,
    });
    expect(err).toBeInstanceOf(ModelMeshError);
    expect(err.limitType).toBe('daily');
    expect(err.limitValue).toBe(10.0);
    expect(err.actualValue).toBe(12.5);
    expect(err.retryable).toBe(false);
  });

  // -- Structured fields ---------------------------------------------------

  it('stores details dict', () => {
    const err = new ModelMeshError('test', { details: { key: 'value' } });
    expect(err.details).toEqual({ key: 'value' });
  });

  it('defaults to empty details and non-retryable', () => {
    const err = new ModelMeshError('test');
    expect(err.details).toEqual({});
    expect(err.retryable).toBe(false);
  });

  // -- Broad catch pattern -------------------------------------------------

  it('all errors caught with instanceof ModelMeshError', () => {
    const errors = [
      new RoutingError('r'),
      new NoActiveModelError('n'),
      new AllProvidersExhaustedError('a'),
      new ProviderError('p'),
      new AuthenticationError('auth'),
      new RateLimitError('rl'),
      new ProviderTimeoutError('t'),
      new ConfigurationError('c'),
      new BudgetExceededError('b'),
    ];
    for (const err of errors) {
      expect(err).toBeInstanceOf(ModelMeshError);
    }
  });

  it('sets correct name property', () => {
    expect(new ModelMeshError().name).toBe('ModelMeshError');
    expect(new RoutingError().name).toBe('RoutingError');
    expect(new NoActiveModelError().name).toBe('NoActiveModelError');
    expect(new AllProvidersExhaustedError().name).toBe('AllProvidersExhaustedError');
    expect(new ProviderError().name).toBe('ProviderError');
    expect(new AuthenticationError().name).toBe('AuthenticationError');
    expect(new RateLimitError().name).toBe('RateLimitError');
    expect(new ProviderTimeoutError().name).toBe('ProviderTimeoutError');
    expect(new ConfigurationError().name).toBe('ConfigurationError');
    expect(new BudgetExceededError().name).toBe('BudgetExceededError');
  });
});

// ==========================================================================
// Feature 2: Request/Response Middleware
// ==========================================================================

describe('Middleware', () => {
  // -- Base class ----------------------------------------------------------

  it('base class has no-op implementations', async () => {
    const mw = new Middleware();
    const ctx: MiddlewareContext = {
      modelId: 'gpt-4',
      providerId: 'openai',
      poolName: 'chat',
      attempt: 1,
      timestamp: Date.now(),
      metadata: {},
    };
    const req = { model: 'test', messages: [], temperature: 1.0, stream: false, topP: 1.0 } as CompletionRequest;
    const res = {
      id: 'r1', model: 'test', choices: [], usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
      created: 0, object: 'chat.completion',
    } as CompletionResponse;

    // beforeRequest returns the request unchanged
    expect(await mw.beforeRequest(req, ctx)).toBe(req);
    // afterResponse returns the response unchanged
    expect(await mw.afterResponse(res, ctx)).toBe(res);
    // onError rethrows
    await expect(mw.onError(new Error('fail'), ctx)).rejects.toThrow('fail');
  });

  // -- MiddlewareContext fields --------------------------------------------

  it('context has all expected fields', () => {
    const ctx: MiddlewareContext = {
      modelId: 'gpt-4o',
      providerId: 'openai',
      poolName: 'chat-pool',
      attempt: 2,
      timestamp: Date.now(),
      metadata: { custom: true },
    };
    expect(ctx.modelId).toBe('gpt-4o');
    expect(ctx.providerId).toBe('openai');
    expect(ctx.poolName).toBe('chat-pool');
    expect(ctx.attempt).toBe(2);
    expect(ctx.metadata).toEqual({ custom: true });
  });

  // -- MiddlewareStack -----------------------------------------------------

  it('runs beforeRequest in order', async () => {
    const order: string[] = [];
    class MwA extends Middleware {
      async beforeRequest(r: CompletionRequest, c: MiddlewareContext) {
        order.push('A');
        return r;
      }
    }
    class MwB extends Middleware {
      async beforeRequest(r: CompletionRequest, c: MiddlewareContext) {
        order.push('B');
        return r;
      }
    }

    const stack = new MiddlewareStack([new MwA(), new MwB()]);
    const ctx: MiddlewareContext = {
      modelId: 'test', providerId: 'test', poolName: 'test',
      attempt: 1, timestamp: 0, metadata: {},
    };
    const req = { model: 'test', messages: [], temperature: 1.0, stream: false, topP: 1.0 } as CompletionRequest;
    await stack.runBeforeRequest(req, ctx);
    expect(order).toEqual(['A', 'B']);
  });

  it('runs afterResponse in reverse order (onion model)', async () => {
    const order: string[] = [];
    class MwA extends Middleware {
      async afterResponse(r: CompletionResponse, c: MiddlewareContext) {
        order.push('A');
        return r;
      }
    }
    class MwB extends Middleware {
      async afterResponse(r: CompletionResponse, c: MiddlewareContext) {
        order.push('B');
        return r;
      }
    }

    const stack = new MiddlewareStack([new MwA(), new MwB()]);
    const ctx: MiddlewareContext = {
      modelId: 'test', providerId: 'test', poolName: 'test',
      attempt: 1, timestamp: 0, metadata: {},
    };
    const res = {
      id: 'r', model: 'test', choices: [], usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
      created: 0, object: 'chat.completion',
    } as CompletionResponse;
    await stack.runAfterResponse(res, ctx);
    expect(order).toEqual(['B', 'A']);
  });

  it('onError returns fallback from first handler', async () => {
    class FallbackMw extends Middleware {
      async onError(error: Error, ctx: MiddlewareContext): Promise<CompletionResponse> {
        return {
          id: 'fallback', model: 'fallback', choices: [],
          usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
          created: 0, object: 'chat.completion',
        };
      }
    }
    const stack = new MiddlewareStack([new FallbackMw()]);
    const ctx: MiddlewareContext = {
      modelId: 'test', providerId: 'test', poolName: 'test',
      attempt: 1, timestamp: 0, metadata: {},
    };
    const result = await stack.runOnError(new Error('fail'), ctx);
    expect(result.id).toBe('fallback');
  });

  it('onError rethrows if no handler provides fallback', async () => {
    const stack = new MiddlewareStack([new Middleware()]);
    const ctx: MiddlewareContext = {
      modelId: 'test', providerId: 'test', poolName: 'test',
      attempt: 1, timestamp: 0, metadata: {},
    };
    await expect(stack.runOnError(new Error('unhandled'), ctx)).rejects.toThrow('unhandled');
  });

  it('stack.add() appends middleware', () => {
    const stack = new MiddlewareStack();
    expect(stack.length).toBe(0);
    stack.add(new Middleware());
    expect(stack.length).toBe(1);
    stack.add(new Middleware());
    expect(stack.length).toBe(2);
  });

  it('request can be transformed by beforeRequest', async () => {
    class TransformMw extends Middleware {
      async beforeRequest(req: CompletionRequest, ctx: MiddlewareContext): Promise<CompletionRequest> {
        return { ...req, model: 'transformed-model' };
      }
    }
    const stack = new MiddlewareStack([new TransformMw()]);
    const ctx: MiddlewareContext = {
      modelId: 'test', providerId: 'test', poolName: 'test',
      attempt: 1, timestamp: 0, metadata: {},
    };
    const req = { model: 'original', messages: [], temperature: 1.0, stream: false, topP: 1.0 } as CompletionRequest;
    const result = await stack.runBeforeRequest(req, ctx);
    expect(result.model).toBe('transformed-model');
  });

  it('createMiddlewareContext auto-populates timestamp and metadata', () => {
    const before = Date.now() / 1000;
    const ctx = createMiddlewareContext({
      modelId: 'gpt-4',
      providerId: 'openai',
      poolName: 'chat',
      attempt: 1,
    });
    const after = Date.now() / 1000;
    expect(ctx.timestamp).toBeGreaterThanOrEqual(before);
    expect(ctx.timestamp).toBeLessThanOrEqual(after);
    expect(ctx.metadata).toEqual({});
    expect(ctx.modelId).toBe('gpt-4');
  });

  it('createMiddlewareContext allows overriding defaults', () => {
    const ctx = createMiddlewareContext({
      modelId: 'test',
      providerId: 'test',
      poolName: 'test',
      attempt: 1,
      timestamp: 12345,
      metadata: { custom: true },
    });
    expect(ctx.timestamp).toBe(12345);
    expect(ctx.metadata).toEqual({ custom: true });
  });
});

// ==========================================================================
// Feature 3: Close / Dispose
// ==========================================================================

describe('MockClient close and lifecycle', () => {
  it('MockClient can be used as a plain object', () => {
    const client = mockClient();
    expect(client).toBeDefined();
    expect(client.calls).toEqual([]);
  });

  it('MockClient has close() method for cleanup parity', () => {
    const client = mockClient();
    expect(typeof client.close).toBe('function');
    // close() is a no-op on mock, but should not throw
    client.close();
  });
});

// ==========================================================================
// Feature 4: Usage Tracking
// ==========================================================================

describe('UsageTracker', () => {
  it('returns zeros when no cost tracker exists', () => {
    // Create a minimal mock mesh without a _costTracker
    const fakeMesh: any = {};
    const tracker = new UsageTracker(fakeMesh);
    expect(tracker.totalCost).toBe(0);
    expect(tracker.dailyCost).toBe(0);
    expect(tracker.monthlyCost).toBe(0);
    expect(tracker.totalTokens).toBe(0);
    expect(tracker.byModel).toEqual({});
    expect(tracker.byProvider).toEqual({});
    expect(tracker.budgetStatus).toBeNull();
  });

  it('returns correct summary when no cost tracker exists', () => {
    const fakeMesh: any = {};
    const tracker = new UsageTracker(fakeMesh);
    const summary = tracker.summary();
    expect(summary.totalCost).toBe(0);
    expect(summary.totalTokens).toBe(0);
    expect(summary.byModel).toEqual({});
    expect(summary.byProvider).toEqual({});
    expect(summary.budgetStatus).toBeNull();
  });

  it('reads from cost tracker when available', () => {
    const fakeMesh: any = {
      _costTracker: {
        summary: () => ({ totalCost: 1.23, byModel: { 'gpt-4': 1.0 }, byProvider: { openai: 1.23 } }),
        getDailyCost: () => 0.5,
        getMonthlyCost: () => 1.23,
        checkBudget: () => ({ exceeded: false, alert: false, dailyUsed: 0.5, dailyLimit: 10, dailyRemaining: 9.5, monthlyUsed: 1.23, monthlyLimit: 100, monthlyRemaining: 98.77 }),
        _records: [
          { promptTokens: 10, completionTokens: 20 },
          { promptTokens: 5, completionTokens: 15 },
        ],
      },
    };
    const tracker = new UsageTracker(fakeMesh);
    expect(tracker.totalCost).toBe(1.23);
    expect(tracker.dailyCost).toBe(0.5);
    expect(tracker.monthlyCost).toBe(1.23);
    expect(tracker.totalTokens).toBe(50); // 10+20+5+15
    expect(tracker.byModel['gpt-4'].totalCost).toBe(1.0);
    expect(tracker.byProvider['openai'].totalCost).toBe(1.23);
    expect(tracker.budgetStatus).toBeDefined();
    expect(tracker.budgetStatus!.exceeded).toBe(false);
  });

  it('reset() calls tracker reset methods', () => {
    let dailyReset = false;
    let monthlyReset = false;
    const fakeMesh: any = {
      _costTracker: {
        resetDaily: () => { dailyReset = true; },
        resetMonthly: () => { monthlyReset = true; },
      },
    };
    const tracker = new UsageTracker(fakeMesh);
    tracker.reset();
    expect(dailyReset).toBe(true);
    expect(monthlyReset).toBe(true);
  });

  it('reset() does nothing when no cost tracker', () => {
    const fakeMesh: any = {};
    const tracker = new UsageTracker(fakeMesh);
    // Should not throw
    tracker.reset();
  });
});

// ==========================================================================
// Feature 5: Testing Mock Client
// ==========================================================================

describe('MockClient', () => {
  it('returns pre-configured response', async () => {
    const client = mockClient({
      responses: [{ content: 'Hello!', model: 'gpt-4o', tokens: 10 }],
    });
    const resp = await client.chat.completions.create({
      model: 'test-pool',
      messages: [{ role: 'user', content: 'Hi' }],
    });
    expect(resp.choices[0].message?.content).toBe('Hello!');
    expect(resp.model).toBe('gpt-4o');
  });

  it('records calls', async () => {
    const client = mockClient({ responses: [{ content: 'A' }] });
    await client.chat.completions.create({
      model: 'my-pool',
      messages: [{ role: 'user', content: 'test msg' }],
    });
    expect(client.calls.length).toBe(1);
    expect(client.calls[0].model).toBe('my-pool');
    expect(client.calls[0].messages[0]).toEqual({ role: 'user', content: 'test msg' });
  });

  it('cycles through multiple responses', async () => {
    const client = mockClient({
      responses: [
        { content: 'First' },
        { content: 'Second' },
        { content: 'Third' },
      ],
    });
    const r1 = await client.chat.completions.create({ model: 'test', messages: [] });
    const r2 = await client.chat.completions.create({ model: 'test', messages: [] });
    const r3 = await client.chat.completions.create({ model: 'test', messages: [] });
    expect(r1.choices[0].message?.content).toBe('First');
    expect(r2.choices[0].message?.content).toBe('Second');
    expect(r3.choices[0].message?.content).toBe('Third');
  });

  it('repeats last response when exhausted', async () => {
    const client = mockClient({
      responses: [{ content: 'Only' }],
    });
    await client.chat.completions.create({ model: 'test', messages: [] });
    const r2 = await client.chat.completions.create({ model: 'test', messages: [] });
    expect(r2.choices[0].message?.content).toBe('Only');
  });

  it('returns default response when no responses configured', async () => {
    const client = mockClient();
    const resp = await client.chat.completions.create({ model: 'test', messages: [] });
    expect(resp.choices[0].message?.content).toBe('Mock response');
    expect(resp.model).toBe('mock-model');
  });

  it('calculates token usage correctly', async () => {
    const client = mockClient({
      responses: [{ tokens: 30 }],
    });
    const resp = await client.chat.completions.create({ model: 'test', messages: [] });
    expect(resp.usage.totalTokens).toBe(30);
    expect(resp.usage.promptTokens).toBe(10); // 30 // 3
    expect(resp.usage.completionTokens).toBe(20); // 30 - 10
  });

  it('supports custom token splits', async () => {
    const client = mockClient({
      responses: [{ tokens: 100, promptTokens: 25, completionTokens: 75 }],
    });
    const resp = await client.chat.completions.create({ model: 'test', messages: [] });
    expect(resp.usage.promptTokens).toBe(25);
    expect(resp.usage.completionTokens).toBe(75);
    expect(resp.usage.totalTokens).toBe(100);
  });

  it('provides pool status', () => {
    const client = mockClient();
    const status = client.poolStatus();
    expect(status['mock-pool']).toBeDefined();
  });

  it('provides explain()', () => {
    const client = mockClient();
    const explanation = client.explain();
    expect(explanation.poolName).toBe('mock-pool');
    expect(explanation.strategy).toBe('mock');
    expect(explanation.selectedModel).toBe('mock-model');
    expect((explanation.candidates as any[]).length).toBeGreaterThan(0);
  });

  it('lists active providers', () => {
    const client = mockClient();
    expect(client.activeProviders()).toContain('mock-provider');
  });

  it('provides describe()', () => {
    const client = mockClient();
    const desc = client.describe();
    expect(desc).toContain('mock-pool');
    expect(desc).toContain('mock-model');
  });

  it('models.list() returns empty list', () => {
    const client = mockClient();
    const models = client.models.list();
    expect(models.data).toEqual([]);
    expect(models.object).toBe('list');
  });

  it('has correct response object type', async () => {
    const client = mockClient({ responses: [{ content: 'test' }] });
    const resp = await client.chat.completions.create({ model: 'test', messages: [] });
    expect(resp.object).toBe('chat.completion');
    expect(resp.id).toBeDefined();
    expect(resp.created).toBeGreaterThan(0);
  });

  it('stores additional kwargs', async () => {
    const client = mockClient({ responses: [{ content: 'test' }] });
    await client.chat.completions.create({
      model: 'test',
      messages: [],
      temperature: 0.5,
    } as any);
    expect(client.calls[0].kwargs).toEqual({ temperature: 0.5 });
  });

  it('poolStatus() accepts optional pool parameter', () => {
    const client = mockClient();
    // With no args
    expect(client.poolStatus()).toBeDefined();
    // With pool arg (parity with Python)
    expect(client.poolStatus('my-pool')).toBeDefined();
  });

  it('describe() accepts optional pool parameter', () => {
    const client = mockClient();
    expect(client.describe()).toContain('mock-pool');
    // With pool arg (parity with Python)
    expect(client.describe('my-pool')).toContain('mock-pool');
  });

  it('has close() method for cleanup', () => {
    const client = mockClient();
    expect(typeof client.close).toBe('function');
    client.close(); // should not throw
  });
});

// ==========================================================================
// Feature 6: Capability Discovery API
// ==========================================================================

describe('Capabilities', () => {
  it('listAll() returns sorted aliases', () => {
    const all = capabilities.listAll();
    expect(all.length).toBeGreaterThan(0);
    // Verify sorted
    const sorted = [...all].sort();
    expect(all).toEqual(sorted);
  });

  it('listAll() includes expected capabilities', () => {
    const all = capabilities.listAll();
    expect(all).toContain('chat-completion');
    expect(all).toContain('text-generation');
    expect(all).toContain('text-embeddings');
  });

  it('resolve() maps alias to full dotted path', () => {
    const path = capabilities.resolve('chat-completion');
    expect(path).toBe('generation.text-generation.chat-completion');
  });

  it('resolve() returns dotted path as-is', () => {
    const path = capabilities.resolve('generation.text-generation.chat-completion');
    expect(path).toBe('generation.text-generation.chat-completion');
  });

  it('resolve() returns unknown alias unchanged', () => {
    expect(capabilities.resolve('nonexistent-capability')).toBe('nonexistent-capability');
  });

  it('search() finds matching aliases', () => {
    const matches = capabilities.search('text');
    expect(matches.length).toBeGreaterThan(0);
    // All results should contain "text" in alias or path
    for (const match of matches) {
      const path = capabilities.resolve(match);
      const combined = `${match} ${path}`.toLowerCase();
      expect(combined).toContain('text');
    }
  });

  it('search() is case-insensitive', () => {
    const lower = capabilities.search('text');
    const upper = capabilities.search('TEXT');
    expect(lower).toEqual(upper);
  });

  it('search() returns empty for no matches', () => {
    const matches = capabilities.search('zzz-nonexistent-zzz');
    expect(matches).toEqual([]);
  });

  it('search() results are sorted', () => {
    const matches = capabilities.search('text');
    const sorted = [...matches].sort();
    expect(matches).toEqual(sorted);
  });

  it('tree() returns hierarchical object', () => {
    const t = capabilities.tree();
    expect(t).toBeDefined();
    expect(typeof t).toBe('object');
    // Should have top-level keys like "generation", "representation", "understanding"
    expect('generation' in t).toBe(true);
  });

  it('tree() has correct nesting', () => {
    const t = capabilities.tree() as Record<string, Record<string, Record<string, unknown>>>;
    expect(t.generation).toBeDefined();
    expect(t.generation['text-generation']).toBeDefined();
    expect(t.generation['text-generation']['chat-completion']).toBeDefined();
  });
});

// ==========================================================================
// Feature 7: Routing Explanation (via MockClient)
// ==========================================================================

describe('Routing Explanation', () => {
  it('explain() returns pool information', () => {
    const client = mockClient();
    const exp = client.explain();
    expect(exp.poolName).toBe('mock-pool');
    expect(exp.strategy).toBe('mock');
  });

  it('explain() returns selected model', () => {
    const client = mockClient();
    const exp = client.explain();
    expect(exp.selectedModel).toBe('mock-model');
  });

  it('explain() returns candidates', () => {
    const client = mockClient();
    const exp = client.explain();
    const candidates = exp.candidates as any[];
    expect(candidates.length).toBe(1);
    expect(candidates[0].modelId).toBe('mock-model');
    expect(candidates[0].providerId).toBe('mock-provider');
    expect(candidates[0].status).toBe('active');
  });

  it('explain() returns reason', () => {
    const client = mockClient();
    const exp = client.explain();
    expect(exp.reason).toBeDefined();
    expect(typeof exp.reason).toBe('string');
  });

  it('explain() accepts model parameter', () => {
    const client = mockClient();
    const exp = client.explain({ model: 'custom-pool' });
    // MockClient always returns the same mock data regardless
    expect(exp.poolName).toBe('mock-pool');
  });
});

// ==========================================================================
// Cross-cutting: Import verification
// ==========================================================================

describe('Module exports', () => {
  it('exceptions module exports all error classes', () => {
    expect(ModelMeshError).toBeDefined();
    expect(RoutingError).toBeDefined();
    expect(NoActiveModelError).toBeDefined();
    expect(AllProvidersExhaustedError).toBeDefined();
    expect(ProviderError).toBeDefined();
    expect(AuthenticationError).toBeDefined();
    expect(RateLimitError).toBeDefined();
    expect(ProviderTimeoutError).toBeDefined();
    expect(ConfigurationError).toBeDefined();
    expect(BudgetExceededError).toBeDefined();
  });

  it('middleware module exports Middleware, MiddlewareStack, and createMiddlewareContext', () => {
    expect(Middleware).toBeDefined();
    expect(createMiddlewareContext).toBeDefined();
    expect(MiddlewareStack).toBeDefined();
  });

  it('testing module exports MockClient and mockClient', () => {
    expect(MockClient).toBeDefined();
    expect(mockClient).toBeDefined();
  });

  it('capabilities module exports all functions', () => {
    expect(capabilities.listAll).toBeDefined();
    expect(capabilities.resolve).toBeDefined();
    expect(capabilities.search).toBeDefined();
    expect(capabilities.tree).toBeDefined();
  });

  it('usage module exports UsageTracker', () => {
    expect(UsageTracker).toBeDefined();
  });
});
