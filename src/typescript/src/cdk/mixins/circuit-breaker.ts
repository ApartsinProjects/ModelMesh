/**
 * Circuit breaker mixin for provider connectors.
 *
 * Implements the circuit breaker pattern to prevent cascading failures.
 * When a provider's error rate exceeds the threshold, the circuit opens
 * and requests fail fast without calling the provider. After a recovery
 * timeout, a single probe request is allowed through; if it succeeds
 * the circuit closes, otherwise it re-opens.
 *
 * States:
 *
 *   CLOSED  --failure threshold-->  OPEN
 *   OPEN    --recovery timeout--->  HALF_OPEN
 *   HALF_OPEN --success----------> CLOSED
 *   HALF_OPEN --failure----------> OPEN
 *
 * Usage:
 *
 *   class MyProvider extends CircuitBreakerMixin {
 *     constructor() {
 *       super({
 *         failureThreshold: 5,
 *         recoveryTimeout: 60_000,
 *         halfOpenMaxAttempts: 1,
 *       });
 *     }
 *
 *     async complete(request: CompletionRequest) {
 *       if (this.isCircuitOpen()) throw new CircuitOpenError(this._cbRemainingMs());
 *       try {
 *         const result = await this._doComplete(request);
 *         this.recordSuccess();
 *         return result;
 *       } catch (err) {
 *         this.recordFailure();
 *         throw err;
 *       }
 *     }
 *   }
 */

// ---------------------------------------------------------------------------
// State enum
// ---------------------------------------------------------------------------

/** Current state of the circuit breaker. */
export enum CircuitBreakerState {
  /** Normal operation -- requests flow through. */
  CLOSED = 'closed',
  /** Circuit tripped -- requests are rejected immediately. */
  OPEN = 'open',
  /** Probe state -- a limited number of requests are allowed through. */
  HALF_OPEN = 'half_open',
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

/**
 * Raised when a request is rejected because the circuit is open.
 */
export class CircuitOpenError extends Error {
  /** Milliseconds remaining until the circuit transitions to HALF_OPEN. */
  public readonly remainingMs: number;

  constructor(remainingMs: number) {
    super(`Circuit breaker is open. Retry in ${(remainingMs / 1000).toFixed(1)}s`);
    this.name = 'CircuitOpenError';
    this.remainingMs = remainingMs;
  }
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/** Configuration for the circuit breaker. */
export interface CircuitBreakerConfig {
  /** Number of consecutive failures to trip the circuit. */
  readonly failureThreshold: number;
  /** Milliseconds to wait before transitioning OPEN -> HALF_OPEN. */
  readonly recoveryTimeout: number;
  /** Max probe requests allowed while in HALF_OPEN state. */
  readonly halfOpenMaxAttempts: number;
  /** Successes needed in HALF_OPEN to close the circuit (default 1). */
  readonly successThreshold?: number;
}

// ---------------------------------------------------------------------------
// Mixin
// ---------------------------------------------------------------------------

/**
 * Mixin providing circuit breaker protection for provider connectors.
 *
 * All state mutations use synchronous access since Node.js is
 * single-threaded. The mixin auto-transitions from OPEN to HALF_OPEN
 * when the recovery timeout has elapsed.
 */
export class CircuitBreakerMixin {
  private _cbConfig: Required<CircuitBreakerConfig>;
  private _cbState: CircuitBreakerState = CircuitBreakerState.CLOSED;
  private _cbFailureCount: number = 0;
  private _cbSuccessCount: number = 0;
  private _cbLastFailureAt: number = 0;
  private _cbHalfOpenCount: number = 0;

  constructor(config?: Partial<CircuitBreakerConfig>) {
    this._cbConfig = {
      failureThreshold: config?.failureThreshold ?? 5,
      recoveryTimeout: config?.recoveryTimeout ?? 60_000,
      halfOpenMaxAttempts: config?.halfOpenMaxAttempts ?? 1,
      successThreshold: config?.successThreshold ?? 1,
    };
  }

  // -- Public API -----------------------------------------------------------

  /**
   * Return `true` when the circuit is OPEN and requests should be
   * rejected. Automatically transitions OPEN -> HALF_OPEN when the
   * recovery timeout has elapsed.
   */
  isCircuitOpen(): boolean {
    this._maybeTransition();
    return this._cbState === CircuitBreakerState.OPEN;
  }

  /**
   * Check whether a request is allowed through the circuit breaker.
   * Throws {@link CircuitOpenError} when the circuit is OPEN or when
   * HALF_OPEN probe slots are exhausted.
   */
  checkCircuit(): void {
    this._maybeTransition();

    if (this._cbState === CircuitBreakerState.CLOSED) {
      return;
    }

    if (this._cbState === CircuitBreakerState.HALF_OPEN) {
      if (this._cbHalfOpenCount < this._cbConfig.halfOpenMaxAttempts) {
        this._cbHalfOpenCount += 1;
        return;
      }
      throw new CircuitOpenError(this._cbConfig.recoveryTimeout);
    }

    // OPEN
    const elapsed = Date.now() - this._cbLastFailureAt;
    const remaining = Math.max(0, this._cbConfig.recoveryTimeout - elapsed);
    throw new CircuitOpenError(remaining);
  }

  /** Record a successful request. */
  recordSuccess(): void {
    if (this._cbState === CircuitBreakerState.HALF_OPEN) {
      this._cbSuccessCount += 1;
      if (this._cbSuccessCount >= this._cbConfig.successThreshold) {
        this._cbState = CircuitBreakerState.CLOSED;
        this._cbFailureCount = 0;
        this._cbSuccessCount = 0;
        this._cbHalfOpenCount = 0;
      }
    } else if (this._cbState === CircuitBreakerState.CLOSED) {
      // Reset consecutive failure count on success.
      this._cbFailureCount = 0;
    }
  }

  /** Record a failed request. */
  recordFailure(): void {
    this._cbLastFailureAt = Date.now();

    if (this._cbState === CircuitBreakerState.HALF_OPEN) {
      // Probe failed -- re-open.
      this._cbState = CircuitBreakerState.OPEN;
      this._cbHalfOpenCount = 0;
      this._cbSuccessCount = 0;
      return;
    }

    this._cbFailureCount += 1;
    if (this._cbFailureCount >= this._cbConfig.failureThreshold) {
      this._cbState = CircuitBreakerState.OPEN;
    }
  }

  /** Current circuit breaker state (may auto-transition). */
  getCircuitState(): CircuitBreakerState {
    this._maybeTransition();
    return this._cbState;
  }

  /** Manually reset the circuit breaker to CLOSED state. */
  resetCircuit(): void {
    this._cbState = CircuitBreakerState.CLOSED;
    this._cbFailureCount = 0;
    this._cbSuccessCount = 0;
    this._cbHalfOpenCount = 0;
  }

  /** Return current circuit breaker statistics. */
  circuitBreakerStats(): Record<string, unknown> {
    this._maybeTransition();
    return {
      state: this._cbState,
      failureCount: this._cbFailureCount,
      successCount: this._cbSuccessCount,
      lastFailureAt: this._cbLastFailureAt,
      config: {
        failureThreshold: this._cbConfig.failureThreshold,
        recoveryTimeout: this._cbConfig.recoveryTimeout,
        halfOpenMaxAttempts: this._cbConfig.halfOpenMaxAttempts,
        successThreshold: this._cbConfig.successThreshold,
      },
    };
  }

  // -- Internal -------------------------------------------------------------

  /**
   * Auto-transition OPEN -> HALF_OPEN if the recovery timeout has
   * elapsed since the last failure.
   */
  private _maybeTransition(): void {
    if (this._cbState === CircuitBreakerState.OPEN) {
      const elapsed = Date.now() - this._cbLastFailureAt;
      if (elapsed >= this._cbConfig.recoveryTimeout) {
        this._cbState = CircuitBreakerState.HALF_OPEN;
        this._cbHalfOpenCount = 0;
        this._cbSuccessCount = 0;
      }
    }
  }
}
