/**
 * Browser localStorage secret store connector.
 *
 * Persists secrets in the browser's localStorage under a configurable
 * key prefix. Secrets survive page reloads and browser restarts.
 *
 * Connector ID: modelmesh.browser-secrets.v1
 *
 * **Security note:** localStorage is accessible to any JavaScript
 * running on the same origin. This connector is intended for
 * convenience in browser demos and prototypes, not for production
 * secret management.
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { SecretStoreConnector, SecretManagement } from '../../interfaces/secret-store';

export interface BrowserSecretStoreConfig {
  /** Key prefix for namespace isolation.  Defaults to "modelmesh-secret:". */
  prefix?: string;
  /** If true, throw when a secret is not found. Default: true. */
  failOnMissing?: boolean;
}

export class BrowserSecretStore implements SecretStoreConnector, SecretManagement {
  static readonly CONNECTOR_ID = 'modelmesh.browser-secrets.v1';
  static readonly RUNTIME = RuntimeEnvironment.BROWSER_ONLY;

  private readonly _prefix: string;
  private readonly _failOnMissing: boolean;

  constructor(config?: BrowserSecretStoreConfig) {
    this._prefix = config?.prefix ?? 'modelmesh-secret:';
    this._failOnMissing = config?.failOnMissing ?? true;
  }

  get(name: string): string {
    const value = localStorage.getItem(this._prefix + name);
    if (value === null) {
      if (this._failOnMissing) {
        throw new Error(`Secret not found: ${name}`);
      }
      return '';
    }
    return value;
  }

  set(name: string, value: string): void {
    localStorage.setItem(this._prefix + name, value);
  }

  list(): string[] {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(this._prefix)) {
        keys.push(k.substring(this._prefix.length));
      }
    }
    return keys.sort();
  }

  delete(name: string): void {
    const key = this._prefix + name;
    if (localStorage.getItem(key) === null) {
      throw new Error(`Secret not found: ${name}`);
    }
    localStorage.removeItem(key);
  }
}
