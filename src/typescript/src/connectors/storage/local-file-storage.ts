/**
 * Local file storage connector.
 *
 * Persists key-value data to a local JSON file. Suitable for
 * development, testing, and single-process deployments.
 *
 * Connector ID: modelmesh.local-file.v1
 */

import * as fs from 'fs';
import * as path from 'path';
import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { EntryMetadata, StorageConnector, StorageEntry } from '../../interfaces/storage';

export interface LocalFileStorageConfig {
  filePath?: string;
}

export class LocalFileStorage implements StorageConnector {
  static readonly CONNECTOR_ID = 'modelmesh.local-file.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private readonly _filePath: string;
  private _data: Record<string, { key: string; data: string; metadata: Record<string, unknown>; lastModified: string }> = {};

  constructor(config?: LocalFileStorageConfig) {
    this._filePath = config?.filePath ?? 'modelmesh_state.json';
    this._loadFile();
  }

  private _loadFile(): void {
    try {
      if (fs.existsSync(this._filePath)) {
        const raw = fs.readFileSync(this._filePath, 'utf-8');
        this._data = JSON.parse(raw);
      }
    } catch {
      this._data = {};
    }
  }

  private _saveFile(): void {
    const dir = path.dirname(this._filePath);
    if (dir) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(this._filePath, JSON.stringify(this._data, null, 2), 'utf-8');
  }

  async load(key: string): Promise<StorageEntry | null> {
    const entry = this._data[key];
    if (!entry) return null;
    return {
      key: entry.key,
      data: Buffer.from(entry.data, 'base64'),
      metadata: entry.metadata,
    };
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    this._data[key] = {
      key,
      data: entry.data.toString('base64'),
      metadata: entry.metadata as Record<string, unknown>,
      lastModified: new Date().toISOString(),
    };
    this._saveFile();
  }

  async list(prefix?: string): Promise<string[]> {
    const keys = Object.keys(this._data);
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
}
