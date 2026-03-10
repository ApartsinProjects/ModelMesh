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
 * 3. Secret Store -- in-memory store for AcmeCorp credentials
 * 4. Storage -- in-memory key-value storage for state persistence
 * 5. Observability -- console output for development debugging
 * 6. Discovery -- health probing against AcmeCorp endpoints
 *
 * NOTE: This sample uses the CDK base classes and interfaces exported from
 * @nistrapa/modelmesh-core. For fully custom implementations (implementing interfaces
 * directly), see the samples/connectors/typescript/ directory.
 */

import {
    // Provider
    OpenAICompatibleProvider,
    BaseProviderConfig,
    ModelInfo,
    createDefaultModelInfo,

    // Rotation
    BaseRotationPolicy,
    BaseRotationConfig,
    ModelState,
    createDefaultModelState,

    // Secret Store
    BaseSecretStore,
    BaseSecretStoreConfig,

    // Storage
    StorageEntry,

    // Observability
    RoutingEvent,
    RequestLogEntry,
    AggregateStats,
    EventType,
    ObservabilityConnector,
    Severity,
    TraceEntry,

    // Discovery
    ProbeResult,
    HealthReport,
    DiscoveryConnector,
    SyncResult,
    SyncStatus,
} from "@nistrapa/modelmesh-core";

// -- 1. Provider ---------------------------------------------------------------

function createProvider(): OpenAICompatibleProvider {
    /** Create an AcmeCorp provider using the OpenAI-compatible format. */
    return new OpenAICompatibleProvider({
        baseUrl: "https://api.acmecorp.example.com",
        apiKey: "acme-api-key-placeholder",
        timeout: 30,
        maxRetries: 3,
        authMethod: "api_key",
        retryableCodes: [429, 500, 502, 503],
        nonRetryableCodes: [400, 401, 403],
        capabilities: ["generation.text-generation.chat-completion"],
        models: [
            createDefaultModelInfo({
                id: "acme-large",
                name: "AcmeCorp Large",
                capabilities: ["generation.text-generation.chat-completion"],
                features: { tool_calling: true },
                contextWindow: 64_000,
                maxOutputTokens: 8_192,
            }),
            createDefaultModelInfo({
                id: "acme-small",
                name: "AcmeCorp Small",
                capabilities: ["generation.text-generation.chat-completion"],
                contextWindow: 16_000,
                maxOutputTokens: 4_096,
            }),
        ],
    });
}

// -- 2. Rotation Policy --------------------------------------------------------

function createRotationPolicy(): BaseRotationPolicy {
    /** Create a threshold-based rotation policy with AcmeCorp priority. */
    return new BaseRotationPolicy({
        failureThreshold: 5,
        errorRateThreshold: 0.3,
        cooldownSeconds: 120,
        budgetLimit: 50.0,
        modelPriority: ["acme-large", "acme-small"],
    });
}

// -- 3. Secret Store -----------------------------------------------------------

function createSecretStore(): BaseSecretStore {
    /** Create an in-memory secret store for AcmeCorp credentials. */
    return new BaseSecretStore({
        secrets: {
            "ACME_API_KEY": "acme-api-key-placeholder",
            "ACME_SECRET": "acme-secret-placeholder",
        },
        cacheEnabled: true,
        cacheTtlMs: 120_000,
        failOnMissing: false,
    });
}

// -- 4. Storage (inline in-memory implementation) ------------------------------

/**
 * Simple in-memory storage implementing the StorageConnector interface.
 *
 * For production use, consider SQLite, Redis, or a cloud-based storage
 * solution. See samples/connectors/typescript/customStorage.ts for a
 * full SQLite implementation.
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

function createStorage(): InMemoryStorage {
    return new InMemoryStorage();
}

// -- 5. Observability (inline console implementation) --------------------------

/**
 * Console-based observability connector for development debugging.
 *
 * Prints routing events, request logs, and statistics to the console.
 * For production use, consider sending events to Slack, Datadog, or a
 * structured logging service. See samples/connectors/typescript/
 * customObservability.ts for a full Slack + JSON file implementation.
 */
class ConsoleObservabilityConnector implements ObservabilityConnector {
    emit(event: RoutingEvent): void {
        console.log(`[EVENT] ${event.eventType} model=${event.modelId ?? "n/a"} provider=${event.providerId ?? "n/a"}`);
    }

    log(entry: RequestLogEntry): void {
        console.log(
            `[LOG] model=${entry.modelId} provider=${entry.providerId} ` +
            `latency=${entry.latencyMs}ms status=${entry.statusCode} ` +
            `tokens=${entry.tokensIn}/${entry.tokensOut}`
        );
    }

    flush(stats: Record<string, AggregateStats>): void {
        for (const [scope, s] of Object.entries(stats)) {
            console.log(`[STATS] ${scope}: requests=${s.requestsTotal} success=${s.requestsSuccess} cost=$${s.costTotal.toFixed(4)}`);
        }
    }

    trace(entry: TraceEntry): void {
        console.log(`[TRACE] [${entry.severity}] ${entry.component}: ${entry.message}`);
    }
}

function createObservability(): ConsoleObservabilityConnector {
    return new ConsoleObservabilityConnector();
}

// -- 6. Discovery (inline health probe implementation) -------------------------

/**
 * Simple HTTP health probe discovery connector.
 *
 * For a full implementation with YAML registry sync and rolling
 * availability scores, see samples/connectors/typescript/
 * customDiscovery.ts.
 */
class SimpleHealthDiscovery implements DiscoveryConnector {
    private endpoints = new Map<string, string>();

    registerProviderUrl(providerId: string, baseUrl: string): void {
        this.endpoints.set(providerId, baseUrl);
    }

    async sync(_providers?: string[]): Promise<SyncResult> {
        return { newModels: [], deprecatedModels: [], updatedModels: [], errors: [] };
    }

    async getSyncStatus(): Promise<SyncStatus> {
        return { modelsSynced: 0, status: "idle" };
    }

    async probe(providerId: string): Promise<ProbeResult> {
        const baseUrl = this.endpoints.get(providerId);
        if (!baseUrl) {
            return { providerId, success: false, error: `Unknown provider: ${providerId}` };
        }
        // In a real implementation, make an HTTP GET to the health endpoint.
        // For this sample, we return a simulated result.
        return { providerId, success: true, latencyMs: 42.5, statusCode: 200 };
    }

    async getHealthReport(providerId?: string): Promise<HealthReport[]> {
        const ids = providerId ? [providerId] : [...this.endpoints.keys()];
        return ids.map(id => ({
            providerId: id,
            available: true,
            availabilityScore: 1.0,
            timestamp: new Date(),
        }));
    }
}

function createDiscovery(): SimpleHealthDiscovery {
    const discovery = new SimpleHealthDiscovery();
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
    const models: ModelInfo[] = provider.listModels();
    console.log(`Provider models: ${JSON.stringify(models.map(m => m.id))}`);

    // Rotation: test deactivation
    const state = createDefaultModelState({
        modelId: "acme-large",
        providerId: "acmecorp",
        failureCount: 6,
    });
    console.log(`Should deactivate acme-large? ${policy.shouldDeactivate(state)}`);

    // Storage: save and load state
    const entry: StorageEntry = {
        key: "acmecorp/state",
        data: Buffer.from('{"last_rotation": "2024-01-01T00:00:00Z"}'),
        metadata: { connector: "acmecorp" },
    };
    await storage.save("acmecorp/state", entry);
    const loaded = await storage.load("acmecorp/state");
    if (loaded) {
        console.log(`Storage load: ${loaded.data.toString()}`);
    }

    // Secret Store: resolve a secret
    const secret = secretStore.get("ACME_API_KEY");
    console.log(`Secret resolved: ${secret.slice(0, 8)}...`);

    // Observability: emit event and log request
    obs.emit({
        eventType: EventType.MODEL_ACTIVATED,
        timestamp: new Date(),
        modelId: "acme-large",
        providerId: "acmecorp",
        metadata: {},
    });
    obs.log({
        timestamp: new Date(),
        modelId: "acme-large",
        providerId: "acmecorp",
        capability: "generation.text-generation.chat-completion",
        deliveryMode: "sync",
        latencyMs: 200.0,
        statusCode: 200,
        tokensIn: 100,
        tokensOut: 250,
    });

    // Discovery: probe health
    const result: ProbeResult = await discovery.probe("acmecorp");
    console.log(`\nHealth probe: success=${result.success}`);

    // Clean up
    await provider.close();

    console.log("\nAll 6 connectors created and exercised successfully.");
}

main().catch(console.error);
