/**
 * In-memory key-value storage connector.
 *
 * Provides an ephemeral Map-based storage backend. All data is lost
 * when the process exits. Useful for testing, serverless functions,
 * and short-lived processes.
 *
 * Connector ID: modelmesh.memory.v1
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { EntryMetadata, StorageConnector, StorageEntry } from '../../interfaces/storage';

export class MemoryStorage implements StorageConnector {
  static readonly CONNECTOR_ID = 'modelmesh.memory.v1';
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  private _store = new Map<string, StorageEntry>();
  private _timestamps = new Map<string, Date>();

  // -- Persistence ----------------------------------------------------------

  async load(key: string): Promise<StorageEntry | null> {
    return this._store.get(key) ?? null;
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    this._store.set(key, entry);
    this._timestamps.set(key, new Date());
  }

  // -- Inventory ------------------------------------------------------------

  async list(prefix?: string): Promise<string[]> {
    const keys = [...this._store.keys()];
    if (prefix === undefined) return keys;
    return keys.filter((k) => k.startsWith(prefix));
  }

  async delete(key: string): Promise<boolean> {
    if (this._store.has(key)) {
      this._store.delete(key);
      this._timestamps.delete(key);
      return true;
    }
    return false;
  }

  // -- Stat Query -----------------------------------------------------------

  async stat(key: string): Promise<EntryMetadata | null> {
    const entry = this._store.get(key);
    if (!entry) return null;
    return {
      key,
      size: entry.data.length,
      lastModified: this._timestamps.get(key) ?? new Date(),
      contentType: 'application/octet-stream',
    };
  }

  async exists(key: string): Promise<boolean> {
    return this._store.has(key);
  }
}
