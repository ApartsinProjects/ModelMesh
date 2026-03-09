/**
 * Custom Storage Connector — SQLite Backend (via better-sqlite3)
 *
 * Demonstrates how to implement a custom storage connector for ModelMesh Lite
 * using SQLite as the persistence backend. SQLite is an excellent choice for
 * single-instance deployments or embedded scenarios where a full database
 * server is not warranted.
 *
 * Implements all four storage sub-interfaces:
 *   - Persistence : read and write serialized data
 *   - Inventory   : enumerate and remove stored entries
 *   - StatQuery   : query metadata without loading full content
 *   - Locking     : advisory locking using database rows
 *
 * See: docs/interfaces/Storage.md
 */
// For a simpler CDK-based approach, see samples/cdk/typescript/

// ---------------------------------------------------------------------------
// Types imported from modelmesh-lite (reproduced here for self-containment)
// ---------------------------------------------------------------------------

/** Controls when storage persistence occurs. */
enum SyncPolicy {
    IN_MEMORY = "in-memory",
    SYNC_ON_BOUNDARY = "sync-on-boundary",
    PERIODIC = "periodic",
    IMMEDIATE = "immediate",
}

/** Serialization format for stored data. */
enum SerializationFormat {
    JSON = "json",
    YAML = "yaml",
    MSGPACK = "msgpack",
}

/** A single stored data entry with its raw content and metadata. */
interface StorageEntry {
    key: string;
    data: Uint8Array;
    metadata: Record<string, unknown>;
}

/** Metadata about a stored entry, without the full content. */
interface EntryMetadata {
    key: string;
    size: number;
    last_modified: Date;
    content_type?: string;
}

/** Handle representing an acquired advisory lock on a stored entry. */
interface LockHandle {
    key: string;
    lock_id: string;
    acquired_at: Date;
    expires_at?: Date;
}

// ---------------------------------------------------------------------------
// Storage sub-interfaces (from docs/interfaces/Storage.md)
// ---------------------------------------------------------------------------

interface Persistence {
    load(key: string): Promise<StorageEntry | null>;
    save(key: string, entry: StorageEntry): Promise<void>;
}

interface Inventory {
    list(prefix?: string): Promise<string[]>;
    delete(key: string): Promise<boolean>;
}

interface StatQuery {
    stat(key: string): Promise<EntryMetadata | null>;
    exists(key: string): Promise<boolean>;
}

interface Locking {
    acquire(key: string, timeout?: number): Promise<LockHandle>;
    release(lock: LockHandle): Promise<void>;
    isLocked(key: string): Promise<boolean>;
}

interface StorageConnector extends Persistence, Inventory, StatQuery {}

// ---------------------------------------------------------------------------
// better-sqlite3 type declarations (minimal subset used by this connector)
// ---------------------------------------------------------------------------

/**
 * Minimal type declarations for better-sqlite3.
 *
 * In a real project, install @types/better-sqlite3 for full type coverage.
 * These declarations cover only the API surface used by this connector.
 */
interface BetterSqlite3Database {
    prepare(sql: string): BetterSqlite3Statement;
    exec(sql: string): void;
    close(): void;
    pragma(pragma: string): unknown;
    transaction<T>(fn: (...args: unknown[]) => T): (...args: unknown[]) => T;
}

interface BetterSqlite3Statement {
    run(...params: unknown[]): { changes: number; lastInsertRowid: number | bigint };
    get(...params: unknown[]): Record<string, unknown> | undefined;
    all(...params: unknown[]): Record<string, unknown>[];
}

// Placeholder for the require call. In a real project, use:
//   import Database from "better-sqlite3";
declare function require(module: string): unknown;
const Database = require("better-sqlite3") as new (
    filename: string,
    options?: Record<string, unknown>,
) => BetterSqlite3Database;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Configuration for the SQLite storage connector. */
interface SqliteStorageConfig {
    /** Path to the SQLite database file (e.g. "./data/modelmesh.db"). */
    dbPath: string;
    /** Enable WAL mode for better concurrent read performance (default: true). */
    walMode?: boolean;
    /** Lock expiration in seconds. Expired locks are auto-released (default: 30). */
    lockExpirationSeconds?: number;
    /** Lock acquisition retry interval in milliseconds (default: 100). */
    lockRetryIntervalMs?: number;
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

import * as crypto from "node:crypto";

class SqliteStorageConnector implements StorageConnector, Locking {
    private readonly db: BetterSqlite3Database;
    private readonly lockExpirationSeconds: number;
    private readonly lockRetryIntervalMs: number;

    // Prepared statements (created once, reused for performance).
    private readonly stmtLoad: BetterSqlite3Statement;
    private readonly stmtSave: BetterSqlite3Statement;
    private readonly stmtList: BetterSqlite3Statement;
    private readonly stmtListWithPrefix: BetterSqlite3Statement;
    private readonly stmtDelete: BetterSqlite3Statement;
    private readonly stmtStat: BetterSqlite3Statement;
    private readonly stmtExists: BetterSqlite3Statement;
    private readonly stmtAcquireLock: BetterSqlite3Statement;
    private readonly stmtReleaseLock: BetterSqlite3Statement;
    private readonly stmtCheckLock: BetterSqlite3Statement;
    private readonly stmtCleanExpiredLocks: BetterSqlite3Statement;

    constructor(config: SqliteStorageConfig) {
        this.lockExpirationSeconds = config.lockExpirationSeconds ?? 30;
        this.lockRetryIntervalMs = config.lockRetryIntervalMs ?? 100;

        // Open (or create) the SQLite database.
        this.db = new Database(config.dbPath);

        // Enable WAL mode for better read concurrency.
        if (config.walMode !== false) {
            this.db.pragma("journal_mode = WAL");
        }

        // Set a reasonable busy timeout (5 seconds).
        this.db.pragma("busy_timeout = 5000");

        // Create tables if they do not exist.
        this.initializeSchema();

        // Prepare all statements up front.
        this.stmtLoad = this.db.prepare(`
            SELECT key, data, metadata, content_type
            FROM storage_entries
            WHERE key = ?
        `);

        this.stmtSave = this.db.prepare(`
            INSERT INTO storage_entries (key, data, metadata, content_type, size, last_modified)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                data = excluded.data,
                metadata = excluded.metadata,
                content_type = excluded.content_type,
                size = excluded.size,
                last_modified = excluded.last_modified
        `);

        this.stmtList = this.db.prepare(`
            SELECT key FROM storage_entries ORDER BY key
        `);

        this.stmtListWithPrefix = this.db.prepare(`
            SELECT key FROM storage_entries WHERE key LIKE ? ORDER BY key
        `);

        this.stmtDelete = this.db.prepare(`
            DELETE FROM storage_entries WHERE key = ?
        `);

        this.stmtStat = this.db.prepare(`
            SELECT key, size, last_modified, content_type
            FROM storage_entries
            WHERE key = ?
        `);

        this.stmtExists = this.db.prepare(`
            SELECT 1 FROM storage_entries WHERE key = ?
        `);

        this.stmtAcquireLock = this.db.prepare(`
            INSERT INTO advisory_locks (key, lock_id, acquired_at, expires_at)
            VALUES (?, ?, ?, ?)
        `);

        this.stmtReleaseLock = this.db.prepare(`
            DELETE FROM advisory_locks WHERE key = ? AND lock_id = ?
        `);

        this.stmtCheckLock = this.db.prepare(`
            SELECT lock_id, acquired_at, expires_at
            FROM advisory_locks
            WHERE key = ? AND expires_at > ?
        `);

        this.stmtCleanExpiredLocks = this.db.prepare(`
            DELETE FROM advisory_locks WHERE expires_at <= ?
        `);
    }

    // -----------------------------------------------------------------------
    // Persistence
    // -----------------------------------------------------------------------

    /**
     * Load a stored entry by key.
     *
     * Returns null if the key does not exist in the database.
     * The data column stores the raw bytes as a SQLite BLOB, and the
     * metadata column stores a JSON-serialized object.
     */
    async load(key: string): Promise<StorageEntry | null> {
        const row = this.stmtLoad.get(key);
        if (!row) return null;

        return {
            key,
            data: new Uint8Array(row.data as Buffer),
            metadata: JSON.parse(row.metadata as string),
        };
    }

    /**
     * Save an entry under the given key.
     *
     * Uses an UPSERT (INSERT ... ON CONFLICT DO UPDATE) to atomically
     * insert or overwrite the entry. Metadata is serialized to JSON.
     * Size and last_modified are computed automatically.
     */
    async save(key: string, entry: StorageEntry): Promise<void> {
        const metadataJson = JSON.stringify(entry.metadata);
        const contentType =
            (entry.metadata.content_type as string) ?? "application/octet-stream";
        const size = entry.data.byteLength;
        const lastModified = new Date().toISOString();

        this.stmtSave.run(
            key,
            Buffer.from(entry.data),
            metadataJson,
            contentType,
            size,
            lastModified,
        );
    }

    // -----------------------------------------------------------------------
    // Inventory
    // -----------------------------------------------------------------------

    /**
     * Return keys matching the optional prefix, or all keys if omitted.
     *
     * Uses a LIKE clause with the prefix as a starts-with filter.
     */
    async list(prefix?: string): Promise<string[]> {
        let rows: Record<string, unknown>[];

        if (prefix !== undefined && prefix !== null) {
            // Escape any existing '%' or '_' characters in the prefix
            // to prevent them from being treated as wildcards.
            const escaped = prefix.replace(/%/g, "\\%").replace(/_/g, "\\_");
            rows = this.stmtListWithPrefix.all(`${escaped}%`);
        } else {
            rows = this.stmtList.all();
        }

        return rows.map((r) => r.key as string);
    }

    /**
     * Delete the entry at the given key.
     *
     * Returns true if a row was actually deleted, false if the key
     * did not exist.
     */
    async delete(key: string): Promise<boolean> {
        const result = this.stmtDelete.run(key);
        return result.changes > 0;
    }

    // -----------------------------------------------------------------------
    // StatQuery
    // -----------------------------------------------------------------------

    /**
     * Return metadata for the given key without loading the full data blob.
     *
     * This is efficient for cache validation: the caller can check the
     * last_modified timestamp or size without transferring the payload.
     */
    async stat(key: string): Promise<EntryMetadata | null> {
        const row = this.stmtStat.get(key);
        if (!row) return null;

        return {
            key: row.key as string,
            size: row.size as number,
            last_modified: new Date(row.last_modified as string),
            content_type: (row.content_type as string) ?? undefined,
        };
    }

    /** Return true if an entry exists at the given key. */
    async exists(key: string): Promise<boolean> {
        const row = this.stmtExists.get(key);
        return row !== undefined;
    }

    // -----------------------------------------------------------------------
    // Locking
    // -----------------------------------------------------------------------

    /**
     * Acquire an advisory lock on the given key.
     *
     * Advisory locks are implemented as rows in the `advisory_locks` table.
     * A lock is considered held if a non-expired row exists for the key.
     * This method retries until the lock is acquired or the timeout expires.
     *
     * @param key     The storage key to lock.
     * @param timeout Maximum seconds to wait. Undefined means wait up to 30s.
     * @throws {Error} If the lock cannot be acquired within the timeout.
     */
    async acquire(key: string, timeout?: number): Promise<LockHandle> {
        const timeoutMs = (timeout ?? this.lockExpirationSeconds) * 1000;
        const deadline = Date.now() + timeoutMs;
        const lockId = crypto.randomUUID();
        const now = new Date();
        const expiresAt = new Date(now.getTime() + this.lockExpirationSeconds * 1000);

        while (Date.now() < deadline) {
            // Clean up any expired locks for this key first.
            this.stmtCleanExpiredLocks.run(new Date().toISOString());

            // Try to insert the lock row. If a non-expired lock exists,
            // the UNIQUE constraint on `key` will cause the insert to fail.
            try {
                this.stmtAcquireLock.run(
                    key,
                    lockId,
                    now.toISOString(),
                    expiresAt.toISOString(),
                );

                return {
                    key,
                    lock_id: lockId,
                    acquired_at: now,
                    expires_at: expiresAt,
                };
            } catch (err: unknown) {
                // If the insert failed due to a conflict, another lock is held.
                // Wait and retry.
                const message = err instanceof Error ? err.message : String(err);
                if (message.includes("UNIQUE constraint failed")) {
                    await this.sleep(this.lockRetryIntervalMs);
                    continue;
                }
                // Re-throw unexpected errors.
                throw err;
            }
        }

        throw new Error(
            `Timeout: could not acquire lock on key "${key}" within ${timeoutMs}ms`,
        );
    }

    /**
     * Release a previously acquired lock.
     *
     * Deletes the lock row matching both the key and the lock_id to prevent
     * accidentally releasing a lock that was re-acquired by another process.
     */
    async release(lock: LockHandle): Promise<void> {
        this.stmtReleaseLock.run(lock.key, lock.lock_id);
    }

    /**
     * Return true if the given key is currently locked.
     *
     * Checks for a non-expired lock row.
     */
    async isLocked(key: string): Promise<boolean> {
        const now = new Date().toISOString();
        const row = this.stmtCheckLock.get(key, now);
        return row !== undefined;
    }

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------

    /**
     * Gracefully close the database connection.
     *
     * Should be called when the application shuts down. After close(), all
     * prepared statements become invalid and further calls will throw.
     */
    close(): void {
        this.db.close();
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    /** Create the storage and locking tables if they do not exist. */
    private initializeSchema(): void {
        this.db.exec(`
            CREATE TABLE IF NOT EXISTS storage_entries (
                key           TEXT PRIMARY KEY,
                data          BLOB NOT NULL,
                metadata      TEXT NOT NULL DEFAULT '{}',
                content_type  TEXT DEFAULT 'application/octet-stream',
                size          INTEGER NOT NULL DEFAULT 0,
                last_modified TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_storage_entries_key
                ON storage_entries(key);

            CREATE TABLE IF NOT EXISTS advisory_locks (
                key         TEXT PRIMARY KEY,
                lock_id     TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                expires_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_advisory_locks_expires
                ON advisory_locks(expires_at);
        `);
    }

    /** Promise-based sleep for retry loops. */
    private sleep(ms: number): Promise<void> {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }
}

// ---------------------------------------------------------------------------
// YAML configuration example
// ---------------------------------------------------------------------------

/*
# modelmesh.yaml — storage section for the SQLite connector
#
# storage:
#   connector: custom
#   connector_class: SqliteStorageConnector
#   config:
#     db_path: "./data/modelmesh.db"
#     wal_mode: true
#     lock_expiration_seconds: 30
#     lock_retry_interval_ms: 100
#   persistence:
#     sync_policy: immediate       # write-through to SQLite on every change
#     format: json                 # serialize state/config as JSON blobs
#     compression: false
#     encryption: false
#   locking:
#     enabled: true
#     timeout: 30s
#     retry_interval: 100ms
*/

export { SqliteStorageConnector };
export type {
    SqliteStorageConfig,
    StorageConnector,
    Persistence,
    Inventory,
    StatQuery,
    Locking,
    StorageEntry,
    EntryMetadata,
    LockHandle,
};
