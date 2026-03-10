/**
 * Ambient type declarations for browser-only APIs.
 *
 * The main tsconfig uses lib: ["ES2022"] without DOM. These declarations
 * provide TypeScript type information for browser storage APIs used by
 * browser-only connector classes (LocalStorageStorage, SessionStorageStorage,
 * IndexedDBStorage, BrowserSecretStore).
 *
 * At runtime, these globals are provided by the browser environment.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// -- Web Storage API --------------------------------------------------------

interface Storage {
  readonly length: number;
  clear(): void;
  getItem(key: string): string | null;
  key(index: number): string | null;
  removeItem(key: string): void;
  setItem(key: string, value: string): void;
}

declare var localStorage: Storage;
declare var sessionStorage: Storage;

// -- IndexedDB API ----------------------------------------------------------

interface IDBRequest<T = any> {
  readonly error: DOMException | null;
  onerror: ((this: IDBRequest<T>, ev: Event) => any) | null;
  onsuccess: ((this: IDBRequest<T>, ev: Event) => any) | null;
  readonly result: T;
}

interface IDBOpenDBRequest extends IDBRequest<IDBDatabase> {
  onupgradeneeded: ((this: IDBOpenDBRequest, ev: IDBVersionChangeEvent) => any) | null;
}

interface IDBVersionChangeEvent extends Event {
  readonly newVersion: number | null;
  readonly oldVersion: number;
}

interface IDBDatabase {
  readonly objectStoreNames: DOMStringList;
  close(): void;
  createObjectStore(name: string, options?: IDBObjectStoreParameters): IDBObjectStore;
  transaction(storeNames: string | string[], mode?: IDBTransactionMode): IDBTransaction;
}

interface IDBObjectStoreParameters {
  autoIncrement?: boolean;
  keyPath?: string | string[] | null;
}

type IDBTransactionMode = 'readonly' | 'readwrite' | 'versionchange';

interface IDBTransaction {
  objectStore(name: string): IDBObjectStore;
}

interface IDBObjectStore {
  put(value: any, key?: any): IDBRequest;
  get(key: any): IDBRequest;
  delete(key: any): IDBRequest;
  count(key?: any): IDBRequest<number>;
  openCursor(range?: any, direction?: string): IDBRequest<IDBCursorWithValue | null>;
}

interface IDBCursorWithValue {
  readonly key: any;
  readonly value: any;
  continue(): void;
}

interface DOMStringList {
  readonly length: number;
  contains(string: string): boolean;
  item(index: number): string | null;
}

interface IDBFactory {
  open(name: string, version?: number): IDBOpenDBRequest;
}

declare var indexedDB: IDBFactory;

// -- Base DOM types used in browser detection --------------------------------

declare var window: any;
declare var document: any;

// -- Encoding helpers (available in all modern environments) ------------------

declare function atob(data: string): string;
declare function btoa(data: string): string;
