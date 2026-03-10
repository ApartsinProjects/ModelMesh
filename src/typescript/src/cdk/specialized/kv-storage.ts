/**
 * Key-value storage for the CDK.
 *
 * Extends BaseStorage with pluggable backends: in-memory (default) or
 * file-based JSON persistence. The memory backend uses the inherited
 * Map; the file backend serializes to and deserializes from a JSON file.
 */

import * as fs from 'fs';
import { BaseStorage, BaseStorageConfig } from '../base-storage';
import { StorageEntry } from '../../interfaces/storage';
import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface KeyValueStorageConfig extends BaseStorageConfig {
  backend?: 'memory' | 'file';
  filePath?: string;
}

/**
 * Pluggable key-value storage with memory or file backend.
 *
 * @example
 * // In-memory (default)
 * const store = new KeyValueStorage();
 *
 * // File-backed
 * const store = new KeyValueStorage({
 *   backend: 'file',
 *   filePath: '/var/data/modelmesh/state.json',
 * });
 */
export class KeyValueStorage extends BaseStorage {
  static override readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private readonly _kvConfig: Required<KeyValueStorageConfig>;

  constructor(config?: KeyValueStorageConfig) {
    super(config);
    this._kvConfig = {
      format: config?.format ?? 'json',
      compression: config?.compression ?? false,
      lockingEnabled: config?.lockingEnabled ?? true,
      lockTimeoutSeconds: config?.lockTimeoutSeconds ?? 30.0,
      backend: config?.backend ?? 'memory',
      filePath: config?.filePath ?? '',
    };

    if (this._kvConfig.backend === 'file' && this._kvConfig.filePath) {
      this._loadFromFile();
    }
  }

  async save(key: string, entry: StorageEntry): Promise<void> {
    await super.save(key, entry);
    if (this._kvConfig.backend === 'file') {
      this._saveToFile();
    }
  }

  async delete(key: string): Promise<boolean> {
    const result = await super.delete(key);
    if (result && this._kvConfig.backend === 'file') {
      this._saveToFile();
    }
    return result;
  }

  private _loadFromFile(): void {
    if (!this._kvConfig.filePath) return;
    try {
      const content = fs.readFileSync(this._kvConfig.filePath, 'utf-8');
      const raw = JSON.parse(content);
      if (typeof raw !== 'object' || raw === null) return;

      for (const [key, record] of Object.entries(raw)) {
        if (typeof record !== 'object' || record === null) continue;
        const rec = record as Record<string, unknown>;
        const dataB64 = (rec.data as string) ?? '';
        const data = Buffer.from(dataB64, 'base64');
        const metadata = (rec.metadata as Record<string, unknown>) ?? {};
        this._store.set(key, { key, data, metadata });
        const tsStr = rec.timestamp as string | undefined;
        if (tsStr) {
          try {
            this._timestamps.set(key, new Date(tsStr));
          } catch {
            this._timestamps.set(key, new Date());
          }
        } else {
          this._timestamps.set(key, new Date());
        }
      }
    } catch {
      // File doesn't exist or can't be parsed — start empty
    }
  }

  private _saveToFile(): void {
    if (!this._kvConfig.filePath) return;
    const output: Record<string, unknown> = {};
    for (const [key, entry] of this._store.entries()) {
      output[key] = {
        data: entry.data.toString('base64'),
        metadata: entry.metadata,
        timestamp: (this._timestamps.get(key) ?? new Date()).toISOString(),
      };
    }
    try {
      fs.writeFileSync(this._kvConfig.filePath, JSON.stringify(output, null, 2), 'utf-8');
    } catch {
      // Silently ignore write errors
    }
  }
}
