/**
 * Environment variable secret store connector.
 *
 * Resolves secrets from environment variables. An optional prefix
 * can be configured to scope lookups.
 *
 * Connector ID: modelmesh.env.v1
 */

import type { SecretStoreConnector } from '../../interfaces/secret-store';

export interface EnvSecretStoreConfig {
  prefix?: string;
  failOnMissing?: boolean;
}

export class EnvSecretStore implements SecretStoreConnector {
  static readonly CONNECTOR_ID = 'modelmesh.env.v1';
  private readonly _prefix: string;
  private readonly _failOnMissing: boolean;

  constructor(config?: EnvSecretStoreConfig) {
    this._prefix = config?.prefix ?? '';
    this._failOnMissing = config?.failOnMissing ?? false;
  }

  get(name: string): string {
    const envName = this._prefix + name;
    const value = process.env[envName];
    if (value === undefined) {
      if (this._failOnMissing) {
        throw new Error(`Secret '${envName}' not found in environment`);
      }
      return '';
    }
    return value;
  }
}
