/**
 * Base storage implementation for the CDK.
 *
 * Implements the full StorageConnector interface plus the optional
 * Locking interface using an in-memory Map backend. Subclasses
 * override persistence methods to write to files, databases, or
 * cloud storage.
 */

import { RuntimeEnvironment } from '../interfaces/runtime';
import {
  EntryMetadata,
  LockHandle,
  Locking,
  StorageConnector,
  StorageEntry,
} from '../interfaces/storage';

export interface BaseStorageConfig {
  format?: string;
  compression?: boolean;
  lockingEnabled?: boolean;
  lockTimeoutSeconds?: number;
}

export class BaseStorage implements StorageConnector, Locking {
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  protected readonly _config: Required<BaseStorageConfig>;
  protected _store = new Map<string, StorageEntry>();
  protected _timestamps = new Map<string, Date>();
  private _locks = new Map<string, LockHandle>();

  constructor(config?: BaseStorageConfig) {
    this._config = {
      format: config?.format ?? 'json',
      compression: config?.compression ?? false,
      lockingEnabled: config?.lockingEnabled ?? true,
      lockTimeoutSeconds: config?.lockTimeoutSeconds ?? 30.0,
    };
  }

  // -- Persistence -----------------------------------------------------------

  async load(key: string): Promise<StorageEntry | null> {
    return this._store.get(key) ?? null;
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    this._store.set(key, entry);
    this._timestamps.set(key, new Date());
  }

  // -- Inventory -------------------------------------------------------------

  async list(prefix?: string): Promise<string[]> {
    const keys = Array.from(this._store.keys());
    if (prefix == null) return keys;
    return keys.filter((k) => k.startsWith(prefix));
  }

  async delete(key: string): Promise<boolean> {
    if (this._store.has(key)) {
      this._store.delete(key);
      this._timestamps.delete(key);
      this._locks.delete(key);
      return true;
    }
    return false;
  }

  // -- Stat Query ------------------------------------------------------------

  async stat(key: string): Promise<EntryMetadata | null> {
    const entry = this._store.get(key);
    if (!entry) return null;
    return {
      key,
      size: entry.data.length,
      lastModified: this._timestamps.get(key) ?? new Date(),
      contentType: this._config.format,
    };
  }

  async exists(key: string): Promise<boolean> {
    return this._store.has(key);
  }

  // -- Locking ---------------------------------------------------------------

  async acquire(key: string, timeout?: number): Promise<LockHandle> {
    if (!this._config.lockingEnabled) {
      throw new Error('Locking is disabled in configuration');
    }

    const effectiveTimeout = timeout ?? this._config.lockTimeoutSeconds;
    const existing = this._locks.get(key);

    if (existing) {
      if (existing.expiresAt && new Date() > existing.expiresAt) {
        this._locks.delete(key);
      } else {
        const deadline = Date.now() + effectiveTimeout * 1000;
        while (this._locks.has(key) && Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, 100));
        }
        if (this._locks.has(key)) {
          throw new Error(
            `Could not acquire lock on '${key}' within ${effectiveTimeout}s`
          );
        }
      }
    }

    const now = new Date();
    const handle: LockHandle = {
      key,
      lockId: crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
      acquiredAt: now,
      expiresAt: new Date(now.getTime() + effectiveTimeout * 1000),
    };
    this._locks.set(key, handle);
    return handle;
  }

  async release(lock: LockHandle): Promise<void> {
    const current = this._locks.get(lock.key);
    if (current && current.lockId === lock.lockId) {
      this._locks.delete(lock.key);
    }
  }

  async isLocked(key: string): Promise<boolean> {
    const handle = this._locks.get(key);
    if (!handle) return false;
    if (handle.expiresAt && new Date() > handle.expiresAt) {
      this._locks.delete(key);
      return false;
    }
    return true;
  }
}
