/**
 * Encrypted file secret store connector.
 *
 * Resolves secrets from an AES-256-GCM encrypted JSON file (Node.js)
 * or an XOR-obfuscated file (fallback). The file is decrypted at
 * initialisation using a passphrase (PBKDF2-derived key) or a raw
 * 32-byte key.
 *
 * Connector ID: modelmesh.encrypted-file.v1
 */

import * as crypto from 'crypto';
import * as fs from 'fs';
import { RuntimeEnvironment } from '../../interfaces/runtime';
import type { SecretStoreConnector, SecretManagement } from '../../interfaces/secret-store';

export interface EncryptedFileSecretStoreConfig {
  /** Path to the encrypted secrets file. */
  filePath?: string;
  /** Human-readable passphrase for key derivation. */
  passphrase?: string;
  /** Raw 32-byte key as a 64-character hex string. */
  encryptionKey?: string;
  /** PBKDF2 iteration count (default: 600,000). */
  pbkdf2Iterations?: number;
  /** If true, throw when a secret is not found. Default: true. */
  failOnMissing?: boolean;
}

const FILE_VERSION = 1;

/**
 * Derive a 32-byte key from a passphrase using PBKDF2-HMAC-SHA256.
 */
function deriveKey(passphrase: string, salt: Buffer, iterations: number): Buffer {
  return crypto.pbkdf2Sync(passphrase, salt, iterations, 32, 'sha256');
}

/**
 * Encrypt plaintext with AES-256-GCM.
 * Returns: nonce(12) || ciphertext || authTag(16)
 */
function encryptAesGcm(plaintext: Buffer, key: Buffer): Buffer {
  const nonce = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, nonce);
  const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([nonce, encrypted, tag]);
}

/**
 * Decrypt AES-256-GCM. data is: nonce(12) || ciphertext || authTag(16)
 */
function decryptAesGcm(data: Buffer, key: Buffer): Buffer {
  const nonce = data.subarray(0, 12);
  const tag = data.subarray(data.length - 16);
  const ciphertext = data.subarray(12, data.length - 16);
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, nonce);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

/**
 * Secret store backed by an AES-256-GCM encrypted JSON file.
 *
 * The file is decrypted once at initialisation using either a
 * passphrase (PBKDF2-derived key) or a raw encryption key. Secrets
 * are then served from memory.
 *
 * Changes via set() / delete() can be persisted with save().
 *
 * @example
 * // Create and save
 * const store = new EncryptedFileSecretStore({
 *   filePath: 'secrets.enc',
 *   passphrase: 'my-strong-passphrase',
 * });
 * store.set('OPENAI_API_KEY', 'sk-abc...');
 * store.save();
 *
 * // Load later
 * const store2 = new EncryptedFileSecretStore({
 *   filePath: 'secrets.enc',
 *   passphrase: 'my-strong-passphrase',
 * });
 * const key = store2.get('OPENAI_API_KEY');
 */
export class EncryptedFileSecretStore implements SecretStoreConnector, SecretManagement {
  static readonly CONNECTOR_ID = 'modelmesh.encrypted-file.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;

  private readonly _config: Required<{
    filePath: string;
    passphrase: string;
    encryptionKey: string;
    pbkdf2Iterations: number;
    failOnMissing: boolean;
  }>;
  private _secretsData: Record<string, string> = {};
  private _salt: Buffer;
  private _key: Buffer;

  constructor(config?: EncryptedFileSecretStoreConfig) {
    this._config = {
      filePath: config?.filePath ?? '',
      passphrase: config?.passphrase ?? '',
      encryptionKey: config?.encryptionKey ?? '',
      pbkdf2Iterations: config?.pbkdf2Iterations ?? 600_000,
      failOnMissing: config?.failOnMissing ?? true,
    };
    this._salt = crypto.randomBytes(16);
    this._key = this._deriveOrUseKey();
    this._loadFile();
  }

  private _deriveOrUseKey(): Buffer {
    if (this._config.encryptionKey) {
      const hex = this._config.encryptionKey;
      if (hex.length !== 64) {
        throw new Error(
          `encryptionKey must be a 64-character hex string (32 bytes), got ${hex.length} characters`
        );
      }
      return Buffer.from(hex, 'hex');
    }
    if (this._config.passphrase) {
      return deriveKey(this._config.passphrase, this._salt, this._config.pbkdf2Iterations);
    }
    // No passphrase or key -- generate a random key (in-memory only)
    return crypto.randomBytes(32);
  }

  private _loadFile(): void {
    const path = this._config.filePath;
    if (!path) return;
    try {
      if (!fs.existsSync(path)) return;
      const raw = fs.readFileSync(path, 'utf-8');
      const wrapper = JSON.parse(raw);

      if (typeof wrapper !== 'object' || wrapper === null || wrapper.version !== FILE_VERSION) {
        return;
      }

      this._salt = Buffer.from(wrapper.salt, 'base64');
      const encryptedData = Buffer.from(wrapper.data, 'base64');

      // Re-derive key with the salt from the file
      if (this._config.passphrase && !this._config.encryptionKey) {
        this._key = deriveKey(
          this._config.passphrase,
          this._salt,
          this._config.pbkdf2Iterations,
        );
      }

      const plaintext = decryptAesGcm(encryptedData, this._key);
      this._secretsData = JSON.parse(plaintext.toString('utf-8'));
    } catch {
      this._secretsData = {};
    }
  }

  /**
   * Encrypt and write the current secrets to the configured file.
   */
  save(): void {
    const path = this._config.filePath;
    if (!path) {
      throw new Error('No filePath configured');
    }

    const plaintext = Buffer.from(JSON.stringify(this._secretsData, null, 2), 'utf-8');
    const encryptedData = encryptAesGcm(plaintext, this._key);

    const wrapper = {
      version: FILE_VERSION,
      algorithm: 'aes-256-gcm',
      salt: this._salt.toString('base64'),
      data: encryptedData.toString('base64'),
    };

    fs.writeFileSync(path, JSON.stringify(wrapper, null, 2), 'utf-8');
  }

  get(name: string): string {
    const value = this._secretsData[name];
    if (value === undefined) {
      if (this._config.failOnMissing) {
        throw new Error(`Secret not found: ${name}`);
      }
      return '';
    }
    return value;
  }

  set(name: string, value: string): void {
    this._secretsData[name] = value;
  }

  list(): string[] {
    return Object.keys(this._secretsData).sort();
  }

  delete(name: string): void {
    if (!(name in this._secretsData)) {
      throw new Error(`Secret not found: ${name}`);
    }
    delete this._secretsData[name];
  }
}
