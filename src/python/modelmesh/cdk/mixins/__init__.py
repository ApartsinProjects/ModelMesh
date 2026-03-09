"""CDK Mixins -- reusable building blocks for connector implementations.

This package provides cross-cutting mixins that connector authors
compose into their classes via multiple inheritance.  Each mixin
delivers a focused piece of infrastructure -- retry logic, caching,
rate limiting, or metrics collection -- so that connectors do not
need to reimplement common patterns.

Re-exports:
    HttpClientMixin: Shared async HTTP client with retries and auth.
    RetryMixin: Configurable retry with exponential backoff and jitter.
    CacheMixin: TTL-based in-memory cache with LRU eviction.
    CacheStats: Dataclass for cache performance counters.
    RateLimiterMixin: Client-side RPM / TPM rate limiting.
    MetricsMixin: Automatic latency, error rate, and throughput tracking.
    MetricSnapshot: Dataclass for point-in-time metric aggregates.
"""
from __future__ import annotations

from modelmesh.cdk.mixins.cache import CacheMixin, CacheStats
from modelmesh.cdk.mixins.http_client import HttpClientMixin
from modelmesh.cdk.mixins.metrics import MetricsMixin, MetricSnapshot
from modelmesh.cdk.mixins.rate_limiter import RateLimiterMixin
from modelmesh.cdk.mixins.retry import RetryMixin

__all__ = [
    "CacheMixin",
    "CacheStats",
    "HttpClientMixin",
    "MetricsMixin",
    "MetricSnapshot",
    "RateLimiterMixin",
    "RetryMixin",
]
