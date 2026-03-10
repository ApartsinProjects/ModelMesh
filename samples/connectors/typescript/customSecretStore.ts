/**
 * Custom Secret Store Connector — JSON File with Optional Encryption
 *
 * Demonstrates how to implement a custom secret store connector for ModelMesh Lite
 * that reads secrets from a JSON configuration file on disk. Secrets can be stored
 * in plaintext (for development) or encrypted with AES-256-GCM (for production).
 *
 * Implements both secret store sub-interfaces:
 *   - SecretResolution  : resolve secrets by name (required)
 *   - SecretManagement  : store, list, and delete secrets (optional, for CLI provisioning)
 *
 * Features:
 *   - In-memory cache with configurable TTL to avoid repeated disk reads
 *   - AES-256-GCM encryption/decryption using Node.js built-in crypto
 *   - Automatic file creation if the secrets file does not exist
 *   - Atomic writes to prevent corruption from concurrent access
 *
 * See: docs/interfaces/SecretStore.md
 */
// For a simpler CDK-based approach, see samples/cdk/typescript/

import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

// ---------------------------------------------------------------------------
// Types imported from @modelmesh/core (reproduced here for self-containment)
// ---------------------------------------------------------------------------

/** A resolved secret with optional version and expiration metadata. */
interface SecretValue {
    value: string;
    version?: string;
    expires_at?: Date;
}

// ---------------------------------------------------------------------------
// Secret store sub-interfaces (from docs/interfaces/SecretStore.md)
// ---------------------------------------------------------------------------

/** Retrieve a secret value by name. Required for all secret store connectors. */
interface SecretResolution {
    get(name: string): string;
}

/** Store, list, and remove secrets. Optional management interface. */
interface SecretManagement {
    set(name: string, value: string): void;
    list(): string[];
    delete(name: string): void;
}

/** Full secret store connector combining the required Resolution interface. */
interface SecretStoreConnector extends SecretResolution {}

// ---------------------------------------------------------------------------
// Configuration types
// ---------------------------------------------------------------------------

/** Configuration for the JSON file secret store. */
interface JsonSecretStoreConfig {
    /** Path to the JSON secrets file. */
    filePath: string;
    /** Whether secrets are encrypted in the file (default: false). */
    encrypted: boolean;
    /**
     * Encryption key as a hex-encoded 32-byte string.
     * Required when `encrypted` is true.
     * Generate with: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
     */
    encryptionKeyHex?: string;
    /** Cache TTL in milliseconds (default: 300000 = 5 minutes). */
    cacheTtlMs?: number;
    /** If true, throw an error when a requested secret is not found (default: true). */
    failOnMissing?: boolean;
}

/** Shape of the on-disk JSON secrets file. */
interface SecretsFileContent {
    /** Schema version for forward compatibility. */
    version: number;
    /** Map from secret name to stored value. */
    secrets: Record<string, StoredSecret>;
}

/** A single stored secret in the JSON file. */
interface StoredSecret {
    /** The secret value (plaintext or encrypted ciphertext in base64). */
    value: string;
    /** ISO 8601 timestamp of when this secret was last updated. */
    updatedAt: string;
    /** Optional version tag for audit tracking. */
    version?: string;
    /**
     * If encrypted, this holds the initialization vector as a hex string.
     * Absent when encryption is disabled.
     */
    iv?: string;
    /**
     * If encrypted, this holds the GCM authentication tag as a hex string.
     * Absent when encryption is disabled.
     */
    authTag?: string;
}

/** A cached secret entry with expiration tracking. */
interface CachedSecret {
    value: string;
    cachedAt: number; // timestamp in ms
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

class JsonFileSecretStore implements SecretStoreConnector, SecretManagement {
    private readonly filePath: string;
    private readonly encrypted: boolean;
    private readonly encryptionKey: Buffer | null;
    private readonly cacheTtlMs: number;
    private readonly failOnMissing: boolean;

    /** In-memory cache of resolved secrets, keyed by secret name. */
    private readonly cache = new Map<string, CachedSecret>();

    /** Encryption algorithm. AES-256-GCM provides authenticated encryption. */
    private static readonly ALGORITHM = "aes-256-gcm";
    /** IV length in bytes for AES-GCM (standard is 12 bytes / 96 bits). */
    private static readonly IV_LENGTH = 12;

    constructor(config: JsonSecretStoreConfig) {
        this.filePath = path.resolve(config.filePath);
        this.encrypted = config.encrypted;
        this.cacheTtlMs = config.cacheTtlMs ?? 300_000; // 5 minutes
        this.failOnMissing = config.failOnMissing ?? true;

        // Parse and validate the encryption key.
        if (this.encrypted) {
            if (!config.encryptionKeyHex) {
                throw new Error(
                    "encryptionKeyHex is required when encrypted=true. " +
                    'Generate one with: node -e "console.log(require(\'crypto\').randomBytes(32).toString(\'hex\'))"',
                );
            }
            this.encryptionKey = Buffer.from(config.encryptionKeyHex, "hex");
            if (this.encryptionKey.length !== 32) {
                throw new Error(
                    `Encryption key must be exactly 32 bytes (64 hex characters), got ${this.encryptionKey.length} bytes`,
                );
            }
        } else {
            this.encryptionKey = null;
        }

        // Ensure the secrets file exists. Create an empty one if it does not.
        this.ensureFileExists();
    }

    // -----------------------------------------------------------------------
    // SecretResolution (required)
    // -----------------------------------------------------------------------

    /**
     * Resolve a secret by name and return its plaintext value.
     *
     * First checks the in-memory cache. If the cached entry has not expired,
     * returns immediately. Otherwise reads from disk, decrypts if needed,
     * caches the result, and returns the value.
     *
     * @throws {Error} If the secret is not found and failOnMissing is true.
     */
    get(name: string): string {
        // Check cache first.
        const cached = this.cache.get(name);
        if (cached && Date.now() - cached.cachedAt < this.cacheTtlMs) {
            return cached.value;
        }

        // Load from disk.
        const fileContent = this.readSecretsFile();
        const stored = fileContent.secrets[name];

        if (!stored) {
            if (this.failOnMissing) {
                throw new Error(`Secret "${name}" not found in ${this.filePath}`);
            }
            return "";
        }

        // Decrypt if needed.
        const plaintext = this.encrypted
            ? this.decrypt(stored)
            : stored.value;

        // Update cache.
        this.cache.set(name, { value: plaintext, cachedAt: Date.now() });

        return plaintext;
    }

    // -----------------------------------------------------------------------
    // SecretManagement (optional)
    // -----------------------------------------------------------------------

    /**
     * Store or update a secret.
     *
     * Encrypts the value if encryption is enabled, then writes the updated
     * file atomically (write to temp file, then rename).
     */
    set(name: string, value: string): void {
        const fileContent = this.readSecretsFile();

        const stored: StoredSecret = this.encrypted
            ? this.encrypt(value)
            : {
                  value,
                  updatedAt: new Date().toISOString(),
                  version: this.generateVersion(),
              };

        fileContent.secrets[name] = stored;
        this.writeSecretsFile(fileContent);

        // Invalidate cache for this secret so the next get() picks up the new value.
        this.cache.delete(name);
    }

    /**
     * Return the names of all available secrets.
     *
     * Reads the secrets file and returns the keys. Does not decrypt values.
     */
    list(): string[] {
        const fileContent = this.readSecretsFile();
        return Object.keys(fileContent.secrets);
    }

    /**
     * Remove a secret by name.
     *
     * @throws {Error} If the secret does not exist.
     */
    delete(name: string): void {
        const fileContent = this.readSecretsFile();

        if (!(name in fileContent.secrets)) {
            throw new Error(`Secret "${name}" not found in ${this.filePath}`);
        }

        delete fileContent.secrets[name];
        this.writeSecretsFile(fileContent);

        // Remove from cache.
        this.cache.delete(name);
    }

    // -----------------------------------------------------------------------
    // Cache management (public utilities)
    // -----------------------------------------------------------------------

    /** Clear all cached secrets. Forces the next get() to read from disk. */
    clearCache(): void {
        this.cache.clear();
    }

    /** Return the number of currently cached secrets. */
    getCacheSize(): number {
        return this.cache.size;
    }

    // -----------------------------------------------------------------------
    // Private: Encryption / Decryption
    // -----------------------------------------------------------------------

    /**
     * Encrypt a plaintext value using AES-256-GCM.
     *
     * AES-GCM provides both confidentiality and authenticity. The IV is
     * generated randomly for each encryption and stored alongside the
     * ciphertext. The auth tag is also stored for verification on decryption.
     */
    private encrypt(plaintext: string): StoredSecret {
        if (!this.encryptionKey) {
            throw new Error("Cannot encrypt without an encryption key");
        }

        // Generate a random 12-byte IV for each encryption.
        const iv = crypto.randomBytes(JsonFileSecretStore.IV_LENGTH);

        const cipher = crypto.createCipheriv(
            JsonFileSecretStore.ALGORITHM,
            this.encryptionKey,
            iv,
        );

        let encrypted = cipher.update(plaintext, "utf8", "base64");
        encrypted += cipher.final("base64");

        const authTag = cipher.getAuthTag();

        return {
            value: encrypted,
            updatedAt: new Date().toISOString(),
            version: this.generateVersion(),
            iv: iv.toString("hex"),
            authTag: authTag.toString("hex"),
        };
    }

    /**
     * Decrypt a stored secret value using AES-256-GCM.
     *
     * Reads the IV and auth tag from the stored secret, then decrypts
     * the ciphertext. Throws if the auth tag verification fails (indicating
     * tampering or a wrong key).
     */
    private decrypt(stored: StoredSecret): string {
        if (!this.encryptionKey) {
            throw new Error("Cannot decrypt without an encryption key");
        }
        if (!stored.iv || !stored.authTag) {
            throw new Error(
                "Stored secret is missing iv or authTag — was it encrypted with a different method?",
            );
        }

        const iv = Buffer.from(stored.iv, "hex");
        const authTag = Buffer.from(stored.authTag, "hex");

        const decipher = crypto.createDecipheriv(
            JsonFileSecretStore.ALGORITHM,
            this.encryptionKey,
            iv,
        );
        decipher.setAuthTag(authTag);

        let decrypted = decipher.update(stored.value, "base64", "utf8");
        decrypted += decipher.final("utf8");

        return decrypted;
    }

    // -----------------------------------------------------------------------
    // Private: File I/O
    // -----------------------------------------------------------------------

    /** Read and parse the secrets JSON file. */
    private readSecretsFile(): SecretsFileContent {
        const raw = fs.readFileSync(this.filePath, "utf8");
        const parsed = JSON.parse(raw);

        // Basic schema validation.
        if (typeof parsed.version !== "number" || typeof parsed.secrets !== "object") {
            throw new Error(
                `Invalid secrets file format at ${this.filePath}. Expected { version: number, secrets: {} }`,
            );
        }

        return parsed as SecretsFileContent;
    }

    /**
     * Write the secrets file atomically.
     *
     * Writes to a temporary file first, then renames it to the target path.
     * This prevents partial writes from corrupting the file if the process
     * crashes mid-write.
     */
    private writeSecretsFile(content: SecretsFileContent): void {
        const json = JSON.stringify(content, null, 2);
        const tempPath = this.filePath + ".tmp";

        fs.writeFileSync(tempPath, json, "utf8");
        fs.renameSync(tempPath, this.filePath);
    }

    /** Create the secrets file with an empty structure if it does not exist. */
    private ensureFileExists(): void {
        if (!fs.existsSync(this.filePath)) {
            const dir = path.dirname(this.filePath);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }

            const initial: SecretsFileContent = {
                version: 1,
                secrets: {},
            };
            fs.writeFileSync(this.filePath, JSON.stringify(initial, null, 2), "utf8");
        }
    }

    /**
     * Generate a short version string for audit tracking.
     *
     * Uses a timestamp + random suffix to create a human-readable version.
     */
    private generateVersion(): string {
        const timestamp = Date.now().toString(36);
        const random = crypto.randomBytes(3).toString("hex");
        return `v${timestamp}-${random}`;
    }
}

// ---------------------------------------------------------------------------
// YAML configuration example
// ---------------------------------------------------------------------------

/*
# modelmesh.yaml — secret store section for the JSON file connector
#
# secret-store:
#   connector: custom
#   connector_class: JsonFileSecretStore
#   config:
#     file_path: "./secrets/api-keys.json"
#     encrypted: true
#     encryption_key_hex: "${env:MODELMESH_SECRET_KEY}"   # 64 hex chars
#     cache_ttl_ms: 300000      # 5 minutes
#     fail_on_missing: true
#   resolution:
#     cache_enabled: true       # built-in cache (in addition to connector cache)
#     cache_ttl: 300s
#     reload_on_rotation: true
#     fail_on_missing: true
#
# The secrets JSON file structure (secrets/api-keys.json):
#
# {
#   "version": 1,
#   "secrets": {
#     "openai-key": {
#       "value": "sk-abc123...",            // plaintext if encrypted=false
#       "updatedAt": "2025-01-15T10:30:00Z",
#       "version": "vlq2f8k-a1b2c3"
#     },
#     "anthropic-key": {
#       "value": "base64-encrypted-value",  // ciphertext if encrypted=true
#       "updatedAt": "2025-01-15T10:30:00Z",
#       "version": "vlq2f8k-d4e5f6",
#       "iv": "0a1b2c3d4e5f6a7b8c9d0e1f",
#       "authTag": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
#     }
#   }
# }
*/

export { JsonFileSecretStore };
export type {
    JsonSecretStoreConfig,
    SecretsFileContent,
    StoredSecret,
    SecretValue,
    SecretResolution,
    SecretManagement,
    SecretStoreConnector,
};
