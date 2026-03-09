/**
 * Quickstart: Create a FileSecretStore and resolve a key from a .env file.
 *
 * Demonstrates reading secrets from a dotenv file using the FileSecretStore
 * specialized class with caching enabled.
 */

import { FileSecretStore, FileSecretStoreConfig } from "@modelmesh/cdk";

function main(): void {
    const store = new FileSecretStore({
        filePath: ".env",
        fileFormat: "dotenv",
        cacheTtlMs: 60_000,
        failOnMissing: true,
    });

    try {
        const apiKey = store.get("OPENAI_API_KEY");
        console.log(`Resolved API key: ${apiKey.slice(0, 8)}...`);
    } catch (err) {
        console.log(`Secret not found: ${err}`);
    }
}

main();
