/**
 * File-based secret store for the CDK.
 *
 * Reads secrets from environment files (.env) or JSON files.
 * Matches Python's FileSecretStore from
 * modelmesh.cdk.specialized.file_secret_store.
 */

import * as fs from 'fs';
import { BaseSecretStore, BaseSecretStoreConfig } from '../base-secret-store';
import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface FileSecretStoreConfig extends BaseSecretStoreConfig {
  filePath?: string;
  format?: 'env' | 'json';
}

/**
 * Secret store that reads from .env or JSON files.
 *
 * @example
 * const store = new FileSecretStore({
 *   filePath: '.env',
 *   format: 'env',
 * });
 * const key = store.get('OPENAI_API_KEY');
 */
export class FileSecretStore extends BaseSecretStore {
  static override readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private readonly _fileConfig: { filePath: string; format: 'env' | 'json' };
  private _secrets = new Map<string, string>();

  constructor(config?: FileSecretStoreConfig) {
    super(config);
    this._fileConfig = {
      filePath: config?.filePath ?? '.env',
      format: config?.format ?? 'env',
    };
    this._loadFile();
  }

  get(name: string): string {
    const val = this._secrets.get(name);
    if (val !== undefined) return val;
    // Fallback to environment
    const envVal = process.env[name];
    if (envVal !== undefined) return envVal;
    throw new Error(`Secret '${name}' not found`);
  }

  private _loadFile(): void {
    try {
      const content = fs.readFileSync(this._fileConfig.filePath, 'utf-8');
      if (this._fileConfig.format === 'json') {
        const parsed = JSON.parse(content);
        if (typeof parsed === 'object' && parsed !== null) {
          for (const [k, v] of Object.entries(parsed)) {
            if (typeof v === 'string') this._secrets.set(k, v);
          }
        }
      } else {
        // Parse .env format
        for (const line of content.split(/\r?\n/)) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith('#')) continue;
          const eqIdx = trimmed.indexOf('=');
          if (eqIdx === -1) continue;
          const key = trimmed.slice(0, eqIdx).trim();
          let value = trimmed.slice(eqIdx + 1).trim();
          // Strip quotes
          if (
            (value.startsWith('"') && value.endsWith('"')) ||
            (value.startsWith("'") && value.endsWith("'"))
          ) {
            value = value.slice(1, -1);
          }
          this._secrets.set(key, value);
        }
      }
    } catch {
      // File not found — will rely on env fallback
    }
  }
}
