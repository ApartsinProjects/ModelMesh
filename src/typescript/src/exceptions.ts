/**
 * Structured exception hierarchy for ModelMesh.
 *
 * All ModelMesh-specific errors inherit from {@link ModelMeshError},
 * enabling broad `catch (e) { if (e instanceof ModelMeshError) }` patterns
 * while still allowing fine-grained handling of specific failure modes.
 *
 * Exception tree:
 *
 *     ModelMeshError
 *     ├── RoutingError
 *     │   ├── NoActiveModelError
 *     │   └── AllProvidersExhaustedError
 *     ├── ProviderError
 *     │   ├── AuthenticationError
 *     │   ├── RateLimitError
 *     │   └── ProviderTimeoutError
 *     ├── ConfigurationError
 *     └── BudgetExceededError
 */

// -- Base -------------------------------------------------------------------

/**
 * Base error for all ModelMesh errors.
 *
 * All ModelMesh-specific errors inherit from this class so that
 * callers can write a single `instanceof ModelMeshError` check.
 */
export class ModelMeshError extends Error {
  /** Optional structured context about the error. */
  readonly details: Record<string, unknown>;
  /** Hint indicating whether the operation may succeed on retry. */
  readonly retryable: boolean;

  constructor(
    message: string = '',
    options?: {
      details?: Record<string, unknown>;
      retryable?: boolean;
    }
  ) {
    super(message);
    this.name = 'ModelMeshError';
    this.details = options?.details ?? {};
    this.retryable = options?.retryable ?? false;
  }
}

// -- Routing errors ---------------------------------------------------------

/** Error during request routing (pool resolution or model selection). */
export class RoutingError extends ModelMeshError {
  /** The pool ID that was being resolved. */
  readonly poolName: string | null;

  constructor(
    message: string = '',
    options?: {
      poolName?: string;
      details?: Record<string, unknown>;
      retryable?: boolean;
    }
  ) {
    super(message, {
      details: options?.details,
      retryable: options?.retryable ?? false,
    });
    this.name = 'RoutingError';
    this.poolName = options?.poolName ?? null;
  }
}

/**
 * No active model is available in the requested pool.
 *
 * Raised when all models in a pool are in standby or have been
 * deactivated, and no candidate can serve the request.
 */
export class NoActiveModelError extends RoutingError {
  constructor(
    message: string = '',
    options?: {
      poolName?: string;
      details?: Record<string, unknown>;
    }
  ) {
    super(message, {
      poolName: options?.poolName,
      details: options?.details,
      retryable: true,
    });
    this.name = 'NoActiveModelError';
  }
}

/**
 * All providers failed after retry/rotation attempts.
 *
 * Raised when the router has exhausted all retry attempts across
 * available models in the pool.
 */
export class AllProvidersExhaustedError extends RoutingError {
  /** Number of attempts made before giving up. */
  readonly attempts: number;
  /** The last provider error encountered. */
  readonly lastError: Error | null;

  constructor(
    message: string = '',
    options?: {
      poolName?: string;
      attempts?: number;
      lastError?: Error | null;
      details?: Record<string, unknown>;
    }
  ) {
    super(message, {
      poolName: options?.poolName,
      details: options?.details,
      retryable: false,
    });
    this.name = 'AllProvidersExhaustedError';
    this.attempts = options?.attempts ?? 0;
    this.lastError = options?.lastError ?? null;
  }
}

// -- Provider errors --------------------------------------------------------

/** Error originating from a provider connector. */
export class ProviderError extends ModelMeshError {
  /** Connector ID of the provider that failed. */
  readonly providerId: string | null;
  /** Model identifier that was being used. */
  readonly modelId: string | null;

  constructor(
    message: string = '',
    options?: {
      providerId?: string;
      modelId?: string;
      details?: Record<string, unknown>;
      retryable?: boolean;
    }
  ) {
    super(message, {
      details: options?.details,
      retryable: options?.retryable ?? false,
    });
    this.name = 'ProviderError';
    this.providerId = options?.providerId ?? null;
    this.modelId = options?.modelId ?? null;
  }
}

/** API key or authentication credentials are invalid or expired. */
export class AuthenticationError extends ProviderError {
  constructor(
    message: string = '',
    options?: {
      providerId?: string;
      modelId?: string;
      details?: Record<string, unknown>;
    }
  ) {
    super(message, {
      providerId: options?.providerId,
      modelId: options?.modelId,
      details: options?.details,
      retryable: false,
    });
    this.name = 'AuthenticationError';
  }
}

/**
 * Provider rate limit or quota has been exceeded.
 */
export class RateLimitError extends ProviderError {
  /** Seconds to wait before retrying, if provided by the upstream API. */
  readonly retryAfter: number | null;

  constructor(
    message: string = '',
    options?: {
      providerId?: string;
      modelId?: string;
      retryAfter?: number;
      details?: Record<string, unknown>;
    }
  ) {
    super(message, {
      providerId: options?.providerId,
      modelId: options?.modelId,
      details: options?.details,
      retryable: true,
    });
    this.name = 'RateLimitError';
    this.retryAfter = options?.retryAfter ?? null;
  }
}

/** Request to the provider timed out. */
export class ProviderTimeoutError extends ProviderError {
  /** The configured timeout in seconds. */
  readonly timeoutSeconds: number | null;

  constructor(
    message: string = '',
    options?: {
      providerId?: string;
      modelId?: string;
      timeoutSeconds?: number;
      details?: Record<string, unknown>;
    }
  ) {
    super(message, {
      providerId: options?.providerId,
      modelId: options?.modelId,
      details: options?.details,
      retryable: true,
    });
    this.name = 'ProviderTimeoutError';
    this.timeoutSeconds = options?.timeoutSeconds ?? null;
  }
}

// -- Configuration errors ---------------------------------------------------

/**
 * Invalid or missing configuration.
 *
 * Raised during initialization when the config is malformed,
 * required fields are missing, or referenced connectors do not exist.
 */
export class ConfigurationError extends ModelMeshError {
  constructor(
    message: string = '',
    options?: {
      details?: Record<string, unknown>;
    }
  ) {
    super(message, {
      details: options?.details,
      retryable: false,
    });
    this.name = 'ConfigurationError';
  }
}

// -- Budget errors ----------------------------------------------------------

/**
 * Budget limit has been exceeded.
 *
 * Raised when a per-request, daily, or monthly cost limit is breached
 * and enforcement is enabled.
 */
export class BudgetExceededError extends ModelMeshError {
  /** Which limit was exceeded ("per_request", "daily", "monthly"). */
  readonly limitType: string | null;
  /** The configured limit value. */
  readonly limitValue: number | null;
  /** The actual cost or accumulated spend. */
  readonly actualValue: number | null;

  constructor(
    message: string = '',
    options?: {
      limitType?: string;
      limitValue?: number;
      actualValue?: number;
      details?: Record<string, unknown>;
    }
  ) {
    super(message, {
      details: options?.details,
      retryable: false,
    });
    this.name = 'BudgetExceededError';
    this.limitType = options?.limitType ?? null;
    this.limitValue = options?.limitValue ?? null;
    this.actualValue = options?.actualValue ?? null;
  }
}
