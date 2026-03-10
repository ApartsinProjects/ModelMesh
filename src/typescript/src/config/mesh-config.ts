/**
 * MeshConfig -- declarative configuration object.
 *
 * Holds the raw configuration dictionary and provides convenience methods
 * for loading from JSON files and accessing configuration sections.
 * Configuration can be built programmatically, loaded from a JSON/YAML
 * file, or constructed by the convenience layer's auto-detection logic.
 */

import * as fs from 'fs';

export class MeshConfig {
  readonly raw: Record<string, unknown>;

  constructor(raw?: Record<string, unknown>) {
    this.raw = raw ?? {};
  }

  /**
   * Load configuration from a JSON file.
   *
   * Since this implementation avoids external dependencies, only JSON
   * files are supported natively. For YAML support, parse externally
   * and use fromDict().
   */
  static fromFile(filePath: string): MeshConfig {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);
    return new MeshConfig(data);
  }

  /** Alias for fromFile. */
  static fromJson(filePath: string): MeshConfig {
    return MeshConfig.fromFile(filePath);
  }

  /** Create a MeshConfig from a plain object. */
  static fromDict(data: Record<string, unknown>): MeshConfig {
    return new MeshConfig(data);
  }

  // -- Section accessors ---------------------------------------------------

  get providers(): Record<string, unknown> {
    return (this.raw.providers as Record<string, unknown>) ?? {};
  }

  get models(): Record<string, unknown> {
    return (this.raw.models as Record<string, unknown>) ?? {};
  }

  get pools(): Record<string, unknown> {
    return (this.raw.pools as Record<string, unknown>) ?? {};
  }

  get secrets(): Record<string, unknown> {
    return (this.raw.secrets as Record<string, unknown>) ?? {};
  }

  get observability(): Record<string, unknown> {
    return (this.raw.observability as Record<string, unknown>) ?? {};
  }

  get storage(): Record<string, unknown> {
    return (this.raw.storage as Record<string, unknown>) ?? {};
  }

  // -- Utility methods -----------------------------------------------------

  get(key: string, defaultValue?: unknown): unknown {
    return key in this.raw ? this.raw[key] : defaultValue;
  }

  /**
   * Create a new MeshConfig with overrides applied.
   *
   * Performs a shallow merge: top-level keys from overrides replace
   * or extend the corresponding keys in this config.
   */
  merge(overrides: Record<string, unknown>): MeshConfig {
    const merged: Record<string, unknown> = { ...this.raw };
    for (const [key, value] of Object.entries(overrides)) {
      if (
        typeof value === 'object' &&
        value !== null &&
        !Array.isArray(value) &&
        typeof merged[key] === 'object' &&
        merged[key] !== null &&
        !Array.isArray(merged[key])
      ) {
        merged[key] = {
          ...(merged[key] as Record<string, unknown>),
          ...(value as Record<string, unknown>),
        };
      } else {
        merged[key] = value;
      }
    }
    return new MeshConfig(merged);
  }

  /**
   * Run basic validation on the configuration.
   *
   * @returns A list of validation error messages. An empty list means
   *     the configuration is valid.
   */
  validate(): string[] {
    const errors: string[] = [];

    if ('providers' in this.raw && typeof this.raw.providers !== 'object') {
      errors.push("'providers' must be an object");
    }

    if ('models' in this.raw && typeof this.raw.models !== 'object') {
      errors.push("'models' must be an object");
    }

    if ('pools' in this.raw && typeof this.raw.pools !== 'object') {
      errors.push("'pools' must be an object");
    }

    // Check that pool models reference known model IDs
    if ('pools' in this.raw && 'models' in this.raw) {
      const knownModels = new Set(Object.keys(this.models));
      const poolsDef = this.pools;
      for (const [poolId, poolDef] of Object.entries(poolsDef)) {
        const pool = poolDef as Record<string, unknown>;
        const modelList = pool.models as string[] | undefined;
        if (modelList) {
          for (const modelRef of modelList) {
            if (!knownModels.has(modelRef)) {
              errors.push(
                `Pool '${poolId}' references unknown model '${modelRef}'`
              );
            }
          }
        }
      }
    }

    return errors;
  }
}
