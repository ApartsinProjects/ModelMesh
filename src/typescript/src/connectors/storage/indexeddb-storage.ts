/**
 * Browser IndexedDB storage connector.
 *
 * Provides persistent storage backed by the browser's IndexedDB API.
 * Unlike localStorage, IndexedDB has no practical size limit and is
 * natively asynchronous — making it the preferred storage backend for
 * browser-based ModelMesh deployments.
 *
 * Connector ID: modelmesh.indexeddb.v1
 *
 * Binary data (Uint8Array) is stored directly without base64 encoding,
 * eliminating the ~33% overhead of localStorage-based connectors.
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { EntryMetadata, StorageConnector, StorageEntry } from '../../interfaces/storage';

export interface IndexedDBStorageConfig {
  /** Database name.  Defaults to "modelmesh". */
  dbName?: string;
  /** Object store name.  Defaults to "storage". */
  storeName?: string;
  /** Database schema version.  Defaults to 1. */
  version?: number;
}

interface StoredRecord {
  key: string;
  data: Uint8Array;
  metadata: Record<string, unknown>;
  lastModified: string;
}

export class IndexedDBStorage implements StorageConnector {
  static readonly CONNECTOR_ID = 'modelmesh.indexeddb.v1';
  static readonly RUNTIME = RuntimeEnvironment.BROWSER_ONLY;

  private readonly _dbName: string;
  private readonly _storeName: string;
  private readonly _version: number;
  private _db: IDBDatabase | null = null;

  constructor(config?: IndexedDBStorageConfig) {
    this._dbName = config?.dbName ?? 'modelmesh';
    this._storeName = config?.storeName ?? 'storage';
    this._version = config?.version ?? 1;
  }

  private async _getDb(): Promise<IDBDatabase> {
    if (this._db) return this._db;
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this._dbName, this._version);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(this._storeName)) {
          db.createObjectStore(this._storeName, { keyPath: 'key' });
        }
      };
      request.onsuccess = () => {
        this._db = request.result;
        resolve(this._db);
      };
      request.onerror = () => reject(request.error);
    });
  }

  private async _tx(mode: IDBTransactionMode): Promise<IDBObjectStore> {
    const db = await this._getDb();
    const tx = db.transaction(this._storeName, mode);
    return tx.objectStore(this._storeName);
  }

  // -- Persistence ----------------------------------------------------------

  async load(key: string): Promise<StorageEntry | null> {
    const store = await this._tx('readonly');
    return new Promise((resolve, reject) => {
      const request = store.get(key);
      request.onsuccess = () => {
        const record = request.result as StoredRecord | undefined;
        if (!record) {
          resolve(null);
          return;
        }
        resolve({
          key: record.key,
          data: record.data as any, // Uint8Array is Buffer-compatible
          metadata: record.metadata,
        });
      };
      request.onerror = () => reject(request.error);
    });
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    const store = await this._tx('readwrite');
    const bytes =
      entry.data instanceof Uint8Array
        ? entry.data
        : new Uint8Array(entry.data);
    return new Promise((resolve, reject) => {
      const request = store.put({
        key,
        data: bytes,
        metadata: entry.metadata,
        lastModified: new Date().toISOString(),
      } as StoredRecord);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  // -- Inventory ------------------------------------------------------------

  async list(prefix?: string): Promise<string[]> {
    const store = await this._tx('readonly');
    return new Promise((resolve, reject) => {
      const keys: string[] = [];
      const request = store.openCursor();
      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          const k = cursor.key as string;
          if (prefix === undefined || k.startsWith(prefix)) {
            keys.push(k);
          }
          cursor.continue();
        } else {
          resolve(keys);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }

  async delete(key: string): Promise<boolean> {
    const doesExist = await this.exists(key);
    if (!doesExist) return false;
    const store = await this._tx('readwrite');
    return new Promise((resolve, reject) => {
      const request = store.delete(key);
      request.onsuccess = () => resolve(true);
      request.onerror = () => reject(request.error);
    });
  }

  // -- Stat Query -----------------------------------------------------------

  async stat(key: string): Promise<EntryMetadata | null> {
    const store = await this._tx('readonly');
    return new Promise((resolve, reject) => {
      const request = store.get(key);
      request.onsuccess = () => {
        const record = request.result as StoredRecord | undefined;
        if (!record) {
          resolve(null);
          return;
        }
        resolve({
          key,
          size: record.data.byteLength,
          lastModified: new Date(record.lastModified),
          contentType: 'application/octet-stream',
        });
      };
      request.onerror = () => reject(request.error);
    });
  }

  async exists(key: string): Promise<boolean> {
    const store = await this._tx('readonly');
    return new Promise((resolve, reject) => {
      const request = store.count(key);
      request.onsuccess = () => resolve(request.result > 0);
      request.onerror = () => reject(request.error);
    });
  }

  /** Close the IndexedDB connection. */
  async close(): Promise<void> {
    if (this._db) {
      this._db.close();
      this._db = null;
    }
  }
}
