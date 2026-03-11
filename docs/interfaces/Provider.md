---
layout: default
title: "Provider Interface"
---

# Provider Interface

A provider connector exposes one or more AI models (or web API services) through a uniform, OpenAI-compatible API. It bridges the gap between the library's abstract capability model and the provider's concrete API: translating requests, managing authentication, tracking usage, and reporting operational data that drives routing and rotation decisions.

> **Reference:** [ConnectorInterfaces.md -- Provider](../ConnectorInterfaces.md#provider) | [ConnectorCatalogue.md -- Provider Connectors](../ConnectorCatalogue.md#provider-connectors)

---

## Sub-Interfaces

The provider connector is composed of seven sub-interfaces. Six are required; Infrastructure is optional.

| Sub-Interface | Required | Purpose |
| --- | --- | --- |
| **Model Execution** | yes | Execute requests through an OpenAI-compatible API |
| **Capabilities** | yes | Declare supported capabilities, delivery modes, and features |
| **Model Catalogue** | yes | List available models with attributes |
| **Quota & Rate Limits** | yes | Report usage, remaining capacity, and rate-limit headroom |
| **Cost & Pricing** | yes | Provide per-token and per-request cost metadata |
| **Error Classification** | yes | Classify errors as retryable or non-retryable |
| **Infrastructure** | no | Batch processing, file upload, fine-tuning, model discovery |

---

## Supporting Types

### Python

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class AuthMethod(Enum):
    """Authentication method used by a provider connector."""
    API_KEY = "api_key"
    OAUTH = "oauth"
    SERVICE_ACCOUNT = "service_account"


@dataclass
class TokenUsage:
    """Token consumption for a single completion request."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class ModelPricing:
    """Per-unit pricing for a model (per 1,000 tokens)."""
    input_per_1k_tokens: float = 0.0
    output_per_1k_tokens: float = 0.0
    per_request: Optional[float] = None


@dataclass
class ModelInfo:
    """Descriptor for a single model exposed by a provider."""
    id: str
    name: str
    capabilities: list[str]
    context_window: int
    max_output_tokens: int
    pricing: Optional[ModelPricing] = None


@dataclass
class CompletionRequest:
    """Normalized request sent to a provider for completion."""
    model: str
    messages: list[dict]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[list[dict]] = None
    stream: bool = False


@dataclass
class CompletionResponse:
    """Normalized response returned from a provider completion."""
    id: str
    model: str
    choices: list[dict]
    usage: TokenUsage


@dataclass
class QuotaStatus:
    """Current quota consumption and limits for a provider."""
    used: int
    remaining: Optional[int] = None
    limit: Optional[int] = None
    resets_at: Optional[datetime] = None


@dataclass
class RateLimitStatus:
    """Current rate-limit headroom for a provider."""
    requests_remaining: Optional[int] = None
    tokens_remaining: Optional[int] = None
    reset_seconds: Optional[float] = None


@dataclass
class ErrorClassificationResult:
    """Result of classifying a provider error."""
    retryable: bool
    category: str
    retry_after: Optional[float] = None


@dataclass
class BatchJob:
    """Descriptor for an asynchronous batch processing job."""
    id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    results_url: Optional[str] = None
```

### TypeScript

```typescript
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
    input_per_token: number;
    output_per_token: number;
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

/** Descriptor for an asynchronous batch processing job. */
interface BatchJob {
    id: string;
    status: string;
    created_at: Date;
    completed_at?: Date;
    results_url?: string;
}
```

---

## Interface Definitions

### Python

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator


class ModelExecution(ABC):
    """Execute requests through an OpenAI-compatible API.

    Handles authentication, format translation, and streaming.
    """

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request and return the full response."""
        ...

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionResponse]:
        """Send a completion request and yield partial responses as they arrive."""
        ...


class Capabilities(ABC):
    """Declare which capabilities, delivery modes, and features the provider supports.

    The router uses this to match requests to eligible providers.
    """

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return the list of capability identifiers this provider supports."""
        ...

    @abstractmethod
    def supports(self, capability: str) -> bool:
        """Check whether this provider supports a specific capability."""
        ...


class ModelCatalogue(ABC):
    """List available models with their attributes.

    Feeds pool membership and model definitions.
    """

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Return all models available from this provider."""
        ...

    @abstractmethod
    async def get_model_info(self, model_id: str) -> ModelInfo:
        """Return detailed information for a specific model."""
        ...


class QuotaRateLimits(ABC):
    """Report current usage, remaining capacity, and rate-limit headroom.

    Enables proactive rotation before limits are hit.
    """

    @abstractmethod
    async def check_quota(self) -> QuotaStatus:
        """Return current quota consumption and limits."""
        ...

    @abstractmethod
    async def get_rate_limits(self) -> RateLimitStatus:
        """Return current rate-limit headroom."""
        ...


class CostPricing(ABC):
    """Provide per-token and per-request cost metadata.

    Feeds cost-first selection and budget-based deactivation.
    """

    @abstractmethod
    async def get_pricing(self, model_id: str) -> ModelPricing:
        """Return pricing information for a specific model."""
        ...

    @abstractmethod
    def report_usage(self, model_id: str, usage: TokenUsage) -> None:
        """Report token usage for cost tracking and budget enforcement."""
        ...


class ErrorClassification(ABC):
    """Classify provider errors as retryable or non-retryable.

    Feeds intelligent retry and rotation decisions.
    """

    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorClassificationResult:
        """Classify an error and return retry guidance."""
        ...

    @abstractmethod
    def is_retryable(self, error: Exception) -> bool:
        """Return True if the error is eligible for retry."""
        ...


class Infrastructure(ABC):
    """Batch processing, file upload, fine-tuning, and model discovery.

    Optional interface. Not all providers support these operations;
    connectors declare which are available via the Capabilities interface.
    """

    async def submit_batch(self, requests: list[CompletionRequest]) -> BatchJob:
        """Submit a batch of completion requests for asynchronous processing."""
        raise NotImplementedError

    async def upload_file(self, path: str, purpose: str) -> str:
        """Upload a file to the provider and return its identifier."""
        raise NotImplementedError

    async def create_fine_tune(self, model: str, training_file: str, **kwargs) -> str:
        """Create a fine-tuning job and return its identifier."""
        raise NotImplementedError

    async def discover_models(self) -> list[ModelInfo]:
        """Enumerate models from the provider API."""
        raise NotImplementedError


class ProviderConnector(
    ModelExecution,
    Capabilities,
    ModelCatalogue,
    QuotaRateLimits,
    CostPricing,
    ErrorClassification,
):
    """Full provider connector combining all required interfaces.

    Implementations must provide concrete methods for all six required
    sub-interfaces. The optional Infrastructure interface can be mixed in
    separately when the provider supports batch, file, or fine-tuning
    operations.
    """
    pass
```

### TypeScript

```typescript
/** Execute requests through an OpenAI-compatible API. */
interface ModelExecution {
    /** Send a completion request and return the full response. */
    complete(request: CompletionRequest): Promise<CompletionResponse>;

    /** Send a completion request and yield partial responses as they arrive. */
    stream(request: CompletionRequest): AsyncIterable<CompletionResponse>;
}

/** Declare which capabilities, delivery modes, and features the provider supports. */
interface Capabilities {
    /** Return the list of capability identifiers this provider supports. */
    getCapabilities(): string[];

    /** Check whether this provider supports a specific capability. */
    supports(capability: string): boolean;
}

/** List available models with their attributes. */
interface ModelCatalogue {
    /** Return all models available from this provider. */
    listModels(): Promise<ModelInfo[]>;

    /** Return detailed information for a specific model. */
    getModelInfo(modelId: string): Promise<ModelInfo>;
}

/** Report current usage, remaining capacity, and rate-limit headroom. */
interface QuotaRateLimits {
    /** Return current quota consumption and limits. */
    checkQuota(): Promise<QuotaStatus>;

    /** Return current rate-limit headroom. */
    getRateLimits(): Promise<RateLimitStatus>;
}

/** Provide per-token and per-request cost metadata. */
interface CostPricing {
    /** Return pricing information for a specific model. */
    getPricing(modelId: string): Promise<ModelPricing>;

    /** Report token usage for cost tracking and budget enforcement. */
    reportUsage(modelId: string, usage: TokenUsage): void;
}

/** Classify provider errors as retryable or non-retryable. */
interface ErrorClassification {
    /** Classify an error and return retry guidance. */
    classifyError(error: Error): ErrorClassificationResult;

    /** Return true if the error is eligible for retry. */
    isRetryable(error: Error): boolean;
}

/** Batch processing, file upload, fine-tuning, and model discovery. Optional. */
interface Infrastructure {
    /** Submit a batch of completion requests for asynchronous processing. */
    submitBatch?(requests: CompletionRequest[]): Promise<BatchJob>;

    /** Upload a file to the provider and return its identifier. */
    uploadFile?(path: string, purpose: string): Promise<string>;

    /** Create a fine-tuning job and return its identifier. */
    createFineTune?(model: string, trainingFile: string, options?: Record<string, unknown>): Promise<string>;

    /** Enumerate models from the provider API. */
    discoverModels?(): Promise<ModelInfo[]>;
}

/** Full provider connector combining all required interfaces. */
interface ProviderConnector extends ModelExecution, Capabilities, ModelCatalogue, QuotaRateLimits, CostPricing, ErrorClassification {}
```

---

## Common Configuration

Parameters shared by all provider connectors. Individual connectors may add connector-specific parameters (see [ConnectorCatalogue.md -- Provider Connectors](../ConnectorCatalogue.md#provider-connectors)).

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `provider.execution.base_url` | string | *(provider-specific)* | Custom API endpoint URL. Overrides the default for self-hosted or proxy deployments. |
| `provider.execution.timeout` | duration | `30s` | Request timeout. Applied to all API calls. |
| `provider.execution.max_retries` | integer | `3` | Provider-level retries before reporting failure to the router. |
| `provider.auth.method` | string | `api_key` | Authentication method: `api_key`, `oauth`, `service_account`. |
| `provider.auth.api_key` | string | -- | API key or secret reference (`${secrets:key-name}`). |
| `provider.auth.key_rotation` | boolean | `false` | Enable automatic key rotation. |
| `provider.catalogue.auto_discover` | boolean | `false` | Enumerate models from the provider API at startup. |
| `provider.catalogue.refresh_interval` | duration | `1h` | Re-sync model catalogue on this schedule. |
| `provider.quota.query_current` | boolean | `false` | Provider API supports querying current usage. |
| `provider.quota.query_remaining` | boolean | `false` | Provider API supports querying remaining capacity. |
| `provider.quota.reset_schedule` | string | `monthly` | Quota reset frequency: `monthly`, `daily`, `rolling`. |
| `provider.budget.daily_limit` | number | -- | Daily spend cap in USD. Triggers deactivation when exceeded. |
| `provider.budget.monthly_limit` | number | -- | Monthly spend cap in USD. |
| `provider.pricing.query` | boolean | `false` | Provider API supports pricing queries. |
| `provider.error.retryable_codes` | list | `[429, 500, 502, 503]` | HTTP status codes eligible for retry. |
| `provider.error.non_retryable_codes` | list | `[400, 401, 403]` | HTTP codes that skip retry and trigger immediate rotation. |
| `provider.infrastructure.batch` | boolean | `false` | Provider supports batch submissions. |
| `provider.infrastructure.files` | boolean | `false` | Provider supports file upload/management. |
| `provider.infrastructure.fine_tuning` | boolean | `false` | Provider supports fine-tuning. |
| `provider.enabled` | boolean | `true` | Enable or disable the provider. |

---

## CDK Base Class

The CDK provides [BaseProvider](../cdk/BaseClasses.md#baseprovider) with OpenAI-compatible defaults and 5 protected hook methods for customization. Specialized classes: [OpenAICompatibleProvider](../cdk/BaseClasses.md#openaicompatibleprovider), [HttpApiProvider](../cdk/BaseClasses.md#httpapiprovider). See [DeveloperGuide -- Tutorial 1](../cdk/DeveloperGuide.md#tutorial-1-your-first-provider-in-10-lines).
