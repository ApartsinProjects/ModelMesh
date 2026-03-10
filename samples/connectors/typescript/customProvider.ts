/**
 * Custom Provider Connector — Self-Hosted vLLM Instance
 *
 * Demonstrates how to implement a custom provider connector for ModelMesh Lite
 * that wraps a self-hosted vLLM inference server. vLLM exposes an OpenAI-compatible
 * API but uses a slightly different request/response envelope, so this connector
 * translates between the ModelMesh normalized format and the vLLM-specific format.
 *
 * Implements all six required provider sub-interfaces:
 *   - ModelExecution   : send completions and stream partial results
 *   - Capabilities     : declare supported features
 *   - ModelCatalogue   : list models served by the vLLM instance
 *   - QuotaRateLimits  : track local request/token budgets
 *   - CostPricing      : report self-hosted cost estimates
 *   - ErrorClassification : classify vLLM errors for retry decisions
 *
 * See: docs/interfaces/Provider.md
 */
// For a simpler CDK-based approach, see samples/cdk/typescript/

// ---------------------------------------------------------------------------
// Types imported from @modelmesh/core (reproduced here for self-containment)
// ---------------------------------------------------------------------------

/** Authentication method used by a provider connector. */
enum AuthMethod {
    API_KEY = "api_key",
    OAUTH = "oauth",
    SERVICE_ACCOUNT = "service_account",
}

/** Token consumption for a single completion request. */
interface TokenUsage {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
}

/** Per-unit pricing for a model. */
interface ModelPricing {
    input_per_1k_tokens: number;
    output_per_1k_tokens: number;
    per_request?: number;
}

/** Descriptor for a single model exposed by a provider. */
interface ModelInfo {
    id: string;
    name: string;
    capabilities: string[];
    context_window: number;
    max_output_tokens: number;
    pricing?: ModelPricing;
}

/** Normalized request sent to a provider for completion. */
interface CompletionRequest {
    model: string;
    messages: Record<string, unknown>[];
    temperature?: number;
    max_tokens?: number;
    tools?: Record<string, unknown>[];
    stream: boolean;
}

/** Normalized response returned from a provider completion. */
interface CompletionResponse {
    id: string;
    model: string;
    choices: Record<string, unknown>[];
    usage: TokenUsage;
}

/** Current quota consumption and limits for a provider. */
interface QuotaStatus {
    used: number;
    remaining?: number;
    limit?: number;
    resets_at?: Date;
}

/** Current rate-limit headroom for a provider. */
interface RateLimitStatus {
    requests_remaining?: number;
    tokens_remaining?: number;
    reset_seconds?: number;
}

/** Result of classifying a provider error. */
interface ErrorClassificationResult {
    retryable: boolean;
    category: string;
    retry_after?: number;
}

// ---------------------------------------------------------------------------
// Provider sub-interfaces (from docs/interfaces/Provider.md)
// ---------------------------------------------------------------------------

interface ModelExecution {
    complete(request: CompletionRequest): Promise<CompletionResponse>;
    stream(request: CompletionRequest): AsyncIterable<CompletionResponse>;
}

interface Capabilities {
    getCapabilities(): string[];
    supports(capability: string): boolean;
}

interface ModelCatalogue {
    listModels(): Promise<ModelInfo[]>;
    getModelInfo(modelId: string): Promise<ModelInfo>;
}

interface QuotaRateLimits {
    checkQuota(): Promise<QuotaStatus>;
    getRateLimits(): Promise<RateLimitStatus>;
}

interface CostPricing {
    getPricing(modelId: string): Promise<ModelPricing>;
    reportUsage(modelId: string, usage: TokenUsage): void;
}

interface ErrorHandling {
    classifyError(error: Error): ErrorClassificationResult;
    isRetryable(error: Error): boolean;
}

interface ProviderConnector
    extends ModelExecution, Capabilities, ModelCatalogue,
            QuotaRateLimits, CostPricing, ErrorHandling {}

// ---------------------------------------------------------------------------
// vLLM-specific types — the wire format used by the self-hosted server
// ---------------------------------------------------------------------------

/** Shape of a vLLM /v1/completions response (chat variant). */
interface VllmChatResponse {
    id: string;
    object: string;
    created: number;
    model: string;
    choices: Array<{
        index: number;
        message: { role: string; content: string };
        finish_reason: string | null;
    }>;
    usage: {
        prompt_tokens: number;
        completion_tokens: number;
        total_tokens: number;
    };
}

/** Shape of a single SSE chunk from vLLM streaming. */
interface VllmStreamChunk {
    id: string;
    object: string;
    created: number;
    model: string;
    choices: Array<{
        index: number;
        delta: { role?: string; content?: string };
        finish_reason: string | null;
    }>;
    usage?: {
        prompt_tokens: number;
        completion_tokens: number;
        total_tokens: number;
    };
}

/** Shape of a vLLM /v1/models response. */
interface VllmModelsResponse {
    object: string;
    data: Array<{
        id: string;
        object: string;
        owned_by: string;
        root: string;
        permission: unknown[];
    }>;
}

/** Configuration for the vLLM provider connector. */
interface VllmProviderConfig {
    /** Base URL of the vLLM server, e.g. "http://gpu-server:8000" */
    baseUrl: string;
    /** Optional API key if the vLLM server requires authentication */
    apiKey?: string;
    /** Request timeout in milliseconds (default: 60000) */
    timeoutMs?: number;
    /** Maximum retries at the connector level (default: 2) */
    maxRetries?: number;
    /** Models served and their context windows (used for catalogue) */
    models: VllmModelDefinition[];
    /** Self-hosted cost estimate per GPU-hour in USD (default: 2.50) */
    gpuHourCost?: number;
    /** Daily request budget (optional; unlimited if omitted) */
    dailyRequestLimit?: number;
    /** Daily token budget (optional; unlimited if omitted) */
    dailyTokenLimit?: number;
}

/** A model definition provided in the connector configuration. */
interface VllmModelDefinition {
    id: string;
    name: string;
    contextWindow: number;
    maxOutputTokens: number;
    capabilities: string[];
}

// ---------------------------------------------------------------------------
// Custom error type for vLLM HTTP errors
// ---------------------------------------------------------------------------

class VllmHttpError extends Error {
    constructor(
        public readonly statusCode: number,
        public readonly responseBody: string,
    ) {
        super(`vLLM returned HTTP ${statusCode}: ${responseBody}`);
        this.name = "VllmHttpError";
    }
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

class VllmProviderConnector implements ProviderConnector {
    private readonly baseUrl: string;
    private readonly apiKey: string | undefined;
    private readonly timeoutMs: number;
    private readonly models: VllmModelDefinition[];
    private readonly gpuHourCost: number;
    private readonly dailyRequestLimit: number | undefined;
    private readonly dailyTokenLimit: number | undefined;

    /** Capabilities this connector supports. */
    private readonly supportedCapabilities: string[] = [
        "generation.text-generation.chat-completion",
    ];

    /** Accumulated usage tracking for quota enforcement. */
    private usageToday = {
        requests: 0,
        tokensIn: 0,
        tokensOut: 0,
        costUsd: 0,
        resetAt: VllmProviderConnector.nextMidnightUtc(),
    };

    constructor(config: VllmProviderConfig) {
        this.baseUrl = config.baseUrl.replace(/\/+$/, "");
        this.apiKey = config.apiKey;
        this.timeoutMs = config.timeoutMs ?? 60_000;
        this.models = config.models;
        this.gpuHourCost = config.gpuHourCost ?? 2.5;
        this.dailyRequestLimit = config.dailyRequestLimit;
        this.dailyTokenLimit = config.dailyTokenLimit;
    }

    // -----------------------------------------------------------------------
    // ModelExecution
    // -----------------------------------------------------------------------

    /**
     * Send a non-streaming completion request to the vLLM server.
     *
     * Translates the normalized CompletionRequest into the vLLM chat
     * completions format, sends it via fetch, and translates the response
     * back to a normalized CompletionResponse.
     */
    async complete(request: CompletionRequest): Promise<CompletionResponse> {
        this.rolloverDailyQuotaIfNeeded();

        // Build the vLLM request body. vLLM uses the OpenAI chat completions
        // format but may include extra fields like `best_of` or `top_k`.
        const body = this.translateToVllmRequest(request);

        const response = await this.fetchWithTimeout(
            `${this.baseUrl}/v1/chat/completions`,
            {
                method: "POST",
                headers: this.buildHeaders(),
                body: JSON.stringify(body),
            },
        );

        if (!response.ok) {
            const text = await response.text();
            throw new VllmHttpError(response.status, text);
        }

        const vllmResponse: VllmChatResponse = await response.json();

        // Track usage for quota and cost reporting.
        this.trackUsage(request.model, vllmResponse.usage);

        return this.translateFromVllmResponse(vllmResponse);
    }

    /**
     * Send a streaming completion request and yield partial responses.
     *
     * vLLM uses Server-Sent Events (SSE). Each SSE data line contains a JSON
     * chunk. The final chunk is `[DONE]`. We parse incremental deltas and
     * yield them as CompletionResponse objects.
     */
    async *stream(request: CompletionRequest): AsyncIterable<CompletionResponse> {
        this.rolloverDailyQuotaIfNeeded();

        const body = this.translateToVllmRequest({ ...request, stream: true });

        const response = await this.fetchWithTimeout(
            `${this.baseUrl}/v1/chat/completions`,
            {
                method: "POST",
                headers: this.buildHeaders(),
                body: JSON.stringify(body),
            },
        );

        if (!response.ok) {
            const text = await response.text();
            throw new VllmHttpError(response.status, text);
        }

        // Read the SSE stream. We use the web-standard ReadableStream API.
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let accumulatedUsage: TokenUsage = {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
        };

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // SSE lines are separated by double newlines.
                const lines = buffer.split("\n");
                buffer = lines.pop()!; // keep the last partial line

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || !trimmed.startsWith("data: ")) continue;

                    const payload = trimmed.slice(6); // remove "data: " prefix
                    if (payload === "[DONE]") continue;

                    const chunk: VllmStreamChunk = JSON.parse(payload);

                    // If the final chunk includes aggregated usage, capture it.
                    if (chunk.usage) {
                        accumulatedUsage = {
                            prompt_tokens: chunk.usage.prompt_tokens,
                            completion_tokens: chunk.usage.completion_tokens,
                            total_tokens: chunk.usage.total_tokens,
                        };
                    }

                    yield {
                        id: chunk.id,
                        model: chunk.model,
                        choices: chunk.choices.map((c) => ({
                            index: c.index,
                            delta: c.delta,
                            finish_reason: c.finish_reason,
                        })),
                        usage: chunk.usage
                            ? {
                                  prompt_tokens: chunk.usage.prompt_tokens,
                                  completion_tokens: chunk.usage.completion_tokens,
                                  total_tokens: chunk.usage.total_tokens,
                              }
                            : { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
                    };
                }
            }
        } finally {
            reader.releaseLock();
        }

        // Report accumulated usage once the stream completes.
        if (accumulatedUsage.total_tokens > 0) {
            this.trackUsage(request.model, accumulatedUsage);
        }
    }

    // -----------------------------------------------------------------------
    // Capabilities
    // -----------------------------------------------------------------------

    /** Return capability identifiers this vLLM connector supports. */
    getCapabilities(): string[] {
        return [...this.supportedCapabilities];
    }

    /** Check whether this connector supports a specific capability. */
    supports(capability: string): boolean {
        return this.supportedCapabilities.includes(capability);
    }

    // -----------------------------------------------------------------------
    // ModelCatalogue
    // -----------------------------------------------------------------------

    /**
     * List all models served by this vLLM instance.
     *
     * Uses the statically configured model definitions enriched with
     * self-hosted pricing estimates. Optionally queries the vLLM /v1/models
     * endpoint to verify availability.
     */
    async listModels(): Promise<ModelInfo[]> {
        // Optionally verify against the live server catalogue.
        let liveModelIds: Set<string> | null = null;
        try {
            const response = await this.fetchWithTimeout(
                `${this.baseUrl}/v1/models`,
                { method: "GET", headers: this.buildHeaders() },
            );
            if (response.ok) {
                const data: VllmModelsResponse = await response.json();
                liveModelIds = new Set(data.data.map((m) => m.id));
            }
        } catch {
            // If the server is unreachable, fall back to static config.
        }

        return this.models
            .filter((m) => liveModelIds === null || liveModelIds.has(m.id))
            .map((m) => this.toModelInfo(m));
    }

    /** Return detailed information for a specific model. */
    async getModelInfo(modelId: string): Promise<ModelInfo> {
        const definition = this.models.find((m) => m.id === modelId);
        if (!definition) {
            throw new Error(`Model "${modelId}" not found in vLLM connector catalogue`);
        }
        return this.toModelInfo(definition);
    }

    // -----------------------------------------------------------------------
    // QuotaRateLimits
    // -----------------------------------------------------------------------

    /**
     * Return current quota consumption against daily budgets.
     *
     * Since vLLM is self-hosted, there is no external quota API. Instead we
     * track local usage against the configured daily limits.
     */
    async checkQuota(): Promise<QuotaStatus> {
        this.rolloverDailyQuotaIfNeeded();

        const limit = this.dailyRequestLimit;
        return {
            used: this.usageToday.requests,
            remaining: limit !== undefined ? Math.max(0, limit - this.usageToday.requests) : undefined,
            limit,
            resets_at: this.usageToday.resetAt,
        };
    }

    /**
     * Return current rate-limit headroom.
     *
     * vLLM does not enforce rate limits natively, but we can derive token
     * headroom from the configured daily token budget.
     */
    async getRateLimits(): Promise<RateLimitStatus> {
        this.rolloverDailyQuotaIfNeeded();

        const totalTokens = this.usageToday.tokensIn + this.usageToday.tokensOut;
        const tokensRemaining =
            this.dailyTokenLimit !== undefined
                ? Math.max(0, this.dailyTokenLimit - totalTokens)
                : undefined;

        const requestsRemaining =
            this.dailyRequestLimit !== undefined
                ? Math.max(0, this.dailyRequestLimit - this.usageToday.requests)
                : undefined;

        // Seconds until midnight UTC reset.
        const resetSeconds = (this.usageToday.resetAt.getTime() - Date.now()) / 1000;

        return {
            requests_remaining: requestsRemaining,
            tokens_remaining: tokensRemaining,
            reset_seconds: Math.max(0, resetSeconds),
        };
    }

    // -----------------------------------------------------------------------
    // CostPricing
    // -----------------------------------------------------------------------

    /**
     * Return pricing for a model.
     *
     * For self-hosted vLLM, we estimate cost based on GPU-hour cost divided
     * by throughput. These are rough estimates; adjust gpuHourCost in config.
     */
    async getPricing(modelId: string): Promise<ModelPricing> {
        // Rough estimate: GPU-hour cost spread across tokens.
        // Assumes ~2000 tokens/second throughput on a modern GPU.
        const tokensPerSecond = 2000;
        const costPerToken = this.gpuHourCost / (tokensPerSecond * 3600);

        return {
            input_per_1k_tokens: costPerToken * 1000,
            output_per_1k_tokens: costPerToken * 1500, // output is ~1.5x more expensive (decode vs prefill)
            per_request: 0, // no per-request overhead for self-hosted
        };
    }

    /**
     * Report token usage for cost tracking.
     *
     * Accumulates into the daily usage counters that drive quota checks
     * and cost reporting.
     */
    reportUsage(modelId: string, usage: TokenUsage): void {
        this.usageToday.tokensIn += usage.prompt_tokens;
        this.usageToday.tokensOut += usage.completion_tokens;
    }

    // -----------------------------------------------------------------------
    // ErrorClassification
    // -----------------------------------------------------------------------

    /**
     * Classify a vLLM error for retry/rotation decisions.
     *
     * vLLM can return non-standard error bodies. This method inspects both
     * the HTTP status code (for VllmHttpError) and the error message to
     * produce a classification the router can act on.
     */
    classifyError(error: Error): ErrorClassification {
        if (error instanceof VllmHttpError) {
            return this.classifyHttpError(error);
        }

        // Network-level errors (DNS failure, connection refused, timeout).
        if (error.name === "AbortError" || error.message.includes("timeout")) {
            return { retryable: true, category: "timeout", retry_after: 5 };
        }
        if (
            error.message.includes("ECONNREFUSED") ||
            error.message.includes("ENOTFOUND") ||
            error.message.includes("fetch failed")
        ) {
            return { retryable: true, category: "network_error", retry_after: 10 };
        }

        // Unknown errors are not retryable by default.
        return { retryable: false, category: "unknown" };
    }

    /** Return true if the error is eligible for retry. */
    isRetryable(error: Error): boolean {
        return this.classifyError(error).retryable;
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    /**
     * Translate a normalized CompletionRequest into the vLLM request body.
     *
     * vLLM's chat completions endpoint is largely OpenAI-compatible, but we
     * explicitly set fields to avoid relying on server defaults.
     */
    private translateToVllmRequest(request: CompletionRequest): Record<string, unknown> {
        const body: Record<string, unknown> = {
            model: request.model,
            messages: request.messages,
            stream: request.stream,
        };

        if (request.temperature !== undefined) {
            body.temperature = request.temperature;
        }
        if (request.max_tokens !== undefined) {
            body.max_tokens = request.max_tokens;
        }
        if (request.tools && request.tools.length > 0) {
            body.tools = request.tools;
        }

        // vLLM-specific: request token usage in streaming responses.
        if (request.stream) {
            body.stream_options = { include_usage: true };
        }

        return body;
    }

    /** Translate a vLLM response back to the normalized CompletionResponse. */
    private translateFromVllmResponse(vllm: VllmChatResponse): CompletionResponse {
        return {
            id: vllm.id,
            model: vllm.model,
            choices: vllm.choices.map((c) => ({
                index: c.index,
                message: c.message,
                finish_reason: c.finish_reason,
            })),
            usage: {
                prompt_tokens: vllm.usage.prompt_tokens,
                completion_tokens: vllm.usage.completion_tokens,
                total_tokens: vllm.usage.total_tokens,
            },
        };
    }

    /** Build HTTP headers for vLLM requests. */
    private buildHeaders(): Record<string, string> {
        const headers: Record<string, string> = {
            "Content-Type": "application/json",
        };
        if (this.apiKey) {
            headers["Authorization"] = `Bearer ${this.apiKey}`;
        }
        return headers;
    }

    /** Wrapper around fetch that enforces the configured timeout. */
    private async fetchWithTimeout(
        url: string,
        init: RequestInit,
    ): Promise<Response> {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeoutMs);

        try {
            return await fetch(url, { ...init, signal: controller.signal });
        } finally {
            clearTimeout(timer);
        }
    }

    /** Convert a model definition to a ModelInfo descriptor. */
    private toModelInfo(def: VllmModelDefinition): ModelInfo {
        const tokensPerSecond = 2000;
        const costPerToken = this.gpuHourCost / (tokensPerSecond * 3600);

        return {
            id: def.id,
            name: def.name,
            capabilities: def.capabilities,
            context_window: def.contextWindow,
            max_output_tokens: def.maxOutputTokens,
            pricing: {
                input_per_1k_tokens: costPerToken * 1000,
                output_per_1k_tokens: costPerToken * 1500,
                per_request: 0,
            },
        };
    }

    /** Track usage from a completed request. */
    private trackUsage(
        modelId: string,
        usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number },
    ): void {
        this.usageToday.requests += 1;
        this.usageToday.tokensIn += usage.prompt_tokens;
        this.usageToday.tokensOut += usage.completion_tokens;
    }

    /** Roll over daily quota counters if past midnight UTC. */
    private rolloverDailyQuotaIfNeeded(): void {
        if (Date.now() >= this.usageToday.resetAt.getTime()) {
            this.usageToday = {
                requests: 0,
                tokensIn: 0,
                tokensOut: 0,
                costUsd: 0,
                resetAt: VllmProviderConnector.nextMidnightUtc(),
            };
        }
    }

    /** Classify an HTTP-level error from vLLM. */
    private classifyHttpError(error: VllmHttpError): ErrorClassification {
        switch (error.statusCode) {
            // Rate-limited (vLLM can return 429 when request queue is full).
            case 429:
                return { retryable: true, category: "rate_limited", retry_after: 15 };

            // Bad request — malformed prompt or unsupported parameter.
            case 400:
                return { retryable: false, category: "invalid_request" };

            // Authentication failure.
            case 401:
            case 403:
                return { retryable: false, category: "auth_failure" };

            // Model not found on the server.
            case 404:
                return { retryable: false, category: "model_not_found" };

            // Server overloaded or CUDA out-of-memory.
            case 503:
                return { retryable: true, category: "server_overloaded", retry_after: 30 };

            // Internal server error (possible CUDA crash).
            case 500:
                // Check for CUDA OOM in the response body.
                if (error.responseBody.includes("CUDA out of memory")) {
                    return { retryable: true, category: "gpu_oom", retry_after: 60 };
                }
                return { retryable: true, category: "internal_error", retry_after: 10 };

            // Bad gateway / gateway timeout (reverse proxy issues).
            case 502:
            case 504:
                return { retryable: true, category: "gateway_error", retry_after: 10 };

            default:
                return { retryable: false, category: "unknown", retry_after: undefined };
        }
    }

    /** Compute the next midnight UTC as a Date. */
    private static nextMidnightUtc(): Date {
        const now = new Date();
        const tomorrow = new Date(Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            now.getUTCDate() + 1,
            0, 0, 0, 0,
        ));
        return tomorrow;
    }
}

// ---------------------------------------------------------------------------
// YAML configuration example
// ---------------------------------------------------------------------------

/*
# modelmesh.yaml — provider section for the vLLM connector
#
# providers:
#   my-vllm:
#     connector: custom
#     connector_class: VllmProviderConnector
#     execution:
#       base_url: "http://gpu-cluster.internal:8000"
#       timeout: 60s
#       max_retries: 2
#     auth:
#       method: api_key
#       api_key: "${secrets:vllm-api-key}"
#     models:
#       - id: "meta-llama/Llama-3.1-70B-Instruct"
#         name: "Llama 3.1 70B (self-hosted)"
#         context_window: 131072
#         max_output_tokens: 4096
#         capabilities: [generation.text-generation.chat-completion]
#       - id: "mistralai/Mistral-7B-Instruct-v0.3"
#         name: "Mistral 7B (self-hosted)"
#         context_window: 32768
#         max_output_tokens: 4096
#         capabilities: [generation.text-generation.chat-completion]
#     budget:
#       gpu_hour_cost: 2.50
#       daily_request_limit: 50000
#       daily_token_limit: 100000000
*/

export { VllmProviderConnector, VllmHttpError };
export type {
    VllmProviderConfig,
    VllmModelDefinition,
    ProviderConnector,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
    ModelPricing,
    ModelInfo,
    QuotaStatus,
    RateLimitStatus,
    ErrorClassification,
};
