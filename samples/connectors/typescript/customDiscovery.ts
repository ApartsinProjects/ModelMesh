/**
 * Custom Discovery Connector — YAML Registry + HTTP Health Probes
 *
 * Demonstrates how to implement a custom discovery connector for ModelMesh Lite
 * that synchronizes model definitions from a YAML registry file and monitors
 * provider health by sending HTTP ping requests to their endpoints.
 *
 * This connector is designed for environments where model definitions are
 * managed in version-controlled YAML files (e.g., in a Git repository) and
 * providers expose a health or readiness endpoint.
 *
 * Implements both required discovery sub-interfaces:
 *   - RegistrySync      : sync model catalogue from a YAML file
 *   - HealthMonitoring  : probe provider endpoints and compute availability scores
 *
 * See: docs/interfaces/Discovery.md
 */
// For a simpler CDK-based approach, see samples/cdk/typescript/

import * as fs from "node:fs";
import * as path from "node:path";

// ---------------------------------------------------------------------------
// Types imported from @modelmesh/core (reproduced here for self-containment)
// ---------------------------------------------------------------------------

/** Action to take when a new model is discovered during sync. */
enum SyncAction {
    REGISTER = "register",
    NOTIFY = "notify",
    IGNORE = "ignore",
}

/** Action to take when a model is detected as deprecated. */
enum DeprecationAction {
    DEACTIVATE = "deactivate",
    NOTIFY = "notify",
    IGNORE = "ignore",
}

/** Outcome of a registry synchronization run. */
interface SyncResult {
    new_models: string[];
    deprecated_models: string[];
    updated_models: string[];
    errors: string[];
}

/** Current status of the registry synchronization process. */
interface SyncStatus {
    last_sync?: Date;
    next_sync?: Date;
    models_synced: number;
    status: string;
}

/** Health assessment for a single provider over a monitoring window. */
interface HealthReport {
    provider_id: string;
    available: boolean;
    latency_ms?: number;
    status_code?: number;
    error?: string;
    availability_score: number;
    timestamp: Date;
}

/** Result of a single health probe against a provider. */
interface ProbeResult {
    provider_id: string;
    success: boolean;
    latency_ms?: number;
    status_code?: number;
    error?: string;
}

// ---------------------------------------------------------------------------
// Discovery sub-interfaces (from docs/interfaces/Discovery.md)
// ---------------------------------------------------------------------------

interface RegistrySync {
    sync(providers?: string[]): Promise<SyncResult>;
    getSyncStatus(): Promise<SyncStatus>;
}

interface HealthMonitoring {
    probe(providerId: string): Promise<ProbeResult>;
    getHealthReport(providerId?: string): Promise<HealthReport[]>;
}

interface DiscoveryConnector extends RegistrySync, HealthMonitoring {}

// ---------------------------------------------------------------------------
// YAML registry types
// ---------------------------------------------------------------------------

/**
 * Minimal YAML parser.
 *
 * In a real project, use a library like `js-yaml`:
 *   import yaml from "js-yaml";
 *
 * This connector includes a declaration for the parsing function
 * and a simple fallback that handles the flat key-value structure
 * of the registry file.
 */
declare function require(module: string): unknown;
const yaml = require("js-yaml") as {
    load(input: string): unknown;
};

/** Shape of a single model entry in the YAML registry file. */
interface YamlModelEntry {
    id: string;
    name: string;
    provider: string;
    capabilities: string[];
    context_window: number;
    max_output_tokens: number;
    status: "active" | "deprecated" | "preview";
    health_endpoint?: string;
    pricing?: {
        input_per_1k_tokens: number;
        output_per_1k_tokens: number;
        per_request?: number;
    };
    metadata?: Record<string, unknown>;
}

/** Shape of a provider entry in the YAML registry file. */
interface YamlProviderEntry {
    id: string;
    name: string;
    base_url: string;
    health_endpoint: string;
    health_method?: string;
    health_expected_status?: number;
    models: string[];
}

/** Top-level shape of the YAML registry file. */
interface YamlRegistryFile {
    version: number;
    providers: YamlProviderEntry[];
    models: YamlModelEntry[];
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Configuration for the YAML discovery connector. */
interface YamlDiscoveryConfig {
    /** Path to the YAML registry file. */
    registryFilePath: string;
    /** How often to re-sync the registry (in milliseconds). Default: 3600000 (1 hour). */
    syncIntervalMs?: number;
    /** Health probe timeout in milliseconds. Default: 10000 (10 seconds). */
    probeTimeoutMs?: number;
    /** Number of recent probe results to keep for rolling availability. Default: 20. */
    probeHistorySize?: number;
    /** Consecutive probe failures before marking a provider as unavailable. Default: 3. */
    failureThreshold?: number;
    /** Action to take when a new model is discovered. Default: "register". */
    onNewModel?: SyncAction;
    /** Action to take when a model is deprecated. Default: "notify". */
    onDeprecatedModel?: DeprecationAction;
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

class YamlDiscoveryConnector implements DiscoveryConnector {
    private readonly registryFilePath: string;
    private readonly syncIntervalMs: number;
    private readonly probeTimeoutMs: number;
    private readonly probeHistorySize: number;
    private readonly failureThreshold: number;
    private readonly onNewModel: SyncAction;
    private readonly onDeprecatedModel: DeprecationAction;

    /**
     * In-memory copy of the last-synced registry.
     * null until the first sync completes.
     */
    private currentRegistry: YamlRegistryFile | null = null;

    /** Set of model IDs known from the previous sync (for diff detection). */
    private previousModelIds = new Set<string>();

    /** Sync status tracking. */
    private syncStatus: SyncStatus = {
        models_synced: 0,
        status: "idle",
    };

    /**
     * Rolling probe history for each provider.
     * Key: provider_id, Value: array of probe results (newest first).
     */
    private probeHistory = new Map<string, ProbeResult[]>();

    constructor(config: YamlDiscoveryConfig) {
        this.registryFilePath = path.resolve(config.registryFilePath);
        this.syncIntervalMs = config.syncIntervalMs ?? 3_600_000;
        this.probeTimeoutMs = config.probeTimeoutMs ?? 10_000;
        this.probeHistorySize = config.probeHistorySize ?? 20;
        this.failureThreshold = config.failureThreshold ?? 3;
        this.onNewModel = config.onNewModel ?? SyncAction.REGISTER;
        this.onDeprecatedModel = config.onDeprecatedModel ?? DeprecationAction.NOTIFY;
    }

    // -----------------------------------------------------------------------
    // RegistrySync
    // -----------------------------------------------------------------------

    /**
     * Synchronize the model catalogue from the YAML registry file.
     *
     * Reads the YAML file, parses it, and computes a diff against the
     * previously known model set. Returns a SyncResult describing what
     * changed (new models, deprecated models, updated models, errors).
     *
     * @param providers Optional list of provider IDs to limit the sync to.
     *                  If omitted, all providers in the registry are synced.
     */
    async sync(providers?: string[]): Promise<SyncResult> {
        this.syncStatus.status = "syncing";
        const errors: string[] = [];

        let registry: YamlRegistryFile;
        try {
            registry = this.loadRegistryFile();
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : String(err);
            errors.push(`Failed to load registry file: ${message}`);
            this.syncStatus.status = "error";
            return {
                new_models: [],
                deprecated_models: [],
                updated_models: [],
                errors,
            };
        }

        // Filter to the requested providers if specified.
        let modelsToSync = registry.models;
        if (providers && providers.length > 0) {
            const providerSet = new Set(providers);
            modelsToSync = registry.models.filter((m) =>
                providerSet.has(m.provider),
            );
        }

        // Build the current model ID set.
        const currentModelIds = new Set(modelsToSync.map((m) => m.id));

        // Compute the diff.
        const newModels: string[] = [];
        const deprecatedModels: string[] = [];
        const updatedModels: string[] = [];

        for (const model of modelsToSync) {
            if (model.status === "deprecated") {
                deprecatedModels.push(model.id);
            } else if (!this.previousModelIds.has(model.id)) {
                newModels.push(model.id);
            } else {
                // Check if the model definition changed.
                const previousModel = this.currentRegistry?.models.find(
                    (m) => m.id === model.id,
                );
                if (previousModel && this.hasModelChanged(previousModel, model)) {
                    updatedModels.push(model.id);
                }
            }
        }

        // Detect models that were removed from the registry entirely.
        for (const previousId of this.previousModelIds) {
            if (!currentModelIds.has(previousId)) {
                deprecatedModels.push(previousId);
            }
        }

        // Update internal state.
        this.currentRegistry = registry;
        this.previousModelIds = currentModelIds;

        // Update sync status.
        const now = new Date();
        this.syncStatus = {
            last_sync: now,
            next_sync: new Date(now.getTime() + this.syncIntervalMs),
            models_synced: modelsToSync.length,
            status: errors.length > 0 ? "completed_with_errors" : "idle",
        };

        return {
            new_models: newModels,
            deprecated_models: [...new Set(deprecatedModels)], // deduplicate
            updated_models: updatedModels,
            errors,
        };
    }

    /**
     * Return the current synchronization status.
     *
     * Includes the last sync time, next scheduled sync, number of models
     * synced, and current status string.
     */
    async getSyncStatus(): Promise<SyncStatus> {
        return { ...this.syncStatus };
    }

    // -----------------------------------------------------------------------
    // HealthMonitoring
    // -----------------------------------------------------------------------

    /**
     * Send a health probe to a provider's health endpoint.
     *
     * Makes an HTTP request to the provider's configured health endpoint
     * (e.g., /health, /v1/models, or /readiness) and measures the response
     * latency. The result is stored in the rolling probe history.
     *
     * @param providerId The ID of the provider to probe.
     */
    async probe(providerId: string): Promise<ProbeResult> {
        const provider = this.findProvider(providerId);

        if (!provider) {
            const result: ProbeResult = {
                provider_id: providerId,
                success: false,
                error: `Provider "${providerId}" not found in registry`,
            };
            this.recordProbeResult(result);
            return result;
        }

        const healthUrl = this.buildHealthUrl(provider);
        const method = (provider.health_method ?? "GET").toUpperCase();
        const expectedStatus = provider.health_expected_status ?? 200;

        const startTime = performance.now();

        try {
            const controller = new AbortController();
            const timer = setTimeout(
                () => controller.abort(),
                this.probeTimeoutMs,
            );

            let response: Response;
            try {
                response = await fetch(healthUrl, {
                    method,
                    signal: controller.signal,
                    headers: { "User-Agent": "ModelMesh-Lite-HealthProbe/1.0" },
                });
            } finally {
                clearTimeout(timer);
            }

            const latencyMs = performance.now() - startTime;
            const success = response.status === expectedStatus;

            const result: ProbeResult = {
                provider_id: providerId,
                success,
                latency_ms: Math.round(latencyMs * 100) / 100,
                status_code: response.status,
                error: success
                    ? undefined
                    : `Unexpected status ${response.status} (expected ${expectedStatus})`,
            };

            this.recordProbeResult(result);
            return result;
        } catch (err: unknown) {
            const latencyMs = performance.now() - startTime;
            const message = err instanceof Error ? err.message : String(err);

            // Classify the error for a more informative error string.
            let errorDescription: string;
            if (message.includes("abort") || message.includes("timeout")) {
                errorDescription = `Health probe timed out after ${this.probeTimeoutMs}ms`;
            } else if (message.includes("ECONNREFUSED")) {
                errorDescription = `Connection refused at ${healthUrl}`;
            } else if (message.includes("ENOTFOUND")) {
                errorDescription = `DNS resolution failed for ${healthUrl}`;
            } else {
                errorDescription = `Probe failed: ${message}`;
            }

            const result: ProbeResult = {
                provider_id: providerId,
                success: false,
                latency_ms: Math.round(latencyMs * 100) / 100,
                error: errorDescription,
            };

            this.recordProbeResult(result);
            return result;
        }
    }

    /**
     * Return health reports for one or all providers.
     *
     * Computes a rolling availability score from the probe history.
     * The score is the fraction of successful probes in the history window.
     *
     * @param providerId A specific provider ID, or omit for all providers.
     */
    async getHealthReport(providerId?: string): Promise<HealthReport[]> {
        if (!this.currentRegistry) {
            return [];
        }

        const providers =
            providerId !== undefined
                ? this.currentRegistry.providers.filter((p) => p.id === providerId)
                : this.currentRegistry.providers;

        return providers.map((provider) => {
            const history = this.probeHistory.get(provider.id) ?? [];
            const report = this.computeHealthReport(provider.id, history);
            return report;
        });
    }

    // -----------------------------------------------------------------------
    // Private: Registry file handling
    // -----------------------------------------------------------------------

    /**
     * Load and parse the YAML registry file.
     *
     * Uses the js-yaml library to parse the file into a typed object.
     * Performs basic validation of the registry structure.
     */
    private loadRegistryFile(): YamlRegistryFile {
        if (!fs.existsSync(this.registryFilePath)) {
            throw new Error(
                `Registry file not found: ${this.registryFilePath}`,
            );
        }

        const raw = fs.readFileSync(this.registryFilePath, "utf8");
        const parsed = yaml.load(raw) as Record<string, unknown>;

        // Basic validation.
        if (!parsed || typeof parsed !== "object") {
            throw new Error("Registry file is empty or not a valid YAML object");
        }
        if (!Array.isArray(parsed.providers)) {
            throw new Error('Registry file must contain a "providers" array');
        }
        if (!Array.isArray(parsed.models)) {
            throw new Error('Registry file must contain a "models" array');
        }

        const registry: YamlRegistryFile = {
            version: (parsed.version as number) ?? 1,
            providers: parsed.providers as YamlProviderEntry[],
            models: parsed.models as YamlModelEntry[],
        };

        // Validate each model has required fields.
        for (const model of registry.models) {
            if (!model.id || !model.provider) {
                throw new Error(
                    `Model entry missing required fields (id, provider): ${JSON.stringify(model)}`,
                );
            }
        }

        return registry;
    }

    /**
     * Check whether a model definition has changed between syncs.
     *
     * Compares key fields to detect pricing changes, capability updates,
     * or status transitions.
     */
    private hasModelChanged(
        previous: YamlModelEntry,
        current: YamlModelEntry,
    ): boolean {
        if (previous.status !== current.status) return true;
        if (previous.context_window !== current.context_window) return true;
        if (previous.max_output_tokens !== current.max_output_tokens) return true;

        // Compare capabilities arrays.
        if (previous.capabilities.length !== current.capabilities.length) return true;
        const prevCaps = new Set(previous.capabilities);
        for (const cap of current.capabilities) {
            if (!prevCaps.has(cap)) return true;
        }

        // Compare pricing if present.
        if (previous.pricing && current.pricing) {
            if (
                previous.pricing.input_per_1k_tokens !== current.pricing.input_per_1k_tokens ||
                previous.pricing.output_per_1k_tokens !== current.pricing.output_per_1k_tokens
            ) {
                return true;
            }
        } else if (previous.pricing !== current.pricing) {
            // One has pricing and the other does not.
            return true;
        }

        return false;
    }

    // -----------------------------------------------------------------------
    // Private: Health probe helpers
    // -----------------------------------------------------------------------

    /** Find a provider by ID in the current registry. */
    private findProvider(providerId: string): YamlProviderEntry | undefined {
        return this.currentRegistry?.providers.find((p) => p.id === providerId);
    }

    /** Build the full health endpoint URL for a provider. */
    private buildHealthUrl(provider: YamlProviderEntry): string {
        const base = provider.base_url.replace(/\/+$/, "");
        const endpoint = provider.health_endpoint.startsWith("/")
            ? provider.health_endpoint
            : `/${provider.health_endpoint}`;
        return `${base}${endpoint}`;
    }

    /** Record a probe result in the rolling history. */
    private recordProbeResult(result: ProbeResult): void {
        let history = this.probeHistory.get(result.provider_id);
        if (!history) {
            history = [];
            this.probeHistory.set(result.provider_id, history);
        }

        // Add to the front (newest first).
        history.unshift(result);

        // Trim to the configured history size.
        if (history.length > this.probeHistorySize) {
            history.length = this.probeHistorySize;
        }
    }

    /**
     * Compute a health report from the rolling probe history.
     *
     * The availability score is calculated as the ratio of successful
     * probes to total probes in the history window. A provider is marked
     * as unavailable if the most recent N consecutive probes all failed,
     * where N is the configured failure threshold.
     */
    private computeHealthReport(
        providerId: string,
        history: ProbeResult[],
    ): HealthReport {
        const now = new Date();

        if (history.length === 0) {
            return {
                provider_id: providerId,
                available: true, // assume available until proven otherwise
                availability_score: 1.0,
                timestamp: now,
            };
        }

        // Count successes for the availability score.
        const successCount = history.filter((r) => r.success).length;
        const availabilityScore = successCount / history.length;

        // Check consecutive recent failures against the threshold.
        let consecutiveFailures = 0;
        for (const result of history) {
            if (!result.success) {
                consecutiveFailures++;
            } else {
                break;
            }
        }
        const available = consecutiveFailures < this.failureThreshold;

        // Use the most recent probe for latency and status code.
        const latest = history[0];

        // Compute average latency from successful probes.
        const successfulProbes = history.filter(
            (r) => r.success && r.latency_ms !== undefined,
        );
        const avgLatency =
            successfulProbes.length > 0
                ? successfulProbes.reduce((sum, r) => sum + (r.latency_ms ?? 0), 0) /
                  successfulProbes.length
                : undefined;

        return {
            provider_id: providerId,
            available,
            latency_ms: avgLatency !== undefined
                ? Math.round(avgLatency * 100) / 100
                : latest.latency_ms,
            status_code: latest.status_code,
            error: latest.error,
            availability_score: Math.round(availabilityScore * 1000) / 1000,
            timestamp: now,
        };
    }
}

// ---------------------------------------------------------------------------
// YAML configuration example
// ---------------------------------------------------------------------------

/*
# modelmesh.yaml — discovery section for the YAML registry connector
#
# discovery:
#   connector: custom
#   connector_class: YamlDiscoveryConnector
#   config:
#     registry_file_path: "./config/model-registry.yaml"
#     sync_interval_ms: 3600000      # 1 hour
#     probe_timeout_ms: 10000        # 10 seconds
#     probe_history_size: 20
#     failure_threshold: 3
#     on_new_model: register
#     on_deprecated_model: notify
#   sync:
#     enabled: true
#     interval: 1h
#     auto_register: true
#   health:
#     enabled: true
#     interval: 60s
#     timeout: 10s
#     failure_threshold: 3
#
# ---
#
# Example YAML registry file (config/model-registry.yaml):
#
# version: 1
#
# providers:
#   - id: openai-primary
#     name: OpenAI (Primary Key)
#     base_url: "https://api.openai.com"
#     health_endpoint: "/v1/models"
#     health_method: GET
#     health_expected_status: 200
#     models:
#       - gpt-4o
#       - gpt-4o-mini
#
#   - id: anthropic-primary
#     name: Anthropic (Primary Key)
#     base_url: "https://api.anthropic.com"
#     health_endpoint: "/v1/messages"
#     health_method: GET
#     health_expected_status: 405   # Anthropic returns 405 for GET on /v1/messages
#     models:
#       - claude-sonnet-4-20250514
#
#   - id: vllm-internal
#     name: Self-hosted vLLM
#     base_url: "http://gpu-server.internal:8000"
#     health_endpoint: "/health"
#     health_method: GET
#     health_expected_status: 200
#     models:
#       - llama-3.1-70b
#
# models:
#   - id: gpt-4o
#     name: GPT-4o
#     provider: openai-primary
#     capabilities: [generation.text-generation.chat-completion]
#     context_window: 128000
#     max_output_tokens: 16384
#     status: active
#     pricing:
#       input_per_1k_tokens: 0.0025
#       output_per_1k_tokens: 0.01
#
#   - id: gpt-4o-mini
#     name: GPT-4o Mini
#     provider: openai-primary
#     capabilities: [generation.text-generation.chat-completion]
#     context_window: 128000
#     max_output_tokens: 16384
#     status: active
#     pricing:
#       input_per_1k_tokens: 0.00015
#       output_per_1k_tokens: 0.0006
#
#   - id: claude-sonnet-4-20250514
#     name: Claude Sonnet 4
#     provider: anthropic-primary
#     capabilities: [generation.text-generation.chat-completion]
#     context_window: 200000
#     max_output_tokens: 16000
#     status: active
#     pricing:
#       input_per_1k_tokens: 0.003
#       output_per_1k_tokens: 0.015
#
#   - id: llama-3.1-70b
#     name: Llama 3.1 70B (Self-Hosted)
#     provider: vllm-internal
#     capabilities: [generation.text-generation.chat-completion]
#     context_window: 131072
#     max_output_tokens: 4096
#     status: active
#
#   - id: gpt-4-turbo
#     name: GPT-4 Turbo (Deprecated)
#     provider: openai-primary
#     capabilities: [generation.text-generation.chat-completion]
#     context_window: 128000
#     max_output_tokens: 4096
#     status: deprecated
*/

export { YamlDiscoveryConnector };
export type {
    YamlDiscoveryConfig,
    YamlRegistryFile,
    YamlModelEntry,
    YamlProviderEntry,
    DiscoveryConnector,
    RegistrySync,
    HealthMonitoring,
    SyncResult,
    SyncStatus,
    HealthReport,
    ProbeResult,
};
