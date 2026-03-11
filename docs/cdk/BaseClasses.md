---
layout: default
title: "CDK Base Classes"
---

# CDK Base Classes

The Connector Development Kit (CDK) provides base classes that implement the connector interfaces with sensible defaults. Each base class handles boilerplate -- HTTP transport, caching, serialization, error classification -- so that custom connectors only override the methods that differ from the defaults. Every base class maps one-to-one with a connector interface and is designed to be subclassed.

> **Interfaces:** [Provider](../interfaces/Provider.md) | [RotationPolicy](../interfaces/RotationPolicy.md) | [SecretStore](../interfaces/SecretStore.md) | [Storage](../interfaces/Storage.md) | [Observability](../interfaces/Observability.md) | [Discovery](../interfaces/Discovery.md)

---

## BaseProvider

The foundation for all provider connectors. Implements the full `ProviderConnector` interface with an OpenAI-compatible default behavior: POST JSON to `/v1/chat/completions`, parse an OpenAI-format response, and handle streaming via SSE. Subclasses override protected hook methods to adapt to non-OpenAI APIs without reimplementing transport, retries, or error classification.

> **Implements:** [ProviderConnector](../interfaces/Provider.md)

### Configuration

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseProviderConfig:
    """Configuration for a BaseProvider instance."""
    base_url: str
    api_key: str = ""
    models: list["ModelInfo"] = field(default_factory=list)
    timeout: float = 30.0
    max_retries: int = 3
    auth_method: str = "api_key"
    retryable_codes: list[int] = field(default_factory=lambda: [429, 500, 502, 503])
    non_retryable_codes: list[int] = field(default_factory=lambda: [400, 401, 403])
    capabilities: list[str] = field(default_factory=lambda: ["generation.text-generation.chat-completion"])
```

```typescript
/** Configuration for a BaseProvider instance. */
interface BaseProviderConfig {
    baseUrl: string;
    apiKey?: string;
    models?: ModelInfo[];
    timeout?: number;           // seconds, default 30
    maxRetries?: number;        // default 3
    authMethod?: string;        // default "api_key"
    retryableCodes?: number[];  // default [429, 500, 502, 503]
    nonRetryableCodes?: number[]; // default [400, 401, 403]
    capabilities?: string[];    // default ["generation.text-generation.chat-completion"]
}
```

> **Capabilities vs Features**
>
> `ModelInfo.capabilities` and `ModelInfo.features` serve different purposes and should not be mixed:
>
> - **`capabilities: list[str]`** -- Dot-notation tree paths that identify *what kind of work* a model can perform. These are used for capability tree registration and pool matching. Examples: `"generation.text-generation.chat-completion"`, `"representation.embeddings.text-embeddings"`, `"generation.image-generation.text-to-image"`.
> - **`features: dict[str, bool]`** -- Feature flags that describe *what a model supports within a capability*. These are not separate capabilities but boolean properties of a model. Examples: `{"tool_calling": True, "vision": True, "system_prompt": True, "streaming": True}`.
>
> **Incorrect (old short-form, do not use):**
> ```python
> capabilities=["chat", "tools", "vision"]  # wrong -- mixes capabilities and features
> ```
> **Correct:**
> ```python
> capabilities=["generation.text-generation.chat-completion"]
> features={"tool_calling": True, "vision": True}
> ```
>
> When `config.models` is empty or individual `ModelInfo` entries omit `capabilities`, ModelMesh auto-discovers them from the provider connector's `list_models()` method. See [QuickProvider](#quickprovider) for the auto-discovery flow.

### Methods and Default Behavior

| Method | Default Behavior |
|---|---|
| `complete(request)` | POST to `{base_url}/v1/chat/completions` with OpenAI JSON format; return parsed `CompletionResponse` |
| `stream(request)` | POST with `stream: true`; yield `CompletionResponse` chunks parsed from SSE |
| `get_capabilities()` | Return `config.capabilities` list |
| `supports(capability)` | Return `capability in config.capabilities` |
| `list_models()` | Return `config.models` list |
| `get_model_info(model_id)` | Find model by ID in `config.models`; raise `KeyError` if missing |
| `check_quota()` | Return `QuotaStatus(used=self._request_count)` with no limit |
| `get_rate_limits()` | Return `RateLimitStatus()` with all fields `None` |
| `get_pricing(model_id)` | Return pricing from `ModelInfo.pricing` or raise `KeyError` |
| `report_usage(model_id, usage)` | Increment internal counters `_request_count` and `_tokens_used` |
| `classify_error(error)` | Map HTTP status to `ErrorClassification` using `retryable_codes` / `non_retryable_codes` |
| `is_retryable(error)` | Return `classify_error(error).retryable` |

### Protected Hook Methods

| Hook | Default | Override To |
|---|---|---|
| `_build_request_payload(request)` | OpenAI JSON format (`model`, `messages`, `temperature`, `max_tokens`, `tools`, `stream`) | Change request translation for non-OpenAI APIs |
| `_parse_response(data)` | Parse OpenAI JSON response into `CompletionResponse` | Handle custom response schemas |
| `_build_headers()` | `{"Authorization": "Bearer {api_key}", "Content-Type": "application/json"}` | Add custom headers or change auth scheme |
| `_get_completion_endpoint()` | `"{base_url}/v1/chat/completions"` | Change the completion URL path |
| `_parse_sse_chunk(line)` | Parse `data: {...}` SSE lines into partial `CompletionResponse` | Handle non-standard streaming formats |

### Python

```python
import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import urllib.request

from modelmesh.cdk.enums import AuthMethod
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    ModelInfo,
    ModelPricing,
    ProviderConnector,
    QuotaStatus,
    RateLimitStatus,
    TokenUsage,
)


@dataclass
class BaseProviderConfig:
    """Configuration for a BaseProvider instance."""
    base_url: str
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)
    timeout: float = 30.0
    max_retries: int = 3
    auth_method: str = "api_key"
    retryable_codes: list[int] = field(default_factory=lambda: [429, 500, 502, 503])
    non_retryable_codes: list[int] = field(default_factory=lambda: [400, 401, 403])
    capabilities: list[str] = field(default_factory=lambda: ["generation.text-generation.chat-completion"])


class BaseProvider(ProviderConnector):
    """Base implementation of the ProviderConnector interface.

    Provides an OpenAI-compatible default behavior for all methods.
    Subclasses override protected hook methods to adapt to non-OpenAI
    APIs without reimplementing transport, retries, or error handling.
    """

    def __init__(self, config: BaseProviderConfig, observability=None) -> None:
        self._config = config
        self._timeout = config.timeout
        self._request_count: int = 0
        self._tokens_used: int = 0
        self._models_by_id: dict[str, ModelInfo] = {
            m.id: m for m in config.models
        }
        self._observability = observability

    # ── Model Execution ─────────────────────────────────────────────

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request and return the full response.

        Builds the payload via ``_build_request_payload``, posts to the
        endpoint returned by ``_get_completion_endpoint``, and parses
        the response via ``_parse_response``. Retries on retryable
        status codes up to ``max_retries`` times.
        """
        payload = self._build_request_payload(request)
        headers = self._build_headers()
        endpoint = self._get_completion_endpoint()

        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                resp = await self._client.post(
                    endpoint, json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                result = self._parse_response(data)
                self.report_usage(request.model, result.usage)
                return result
            except urllib.error.HTTPError as exc:
                last_error = exc
                classification = self.classify_error(exc)
                if not classification.retryable or attempt == self._config.max_retries:
                    raise
                retry_after = classification.retry_after or (2 ** attempt)
                import asyncio
                await asyncio.sleep(retry_after)

        raise last_error  # unreachable but satisfies type checker

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[CompletionResponse]:
        """Send a completion request and yield partial responses via SSE.

        Sets ``stream: true`` in the payload and reads the response as
        a server-sent event stream, parsing each chunk through
        ``_parse_sse_chunk``.
        """
        payload = self._build_request_payload(request)
        payload["stream"] = True
        headers = self._build_headers()
        endpoint = self._get_completion_endpoint()

        async with self._client.stream(
            "POST", endpoint, json=payload, headers=headers
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str.strip() == "[DONE]":
                    break
                chunk = self._parse_sse_chunk(data_str)
                if chunk is not None:
                    yield chunk

    # ── Capabilities ────────────────────────────────────────────────

    def get_capabilities(self) -> list[str]:
        """Return the list of capability identifiers this provider supports."""
        return list(self._config.capabilities)

    def supports(self, capability: str) -> bool:
        """Check whether this provider supports a specific capability."""
        return capability in self._config.capabilities

    # ── Model Catalogue ─────────────────────────────────────────────

    def list_models(self) -> list[ModelInfo]:
        """Return all models available from this provider."""
        return list(self._config.models)

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Return detailed information for a specific model.

        Raises:
            KeyError: If the model ID is not found in the catalogue.
        """
        if model_id not in self._models_by_id:
            raise KeyError(f"Model not found: {model_id}")
        return self._models_by_id[model_id]

    # ── Quota & Rate Limits ─────────────────────────────────────────

    def check_quota(self) -> QuotaStatus:
        """Return current quota consumption. No limit enforced by default."""
        return QuotaStatus(used=self._request_count)

    def get_rate_limits(self) -> RateLimitStatus:
        """Return current rate-limit headroom. Unknown by default."""
        return RateLimitStatus()

    # ── Cost & Pricing ──────────────────────────────────────────────

    def get_pricing(self, model_id: str) -> ModelPricing:
        """Return pricing information for a specific model.

        Raises:
            KeyError: If the model or its pricing is not configured.
        """
        info = await self.get_model_info(model_id)
        if info.pricing is None:
            raise KeyError(f"No pricing configured for model: {model_id}")
        return info.pricing

    def report_usage(self, model_id: str, usage: TokenUsage) -> None:
        """Increment internal request and token counters."""
        self._request_count += 1
        self._tokens_used += usage.total_tokens

    # ── Error Classification ────────────────────────────────────────

    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify an error using configured retryable/non-retryable codes.

        Maps HTTP status codes to categories: ``rate_limit`` for 429,
        ``server_error`` for 5xx, ``client_error`` for 4xx, and
        ``unknown`` for everything else.
        """
        status_code = getattr(
            getattr(error, "response", None), "status_code", None
        )
        if status_code is None:
            return ErrorClassification(
                retryable=False, category="unknown"
            )

        if status_code in self._config.retryable_codes:
            retry_after = None
            if status_code == 429:
                resp = getattr(error, "response", None)
                if resp is not None:
                    retry_after_hdr = resp.headers.get("Retry-After")
                    if retry_after_hdr:
                        retry_after = float(retry_after_hdr)
            return ErrorClassification(
                retryable=True,
                category="rate_limit" if status_code == 429 else "server_error",
                retry_after=retry_after,
            )

        if status_code in self._config.non_retryable_codes:
            return ErrorClassification(
                retryable=False, category="client_error"
            )

        return ErrorClassification(retryable=False, category="unknown")

    def is_retryable(self, error: Exception) -> bool:
        """Return True if the error is eligible for retry."""
        return self.classify_error(error).retryable

    # ── Protected Hooks ─────────────────────────────────────────────

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a CompletionRequest into an OpenAI-format JSON payload.

        Override this method to adapt the request format for
        non-OpenAI-compatible APIs.
        """
        payload: dict = {
            "model": request.model,
            "messages": request.messages,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = request.tools
        if request.stream:
            payload["stream"] = True
        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Parse an OpenAI-format JSON response into a CompletionResponse.

        Override this method to handle custom response schemas.
        """
        usage_data = data.get("usage", {})
        raw_choices = data.get("choices", [])
        choices = []
        for raw in raw_choices:
            msg_data = raw.get("message")
            message = None
            if msg_data:
                message = ChatMessage(
                    role=msg_data.get("role", "assistant"),
                    content=msg_data.get("content"),
                    tool_calls=msg_data.get("tool_calls"),
                )
            choices.append(CompletionChoice(
                index=raw.get("index", 0),
                message=message,
                finish_reason=raw.get("finish_reason"),
            ))
        return CompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=choices,
            usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
        )

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for the request.

        Override to add custom headers or change the auth scheme.
        """
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _get_completion_endpoint(self) -> str:
        """Return the full URL for the chat completions endpoint.

        Override to change the URL path for non-OpenAI APIs.
        """
        base = self._config.base_url.rstrip("/")
        return f"{base}/v1/chat/completions"

    def _parse_sse_chunk(self, line: str) -> CompletionResponse | None:
        """Parse a single SSE data line into a partial CompletionResponse.

        Override to handle non-standard streaming formats. Return None
        to skip a chunk.
        """
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        raw_choices = data.get("choices", [])
        if not raw_choices:
            return None
        choices = []
        for raw in raw_choices:
            delta_data = raw.get("delta")
            delta = None
            if delta_data:
                delta = ChatMessage(
                    role=delta_data.get("role", "assistant"),
                    content=delta_data.get("content"),
                    tool_calls=delta_data.get("tool_calls"),
                )
            choices.append(CompletionChoice(
                index=raw.get("index", 0),
                delta=delta,
                finish_reason=raw.get("finish_reason"),
            ))
        return CompletionResponse(
            id=data.get("id", ""),
            model=data.get("model", ""),
            choices=choices,
            usage=TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            ),
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
```

### TypeScript

```typescript
import {
    AuthMethod,
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    ModelInfo,
    ModelPricing,
    ProviderConnector,
    QuotaStatus,
    RateLimitStatus,
    TokenUsage,
} from "../interfaces/provider";

/** Configuration for a BaseProvider instance. */
interface BaseProviderConfig {
    baseUrl: string;
    apiKey?: string;
    models?: ModelInfo[];
    timeout?: number;
    maxRetries?: number;
    authMethod?: string;
    retryableCodes?: number[];
    nonRetryableCodes?: number[];
    capabilities?: string[];    // default ["generation.text-generation.chat-completion"]
}

/**
 * Base implementation of the ProviderConnector interface.
 *
 * Provides an OpenAI-compatible default behavior for all methods.
 * Subclasses override protected hook methods to adapt to non-OpenAI
 * APIs without reimplementing transport, retries, or error handling.
 */
class BaseProvider implements ProviderConnector {
    protected config: Required<BaseProviderConfig>;
    private requestCount = 0;
    private tokensUsed = 0;
    private modelsById: Map<string, ModelInfo>;

    constructor(config: BaseProviderConfig) {
        this.config = {
            baseUrl: config.baseUrl,
            apiKey: config.apiKey ?? "",
            models: config.models ?? [],
            timeout: config.timeout ?? 30,
            maxRetries: config.maxRetries ?? 3,
            authMethod: config.authMethod ?? "api_key",
            retryableCodes: config.retryableCodes ?? [429, 500, 502, 503],
            nonRetryableCodes: config.nonRetryableCodes ?? [400, 401, 403],
            capabilities: config.capabilities ?? ["generation.text-generation.chat-completion"],
        };
        this.modelsById = new Map(
            this.config.models.map((m) => [m.id, m])
        );
    }

    // ── Model Execution ─────────────────────────────────────────

    /** Send a completion request and return the full response. */
    async complete(request: CompletionRequest): Promise<CompletionResponse> {
        const payload = this.buildRequestPayload(request);
        const headers = this.buildHeaders();
        const endpoint = this.getCompletionEndpoint();

        let lastError: Error | null = null;
        for (let attempt = 0; attempt <= this.config.maxRetries; attempt++) {
            try {
                const resp = await fetch(endpoint, {
                    method: "POST",
                    headers,
                    body: JSON.stringify(payload),
                    signal: AbortSignal.timeout(this.config.timeout * 1000),
                });
                if (!resp.ok) {
                    throw new HttpError(resp.status, await resp.text());
                }
                const data = await resp.json();
                const result = this.parseResponse(data);
                this.reportUsage(request.model, result.usage);
                return result;
            } catch (err) {
                lastError = err as Error;
                const classification = this.classifyError(lastError);
                if (!classification.retryable || attempt === this.config.maxRetries) {
                    throw lastError;
                }
                const delay = classification.retry_after ?? 2 ** attempt;
                await new Promise((r) => setTimeout(r, delay * 1000));
            }
        }
        throw lastError!;
    }

    /** Send a completion request and yield partial responses via SSE. */
    async *stream(request: CompletionRequest): AsyncIterable<CompletionResponse> {
        const payload = this.buildRequestPayload(request);
        payload.stream = true;
        const headers = this.buildHeaders();
        const endpoint = this.getCompletionEndpoint();

        const resp = await fetch(endpoint, {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
        });
        if (!resp.ok || !resp.body) {
            throw new HttpError(resp.status, "Stream request failed");
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const dataStr = line.slice(6).trim();
                if (dataStr === "[DONE]") return;
                const chunk = this.parseSseChunk(dataStr);
                if (chunk) yield chunk;
            }
        }
    }

    // ── Capabilities ────────────────────────────────────────────

    /** Return the list of capability identifiers this provider supports. */
    getCapabilities(): string[] {
        return [...this.config.capabilities];
    }

    /** Check whether this provider supports a specific capability. */
    supports(capability: string): boolean {
        return this.config.capabilities.includes(capability);
    }

    // ── Model Catalogue ─────────────────────────────────────────

    /** Return all models available from this provider. */
    async listModels(): Promise<ModelInfo[]> {
        return [...this.config.models];
    }

    /** Return detailed information for a specific model. */
    async getModelInfo(modelId: string): Promise<ModelInfo> {
        const info = this.modelsById.get(modelId);
        if (!info) throw new Error(`Model not found: ${modelId}`);
        return info;
    }

    // ── Quota & Rate Limits ─────────────────────────────────────

    /** Return current quota consumption. No limit enforced by default. */
    async checkQuota(): Promise<QuotaStatus> {
        return { used: this.requestCount };
    }

    /** Return current rate-limit headroom. Unknown by default. */
    async getRateLimits(): Promise<RateLimitStatus> {
        return {};
    }

    // ── Cost & Pricing ──────────────────────────────────────────

    /** Return pricing information for a specific model. */
    async getPricing(modelId: string): Promise<ModelPricing> {
        const info = await this.getModelInfo(modelId);
        if (!info.pricing) {
            throw new Error(`No pricing configured for model: ${modelId}`);
        }
        return info.pricing;
    }

    /** Increment internal request and token counters. */
    reportUsage(modelId: string, usage: TokenUsage): void {
        this.requestCount += 1;
        this.tokensUsed += usage.total_tokens;
    }

    // ── Error Classification ────────────────────────────────────

    /** Classify an error using configured retryable/non-retryable codes. */
    classifyError(error: Error): ErrorClassification {
        const status = (error as HttpError).statusCode;
        if (status === undefined) {
            return { retryable: false, category: "unknown" };
        }
        if (this.config.retryableCodes.includes(status)) {
            return {
                retryable: true,
                category: status === 429 ? "rate_limit" : "server_error",
                retry_after: status === 429 ? (error as HttpError).retryAfter : undefined,
            };
        }
        if (this.config.nonRetryableCodes.includes(status)) {
            return { retryable: false, category: "client_error" };
        }
        return { retryable: false, category: "unknown" };
    }

    /** Return true if the error is eligible for retry. */
    isRetryable(error: Error): boolean {
        return this.classifyError(error).retryable;
    }

    // ── Protected Hooks ─────────────────────────────────────────

    /** Translate a CompletionRequest into an OpenAI-format JSON payload. */
    protected buildRequestPayload(request: CompletionRequest): Record<string, unknown> {
        const payload: Record<string, unknown> = {
            model: request.model,
            messages: request.messages,
        };
        if (request.temperature !== undefined) payload.temperature = request.temperature;
        if (request.max_tokens !== undefined) payload.max_tokens = request.max_tokens;
        if (request.tools) payload.tools = request.tools;
        if (request.stream) payload.stream = true;
        return payload;
    }

    /** Parse an OpenAI-format JSON response into a CompletionResponse. */
    protected parseResponse(data: Record<string, unknown>): CompletionResponse {
        const usageData = (data.usage as Record<string, number>) ?? {};
        const rawChoices = (data.choices as Record<string, any>[]) ?? [];
        const choices = rawChoices.map((raw) => {
            const msg = raw.message;
            return {
                index: raw.index ?? 0,
                message: msg
                    ? { role: msg.role || "assistant", content: msg.content }
                    : undefined,
                finishReason: raw.finish_reason,
            };
        });
        return {
            id: (data.id as string) ?? "",
            model: (data.model as string) ?? "",
            choices,
            usage: {
                promptTokens: usageData.prompt_tokens ?? 0,
                completionTokens: usageData.completion_tokens ?? 0,
                totalTokens: usageData.total_tokens ?? 0,
            },
        };
    }

    /** Build HTTP headers for the request. */
    protected buildHeaders(): Record<string, string> {
        const headers: Record<string, string> = {
            "Content-Type": "application/json",
        };
        if (this.config.apiKey) {
            headers["Authorization"] = `Bearer ${this.config.apiKey}`;
        }
        return headers;
    }

    /** Return the full URL for the chat completions endpoint. */
    protected getCompletionEndpoint(): string {
        const base = this.config.baseUrl.replace(/\/+$/, "");
        return `${base}/v1/chat/completions`;
    }

    /** Parse a single SSE data line into a partial CompletionResponse. */
    protected parseSseChunk(line: string): CompletionResponse | null {
        try {
            const data = JSON.parse(line);
            const rawChoices = data.choices ?? [];
            if (rawChoices.length === 0) return null;
            const choices = rawChoices.map((raw: any) => {
                const delta = raw.delta;
                return {
                    index: raw.index ?? 0,
                    delta: delta
                        ? { role: delta.role || "assistant", content: delta.content }
                        : undefined,
                    finishReason: raw.finish_reason,
                };
            });
            return {
                id: data.id ?? "",
                model: data.model ?? "",
                choices,
                usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
            };
        } catch {
            return null;
        }
    }
}

/** HTTP error with status code for error classification. */
class HttpError extends Error {
    constructor(
        public readonly statusCode: number,
        message: string,
        public readonly retryAfter?: number
    ) {
        super(message);
        this.name = "HttpError";
    }
}
```

---

## BrowserBaseProvider

Browser-compatible equivalent of `BaseProvider`. Identical interface and protected hooks, but uses the Fetch API and `ReadableStream` instead of Node.js `http`/`https` modules and Node streams. Works in any environment that supports `fetch()` -- browsers, Deno, Cloudflare Workers, Bun.

> **Implements:** [ProviderConnector](../interfaces/Provider.md) (same as BaseProvider)

### How It Differs from BaseProvider

| Aspect | BaseProvider | BrowserBaseProvider |
|---|---|---|
| HTTP transport | Node.js `http`/`https` via `urllib` (Python) or built-in `http` (TS) | `fetch()` API |
| Streaming | Node.js streams / `AsyncIterator` with line-based SSE parsing | `ReadableStream` with `TextDecoderStream` and SSE parsing |
| Request timeout | `req.destroy()` / `socket.setTimeout()` | `AbortController` with `AbortSignal.timeout()` |
| CORS proxy | Not applicable | `proxyUrl` config prepends proxy URL to all API endpoints |
| Environment | Node.js only | Browser, Deno, Bun, Cloudflare Workers, any fetch-capable runtime |
| API surface | Identical | Identical |

### Configuration

```typescript
interface BrowserProviderConfig {
    baseUrl: string;
    apiKey: string;
    models: ModelInfo[];
    timeout: number;           // seconds, default 30
    maxRetries: number;        // default 3
    authMethod: string;        // default "api_key"
    retryableCodes: number[];  // default [429, 500, 502, 503]
    nonRetryableCodes: number[]; // default [400, 401, 403]
    capabilities: string[];    // default ["generation.text-generation.chat-completion"]
    proxyUrl?: string;         // optional CORS proxy URL prefix
}
```

The `proxyUrl` field is the only configuration difference from `BaseProviderConfig`. When set, all API requests are sent to `{proxyUrl}/{baseUrl}/path` instead of `{baseUrl}/path`. The proxy is expected to forward the request and add CORS headers to the response.

### Protected Hook Methods

All hooks from `BaseProvider` are available and work identically:

| Hook | Default | Override To |
|---|---|---|
| `_buildRequestPayload(request)` | OpenAI JSON format | Change request translation |
| `_parseResponse(data)` | Parse OpenAI JSON response | Handle custom response schemas |
| `_buildHeaders()` | `{"Authorization": "Bearer {apiKey}", "Content-Type": "application/json"}` | Add custom headers or change auth |
| `_getCompletionEndpoint()` | `"{baseUrl}/v1/chat/completions"` | Change the URL path |
| `_parseSseChunk(line)` | Parse `data: {...}` SSE lines | Handle non-standard streaming |

### When to Use Which Base Class

```
Is the provider used in a web browser or edge runtime?
├── Yes ──► BrowserBaseProvider
└── No
    └── Is it used in Node.js?
        └── Yes ──► BaseProvider
```

Both can be used in Deno and Bun. `BrowserBaseProvider` is the safer default for cross-runtime code since `fetch()` is available everywhere.

> **See also:** [Browser Usage Guide](../guides/BrowserUsage.md) for CORS proxy setup, security considerations, and browser-specific patterns.

---

## BaseRotationPolicy

The foundation for all rotation policies. Implements the three sub-interfaces -- `DeactivationPolicy`, `RecoveryPolicy`, and `SelectionStrategy` -- with threshold-based defaults: deactivate on consecutive failure count or error rate, recover after a cooldown period, and select by priority list with fallback to lowest error rate.

> **Implements:** [DeactivationPolicy + RecoveryPolicy + SelectionStrategy](../interfaces/RotationPolicy.md)

### Configuration

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseRotationPolicyConfig:
    """Configuration for a BaseRotationPolicy instance."""
    retry_limit: int = 3
    error_rate_threshold: float = 0.5
    error_codes: list[int] = field(default_factory=lambda: [429, 500, 503])
    request_limit: Optional[int] = None
    token_limit: Optional[int] = None
    budget_limit: Optional[float] = None
    cooldown_seconds: float = 60.0
    model_priority: list[str] = field(default_factory=list)
    provider_priority: list[str] = field(default_factory=list)
```

```typescript
/** Configuration for a BaseRotationPolicy instance. */
interface BaseRotationPolicyConfig {
    retryLimit?: number;             // default 3
    errorRateThreshold?: number;     // default 0.5
    errorCodes?: number[];           // default [429, 500, 503]
    requestLimit?: number;           // no limit by default
    tokenLimit?: number;             // no limit by default
    budgetLimit?: number;            // no limit by default
    cooldownSeconds?: number;        // default 60
    modelPriority?: string[];        // ordered model preference
    providerPriority?: string[];     // ordered provider preference
}
```

### Methods and Default Behavior

| Method | Default Behavior |
|---|---|
| `should_deactivate(snapshot)` | Return `True` if `failure_count >= retry_limit` OR `error_rate >= error_rate_threshold` OR quota/budget/token limits exceeded |
| `get_reason(snapshot)` | Return the first matching `DeactivationReason` or `None` |
| `should_recover(snapshot)` | Return `True` if `cooldown_remaining` is `None` or `<= 0` |
| `get_recovery_schedule(snapshot)` | Return `now + cooldown_seconds` if model is in standby |
| `select(candidates, request)` | Choose highest-scored candidate via `score()` |
| `score(candidate, request)` | Score by priority position (if listed), then by lowest error rate |

### Python

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from modelmesh.interfaces.rotation_policy import (
    CompletionRequest,
    DeactivationPolicy,
    DeactivationReason,
    ModelSnapshot,
    RecoveryPolicy,
    SelectionResult,
    SelectionStrategy,
)


@dataclass
class BaseRotationPolicyConfig:
    """Configuration for a BaseRotationPolicy instance."""
    retry_limit: int = 3
    error_rate_threshold: float = 0.5
    error_codes: list[int] = field(default_factory=lambda: [429, 500, 503])
    request_limit: Optional[int] = None
    token_limit: Optional[int] = None
    budget_limit: Optional[float] = None
    cooldown_seconds: float = 60.0
    model_priority: list[str] = field(default_factory=list)
    provider_priority: list[str] = field(default_factory=list)


class BaseRotationPolicy(DeactivationPolicy, RecoveryPolicy, SelectionStrategy):
    """Base implementation of all three rotation policy sub-interfaces.

    Provides threshold-based deactivation, cooldown-based recovery, and
    priority-list selection with error-rate fallback. Subclasses override
    individual methods to implement custom logic without replacing the
    entire policy.
    """

    def __init__(self, config: BaseRotationPolicyConfig) -> None:
        self._config = config

    # ── Deactivation ────────────────────────────────────────────────

    def should_deactivate(self, snapshot: ModelSnapshot) -> bool:
        """Return True if the model should be moved to standby.

        Checks failure count, error rate, request limit, token limit,
        and budget limit in that order.
        """
        return self.get_reason(snapshot) is not None

    def get_reason(self, snapshot: ModelSnapshot) -> DeactivationReason | None:
        """Return the first matching deactivation reason, or None.

        Evaluation order:
        1. Consecutive failure count >= retry_limit
        2. Error rate >= error_rate_threshold
        3. Request limit exceeded
        4. Token limit exceeded
        5. Budget limit exceeded
        """
        if snapshot.failure_count >= self._config.retry_limit:
            return DeactivationReason.ERROR_THRESHOLD

        if snapshot.error_rate >= self._config.error_rate_threshold:
            return DeactivationReason.ERROR_THRESHOLD

        if (
            self._config.request_limit is not None
            and snapshot.quota_used >= self._config.request_limit
        ):
            return DeactivationReason.REQUEST_LIMIT

        if (
            self._config.token_limit is not None
            and snapshot.tokens_used >= self._config.token_limit
        ):
            return DeactivationReason.TOKEN_LIMIT

        if (
            self._config.budget_limit is not None
            and snapshot.cost_accumulated >= self._config.budget_limit
        ):
            return DeactivationReason.BUDGET_EXCEEDED

        return None

    # ── Recovery ────────────────────────────────────────────────────

    def should_recover(self, snapshot: ModelSnapshot) -> bool:
        """Return True if cooldown has expired and the model can be reactivated."""
        if snapshot.cooldown_remaining is None:
            return True
        return snapshot.cooldown_remaining <= 0

    def get_recovery_schedule(self, snapshot: ModelSnapshot) -> datetime | None:
        """Return the datetime when the model should next be checked for recovery.

        Returns ``now + cooldown_seconds`` for standby models, or None
        for active models.
        """
        from modelmesh.interfaces.rotation_policy import ModelStatus

        if snapshot.status != ModelStatus.STANDBY:
            return None
        return datetime.utcnow() + timedelta(
            seconds=self._config.cooldown_seconds
        )

    # ── Selection ───────────────────────────────────────────────────

    def select(
        self, candidates: list[ModelSnapshot], request: CompletionRequest
    ) -> SelectionResult:
        """Select the highest-scored candidate for the given request.

        Raises:
            ValueError: If the candidate list is empty.
        """
        if not candidates:
            raise ValueError("No candidates available for selection")

        best = max(candidates, key=lambda c: self.score(c, request))
        return SelectionResult(
            model_id=best.model_id,
            provider_id=best.provider_id,
            score=self.score(best, request),
            reason=self._selection_reason(best),
        )

    def score(self, candidate: ModelSnapshot, request: CompletionRequest) -> float:
        """Score a candidate by priority position, then by lowest error rate.

        Priority-listed models receive scores 1000+ (higher for earlier
        position). Non-priority models are scored as ``1.0 - error_rate``.
        """
        # Check model priority list first
        if candidate.model_id in self._config.model_priority:
            idx = self._config.model_priority.index(candidate.model_id)
            return 1000.0 + (len(self._config.model_priority) - idx)

        # Check provider priority list
        if candidate.provider_id in self._config.provider_priority:
            idx = self._config.provider_priority.index(candidate.provider_id)
            return 500.0 + (len(self._config.provider_priority) - idx)

        # Fallback: lowest error rate wins
        return 1.0 - candidate.error_rate

    def _selection_reason(self, candidate: ModelSnapshot) -> str:
        """Return a human-readable reason for why a candidate was selected."""
        if candidate.model_id in self._config.model_priority:
            return "model_priority"
        if candidate.provider_id in self._config.provider_priority:
            return "provider_priority"
        return "lowest_error_rate"
```

### TypeScript

```typescript
import {
    CompletionRequest,
    DeactivationPolicy,
    DeactivationReason,
    ModelSnapshot,
    ModelStatus,
    RecoveryPolicy,
    SelectionResult,
    SelectionStrategy,
} from "../interfaces/rotation_policy";

/** Configuration for a BaseRotationPolicy instance. */
interface BaseRotationPolicyConfig {
    retryLimit?: number;
    errorRateThreshold?: number;
    errorCodes?: number[];
    requestLimit?: number;
    tokenLimit?: number;
    budgetLimit?: number;
    cooldownSeconds?: number;
    modelPriority?: string[];
    providerPriority?: string[];
}

/**
 * Base implementation of all three rotation policy sub-interfaces.
 *
 * Provides threshold-based deactivation, cooldown-based recovery, and
 * priority-list selection with error-rate fallback.
 */
class BaseRotationPolicy
    implements DeactivationPolicy, RecoveryPolicy, SelectionStrategy
{
    protected config: Required<BaseRotationPolicyConfig>;

    constructor(config: BaseRotationPolicyConfig = {}) {
        this.config = {
            retryLimit: config.retryLimit ?? 3,
            errorRateThreshold: config.errorRateThreshold ?? 0.5,
            errorCodes: config.errorCodes ?? [429, 500, 503],
            requestLimit: config.requestLimit ?? Infinity,
            tokenLimit: config.tokenLimit ?? Infinity,
            budgetLimit: config.budgetLimit ?? Infinity,
            cooldownSeconds: config.cooldownSeconds ?? 60,
            modelPriority: config.modelPriority ?? [],
            providerPriority: config.providerPriority ?? [],
        };
    }

    // ── Deactivation ────────────────────────────────────────────

    /** Return true if the model should be moved to standby. */
    shouldDeactivate(snapshot: ModelSnapshot): boolean {
        return this.getReason(snapshot) !== null;
    }

    /** Return the first matching deactivation reason, or null. */
    getReason(snapshot: ModelSnapshot): DeactivationReason | null {
        if (snapshot.failure_count >= this.config.retryLimit) {
            return DeactivationReason.ERROR_THRESHOLD;
        }
        if (snapshot.error_rate >= this.config.errorRateThreshold) {
            return DeactivationReason.ERROR_THRESHOLD;
        }
        if (snapshot.quota_used >= this.config.requestLimit) {
            return DeactivationReason.REQUEST_LIMIT;
        }
        if (snapshot.tokens_used >= this.config.tokenLimit) {
            return DeactivationReason.TOKEN_LIMIT;
        }
        if (snapshot.cost_accumulated >= this.config.budgetLimit) {
            return DeactivationReason.BUDGET_EXCEEDED;
        }
        return null;
    }

    // ── Recovery ────────────────────────────────────────────────

    /** Return true if cooldown has expired and the model can be reactivated. */
    shouldRecover(snapshot: ModelSnapshot): boolean {
        if (snapshot.cooldown_remaining === undefined) return true;
        return snapshot.cooldown_remaining <= 0;
    }

    /** Return the datetime when the model should next be checked for recovery. */
    getRecoverySchedule(snapshot: ModelSnapshot): Date | null {
        if (snapshot.status !== ModelStatus.STANDBY) return null;
        return new Date(Date.now() + this.config.cooldownSeconds * 1000);
    }

    // ── Selection ───────────────────────────────────────────────

    /** Select the highest-scored candidate for the given request. */
    select(
        candidates: ModelSnapshot[],
        request: CompletionRequest
    ): SelectionResult {
        if (candidates.length === 0) {
            throw new Error("No candidates available for selection");
        }

        let best = candidates[0];
        let bestScore = this.score(best, request);
        for (let i = 1; i < candidates.length; i++) {
            const s = this.score(candidates[i], request);
            if (s > bestScore) {
                best = candidates[i];
                bestScore = s;
            }
        }

        return {
            model_id: best.model_id,
            provider_id: best.provider_id,
            score: bestScore,
            reason: this.selectionReason(best),
        };
    }

    /** Score a candidate by priority position, then by lowest error rate. */
    score(candidate: ModelSnapshot, request: CompletionRequest): number {
        const modelIdx = this.config.modelPriority.indexOf(candidate.model_id);
        if (modelIdx >= 0) {
            return 1000 + (this.config.modelPriority.length - modelIdx);
        }

        const providerIdx = this.config.providerPriority.indexOf(candidate.provider_id);
        if (providerIdx >= 0) {
            return 500 + (this.config.providerPriority.length - providerIdx);
        }

        return 1.0 - candidate.error_rate;
    }

    private selectionReason(candidate: ModelSnapshot): string {
        if (this.config.modelPriority.includes(candidate.model_id)) {
            return "model_priority";
        }
        if (this.config.providerPriority.includes(candidate.provider_id)) {
            return "provider_priority";
        }
        return "lowest_error_rate";
    }
}
```

---

## BaseSecretStore

The foundation for all secret store connectors. Implements the `SecretStoreConnector` interface with an in-memory dictionary backend and optional caching. Subclasses override the single `_resolve(name)` hook to read secrets from files, vaults, or cloud services. The base class handles cache management and missing-secret policy.

> **Implements:** [SecretStoreConnector](../interfaces/SecretStore.md)

### Configuration

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseSecretStoreConfig:
    """Configuration for a BaseSecretStore instance."""
    secrets: dict[str, str] = field(default_factory=dict)
    cache_enabled: bool = True
    cache_ttl_ms: int = 300_000
    fail_on_missing: bool = True
```

```typescript
/** Configuration for a BaseSecretStore instance. */
interface BaseSecretStoreConfig {
    secrets?: Record<string, string>;  // pre-loaded secrets
    cacheEnabled?: boolean;            // default true
    cacheTtlMs?: number;               // default 300000
    failOnMissing?: boolean;           // default true
}
```

### Methods and Default Behavior

| Method | Default Behavior |
|---|---|
| `get(name)` | Check cache, then call `_resolve(name)`, cache the result, and return the value. Raise `KeyError` if missing and `fail_on_missing` is `True` |

### Protected Hook Methods

| Hook | Default | Override To |
|---|---|---|
| `_resolve(name)` | Look up `name` in `config.secrets` dict | Read from file, vault, cloud secret manager, or environment variable |

### Python

```python
import time
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.interfaces.secret_store import SecretStoreConnector


@dataclass
class BaseSecretStoreConfig:
    """Configuration for a BaseSecretStore instance."""
    secrets: dict[str, str] = field(default_factory=dict)
    cache_enabled: bool = True
    cache_ttl_ms: int = 300_000
    fail_on_missing: bool = True


class BaseSecretStore(SecretStoreConnector):
    """Base implementation of the SecretStoreConnector interface.

    Provides in-memory secret storage with optional TTL-based caching.
    Subclasses override ``_resolve`` to read secrets from external
    backends (files, vaults, cloud services).
    """

    def __init__(self, config: BaseSecretStoreConfig) -> None:
        self._config = config
        self._cache: dict[str, tuple[str, float]] = {}

    def get(self, name: str) -> str:
        """Resolve a secret by name and return its value.

        Checks the cache first (if enabled), then delegates to
        ``_resolve``. Caches the result with a TTL if caching is
        enabled.

        Raises:
            KeyError: If the secret is not found and fail_on_missing
                      is True.
        """
        # Check cache
        if self._config.cache_enabled and name in self._cache:
            value, expires_at = self._cache[name]
            if time.monotonic() < expires_at:
                return value
            del self._cache[name]

        # Resolve from backend
        value = self._resolve(name)
        if value is None:
            if self._config.fail_on_missing:
                raise KeyError(f"Secret not found: {name}")
            return ""

        # Cache the result
        if self._config.cache_enabled:
            expires_at = time.monotonic() + (self._config.cache_ttl_ms / 1000.0)
            self._cache[name] = (value, expires_at)

        return value

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret by name from the configured backend.

        The default implementation looks up the name in the
        ``config.secrets`` dictionary. Override this method to read
        from files, environment variables, vaults, or cloud services.

        Returns:
            The secret value, or None if not found.
        """
        return self._config.secrets.get(name)

    def clear_cache(self) -> None:
        """Clear all cached secret values."""
        self._cache.clear()
```

### TypeScript

```typescript
import { SecretStoreConnector } from "../interfaces/secret_store";

/** Configuration for a BaseSecretStore instance. */
interface BaseSecretStoreConfig {
    secrets?: Record<string, string>;
    cacheEnabled?: boolean;
    cacheTtlMs?: number;
    failOnMissing?: boolean;
}

/**
 * Base implementation of the SecretStoreConnector interface.
 *
 * Provides in-memory secret storage with optional TTL-based caching.
 * Subclasses override `resolve` to read secrets from external backends.
 */
class BaseSecretStore implements SecretStoreConnector {
    protected config: Required<BaseSecretStoreConfig>;
    private cache = new Map<string, { value: string; expiresAt: number }>();

    constructor(config: BaseSecretStoreConfig = {}) {
        this.config = {
            secrets: config.secrets ?? {},
            cacheEnabled: config.cacheEnabled ?? true,
            cacheTtlMs: config.cacheTtlMs ?? 300_000,
            failOnMissing: config.failOnMissing ?? true,
        };
    }

    /**
     * Resolve a secret by name and return its value.
     * @throws {Error} If the secret is not found and failOnMissing is true.
     */
    get(name: string): string {
        // Check cache
        if (this.config.cacheEnabled) {
            const cached = this.cache.get(name);
            if (cached && Date.now() < cached.expiresAt) {
                return cached.value;
            }
            if (cached) this.cache.delete(name);
        }

        // Resolve from backend
        const value = this.resolve(name);
        if (value === null) {
            if (this.config.failOnMissing) {
                throw new Error(`Secret not found: ${name}`);
            }
            return "";
        }

        // Cache the result
        if (this.config.cacheEnabled) {
            this.cache.set(name, {
                value,
                expiresAt: Date.now() + this.config.cacheTtlMs,
            });
        }

        return value;
    }

    /**
     * Resolve a secret by name from the configured backend.
     * Override to read from files, vaults, or cloud services.
     * @returns The secret value, or null if not found.
     */
    protected resolve(name: string): string | null {
        return this.config.secrets[name] ?? null;
    }

    /** Clear all cached secret values. */
    clearCache(): void {
        this.cache.clear();
    }
}
```

---

## BaseStorage

The foundation for all storage connectors. Implements the full `StorageConnector` interface (Persistence, Inventory, StatQuery) plus the optional `Locking` interface using an in-memory dictionary backend. Handles serialization format selection and optional compression. Subclasses override persistence methods to write to files, databases, or cloud storage.

> **Implements:** [StorageConnector + Locking](../interfaces/Storage.md)

### Configuration

```python
from dataclasses import dataclass


@dataclass
class BaseStorageConfig:
    """Configuration for a BaseStorage instance."""
    format: str = "json"
    compression: bool = False
    locking_enabled: bool = True
    lock_timeout_seconds: float = 30.0
```

```typescript
/** Configuration for a BaseStorage instance. */
interface BaseStorageConfig {
    format?: string;              // "json" | "yaml" | "msgpack", default "json"
    compression?: boolean;        // default false
    lockingEnabled?: boolean;     // default true
    lockTimeoutSeconds?: number;  // default 30
}
```

### Methods and Default Behavior

| Method | Default Behavior |
|---|---|
| `load(key)` | Return entry from in-memory dict, or `None` if missing |
| `save(key, entry)` | Store entry in in-memory dict with current timestamp |
| `list(prefix)` | Return keys matching prefix, or all keys if `None` |
| `delete(key)` | Remove key from dict; return `True` if it existed |
| `stat(key)` | Return `EntryMetadata` (size, last_modified) without loading data |
| `exists(key)` | Return `True` if key is in the dict |
| `acquire(key, timeout)` | Create a `LockHandle` and mark key as locked |
| `release(lock)` | Remove the lock from the key |
| `is_locked(key)` | Return `True` if the key is currently locked |

### Python

```python
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from modelmesh.interfaces.storage import (
    EntryMetadata,
    Inventory,
    LockHandle,
    Locking,
    Persistence,
    StatQuery,
    StorageConnector,
    StorageEntry,
)


@dataclass
class BaseStorageConfig:
    """Configuration for a BaseStorage instance."""
    format: str = "json"
    compression: bool = False
    locking_enabled: bool = True
    lock_timeout_seconds: float = 30.0


class BaseStorage(StorageConnector, Locking):
    """Base implementation of the StorageConnector and Locking interfaces.

    Provides an in-memory storage backend with JSON serialization,
    optional compression, and advisory locking. Subclasses override
    persistence methods to write to files, databases, or cloud storage.
    """

    def __init__(self, config: BaseStorageConfig) -> None:
        self._config = config
        self._store: dict[str, StorageEntry] = {}
        self._timestamps: dict[str, datetime] = {}
        self._locks: dict[str, LockHandle] = {}

    # ── Persistence ─────────────────────────────────────────────────

    async def load(self, key: str) -> StorageEntry | None:
        """Load a stored entry by key, or return None if not found."""
        return self._store.get(key)

    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save an entry under the given key. Overwrites if the key exists.

        Applies compression if enabled in configuration.
        """
        if self._config.compression:
            import gzip
            entry = StorageEntry(
                key=entry.key,
                data=gzip.compress(entry.data),
                metadata={**entry.metadata, "_compressed": True},
            )
        self._store[key] = entry
        self._timestamps[key] = datetime.utcnow()

    # ── Inventory ───────────────────────────────────────────────────

    async def list(self, prefix: str | None = None) -> list[str]:
        """Return keys matching the optional prefix, or all keys."""
        if prefix is None:
            return list(self._store.keys())
        return [k for k in self._store if k.startswith(prefix)]

    async def delete(self, key: str) -> bool:
        """Delete the entry at the given key. Return True if it existed."""
        if key in self._store:
            del self._store[key]
            self._timestamps.pop(key, None)
            self._locks.pop(key, None)
            return True
        return False

    # ── Stat Query ──────────────────────────────────────────────────

    async def stat(self, key: str) -> EntryMetadata | None:
        """Return metadata for the given key, or None if not found."""
        entry = self._store.get(key)
        if entry is None:
            return None
        return EntryMetadata(
            key=key,
            size=len(entry.data),
            last_modified=self._timestamps.get(key, datetime.utcnow()),
            content_type=self._config.format,
        )

    async def exists(self, key: str) -> bool:
        """Return True if an entry exists at the given key."""
        return key in self._store

    # ── Locking ─────────────────────────────────────────────────────

    async def acquire(self, key: str, timeout: float | None = None) -> LockHandle:
        """Acquire an advisory lock on the given key.

        Args:
            key: The storage key to lock.
            timeout: Maximum seconds to wait. Defaults to config value.

        Raises:
            TimeoutError: If the lock cannot be acquired within the timeout.
        """
        if not self._config.locking_enabled:
            raise RuntimeError("Locking is disabled in configuration")

        effective_timeout = timeout or self._config.lock_timeout_seconds

        if key in self._locks:
            existing = self._locks[key]
            if (
                existing.expires_at is not None
                and datetime.utcnow() > existing.expires_at
            ):
                del self._locks[key]
            else:
                import asyncio
                deadline = datetime.utcnow() + timedelta(seconds=effective_timeout)
                while key in self._locks and datetime.utcnow() < deadline:
                    await asyncio.sleep(0.1)
                if key in self._locks:
                    raise TimeoutError(
                        f"Could not acquire lock on '{key}' within {effective_timeout}s"
                    )

        now = datetime.utcnow()
        handle = LockHandle(
            key=key,
            lock_id=str(uuid.uuid4()),
            acquired_at=now,
            expires_at=now + timedelta(seconds=effective_timeout),
        )
        self._locks[key] = handle
        return handle

    async def release(self, lock: LockHandle) -> None:
        """Release a previously acquired lock."""
        if lock.key in self._locks and self._locks[lock.key].lock_id == lock.lock_id:
            del self._locks[lock.key]

    async def is_locked(self, key: str) -> bool:
        """Return True if the given key is currently locked."""
        if key not in self._locks:
            return False
        handle = self._locks[key]
        if handle.expires_at is not None and datetime.utcnow() > handle.expires_at:
            del self._locks[key]
            return False
        return True
```

### TypeScript

```typescript
import {
    EntryMetadata,
    LockHandle,
    Locking,
    StorageConnector,
    StorageEntry,
} from "../interfaces/storage";

/** Configuration for a BaseStorage instance. */
interface BaseStorageConfig {
    format?: string;
    compression?: boolean;
    lockingEnabled?: boolean;
    lockTimeoutSeconds?: number;
}

/**
 * Base implementation of the StorageConnector and Locking interfaces.
 *
 * Provides an in-memory storage backend with JSON serialization,
 * optional compression, and advisory locking.
 */
class BaseStorage implements StorageConnector, Locking {
    protected config: Required<BaseStorageConfig>;
    private store = new Map<string, StorageEntry>();
    private timestamps = new Map<string, Date>();
    private locks = new Map<string, LockHandle>();

    constructor(config: BaseStorageConfig = {}) {
        this.config = {
            format: config.format ?? "json",
            compression: config.compression ?? false,
            lockingEnabled: config.lockingEnabled ?? true,
            lockTimeoutSeconds: config.lockTimeoutSeconds ?? 30,
        };
    }

    // ── Persistence ─────────────────────────────────────────────

    /** Load a stored entry by key, or return null if not found. */
    async load(key: string): Promise<StorageEntry | null> {
        return this.store.get(key) ?? null;
    }

    /** Save an entry under the given key. Overwrites if the key exists. */
    async save(key: string, entry: StorageEntry): Promise<void> {
        this.store.set(key, entry);
        this.timestamps.set(key, new Date());
    }

    // ── Inventory ───────────────────────────────────────────────

    /** Return keys matching the optional prefix, or all keys. */
    async list(prefix?: string): Promise<string[]> {
        const keys = Array.from(this.store.keys());
        if (prefix === undefined) return keys;
        return keys.filter((k) => k.startsWith(prefix));
    }

    /** Delete the entry at the given key. Return true if it existed. */
    async delete(key: string): Promise<boolean> {
        const existed = this.store.has(key);
        this.store.delete(key);
        this.timestamps.delete(key);
        this.locks.delete(key);
        return existed;
    }

    // ── Stat Query ──────────────────────────────────────────────

    /** Return metadata for the given key, or null if not found. */
    async stat(key: string): Promise<EntryMetadata | null> {
        const entry = this.store.get(key);
        if (!entry) return null;
        return {
            key,
            size: entry.data.byteLength,
            last_modified: this.timestamps.get(key) ?? new Date(),
            content_type: this.config.format,
        };
    }

    /** Return true if an entry exists at the given key. */
    async exists(key: string): Promise<boolean> {
        return this.store.has(key);
    }

    // ── Locking ─────────────────────────────────────────────────

    /**
     * Acquire an advisory lock on the given key.
     * @throws {Error} If the lock cannot be acquired within the timeout.
     */
    async acquire(key: string, timeout?: number): Promise<LockHandle> {
        if (!this.config.lockingEnabled) {
            throw new Error("Locking is disabled in configuration");
        }

        const effectiveTimeout = timeout ?? this.config.lockTimeoutSeconds;
        const deadline = Date.now() + effectiveTimeout * 1000;

        // Wait for existing lock to expire or be released
        while (this.locks.has(key)) {
            const existing = this.locks.get(key)!;
            if (existing.expires_at && new Date() > existing.expires_at) {
                this.locks.delete(key);
                break;
            }
            if (Date.now() >= deadline) {
                throw new Error(
                    `Could not acquire lock on '${key}' within ${effectiveTimeout}s`
                );
            }
            await new Promise((r) => setTimeout(r, 100));
        }

        const now = new Date();
        const handle: LockHandle = {
            key,
            lock_id: crypto.randomUUID(),
            acquired_at: now,
            expires_at: new Date(now.getTime() + effectiveTimeout * 1000),
        };
        this.locks.set(key, handle);
        return handle;
    }

    /** Release a previously acquired lock. */
    async release(lock: LockHandle): Promise<void> {
        const existing = this.locks.get(lock.key);
        if (existing && existing.lock_id === lock.lock_id) {
            this.locks.delete(lock.key);
        }
    }

    /** Return true if the given key is currently locked. */
    async isLocked(key: string): Promise<boolean> {
        const handle = this.locks.get(key);
        if (!handle) return false;
        if (handle.expires_at && new Date() > handle.expires_at) {
            this.locks.delete(key);
            return false;
        }
        return true;
    }
}
```

---

## BaseObservability

The foundation for all observability connectors. Implements the full `ObservabilityConnector` interface (Events, Logging, Statistics, Tracing) with configurable event filtering, log-level control, severity-based trace filtering, secret redaction, and buffered statistics flushing. Subclasses override five protected hook methods (`_format_event`, `_format_log`, `_format_stats`, `_format_trace`, `_write`) to change output format and destination without reimplementing filtering or buffering logic.

> **Implements:** [ObservabilityConnector](../interfaces/Observability.md)

### Configuration

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseObservabilityConfig:
    """Configuration for a BaseObservability instance."""
    event_filter: list[str] = field(default_factory=list)
    log_level: str = "metadata"
    min_severity: str = "info"
    redact_secrets: bool = True
    flush_interval_seconds: float = 60.0
    scopes: list[str] = field(default_factory=lambda: ["model", "provider", "pool"])
```

```typescript
/** Configuration for a BaseObservability instance. */
interface BaseObservabilityConfig {
    eventFilter?: string[];          // empty = all events
    logLevel?: string;               // "metadata" | "summary" | "full", default "metadata"
    minSeverity?: string;            // "debug" | "info" | "warning" | "error" | "critical", default "info"
    redactSecrets?: boolean;         // default true
    flushIntervalSeconds?: number;   // default 60
    scopes?: string[];               // default ["model", "provider", "pool"]
}
```

### Methods and Default Behavior

| Method | Default Behavior |
|---|---|
| `emit(event)` | Filter by `event_filter` (pass all if empty), format via `_format_event`, write via `_write` |
| `log(entry)` | Redact secrets if enabled, format via `_format_log`, write via `_write` |
| `flush(stats)` | Filter by `scopes`, format via `_format_stats`, write via `_write` |
| `trace(entry)` | Filter by `min_severity` (discard entries below threshold), format via `_format_trace`, redact secrets if enabled, write via `_write` |

### Protected Hook Methods

| Hook | Default | Override To |
|---|---|---|
| `_format_event(event)` | JSON string with timestamp, type, model, provider, pool | Change event serialization (e.g., structured log, protobuf) |
| `_format_log(entry)` | JSON string filtered by `log_level` | Change log format or add fields |
| `_format_stats(scope_id, stats)` | JSON string with scope and all metric fields | Change statistics format |
| `_format_trace(entry)` | JSON string with severity, timestamp, component, message, metadata, error | Change trace format or add fields |
| `_write(line)` | No-op (subclasses must override) | Write to console, file, HTTP endpoint, message queue |

### Python

```python
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.interfaces.observability import (
    AggregateStats,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)


@dataclass
class BaseObservabilityConfig:
    """Configuration for a BaseObservability instance."""
    event_filter: list[str] = field(default_factory=list)
    log_level: str = "metadata"
    min_severity: str = "info"
    redact_secrets: bool = True
    flush_interval_seconds: float = 60.0
    scopes: list[str] = field(default_factory=lambda: ["model", "provider", "pool"])


class BaseObservability(ObservabilityConnector):
    """Base implementation of the ObservabilityConnector interface.

    Provides event filtering, log-level control, severity-based trace
    filtering, secret redaction, and scope-based statistics flushing.
    Subclasses override the five protected hook methods to change output
    format and destination.
    """

    _SECRET_PATTERN = re.compile(
        r'("(?:api_key|token|secret|password|authorization)":\s*")([^"]+)(")',
        re.IGNORECASE,
    )

    _SEVERITY_ORDER = {
        Severity.DEBUG: 0,
        Severity.INFO: 1,
        Severity.WARNING: 2,
        Severity.ERROR: 3,
        Severity.CRITICAL: 4,
    }

    def __init__(self, config: BaseObservabilityConfig) -> None:
        self._config = config

    # ── Events ──────────────────────────────────────────────────────

    def emit(self, event: RoutingEvent) -> None:
        """Emit a routing event to the configured output.

        Events are filtered against ``event_filter`` (if non-empty),
        formatted via ``_format_event``, and written via ``_write``.
        """
        if self._config.event_filter:
            if event.event_type.value not in self._config.event_filter:
                return

        line = self._format_event(event)
        if self._config.redact_secrets:
            line = self._redact(line)
        self._write(line)

    # ── Logging ─────────────────────────────────────────────────────

    def log(self, entry: RequestLogEntry) -> None:
        """Record a request/response log entry.

        Applies log-level filtering, redacts secrets if enabled,
        formats via ``_format_log``, and writes via ``_write``.
        """
        line = self._format_log(entry)
        if self._config.redact_secrets:
            line = self._redact(line)
        self._write(line)

    # ── Statistics ──────────────────────────────────────────────────

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Flush buffered aggregate statistics to the configured output.

        Filters scopes against ``config.scopes`` and formats each
        scope via ``_format_stats``.
        """
        for scope_id, aggregate in stats.items():
            line = self._format_stats(scope_id, aggregate)
            self._write(line)

    # ── Tracing ────────────────────────────────────────────────────

    def trace(self, entry: TraceEntry) -> None:
        """Record a trace entry, filtering by minimum severity.

        Entries whose severity is below ``config.min_severity`` are
        discarded. Remaining entries are formatted via ``_format_trace``,
        redacted if enabled, and written via ``_write``.
        """
        min_level = self._SEVERITY_ORDER.get(
            Severity(self._config.min_severity), 1
        )
        entry_level = self._SEVERITY_ORDER.get(entry.severity, 0)
        if entry_level < min_level:
            return
        line = self._format_trace(entry)
        if self._config.redact_secrets:
            line = self._redact(line)
        self._write(line)

    # ── Protected Hooks ─────────────────────────────────────────────

    def _format_event(self, event: RoutingEvent) -> str:
        """Format a routing event as a JSON string.

        Override to change event serialization format.
        """
        return json.dumps(
            {
                "type": "event",
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "model_id": event.model_id,
                "provider_id": event.provider_id,
                "pool_id": event.pool_id,
                "metadata": event.metadata,
            },
            default=str,
        )

    def _format_log(self, entry: RequestLogEntry) -> str:
        """Format a log entry as a JSON string filtered by log level.

        Log levels control which fields are included:
        - ``metadata``: timestamp, model_id, provider_id, status_code, latency_ms
        - ``summary``: metadata + tokens_in, tokens_out, cost, capability
        - ``full``: all fields including error details

        Override to change log format or add custom fields.
        """
        data: dict = {
            "type": "log",
            "timestamp": entry.timestamp.isoformat(),
            "model_id": entry.model_id,
            "provider_id": entry.provider_id,
            "status_code": entry.status_code,
            "latency_ms": entry.latency_ms,
        }

        if self._config.log_level in ("summary", "full"):
            data["tokens_in"] = entry.tokens_in
            data["tokens_out"] = entry.tokens_out
            data["cost"] = entry.cost
            data["capability"] = entry.capability
            data["delivery_mode"] = entry.delivery_mode

        if self._config.log_level == "full":
            data["error"] = entry.error

        return json.dumps(data, default=str)

    def _format_stats(self, scope_id: str, stats: AggregateStats) -> str:
        """Format aggregate statistics as a JSON string.

        Override to change statistics serialization format.
        """
        return json.dumps(
            {
                "type": "stats",
                "scope_id": scope_id,
                "requests_total": stats.requests_total,
                "requests_success": stats.requests_success,
                "requests_failed": stats.requests_failed,
                "tokens_in": stats.tokens_in,
                "tokens_out": stats.tokens_out,
                "cost_total": stats.cost_total,
                "latency_avg": stats.latency_avg,
                "latency_p95": stats.latency_p95,
                "downtime_total": stats.downtime_total,
                "rotation_events": stats.rotation_events,
            },
            default=str,
        )

    def _format_trace(self, entry: TraceEntry) -> str:
        """Format a trace entry as a JSON string.

        Override to change trace serialization format.
        """
        data = {
            "type": "trace",
            "severity": entry.severity.value,
            "timestamp": entry.timestamp.isoformat(),
            "component": entry.component,
            "message": entry.message,
        }
        if entry.metadata:
            data["metadata"] = entry.metadata
        if entry.error:
            data["error"] = entry.error
        return json.dumps(data, default=str)

    def _write(self, line: str) -> None:
        """Write a formatted line to the output destination.

        The default implementation is a no-op. Subclasses must
        override this method to write to console, file, HTTP
        endpoint, or message queue.
        """
        pass

    def _redact(self, text: str) -> str:
        """Redact secret values from a formatted string."""
        return self._SECRET_PATTERN.sub(r"\1***REDACTED***\3", text)
```

### TypeScript

```typescript
import {
    AggregateStats,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
} from "../interfaces/observability";

/** Configuration for a BaseObservability instance. */
interface BaseObservabilityConfig {
    eventFilter?: string[];
    logLevel?: string;
    minSeverity?: string;            // "debug" | "info" | "warning" | "error" | "critical", default "info"
    redactSecrets?: boolean;
    flushIntervalSeconds?: number;
    scopes?: string[];
}

/**
 * Base implementation of the ObservabilityConnector interface.
 *
 * Provides event filtering, log-level control, severity-based trace
 * filtering, secret redaction, and scope-based statistics flushing.
 * Subclasses override the five protected hook methods to change output
 * format and destination.
 */
class BaseObservability implements ObservabilityConnector {
    protected config: Required<BaseObservabilityConfig>;

    private static readonly SECRET_PATTERN =
        /("(?:api_key|token|secret|password|authorization)":\s*")([^"]+)(")/gi;

    private static readonly SEVERITY_ORDER: Record<string, number> = {
        debug: 0,
        info: 1,
        warning: 2,
        error: 3,
        critical: 4,
    };

    constructor(config: BaseObservabilityConfig = {}) {
        this.config = {
            eventFilter: config.eventFilter ?? [],
            logLevel: config.logLevel ?? "metadata",
            minSeverity: config.minSeverity ?? "info",
            redactSecrets: config.redactSecrets ?? true,
            flushIntervalSeconds: config.flushIntervalSeconds ?? 60,
            scopes: config.scopes ?? ["model", "provider", "pool"],
        };
    }

    // ── Events ──────────────────────────────────────────────────

    /** Emit a routing event to the configured output. */
    emit(event: RoutingEvent): void {
        if (this.config.eventFilter.length > 0) {
            if (!this.config.eventFilter.includes(event.event_type)) {
                return;
            }
        }

        let line = this.formatEvent(event);
        if (this.config.redactSecrets) line = this.redact(line);
        this.write(line);
    }

    // ── Logging ─────────────────────────────────────────────────

    /** Record a request/response log entry. */
    log(entry: RequestLogEntry): void {
        let line = this.formatLog(entry);
        if (this.config.redactSecrets) line = this.redact(line);
        this.write(line);
    }

    // ── Statistics ──────────────────────────────────────────────

    /** Flush buffered aggregate statistics to the configured output. */
    flush(stats: Record<string, AggregateStats>): void {
        for (const [scopeId, aggregate] of Object.entries(stats)) {
            const line = this.formatStats(scopeId, aggregate);
            this.write(line);
        }
    }

    // ── Tracing ────────────────────────────────────────────────

    /** Record a trace entry, filtering by minimum severity. */
    trace(entry: TraceEntry): void {
        const minLevel = BaseObservability.SEVERITY_ORDER[this.config.minSeverity] ?? 1;
        const entryLevel = BaseObservability.SEVERITY_ORDER[entry.severity] ?? 0;
        if (entryLevel < minLevel) return;

        let line = this.formatTrace(entry);
        if (this.config.redactSecrets) line = this.redact(line);
        this.write(line);
    }

    // ── Protected Hooks ─────────────────────────────────────────

    /** Format a routing event as a JSON string. */
    protected formatEvent(event: RoutingEvent): string {
        return JSON.stringify({
            type: "event",
            event_type: event.event_type,
            timestamp: event.timestamp.toISOString(),
            model_id: event.model_id,
            provider_id: event.provider_id,
            pool_id: event.pool_id,
            metadata: event.metadata,
        });
    }

    /** Format a log entry as a JSON string filtered by log level. */
    protected formatLog(entry: RequestLogEntry): string {
        const data: Record<string, unknown> = {
            type: "log",
            timestamp: entry.timestamp.toISOString(),
            model_id: entry.model_id,
            provider_id: entry.provider_id,
            status_code: entry.status_code,
            latency_ms: entry.latency_ms,
        };

        if (this.config.logLevel === "summary" || this.config.logLevel === "full") {
            data.tokens_in = entry.tokens_in;
            data.tokens_out = entry.tokens_out;
            data.cost = entry.cost;
            data.capability = entry.capability;
            data.delivery_mode = entry.delivery_mode;
        }

        if (this.config.logLevel === "full") {
            data.error = entry.error;
        }

        return JSON.stringify(data);
    }

    /** Format aggregate statistics as a JSON string. */
    protected formatStats(scopeId: string, stats: AggregateStats): string {
        return JSON.stringify({
            type: "stats",
            scope_id: scopeId,
            requests_total: stats.requests_total,
            requests_success: stats.requests_success,
            requests_failed: stats.requests_failed,
            tokens_in: stats.tokens_in,
            tokens_out: stats.tokens_out,
            cost_total: stats.cost_total,
            latency_avg: stats.latency_avg,
            latency_p95: stats.latency_p95,
            downtime_total: stats.downtime_total,
            rotation_events: stats.rotation_events,
        });
    }

    /** Format a trace entry as a JSON string. */
    protected formatTrace(entry: TraceEntry): string {
        const data: Record<string, unknown> = {
            type: "trace",
            severity: entry.severity,
            timestamp: entry.timestamp.toISOString(),
            component: entry.component,
            message: entry.message,
        };
        if (entry.metadata) data.metadata = entry.metadata;
        if (entry.error) data.error = entry.error;
        return JSON.stringify(data);
    }

    /**
     * Write a formatted line to the output destination.
     * The default implementation is a no-op. Subclasses must override.
     */
    protected write(line: string): void {
        // No-op: subclasses override to write to console, file, HTTP, etc.
    }

    private redact(text: string): string {
        return text.replace(
            BaseObservability.SECRET_PATTERN,
            "$1***REDACTED***$3"
        );
    }
}
```

---

## BaseDiscovery

The foundation for all discovery connectors. Implements the full `DiscoveryConnector` interface (RegistrySync, HealthMonitoring) with background scheduling, configurable sync and health probe intervals, and failure-threshold-based provider deactivation. Subclasses override `probe()` to implement protocol-specific health checks (HTTP, gRPC, TCP) and can override `sync()` to add custom model catalogue logic.

> **Implements:** [DiscoveryConnector](../interfaces/Discovery.md)

### Configuration

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseDiscoveryConfig:
    """Configuration for a BaseDiscovery instance."""
    providers: list[str] = field(default_factory=list)
    sync_interval_seconds: float = 3600.0
    health_interval_seconds: float = 60.0
    health_timeout_seconds: float = 10.0
    failure_threshold: int = 3
    on_new_model: str = "register"
    on_deprecated_model: str = "notify"
```

```typescript
/** Configuration for a BaseDiscovery instance. */
interface BaseDiscoveryConfig {
    providers?: string[];              // provider IDs to monitor
    syncIntervalSeconds?: number;      // default 3600
    healthIntervalSeconds?: number;    // default 60
    healthTimeoutSeconds?: number;     // default 10
    failureThreshold?: number;         // default 3
    onNewModel?: string;               // "register" | "notify" | "ignore"
    onDeprecatedModel?: string;        // "deactivate" | "notify" | "ignore"
}
```

### Methods and Default Behavior

| Method | Default Behavior |
|---|---|
| `sync(providers)` | Iterate configured providers, call each provider's `discover_models()` (if supported), diff against known catalogue, return `SyncResult` |
| `get_sync_status()` | Return `SyncStatus` with last/next sync times and model count |
| `probe(provider_id)` | Return `ProbeResult(success=True)` with zero latency (no-op; subclasses override) |
| `get_health_report(provider_id)` | Return `HealthReport` entries from internal health history |

### Python

```python
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from modelmesh.interfaces.discovery import (
    DiscoveryConnector,
    HealthReport,
    ProbeResult,
    SyncResult,
    SyncStatus,
)


@dataclass
class BaseDiscoveryConfig:
    """Configuration for a BaseDiscovery instance."""
    providers: list[str] = field(default_factory=list)
    sync_interval_seconds: float = 3600.0
    health_interval_seconds: float = 60.0
    health_timeout_seconds: float = 10.0
    failure_threshold: int = 3
    on_new_model: str = "register"
    on_deprecated_model: str = "notify"


class BaseDiscovery(DiscoveryConnector):
    """Base implementation of the DiscoveryConnector interface.

    Provides registry synchronization with diff-based change detection
    and health monitoring with failure-threshold-based deactivation.
    Subclasses override ``probe`` to implement protocol-specific health
    checks and can override ``sync`` for custom catalogue logic.
    """

    def __init__(self, config: BaseDiscoveryConfig) -> None:
        self._config = config
        self._known_models: dict[str, list[str]] = {}
        self._last_sync: Optional[datetime] = None
        self._models_synced: int = 0
        self._health_history: dict[str, list[HealthReport]] = {}
        self._failure_counts: dict[str, int] = {}

    # ── Registry Sync ───────────────────────────────────────────────

    async def sync(self, providers: list[str] | None = None) -> SyncResult:
        """Synchronize the model catalogue with provider APIs.

        Calls ``discover_models()`` on each provider connector (via the
        provider registry), diffs against the known catalogue, and
        returns new, deprecated, and updated models.

        Args:
            providers: Provider IDs to sync. If None, syncs all
                       configured providers.
        """
        target_providers = providers or self._config.providers
        new_models: list[str] = []
        deprecated_models: list[str] = []
        updated_models: list[str] = []
        errors: list[str] = []

        for provider_id in target_providers:
            try:
                discovered = await self._discover_provider_models(provider_id)
                known = set(self._known_models.get(provider_id, []))
                discovered_set = set(discovered)

                for model_id in discovered_set - known:
                    new_models.append(f"{provider_id}/{model_id}")
                for model_id in known - discovered_set:
                    deprecated_models.append(f"{provider_id}/{model_id}")
                for model_id in known & discovered_set:
                    updated_models.append(f"{provider_id}/{model_id}")

                self._known_models[provider_id] = list(discovered_set)
            except Exception as exc:
                errors.append(f"{provider_id}: {exc}")

        self._last_sync = datetime.utcnow()
        self._models_synced = sum(len(v) for v in self._known_models.values())

        return SyncResult(
            new_models=new_models,
            deprecated_models=deprecated_models,
            updated_models=updated_models,
            errors=errors,
        )

    async def get_sync_status(self) -> SyncStatus:
        """Return the current synchronization status."""
        next_sync = None
        if self._last_sync is not None:
            next_sync = self._last_sync + timedelta(
                seconds=self._config.sync_interval_seconds
            )
        return SyncStatus(
            last_sync=self._last_sync,
            next_sync=next_sync,
            models_synced=self._models_synced,
            status="idle" if self._last_sync else "pending",
        )

    # ── Health Monitoring ───────────────────────────────────────────

    async def probe(self, provider_id: str) -> ProbeResult:
        """Send a health probe to the specified provider.

        The default implementation returns a successful no-op probe.
        Subclasses override this to implement HTTP, gRPC, or TCP
        health checks.
        """
        return ProbeResult(
            provider_id=provider_id,
            success=True,
            latency_ms=0.0,
        )

    async def get_health_report(
        self, provider_id: str | None = None
    ) -> list[HealthReport]:
        """Return health reports for one or all providers.

        Probes each provider (or the specified one), records the
        result in history, and returns health reports with rolling
        availability scores.
        """
        target_providers = (
            [provider_id] if provider_id else self._config.providers
        )
        reports: list[HealthReport] = []

        for pid in target_providers:
            result = await self.probe(pid)

            # Track failure counts
            if result.success:
                self._failure_counts[pid] = 0
            else:
                self._failure_counts[pid] = self._failure_counts.get(pid, 0) + 1

            # Calculate availability score from history
            history = self._health_history.get(pid, [])
            total = len(history) + 1
            successes = sum(1 for h in history if h.available) + (
                1 if result.success else 0
            )
            availability_score = successes / total if total > 0 else 1.0

            report = HealthReport(
                provider_id=pid,
                available=result.success,
                latency_ms=result.latency_ms,
                status_code=result.status_code,
                error=result.error,
                availability_score=availability_score,
            )
            reports.append(report)

            # Store in history (keep last 100 entries)
            if pid not in self._health_history:
                self._health_history[pid] = []
            self._health_history[pid].append(report)
            if len(self._health_history[pid]) > 100:
                self._health_history[pid] = self._health_history[pid][-100:]

        return reports

    def is_provider_degraded(self, provider_id: str) -> bool:
        """Return True if the provider has exceeded the failure threshold."""
        return (
            self._failure_counts.get(provider_id, 0)
            >= self._config.failure_threshold
        )

    # ── Internal ────────────────────────────────────────────────────

    async def _discover_provider_models(self, provider_id: str) -> list[str]:
        """Discover models from a provider. Override for custom logic.

        The default implementation returns the known model list
        (no-op discovery). Subclasses connect to provider APIs
        to enumerate available models.
        """
        return self._known_models.get(provider_id, [])
```

### TypeScript

```typescript
import {
    DiscoveryConnector,
    HealthReport,
    ProbeResult,
    SyncResult,
    SyncStatus,
} from "../interfaces/discovery";

/** Configuration for a BaseDiscovery instance. */
interface BaseDiscoveryConfig {
    providers?: string[];
    syncIntervalSeconds?: number;
    healthIntervalSeconds?: number;
    healthTimeoutSeconds?: number;
    failureThreshold?: number;
    onNewModel?: string;
    onDeprecatedModel?: string;
}

/**
 * Base implementation of the DiscoveryConnector interface.
 *
 * Provides registry synchronization with diff-based change detection
 * and health monitoring with failure-threshold-based deactivation.
 */
class BaseDiscovery implements DiscoveryConnector {
    protected config: Required<BaseDiscoveryConfig>;
    private knownModels = new Map<string, string[]>();
    private lastSync: Date | null = null;
    private modelsSynced = 0;
    private healthHistory = new Map<string, HealthReport[]>();
    private failureCounts = new Map<string, number>();

    constructor(config: BaseDiscoveryConfig = {}) {
        this.config = {
            providers: config.providers ?? [],
            syncIntervalSeconds: config.syncIntervalSeconds ?? 3600,
            healthIntervalSeconds: config.healthIntervalSeconds ?? 60,
            healthTimeoutSeconds: config.healthTimeoutSeconds ?? 10,
            failureThreshold: config.failureThreshold ?? 3,
            onNewModel: config.onNewModel ?? "register",
            onDeprecatedModel: config.onDeprecatedModel ?? "notify",
        };
    }

    // ── Registry Sync ───────────────────────────────────────────

    /** Synchronize the model catalogue with provider APIs. */
    async sync(providers?: string[]): Promise<SyncResult> {
        const targetProviders = providers ?? this.config.providers;
        const newModels: string[] = [];
        const deprecatedModels: string[] = [];
        const updatedModels: string[] = [];
        const errors: string[] = [];

        for (const providerId of targetProviders) {
            try {
                const discovered = await this.discoverProviderModels(providerId);
                const known = new Set(this.knownModels.get(providerId) ?? []);
                const discoveredSet = new Set(discovered);

                for (const modelId of discoveredSet) {
                    if (!known.has(modelId)) {
                        newModels.push(`${providerId}/${modelId}`);
                    }
                }
                for (const modelId of known) {
                    if (!discoveredSet.has(modelId)) {
                        deprecatedModels.push(`${providerId}/${modelId}`);
                    }
                }
                for (const modelId of discoveredSet) {
                    if (known.has(modelId)) {
                        updatedModels.push(`${providerId}/${modelId}`);
                    }
                }

                this.knownModels.set(providerId, [...discoveredSet]);
            } catch (err) {
                errors.push(`${providerId}: ${err}`);
            }
        }

        this.lastSync = new Date();
        this.modelsSynced = Array.from(this.knownModels.values()).reduce(
            (sum, v) => sum + v.length, 0
        );

        return { new_models: newModels, deprecated_models: deprecatedModels, updated_models: updatedModels, errors };
    }

    /** Return the current synchronization status. */
    async getSyncStatus(): Promise<SyncStatus> {
        const nextSync = this.lastSync
            ? new Date(this.lastSync.getTime() + this.config.syncIntervalSeconds * 1000)
            : undefined;
        return {
            last_sync: this.lastSync ?? undefined,
            next_sync: nextSync,
            models_synced: this.modelsSynced,
            status: this.lastSync ? "idle" : "pending",
        };
    }

    // ── Health Monitoring ───────────────────────────────────────

    /** Send a health probe to the specified provider. No-op by default. */
    async probe(providerId: string): Promise<ProbeResult> {
        return {
            provider_id: providerId,
            success: true,
            latency_ms: 0,
        };
    }

    /** Return health reports for one or all providers. */
    async getHealthReport(providerId?: string): Promise<HealthReport[]> {
        const targetProviders = providerId
            ? [providerId]
            : this.config.providers;
        const reports: HealthReport[] = [];

        for (const pid of targetProviders) {
            const result = await this.probe(pid);

            if (result.success) {
                this.failureCounts.set(pid, 0);
            } else {
                this.failureCounts.set(pid, (this.failureCounts.get(pid) ?? 0) + 1);
            }

            const history = this.healthHistory.get(pid) ?? [];
            const total = history.length + 1;
            const successes =
                history.filter((h) => h.available).length +
                (result.success ? 1 : 0);
            const availabilityScore = total > 0 ? successes / total : 1.0;

            const report: HealthReport = {
                provider_id: pid,
                available: result.success,
                latency_ms: result.latency_ms,
                status_code: result.status_code,
                error: result.error,
                availability_score: availabilityScore,
                timestamp: new Date(),
            };
            reports.push(report);

            const updated = [...history, report].slice(-100);
            this.healthHistory.set(pid, updated);
        }

        return reports;
    }

    /** Return true if the provider has exceeded the failure threshold. */
    isProviderDegraded(providerId: string): boolean {
        return (this.failureCounts.get(providerId) ?? 0) >= this.config.failureThreshold;
    }

    // ── Internal ────────────────────────────────────────────────

    /** Discover models from a provider. Override for custom logic. */
    protected async discoverProviderModels(providerId: string): Promise<string[]> {
        return this.knownModels.get(providerId) ?? [];
    }
}
```

---

# Specialized Classes

The CDK ships seven specialized subclasses that cover common use cases without requiring any overrides. Each inherits from one base class and either locks in a specific backend or adds structured configuration for common patterns.

---

## OpenAICompatibleProvider

Zero-configuration provider for any API that speaks the OpenAI chat completions format. Since `BaseProvider` already defaults to OpenAI-format request/response translation, this class requires no overrides -- it exists purely as a semantic alias that signals intent and enables type-safe configuration.

> **Extends:** [BaseProvider](#baseprovider)

### Python

```python
class OpenAICompatibleProvider(BaseProvider):
    """Provider for APIs that use the OpenAI chat completions format.

    No overrides are needed. The base class already speaks
    OpenAI-format JSON for requests, responses, and streaming.
    Use this class for OpenAI, Azure OpenAI, Groq, Together AI,
    OpenRouter, vLLM, or any endpoint that accepts
    ``POST /v1/chat/completions`` with the standard schema.

    Example::

        provider = OpenAICompatibleProvider(BaseProviderConfig(
            base_url="https://api.openai.com",
            api_key="${secrets:openai-key}",
            models=[ModelInfo(
                id="gpt-4o",
                name="GPT-4o",
                capabilities=["generation.text-generation.chat-completion"],
                features={"tool_calling": True, "vision": True, "system_prompt": True},
                context_window=128_000,
                max_output_tokens=16_384,
            )],
        ))
    """
    pass
```

### TypeScript

```typescript
/**
 * Provider for APIs that use the OpenAI chat completions format.
 *
 * No overrides are needed. Use for OpenAI, Azure OpenAI, Groq,
 * Together AI, OpenRouter, vLLM, or any standard-compatible endpoint.
 */
class OpenAICompatibleProvider extends BaseProvider {
    // Inherits all behavior from BaseProvider.
    // No overrides required.
}
```

---

## QuickProvider

A minimal provider that works with just `base_url` and `api_key`. Unlike `OpenAICompatibleProvider`, it does not require a `models` list -- if `models` is empty, it auto-discovers available models by calling the provider's `/v1/models` endpoint at initialization. Used internally by the convenience layer's auto-detection and available to users for quick custom provider setup.

> **Extends:** [BaseProvider](#baseprovider)

### Configuration

```python
from dataclasses import dataclass, field

@dataclass
class QuickProviderConfig(BaseProviderConfig):
    """Configuration for a QuickProvider instance.

    Only ``base_url`` and ``api_key`` are required.
    If ``models`` is left empty, the provider will auto-discover
    available models from the ``/v1/models`` endpoint.
    """
    base_url: str = ""
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)  # empty = auto-discover
```

### Auto-Discovery

When `models` is empty, `QuickProvider` calls `GET {base_url}/v1/models` and populates the models list from the response. This happens once during initialization and the result is cached for the lifetime of the provider instance.

```
QuickProvider.__init__(config)
│
├── config.models is non-empty?
│   └── Yes ──► use provided models list
│
└── config.models is empty?
    └── GET {base_url}/v1/models
        ├── success ──► parse response, populate self._models
        └── failure ──► raise ProviderInitError
```

### Python

```python
import json
import urllib.request

from modelmesh.cdk import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import ModelInfo


class QuickProvider(BaseProvider):
    """Minimal provider that requires only base_url and api_key.

    If no models are supplied, auto-discovers them from the
    provider's /v1/models endpoint during initialization.

    Example::

        provider = QuickProvider(QuickProviderConfig(
            base_url="https://api.groq.com/openai",
            api_key="${secrets:groq-key}",
            # models=[] triggers auto-discovery
        ))
    """

    async def _initialize(self) -> None:
        """Initialize the provider and auto-discover models if needed."""
        await super()._initialize()
        if not self._models:
            self._models = await self._discover_models()

    async def _discover_models(self) -> list[ModelInfo]:
        """Fetch available models from the /v1/models endpoint."""
        url = f"{self._base_url}/v1/models"
        headers = self._get_headers()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        models: list[ModelInfo] = []
        for entry in data.get("data", []):
            models.append(ModelInfo(
                id=entry["id"],
                name=entry.get("id", entry.get("name", "")),
                capabilities=["generation.text-generation.chat-completion"],
                context_window=entry.get("context_window", 4096),
                max_output_tokens=entry.get("max_output_tokens", 4096),
            ))
        return models
```

### TypeScript

```typescript
import { BaseProvider, BaseProviderConfig } from "../cdk/base_provider";
import { ModelInfo } from "../interfaces/provider";

/**
 * Minimal provider that requires only base_url and api_key.
 *
 * If no models are supplied, auto-discovers them from the
 * provider's /v1/models endpoint during initialization.
 */
class QuickProvider extends BaseProvider {
    protected override async initialize(): Promise<void> {
        await super.initialize();
        if (this.models.length === 0) {
            this.models = await this.discoverModels();
        }
    }

    private async discoverModels(): Promise<ModelInfo[]> {
        const url = `${this.baseUrl}/v1/models`;
        const resp = await fetch(url, { headers: this.getHeaders() });
        if (!resp.ok) {
            throw new Error(`Model discovery failed: ${resp.status}`);
        }
        const data = await resp.json();

        return (data.data ?? []).map((entry: Record<string, unknown>) => ({
            id: entry.id as string,
            name: (entry.id ?? entry.name ?? "") as string,
            capabilities: ["generation.text-generation.chat-completion"],
            contextWindow: (entry.context_window ?? 4096) as number,
            maxOutputTokens: (entry.max_output_tokens ?? 4096) as number,
        }));
    }
}
```

---

## HttpApiProvider

Provider for custom REST APIs that do not follow the OpenAI format. Adds `RequestMapping` and `ResponseMapping` configuration that declaratively map between the normalized `CompletionRequest`/`CompletionResponse` types and the provider's custom JSON schema. Overrides `_build_request_payload` and `_parse_response` to apply the mappings.

> **Extends:** [BaseProvider](#baseprovider)

### Configuration (additional)

```python
from dataclasses import dataclass, field


@dataclass
class RequestMapping:
    """Declarative mapping from CompletionRequest fields to custom JSON paths."""
    model_field: str = "model"
    messages_field: str = "messages"
    temperature_field: str = "temperature"
    max_tokens_field: str = "max_tokens"
    extra_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ResponseMapping:
    """Declarative mapping from custom JSON response paths to CompletionResponse fields."""
    id_field: str = "id"
    model_field: str = "model"
    choices_field: str = "choices"
    usage_field: str = "usage"
    prompt_tokens_field: str = "prompt_tokens"
    completion_tokens_field: str = "completion_tokens"


@dataclass
class HttpApiProviderConfig(BaseProviderConfig):
    """Configuration for an HttpApiProvider instance."""
    request_mapping: RequestMapping = field(default_factory=RequestMapping)
    response_mapping: ResponseMapping = field(default_factory=ResponseMapping)
    completion_endpoint: str = "/v1/chat/completions"
```

### Python

```python
from dataclasses import dataclass, field

from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse, TokenUsage


@dataclass
class RequestMapping:
    """Declarative mapping from CompletionRequest fields to custom JSON paths."""
    model_field: str = "model"
    messages_field: str = "messages"
    temperature_field: str = "temperature"
    max_tokens_field: str = "max_tokens"
    extra_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ResponseMapping:
    """Declarative mapping from custom JSON response to CompletionResponse fields."""
    id_field: str = "id"
    model_field: str = "model"
    choices_field: str = "choices"
    usage_field: str = "usage"
    prompt_tokens_field: str = "prompt_tokens"
    completion_tokens_field: str = "completion_tokens"


@dataclass
class HttpApiProviderConfig(BaseProviderConfig):
    """Configuration for an HttpApiProvider instance."""
    request_mapping: RequestMapping = field(default_factory=RequestMapping)
    response_mapping: ResponseMapping = field(default_factory=ResponseMapping)
    completion_endpoint: str = "/v1/chat/completions"


class HttpApiProvider(BaseProvider):
    """Provider for custom REST APIs with declarative field mapping.

    Uses ``RequestMapping`` and ``ResponseMapping`` to translate between
    the normalized request/response types and the provider's custom
    JSON schema without writing code.

    Example::

        provider = HttpApiProvider(HttpApiProviderConfig(
            base_url="https://custom-api.example.com",
            api_key="${secrets:custom-key}",
            completion_endpoint="/api/generate",
            request_mapping=RequestMapping(
                model_field="model_name",
                messages_field="prompt",
                temperature_field="temp",
                max_tokens_field="max_length",
            ),
            response_mapping=ResponseMapping(
                id_field="request_id",
                choices_field="outputs",
                usage_field="token_usage",
                prompt_tokens_field="input_tokens",
                completion_tokens_field="output_tokens",
            ),
        ))
    """

    def __init__(self, config: HttpApiProviderConfig) -> None:
        super().__init__(config)
        self._mapping_config = config

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Build request payload using the configured field mapping."""
        rm = self._mapping_config.request_mapping
        payload: dict = {
            rm.model_field: request.model,
            rm.messages_field: request.messages,
        }
        if request.temperature is not None:
            payload[rm.temperature_field] = request.temperature
        if request.max_tokens is not None:
            payload[rm.max_tokens_field] = request.max_tokens
        if request.stream:
            payload["stream"] = True
        for target_key, source_expr in rm.extra_fields.items():
            payload[target_key] = source_expr
        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Parse response using the configured field mapping."""
        rm = self._mapping_config.response_mapping
        usage_data = self._get_nested(data, rm.usage_field, {})
        return CompletionResponse(
            id=str(self._get_nested(data, rm.id_field, "")),
            model=str(self._get_nested(data, rm.model_field, "")),
            choices=self._get_nested(data, rm.choices_field, []),
            usage=TokenUsage(
                prompt_tokens=int(
                    self._get_nested(usage_data, rm.prompt_tokens_field, 0)
                ),
                completion_tokens=int(
                    self._get_nested(usage_data, rm.completion_tokens_field, 0)
                ),
                total_tokens=int(
                    self._get_nested(usage_data, rm.prompt_tokens_field, 0)
                ) + int(
                    self._get_nested(usage_data, rm.completion_tokens_field, 0)
                ),
            ),
        )

    def _get_completion_endpoint(self) -> str:
        """Return the custom completion endpoint path."""
        base = self._config.base_url.rstrip("/")
        path = self._mapping_config.completion_endpoint
        return f"{base}{path}"

    @staticmethod
    def _get_nested(data: dict, path: str, default=None):
        """Resolve a dot-separated field path in a nested dict."""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
```

### TypeScript

```typescript
/** Declarative mapping from CompletionRequest fields to custom JSON paths. */
interface RequestMapping {
    modelField?: string;
    messagesField?: string;
    temperatureField?: string;
    maxTokensField?: string;
    extraFields?: Record<string, string>;
}

/** Declarative mapping from custom JSON response to CompletionResponse fields. */
interface ResponseMapping {
    idField?: string;
    modelField?: string;
    choicesField?: string;
    usageField?: string;
    promptTokensField?: string;
    completionTokensField?: string;
}

/** Configuration for an HttpApiProvider instance. */
interface HttpApiProviderConfig extends BaseProviderConfig {
    requestMapping?: RequestMapping;
    responseMapping?: ResponseMapping;
    completionEndpoint?: string;
}

/**
 * Provider for custom REST APIs with declarative field mapping.
 *
 * Uses RequestMapping and ResponseMapping to translate between
 * normalized request/response types and custom JSON schemas.
 */
class HttpApiProvider extends BaseProvider {
    private requestMapping: Required<RequestMapping>;
    private responseMapping: Required<ResponseMapping>;
    private completionEndpointPath: string;

    constructor(config: HttpApiProviderConfig) {
        super(config);
        this.requestMapping = {
            modelField: config.requestMapping?.modelField ?? "model",
            messagesField: config.requestMapping?.messagesField ?? "messages",
            temperatureField: config.requestMapping?.temperatureField ?? "temperature",
            maxTokensField: config.requestMapping?.maxTokensField ?? "max_tokens",
            extraFields: config.requestMapping?.extraFields ?? {},
        };
        this.responseMapping = {
            idField: config.responseMapping?.idField ?? "id",
            modelField: config.responseMapping?.modelField ?? "model",
            choicesField: config.responseMapping?.choicesField ?? "choices",
            usageField: config.responseMapping?.usageField ?? "usage",
            promptTokensField: config.responseMapping?.promptTokensField ?? "prompt_tokens",
            completionTokensField: config.responseMapping?.completionTokensField ?? "completion_tokens",
        };
        this.completionEndpointPath = config.completionEndpoint ?? "/v1/chat/completions";
    }

    protected buildRequestPayload(request: CompletionRequest): Record<string, unknown> {
        const rm = this.requestMapping;
        const payload: Record<string, unknown> = {
            [rm.modelField]: request.model,
            [rm.messagesField]: request.messages,
        };
        if (request.temperature !== undefined) payload[rm.temperatureField] = request.temperature;
        if (request.max_tokens !== undefined) payload[rm.maxTokensField] = request.max_tokens;
        if (request.stream) payload.stream = true;
        for (const [key, value] of Object.entries(rm.extraFields)) {
            payload[key] = value;
        }
        return payload;
    }

    protected parseResponse(data: Record<string, unknown>): CompletionResponse {
        const rm = this.responseMapping;
        const usageData = (this.getNested(data, rm.usageField) ?? {}) as Record<string, number>;
        const promptTokens = Number(this.getNested(usageData, rm.promptTokensField) ?? 0);
        const completionTokens = Number(this.getNested(usageData, rm.completionTokensField) ?? 0);
        return {
            id: String(this.getNested(data, rm.idField) ?? ""),
            model: String(this.getNested(data, rm.modelField) ?? ""),
            choices: (this.getNested(data, rm.choicesField) ?? []) as Record<string, unknown>[],
            usage: {
                prompt_tokens: promptTokens,
                completion_tokens: completionTokens,
                total_tokens: promptTokens + completionTokens,
            },
        };
    }

    protected getCompletionEndpoint(): string {
        const base = this.config.baseUrl.replace(/\/+$/, "");
        return `${base}${this.completionEndpointPath}`;
    }

    private getNested(data: Record<string, unknown>, path: string): unknown {
        const keys = path.split(".");
        let current: unknown = data;
        for (const key of keys) {
            if (current && typeof current === "object" && key in current) {
                current = (current as Record<string, unknown>)[key];
            } else {
                return undefined;
            }
        }
        return current;
    }
}
```

---

## ThresholdRotationPolicy

Semantic alias for `BaseRotationPolicy`. The base class already implements threshold-based deactivation (failure count, error rate, quota, tokens, budget), cooldown-based recovery, and priority-list selection. This class exists for naming clarity in configuration files where `ThresholdRotationPolicy` communicates intent more directly than `BaseRotationPolicy`.

> **Extends:** [BaseRotationPolicy](#baserotationpolicy)

### Python

```python
class ThresholdRotationPolicy(BaseRotationPolicy):
    """Threshold-based rotation policy.

    Deactivates models when failure counts, error rates, or usage
    limits exceed configured thresholds. Recovers models after a
    cooldown period. Selects by priority list with error-rate fallback.

    This is a semantic alias for ``BaseRotationPolicy`` -- the base
    class already implements threshold-based logic. Use this class name
    in configuration to communicate intent clearly.

    Example::

        policy = ThresholdRotationPolicy(BaseRotationPolicyConfig(
            retry_limit=5,
            error_rate_threshold=0.3,
            cooldown_seconds=120,
            budget_limit=10.0,
            model_priority=["gpt-4o", "claude-sonnet-4"],
        ))
    """
    pass
```

### TypeScript

```typescript
/**
 * Threshold-based rotation policy.
 *
 * Semantic alias for BaseRotationPolicy. Use this class name
 * in configuration to communicate intent clearly.
 */
class ThresholdRotationPolicy extends BaseRotationPolicy {
    // Inherits all behavior from BaseRotationPolicy.
}
```

---

## FileSecretStore

File-backed secret store that reads secrets from `.env`, JSON, or TOML files. Overrides `_resolve()` to parse the configured file format and look up secrets by name. Supports automatic reloading when the file changes.

> **Extends:** [BaseSecretStore](#basesecretstore)

### Configuration (additional)

```python
@dataclass
class FileSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for a FileSecretStore instance."""
    file_path: str = ".env"
    file_format: str = "dotenv"       # "dotenv" | "json" | "toml"
    watch_for_changes: bool = False
```

### Python

```python
import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for a FileSecretStore instance."""
    file_path: str = ".env"
    file_format: str = "dotenv"
    watch_for_changes: bool = False


class FileSecretStore(BaseSecretStore):
    """Secret store backed by a local file (.env, JSON, or TOML).

    Overrides ``_resolve`` to read secrets from the configured file.
    Supports dotenv, JSON, and TOML formats. Optionally watches the
    file for changes and reloads automatically.

    Example::

        store = FileSecretStore(FileSecretStoreConfig(
            file_path="/app/secrets.json",
            file_format="json",
            cache_ttl_ms=60_000,
        ))
    """

    def __init__(self, config: FileSecretStoreConfig) -> None:
        super().__init__(config)
        self._file_config = config
        self._file_data: dict[str, str] = {}
        self._last_mtime: Optional[float] = None
        self._load_file()

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret by name from the loaded file data.

        Reloads the file if ``watch_for_changes`` is enabled and the
        file modification time has changed.
        """
        if self._file_config.watch_for_changes:
            self._maybe_reload()
        return self._file_data.get(name)

    def _load_file(self) -> None:
        """Parse the secrets file according to the configured format."""
        path = self._file_config.file_path
        if not os.path.exists(path):
            return

        self._last_mtime = os.path.getmtime(path)

        if self._file_config.file_format == "dotenv":
            self._file_data = self._parse_dotenv(path)
        elif self._file_config.file_format == "json":
            with open(path, "r", encoding="utf-8") as f:
                self._file_data = json.load(f)
        elif self._file_config.file_format == "toml":
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with open(path, "rb") as f:
                self._file_data = self._flatten(tomllib.load(f))
        else:
            raise ValueError(
                f"Unsupported file format: {self._file_config.file_format}"
            )

    def _maybe_reload(self) -> None:
        """Reload the file if its modification time has changed."""
        path = self._file_config.file_path
        if not os.path.exists(path):
            return
        mtime = os.path.getmtime(path)
        if mtime != self._last_mtime:
            self._load_file()
            self.clear_cache()

    @staticmethod
    def _parse_dotenv(path: str) -> dict[str, str]:
        """Parse a dotenv file into a dict of key-value pairs."""
        data: dict[str, str] = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                data[key] = value
        return data

    @staticmethod
    def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
        """Flatten a nested dict into dot-separated key paths."""
        result: dict[str, str] = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(FileSecretStore._flatten(value, full_key))
            else:
                result[full_key] = str(value)
        return result
```

### TypeScript

```typescript
import * as fs from "fs";
import * as path from "path";

/** Configuration for a FileSecretStore instance. */
interface FileSecretStoreConfig extends BaseSecretStoreConfig {
    filePath?: string;           // default ".env"
    fileFormat?: string;         // "dotenv" | "json" | "toml"
    watchForChanges?: boolean;   // default false
}

/**
 * Secret store backed by a local file (.env, JSON, or TOML).
 *
 * Overrides `resolve` to read secrets from the configured file.
 */
class FileSecretStore extends BaseSecretStore {
    private filePath: string;
    private fileFormat: string;
    private watchForChanges: boolean;
    private fileData: Record<string, string> = {};
    private lastMtime: number | null = null;

    constructor(config: FileSecretStoreConfig = {}) {
        super(config);
        this.filePath = config.filePath ?? ".env";
        this.fileFormat = config.fileFormat ?? "dotenv";
        this.watchForChanges = config.watchForChanges ?? false;
        this.loadFile();
    }

    protected resolve(name: string): string | null {
        if (this.watchForChanges) this.maybeReload();
        return this.fileData[name] ?? null;
    }

    private loadFile(): void {
        if (!fs.existsSync(this.filePath)) return;
        this.lastMtime = fs.statSync(this.filePath).mtimeMs;

        if (this.fileFormat === "dotenv") {
            this.fileData = this.parseDotenv(this.filePath);
        } else if (this.fileFormat === "json") {
            const content = fs.readFileSync(this.filePath, "utf-8");
            this.fileData = JSON.parse(content);
        } else {
            throw new Error(`Unsupported file format: ${this.fileFormat}`);
        }
    }

    private maybeReload(): void {
        if (!fs.existsSync(this.filePath)) return;
        const mtime = fs.statSync(this.filePath).mtimeMs;
        if (mtime !== this.lastMtime) {
            this.loadFile();
            this.clearCache();
        }
    }

    private parseDotenv(filePath: string): Record<string, string> {
        const data: Record<string, string> = {};
        const content = fs.readFileSync(filePath, "utf-8");
        for (const rawLine of content.split("\n")) {
            const line = rawLine.trim();
            if (!line || line.startsWith("#") || !line.includes("=")) continue;
            const eqIdx = line.indexOf("=");
            const key = line.slice(0, eqIdx).trim();
            let value = line.slice(eqIdx + 1).trim();
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
                value = value.slice(1, -1);
            }
            data[key] = value;
        }
        return data;
    }
}
```

---

## KeyValueStorage

Pluggable key-value storage with selectable backend. Ships with two backends: `memory` (the default `BaseStorage` in-memory dict) and `file` (JSON files on disk). The `file` backend overrides `load` and `save` to read/write JSON files in a configurable directory.

> **Extends:** [BaseStorage](#basestorage)

### Configuration (additional)

```python
@dataclass
class KeyValueStorageConfig(BaseStorageConfig):
    """Configuration for a KeyValueStorage instance."""
    backend: str = "memory"       # "memory" | "file"
    directory: str = ".modelmesh/storage"
```

### Python

```python
import json
import os
from dataclasses import dataclass
from datetime import datetime

from modelmesh.interfaces.storage import EntryMetadata, StorageEntry


@dataclass
class KeyValueStorageConfig(BaseStorageConfig):
    """Configuration for a KeyValueStorage instance."""
    backend: str = "memory"
    directory: str = ".modelmesh/storage"


class KeyValueStorage(BaseStorage):
    """Key-value storage with pluggable memory or file backend.

    The ``memory`` backend inherits the base class in-memory dict.
    The ``file`` backend overrides ``load`` and ``save`` to persist
    entries as JSON files in a configurable directory.

    Example::

        storage = KeyValueStorage(KeyValueStorageConfig(
            backend="file",
            directory="/app/data/state",
            format="json",
            locking_enabled=True,
        ))
    """

    def __init__(self, config: KeyValueStorageConfig) -> None:
        super().__init__(config)
        self._kv_config = config
        if config.backend == "file":
            os.makedirs(config.directory, exist_ok=True)

    async def load(self, key: str) -> StorageEntry | None:
        """Load entry from file backend, or delegate to in-memory."""
        if self._kv_config.backend == "file":
            path = self._key_to_path(key)
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StorageEntry(
                key=data["key"],
                data=data["data"].encode("utf-8"),
                metadata=data.get("metadata", {}),
            )
        return await super().load(key)

    async def save(self, key: str, entry: StorageEntry) -> None:
        """Save entry to file backend, or delegate to in-memory."""
        if self._kv_config.backend == "file":
            path = self._key_to_path(key)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "key": entry.key,
                        "data": entry.data.decode("utf-8")
                            if isinstance(entry.data, bytes) else entry.data,
                        "metadata": entry.metadata,
                        "saved_at": datetime.utcnow().isoformat(),
                    },
                    f,
                    indent=2,
                )
            return
        await super().save(key, entry)

    async def delete(self, key: str) -> bool:
        """Delete entry from file backend, or delegate to in-memory."""
        if self._kv_config.backend == "file":
            path = self._key_to_path(key)
            if os.path.exists(path):
                os.remove(path)
                return True
            return False
        return await super().delete(key)

    async def list(self, prefix: str | None = None) -> list[str]:
        """List keys from file backend, or delegate to in-memory."""
        if self._kv_config.backend == "file":
            if not os.path.exists(self._kv_config.directory):
                return []
            keys = [
                f.replace(".json", "")
                for f in os.listdir(self._kv_config.directory)
                if f.endswith(".json")
            ]
            if prefix:
                keys = [k for k in keys if k.startswith(prefix)]
            return keys
        return await super().list(prefix)

    async def exists(self, key: str) -> bool:
        """Check if key exists in file backend, or delegate to in-memory."""
        if self._kv_config.backend == "file":
            return os.path.exists(self._key_to_path(key))
        return await super().exists(key)

    async def stat(self, key: str) -> EntryMetadata | None:
        """Return metadata from file backend, or delegate to in-memory."""
        if self._kv_config.backend == "file":
            path = self._key_to_path(key)
            if not os.path.exists(path):
                return None
            stat = os.stat(path)
            return EntryMetadata(
                key=key,
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                content_type=self._config.format,
            )
        return await super().stat(key)

    def _key_to_path(self, key: str) -> str:
        """Convert a storage key to a filesystem path."""
        safe_key = key.replace("/", "__").replace("\\", "__")
        return os.path.join(self._kv_config.directory, f"{safe_key}.json")
```

### TypeScript

```typescript
import * as fs from "fs";
import * as pathModule from "path";

/** Configuration for a KeyValueStorage instance. */
interface KeyValueStorageConfig extends BaseStorageConfig {
    backend?: string;       // "memory" | "file", default "memory"
    directory?: string;     // default ".modelmesh/storage"
}

/**
 * Key-value storage with pluggable memory or file backend.
 *
 * The file backend persists entries as JSON files in a directory.
 */
class KeyValueStorage extends BaseStorage {
    private backend: string;
    private directory: string;

    constructor(config: KeyValueStorageConfig = {}) {
        super(config);
        this.backend = config.backend ?? "memory";
        this.directory = config.directory ?? ".modelmesh/storage";
        if (this.backend === "file") {
            fs.mkdirSync(this.directory, { recursive: true });
        }
    }

    async load(key: string): Promise<StorageEntry | null> {
        if (this.backend === "file") {
            const filePath = this.keyToPath(key);
            if (!fs.existsSync(filePath)) return null;
            const raw = JSON.parse(fs.readFileSync(filePath, "utf-8"));
            return {
                key: raw.key,
                data: new TextEncoder().encode(raw.data),
                metadata: raw.metadata ?? {},
            };
        }
        return super.load(key);
    }

    async save(key: string, entry: StorageEntry): Promise<void> {
        if (this.backend === "file") {
            const filePath = this.keyToPath(key);
            const content = JSON.stringify({
                key: entry.key,
                data: new TextDecoder().decode(entry.data),
                metadata: entry.metadata,
                saved_at: new Date().toISOString(),
            }, null, 2);
            fs.writeFileSync(filePath, content, "utf-8");
            return;
        }
        return super.save(key, entry);
    }

    async delete(key: string): Promise<boolean> {
        if (this.backend === "file") {
            const filePath = this.keyToPath(key);
            if (fs.existsSync(filePath)) {
                fs.unlinkSync(filePath);
                return true;
            }
            return false;
        }
        return super.delete(key);
    }

    async list(prefix?: string): Promise<string[]> {
        if (this.backend === "file") {
            if (!fs.existsSync(this.directory)) return [];
            let keys = fs.readdirSync(this.directory)
                .filter((f) => f.endsWith(".json"))
                .map((f) => f.replace(".json", ""));
            if (prefix) keys = keys.filter((k) => k.startsWith(prefix));
            return keys;
        }
        return super.list(prefix);
    }

    async exists(key: string): Promise<boolean> {
        if (this.backend === "file") {
            return fs.existsSync(this.keyToPath(key));
        }
        return super.exists(key);
    }

    async stat(key: string): Promise<EntryMetadata | null> {
        if (this.backend === "file") {
            const filePath = this.keyToPath(key);
            if (!fs.existsSync(filePath)) return null;
            const stats = fs.statSync(filePath);
            return {
                key,
                size: stats.size,
                last_modified: stats.mtime,
                content_type: this.config.format,
            };
        }
        return super.stat(key);
    }

    private keyToPath(key: string): string {
        const safeKey = key.replace(/[/\\]/g, "__");
        return pathModule.join(this.directory, `${safeKey}.json`);
    }
}
```

---

## ConsoleObservability

Observability connector that writes ANSI-colored output to the console (stdout/stderr). Designed for local development and debugging. Overrides all four hook methods to produce human-readable, color-coded output.

> **Extends:** [BaseObservability](#baseobservability)

### Python

```python
import sys
from datetime import datetime


class ConsoleObservability(BaseObservability):
    """Observability connector that writes ANSI-colored output to the console.

    Designed for local development and debugging. Events, logs, and
    statistics are formatted with ANSI color codes for readability.

    Color scheme:
    - Events: cyan for type, yellow for model/provider
    - Logs: green for success (2xx), red for errors (4xx/5xx)
    - Statistics: magenta for scope, white for metrics

    Example::

        obs = ConsoleObservability(BaseObservabilityConfig(
            log_level="summary",
            redact_secrets=True,
        ))
    """

    # ANSI color codes
    RESET = "\033[0m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    DIM = "\033[2m"
    BOLD = "\033[1m"

    def _format_event(self, event: "RoutingEvent") -> str:
        """Format event with ANSI colors for console output."""
        timestamp = event.timestamp.strftime("%H:%M:%S")
        parts = [
            f"{self.DIM}{timestamp}{self.RESET}",
            f"{self.CYAN}{self.BOLD}[EVENT]{self.RESET}",
            f"{self.CYAN}{event.event_type.value}{self.RESET}",
        ]
        if event.model_id:
            parts.append(f"{self.YELLOW}model={event.model_id}{self.RESET}")
        if event.provider_id:
            parts.append(f"{self.YELLOW}provider={event.provider_id}{self.RESET}")
        if event.pool_id:
            parts.append(f"pool={event.pool_id}")
        return " ".join(parts)

    def _format_log(self, entry: "RequestLogEntry") -> str:
        """Format log entry with ANSI colors based on status code."""
        timestamp = entry.timestamp.strftime("%H:%M:%S")
        status_color = self.GREEN if entry.status_code < 400 else self.RED
        parts = [
            f"{self.DIM}{timestamp}{self.RESET}",
            f"{status_color}[{entry.status_code}]{self.RESET}",
            f"{self.YELLOW}{entry.model_id}{self.RESET}",
            f"{entry.latency_ms:.0f}ms",
        ]

        if self._config.log_level in ("summary", "full"):
            parts.append(f"tokens={entry.tokens_in}+{entry.tokens_out}")
            if entry.cost is not None:
                parts.append(f"${entry.cost:.4f}")

        if self._config.log_level == "full" and entry.error:
            parts.append(f"{self.RED}{entry.error}{self.RESET}")

        return " ".join(parts)

    def _format_stats(self, scope_id: str, stats: "AggregateStats") -> str:
        """Format statistics with ANSI colors for console output."""
        success_rate = (
            (stats.requests_success / stats.requests_total * 100)
            if stats.requests_total > 0
            else 0
        )
        return (
            f"{self.MAGENTA}{self.BOLD}[STATS]{self.RESET} "
            f"{self.MAGENTA}{scope_id}{self.RESET} "
            f"reqs={stats.requests_total} "
            f"ok={success_rate:.1f}% "
            f"latency_avg={stats.latency_avg:.0f}ms "
            f"p95={stats.latency_p95:.0f}ms "
            f"cost=${stats.cost_total:.2f} "
            f"rotations={stats.rotation_events}"
        )

    def _write(self, line: str) -> None:
        """Write the formatted line to stdout."""
        print(line, file=sys.stdout, flush=True)
```

### TypeScript

```typescript
/**
 * Observability connector that writes ANSI-colored output to the console.
 *
 * Designed for local development and debugging.
 */
class ConsoleObservability extends BaseObservability {
    private static readonly RESET = "\x1b[0m";
    private static readonly CYAN = "\x1b[36m";
    private static readonly YELLOW = "\x1b[33m";
    private static readonly GREEN = "\x1b[32m";
    private static readonly RED = "\x1b[31m";
    private static readonly MAGENTA = "\x1b[35m";
    private static readonly DIM = "\x1b[2m";
    private static readonly BOLD = "\x1b[1m";

    protected formatEvent(event: RoutingEvent): string {
        const C = ConsoleObservability;
        const ts = event.timestamp.toTimeString().slice(0, 8);
        const parts = [
            `${C.DIM}${ts}${C.RESET}`,
            `${C.CYAN}${C.BOLD}[EVENT]${C.RESET}`,
            `${C.CYAN}${event.event_type}${C.RESET}`,
        ];
        if (event.model_id) parts.push(`${C.YELLOW}model=${event.model_id}${C.RESET}`);
        if (event.provider_id) parts.push(`${C.YELLOW}provider=${event.provider_id}${C.RESET}`);
        if (event.pool_id) parts.push(`pool=${event.pool_id}`);
        return parts.join(" ");
    }

    protected formatLog(entry: RequestLogEntry): string {
        const C = ConsoleObservability;
        const ts = entry.timestamp.toTimeString().slice(0, 8);
        const statusColor = entry.status_code < 400 ? C.GREEN : C.RED;
        const parts = [
            `${C.DIM}${ts}${C.RESET}`,
            `${statusColor}[${entry.status_code}]${C.RESET}`,
            `${C.YELLOW}${entry.model_id}${C.RESET}`,
            `${entry.latency_ms.toFixed(0)}ms`,
        ];

        if (this.config.logLevel === "summary" || this.config.logLevel === "full") {
            parts.push(`tokens=${entry.tokens_in}+${entry.tokens_out}`);
            if (entry.cost !== undefined) parts.push(`$${entry.cost.toFixed(4)}`);
        }

        if (this.config.logLevel === "full" && entry.error) {
            parts.push(`${C.RED}${entry.error}${C.RESET}`);
        }

        return parts.join(" ");
    }

    protected formatStats(scopeId: string, stats: AggregateStats): string {
        const C = ConsoleObservability;
        const successRate = stats.requests_total > 0
            ? (stats.requests_success / stats.requests_total * 100).toFixed(1)
            : "0.0";
        return [
            `${C.MAGENTA}${C.BOLD}[STATS]${C.RESET}`,
            `${C.MAGENTA}${scopeId}${C.RESET}`,
            `reqs=${stats.requests_total}`,
            `ok=${successRate}%`,
            `latency_avg=${stats.latency_avg.toFixed(0)}ms`,
            `p95=${stats.latency_p95.toFixed(0)}ms`,
            `cost=$${stats.cost_total.toFixed(2)}`,
            `rotations=${stats.rotation_events}`,
        ].join(" ");
    }

    protected write(line: string): void {
        console.log(line);
    }
}
```

---

## HttpHealthDiscovery

Discovery connector that performs HTTP health probes against provider endpoints. Overrides `probe()` to send HTTP GET requests to a configurable health path and evaluate the response status code and latency.

> **Extends:** [BaseDiscovery](#basediscovery)

### Configuration (additional)

```python
@dataclass
class HttpHealthDiscoveryConfig(BaseDiscoveryConfig):
    """Configuration for an HttpHealthDiscovery instance."""
    health_path: str = "/health"
    expected_status: int = 200
```

### Python

```python
import time
from dataclasses import dataclass

import urllib.request

from modelmesh.interfaces.discovery import ProbeResult


@dataclass
class HttpHealthDiscoveryConfig(BaseDiscoveryConfig):
    """Configuration for an HttpHealthDiscovery instance."""
    health_path: str = "/health"
    expected_status: int = 200


class HttpHealthDiscovery(BaseDiscovery):
    """Discovery connector that probes providers via HTTP GET.

    Overrides ``probe`` to send an HTTP GET request to each provider's
    health endpoint and evaluate the response status and latency.
    Uses the provider's ``base_url`` combined with ``health_path``.

    Example::

        discovery = HttpHealthDiscovery(HttpHealthDiscoveryConfig(
            providers=["openai", "anthropic"],
            health_path="/v1/models",
            expected_status=200,
            health_interval_seconds=30,
            failure_threshold=3,
        ))
    """

    def __init__(self, config: HttpHealthDiscoveryConfig) -> None:
        super().__init__(config)
        self._http_config = config
        self._timeout = config.health_timeout_seconds
        self._provider_urls: dict[str, str] = {}

    def register_provider_url(self, provider_id: str, base_url: str) -> None:
        """Register a provider's base URL for health probing."""
        self._provider_urls[provider_id] = base_url.rstrip("/")

    async def probe(self, provider_id: str) -> ProbeResult:
        """Send an HTTP GET health probe to the provider.

        Measures response latency and checks the status code against
        ``expected_status``. Returns a ``ProbeResult`` with success,
        latency, status code, and any error message.
        """
        base_url = self._provider_urls.get(provider_id)
        if base_url is None:
            return ProbeResult(
                provider_id=provider_id,
                success=False,
                error=f"No URL registered for provider: {provider_id}",
            )

        url = f"{base_url}{self._http_config.health_path}"
        start = time.monotonic()

        try:
            resp = await self._client.get(url)
            elapsed_ms = (time.monotonic() - start) * 1000
            success = resp.status_code == self._http_config.expected_status
            return ProbeResult(
                provider_id=provider_id,
                success=success,
                latency_ms=elapsed_ms,
                status_code=resp.status_code,
                error=None if success else f"Unexpected status: {resp.status_code}",
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            return ProbeResult(
                provider_id=provider_id,
                success=False,
                latency_ms=elapsed_ms,
                error=str(exc),
            )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
```

### TypeScript

```typescript
/** Configuration for an HttpHealthDiscovery instance. */
interface HttpHealthDiscoveryConfig extends BaseDiscoveryConfig {
    healthPath?: string;       // default "/health"
    expectedStatus?: number;   // default 200
}

/**
 * Discovery connector that probes providers via HTTP GET.
 *
 * Overrides `probe` to send HTTP GET requests to provider
 * health endpoints and evaluate response status and latency.
 */
class HttpHealthDiscovery extends BaseDiscovery {
    private healthPath: string;
    private expectedStatus: number;
    private providerUrls = new Map<string, string>();

    constructor(config: HttpHealthDiscoveryConfig = {}) {
        super(config);
        this.healthPath = config.healthPath ?? "/health";
        this.expectedStatus = config.expectedStatus ?? 200;
    }

    /** Register a provider's base URL for health probing. */
    registerProviderUrl(providerId: string, baseUrl: string): void {
        this.providerUrls.set(providerId, baseUrl.replace(/\/+$/, ""));
    }

    /** Send an HTTP GET health probe to the provider. */
    async probe(providerId: string): Promise<ProbeResult> {
        const baseUrl = this.providerUrls.get(providerId);
        if (!baseUrl) {
            return {
                provider_id: providerId,
                success: false,
                error: `No URL registered for provider: ${providerId}`,
            };
        }

        const url = `${baseUrl}${this.healthPath}`;
        const start = performance.now();

        try {
            const resp = await fetch(url, {
                signal: AbortSignal.timeout(this.config.healthTimeoutSeconds * 1000),
            });
            const latencyMs = performance.now() - start;
            const success = resp.status === this.expectedStatus;
            return {
                provider_id: providerId,
                success,
                latency_ms: latencyMs,
                status_code: resp.status,
                error: success ? undefined : `Unexpected status: ${resp.status}`,
            };
        } catch (err) {
            const latencyMs = performance.now() - start;
            return {
                provider_id: providerId,
                success: false,
                latency_ms: latencyMs,
                error: String(err),
            };
        }
    }
}
```

---

# Configuration Object Reference

Complete listing of all configuration fields across all six base class config objects.

## BaseProviderConfig

| Field | Python Type | TypeScript Type | Default | Description |
|---|---|---|---|---|
| `base_url` | `str` | `string` | *(required)* | Provider API base URL |
| `api_key` | `str` | `string?` | `""` | API key or secret reference |
| `models` | `list[ModelInfo]` | `ModelInfo[]` | `[]` | Static model catalogue |
| `timeout` | `float` | `number` | `30.0` | Request timeout in seconds |
| `max_retries` | `int` | `number` | `3` | Max retry attempts on retryable errors |
| `auth_method` | `str` | `string` | `"api_key"` | Auth method: `api_key`, `oauth`, `service_account` |
| `retryable_codes` | `list[int]` | `number[]` | `[429, 500, 502, 503]` | HTTP codes eligible for retry |
| `non_retryable_codes` | `list[int]` | `number[]` | `[400, 401, 403]` | HTTP codes that skip retry |
| `capabilities` | `list[str]` | `string[]` | `["generation.text-generation.chat-completion"]` | Capability tree paths (dot-notation) for pool matching |

## BaseRotationPolicyConfig

| Field | Python Type | TypeScript Type | Default | Description |
|---|---|---|---|---|
| `retry_limit` | `int` | `number` | `3` | Consecutive failures before deactivation |
| `error_rate_threshold` | `float` | `number` | `0.5` | Error rate (0.0-1.0) before deactivation |
| `error_codes` | `list[int]` | `number[]` | `[429, 500, 503]` | HTTP codes that count toward deactivation |
| `request_limit` | `Optional[int]` | `number?` | `None` | Max requests before deactivation |
| `token_limit` | `Optional[int]` | `number?` | `None` | Max tokens before deactivation |
| `budget_limit` | `Optional[float]` | `number?` | `None` | Max spend (USD) before deactivation |
| `cooldown_seconds` | `float` | `number` | `60.0` | Seconds before recovery eligibility |
| `model_priority` | `list[str]` | `string[]` | `[]` | Ordered model preference for selection |
| `provider_priority` | `list[str]` | `string[]` | `[]` | Ordered provider preference for selection |

## BaseSecretStoreConfig

| Field | Python Type | TypeScript Type | Default | Description |
|---|---|---|---|---|
| `secrets` | `dict[str, str]` | `Record<string, string>` | `{}` | Pre-loaded secret key-value pairs |
| `cache_enabled` | `bool` | `boolean` | `True` | Enable in-memory secret caching |
| `cache_ttl_ms` | `int` | `number` | `300000` | Cache time-to-live in milliseconds |
| `fail_on_missing` | `bool` | `boolean` | `True` | Raise error on missing secret |

## BaseStorageConfig

| Field | Python Type | TypeScript Type | Default | Description |
|---|---|---|---|---|
| `format` | `str` | `string` | `"json"` | Serialization format: `json`, `yaml`, `msgpack` |
| `compression` | `bool` | `boolean` | `False` | Compress data before writing |
| `locking_enabled` | `bool` | `boolean` | `True` | Enable advisory locking |
| `lock_timeout_seconds` | `float` | `number` | `30.0` | Max seconds to wait for lock |

## BaseObservabilityConfig

| Field | Python Type | TypeScript Type | Default | Description |
|---|---|---|---|---|
| `event_filter` | `list[str]` | `string[]` | `[]` | Event types to emit (empty = all) |
| `log_level` | `str` | `string` | `"metadata"` | Detail level: `metadata`, `summary`, `full` |
| `min_severity` | `str` | `string` | `"info"` | Minimum severity for trace entries: `debug`, `info`, `warning`, `error`, `critical`. Entries below this level are discarded. |
| `redact_secrets` | `bool` | `boolean` | `True` | Redact API keys from output |
| `flush_interval_seconds` | `float` | `number` | `60.0` | Statistics flush interval |
| `scopes` | `list[str]` | `string[]` | `["model", "provider", "pool"]` | Aggregation scopes |

## BaseDiscoveryConfig

| Field | Python Type | TypeScript Type | Default | Description |
|---|---|---|---|---|
| `providers` | `list[str]` | `string[]` | `[]` | Provider IDs to monitor |
| `sync_interval_seconds` | `float` | `number` | `3600.0` | Registry sync interval |
| `health_interval_seconds` | `float` | `number` | `60.0` | Health probe interval |
| `health_timeout_seconds` | `float` | `number` | `10.0` | Probe timeout |
| `failure_threshold` | `int` | `number` | `3` | Consecutive failures before deactivation |
| `on_new_model` | `str` | `string` | `"register"` | Action on new model: `register`, `notify`, `ignore` |
| `on_deprecated_model` | `str` | `string` | `"notify"` | Action on deprecated: `deactivate`, `notify`, `ignore` |