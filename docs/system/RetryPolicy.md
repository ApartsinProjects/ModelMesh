---
layout: default
title: "RetryPolicy"
---

# RetryPolicy

Configurable retry logic applied before rotation. On failure, determines whether to retry the same model (with backoff) or rotate to the next candidate. Retry attempts count toward the deactivation threshold managed by the `DeactivationEvaluator`.

**Depends on:** [Model](Model.md), [RotationPolicyService](RotationPolicyService.md).

---

## Python

```python
from __future__ import annotations

from enum import Enum


class BackoffStrategy(Enum):
    """Strategy for computing delay between retry attempts."""

    FIXED = "fixed"
    """Constant delay between retries."""

    EXPONENTIAL_JITTER = "exponential_jitter"
    """Exponential backoff with random jitter."""

    RETRY_AFTER = "retry_after"
    """Honor the Retry-After header from the provider response."""


class RetryScope(Enum):
    """Scope of retry behavior before rotation."""

    SAME_MODEL = "same_model"
    """Retry on the same model instance."""

    SAME_PROVIDER = "same_provider"
    """Retry on a different model from the same provider."""

    ANY = "any"
    """Retry on a model from any provider."""


class ErrorClassification(Enum):
    """Classification of an error for retry decisions."""

    RETRYABLE = "retryable"
    """Error is transient and the request should be retried."""

    NON_RETRYABLE = "non_retryable"
    """Error is permanent and the request should not be retried."""

    RATE_LIMITED = "rate_limited"
    """Rate limit hit; retry after the indicated delay."""


class RetryPolicy:
    """Configurable retry logic with backoff before rotation."""

    _max_attempts: int
    _backoff: BackoffStrategy
    _initial_delay: float
    _max_delay: float
    _scope: RetryScope

    def __init__(
        self,
        max_attempts: int = 3,
        backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER,
        initial_delay: float = 0.5,
        max_delay: float = 10.0,
        scope: RetryScope = RetryScope.SAME_MODEL,
    ) -> None:
        self._max_attempts = max_attempts
        self._backoff = backoff
        self._initial_delay = initial_delay
        self._max_delay = max_delay
        self._scope = scope

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Return whether the error is retryable and attempts remain.

        Args:
            error: The exception raised by the provider.
            attempt: Current attempt number (1-based).

        Returns:
            True if the request should be retried.
        """
        ...

    def get_delay(self, attempt: int) -> float:
        """Return the backoff delay in seconds for the given attempt number.

        Args:
            attempt: Current attempt number (1-based).

        Returns:
            Delay in seconds before the next retry.
        """
        ...

    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify an error as retryable, non-retryable, or rate-limited.

        Args:
            error: The exception raised by the provider.

        Returns:
            The error classification.
        """
        ...
```

---

## TypeScript

```typescript
enum BackoffStrategy {
  /** Constant delay between retries. */
  FIXED = "fixed",
  /** Exponential backoff with random jitter. */
  EXPONENTIAL_JITTER = "exponential_jitter",
  /** Honor the Retry-After header from the provider response. */
  RETRY_AFTER = "retry_after",
}

enum RetryScope {
  /** Retry on the same model instance. */
  SAME_MODEL = "same_model",
  /** Retry on a different model from the same provider. */
  SAME_PROVIDER = "same_provider",
  /** Retry on a model from any provider. */
  ANY = "any",
}

enum ErrorClassification {
  /** Error is transient and the request should be retried. */
  RETRYABLE = "retryable",
  /** Error is permanent and the request should not be retried. */
  NON_RETRYABLE = "non_retryable",
  /** Rate limit hit; retry after the indicated delay. */
  RATE_LIMITED = "rate_limited",
}

class RetryPolicy {
  private maxAttempts: number;
  private backoff: BackoffStrategy;
  private initialDelay: number;
  private maxDelay: number;
  private scope: RetryScope;

  constructor(
    maxAttempts?: number,
    backoff?: BackoffStrategy,
    initialDelay?: number,
    maxDelay?: number,
    scope?: RetryScope,
  );

  /** Return whether the error is retryable and attempts remain. */
  shouldRetry(error: Error, attempt: number): boolean;

  /** Return the backoff delay in seconds for the given attempt number. */
  getDelay(attempt: number): number;

  /** Classify an error as retryable, non-retryable, or rate-limited. */
  classifyError(error: Error): ErrorClassification;
}
```

---

## Configuration

Retry parameters are configured per pool. See [SystemConfiguration.md -- Pools](../SystemConfiguration.md#pools).

| Parameter | Type | Description |
| --- | --- | --- |
| `retry.max_attempts` | integer | Retries on same model before rotating. |
| `retry.backoff` | string | Backoff strategy: `fixed`, `exponential_jitter`, `retry_after`. |
| `retry.initial_delay` | duration | First retry delay (e.g., `500ms`). |
| `retry.max_delay` | duration | Maximum backoff delay (e.g., `10s`). |
| `retry.retryable_codes` | list | HTTP codes eligible for retry (e.g., `[429, 500, 502, 503]`). |
| `retry.non_retryable_codes` | list | HTTP codes that skip retry and rotate immediately (e.g., `[400, 401, 403]`). |
| `retry.scope` | string | Retry scope: `same_model`, `same_provider`, `any`. |
| `retry.honor_retry_after` | boolean | Use provider's `Retry-After` header when present. |
