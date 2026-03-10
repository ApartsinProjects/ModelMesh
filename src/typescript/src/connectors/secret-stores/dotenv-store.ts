/**
 * Dotenv file secret store connector.
 *
 * Resolves secrets from .env files by parsing KEY=VALUE lines.
 * Supports comments (#), quoted values, and multiline values.
 *
 * Connector ID: modelmesh.dotenv.v1
 */

import * as fs from 'fs';
import type { SecretStoreConnector } from '../../interfaces/secret-store';

export interface DotenvSecretStoreConfig {
  filePath?: string;
  overrideEnv?: boolean;
  failOnMissing?: boolean;
}

export class DotenvSecretStore implements SecretStoreConnector {
  static readonly CONNECTOR_ID = 'modelmesh.dotenv.v1';
  private readonly _overrideEnv: boolean;
  private readonly _failOnMissing: boolean;
  private _values: Record<string, string> = {};

  constructor(config?: DotenvSecretStoreConfig) {
    this._overrideEnv = config?.overrideEnv ?? false;
    this._failOnMissing = config?.failOnMissing ?? false;
    this._loadFile(config?.filePath ?? '.env');
  }

  private _loadFile(filePath: string): void {
    try {
      if (!fs.existsSync(filePath)) return;
      const content = fs.readFileSync(filePath, 'utf-8');
      const lines = content.split('\n');

      let i = 0;
      while (i < lines.length) {
        let line = lines[i].replace(/\r$/, '');
        i++;

        const stripped = line.trim();
        if (!stripped || stripped.startsWith('#')) continue;
        if (!stripped.includes('=')) continue;

        const eqIdx = stripped.indexOf('=');
        const key = stripped.substring(0, eqIdx).trim();
        let rawValue = stripped.substring(eqIdx + 1).trim();

        // Handle backslash continuation
        while (rawValue.endsWith('\\') && i < lines.length) {
          rawValue = rawValue.slice(0, -1) + lines[i].replace(/\r$/, '');
          i++;
        }

        // Handle quoted values
        if (
          rawValue.length >= 2 &&
          rawValue[0] === rawValue[rawValue.length - 1] &&
          (rawValue[0] === "'" || rawValue[0] === '"')
        ) {
          rawValue = rawValue.slice(1, -1);
        } else {
          // Strip inline comments for unquoted values
          for (const commentPrefix of [' #', '\t#']) {
            const commentIdx = rawValue.indexOf(commentPrefix);
            if (commentIdx >= 0) {
              rawValue = rawValue.substring(0, commentIdx).trimEnd();
              break;
            }
          }
        }

        if (key) {
          this._values[key] = rawValue;
        }
      }
    } catch {
      // Ignore file read errors
    }
  }

  get(name: string): string {
    const envValue = process.env[name];
    const fileValue = this._values[name];

    let result: string | undefined;
    if (this._overrideEnv) {
      result = fileValue ?? envValue;
    } else {
      result = envValue ?? fileValue;
    }

    if (result === undefined) {
      if (this._failOnMissing) {
        throw new Error(`Secret '${name}' not found`);
      }
      return '';
    }
    return result;
  }
}
