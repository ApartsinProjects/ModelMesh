"""Automatic latency, error rate, and throughput tracking.

Provides a ``MetricsMixin`` that can be composed into any class via
multiple inheritance.  The mixin records request outcomes, latency
distributions, token counts, and cost, then exposes a snapshot
method that computes aggregate statistics on demand.

Typical usage::

    class MyProvider(MetricsMixin):
        def __init__(self):
            self.__init_metrics__()

        async def complete(self, prompt: str) -> str:
            with self._metrics_track_request():
                response = await self._call_api(prompt)
            self._metrics_record_tokens(response.usage.total_tokens, cost=0.002)
            return response.text

        def report(self) -> MetricSnapshot:
            return self._metrics_snapshot()
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass

__all__ = ["MetricsMixin", "MetricSnapshot"]


@dataclass
class MetricSnapshot:
    """Point-in-time aggregate of collected metrics.

    All latency values are in milliseconds.  Rates and throughput
    are computed over the elapsed wall-clock time since the last
    :meth:`MetricsMixin._metrics_reset` (or initialization).

    Attributes:
        total_requests: Total number of requests tracked (success +
            failure).
        successful_requests: Number of requests that completed
            without raising an exception.
        failed_requests: Number of requests that raised an exception.
        total_tokens: Cumulative token count recorded via
            :meth:`MetricsMixin._metrics_record_tokens`.
        total_cost: Cumulative cost recorded via
            :meth:`MetricsMixin._metrics_record_tokens`.
        avg_latency_ms: Arithmetic mean of recorded latencies.
        p50_latency_ms: Median (50th percentile) latency.
        p95_latency_ms: 95th percentile latency.
        p99_latency_ms: 99th percentile latency.
        error_rate: Fraction of requests that failed, between ``0.0``
            and ``1.0``.
        requests_per_minute: Average throughput in requests per
            minute since the metrics window started.
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate: float = 0.0
    requests_per_minute: float = 0.0


class MetricsMixin:
    """Automatic metrics tracking for request latency, errors, and throughput.

    Mix into any class via multiple inheritance.  Call
    :meth:`__init_metrics__` during initialization, then wrap each
    request in :meth:`_metrics_track_request` to record latency and
    success/failure status.  Use :meth:`_metrics_record_tokens` to
    accumulate token and cost totals, and :meth:`_metrics_snapshot`
    to retrieve a point-in-time aggregate.

    Latencies are stored as a flat list in milliseconds.  Percentile
    calculations use nearest-rank interpolation over the sorted
    latency list.
    """

    def __init_metrics__(self) -> None:
        """Initialize metrics internal state.

        Must be called before any other metrics method.  Resets all
        counters and records the current wall-clock time as the start
        of the measurement window.
        """
        self._metrics_latencies: list[float] = []
        self._metrics_total_requests: int = 0
        self._metrics_successful: int = 0
        self._metrics_failed: int = 0
        self._metrics_total_tokens: int = 0
        self._metrics_total_cost: float = 0.0
        self._metrics_start_time: float = time.time()

    @contextmanager
    def _metrics_track_request(self):
        """Context manager that records latency and outcome for a request.

        Wrap the body of a request handler in this context manager.
        On normal exit the request is counted as successful; if an
        exception propagates the request is counted as failed (and
        the exception is re-raised).  In both cases the elapsed time
        is appended to the latency list.

        Yields:
            Control to the caller's ``with`` block.

        Example::

            with self._metrics_track_request():
                result = await self._call_api(payload)
        """
        start = time.time()
        try:
            yield
            self._metrics_successful += 1
        except Exception:
            self._metrics_failed += 1
            raise
        finally:
            self._metrics_total_requests += 1
            self._metrics_latencies.append((time.time() - start) * 1000)

    def _metrics_record_tokens(self, tokens: int, cost: float = 0.0) -> None:
        """Record token usage and cost for a completed request.

        Call this after receiving a response to accumulate totals
        that appear in the next :meth:`_metrics_snapshot`.

        Args:
            tokens: Number of tokens consumed (input + output).
            cost: Monetary cost of the request in the provider's
                billing currency.  Defaults to ``0.0``.
        """
        self._metrics_total_tokens += tokens
        self._metrics_total_cost += cost

    def _metrics_snapshot(self) -> MetricSnapshot:
        """Compute and return a point-in-time aggregate of all metrics.

        Percentile latencies are calculated using nearest-rank
        interpolation over the sorted latency list.  If no latencies
        have been recorded, all latency fields are ``0.0``.

        Returns:
            A :class:`MetricSnapshot` with current aggregate values.
        """
        sorted_lat = sorted(self._metrics_latencies) if self._metrics_latencies else [0]
        elapsed_min = max((time.time() - self._metrics_start_time) / 60, 0.001)

        return MetricSnapshot(
            total_requests=self._metrics_total_requests,
            successful_requests=self._metrics_successful,
            failed_requests=self._metrics_failed,
            total_tokens=self._metrics_total_tokens,
            total_cost=self._metrics_total_cost,
            avg_latency_ms=sum(sorted_lat) / len(sorted_lat),
            p50_latency_ms=sorted_lat[len(sorted_lat) // 2],
            p95_latency_ms=sorted_lat[int(len(sorted_lat) * 0.95)],
            p99_latency_ms=sorted_lat[int(len(sorted_lat) * 0.99)],
            error_rate=self._metrics_failed / max(self._metrics_total_requests, 1),
            requests_per_minute=self._metrics_total_requests / elapsed_min,
        )

    def _metrics_reset(self) -> None:
        """Reset all metrics to their initial state.

        Clears the latency list, zeroes all counters, and resets the
        measurement window start time to now.
        """
        self._metrics_latencies.clear()
        self._metrics_total_requests = 0
        self._metrics_successful = 0
        self._metrics_failed = 0
        self._metrics_total_tokens = 0
        self._metrics_total_cost = 0.0
        self._metrics_start_time = time.time()
