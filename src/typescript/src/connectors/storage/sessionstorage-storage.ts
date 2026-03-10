/**
 * Browser sessionStorage storage connector.
 *
 * Provides per-tab storage backed by the browser's sessionStorage API.
 * Data is cleared when the tab or browser window is closed. Limited to
 * approximately 5–10 MB per origin.
 *
 * Connector ID: modelmesh.sessionstorage.v1
 *
 * Data is stored as base64-encoded JSON strings.  All keys are
 * prefixed with a configurable namespace (default: "modelmesh:").
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { EntryMetadata, StorageConnector, StorageEntry } from '../../interfaces/storage';

export interface SessionStorageStorageConfig {
  /** Key prefix for namespace isolation.  Defaults to "modelmesh:". */
  prefix?: string;
}

export class SessionStorageStorage implements StorageConnector {
  static readonly CONNECTOR_ID = 'modelmesh.sessionstorage.v1';
  static readonly RUNTIME = RuntimeEnvironment.BROWSER_ONLY;

  private readonly _prefix: string;

  constructor(config?: SessionStorageStorageConfig) {
    this._prefix = config?.prefix ?? 'modelmesh:';
  }

  private _key(key: string): string {
    return this._prefix + key;
  }

  // -- Persistence ----------------------------------------------------------

  async load(key: string): Promise<StorageEntry | null> {
    const raw = sessionStorage.getItem(this._key(key));
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    const bytes = Uint8Array.from(atob(parsed.data), (c) => c.charCodeAt(0));
    return {
      key: parsed.key,
      data: bytes as any,
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
    sessionStorage.setItem(this._key(key), JSON.stringify(stored));
  }

  // -- Inventory ------------------------------------------------------------

  async list(prefix?: string): Promise<string[]> {
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const fullKey = sessionStorage.key(i);
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
    if (sessionStorage.getItem(fullKey) !== null) {
      sessionStorage.removeItem(fullKey);
      return true;
    }
    return false;
  }

  // -- Stat Query -----------------------------------------------------------

  async stat(key: string): Promise<EntryMetadata | null> {
    const raw = sessionStorage.getItem(this._key(key));
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
    return sessionStorage.getItem(this._key(key)) !== null;
  }
}
