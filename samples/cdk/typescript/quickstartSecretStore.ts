/**
 * Quickstart: Create a BaseSecretStore and resolve a key.
 *
 * Demonstrates reading secrets from an in-memory store using the
 * BaseSecretStore CDK class. For file-based secret stores or vault
 * integrations, subclass BaseSecretStore and override the _resolve()
 * method. See samples/connectors/typescript/customSecretStore.ts for
 * a full file-backed implementation.
 */

import { BaseSecretStore, BaseSecretStoreConfig } from "@modelmesh/core";

function main(): void {
    // Create a secret store with inline secrets (for development).
    // In production, subclass BaseSecretStore and override _resolve()
    // to read from .env files, AWS Secrets Manager, HashiCorp Vault, etc.
    const store = new BaseSecretStore({
        secrets: {
            "OPENAI_API_KEY": "sk-your-api-key-here",
            "ANTHROPIC_API_KEY": "sk-ant-your-key-here",
        },
        cacheEnabled: true,
        cacheTtlMs: 60_000,
        failOnMissing: true,
    });

    try {
        const apiKey = store.get("OPENAI_API_KEY");
        console.log(`Resolved API key: ${apiKey.slice(0, 8)}...`);
    } catch (err) {
        console.log(`Secret not found: ${err}`);
    }

    // Clear the cache to force re-resolution on next get()
    store.clearCache();
    console.log("Cache cleared.");
}

main();
