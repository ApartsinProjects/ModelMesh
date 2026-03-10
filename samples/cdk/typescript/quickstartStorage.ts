/**
 * Quickstart: Create an in-memory storage and perform save/load/list/delete.
 *
 * Demonstrates the full CRUD cycle using a simple in-memory storage
 * implementation that conforms to the StorageConnector interface.
 *
 * For production use, implement a persistent backend (SQLite, Redis, etc.).
 * See samples/connectors/typescript/customStorage.ts for a full SQLite
 * implementation.
 */

import { StorageEntry } from "@modelmesh/core";

/**
 * Minimal in-memory storage for demonstration purposes.
 *
 * Implements the Persistence and Inventory sub-interfaces of
 * StorageConnector. A production connector would persist data to
 * disk, a database, or a cloud service.
 */
class InMemoryStorage {
    private store = new Map<string, StorageEntry>();

    async save(key: string, entry: StorageEntry): Promise<void> {
        this.store.set(key, entry);
    }

    async load(key: string): Promise<StorageEntry | null> {
        return this.store.get(key) ?? null;
    }

    async list(prefix?: string): Promise<string[]> {
        const keys = [...this.store.keys()];
        if (prefix) {
            return keys.filter(k => k.startsWith(prefix));
        }
        return keys;
    }

    async delete(key: string): Promise<boolean> {
        return this.store.delete(key);
    }
}

async function main(): Promise<void> {
    const storage = new InMemoryStorage();

    // Save
    const entry: StorageEntry = {
        key: "config/app-settings",
        data: Buffer.from('{"theme": "dark", "lang": "en"}'),
        metadata: { source: "quickstart" },
    };
    await storage.save("config/app-settings", entry);
    console.log("Saved entry.");

    // Load
    const loaded = await storage.load("config/app-settings");
    if (loaded) {
        const decoded = loaded.data.toString();
        console.log(`Loaded: ${decoded}`);
    }

    // List
    const keys = await storage.list("config/");
    console.log(`Keys: ${keys}`);

    // Delete
    const deleted = await storage.delete("config/app-settings");
    console.log(`Deleted: ${deleted}`);
}

main().catch(console.error);
