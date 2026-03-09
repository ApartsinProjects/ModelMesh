"""Client-side rate limiting using a sliding-window token bucket.

Provides a ``RateLimiterMixin`` that can be composed into any class
via multiple inheritance.  The mixin enforces requests-per-minute
(RPM) and tokens-per-minute (TPM) limits as well as an optional
minimum delay between consecutive requests.

Typical usage::

    class MyProvider(RateLimiterMixin):
        _rate_limit_rpm = 120
        _rate_limit_tpm = 200_000

        async def complete(self, prompt: str) -> str:
            await self._rate_limit_acquire(estimated_tokens=500)
            response = await self._call_api(prompt)
            self._rate_limit_record_tokens(response.usage.total_tokens)
            return response.text
"""
from __future__ import annotations

import asyncio
import time

__all__ = ["RateLimiterMixin"]


class RateLimiterMixin:
    """Client-side rate limiting with RPM, TPM, and minimum-delay controls.

    Mix into any class via multiple inheritance.  Call
    :meth:`_rate_limit_acquire` before making a request to ensure
    rate limits are respected.  After receiving a response, call
    :meth:`_rate_limit_record_tokens` to record actual token usage
    for accurate TPM tracking.

    The implementation uses a sliding one-minute window: timestamps
    and token counts older than 60 seconds are pruned on each
    acquire call.

    Class-level attributes control the limits and may be overridden
    on the subclass or instance:

    Attributes:
        _rate_limit_rpm: Maximum requests allowed per minute.
            Defaults to ``60``.
        _rate_limit_tpm: Maximum tokens allowed per minute.
            Defaults to ``100_000``.
        _rate_limit_min_delay: Minimum delay in seconds between
            consecutive requests.  Set to ``0`` to disable.
            Defaults to ``0``.
    """

    _rate_limit_rpm: int = 60
    _rate_limit_tpm: int = 100_000
    _rate_limit_min_delay: float = 0

    def __init_rate_limiter__(self) -> None:
        """Initialize rate limiter internal state.

        Must be called before :meth:`_rate_limit_acquire` or
        :meth:`_rate_limit_record_tokens`.  Sets up the sliding
        window data structures.
        """
        self._request_timestamps: list[float] = []
        self._token_counts: list[tuple[float, int]] = []  # (timestamp, tokens)
        self._last_request_at: float = 0

    async def _rate_limit_acquire(self, estimated_tokens: int = 0) -> None:
        """Wait until rate limits allow a new request.

        Blocks the caller (via :func:`asyncio.sleep`) until the
        request can be issued without exceeding the configured RPM,
        TPM, or minimum-delay constraints.

        Args:
            estimated_tokens: Estimated token count for the upcoming
                request.  Used for proactive TPM enforcement.  Pass
                ``0`` to skip token-based limiting.
        """
        now = time.time()
        window_start = now - 60.0

        # Clean old entries outside the sliding window
        self._request_timestamps = [
            t for t in self._request_timestamps if t > window_start
        ]
        self._token_counts = [
            (t, n) for t, n in self._token_counts if t > window_start
        ]

        # Check RPM -- wait until the oldest request in the window
        # has expired if we are at capacity.
        while len(self._request_timestamps) >= self._rate_limit_rpm:
            wait = self._request_timestamps[0] - window_start
            await asyncio.sleep(max(wait, 0.1))
            now = time.time()
            window_start = now - 60.0
            self._request_timestamps = [
                t for t in self._request_timestamps if t > window_start
            ]

        # Check TPM -- if the estimated request would push us over
        # the limit, apply a simple back-off pause.
        current_tokens = sum(n for _, n in self._token_counts)
        if current_tokens + estimated_tokens > self._rate_limit_tpm:
            await asyncio.sleep(1.0)

        # Enforce minimum delay between consecutive requests
        if self._rate_limit_min_delay > 0:
            elapsed = now - self._last_request_at
            if elapsed < self._rate_limit_min_delay:
                await asyncio.sleep(self._rate_limit_min_delay - elapsed)

        self._request_timestamps.append(time.time())
        self._last_request_at = time.time()

    def _rate_limit_record_tokens(self, tokens: int) -> None:
        """Record actual token usage after a response is received.

        Call this after completing a request to keep the TPM counter
        accurate.  The recorded count contributes to the sliding
        window used by :meth:`_rate_limit_acquire`.

        Args:
            tokens: Number of tokens consumed by the completed
                request (input + output).
        """
        self._token_counts.append((time.time(), tokens))
