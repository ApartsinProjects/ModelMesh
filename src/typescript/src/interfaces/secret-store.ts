/**
 * Secret store connector interface and associated data types.
 *
 * Defines the SecretStoreConnector interface for resolving API keys
 * and tokens from a secure backend at runtime.
 */

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

export interface SecretValue {
  value: string;
  version?: string;
  expiresAt?: Date;
}

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface SecretResolution {
  get(name: string): string;
}

export interface SecretManagement {
  set(name: string, value: string): void;
  list(): string[];
  delete(name: string): void;
}

export interface SecretStoreConnector extends SecretResolution {}
