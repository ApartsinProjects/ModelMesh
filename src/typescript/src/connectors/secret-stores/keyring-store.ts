/**
 * OS keychain secret store connector.
 *
 * Resolves secrets from the operating system's native credential store.
 * Uses the `keytar` npm package when available. Falls back gracefully
 * if the library is not installed.
 *
 * Connector ID: modelmesh.keyring.v1
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { SecretStoreConnector } from '../../interfaces/secret-store';

export interface KeyringSecretStoreConfig {
  /**
   * The service/application name under which secrets are stored
   * in the OS keychain. Defaults to "modelmesh".
   */
  serviceName?: string;
  /** If true, throw when a secret is not found. Default: true. */
  failOnMissing?: boolean;
}

// Attempt to load keytar at module level
let _keytar: {
  getPassword(service: string, account: string): Promise<string | null>;
  setPassword(service: string, account: string, password: string): Promise<void>;
  deletePassword(service: string, account: string): Promise<boolean>;
  findCredentials(service: string): Promise<Array<{ account: string; password: string }>>;
} | null = null;
let _keytarAvailable = false;

try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  _keytar = require('keytar');
  _keytarAvailable = true;
} catch {
  _keytar = null;
  _keytarAvailable = false;
}

/**
 * Secret store backed by the operating system's keychain.
 *
 * Uses the `keytar` npm package to read secrets from the OS-native
 * credential store (macOS Keychain, Windows Credential Locker,
 * Linux SecretService / KWallet).
 *
 * If `keytar` is not installed, initialisation succeeds but all
 * lookups return empty string (or throw if failOnMissing is true).
 * The `keytarAvailable` property indicates whether the backend
 * is usable.
 *
 * Note: Because keytar's API is async, `get()` performs a synchronous
 * wrapper using `execSync` for compatibility with the SecretStoreConnector
 * interface. For async-first code, use `getAsync()` instead.
 *
 * @example
 * const store = new KeyringSecretStore({ serviceName: 'modelmesh-prod' });
 * if (store.keytarAvailable) {
 *   const key = await store.getAsync('OPENAI_API_KEY');
 * }
 */
export class KeyringSecretStore implements SecretStoreConnector {
  static readonly CONNECTOR_ID = 'modelmesh.keyring.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private readonly _serviceName: string;
  private readonly _failOnMissing: boolean;
  private _cache: Record<string, string> = {};

  constructor(config?: KeyringSecretStoreConfig) {
    this._serviceName = config?.serviceName ?? 'modelmesh';
    this._failOnMissing = config?.failOnMissing ?? true;
  }

  /** Return true if the `keytar` library is installed. */
  get keytarAvailable(): boolean {
    return _keytarAvailable;
  }

  /**
   * Synchronous get -- returns from internal cache.
   *
   * Call `preload()` or `getAsync()` first to populate the cache
   * from the OS keychain. If the cache does not contain the secret,
   * returns empty string or throws depending on config.
   */
  get(name: string): string {
    const value = this._cache[name];
    if (value !== undefined) {
      return value;
    }
    if (this._failOnMissing) {
      throw new Error(`Secret '${name}' not found in keyring cache. Call preload() or getAsync() first.`);
    }
    return '';
  }

  /**
   * Asynchronously retrieve a secret from the OS keychain.
   *
   * Also populates the internal cache so subsequent `get()` calls
   * return the value synchronously.
   */
  async getAsync(name: string): Promise<string> {
    if (!_keytarAvailable || !_keytar) {
      if (this._failOnMissing) {
        throw new Error('keytar library is not installed');
      }
      return '';
    }

    try {
      const value = await _keytar.getPassword(this._serviceName, name);
      if (value === null) {
        if (this._failOnMissing) {
          throw new Error(`Secret '${name}' not found in OS keychain`);
        }
        return '';
      }
      this._cache[name] = value;
      return value;
    } catch (err) {
      if (this._failOnMissing) {
        throw err;
      }
      return '';
    }
  }

  /**
   * Pre-load secrets from the OS keychain into the internal cache.
   *
   * After calling this, `get()` can be used synchronously.
   */
  async preload(names: string[]): Promise<void> {
    for (const name of names) {
      await this.getAsync(name);
    }
  }

  /**
   * Store a secret in the OS keychain.
   */
  async setAsync(name: string, value: string): Promise<void> {
    if (!_keytarAvailable || !_keytar) {
      throw new Error('keytar library is not installed');
    }
    await _keytar.setPassword(this._serviceName, name, value);
    this._cache[name] = value;
  }

  /**
   * Delete a secret from the OS keychain.
   */
  async deleteAsync(name: string): Promise<boolean> {
    if (!_keytarAvailable || !_keytar) {
      throw new Error('keytar library is not installed');
    }
    const result = await _keytar.deletePassword(this._serviceName, name);
    delete this._cache[name];
    return result;
  }

  /**
   * Clear the internal cache.
   */
  clearCache(): void {
    this._cache = {};
  }
}
