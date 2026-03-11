---
layout: default
title: "CDK Mixins Reference"
---

# CDK Mixins Reference

Mixins are reusable building blocks that connector authors compose into their implementations. Each mixin provides a focused set of functionality -- HTTP communication, caching, serialization, metrics, or configuration validation -- so that connectors do not need to reimplement common infrastructure.

**Python** uses multiple inheritance. A connector class inherits from both its base interface and any number of mixins. Method resolution follows the standard MRO (C3 linearization), and `__init__` cooperates via `super()`.

**TypeScript** uses composition. Because TypeScript interfaces cannot carry implementation, mixins are standalone helper objects created by factory functions. The connector receives them through its constructor and delegates to their methods explicitly.

> **Cross-references:** Types referenced below are defined in the interface documentation:
> - [Provider](../interfaces/Provider.html) -- `CompletionRequest`, `CompletionResponse`, `TokenUsage`
> - [Storage](../interfaces/Storage.html) -- `SerializationFormat`
> - [Rotation Policy](../interfaces/RotationPolicy.html) -- `ModelSnapshot`

---

## HttpClientMixin

Shared async HTTP client with automatic retries, timeout management, and authorization header injection. Every provider connector that communicates over HTTP should use this mixin rather than managing its own client lifecycle.

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `_init_http_client` | `(base_url, timeout, max_retries, headers)` | Create the underlying HTTP client with the given base URL, timeout (seconds), retry limit, and default headers. |
| `_http_get` | `(path, **kwargs)` | Issue a GET request to `base_url + path`. Returns the parsed JSON response body. |
| `_http_post` | `(path, json, **kwargs)` | Issue a POST request with a JSON body. Returns the parsed JSON response body. |
| `_http_stream` | `(path, json, **kwargs) -> AsyncIterator[str]` | Issue a POST request and yield Server-Sent Event data lines as they arrive. |
| `_close_http_client` | `()` | Close the underlying HTTP client and release resources. |

### Behavior

- Creates an `httpx.AsyncClient` (Python) or a `fetch`-based wrapper (TypeScript).
- Automatically injects an `Authorization: Bearer <token>` header when a token is present.
- Retries on HTTP 429, 500, 502, and 503 with exponential backoff (base 1 s, factor 2, jitter up to 0.5 s).
- Raises after `max_retries` exhausted.

### Python

```python
import asyncio
import random
from typing import Any, AsyncIterator

import httpx


class HttpClientMixin:
    """Shared async HTTP client with retries and authorization.

    Provides a managed httpx.AsyncClient that automatically injects
    authorization headers and retries transient failures with
    exponential backoff.
    """

    _http_client: httpx.AsyncClient | None = None
    _http_base_url: str = ""
    _http_max_retries: int = 3
    _http_auth_token: str | None = None

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503}

    def _init_http_client(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Create the underlying HTTP client.

        Args:
            base_url: Base URL for all requests (e.g. "https://api.openai.com/v1").
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for transient failures.
            headers: Additional default headers merged into every request.
        """
        self._http_base_url = base_url.rstrip("/")
        self._http_max_retries = max_retries

        default_headers = dict(headers or {})
        if self._http_auth_token:
            default_headers["Authorization"] = f"Bearer {self._http_auth_token}"

        self._http_client = httpx.AsyncClient(
            base_url=self._http_base_url,
            timeout=httpx.Timeout(timeout),
            headers=default_headers,
        )

    async def _http_get(self, path: str, **kwargs: Any) -> Any:
        """Issue a GET request and return the parsed JSON body.

        Args:
            path: URL path appended to the base URL.
            **kwargs: Additional keyword arguments forwarded to httpx.

        Returns:
            Parsed JSON response body.

        Raises:
            httpx.HTTPStatusError: After retries are exhausted.
        """
        return await self._request_with_retry("GET", path, **kwargs)

    async def _http_post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        """Issue a POST request with a JSON body and return the parsed response.

        Args:
            path: URL path appended to the base URL.
            json: Request body serialized as JSON.
            **kwargs: Additional keyword arguments forwarded to httpx.

        Returns:
            Parsed JSON response body.

        Raises:
            httpx.HTTPStatusError: After retries are exhausted.
        """
        return await self._request_with_retry("POST", path, json=json, **kwargs)

    async def _http_stream(
        self, path: str, json: Any = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        """Issue a streaming POST request and yield SSE data lines.

        Args:
            path: URL path appended to the base URL.
            json: Request body serialized as JSON.
            **kwargs: Additional keyword arguments forwarded to httpx.

        Yields:
            Individual data lines from the Server-Sent Events stream.
        """
        assert self._http_client is not None, "Call _init_http_client first"
        async with self._http_client.stream(
            "POST", path, json=json, **kwargs
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    async def _close_http_client(self) -> None:
        """Close the HTTP client and release connection pool resources."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _request_with_retry(
        self, method: str, path: str, **kwargs: Any
    ) -> Any:
        """Execute a request with exponential backoff on transient errors.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path appended to the base URL.
            **kwargs: Forwarded to the httpx request.

        Returns:
            Parsed JSON response body.

        Raises:
            httpx.HTTPStatusError: When retries are exhausted.
        """
        assert self._http_client is not None, "Call _init_http_client first"
        last_error: Exception | None = None

        for attempt in range(self._http_max_retries + 1):
            try:
                response = await self._http_client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in self.RETRYABLE_STATUS_CODES:
                    raise
                if attempt < self._http_max_retries:
                    delay = (2 ** attempt) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]
```

### TypeScript

```typescript
/**
 * Shared async HTTP client with retries and authorization.
 *
 * Uses the Fetch API to issue requests. Automatically injects
 * authorization headers and retries transient failures with
 * exponential backoff.
 */
class HttpClient {
    private baseUrl: string = "";
    private maxRetries: number = 3;
    private timeout: number = 30_000;
    private defaultHeaders: Record<string, string> = {};

    private static readonly RETRYABLE_STATUS_CODES = new Set([429, 500, 502, 503]);

    /**
     * Initialize the HTTP client.
     *
     * @param baseUrl - Base URL for all requests.
     * @param timeout - Request timeout in milliseconds.
     * @param maxRetries - Maximum retry attempts for transient failures.
     * @param headers - Additional default headers merged into every request.
     */
    init(
        baseUrl: string,
        timeout: number = 30_000,
        maxRetries: number = 3,
        headers: Record<string, string> = {},
    ): void {
        this.baseUrl = baseUrl.replace(/\/+$/, "");
        this.timeout = timeout;
        this.maxRetries = maxRetries;
        this.defaultHeaders = { ...headers };
    }

    /** Set the bearer token injected into every request. */
    setAuthToken(token: string): void {
        this.defaultHeaders["Authorization"] = `Bearer ${token}`;
    }

    /**
     * Issue a GET request and return the parsed JSON body.
     *
     * @param path - URL path appended to the base URL.
     * @param options - Additional fetch options.
     * @returns Parsed JSON response body.
     */
    async get<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
        return this.requestWithRetry<T>("GET", path, undefined, options);
    }

    /**
     * Issue a POST request with a JSON body and return the parsed response.
     *
     * @param path - URL path appended to the base URL.
     * @param body - Request body serialized as JSON.
     * @param options - Additional fetch options.
     * @returns Parsed JSON response body.
     */
    async post<T = unknown>(
        path: string,
        body?: unknown,
        options: RequestInit = {},
    ): Promise<T> {
        return this.requestWithRetry<T>("POST", path, body, options);
    }

    /**
     * Issue a streaming POST request and yield SSE data lines.
     *
     * @param path - URL path appended to the base URL.
     * @param body - Request body serialized as JSON.
     * @param options - Additional fetch options.
     * @yields Individual data lines from the Server-Sent Events stream.
     */
    async *stream(
        path: string,
        body?: unknown,
        options: RequestInit = {},
    ): AsyncGenerator<string> {
        const url = `${this.baseUrl}${path}`;
        const response = await fetch(url, {
            method: "POST",
            headers: {
                ...this.defaultHeaders,
                "Content-Type": "application/json",
                ...((options.headers as Record<string, string>) ?? {}),
            },
            body: body != null ? JSON.stringify(body) : undefined,
            signal: AbortSignal.timeout(this.timeout),
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop()!;

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    yield line.slice(6);
                }
            }
        }
    }

    /** Close the HTTP client and release resources. */
    close(): void {
        this.defaultHeaders = {};
    }

    private async requestWithRetry<T>(
        method: string,
        path: string,
        body?: unknown,
        options: RequestInit = {},
    ): Promise<T> {
        let lastError: Error | null = null;
        const url = `${this.baseUrl}${path}`;

        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                const response = await fetch(url, {
                    method,
                    headers: {
                        ...this.defaultHeaders,
                        "Content-Type": "application/json",
                        ...((options.headers as Record<string, string>) ?? {}),
                    },
                    body: body != null ? JSON.stringify(body) : undefined,
                    signal: AbortSignal.timeout(this.timeout),
                });

                if (!response.ok) {
                    if (!HttpClient.RETRYABLE_STATUS_CODES.has(response.status)) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    throw new Error(`HTTP ${response.status}: retryable`);
                }

                return (await response.json()) as T;
            } catch (error) {
                lastError = error as Error;
                if (attempt < this.maxRetries) {
                    const delay = 2 ** attempt + Math.random() * 0.5;
                    await new Promise((resolve) => setTimeout(resolve, delay * 1000));
                }
            }
        }

        throw lastError!;
    }
}
```

---

## CacheMixin

TTL-based in-memory cache with LRU eviction. Useful for caching model catalogue responses, pricing data, or any provider query result that does not change on every request.

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `_init_cache` | `(ttl_ms, max_entries)` | Initialize the cache with a TTL (milliseconds) and a maximum entry count. |
| `_cache_get` | `(key)` | Retrieve a cached value by key, or `None`/`null` if missing or expired. |
| `_cache_set` | `(key, value)` | Store a value under the given key. Evicts the oldest entry if at capacity. |
| `_cache_invalidate` | `(key)` | Remove a single key from the cache. |
| `_cache_clear` | `()` | Remove all entries from the cache. |
| `_cache_stats` | `()` | Return hit/miss/eviction counters and current size. |

### Behavior

- Entries are stored in a dict (Python) or `Map` (TypeScript) with monotonic timestamps.
- A `get` checks TTL and returns `None`/`null` for expired entries (lazy expiration).
- When `max_entries` is reached on `set`, the entry with the oldest access time is evicted (LRU).
- Stats counters reset on `_cache_clear`.

### Python

```python
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheStats:
    """Counters for cache performance monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0


class CacheMixin:
    """TTL-based in-memory cache with LRU eviction.

    Stores values alongside monotonic timestamps. Expired entries are
    removed lazily on read. When the maximum entry count is reached,
    the least-recently-accessed entry is evicted.
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

        Args:
            ttl_ms: Time-to-live for each entry in milliseconds.
            max_entries: Maximum number of entries before LRU eviction.
        """
        self._cache_store = {}
        self._cache_ttl_ms = ttl_ms
        self._cache_max_entries = max_entries
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0

    def _cache_get(self, key: str) -> Any | None:
        """Retrieve a cached value by key.

        Returns None if the key is not found or the entry has expired.
        Expired entries are removed lazily on access.

        Args:
            key: Cache key.

        Returns:
            The cached value, or None if missing or expired.
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
            A CacheStats instance with hits, misses, evictions, and size.
        """
        return CacheStats(
            hits=self._cache_hits,
            misses=self._cache_misses,
            evictions=self._cache_evictions,
            size=len(self._cache_store),
        )
```

### TypeScript

```typescript
/** Counters for cache performance monitoring. */
interface CacheStats {
    hits: number;
    misses: number;
    evictions: number;
    size: number;
}

/** Internal cache entry storing creation time, access time, and value. */
interface CacheEntry<T> {
    created: number;
    accessed: number;
    value: T;
}

/**
 * TTL-based in-memory cache with LRU eviction.
 *
 * Stores values alongside monotonic timestamps. Expired entries are
 * removed lazily on read. When the maximum entry count is reached,
 * the least-recently-accessed entry is evicted.
 */
class Cache<T = unknown> {
    private store = new Map<string, CacheEntry<T>>();
    private ttlMs: number;
    private maxEntries: number;
    private hits = 0;
    private misses = 0;
    private evictions = 0;

    /**
     * Create a new Cache instance.
     *
     * @param ttlMs - Time-to-live for each entry in milliseconds.
     * @param maxEntries - Maximum number of entries before LRU eviction.
     */
    constructor(ttlMs: number = 60_000, maxEntries: number = 1024) {
        this.ttlMs = ttlMs;
        this.maxEntries = maxEntries;
    }

    /**
     * Retrieve a cached value by key.
     * Returns null if the key is not found or the entry has expired.
     *
     * @param key - Cache key.
     * @returns The cached value, or null if missing or expired.
     */
    get(key: string): T | null {
        const entry = this.store.get(key);
        if (!entry) {
            this.misses++;
            return null;
        }

        const now = performance.now();
        if (now - entry.created > this.ttlMs) {
            this.store.delete(key);
            this.misses++;
            return null;
        }

        entry.accessed = now;
        this.hits++;
        return entry.value;
    }

    /**
     * Store a value under the given key.
     * If the cache is at capacity and the key is new, the
     * least-recently-accessed entry is evicted.
     *
     * @param key - Cache key.
     * @param value - Value to store.
     */
    set(key: string, value: T): void {
        const now = performance.now();

        if (!this.store.has(key) && this.store.size >= this.maxEntries) {
            let lruKey: string | null = null;
            let lruTime = Infinity;
            for (const [k, entry] of this.store) {
                if (entry.accessed < lruTime) {
                    lruTime = entry.accessed;
                    lruKey = k;
                }
            }
            if (lruKey !== null) {
                this.store.delete(lruKey);
                this.evictions++;
            }
        }

        this.store.set(key, { created: now, accessed: now, value });
    }

    /**
     * Remove a single key from the cache.
     *
     * @param key - Cache key to remove.
     */
    invalidate(key: string): void {
        this.store.delete(key);
    }

    /** Remove all entries and reset stats counters. */
    clear(): void {
        this.store.clear();
        this.hits = 0;
        this.misses = 0;
        this.evictions = 0;
    }

    /**
     * Return current cache performance counters.
     *
     * @returns Cache statistics including hits, misses, evictions, and size.
     */
    stats(): CacheStats {
        return {
            hits: this.hits,
            misses: this.misses,
            evictions: this.evictions,
            size: this.store.size,
        };
    }
}
```

---

## FileSerializerMixin

JSON, YAML, and msgpack serialization with atomic file writes. Used by storage connectors to persist state, configuration, and logs to disk without risking partial writes on crash.

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `_serialize` | `(data, format)` | Serialize a data structure to bytes in the given format. |
| `_deserialize` | `(raw, format)` | Deserialize bytes back into a data structure. |
| `_atomic_write` | `(path, data)` | Write bytes to a file atomically via temp-file-and-rename. |
| `_read_file` | `(path)` | Read the entire contents of a file as bytes. |

### Behavior

- Default format is JSON. YAML and msgpack are supported when the corresponding library is installed.
- `_atomic_write` writes to a temporary file in the same directory, then renames it over the target path. This guarantees the file is never left in a partial state.
- `_read_file` returns raw bytes; callers pass them to `_deserialize`.

### Python

```python
import json
import os
import tempfile
from enum import Enum
from typing import Any


class SerializationFormat(Enum):
    """Serialization format for stored data."""
    JSON = "json"
    YAML = "yaml"
    MSGPACK = "msgpack"


class FileSerializerMixin:
    """JSON/YAML/msgpack serialization with atomic file writes.

    Provides a uniform interface for serializing data structures to
    bytes and writing them to disk safely. Atomic writes use a
    temporary file in the same directory followed by an os.replace
    to prevent partial-write corruption.
    """

    def _serialize(
        self, data: Any, format: SerializationFormat = SerializationFormat.JSON
    ) -> bytes:
        """Serialize a data structure to bytes.

        Args:
            data: The data structure to serialize.
            format: Target serialization format.

        Returns:
            Serialized bytes.

        Raises:
            ValueError: If the format is not supported or the required
                library is not installed.
        """
        if format == SerializationFormat.JSON:
            return json.dumps(data, indent=2, default=str).encode("utf-8")
        elif format == SerializationFormat.YAML:
            try:
                import yaml
            except ImportError:
                raise ValueError("PyYAML is required for YAML serialization")
            return yaml.safe_dump(data, default_flow_style=False).encode("utf-8")
        elif format == SerializationFormat.MSGPACK:
            try:
                import msgpack
            except ImportError:
                raise ValueError("msgpack is required for msgpack serialization")
            return msgpack.packb(data, use_bin_type=True)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _deserialize(
        self, raw: bytes, format: SerializationFormat = SerializationFormat.JSON
    ) -> Any:
        """Deserialize bytes back into a data structure.

        Args:
            raw: Raw bytes to deserialize.
            format: Source serialization format.

        Returns:
            The deserialized data structure.

        Raises:
            ValueError: If the format is not supported or the required
                library is not installed.
        """
        if format == SerializationFormat.JSON:
            return json.loads(raw.decode("utf-8"))
        elif format == SerializationFormat.YAML:
            try:
                import yaml
            except ImportError:
                raise ValueError("PyYAML is required for YAML deserialization")
            return yaml.safe_load(raw.decode("utf-8"))
        elif format == SerializationFormat.MSGPACK:
            try:
                import msgpack
            except ImportError:
                raise ValueError("msgpack is required for msgpack deserialization")
            return msgpack.unpackb(raw, raw=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _atomic_write(self, path: str, data: bytes) -> None:
        """Write bytes to a file atomically.

        Writes to a temporary file in the same directory as the target,
        then renames it into place. This guarantees the target file is
        never left in a partial state.

        Args:
            path: Destination file path.
            data: Bytes to write.
        """
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            os.write(fd, data)
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp_path, path)
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _read_file(self, path: str) -> bytes:
        """Read the entire contents of a file.

        Args:
            path: File path to read.

        Returns:
            Raw file contents as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        with open(path, "rb") as f:
            return f.read()
```

### TypeScript

```typescript
import { readFileSync, writeFileSync, mkdirSync, renameSync, unlinkSync } from "fs";
import { dirname, join } from "path";
import { randomBytes } from "crypto";

/** Serialization format for stored data. */
enum SerializationFormat {
    JSON = "json",
    YAML = "yaml",
    MSGPACK = "msgpack",
}

/**
 * JSON/YAML/msgpack serialization with atomic file writes.
 *
 * Provides a uniform interface for serializing data structures to
 * byte buffers and writing them to disk safely. Atomic writes use
 * a temporary file in the same directory followed by a rename.
 */
class FileSerializer {
    /**
     * Serialize a data structure to a byte buffer.
     *
     * @param data - The data structure to serialize.
     * @param format - Target serialization format (default: JSON).
     * @returns Serialized data as a Uint8Array.
     * @throws Error if the format is not supported.
     */
    serialize(
        data: unknown,
        format: SerializationFormat = SerializationFormat.JSON,
    ): Uint8Array {
        switch (format) {
            case SerializationFormat.JSON: {
                const json = JSON.stringify(data, null, 2);
                return new TextEncoder().encode(json);
            }
            case SerializationFormat.YAML:
                throw new Error(
                    "YAML serialization requires a YAML library (e.g. js-yaml)",
                );
            case SerializationFormat.MSGPACK:
                throw new Error(
                    "msgpack serialization requires a msgpack library (e.g. @msgpack/msgpack)",
                );
            default:
                throw new Error(`Unsupported format: ${format}`);
        }
    }

    /**
     * Deserialize a byte buffer back into a data structure.
     *
     * @param raw - Raw bytes to deserialize.
     * @param format - Source serialization format (default: JSON).
     * @returns The deserialized data structure.
     * @throws Error if the format is not supported.
     */
    deserialize<T = unknown>(
        raw: Uint8Array,
        format: SerializationFormat = SerializationFormat.JSON,
    ): T {
        switch (format) {
            case SerializationFormat.JSON: {
                const text = new TextDecoder().decode(raw);
                return JSON.parse(text) as T;
            }
            case SerializationFormat.YAML:
                throw new Error(
                    "YAML deserialization requires a YAML library (e.g. js-yaml)",
                );
            case SerializationFormat.MSGPACK:
                throw new Error(
                    "msgpack deserialization requires a msgpack library (e.g. @msgpack/msgpack)",
                );
            default:
                throw new Error(`Unsupported format: ${format}`);
        }
    }

    /**
     * Write bytes to a file atomically via temp-file-and-rename.
     *
     * @param filePath - Destination file path.
     * @param data - Bytes to write.
     */
    atomicWrite(filePath: string, data: Uint8Array): void {
        const dir = dirname(filePath);
        mkdirSync(dir, { recursive: true });

        const tmpName = join(dir, `.tmp-${randomBytes(8).toString("hex")}`);
        try {
            writeFileSync(tmpName, data);
            renameSync(tmpName, filePath);
        } catch (error) {
            try {
                unlinkSync(tmpName);
            } catch {
                // Ignore cleanup errors
            }
            throw error;
        }
    }

    /**
     * Read the entire contents of a file.
     *
     * @param filePath - File path to read.
     * @returns Raw file contents as a Uint8Array.
     */
    readFile(filePath: string): Uint8Array {
        return readFileSync(filePath);
    }
}
```

---

## RollingWindowMixin

Rolling window metrics collection with EWMA scoring. Tracks per-key success rates, averages, and composite scores that feed into selection strategies and deactivation policies.

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `_init_window` | `(window_size, window_duration_seconds)` | Initialize window parameters: max samples per key and the duration after which samples expire. |
| `_record_sample` | `(key, value, success)` | Record a single observation for a key. |
| `_get_rate` | `(key)` | Return the success rate (0.0--1.0) for the key over the current window. |
| `_get_average` | `(key)` | Return the arithmetic mean of values for the key over the current window. |
| `_get_score` | `(key)` | Return an EWMA-weighted composite score combining success rate and average value. |

### Behavior

- Each key maintains a deque of `(timestamp, value, success)` tuples.
- Samples older than `window_duration_seconds` are pruned on every read.
- When the deque exceeds `window_size`, the oldest samples are dropped.
- `_get_score` applies Exponential Weighted Moving Average (alpha = 0.3) over the values, scaled by the success rate.

### Python

```python
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class Sample:
    """A single observation recorded in the rolling window."""
    timestamp: float
    value: float
    success: bool


class RollingWindowMixin:
    """Rolling window metrics with EWMA scoring.

    Tracks per-key success rates, value averages, and composite scores.
    Expired samples are pruned lazily on each read operation.
    """

    _window_data: dict[str, deque[Sample]]
    _window_size: int = 100
    _window_duration: float = 300.0
    _ewma_alpha: float = 0.3

    def _init_window(
        self,
        window_size: int = 100,
        window_duration_seconds: float = 300.0,
    ) -> None:
        """Initialize rolling window parameters.

        Args:
            window_size: Maximum number of samples retained per key.
            window_duration_seconds: Samples older than this many seconds
                are pruned on read.
        """
        self._window_data = {}
        self._window_size = window_size
        self._window_duration = window_duration_seconds

    def _record_sample(
        self, key: str, value: float, success: bool = True
    ) -> None:
        """Record a single observation for a key.

        Args:
            key: Metric key (e.g. model ID or provider ID).
            value: Observed value (e.g. latency in ms).
            success: Whether the observation represents a success.
        """
        if key not in self._window_data:
            self._window_data[key] = deque(maxlen=self._window_size)

        sample = Sample(
            timestamp=time.monotonic(),
            value=value,
            success=success,
        )
        self._window_data[key].append(sample)

    def _get_rate(self, key: str) -> float:
        """Return the success rate for a key over the current window.

        Args:
            key: Metric key.

        Returns:
            Success rate between 0.0 and 1.0.  Returns 1.0 if no
            samples are present.
        """
        samples = self._prune_and_get(key)
        if not samples:
            return 1.0
        successes = sum(1 for s in samples if s.success)
        return successes / len(samples)

    def _get_average(self, key: str) -> float:
        """Return the arithmetic mean of values over the current window.

        Args:
            key: Metric key.

        Returns:
            Mean value, or 0.0 if no samples are present.
        """
        samples = self._prune_and_get(key)
        if not samples:
            return 0.0
        return sum(s.value for s in samples) / len(samples)

    def _get_score(self, key: str) -> float:
        """Return an EWMA-weighted composite score for a key.

        The score combines the success rate with an exponentially
        weighted moving average of the recorded values. Higher scores
        indicate better performance.

        Args:
            key: Metric key.

        Returns:
            Composite score. Returns 0.0 if no samples are present.
        """
        samples = self._prune_and_get(key)
        if not samples:
            return 0.0

        # Compute EWMA over values
        ewma = samples[0].value
        for sample in samples[1:]:
            ewma = self._ewma_alpha * sample.value + (1 - self._ewma_alpha) * ewma

        success_rate = self._get_rate(key)
        return ewma * success_rate

    def _prune_and_get(self, key: str) -> list[Sample]:
        """Prune expired samples and return the remaining list.

        Args:
            key: Metric key.

        Returns:
            List of non-expired samples for the key.
        """
        window = self._window_data.get(key)
        if window is None:
            return []

        cutoff = time.monotonic() - self._window_duration
        while window and window[0].timestamp < cutoff:
            window.popleft()

        return list(window)
```

### TypeScript

```typescript
/** A single observation recorded in the rolling window. */
interface Sample {
    timestamp: number;
    value: number;
    success: boolean;
}

/**
 * Rolling window metrics with EWMA scoring.
 *
 * Tracks per-key success rates, value averages, and composite scores.
 * Expired samples are pruned lazily on each read operation.
 */
class RollingWindow {
    private data = new Map<string, Sample[]>();
    private windowSize: number;
    private windowDuration: number;
    private ewmaAlpha: number;

    /**
     * Create a new RollingWindow instance.
     *
     * @param windowSize - Maximum number of samples retained per key.
     * @param windowDurationSeconds - Samples older than this many seconds
     *     are pruned on read.
     * @param ewmaAlpha - EWMA smoothing factor (default: 0.3).
     */
    constructor(
        windowSize: number = 100,
        windowDurationSeconds: number = 300,
        ewmaAlpha: number = 0.3,
    ) {
        this.windowSize = windowSize;
        this.windowDuration = windowDurationSeconds * 1000; // store as ms
        this.ewmaAlpha = ewmaAlpha;
    }

    /**
     * Record a single observation for a key.
     *
     * @param key - Metric key (e.g. model ID or provider ID).
     * @param value - Observed value (e.g. latency in ms).
     * @param success - Whether the observation represents a success.
     */
    recordSample(key: string, value: number, success: boolean = true): void {
        if (!this.data.has(key)) {
            this.data.set(key, []);
        }

        const samples = this.data.get(key)!;
        samples.push({ timestamp: performance.now(), value, success });

        // Enforce max window size
        while (samples.length > this.windowSize) {
            samples.shift();
        }
    }

    /**
     * Return the success rate for a key over the current window.
     *
     * @param key - Metric key.
     * @returns Success rate between 0.0 and 1.0. Returns 1.0 if no samples.
     */
    getRate(key: string): number {
        const samples = this.pruneAndGet(key);
        if (samples.length === 0) return 1.0;
        const successes = samples.filter((s) => s.success).length;
        return successes / samples.length;
    }

    /**
     * Return the arithmetic mean of values over the current window.
     *
     * @param key - Metric key.
     * @returns Mean value, or 0.0 if no samples.
     */
    getAverage(key: string): number {
        const samples = this.pruneAndGet(key);
        if (samples.length === 0) return 0.0;
        const sum = samples.reduce((acc, s) => acc + s.value, 0);
        return sum / samples.length;
    }

    /**
     * Return an EWMA-weighted composite score for a key.
     * Higher scores indicate better performance.
     *
     * @param key - Metric key.
     * @returns Composite score, or 0.0 if no samples.
     */
    getScore(key: string): number {
        const samples = this.pruneAndGet(key);
        if (samples.length === 0) return 0.0;

        let ewma = samples[0].value;
        for (let i = 1; i < samples.length; i++) {
            ewma = this.ewmaAlpha * samples[i].value + (1 - this.ewmaAlpha) * ewma;
        }

        const successRate = this.getRate(key);
        return ewma * successRate;
    }

    private pruneAndGet(key: string): Sample[] {
        const samples = this.data.get(key);
        if (!samples) return [];

        const cutoff = performance.now() - this.windowDuration;
        while (samples.length > 0 && samples[0].timestamp < cutoff) {
            samples.shift();
        }

        return samples;
    }
}
```

---

## ConfigValidatorMixin

Configuration validation with type checking, required-field enforcement, URL validation, and duration parsing. Applied during connector initialization to surface configuration errors early and produce clear diagnostic messages.

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `_validate_config` | `(config, schema)` | Validate an entire config dict against a schema. Returns a list of error messages (empty = valid). |
| `_require_field` | `(config, field, field_type)` | Assert that a field exists in the config and has the expected type. Raises on failure. |
| `_validate_url` | `(url)` | Return `True` if the string is a valid HTTP or HTTPS URL. |
| `_validate_duration` | `(value)` | Parse a duration string ("30s", "5m", "1h") to seconds as a float. Raises on invalid input. |

### Behavior

- Schema is a dict mapping field names to `{"type": ..., "required": bool}` entries.
- `_validate_config` walks the schema, checks presence of required fields, and validates types.
- `_validate_duration` supports `s` (seconds), `m` (minutes), `h` (hours), and `d` (days).
- Validation errors are collected as a list rather than raising on the first error, so the caller sees all problems at once.

### Python

```python
import re
from typing import Any
from urllib.parse import urlparse


class ConfigValidatorMixin:
    """Configuration validation with type checking and duration parsing.

    Validates config dicts against schemas, enforces required fields,
    parses duration strings, and validates URLs. Errors are collected
    as a list so all problems surface at once.
    """

    DURATION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(s|m|h|d)$")
    DURATION_MULTIPLIERS = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}

    def _validate_config(
        self, config: dict[str, Any], schema: dict[str, dict]
    ) -> list[str]:
        """Validate a config dict against a schema.

        The schema maps field names to descriptors::

            {
                "base_url": {"type": str, "required": True},
                "timeout":  {"type": str, "required": False},
            }

        Args:
            config: Configuration dictionary to validate.
            schema: Schema describing expected fields, types, and
                whether each field is required.

        Returns:
            A list of human-readable error messages. An empty list
            means the configuration is valid.
        """
        errors: list[str] = []

        for field, descriptor in schema.items():
            required = descriptor.get("required", False)
            expected_type = descriptor.get("type")

            if field not in config:
                if required:
                    errors.append(f"Missing required field: '{field}'")
                continue

            value = config[field]
            if expected_type is not None and not isinstance(value, expected_type):
                errors.append(
                    f"Field '{field}' expected type {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        return errors

    def _require_field(
        self, config: dict[str, Any], field: str, field_type: type
    ) -> Any:
        """Assert that a field exists and has the expected type.

        Args:
            config: Configuration dictionary.
            field: Field name to check.
            field_type: Expected Python type.

        Returns:
            The field value if valid.

        Raises:
            KeyError: If the field is missing.
            TypeError: If the field has the wrong type.
        """
        if field not in config:
            raise KeyError(f"Missing required field: '{field}'")

        value = config[field]
        if not isinstance(value, field_type):
            raise TypeError(
                f"Field '{field}' expected type {field_type.__name__}, "
                f"got {type(value).__name__}"
            )
        return value

    def _validate_url(self, url: str) -> bool:
        """Check whether a string is a valid HTTP or HTTPS URL.

        Args:
            url: URL string to validate.

        Returns:
            True if the URL has a valid scheme (http/https) and netloc.
        """
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def _validate_duration(self, value: str) -> float:
        """Parse a duration string to seconds.

        Supported suffixes: ``s`` (seconds), ``m`` (minutes),
        ``h`` (hours), ``d`` (days).

        Args:
            value: Duration string (e.g. "30s", "5m", "1h", "7d").

        Returns:
            Duration in seconds as a float.

        Raises:
            ValueError: If the string does not match the expected format.
        """
        match = self.DURATION_PATTERN.match(value.strip())
        if not match:
            raise ValueError(
                f"Invalid duration '{value}'. "
                f"Expected format: <number><s|m|h|d> (e.g. '30s', '5m', '1h')"
            )

        amount = float(match.group(1))
        unit = match.group(2)
        return amount * self.DURATION_MULTIPLIERS[unit]
```

### TypeScript

```typescript
/** Schema descriptor for a single config field. */
interface FieldSchema {
    type: "string" | "number" | "boolean" | "object" | "array";
    required: boolean;
}

/**
 * Configuration validation with type checking and duration parsing.
 *
 * Validates config objects against schemas, enforces required fields,
 * parses duration strings, and validates URLs. Errors are collected
 * as a list so all problems surface at once.
 */
class ConfigValidator {
    private static readonly DURATION_PATTERN = /^(\d+(?:\.\d+)?)\s*(s|m|h|d)$/;

    private static readonly DURATION_MULTIPLIERS: Record<string, number> = {
        s: 1,
        m: 60,
        h: 3600,
        d: 86400,
    };

    /**
     * Validate a config object against a schema.
     *
     * @param config - Configuration object to validate.
     * @param schema - Schema mapping field names to type/required descriptors.
     * @returns Array of error messages. Empty array means valid.
     */
    validateConfig(
        config: Record<string, unknown>,
        schema: Record<string, FieldSchema>,
    ): string[] {
        const errors: string[] = [];

        for (const [field, descriptor] of Object.entries(schema)) {
            const value = config[field];

            if (value === undefined) {
                if (descriptor.required) {
                    errors.push(`Missing required field: '${field}'`);
                }
                continue;
            }

            const actualType = Array.isArray(value) ? "array" : typeof value;
            if (actualType !== descriptor.type) {
                errors.push(
                    `Field '${field}' expected type ${descriptor.type}, got ${actualType}`,
                );
            }
        }

        return errors;
    }

    /**
     * Assert that a field exists and has the expected type.
     *
     * @param config - Configuration object.
     * @param field - Field name to check.
     * @param fieldType - Expected type string.
     * @returns The field value if valid.
     * @throws Error if the field is missing or has the wrong type.
     */
    requireField<T>(
        config: Record<string, unknown>,
        field: string,
        fieldType: "string" | "number" | "boolean" | "object" | "array",
    ): T {
        const value = config[field];

        if (value === undefined) {
            throw new Error(`Missing required field: '${field}'`);
        }

        const actualType = Array.isArray(value) ? "array" : typeof value;
        if (actualType !== fieldType) {
            throw new TypeError(
                `Field '${field}' expected type ${fieldType}, got ${actualType}`,
            );
        }

        return value as T;
    }

    /**
     * Check whether a string is a valid HTTP or HTTPS URL.
     *
     * @param url - URL string to validate.
     * @returns True if the URL has a valid http/https scheme.
     */
    validateUrl(url: string): boolean {
        try {
            const parsed = new URL(url);
            return parsed.protocol === "http:" || parsed.protocol === "https:";
        } catch {
            return false;
        }
    }

    /**
     * Parse a duration string to seconds.
     * Supported suffixes: s (seconds), m (minutes), h (hours), d (days).
     *
     * @param value - Duration string (e.g. "30s", "5m", "1h", "7d").
     * @returns Duration in seconds.
     * @throws Error if the string does not match the expected format.
     */
    validateDuration(value: string): number {
        const match = value.trim().match(ConfigValidator.DURATION_PATTERN);
        if (!match) {
            throw new Error(
                `Invalid duration '${value}'. ` +
                `Expected format: <number><s|m|h|d> (e.g. '30s', '5m', '1h')`,
            );
        }

        const amount = parseFloat(match[1]);
        const unit = match[2];
        return amount * ConfigValidator.DURATION_MULTIPLIERS[unit];
    }
}
```

---

## Using Multiple Mixins Together

Connectors frequently combine several mixins. The following example builds a custom provider connector that uses `HttpClientMixin` for API communication and `CacheMixin` for caching model catalogue responses.

### Python (Multiple Inheritance)

```python
from typing import AsyncIterator


class CachedHttpProvider(
    HttpClientMixin,
    CacheMixin,
    # ProviderConnector would be here in a real implementation
):
    """Example provider that caches model listings using multiple mixins.

    Demonstrates the Python mixin pattern: the class inherits from
    both HttpClientMixin and CacheMixin alongside the base connector
    interface. Each mixin initializes independently via its own
    _init method.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._http_auth_token = api_key
        self._init_http_client(
            base_url=base_url,
            timeout=30.0,
            max_retries=3,
        )
        self._init_cache(
            ttl_ms=300_000,  # 5 minutes
            max_entries=256,
        )

    async def list_models(self) -> list[dict]:
        """List models, returning cached results when available.

        On cache miss, fetches from the provider API and caches the
        result for subsequent calls within the TTL window.

        Returns:
            List of model descriptors.
        """
        cached = self._cache_get("models")
        if cached is not None:
            return cached

        models = await self._http_get("/models")
        self._cache_set("models", models)
        return models

    async def complete(self, request: dict) -> dict:
        """Send a completion request to the provider.

        Args:
            request: Normalized completion request body.

        Returns:
            Provider response parsed as a dict.
        """
        return await self._http_post("/chat/completions", json=request)

    async def stream(self, request: dict) -> AsyncIterator[str]:
        """Stream a completion request, yielding data chunks.

        Args:
            request: Normalized completion request body with stream=True.

        Yields:
            Individual SSE data lines from the provider.
        """
        request["stream"] = True
        async for chunk in self._http_stream("/chat/completions", json=request):
            yield chunk

    async def close(self) -> None:
        """Release HTTP client and clear the cache."""
        await self._close_http_client()
        self._cache_clear()
```

### TypeScript (Composition)

```typescript
/**
 * Example provider that caches model listings using composition.
 *
 * Demonstrates the TypeScript composition pattern: the class creates
 * helper objects (HttpClient and Cache) in its constructor and
 * delegates to them explicitly. This avoids the diamond-inheritance
 * problem and keeps dependencies visible.
 */
class CachedHttpProvider {
    private http: HttpClient;
    private cache: Cache;

    /**
     * Create a new CachedHttpProvider.
     *
     * @param baseUrl - Provider API base URL.
     * @param apiKey - Bearer token for authorization.
     */
    constructor(baseUrl: string, apiKey: string) {
        this.http = new HttpClient();
        this.http.init(baseUrl, 30_000, 3);
        this.http.setAuthToken(apiKey);

        this.cache = new Cache(300_000, 256); // 5 min TTL, 256 entries
    }

    /**
     * List models, returning cached results when available.
     *
     * @returns Array of model descriptors.
     */
    async listModels(): Promise<unknown[]> {
        const cached = this.cache.get("models");
        if (cached !== null) {
            return cached as unknown[];
        }

        const models = await this.http.get<unknown[]>("/models");
        this.cache.set("models", models);
        return models;
    }

    /**
     * Send a completion request to the provider.
     *
     * @param request - Normalized completion request body.
     * @returns Provider response.
     */
    async complete(request: Record<string, unknown>): Promise<unknown> {
        return this.http.post("/chat/completions", request);
    }

    /**
     * Stream a completion request, yielding data chunks.
     *
     * @param request - Normalized completion request body.
     * @yields Individual SSE data lines from the provider.
     */
    async *stream(
        request: Record<string, unknown>,
    ): AsyncGenerator<string> {
        yield* this.http.stream("/chat/completions", {
            ...request,
            stream: true,
        });
    }

    /** Release HTTP client and clear the cache. */
    close(): void {
        this.http.close();
        this.cache.clear();
    }
}
```

---

## CircuitBreakerMixin

Implements the circuit breaker pattern to prevent cascading failures when a provider becomes unhealthy. When a provider's error count exceeds the failure threshold, the circuit opens and requests fail fast without calling the provider. After a reset timeout, a single probe request is allowed; if it succeeds, the circuit closes.

### States

| State | Description |
| --- | --- |
| `CLOSED` | Normal operation. Requests pass through. |
| `OPEN` | Provider is unhealthy. Requests fail fast with `CircuitOpenError`. |
| `HALF_OPEN` | Probe mode. A limited number of requests pass through to test recovery. |

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `configure_circuit_breaker` | `(failure_threshold, reset_timeout, half_open_max, success_threshold)` | Set circuit breaker parameters. |
| `check_circuit` | `()` | Verify the circuit allows a request. Raises `CircuitOpenError` if open. |
| `record_success` | `()` | Record a successful request. Closes circuit in half-open state. |
| `record_failure` | `()` | Record a failed request. Opens circuit when threshold is reached. |
| `reset_circuit` | `()` | Manually reset the circuit to CLOSED. |
| `circuit_breaker_stats` | `()` | Return current state, failure count, and config. |

### Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `failure_threshold` | `int` | `5` | Consecutive failures to trip the circuit. |
| `reset_timeout` | `float` | `60.0` | Seconds before OPEN transitions to HALF_OPEN. |
| `half_open_max` | `int` | `1` | Max probe requests in HALF_OPEN state. |
| `success_threshold` | `int` | `1` | Successes in HALF_OPEN needed to close. |

---

## TimeoutMixin

Enforces per-request timeouts by wrapping async operations with `asyncio.wait_for`. Raises `RequestTimeoutError` when exceeded.

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `configure_timeout` | `(default, streaming, streaming_total, connect)` | Set timeout values in seconds. |
| `with_timeout` | `(coro, timeout?, operation?)` | Execute a coroutine with a timeout. |
| `with_stream_timeout` | `(aiter, first_chunk_timeout?, total_timeout?)` | Wrap a streaming async iterator with timeouts. |

### Configuration

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `default` | `float` | `30.0` | Non-streaming request timeout. |
| `streaming` | `float` | `60.0` | First-chunk timeout for streams. |
| `streaming_total` | `float` | `300.0` | Total stream duration timeout. |
| `connect` | `float` | `10.0` | Connection establishment timeout. |

---

## StreamingCheckpointMixin

Tracks streaming response progress so that interrupted streams can be detected and potentially resumed. Buffers content and token counts per active stream.

### Methods

| Method | Signature | Description |
| --- | --- | --- |
| `configure_checkpoints` | `(max_buffer_tokens, checkpoint_interval, max_checkpoints)` | Set checkpoint parameters. |
| `create_checkpoint` | `(request_id, model_id?)` | Create and register a new stream checkpoint. |
| `get_checkpoint` | `(request_id)` | Retrieve a checkpoint by request ID. |
| `remove_checkpoint` | `(request_id)` | Remove a completed checkpoint. |
| `active_checkpoints` | `()` | Return all incomplete checkpoints. |
| `checkpoint_stats` | `()` | Return summary statistics. |

### StreamCheckpoint

| Field | Type | Description |
| --- | --- | --- |
| `request_id` | `str` | Unique request identifier. |
| `model_id` | `str` | Model generating the stream. |
| `tokens_received` | `int` | Total tokens received. |
| `content_buffer` | `str` | Accumulated text. |
| `is_complete` | `bool` | Whether the stream finished normally. |
| `duration` | `float` | Elapsed time in seconds (property). |
| `tokens_per_second` | `float` | Throughput metric (property). |
