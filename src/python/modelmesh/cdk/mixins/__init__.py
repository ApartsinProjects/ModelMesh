"""CDK Mixins -- reusable building blocks for connector implementations.

This package provides cross-cutting mixins that connector authors
compose into their classes via multiple inheritance.  Each mixin
delivers a focused piece of infrastructure -- retry logic, caching,
rate limiting, metrics collection, circuit breaking, timeout
enforcement, or streaming checkpoints -- so that connectors do not
need to reimplement common patterns.

Re-exports:
    HttpClientMixin: Shared async HTTP client with retries and auth.
    RetryMixin: Configurable retry with exponential backoff and jitter.
    CacheMixin: TTL-based in-memory cache with LRU eviction.
    CacheStats: Dataclass for cache performance counters.
    RateLimiterMixin: Client-side RPM / TPM rate limiting.
    MetricsMixin: Automatic latency, error rate, and throughput tracking.
    MetricSnapshot: Dataclass for point-in-time metric aggregates.
    CircuitBreakerMixin: Circuit breaker pattern for provider protection.
    CircuitState: Current circuit breaker state enum.
    CircuitOpenError: Raised when circuit is open.
    TimeoutMixin: Per-request timeout enforcement.
    RequestTimeoutError: Raised when request exceeds timeout.
    StreamingCheckpointMixin: Stream progress tracking and resume.
    StreamCheckpoint: Individual stream checkpoint state.
"""
from __future__ import annotations

from modelmesh.cdk.mixins.cache import CacheMixin, CacheStats
from modelmesh.cdk.mixins.circuit_breaker import (
    CircuitBreakerMixin,
    CircuitOpenError,
    CircuitState,
)
from modelmesh.cdk.mixins.http_client import HttpClientMixin
from modelmesh.cdk.mixins.metrics import MetricsMixin, MetricSnapshot
from modelmesh.cdk.mixins.rate_limiter import RateLimiterMixin
from modelmesh.cdk.mixins.retry import RetryMixin
from modelmesh.cdk.mixins.streaming_checkpoint import (
    StreamCheckpoint,
    StreamingCheckpointMixin,
)
from modelmesh.cdk.mixins.timeout import RequestTimeoutError, TimeoutMixin

__all__ = [
    "CacheMixin",
    "CacheStats",
    "CircuitBreakerMixin",
    "CircuitOpenError",
    "CircuitState",
    "HttpClientMixin",
    "MetricsMixin",
    "MetricSnapshot",
    "RateLimiterMixin",
    "RequestTimeoutError",
    "RetryMixin",
    "StreamCheckpoint",
    "StreamingCheckpointMixin",
    "TimeoutMixin",
]
