/**
 * SQLite-style key-value storage connector.
 *
 * In the TypeScript implementation, this uses a JSON file backend
 * to maintain zero external dependencies. Provides the same API as
 * the Python SQLite connector.
 *
 * Connector ID: modelmesh.sqlite.v1
 */

import * as fs from 'fs';
import * as path from 'path';
import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { EntryMetadata, StorageConnector, StorageEntry } from '../../interfaces/storage';

export interface SqliteStorageConfig {
  dbPath?: string;
  tableName?: string;
}

export class SqliteStorage implements StorageConnector {
  static readonly CONNECTOR_ID = 'modelmesh.sqlite.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private readonly _config: Required<SqliteStorageConfig>;
  private _data: Record<string, { data: string; metadata: string; lastModified: string }> = {};

  constructor(config?: SqliteStorageConfig) {
    this._config = {
      dbPath: config?.dbPath ?? 'modelmesh_state.db.json',
      tableName: config?.tableName ?? 'kv_store',
    };
    this._loadFile();
  }

  private get _filePath(): string {
    return this._config.dbPath;
  }

  private _loadFile(): void {
    try {
      if (fs.existsSync(this._filePath)) {
        const raw = fs.readFileSync(this._filePath, 'utf-8');
        const parsed = JSON.parse(raw);
        this._data = parsed[this._config.tableName] ?? {};
      }
    } catch {
      this._data = {};
    }
  }

  private _saveFile(): void {
    const dir = path.dirname(this._filePath);
    if (dir) fs.mkdirSync(dir, { recursive: true });
    const wrapped = { [this._config.tableName]: this._data };
    fs.writeFileSync(this._filePath, JSON.stringify(wrapped, null, 2), 'utf-8');
  }

  async load(key: string): Promise<StorageEntry | null> {
    const entry = this._data[key];
    if (!entry) return null;
    return {
      key,
      data: Buffer.from(entry.data, 'base64'),
      metadata: JSON.parse(entry.metadata),
    };
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    this._data[key] = {
      data: entry.data.toString('base64'),
      metadata: JSON.stringify(entry.metadata),
      lastModified: new Date().toISOString(),
    };
    this._saveFile();
  }

  async list(prefix?: string): Promise<string[]> {
    const keys = Object.keys(this._data).sort();
    if (prefix === undefined) return keys;
    return keys.filter((k) => k.startsWith(prefix));
  }

  async delete(key: string): Promise<boolean> {
    if (key in this._data) {
      delete this._data[key];
      this._saveFile();
      return true;
    }
    return false;
  }

  async stat(key: string): Promise<EntryMetadata | null> {
    const entry = this._data[key];
    if (!entry) return null;
    return {
      key,
      size: Buffer.from(entry.data, 'base64').length,
      lastModified: new Date(entry.lastModified),
      contentType: 'application/octet-stream',
    };
  }

  async exists(key: string): Promise<boolean> {
    return key in this._data;
  }

  close(): void {
    // No-op for JSON backend
  }
}
