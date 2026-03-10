/**
 * Base secret store implementation for the CDK.
 *
 * Implements the SecretStoreConnector interface with an in-memory
 * dictionary backend and optional TTL-based caching. Subclasses override
 * the _resolve(name) hook to read secrets from files, vaults, or
 * cloud services.
 */

import { RuntimeEnvironment } from '../interfaces/runtime';
import { SecretStoreConnector } from '../interfaces/secret-store';

export interface BaseSecretStoreConfig {
  secrets?: Record<string, string>;
  cacheEnabled?: boolean;
  cacheTtlMs?: number;
  failOnMissing?: boolean;
}

export class BaseSecretStore implements SecretStoreConnector {
  static readonly RUNTIME = RuntimeEnvironment.UNIVERSAL;

  protected readonly _config: Required<BaseSecretStoreConfig>;
  private readonly _cache = new Map<string, { value: string; expiresAt: number }>();

  constructor(config?: BaseSecretStoreConfig) {
    this._config = {
      secrets: config?.secrets ?? {},
      cacheEnabled: config?.cacheEnabled ?? true,
      cacheTtlMs: config?.cacheTtlMs ?? 300000,
      failOnMissing: config?.failOnMissing ?? true,
    };
  }

  get(name: string): string {
    // Check cache
    if (this._config.cacheEnabled && this._cache.has(name)) {
      const cached = this._cache.get(name)!;
      if (Date.now() < cached.expiresAt) {
        return cached.value;
      }
      this._cache.delete(name);
    }

    // Resolve from backend
    const value = this._resolve(name);
    if (value == null) {
      if (this._config.failOnMissing) {
        throw new Error('Secret not found: ' + name);
      }
      return '';
    }

    // Cache the result
    if (this._config.cacheEnabled) {
      this._cache.set(name, {
        value,
        expiresAt: Date.now() + this._config.cacheTtlMs,
      });
    }

    return value;
  }

  protected _resolve(name: string): string | null {
    return this._config.secrets[name] ?? null;
  }

  clearCache(): void {
    this._cache.clear();
  }
}
