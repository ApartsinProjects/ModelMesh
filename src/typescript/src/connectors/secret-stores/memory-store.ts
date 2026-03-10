/**
 * In-memory secret store connector.
 *
 * Resolves secrets from a user-provided dictionary. Keys are supplied at
 * construction time and held in memory for the lifetime of the store.
 *
 * Connector ID: modelmesh.memory.v1
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { SecretStoreConnector, SecretManagement } from '../../interfaces/secret-store';

export interface MemorySecretStoreConfig {
  /** Secret name/value pairs to initialise the store with. */
  secrets?: Record<string, string>;
  /** If true, throw when a secret is not found. Default: true. */
  failOnMissing?: boolean;
}

/**
 * Secret store backed entirely by an in-memory dictionary.
 *
 * All secrets are held in a plain object and never touch disk or
 * network. The caller supplies keys at construction time.
 *
 * This connector also implements SecretManagement so secrets can be
 * added, listed, and removed at runtime.
 *
 * Ideal for:
 * - Unit testing -- inject known secrets without environment setup.
 * - Scripts / notebooks -- pass keys directly from user input.
 * - Hardcoded keys -- embed API keys for personal tools.
 *
 * @example
 * const store = new MemorySecretStore({
 *   secrets: {
 *     OPENAI_API_KEY: 'sk-abc...',
 *     ANTHROPIC_API_KEY: 'sk-ant...',
 *   },
 * });
 * const key = store.get('OPENAI_API_KEY');
 *
 * // Add at runtime
 * store.set('NEW_KEY', 'value123');
 */
export class MemorySecretStore implements SecretStoreConnector, SecretManagement {
  static readonly CONNECTOR_ID = 'modelmesh.memory-secrets.v1';
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;
  private readonly _secrets: Record<string, string>;
  private readonly _failOnMissing: boolean;

  constructor(config?: MemorySecretStoreConfig) {
    this._secrets = { ...(config?.secrets ?? {}) };
    this._failOnMissing = config?.failOnMissing ?? true;
  }

  get(name: string): string {
    const value = this._secrets[name];
    if (value === undefined) {
      if (this._failOnMissing) {
        throw new Error(`Secret not found: ${name}`);
      }
      return '';
    }
    return value;
  }

  set(name: string, value: string): void {
    this._secrets[name] = value;
  }

  list(): string[] {
    return Object.keys(this._secrets).sort();
  }

  delete(name: string): void {
    if (!(name in this._secrets)) {
      throw new Error(`Secret not found: ${name}`);
    }
    delete this._secrets[name];
  }
}
