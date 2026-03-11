/**
 * TTL-based in-memory cache with LRU eviction.
 *
 * Provides a `CacheMixin` that can be composed into any class.
 * The mixin stores values alongside monotonic timestamps and evicts
 * expired entries lazily on read. When the maximum entry count is
 * reached, the least-recently-accessed entry is evicted to make room.
 *
 * Usage:
 *
 *   class MyService extends CacheMixin<MyValue> {
 *     constructor() {
 *       super({ maxSize: 256, ttlMs: 60_000 });
 *     }
 *
 *     getData(key: string): MyValue {
 *       const cached = this.cacheGet(key);
 *       if (cached !== undefined) return cached;
 *       const value = this.fetchData(key);
 *       this.cacheSet(key, value);
 *       return value;
 *     }
 *   }
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/** Configuration for the cache mixin. */
export interface CacheConfig {
  /** Maximum number of entries before LRU eviction kicks in. */
  readonly maxSize: number;
  /** Time-to-live for each entry in milliseconds. */
  readonly ttlMs: number;
  /** Whether the cache is enabled. When `false`, all operations are no-ops. */
  readonly enabled: boolean;
}

// ---------------------------------------------------------------------------
// Internal entry type
// ---------------------------------------------------------------------------

/** Internal cache entry with timestamps for TTL and LRU tracking. */
interface CacheEntry<T> {
  /** Monotonic timestamp when the entry was created. */
  createdAt: number;
  /** Monotonic timestamp when the entry was last accessed. */
  accessedAt: number;
  /** The cached value. */
  value: T;
}

// ---------------------------------------------------------------------------
// Mixin
// ---------------------------------------------------------------------------

/**
 * TTL-based in-memory cache with LRU eviction.
 *
 * Entries are stored in a `Map` mapping keys to `CacheEntry` objects.
 * A `cacheGet` checks the TTL and returns `undefined` for expired
 * entries (lazy expiration). When `cacheSet` is called and the store
 * is at capacity for a new key, the least-recently-accessed entry is
 * evicted.
 *
 * Performance counters (hits, misses, evictions) are tracked and can
 * be retrieved via `cacheStats()`. Counters are reset when
 * `cacheClear()` is called.
 *
 * @typeParam T - The type of cached values.
 */
export class CacheMixin<T = unknown> {
  private readonly _cacheConfig: CacheConfig;
  private _store: Map<string, CacheEntry<T>> = new Map();
  private _hits: number = 0;
  private _misses: number = 0;
  private _evictions: number = 0;

  constructor(config?: Partial<CacheConfig>) {
    this._cacheConfig = {
      maxSize: config?.maxSize ?? 1024,
      ttlMs: config?.ttlMs ?? 60_000,
      enabled: config?.enabled ?? true,
    };
  }

  /**
   * Retrieve a cached value by key.
   *
   * Returns `undefined` if the key is not found or the entry has
   * expired. Expired entries are removed lazily on access. On a
   * cache hit the entry's last-accessed timestamp is updated for
   * LRU tracking.
   *
   * @param key - Cache key.
   * @returns The cached value, or `undefined` if missing or expired.
   */
  cacheGet(key: string): T | undefined {
    if (!this._cacheConfig.enabled) {
      this._misses += 1;
      return undefined;
    }

    const entry = this._store.get(key);
    if (entry === undefined) {
      this._misses += 1;
      return undefined;
    }

    const now = Date.now();
    const elapsed = now - entry.createdAt;

    if (elapsed > this._cacheConfig.ttlMs) {
      this._store.delete(key);
      this._misses += 1;
      return undefined;
    }

    // Update access time for LRU tracking.
    entry.accessedAt = now;
    this._hits += 1;
    return entry.value;
  }

  /**
   * Store a value under the given key.
   *
   * If the cache is at maximum capacity and the key is new, the
   * least-recently-accessed entry is evicted first.
   *
   * @param key - Cache key.
   * @param value - Value to store.
   */
  cacheSet(key: string, value: T): void {
    if (!this._cacheConfig.enabled) return;

    const now = Date.now();

    if (!this._store.has(key) && this._store.size >= this._cacheConfig.maxSize) {
      // Evict the least-recently-accessed entry.
      let lruKey: string | undefined;
      let lruTime = Infinity;
      for (const [k, entry] of this._store) {
        if (entry.accessedAt < lruTime) {
          lruTime = entry.accessedAt;
          lruKey = k;
        }
      }
      if (lruKey !== undefined) {
        this._store.delete(lruKey);
        this._evictions += 1;
      }
    }

    this._store.set(key, {
      createdAt: now,
      accessedAt: now,
      value,
    });
  }

  /**
   * Check whether a key exists in the cache and has not expired.
   *
   * This does not update the access timestamp -- use `cacheGet` for
   * that.
   *
   * @param key - Cache key.
   * @returns `true` if the key is present and not expired.
   */
  cacheHas(key: string): boolean {
    if (!this._cacheConfig.enabled) return false;

    const entry = this._store.get(key);
    if (entry === undefined) return false;

    const elapsed = Date.now() - entry.createdAt;
    if (elapsed > this._cacheConfig.ttlMs) {
      this._store.delete(key);
      return false;
    }

    return true;
  }

  /**
   * Remove a single key from the cache.
   *
   * This is a no-op if the key does not exist.
   *
   * @param key - Cache key to remove.
   */
  cacheInvalidate(key: string): void {
    this._store.delete(key);
  }

  /** Remove all entries and reset stats counters. */
  cacheClear(): void {
    this._store.clear();
    this._hits = 0;
    this._misses = 0;
    this._evictions = 0;
  }

  /**
   * Return current cache performance counters.
   *
   * @returns An object with `hits`, `misses`, `evictions`, and
   *   current `size`.
   */
  cacheStats(): { hits: number; misses: number; evictions: number; size: number } {
    return {
      hits: this._hits,
      misses: this._misses,
      evictions: this._evictions,
      size: this._store.size,
    };
  }
}
