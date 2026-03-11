/**
 * Cross-cutting retry logic with configurable exponential backoff.
 *
 * Provides a `RetryMixin` that can be composed into any class.
 * The mixin exposes a single async entry-point, `executeWithRetry`,
 * which executes an arbitrary async callable and automatically retries
 * on transient failures using exponential backoff with optional jitter.
 *
 * Usage:
 *
 *   class MyService extends RetryMixin {
 *     constructor() {
 *       super({ maxRetries: 5, baseDelay: 1000 });
 *     }
 *
 *     async fetch(url: string): Promise<Response> {
 *       return this.executeWithRetry(() => this._doFetch(url));
 *     }
 *   }
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/** Configuration for the retry mixin. */
export interface RetryConfig {
  /** Maximum number of retry attempts (not counting the initial attempt). */
  readonly maxRetries: number;
  /** Base delay in milliseconds for the first backoff interval. */
  readonly baseDelay: number;
  /** Upper bound in milliseconds for any single backoff interval. */
  readonly maxDelay: number;
  /** When `true`, each computed delay is multiplied by a random factor
   *  in [0.5, 1.5) to de-correlate concurrent callers. */
  readonly jitter: boolean;
}

// ---------------------------------------------------------------------------
// Mixin
// ---------------------------------------------------------------------------

/**
 * Configurable retry with exponential backoff.
 *
 * Compose into any class via extension or delegation.  Call
 * `executeWithRetry(fn)` to execute `fn` with automatic retry on
 * failure.
 *
 * Class-level defaults may be overridden via the constructor config.
 */
export class RetryMixin {
  private readonly _retryConfig: RetryConfig;

  constructor(config?: Partial<RetryConfig>) {
    this._retryConfig = {
      maxRetries: config?.maxRetries ?? 3,
      baseDelay: config?.baseDelay ?? 1000,
      maxDelay: config?.maxDelay ?? 30_000,
      jitter: config?.jitter ?? true,
    };
  }

  /**
   * Execute `fn` with retry logic.
   *
   * If `fn` throws an error that {@link shouldRetry} considers
   * retryable, the call is retried after an exponentially increasing
   * delay (subject to jitter). When all attempts are exhausted the
   * last error is re-thrown.
   *
   * @typeParam T - The return type of the async callable.
   * @param fn - An async callable to execute.
   * @returns The return value of `fn` on the first successful call.
   * @throws The last error thrown by `fn` when all retry attempts have
   *   been exhausted, or immediately when {@link shouldRetry} returns
   *   `false`.
   */
  async executeWithRetry<T>(fn: () => Promise<T>): Promise<T> {
    let lastError: unknown = null;
    const totalAttempts = this._retryConfig.maxRetries + 1;

    for (let attempt = 0; attempt < totalAttempts; attempt++) {
      try {
        return await fn();
      } catch (error: unknown) {
        lastError = error;

        // Last attempt -- re-throw immediately.
        if (attempt === totalAttempts - 1) {
          throw error;
        }

        // Non-retryable errors propagate immediately.
        if (!this.shouldRetry(error, attempt)) {
          throw error;
        }

        const delay = this.calculateDelay(attempt);
        await this._sleep(delay);
      }
    }

    // Should never reach here, but satisfies the compiler.
    throw lastError;
  }

  /**
   * Compute the backoff delay for the given attempt number.
   *
   * The delay grows exponentially:
   *
   *   delay = baseDelay * (2 ** attempt)
   *
   * It is clamped to `maxDelay` and, when `jitter` is enabled,
   * multiplied by a random factor drawn uniformly from [0.5, 1.5).
   *
   * @param attempt - Zero-based attempt index (0 for the first retry).
   * @returns The computed delay in milliseconds.
   */
  calculateDelay(attempt: number): number {
    let delay = this._retryConfig.baseDelay * Math.pow(2, attempt);
    delay = Math.min(delay, this._retryConfig.maxDelay);
    if (this._retryConfig.jitter) {
      delay *= 0.5 + Math.random();
    }
    return delay;
  }

  /**
   * Determine whether the error should trigger a retry.
   *
   * The default implementation returns `true` for all errors, meaning
   * every failure is retried.  Override this method to restrict retries
   * to specific error types (e.g., transient network errors or
   * rate-limit responses).
   *
   * @param error - The error thrown by the target callable.
   * @param attempt - The zero-based attempt index.
   * @returns `true` if the operation should be retried.
   */
  shouldRetry(_error: unknown, _attempt: number): boolean {
    return true;
  }

  /** Internal sleep helper. */
  private _sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
