"""TTL-based in-memory cache with LRU eviction.

Provides a ``CacheMixin`` that can be composed into any class via
multiple inheritance.  The mixin stores values alongside monotonic
timestamps and evicts expired entries lazily on read.  When the
maximum entry count is reached, the least-recently-accessed entry is
evicted to make room.

Typical usage::

    class MyService(CacheMixin):
        def __init__(self):
            self._init_cache(ttl_ms=60_000, max_entries=256)

        def get_data(self, key: str):
            cached = self._cache_get(key)
            if cached is not None:
                return cached
            value = self._fetch_data(key)
            self._cache_set(key, value)
            return value
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

__all__ = ["CacheMixin", "CacheStats"]


@dataclass
class CacheStats:
    """Counters for cache performance monitoring.

    Attributes:
        hits: Number of cache hits (key found and not expired).
        misses: Number of cache misses (key absent or expired).
        evictions: Number of entries evicted due to capacity limits.
        size: Current number of live entries in the cache.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0


class CacheMixin:
    """TTL-based in-memory cache with LRU eviction.

    Mix into any class via multiple inheritance.  Call
    :meth:`_init_cache` during initialization to set up the internal
    store, then use :meth:`_cache_get` and :meth:`_cache_set` to
    read and write cached values.

    Entries are stored in a dict mapping keys to
    ``(created, last_accessed, value)`` tuples.  A :meth:`_cache_get`
    checks the TTL and returns ``None`` for expired entries (lazy
    expiration).  When :meth:`_cache_set` is called and the store is
    at capacity for a new key, the least-recently-accessed entry is
    evicted.

    Performance counters (hits, misses, evictions) are tracked and
    can be retrieved via :meth:`_cache_stats`.  Counters are reset
    when :meth:`_cache_clear` is called.
    """

    _cache_store: dict[str, tuple[float, float, Any]]  # key -> (created, accessed, value)
    _cache_ttl_ms: float = 60_000
    _cache_max_entries: int = 1024
    _cache_hits: int = 0
    _cache_misses: int = 0
    _cache_evictions: int = 0

    def _init_cache(
        self, ttl_ms: float = 60_000, max_entries: int = 1024
    ) -> None:
        """Initialize the cache.

        Must be called before any other cache method.  Resets internal
        state including the entry store and all performance counters.

        Args:
            ttl_ms: Time-to-live for each entry in milliseconds.
                Entries older than this are treated as expired on the
                next read.
            max_entries: Maximum number of entries before LRU eviction
                kicks in on :meth:`_cache_set`.
        """
        self._cache_store = {}
        self._cache_ttl_ms = ttl_ms
        self._cache_max_entries = max_entries
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0

    def _cache_get(self, key: str) -> Any | None:
        """Retrieve a cached value by key.

        Returns ``None`` if the key is not found or the entry has
        expired.  Expired entries are removed lazily on access.  On a
        cache hit the entry's last-accessed timestamp is updated for
        LRU tracking.

        Args:
            key: Cache key.

        Returns:
            The cached value, or ``None`` if missing or expired.
        """
        entry = self._cache_store.get(key)
        if entry is None:
            self._cache_misses += 1
            return None

        created, _accessed, value = entry
        now = time.monotonic()
        elapsed_ms = (now - created) * 1000

        if elapsed_ms > self._cache_ttl_ms:
            del self._cache_store[key]
            self._cache_misses += 1
            return None

        # Update access time for LRU tracking
        self._cache_store[key] = (created, now, value)
        self._cache_hits += 1
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        """Store a value under the given key.

        If the cache is at maximum capacity and the key is new, the
        least-recently-accessed entry is evicted first.

        Args:
            key: Cache key.
            value: Value to store.
        """
        now = time.monotonic()

        if key not in self._cache_store and len(self._cache_store) >= self._cache_max_entries:
            # Evict the least-recently-accessed entry
            lru_key = min(self._cache_store, key=lambda k: self._cache_store[k][1])
            del self._cache_store[lru_key]
            self._cache_evictions += 1

        self._cache_store[key] = (now, now, value)

    def _cache_invalidate(self, key: str) -> None:
        """Remove a single key from the cache.

        This is a no-op if the key does not exist.

        Args:
            key: Cache key to remove.
        """
        self._cache_store.pop(key, None)

    def _cache_clear(self) -> None:
        """Remove all entries and reset stats counters."""
        self._cache_store.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0

    def _cache_stats(self) -> CacheStats:
        """Return current cache performance counters.

        Returns:
            A :class:`CacheStats` instance with hits, misses,
            evictions, and current size.
        """
        return CacheStats(
            hits=self._cache_hits,
            misses=self._cache_misses,
            evictions=self._cache_evictions,
            size=len(self._cache_store),
        )
