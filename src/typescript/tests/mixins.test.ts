/**
 * Tests for CDK mixins: CircuitBreaker, Retry, Cache, RateLimiter.
 */
import {
  CircuitBreakerMixin,
  CircuitBreakerState,
  CircuitOpenError,
} from '@/cdk/mixins/circuit-breaker';
import { RetryMixin } from '@/cdk/mixins/retry';
import { CacheMixin } from '@/cdk/mixins/cache';
import { RateLimiterMixin } from '@/cdk/mixins/rate-limiter';

// ---------------------------------------------------------------------------
// CircuitBreakerMixin
// ---------------------------------------------------------------------------

describe('CircuitBreakerMixin', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('starts in CLOSED state', () => {
    const cb = new CircuitBreakerMixin({ failureThreshold: 3 });
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.CLOSED);
  });

  test('stays CLOSED below failure threshold', () => {
    const cb = new CircuitBreakerMixin({ failureThreshold: 3 });
    cb.recordFailure();
    cb.recordFailure();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.CLOSED);
  });

  test('transitions to OPEN after failure threshold', () => {
    const cb = new CircuitBreakerMixin({ failureThreshold: 3 });
    cb.recordFailure();
    cb.recordFailure();
    cb.recordFailure();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.OPEN);
  });

  test('transitions from OPEN to HALF_OPEN after recovery timeout', () => {
    const cb = new CircuitBreakerMixin({
      failureThreshold: 2,
      recoveryTimeout: 5000,
    });
    cb.recordFailure();
    cb.recordFailure();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.OPEN);

    // Advance time past the recovery timeout
    jest.advanceTimersByTime(5000);
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.HALF_OPEN);
  });

  test('transitions from HALF_OPEN to CLOSED on success threshold', () => {
    const cb = new CircuitBreakerMixin({
      failureThreshold: 2,
      recoveryTimeout: 5000,
      successThreshold: 2,
    });

    // Trip the circuit
    cb.recordFailure();
    cb.recordFailure();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.OPEN);

    // Wait for recovery
    jest.advanceTimersByTime(5000);
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.HALF_OPEN);

    // Record enough successes
    cb.recordSuccess();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.HALF_OPEN);
    cb.recordSuccess();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.CLOSED);
  });

  test('transitions from HALF_OPEN to OPEN on failure', () => {
    const cb = new CircuitBreakerMixin({
      failureThreshold: 2,
      recoveryTimeout: 5000,
    });

    // Trip then recover to HALF_OPEN
    cb.recordFailure();
    cb.recordFailure();
    jest.advanceTimersByTime(5000);
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.HALF_OPEN);

    // Fail the probe
    cb.recordFailure();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.OPEN);
  });

  test('checkCircuit() throws CircuitOpenError when OPEN', () => {
    const cb = new CircuitBreakerMixin({
      failureThreshold: 2,
      recoveryTimeout: 10_000,
    });

    cb.recordFailure();
    cb.recordFailure();

    expect(() => cb.checkCircuit()).toThrow(CircuitOpenError);
    try {
      cb.checkCircuit();
    } catch (e) {
      expect(e).toBeInstanceOf(CircuitOpenError);
      expect((e as CircuitOpenError).remainingMs).toBeGreaterThanOrEqual(0);
    }
  });

  test('checkCircuit() allows requests when CLOSED', () => {
    const cb = new CircuitBreakerMixin({ failureThreshold: 5 });
    expect(() => cb.checkCircuit()).not.toThrow();
  });

  test('resetCircuit() returns to CLOSED', () => {
    const cb = new CircuitBreakerMixin({ failureThreshold: 2 });

    cb.recordFailure();
    cb.recordFailure();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.OPEN);

    cb.resetCircuit();
    expect(cb.getCircuitState()).toBe(CircuitBreakerState.CLOSED);
  });

  test('circuitBreakerStats() returns correct counts', () => {
    const cb = new CircuitBreakerMixin({
      failureThreshold: 5,
      recoveryTimeout: 60_000,
    });

    cb.recordFailure();
    cb.recordFailure();
    const stats = cb.circuitBreakerStats();
    expect(stats.state).toBe(CircuitBreakerState.CLOSED);
    expect(stats.failureCount).toBe(2);
    expect(stats.config).toEqual({
      failureThreshold: 5,
      recoveryTimeout: 60_000,
      halfOpenMaxAttempts: 1,
      successThreshold: 1,
    });
  });
});

// ---------------------------------------------------------------------------
// RetryMixin
// ---------------------------------------------------------------------------

describe('RetryMixin', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('succeeds on first attempt without retry', async () => {
    const retry = new RetryMixin({ maxRetries: 3 });
    let attempts = 0;
    const result = await retry.executeWithRetry(async () => {
      attempts++;
      return 'ok';
    });
    expect(result).toBe('ok');
    expect(attempts).toBe(1);
  });

  test('retries on failure up to maxRetries', async () => {
    const retry = new RetryMixin({ maxRetries: 3, baseDelay: 100, jitter: false });
    let attempts = 0;

    const promise = retry.executeWithRetry(async () => {
      attempts++;
      if (attempts < 3) throw new Error('fail');
      return 'recovered';
    });

    // Advance past all delays
    for (let i = 0; i < 3; i++) {
      await Promise.resolve(); // let microtask queue flush
      jest.advanceTimersByTime(30_000);
    }

    const result = await promise;
    expect(result).toBe('recovered');
    expect(attempts).toBe(3);
  });

  test('throws after all retries exhausted', async () => {
    const retry = new RetryMixin({ maxRetries: 2, baseDelay: 100, jitter: false });

    const promise = retry.executeWithRetry(async () => {
      throw new Error('persistent failure');
    });

    // Advance past all delays
    for (let i = 0; i < 3; i++) {
      await Promise.resolve();
      jest.advanceTimersByTime(30_000);
    }

    await expect(promise).rejects.toThrow('persistent failure');
  });

  test('calculateDelay uses exponential backoff', () => {
    const retry = new RetryMixin({
      baseDelay: 1000,
      maxDelay: 30_000,
      jitter: false,
    });

    expect(retry.calculateDelay(0)).toBe(1000);   // 1000 * 2^0
    expect(retry.calculateDelay(1)).toBe(2000);   // 1000 * 2^1
    expect(retry.calculateDelay(2)).toBe(4000);   // 1000 * 2^2
    expect(retry.calculateDelay(3)).toBe(8000);   // 1000 * 2^3
  });

  test('calculateDelay with jitter varies output', () => {
    const retry = new RetryMixin({
      baseDelay: 1000,
      maxDelay: 30_000,
      jitter: true,
    });

    // With jitter, delay = baseDelay * 2^attempt * (0.5 + Math.random())
    // Range for attempt 0: [500, 1500)
    const delay = retry.calculateDelay(0);
    expect(delay).toBeGreaterThanOrEqual(500);
    expect(delay).toBeLessThan(1500);
  });

  test('calculateDelay respects maxDelay cap', () => {
    const retry = new RetryMixin({
      baseDelay: 1000,
      maxDelay: 5000,
      jitter: false,
    });

    // attempt 10 would be 1000 * 2^10 = 1024000, but capped at 5000
    expect(retry.calculateDelay(10)).toBe(5000);
  });

  test('shouldRetry can be overridden', async () => {
    class CustomRetry extends RetryMixin {
      shouldRetry(error: unknown, _attempt: number): boolean {
        return error instanceof Error && error.message === 'retryable';
      }
    }

    const retry = new CustomRetry({ maxRetries: 3, baseDelay: 100, jitter: false });

    // Non-retryable error should propagate immediately
    const promise = retry.executeWithRetry(async () => {
      throw new Error('non-retryable');
    });

    await expect(promise).rejects.toThrow('non-retryable');
  });

  test('zero maxRetries means no retries', async () => {
    const retry = new RetryMixin({ maxRetries: 0 });
    let attempts = 0;

    const promise = retry.executeWithRetry(async () => {
      attempts++;
      throw new Error('fail');
    });

    await expect(promise).rejects.toThrow('fail');
    expect(attempts).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// CacheMixin
// ---------------------------------------------------------------------------

describe('CacheMixin', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('cacheSet and cacheGet round-trip', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 60_000 });
    cache.cacheSet('key1', 'value1');
    expect(cache.cacheGet('key1')).toBe('value1');
  });

  test('cacheGet returns undefined for missing key', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 60_000 });
    expect(cache.cacheGet('nonexistent')).toBeUndefined();
  });

  test('cacheHas returns true for existing key', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 60_000 });
    cache.cacheSet('key1', 'value1');
    expect(cache.cacheHas('key1')).toBe(true);
  });

  test('cacheHas returns false for missing key', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 60_000 });
    expect(cache.cacheHas('nonexistent')).toBe(false);
  });

  test('LRU eviction removes oldest entry', () => {
    const cache = new CacheMixin<string>({ maxSize: 2, ttlMs: 60_000 });

    cache.cacheSet('a', 'A');
    jest.advanceTimersByTime(10);
    cache.cacheSet('b', 'B');
    jest.advanceTimersByTime(10);

    // Access 'a' to make 'b' the least-recently-used
    cache.cacheGet('a');
    jest.advanceTimersByTime(10);

    // Adding 'c' should evict 'b' (the LRU entry)
    cache.cacheSet('c', 'C');

    expect(cache.cacheGet('a')).toBe('A');
    expect(cache.cacheGet('b')).toBeUndefined();
    expect(cache.cacheGet('c')).toBe('C');
  });

  test('TTL expiry removes stale entries', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 5000 });
    cache.cacheSet('key1', 'value1');

    // Still valid
    jest.advanceTimersByTime(4000);
    expect(cache.cacheGet('key1')).toBe('value1');

    // Now expired
    jest.advanceTimersByTime(2000);
    expect(cache.cacheGet('key1')).toBeUndefined();
  });

  test('cacheClear removes all entries', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 60_000 });
    cache.cacheSet('a', 'A');
    cache.cacheSet('b', 'B');
    cache.cacheClear();

    expect(cache.cacheGet('a')).toBeUndefined();
    expect(cache.cacheGet('b')).toBeUndefined();
    expect(cache.cacheStats().size).toBe(0);
  });

  test('cacheInvalidate removes specific key', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 60_000 });
    cache.cacheSet('a', 'A');
    cache.cacheSet('b', 'B');
    cache.cacheInvalidate('a');

    expect(cache.cacheGet('a')).toBeUndefined();
    expect(cache.cacheGet('b')).toBe('B');
  });

  test('cacheStats tracks hits and misses', () => {
    const cache = new CacheMixin<string>({ maxSize: 10, ttlMs: 60_000 });
    cache.cacheSet('a', 'A');

    cache.cacheGet('a');       // hit
    cache.cacheGet('a');       // hit
    cache.cacheGet('missing'); // miss

    const stats = cache.cacheStats();
    expect(stats.hits).toBe(2);
    expect(stats.misses).toBe(1);
  });

  test('cacheStats tracks evictions', () => {
    const cache = new CacheMixin<string>({ maxSize: 2, ttlMs: 60_000 });
    cache.cacheSet('a', 'A');
    jest.advanceTimersByTime(10);
    cache.cacheSet('b', 'B');
    jest.advanceTimersByTime(10);
    cache.cacheSet('c', 'C'); // evicts 'a' (oldest accessedAt)

    const stats = cache.cacheStats();
    expect(stats.evictions).toBe(1);
  });

  test('disabled cache returns undefined', () => {
    const cache = new CacheMixin<string>({
      maxSize: 10,
      ttlMs: 60_000,
      enabled: false,
    });

    cache.cacheSet('key', 'value');
    expect(cache.cacheGet('key')).toBeUndefined();
    expect(cache.cacheHas('key')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// RateLimiterMixin
// ---------------------------------------------------------------------------

describe('RateLimiterMixin', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('acquire() succeeds within rate limit', () => {
    const rl = new RateLimiterMixin({ requestsPerMinute: 10 });
    expect(rl.acquire()).toBe(true);
  });

  test('acquire() fails when rate limit exceeded', () => {
    const rl = new RateLimiterMixin({ requestsPerMinute: 3, burstMultiplier: 1.0 });
    expect(rl.acquire()).toBe(true);
    expect(rl.acquire()).toBe(true);
    expect(rl.acquire()).toBe(true);
    // 4th should fail
    expect(rl.acquire()).toBe(false);
  });

  test('recordTokens tracks token usage', () => {
    const rl = new RateLimiterMixin({
      requestsPerMinute: 100,
      tokensPerMinute: 1000,
    });

    rl.acquire();
    rl.recordTokens(500);

    const capacity = rl.getRemainingCapacity();
    expect(capacity.tokens).toBe(500);
    expect(capacity.requests).toBe(99);
  });

  test('getRemainingCapacity shows available tokens', () => {
    const rl = new RateLimiterMixin({
      requestsPerMinute: 60,
      tokensPerMinute: 100_000,
    });

    const capacity = rl.getRemainingCapacity();
    expect(capacity.requests).toBe(60);
    expect(capacity.tokens).toBe(100_000);
  });

  test('burst multiplier allows short bursts', () => {
    const rl = new RateLimiterMixin({
      requestsPerMinute: 10,
      burstMultiplier: 2.0,
    });

    // With burst multiplier of 2, effective RPM = 20
    for (let i = 0; i < 20; i++) {
      expect(rl.acquire()).toBe(true);
    }
    expect(rl.acquire()).toBe(false);
  });

  test('capacity replenishes over time', () => {
    const rl = new RateLimiterMixin({
      requestsPerMinute: 2,
      burstMultiplier: 1.0,
    });

    expect(rl.acquire()).toBe(true);
    expect(rl.acquire()).toBe(true);
    expect(rl.acquire()).toBe(false);

    // Advance past the 60-second sliding window
    jest.advanceTimersByTime(61_000);

    // Capacity should be replenished
    expect(rl.acquire()).toBe(true);
  });
});
