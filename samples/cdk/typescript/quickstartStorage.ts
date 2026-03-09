/**
 * Quickstart: Create a KeyValueStorage and perform save/load/list/delete.
 *
 * Demonstrates the full CRUD cycle using the in-memory backend of the
 * KeyValueStorage specialized class.
 */

import { KeyValueStorage, KeyValueStorageConfig, StorageEntry } from "@modelmesh/cdk";

async function main(): Promise<void> {
    const storage = new KeyValueStorage({
        backend: "memory",
        format: "json",
    });

    // Save
    const entry: StorageEntry = {
        key: "config/app-settings",
        data: new TextEncoder().encode('{"theme": "dark", "lang": "en"}'),
        metadata: { source: "quickstart" },
    };
    await storage.save("config/app-settings", entry);
    console.log("Saved entry.");

    // Load
    const loaded = await storage.load("config/app-settings");
    if (loaded) {
        const decoded = new TextDecoder().decode(loaded.data);
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
