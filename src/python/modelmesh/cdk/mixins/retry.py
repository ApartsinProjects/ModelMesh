"""Cross-cutting retry logic with configurable exponential backoff.

Provides a ``RetryMixin`` that can be composed into any class via
multiple inheritance.  The mixin exposes a single async entry-point,
:meth:`_retry`, which executes an arbitrary async callable and
automatically retries on transient failures using exponential backoff
with optional jitter.

Typical usage::

    class MyService(RetryMixin):
        _retry_max_attempts = 5

        async def fetch(self, url: str) -> dict:
            return await self._retry(self._do_fetch, url)
"""
from __future__ import annotations

import asyncio
import random

__all__ = ["RetryMixin"]


class RetryMixin:
    """Configurable retry with exponential backoff.

    Mix into any class via multiple inheritance.  Call
    ``self._retry(async_fn, *args, **kwargs)`` to execute *async_fn*
    with automatic retry on failure.

    Class-level attributes control the retry policy and may be
    overridden on the subclass or instance:

    Attributes:
        _retry_max_attempts: Maximum number of attempts before the
            last error is re-raised.  Defaults to ``3``.
        _retry_base_delay: Base delay in seconds for the first
            backoff interval.  Defaults to ``1.0``.
        _retry_max_delay: Upper bound in seconds for any single
            backoff interval.  Defaults to ``30.0``.
        _retry_exponential_base: Exponential base applied to the
            attempt number when computing the delay.  Defaults to
            ``2.0``.
        _retry_jitter: When ``True``, each computed delay is
            multiplied by a random factor in ``[0.5, 1.5)`` to
            de-correlate concurrent callers.  Defaults to ``True``.
    """

    _retry_max_attempts: int = 3
    _retry_base_delay: float = 1.0
    _retry_max_delay: float = 30.0
    _retry_exponential_base: float = 2.0
    _retry_jitter: bool = True

    async def _retry(self, fn, *args, **kwargs):
        """Execute *fn* with retry logic.

        *fn* is called as ``await fn(*args, **kwargs)``.  If it raises
        an exception that :meth:`_is_retryable_error` considers
        retryable, the call is retried after an exponentially
        increasing delay (subject to jitter).  When all attempts are
        exhausted the last exception is re-raised.

        Args:
            fn: An async callable to execute.
            *args: Positional arguments forwarded to *fn*.
            **kwargs: Keyword arguments forwarded to *fn*.

        Returns:
            The return value of *fn* on the first successful call.

        Raises:
            Exception: The last exception raised by *fn* when all
                retry attempts have been exhausted, or immediately
                when :meth:`_is_retryable_error` returns ``False``.
        """
        last_error: Exception | None = None
        for attempt in range(self._retry_max_attempts):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt == self._retry_max_attempts - 1:
                    raise
                if not self._is_retryable_error(e):
                    raise
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)
        raise last_error  # type: ignore[misc]

    def _calculate_delay(self, attempt: int) -> float:
        """Compute the backoff delay for the given *attempt* number.

        The delay grows exponentially:

            delay = base_delay * (exponential_base ** attempt)

        It is clamped to :attr:`_retry_max_delay` and, when
        :attr:`_retry_jitter` is enabled, multiplied by a random
        factor drawn uniformly from ``[0.5, 1.5)``.

        Args:
            attempt: Zero-based attempt index (``0`` for the first
                retry, ``1`` for the second, etc.).

        Returns:
            The computed delay in seconds.
        """
        delay = self._retry_base_delay * (self._retry_exponential_base ** attempt)
        delay = min(delay, self._retry_max_delay)
        if self._retry_jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine whether *error* should trigger a retry.

        The default implementation returns ``True`` for all exceptions,
        meaning every failure is retried.  Override this method to
        restrict retries to specific exception types (e.g., transient
        network errors or rate-limit responses).

        Args:
            error: The exception raised by the target callable.

        Returns:
            ``True`` if the operation should be retried, ``False`` to
            propagate the exception immediately.
        """
        return True
