/**
 * Client-side rate limiting using a sliding-window token bucket.
 *
 * Provides a `RateLimiterMixin` that can be composed into any class.
 * The mixin enforces requests-per-minute (RPM) and tokens-per-minute
 * (TPM) limits as well as an optional burst multiplier.
 *
 * Usage:
 *
 *   class MyProvider extends RateLimiterMixin {
 *     constructor() {
 *       super({ requestsPerMinute: 120, tokensPerMinute: 200_000 });
 *     }
 *
 *     async complete(prompt: string): Promise<string> {
 *       await this.waitForCapacity();
 *       if (!this.acquire()) throw new Error('Rate limited');
 *       const response = await this.callApi(prompt);
 *       this.recordTokens(response.usage.totalTokens);
 *       return response.text;
 *     }
 *   }
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/** Configuration for the rate limiter mixin. */
export interface RateLimiterConfig {
  /** Maximum requests allowed per minute. */
  readonly requestsPerMinute: number;
  /** Maximum tokens allowed per minute. */
  readonly tokensPerMinute: number;
  /** Burst multiplier for short spikes above the steady rate. */
  readonly burstMultiplier: number;
}

// ---------------------------------------------------------------------------
// Mixin
// ---------------------------------------------------------------------------

/**
 * Client-side rate limiting with RPM and TPM controls.
 *
 * The implementation uses a sliding one-minute window: timestamps and
 * token counts older than 60 seconds are pruned on each `acquire`
 * call.
 *
 * Compose into any class via extension.
 */
export class RateLimiterMixin {
  private readonly _rlConfig: RateLimiterConfig;
  private _requestTimestamps: number[] = [];
  private _tokenCounts: Array<{ timestamp: number; count: number }> = [];
  private _lastRequestAt: number = 0;

  constructor(config?: Partial<RateLimiterConfig>) {
    this._rlConfig = {
      requestsPerMinute: config?.requestsPerMinute ?? 60,
      tokensPerMinute: config?.tokensPerMinute ?? 100_000,
      burstMultiplier: config?.burstMultiplier ?? 1.0,
    };
  }

  /**
   * Try to acquire a request slot.
   *
   * Prunes the sliding window, then checks whether a new request is
   * allowed under the RPM limit (adjusted by `burstMultiplier`).
   * Returns `true` if the request is allowed and the slot is consumed,
   * or `false` if the rate limit would be exceeded.
   */
  acquire(): boolean {
    const now = Date.now();
    const windowStart = now - 60_000;

    // Prune old entries.
    this._requestTimestamps = this._requestTimestamps.filter(
      (t) => t > windowStart
    );
    this._tokenCounts = this._tokenCounts.filter(
      (e) => e.timestamp > windowStart
    );

    const effectiveRpm = Math.floor(
      this._rlConfig.requestsPerMinute * this._rlConfig.burstMultiplier
    );

    if (this._requestTimestamps.length >= effectiveRpm) {
      return false;
    }

    this._requestTimestamps.push(now);
    this._lastRequestAt = now;
    return true;
  }

  /**
   * Record actual token usage after a response is received.
   *
   * Call this after completing a request to keep the TPM counter
   * accurate. The recorded count contributes to the sliding window
   * used by {@link getRemainingCapacity} and {@link waitForCapacity}.
   *
   * @param count - Number of tokens consumed by the completed request.
   */
  recordTokens(count: number): void {
    this._tokenCounts.push({ timestamp: Date.now(), count });
  }

  /**
   * Return remaining capacity within the current sliding window.
   *
   * @returns An object with remaining `requests` and `tokens` counts.
   */
  getRemainingCapacity(): { requests: number; tokens: number } {
    const now = Date.now();
    const windowStart = now - 60_000;

    // Prune old entries.
    this._requestTimestamps = this._requestTimestamps.filter(
      (t) => t > windowStart
    );
    this._tokenCounts = this._tokenCounts.filter(
      (e) => e.timestamp > windowStart
    );

    const effectiveRpm = Math.floor(
      this._rlConfig.requestsPerMinute * this._rlConfig.burstMultiplier
    );

    const usedRequests = this._requestTimestamps.length;
    const usedTokens = this._tokenCounts.reduce(
      (sum, e) => sum + e.count,
      0
    );

    const effectiveTpm = Math.floor(
      this._rlConfig.tokensPerMinute * this._rlConfig.burstMultiplier
    );

    return {
      requests: Math.max(0, effectiveRpm - usedRequests),
      tokens: Math.max(0, effectiveTpm - usedTokens),
    };
  }

  /**
   * Wait asynchronously until there is capacity for a new request.
   *
   * Polls the sliding window every 100ms until the RPM and TPM limits
   * allow a new request. Resolves immediately if capacity is already
   * available.
   */
  async waitForCapacity(): Promise<void> {
    const poll = (): boolean => {
      const { requests, tokens } = this.getRemainingCapacity();
      return requests > 0 && tokens > 0;
    };

    while (!poll()) {
      await new Promise<void>((resolve) => setTimeout(resolve, 100));
    }
  }
}
