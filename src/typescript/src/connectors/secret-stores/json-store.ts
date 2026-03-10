/**
 * JSON file secret store connector.
 *
 * Resolves secrets from a JSON file. Supports nested objects with
 * dot-notation paths.
 *
 * Connector ID: modelmesh.json-secrets.v1
 */

import * as fs from 'fs';
import type { SecretStoreConnector } from '../../interfaces/secret-store';

export interface JsonSecretStoreConfig {
  filePath?: string;
  jsonPath?: string;
  failOnMissing?: boolean;
}

export class JsonSecretStore implements SecretStoreConnector {
  static readonly CONNECTOR_ID = 'modelmesh.json-secrets.v1';
  private readonly _failOnMissing: boolean;
  private _data: Record<string, unknown> = {};

  constructor(config?: JsonSecretStoreConfig) {
    this._failOnMissing = config?.failOnMissing ?? false;
    this._loadFile(config?.filePath ?? '', config?.jsonPath ?? '');
  }

  private _loadFile(filePath: string, jsonPath: string): void {
    if (!filePath) return;
    try {
      if (!fs.existsSync(filePath)) return;
      const raw = fs.readFileSync(filePath, 'utf-8');
      let data = JSON.parse(raw);

      if (jsonPath) {
        data = JsonSecretStore._traverse(data, jsonPath);
      }

      this._data = typeof data === 'object' && data !== null ? data : {};
    } catch {
      this._data = {};
    }
  }

  private static _traverse(data: unknown, dotPath: string): Record<string, unknown> {
    let current: unknown = data;
    for (const segment of dotPath.split('.')) {
      if (typeof current !== 'object' || current === null || !(segment in (current as Record<string, unknown>))) {
        return {};
      }
      current = (current as Record<string, unknown>)[segment];
    }
    if (typeof current !== 'object' || current === null) {
      return {};
    }
    return current as Record<string, unknown>;
  }

  get(name: string): string {
    let current: unknown = this._data;
    const segments = name.split('.');
    for (const segment of segments) {
      if (typeof current !== 'object' || current === null || !(segment in (current as Record<string, unknown>))) {
        if (this._failOnMissing) {
          throw new Error(`Secret '${name}' not found`);
        }
        return '';
      }
      current = (current as Record<string, unknown>)[segment];
    }

    if (current === null || current === undefined) {
      if (this._failOnMissing) {
        throw new Error(`Secret '${name}' not found`);
      }
      return '';
    }
    return String(current);
  }
}
