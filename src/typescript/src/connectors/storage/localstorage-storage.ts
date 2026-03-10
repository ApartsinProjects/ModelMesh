/**
 * Browser localStorage storage connector.
 *
 * Provides persistent key-value storage backed by the browser's
 * localStorage API. Data survives page reloads and browser restarts
 * but is limited to approximately 5–10 MB per origin.
 *
 * Connector ID: modelmesh.localstorage.v1
 *
 * Data is stored as base64-encoded JSON strings.  All keys are
 * prefixed with a configurable namespace (default: "modelmesh:").
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { EntryMetadata, StorageConnector, StorageEntry } from '../../interfaces/storage';

export interface LocalStorageStorageConfig {
  /** Key prefix for namespace isolation.  Defaults to "modelmesh:". */
  prefix?: string;
}

export class LocalStorageStorage implements StorageConnector {
  static readonly CONNECTOR_ID = 'modelmesh.localstorage.v1';
  static readonly RUNTIME = RuntimeEnvironment.BROWSER_ONLY;

  private readonly _prefix: string;

  constructor(config?: LocalStorageStorageConfig) {
    this._prefix = config?.prefix ?? 'modelmesh:';
  }

  private _key(key: string): string {
    return this._prefix + key;
  }

  // -- Persistence ----------------------------------------------------------

  async load(key: string): Promise<StorageEntry | null> {
    const raw = localStorage.getItem(this._key(key));
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    const bytes = Uint8Array.from(atob(parsed.data), (c) => c.charCodeAt(0));
    return {
      key: parsed.key,
      data: bytes as any, // Uint8Array is Buffer-compatible
      metadata: parsed.metadata,
    };
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    const bytes =
      entry.data instanceof Uint8Array
        ? entry.data
        : new Uint8Array(entry.data);
    const b64 = btoa(String.fromCharCode(...bytes));
    const stored = {
      key,
      data: b64,
      metadata: entry.metadata,
      lastModified: new Date().toISOString(),
    };
    localStorage.setItem(this._key(key), JSON.stringify(stored));
  }

  // -- Inventory ------------------------------------------------------------

  async list(prefix?: string): Promise<string[]> {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const fullKey = localStorage.key(i);
      if (fullKey && fullKey.startsWith(this._prefix)) {
        const shortKey = fullKey.substring(this._prefix.length);
        if (prefix === undefined || shortKey.startsWith(prefix)) {
          keys.push(shortKey);
        }
      }
    }
    return keys;
  }

  async delete(key: string): Promise<boolean> {
    const fullKey = this._key(key);
    if (localStorage.getItem(fullKey) !== null) {
      localStorage.removeItem(fullKey);
      return true;
    }
    return false;
  }

  // -- Stat Query -----------------------------------------------------------

  async stat(key: string): Promise<EntryMetadata | null> {
    const raw = localStorage.getItem(this._key(key));
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    const decoded = atob(parsed.data);
    return {
      key,
      size: decoded.length,
      lastModified: new Date(parsed.lastModified),
      contentType: 'application/octet-stream',
    };
  }

  async exists(key: string): Promise<boolean> {
    return localStorage.getItem(this._key(key)) !== null;
  }
}
