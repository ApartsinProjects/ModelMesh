/**
 * Tutorial 5: AcmeCorp complete connector set -- all 6 connector types.
 *
 * Demonstrates building a full set of connectors for a hypothetical
 * "AcmeCorp" integration. Each connector uses a CDK base or specialized
 * class, showing how all six types work together.
 *
 * Connector types covered:
 * 1. Provider -- AcmeCorp's OpenAI-compatible inference API
 * 2. Rotation Policy -- threshold-based with AcmeCorp priority list
 * 3. Secret Store -- file-backed store for AcmeCorp credentials
 * 4. Storage -- key-value storage for state persistence
 * 5. Observability -- console output for development debugging
 * 6. Discovery -- HTTP health probes against AcmeCorp endpoints
 */

import {
    // Provider
    OpenAICompatibleProvider,
    BaseProviderConfig,
    ModelInfo,

    // Rotation
    ThresholdRotationPolicy,
    BaseRotationPolicyConfig,

    // Secret Store
    FileSecretStore,
    FileSecretStoreConfig,

    // Storage
    KeyValueStorage,
    KeyValueStorageConfig,
    StorageEntry,

    // Observability
    ConsoleObservability,
    BaseObservabilityConfig,
    RoutingEvent,
    RequestLogEntry,
    AggregateStats,
    EventType,

    // Discovery
    HttpHealthDiscovery,
    HttpHealthDiscoveryConfig,
    ProbeResult,

    // Helpers
    mockModelSnapshot,
    mockCompletionRequest,
} from "@modelmesh/cdk";

// -- 1. Provider ---------------------------------------------------------------

function createProvider(): OpenAICompatibleProvider {
    /** Create an AcmeCorp provider using the OpenAI-compatible format. */
    return new OpenAICompatibleProvider({
        baseUrl: "https://api.acmecorp.example.com",
        apiKey: "acme-api-key-placeholder",
        timeout: 30,
        maxRetries: 3,
        capabilities: ["generation.text-generation.chat-completion"],
        models: [
            {
                id: "acme-large",
                name: "AcmeCorp Large",
                capabilities: ["generation.text-generation.chat-completion"],
                features: { tool_calling: true },
                context_window: 64_000,
                max_output_tokens: 8_192,
            },
            {
                id: "acme-small",
                name: "AcmeCorp Small",
                capabilities: ["generation.text-generation.chat-completion"],
                context_window: 16_000,
                max_output_tokens: 4_096,
            },
        ],
    });
}

// -- 2. Rotation Policy --------------------------------------------------------

function createRotationPolicy(): ThresholdRotationPolicy {
    /** Create a threshold-based rotation policy with AcmeCorp priority. */
    return new ThresholdRotationPolicy({
        retryLimit: 5,
        errorRateThreshold: 0.3,
        cooldownSeconds: 120,
        budgetLimit: 50.0,
        modelPriority: ["acme-large", "acme-small"],
    });
}

// -- 3. Secret Store -----------------------------------------------------------

function createSecretStore(): FileSecretStore {
    /** Create a file-backed secret store for AcmeCorp credentials. */
    return new FileSecretStore({
        filePath: ".env",
        fileFormat: "dotenv",
        cacheTtlMs: 120_000,
        failOnMissing: false,
    });
}

// -- 4. Storage ----------------------------------------------------------------

function createStorage(): KeyValueStorage {
    /** Create a key-value storage for AcmeCorp state persistence. */
    return new KeyValueStorage({
        backend: "memory",
        format: "json",
        lockingEnabled: true,
    });
}

// -- 5. Observability ----------------------------------------------------------

function createObservability(): ConsoleObservability {
    /** Create a console observability connector for development. */
    return new ConsoleObservability({
        logLevel: "summary",
        redactSecrets: true,
        scopes: ["model", "provider"],
    });
}

// -- 6. Discovery --------------------------------------------------------------

function createDiscovery(): HttpHealthDiscovery {
    /** Create an HTTP health discovery connector for AcmeCorp. */
    const discovery = new HttpHealthDiscovery({
        providers: ["acmecorp"],
        healthPath: "/health",
        expectedStatus: 200,
        healthIntervalSeconds: 30,
        failureThreshold: 3,
    });
    discovery.registerProviderUrl(
        "acmecorp", "https://api.acmecorp.example.com"
    );
    return discovery;
}

// -- Main: Wire everything together --------------------------------------------

async function main(): Promise<void> {
    const provider = createProvider();
    const policy = createRotationPolicy();
    const secretStore = createSecretStore();
    const storage = createStorage();
    const obs = createObservability();
    const discovery = createDiscovery();

    console.log("=== AcmeCorp Connector Set ===\n");

    // Provider: list models
    const models: ModelInfo[] = await provider.listModels();
    console.log(`Provider models: ${JSON.stringify(models.map(m => m.id))}`);

    // Rotation: test deactivation
    const snapshot = mockModelSnapshot({
        modelId: "acme-large",
        providerId: "acmecorp",
        failureCount: 6,
        errorRate: 0.4,
    });
    console.log(`Should deactivate acme-large? ${policy.shouldDeactivate(snapshot)}`);

    // Storage: save and load state
    const entry: StorageEntry = {
        key: "acmecorp/state",
        data: new TextEncoder().encode('{"last_rotation": "2024-01-01T00:00:00Z"}'),
        metadata: { connector: "acmecorp" },
    };
    await storage.save("acmecorp/state", entry);
    const loaded = await storage.load("acmecorp/state");
    if (loaded) {
        console.log(`Storage load: ${new TextDecoder().decode(loaded.data)}`);
    }

    // Observability: emit event and log request
    obs.emit({
        event_type: EventType.MODEL_ACTIVATED,
        timestamp: new Date(),
        model_id: "acme-large",
        provider_id: "acmecorp",
    });
    obs.log({
        timestamp: new Date(),
        model_id: "acme-large",
        provider_id: "acmecorp",
        capability: "generation.text-generation.chat-completion",
        delivery_mode: "sync",
        latency_ms: 200.0,
        status_code: 200,
        tokens_in: 100,
        tokens_out: 250,
    });

    // Discovery: probe health
    const result: ProbeResult = await discovery.probe("acmecorp");
    console.log(`\nHealth probe: success=${result.success}`);

    // Clean up
    await provider.close();
    await discovery.close();

    console.log("\nAll 6 connectors created and exercised successfully.");
}

main().catch(console.error);
