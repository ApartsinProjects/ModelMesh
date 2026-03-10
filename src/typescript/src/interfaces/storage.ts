/**
 * Storage connector interface and associated data types.
 *
 * Defines the StorageConnector interface for serializing and
 * deserializing library data to an external backend.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export enum SyncPolicy {
  IN_MEMORY = 'in-memory',
  SYNC_ON_BOUNDARY = 'sync-on-boundary',
  PERIODIC = 'periodic',
  IMMEDIATE = 'immediate',
}

export enum SerializationFormat {
  JSON = 'json',
  YAML = 'yaml',
  MSGPACK = 'msgpack',
}

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

export interface StorageEntry {
  key: string;
  data: Buffer;
  metadata: Record<string, unknown>;
}

export interface EntryMetadata {
  key: string;
  size: number;
  lastModified: Date;
  contentType?: string;
}

export interface LockHandle {
  key: string;
  lockId: string;
  acquiredAt: Date;
  expiresAt?: Date;
}

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface Persistence {
  load(key: string): Promise<StorageEntry | null>;
  save(key: string, entry: StorageEntry): Promise<void>;
}

export interface Inventory {
  list(prefix?: string): Promise<string[]>;
  delete(key: string): Promise<boolean>;
}

export interface StatQuery {
  stat(key: string): Promise<EntryMetadata | null>;
  exists(key: string): Promise<boolean>;
}

export interface Locking {
  acquire(key: string, timeout?: number): Promise<LockHandle>;
  release(lock: LockHandle): Promise<void>;
  isLocked(key: string): Promise<boolean>;
}

export interface StorageConnector extends Persistence, Inventory, StatQuery {}
