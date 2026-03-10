---
layout: default
title: "CDK Developer Guide"
---

# CDK Developer Guide

A tutorial-driven guide for using ModelMesh Lite, from the convenience layer (`modelmesh.create()`) through custom connectors built with the Connector Development Kit (CDK). Tutorials 0-1 cover the OpenAI-compatible convenience API, Tutorials 2-7 progress from zero-code configuration through full connector suites and automated testing, and Tutorial 8 provides a beginner-friendly walkthrough for new programmers.

> **Prerequisites:** Tutorials 0-1 require only `pip install modelmesh-lite` and an API key. Tutorials 2-7 assume familiarity with the [CDK Overview](Overview.html) and the [class hierarchy](Overview.html#class-hierarchy). Tutorial 8 is self-contained. Each tutorial references the relevant CDK reference documents inline.

---

## Table of Contents

0. [Tutorial 0: Chat Completion in 4 Lines -- OpenAI-Compatible](#tutorial-0-chat-completion-in-4-lines----openai-compatible)
1. [Tutorial 1: Multi-Provider Rotation with Capabilities](#tutorial-1-multi-provider-rotation-with-capabilities)
2. [Tutorial 2: Your First Provider in 10 Lines](#tutorial-2-your-first-provider-in-10-lines)
3. [Tutorial 3: Custom Error Handling](#tutorial-3-custom-error-handling)
4. [Tutorial 4: Custom Rotation Policy from Scratch](#tutorial-4-custom-rotation-policy-from-scratch)
5. [Tutorial 5: Derive from an Existing Connector](#tutorial-5-derive-from-an-existing-connector)
6. [Tutorial 6: Complete Connector Set for "AcmeCorp"](#tutorial-6-complete-connector-set-for-acmecorp)
7. [Tutorial 7: Testing with CDK Utilities](#tutorial-7-testing-with-cdk-utilities)
8. [Tutorial 8: Teen Programmer Guide -- Build Your First AI App](#tutorial-8-teen-programmer-guide----build-your-first-ai-app)
9. [Tutorial 9: Building a Browser-Compatible Provider](#tutorial-9-building-a-browser-compatible-provider)
10. [Tutorial 10: Audio Provider Development](#tutorial-10-audio-provider-development)

---

## Tutorial 0: Chat Completion in 4 Lines -- OpenAI-Compatible

### What you will learn

- How `modelmesh.create()` returns an OpenAI SDK-compatible client
- How virtual model names map to capabilities/pools
- How providers are auto-detected from environment variables

### Background

The convenience layer makes ModelMesh usage nearly identical to the OpenAI SDK. The only differences: the import (`modelmesh` instead of `openai`), the `create()` call (which specifies a capability instead of nothing), and the `model` parameter (which uses a virtual name instead of a real model name). Everything else -- `client.chat.completions.create()`, response shape, streaming -- is identical.

### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Explain what an API is in two sentences."}],
)
print(response.choices[0].message.content)
```

### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";

const client = create("chat-completion");

const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Explain what an API is in two sentences." }],
});
console.log(response.choices[0].message.content);
```

### Comparison with OpenAI SDK

| | OpenAI SDK | ModelMesh Lite |
| --- | --- | --- |
| **Import** | `import openai` | `import modelmesh` |
| **Client creation** | `client = openai.OpenAI()` | `client = modelmesh.create("chat-completion")` |
| **Model parameter** | `model="gpt-4o"` | `model="chat-completion"` |
| **API call** | `client.chat.completions.create(...)` | `client.chat.completions.create(...)` |
| **Response shape** | `response.choices[0].message.content` | `response.choices[0].message.content` |
| **Streaming** | `stream=True` | `stream=True` |
| **Auth** | `OPENAI_API_KEY` env var | Any supported provider's env var |

### What happens under the hood

1. `modelmesh.create("chat-completion")` scans environment variables for known API keys (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`)
2. Configures each found provider with its default models
3. Creates a capability pool targeting `"chat-completion"`
4. Returns a `MeshClient` with an OpenAI-compatible interface
5. `model="chat-completion"` resolves to that pool, which routes to the best active model

### What's next

[Tutorial 1](#tutorial-1-multi-provider-rotation-with-capabilities) shows how to request multiple capabilities, filter by provider, and choose a rotation strategy.

---

## Tutorial 1: Multi-Provider Rotation with Capabilities

### What you will learn

- How to specify multiple capabilities in a single `modelmesh.create()` call
- How to filter by specific providers and models
- How to choose a rotation strategy (e.g., `"cost-first"`, `"latency-first"`)
- How to use multiple OpenAI-compatible endpoints (chat + embeddings) from the same client

### Background

When you pass multiple capability names to `modelmesh.create()`, the returned `MeshClient` exposes an OpenAI-compatible interface for each capability. The `providers` parameter filters which providers are eligible, and the `strategy` parameter controls how the pool selects among active models.

### Python

```python
import modelmesh

client = modelmesh.create(
    "chat-completion", "text-embeddings",
    providers=["openai", "anthropic"],
    strategy="cost-first",
)

# Chat completion
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)

# Embeddings
embeddings = client.embeddings.create(
    model="text-embeddings",
    input="Hello world",
)
print(f"Embedding dimension: {len(embeddings.data[0].embedding)}")
```

### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";

const client = create(
    "chat-completion", "text-embeddings",
    {
        providers: ["openai", "anthropic"],
        strategy: "cost-first",
    },
);

// Chat completion
const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "Hello!" }],
});
console.log(response.choices[0].message.content);

// Embeddings
const embeddings = await client.embeddings.create({
    model: "text-embeddings",
    input: "Hello world",
});
console.log(`Embedding dimension: ${embeddings.data[0].embedding.length}`);
```

### Variation: Predefined Pool

```python
client = modelmesh.create(pool="text-generation")
response = client.chat.completions.create(
    model="text-generation",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

```typescript
const client = create({ pool: "text-generation" });
const response = await client.chat.completions.create({
    model: "text-generation",
    messages: [{ role: "user", content: "Hello!" }],
});
```

### Variation: Full Config

```python
client = modelmesh.create(config="modelmesh.yaml")
```

```typescript
const client = create({ config: "modelmesh.yaml" });
```

### What's next

[Tutorial 2](#tutorial-2-your-first-provider-in-10-lines) introduces the CDK and shows how to build a provider connector from scratch using `OpenAICompatibleProvider`.

---

## Tutorial 2: Your First Provider in 10 Lines

### What you will learn

- How `OpenAICompatibleProvider` removes the need for any code
- How to configure a provider entirely through a dataclass config (Python) or an interface literal (TypeScript)
- How to issue a chat completion call against the configured provider

### Background

The CDK is designed so that the simplest connector requires no code at all. `OpenAICompatibleProvider` is a semantic alias for `BaseProvider` -- it inherits every default (OpenAI-format request translation, SSE streaming, retry logic, error classification) without overriding anything. You supply a `BaseProviderConfig` with a `base_url` and `api_key`, and the provider is ready to use.

> **Reference:** [BaseClasses.md -- OpenAICompatibleProvider](BaseClasses.html#openaicompatibleprovider) | [BaseClasses.md -- BaseProviderConfig](BaseClasses.html#configuration)

### Python

```python
import asyncio
from modelmesh.cdk import OpenAICompatibleProvider, BaseProviderConfig
from modelmesh.interfaces.provider import CompletionRequest, ModelInfo


# 1. Configure -- this is the entire "connector"
config = BaseProviderConfig(
    base_url="https://api.openai.com",
    api_key="sk-your-key-here",
    models=[
        ModelInfo(
            id="gpt-4o",
            name="GPT-4o",
            capabilities=["generation.text-generation.chat-completion"],
            features={"tool_calling": True, "vision": True, "system_prompt": True},
            context_window=128_000,
            max_output_tokens=16_384,
        ),
    ],
)

# 2. Instantiate
provider = OpenAICompatibleProvider(config)

# 3. Use
async def main() -> None:
    response = await provider.complete(
        CompletionRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Say hello in three languages."}],
        )
    )
    print(response.choices[0]["message"]["content"])
    print(f"Tokens used: {response.usage.total_tokens}")

asyncio.run(main())
```

### TypeScript

```typescript
import {
    OpenAICompatibleProvider,
    BaseProviderConfig,
} from "@nistrapa/modelmesh-core/cdk";
import { CompletionRequest, ModelInfo } from "@nistrapa/modelmesh-core/interfaces/provider";

// 1. Configure -- this is the entire "connector"
const config: BaseProviderConfig = {
    baseUrl: "https://api.openai.com",
    apiKey: "sk-your-key-here",
    models: [
        {
            id: "gpt-4o",
            name: "GPT-4o",
            capabilities: ["generation.text-generation.chat-completion"],
            features: { tool_calling: true, vision: true, system_prompt: true },
            context_window: 128_000,
            max_output_tokens: 16_384,
        },
    ],
};

// 2. Instantiate
const provider = new OpenAICompatibleProvider(config);

// 3. Use
async function main(): Promise<void> {
    const response = await provider.complete({
        model: "gpt-4o",
        messages: [{ role: "user", content: "Say hello in three languages." }],
    });
    console.log(response.choices[0].message.content);
    console.log(`Tokens used: ${response.usage.total_tokens}`);
}

main();
```

### What just happened

Zero lines of connector code were written. The `OpenAICompatibleProvider` class inherited all behavior from `BaseProvider`: HTTP transport, retry logic, error classification, streaming support, quota tracking, and OpenAI-format request/response translation. The config dataclass was the only input.

You can also skip code entirely and declare this in YAML:

```yaml
providers:
  my-openai:
    connector: openai-compatible
    config:
      base_url: "https://api.openai.com"
      auth:
        method: api_key
        api_key: "${secrets:openai-key}"
      models:
        - id: "gpt-4o"
          capabilities: ["generation.text-generation.chat-completion"]
          context_window: 128000
```

### What's next

[Tutorial 3](#tutorial-3-custom-error-handling) shows how to override a single hook method when the defaults do not match your API's behavior.

---

## Tutorial 3: Custom Error Handling

### What you will learn

- How to subclass `BaseProvider` and override a single protected hook method
- The hook method pattern: override one method, inherit everything else
- How `classify_error()` maps HTTP errors to retryable/non-retryable categories

### Background

Some APIs return errors in a non-standard format. For example, an internal ML service might return HTTP 200 with an error payload in the JSON body instead of using standard HTTP status codes. The CDK's hook method pattern lets you override `classify_error()` to handle this without touching request translation, retry orchestration, or streaming.

> **Reference:** [BaseClasses.md -- Protected Hook Methods](BaseClasses.html#protected-hook-methods) | [BaseClasses.md -- Error Classification](BaseClasses.html#methods-and-default-behavior)

### Python

```python
from modelmesh.cdk import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ErrorClassificationResult,
    TokenUsage,
)


class InternalMLProvider(BaseProvider):
    """Provider for an internal ML API that returns errors inside 200 responses.

    The API returns HTTP 200 for everything. Errors are signaled by an
    ``"error"`` key in the JSON body with a ``"code"`` field:
        - "rate_limited"  -> retryable, wait 10s
        - "model_loading" -> retryable, wait 30s
        - "invalid_input" -> not retryable
        - anything else   -> not retryable
    """

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Check for in-band errors before parsing the response."""
        if "error" in data:
            error_code = data["error"].get("code", "unknown")
            raise InternalMLError(error_code, data["error"].get("message", ""))

        return CompletionResponse(
            id=data["request_id"],
            model=data["model_name"],
            choices=[{"message": {"content": data["output"]}}],
            usage=TokenUsage(
                prompt_tokens=data["tokens"]["input"],
                completion_tokens=data["tokens"]["output"],
                total_tokens=data["tokens"]["input"] + data["tokens"]["output"],
            ),
        )

    def classify_error(self, error: Exception) -> ErrorClassificationResult:
        """Classify in-band errors from the internal ML API."""
        if isinstance(error, InternalMLError):
            if error.code == "rate_limited":
                return ErrorClassificationResult(
                    retryable=True, category="rate_limit", retry_after=10.0
                )
            if error.code == "model_loading":
                return ErrorClassificationResult(
                    retryable=True, category="server_error", retry_after=30.0
                )
            return ErrorClassificationResult(
                retryable=False, category="client_error"
            )

        # Fall back to the base class for standard HTTP errors
        return super().classify_error(error)


class InternalMLError(Exception):
    """Error returned inside a 200 response from the internal ML API."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
```

### TypeScript

```typescript
import { BaseProvider, BaseProviderConfig } from "@nistrapa/modelmesh-core/cdk";
import {
    CompletionResponse,
    ErrorClassificationResult,
    TokenUsage,
} from "@nistrapa/modelmesh-core/interfaces/provider";

/** Error returned inside a 200 response from the internal ML API. */
class InternalMLError extends Error {
    constructor(
        public readonly code: string,
        message: string,
    ) {
        super(`${code}: ${message}`);
        this.name = "InternalMLError";
    }
}

/**
 * Provider for an internal ML API that returns errors inside 200 responses.
 *
 * The API signals errors via an "error" key in the JSON body rather than
 * HTTP status codes.
 */
class InternalMLProvider extends BaseProvider {
    protected parseResponse(data: Record<string, unknown>): CompletionResponse {
        if (data.error) {
            const err = data.error as { code?: string; message?: string };
            throw new InternalMLError(err.code ?? "unknown", err.message ?? "");
        }

        const tokens = data.tokens as { input: number; output: number };
        return {
            id: data.request_id as string,
            model: data.model_name as string,
            choices: [{ message: { content: data.output as string } }],
            usage: {
                prompt_tokens: tokens.input,
                completion_tokens: tokens.output,
                total_tokens: tokens.input + tokens.output,
            },
        };
    }

    classifyError(error: Error): ErrorClassificationResult {
        if (error instanceof InternalMLError) {
            if (error.code === "rate_limited") {
                return { retryable: true, category: "rate_limit", retry_after: 10 };
            }
            if (error.code === "model_loading") {
                return { retryable: true, category: "server_error", retry_after: 30 };
            }
            return { retryable: false, category: "client_error" };
        }

        // Fall back to the base class for standard HTTP errors
        return super.classifyError(error);
    }
}
```

### Key takeaway

Two methods were overridden: `_parse_response` (to detect in-band errors) and `classify_error` (to classify them). Everything else -- HTTP transport, retry loops, streaming, quota tracking, model catalogue -- is inherited from `BaseProvider` unchanged.

### What's next

[Tutorial 4](#tutorial-4-custom-rotation-policy-from-scratch) moves beyond providers to build a completely custom rotation policy from scratch.

---

## Tutorial 4: Custom Rotation Policy from Scratch

### What you will learn

- How `BaseRotationPolicy` unifies the three rotation sub-interfaces (Deactivation, Recovery, Selection)
- How to override `should_deactivate()` to implement domain-specific rules
- How to override `select()` and `score()` for time-of-day cost optimization

### Background

The default `BaseRotationPolicy` deactivates models based on failure counts and error rates, recovers after a fixed cooldown, and selects by priority list. But some organizations need custom logic -- for example, routing to cheaper models during off-peak hours and deactivating all non-essential models during scheduled maintenance windows.

> **Reference:** [BaseClasses.md -- BaseRotationPolicy](BaseClasses.html#baserotationpolicy) | [BaseClasses.md -- BaseRotationPolicyConfig](BaseClasses.html#baserotationpolicyconfig)

### Python

```python
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.cdk import BaseRotationPolicy, BaseRotationPolicyConfig
from modelmesh.interfaces.rotation_policy import (
    CompletionRequest,
    DeactivationReason,
    ModelSnapshot,
    SelectionResult,
)


@dataclass
class TimeOfDayPolicyConfig(BaseRotationPolicyConfig):
    """Extended config with maintenance windows and cost tiers."""
    maintenance_windows: list[tuple[int, int]] = field(
        default_factory=lambda: [(2, 4)]  # 2:00 AM - 4:00 AM UTC
    )
    peak_hours: tuple[int, int] = (9, 17)  # 9 AM - 5 PM UTC
    cheap_models: list[str] = field(
        default_factory=lambda: ["gpt-3.5-turbo", "claude-3-haiku"]
    )
    premium_models: list[str] = field(
        default_factory=lambda: ["gpt-4o", "claude-3-opus"]
    )


class TimeOfDayRotationPolicy(BaseRotationPolicy):
    """Rotation policy that routes by time-of-day cost tiers.

    - During maintenance windows: deactivate all non-essential models
    - During peak hours: prefer premium models for lower latency
    - During off-peak hours: prefer cheap models to reduce cost
    """

    def __init__(self, config: TimeOfDayPolicyConfig) -> None:
        super().__init__(config)
        self._tod_config = config

    def _is_maintenance(self) -> bool:
        """Return True if the current hour falls in a maintenance window."""
        hour = datetime.utcnow().hour
        return any(start <= hour < end for start, end in self._tod_config.maintenance_windows)

    def _is_peak(self) -> bool:
        """Return True if the current hour is within peak hours."""
        hour = datetime.utcnow().hour
        start, end = self._tod_config.peak_hours
        return start <= hour < end

    def should_deactivate(self, snapshot: ModelSnapshot) -> bool:
        """Deactivate non-essential models during maintenance windows."""
        # Always respect the base class threshold checks
        if super().should_deactivate(snapshot):
            return True

        # During maintenance, deactivate everything except cheap models
        if self._is_maintenance():
            return snapshot.model_id not in self._tod_config.cheap_models

        return False

    def get_reason(self, snapshot: ModelSnapshot) -> DeactivationReason | None:
        """Return the deactivation reason, including maintenance."""
        base_reason = super().get_reason(snapshot)
        if base_reason is not None:
            return base_reason

        if self._is_maintenance() and snapshot.model_id not in self._tod_config.cheap_models:
            return DeactivationReason.MAINTENANCE_WINDOW

        return None

    def score(self, candidate: ModelSnapshot, request: CompletionRequest) -> float:
        """Score candidates by time-of-day cost tier.

        Peak hours:    premium models get +500 bonus
        Off-peak:      cheap models get +500 bonus
        All times:     base score from error rate still applies
        """
        base_score = super().score(candidate, request)

        if self._is_peak():
            if candidate.model_id in self._tod_config.premium_models:
                return base_score + 500.0
        else:
            if candidate.model_id in self._tod_config.cheap_models:
                return base_score + 500.0

        return base_score


# Usage
policy = TimeOfDayRotationPolicy(TimeOfDayPolicyConfig(
    retry_limit=3,
    cooldown_seconds=120.0,
    maintenance_windows=[(2, 4)],
    peak_hours=(9, 17),
    cheap_models=["gpt-3.5-turbo"],
    premium_models=["gpt-4o"],
))
```

### TypeScript

```typescript
import {
    BaseRotationPolicy,
    BaseRotationPolicyConfig,
} from "@nistrapa/modelmesh-core/cdk";
import {
    CompletionRequest,
    DeactivationReason,
    ModelSnapshot,
    SelectionResult,
} from "@nistrapa/modelmesh-core/interfaces/rotation_policy";

/** Extended config with maintenance windows and cost tiers. */
interface TimeOfDayPolicyConfig extends BaseRotationPolicyConfig {
    maintenanceWindows?: [number, number][];  // [startHour, endHour] UTC
    peakHours?: [number, number];             // [startHour, endHour] UTC
    cheapModels?: string[];
    premiumModels?: string[];
}

/**
 * Rotation policy that routes by time-of-day cost tiers.
 *
 * - Maintenance windows: deactivate non-essential models
 * - Peak hours: prefer premium models for lower latency
 * - Off-peak: prefer cheap models to reduce cost
 */
class TimeOfDayRotationPolicy extends BaseRotationPolicy {
    private readonly maintenanceWindows: [number, number][];
    private readonly peakHours: [number, number];
    private readonly cheapModels: Set<string>;
    private readonly premiumModels: Set<string>;

    constructor(config: TimeOfDayPolicyConfig) {
        super(config);
        this.maintenanceWindows = config.maintenanceWindows ?? [[2, 4]];
        this.peakHours = config.peakHours ?? [9, 17];
        this.cheapModels = new Set(config.cheapModels ?? ["gpt-3.5-turbo", "claude-3-haiku"]);
        this.premiumModels = new Set(config.premiumModels ?? ["gpt-4o", "claude-3-opus"]);
    }

    private isMaintenance(): boolean {
        const hour = new Date().getUTCHours();
        return this.maintenanceWindows.some(([start, end]) => hour >= start && hour < end);
    }

    private isPeak(): boolean {
        const hour = new Date().getUTCHours();
        return hour >= this.peakHours[0] && hour < this.peakHours[1];
    }

    shouldDeactivate(snapshot: ModelSnapshot): boolean {
        if (super.shouldDeactivate(snapshot)) {
            return true;
        }

        if (this.isMaintenance()) {
            return !this.cheapModels.has(snapshot.model_id);
        }

        return false;
    }

    getReason(snapshot: ModelSnapshot): DeactivationReason | null {
        const baseReason = super.getReason(snapshot);
        if (baseReason !== null) {
            return baseReason;
        }

        if (this.isMaintenance() && !this.cheapModels.has(snapshot.model_id)) {
            return DeactivationReason.MAINTENANCE_WINDOW;
        }

        return null;
    }

    score(candidate: ModelSnapshot, request: CompletionRequest): number {
        const baseScore = super.score(candidate, request);

        if (this.isPeak()) {
            if (this.premiumModels.has(candidate.model_id)) {
                return baseScore + 500;
            }
        } else {
            if (this.cheapModels.has(candidate.model_id)) {
                return baseScore + 500;
            }
        }

        return baseScore;
    }
}

// Usage
const policy = new TimeOfDayRotationPolicy({
    retryLimit: 3,
    cooldownSeconds: 120,
    maintenanceWindows: [[2, 4]],
    peakHours: [9, 17],
    cheapModels: ["gpt-3.5-turbo"],
    premiumModels: ["gpt-4o"],
});
```

### Key takeaway

The custom policy overrides three methods (`should_deactivate`, `get_reason`, `score`) and delegates to `super()` for all baseline behavior. Recovery logic, candidate filtering, and the `select()` orchestration are all inherited unchanged from `BaseRotationPolicy`.

### What's next

[Tutorial 5](#tutorial-5-derive-from-an-existing-connector) shows how to extend a pre-shipped connector rather than a base class.

---

## Tutorial 5: Derive from an Existing Connector

### What you will learn

- How to extend a pre-shipped connector (the OpenAI provider) to add Azure OpenAI support
- How `super()` calls preserve all parent behavior while you add custom headers and endpoint routing
- The difference between deriving from a base class vs. deriving from a concrete connector

### Background

When a pre-shipped connector is 90% correct and you only need to adjust authentication, URL structure, or a few header values, derive from the concrete connector class instead of the base class. This inherits all provider-specific logic (model catalogue, pricing tables, error mapping) in addition to the CDK base behavior.

> **Reference:** [Overview.md -- Derive from an Existing Pre-Shipped Connector](Overview.html#3-derive-from-an-existing-pre-shipped-connector) | [BaseClasses.md -- BaseProvider Protected Hooks](BaseClasses.html#protected-hook-methods)

### Python

```python
from dataclasses import dataclass
from typing import Optional

from modelmesh.connectors.openai import OpenAIProvider


@dataclass
class AzureOpenAIConfig:
    """Configuration specific to Azure OpenAI deployments."""
    resource: str          # Azure resource name
    deployment: str        # Deployment name (maps to model)
    api_key: str
    api_version: str = "2024-02-01"
    models: list = None    # Inherited from parent; auto-populated below


class AzureOpenAIProvider(OpenAIProvider):
    """OpenAI connector adapted for Azure-hosted deployments.

    Azure OpenAI differs from standard OpenAI in three ways:
    1. URL structure: https://{resource}.openai.azure.com/openai/deployments/{deployment}
    2. Auth header: ``api-key`` instead of ``Authorization: Bearer ...``
    3. Query parameter: ``api-version`` is required on every request

    Everything else -- request format, response parsing, streaming,
    error classification, retry logic -- is identical to OpenAI.
    """

    def __init__(self, config: AzureOpenAIConfig) -> None:
        # Build a standard OpenAI config for the parent
        from modelmesh.cdk import BaseProviderConfig
        parent_config = BaseProviderConfig(
            base_url=(
                f"https://{config.resource}.openai.azure.com"
                f"/openai/deployments/{config.deployment}"
            ),
            api_key=config.api_key,
            models=config.models or [],
        )
        super().__init__(parent_config)
        self._azure_config = config

    def _build_headers(self) -> dict[str, str]:
        """Use Azure's api-key header instead of Bearer token."""
        headers = super()._build_headers()
        # Remove the standard Bearer token
        headers.pop("Authorization", None)
        # Add the Azure-specific api-key header
        headers["api-key"] = self._azure_config.api_key
        return headers

    def _get_completion_endpoint(self) -> str:
        """Append the required api-version query parameter."""
        base = super()._get_completion_endpoint()
        return f"{base}?api-version={self._azure_config.api_version}"


# Usage
provider = AzureOpenAIProvider(AzureOpenAIConfig(
    resource="my-company",
    deployment="gpt-4o-prod",
    api_key="azure-key-here",
    api_version="2024-02-01",
))
```

### TypeScript

```typescript
import { OpenAIProvider } from "@nistrapa/modelmesh-core/connectors/openai";
import { BaseProviderConfig } from "@nistrapa/modelmesh-core/cdk";

/** Configuration specific to Azure OpenAI deployments. */
interface AzureOpenAIConfig {
    resource: string;       // Azure resource name
    deployment: string;     // Deployment name
    apiKey: string;
    apiVersion?: string;    // default "2024-02-01"
}

/**
 * OpenAI connector adapted for Azure-hosted deployments.
 *
 * Overrides URL structure (resource + deployment), auth header
 * (api-key instead of Bearer), and adds the api-version query param.
 * Everything else is inherited from OpenAIProvider.
 */
class AzureOpenAIProvider extends OpenAIProvider {
    private readonly azureConfig: Required<AzureOpenAIConfig>;

    constructor(config: AzureOpenAIConfig) {
        const parentConfig: BaseProviderConfig = {
            baseUrl:
                `https://${config.resource}.openai.azure.com` +
                `/openai/deployments/${config.deployment}`,
            apiKey: config.apiKey,
        };
        super(parentConfig);
        this.azureConfig = {
            resource: config.resource,
            deployment: config.deployment,
            apiKey: config.apiKey,
            apiVersion: config.apiVersion ?? "2024-02-01",
        };
    }

    protected buildHeaders(): Record<string, string> {
        const headers = super.buildHeaders();
        // Replace Bearer token with Azure's api-key header
        delete headers["Authorization"];
        headers["api-key"] = this.azureConfig.apiKey;
        return headers;
    }

    protected getCompletionEndpoint(): string {
        const base = super.getCompletionEndpoint();
        return `${base}?api-version=${this.azureConfig.apiVersion}`;
    }
}

// Usage
const provider = new AzureOpenAIProvider({
    resource: "my-company",
    deployment: "gpt-4o-prod",
    apiKey: "azure-key-here",
    apiVersion: "2024-02-01",
});
```

### Key takeaway

Only two hook methods were overridden: `_build_headers` (to swap the auth scheme) and `_get_completion_endpoint` (to add the API version parameter). The constructor translates Azure-specific config into the parent's expected format. All OpenAI-specific behavior -- request translation, response parsing, streaming, error classification, model catalogue, retry logic -- is inherited from `OpenAIProvider` through `super()`.

### What's next

[Tutorial 6](#tutorial-6-complete-connector-set-for-acmecorp) shows how to build all six connector types for a fictional company.

---

## Tutorial 6: Complete Connector Set for "AcmeCorp"

### What you will learn

- How all six connector types work together in a real deployment
- How to keep each connector short by leveraging base class defaults
- How to wire all connectors together with YAML configuration

### Background

AcmeCorp runs an internal AI platform. They need a provider for their custom ML API, a rotation policy that respects their SLA tiers, a secret store backed by environment variables, file-system storage for state, a webhook-based observability pipeline, and a discovery connector that polls their internal model registry. Each connector inherits from the appropriate CDK base class and overrides only what differs.

> **Reference:** [BaseClasses.md](BaseClasses.html) (all six base classes) | [Mixins.md](Mixins.html) (RetryMixin, CacheMixin)

### Python

```python
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

from modelmesh.cdk import (
    BaseProvider, BaseProviderConfig,
    BaseRotationPolicy, BaseRotationPolicyConfig,
    BaseSecretStore, BaseSecretStoreConfig,
    BaseStorage, BaseStorageConfig,
    BaseObservability, BaseObservabilityConfig,
    BaseDiscovery, BaseDiscoveryConfig,
)
from modelmesh.interfaces.provider import (
    CompletionRequest, CompletionResponse, TokenUsage,
)
from modelmesh.interfaces.rotation_policy import (
    ModelSnapshot, SelectionResult, CompletionRequest as RotationRequest,
)
from modelmesh.interfaces.discovery import ProbeResult


# ── 1. AcmeProvider ────────────────────────────────────────────────

class AcmeProvider(BaseProvider):
    """Provider for AcmeCorp's internal /api/predict endpoint."""

    def _get_completion_endpoint(self) -> str:
        return f"{self._config.base_url.rstrip('/')}/api/predict"

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        return {
            "model_name": request.model,
            "prompt": request.messages[-1]["content"],
            "params": {"max_length": request.max_tokens or 1024},
        }

    def _parse_response(self, data: dict) -> CompletionResponse:
        return CompletionResponse(
            id=data["id"],
            model=data["model_name"],
            choices=[{"message": {"content": data["result"]}}],
            usage=TokenUsage(
                prompt_tokens=data["usage"]["in"],
                completion_tokens=data["usage"]["out"],
                total_tokens=data["usage"]["in"] + data["usage"]["out"],
            ),
        )


# ── 2. AcmeRotation ───────────────────────────────────────────────

class AcmeRotation(BaseRotationPolicy):
    """Rotation policy that treats SLA-tier models as higher priority."""

    def score(self, candidate: ModelSnapshot, request: RotationRequest) -> float:
        base = super().score(candidate, request)
        # Boost SLA-tier models by 200 points
        if candidate.provider_id == "acme-sla":
            return base + 200.0
        return base


# ── 3. AcmeSecretStore ────────────────────────────────────────────

class AcmeSecretStore(BaseSecretStore):
    """Secret store that reads from environment variables with an ACME_ prefix."""

    def _resolve(self, name: str) -> str | None:
        env_name = f"ACME_{name.upper().replace('-', '_')}"
        return os.environ.get(env_name)


# ── 4. AcmeStorage ────────────────────────────────────────────────

class AcmeStorage(BaseStorage):
    """File-system storage under /var/acme/modelmesh/."""

    def __init__(self, config: BaseStorageConfig) -> None:
        super().__init__(config)
        self._root = Path("/var/acme/modelmesh")
        self._root.mkdir(parents=True, exist_ok=True)

    async def save(self, key: str, entry) -> None:
        path = self._root / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"key": entry.key, "data": entry.data.decode()}))
        await super().save(key, entry)

    async def load(self, key: str):
        path = self._root / f"{key}.json"
        if path.exists():
            return await super().load(key)
        return None


# ── 5. AcmeObservability ──────────────────────────────────────────

class AcmeObservability(BaseObservability):
    """Observability connector that posts formatted lines to a webhook.

    Only ``_write`` is overridden. All four data methods -- ``emit``,
    ``log``, ``flush``, and ``trace`` (with severity filtering via
    ``min_severity``) -- are inherited from ``BaseObservability`` and
    call ``_write`` automatically.
    """

    def __init__(self, config: BaseObservabilityConfig, webhook_url: str) -> None:
        super().__init__(config)
        self._webhook_url = webhook_url

    def _write(self, line: str) -> None:
        """POST each formatted line to the AcmeCorp logging webhook."""
        httpx.post(self._webhook_url, json={"message": line}, timeout=5.0)


# ── 6. AcmeDiscovery ─────────────────────────────────────────────

class AcmeDiscovery(BaseDiscovery):
    """Discovery connector that probes AcmeCorp's /healthz endpoint."""

    async def probe(self, provider_id: str) -> ProbeResult:
        url = f"https://{provider_id}.internal.acme.com/healthz"
        try:
            async with httpx.AsyncClient(timeout=self._config.health_timeout_seconds) as client:
                resp = await client.get(url)
                return ProbeResult(
                    provider_id=provider_id,
                    success=resp.status_code == 200,
                    latency_ms=resp.elapsed.total_seconds() * 1000,
                )
        except Exception:
            return ProbeResult(provider_id=provider_id, success=False, latency_ms=0.0)
```

### TypeScript

```typescript
import {
    BaseProvider, BaseProviderConfig,
    BaseRotationPolicy, BaseRotationPolicyConfig,
    BaseSecretStore, BaseSecretStoreConfig,
    BaseStorage, BaseStorageConfig,
    BaseObservability, BaseObservabilityConfig,
    BaseDiscovery, BaseDiscoveryConfig,
} from "@nistrapa/modelmesh-core/cdk";
import { CompletionRequest, CompletionResponse, TokenUsage } from "@nistrapa/modelmesh-core/interfaces/provider";
import { ModelSnapshot, CompletionRequest as RotationRequest } from "@nistrapa/modelmesh-core/interfaces/rotation_policy";
import { ProbeResult } from "@nistrapa/modelmesh-core/interfaces/discovery";
import fs from "node:fs";
import path from "node:path";

// ── 1. AcmeProvider ──────────────────────────────────────────────

class AcmeProvider extends BaseProvider {
    protected getCompletionEndpoint(): string {
        return `${this.config.baseUrl.replace(/\/$/, "")}/api/predict`;
    }

    protected buildRequestPayload(request: CompletionRequest): Record<string, unknown> {
        return {
            model_name: request.model,
            prompt: request.messages[request.messages.length - 1].content,
            params: { max_length: request.max_tokens ?? 1024 },
        };
    }

    protected parseResponse(data: Record<string, unknown>): CompletionResponse {
        const usage = data.usage as { in: number; out: number };
        return {
            id: data.id as string,
            model: data.model_name as string,
            choices: [{ message: { content: data.result as string } }],
            usage: { prompt_tokens: usage.in, completion_tokens: usage.out, total_tokens: usage.in + usage.out },
        };
    }
}

// ── 2. AcmeRotation ──────────────────────────────────────────────

class AcmeRotation extends BaseRotationPolicy {
    score(candidate: ModelSnapshot, request: RotationRequest): number {
        const base = super.score(candidate, request);
        return candidate.provider_id === "acme-sla" ? base + 200 : base;
    }
}

// ── 3. AcmeSecretStore ───────────────────────────────────────────

class AcmeSecretStore extends BaseSecretStore {
    protected resolve(name: string): string | null {
        const envName = `ACME_${name.toUpperCase().replace(/-/g, "_")}`;
        return process.env[envName] ?? null;
    }
}

// ── 4. AcmeStorage ───────────────────────────────────────────────

class AcmeStorage extends BaseStorage {
    private readonly root = "/var/acme/modelmesh";

    constructor(config: BaseStorageConfig) {
        super(config);
        fs.mkdirSync(this.root, { recursive: true });
    }

    async save(key: string, entry: { key: string; data: Buffer; metadata: Record<string, unknown> }): Promise<void> {
        const filePath = path.join(this.root, `${key}.json`);
        fs.mkdirSync(path.dirname(filePath), { recursive: true });
        fs.writeFileSync(filePath, JSON.stringify({ key: entry.key, data: entry.data.toString() }));
        await super.save(key, entry);
    }
}

// ── 5. AcmeObservability ─────────────────────────────────────────

/**
 * Observability connector that posts formatted lines to a webhook.
 *
 * Only `write` is overridden. All four data methods -- `emit`, `log`,
 * `flush`, and `trace` (with severity filtering via `minSeverity`) --
 * are inherited from `BaseObservability` and call `write` automatically.
 */
class AcmeObservability extends BaseObservability {
    constructor(config: BaseObservabilityConfig, private readonly webhookUrl: string) {
        super(config);
    }

    protected write(line: string): void {
        fetch(this.webhookUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: line }),
        }).catch(() => { /* best-effort logging */ });
    }
}

// ── 6. AcmeDiscovery ─────────────────────────────────────────────

class AcmeDiscovery extends BaseDiscovery {
    async probe(providerId: string): Promise<ProbeResult> {
        const url = `https://${providerId}.internal.acme.com/healthz`;
        const start = Date.now();
        try {
            const resp = await fetch(url, { signal: AbortSignal.timeout(this.config.healthTimeoutSeconds * 1000) });
            return { provider_id: providerId, success: resp.ok, latency_ms: Date.now() - start };
        } catch {
            return { provider_id: providerId, success: false, latency_ms: 0 };
        }
    }
}
```

### Wiring it all together with YAML

```yaml
# modelmesh.yaml -- AcmeCorp complete configuration
providers:
  acme-primary:
    connector: acme-provider
    config:
      base_url: "https://ml.internal.acme.com"
      auth:
        method: api_key
        api_key: "${secrets:acme-api-key}"
      models:
        - id: "acme-large"
          capabilities: ["generation.text-generation.chat-completion"]
          context_window: 32000
        - id: "acme-small"
          capabilities: ["generation.text-generation.chat-completion"]
          context_window: 8000

rotation:
  connector: acme-rotation
  config:
    retry_limit: 3
    cooldown_seconds: 120
    error_rate_threshold: 0.4

secrets:
  connector: acme-secret-store
  config:
    cache_enabled: true
    cache_ttl_ms: 600000

storage:
  connector: acme-storage
  config:
    format: json
    compression: false

observability:
  connector: acme-observability
  config:
    log_level: summary
    redact_secrets: true
    flush_interval_seconds: 30
  webhook_url: "https://logs.internal.acme.com/ingest"

discovery:
  connector: acme-discovery
  config:
    providers: ["acme-primary"]
    sync_interval_seconds: 1800
    health_interval_seconds: 30
    failure_threshold: 5
```

### Key takeaway

Six connectors, each between 5 and 20 lines of actual logic. Every connector overrides only the methods that are specific to AcmeCorp's infrastructure. The CDK base classes supply everything else: retry logic, caching, serialization, error classification, quota tracking, lock management, event filtering, and health scheduling.

### What's next

[Tutorial 7](#tutorial-7-testing-with-cdk-utilities) shows how to test these connectors using the CDK's built-in test harness and mock utilities.

---

## Tutorial 7: Testing with CDK Utilities

### What you will learn

- How to use `MockHttpClient` to test providers without making real HTTP calls
- How to use `mock_model_snapshot` and `mock_completion_request` to create test fixtures
- How to run the `ConnectorTestHarness` for automated interface compliance verification

### Background

The CDK ships three test utilities designed to work together. `MockHttpClient` replaces the real HTTP transport layer with canned responses. `mock_model_snapshot` and `mock_completion_request` create test fixtures with sensible defaults. `ConnectorTestHarness` runs standard interface compliance tests against any connector.

> **Reference:** [Helpers.md -- MockHttpClient](Helpers.html#mockhttpclient) | [Helpers.md -- MockModelSnapshot](Helpers.html#mockmodelsnapshot) | [Helpers.md -- ConnectorTestHarness](Helpers.html#connectortestharness)

### Python

```python
import asyncio
from modelmesh.cdk import BaseProvider, BaseProviderConfig
from modelmesh.cdk.helpers import (
    ConnectorTestHarness,
    MockHttpClient,
    mock_completion_request,
    mock_model_snapshot,
)
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    TokenUsage,
)


# ── The provider under test ────────────────────────────────────────
# (Re-using the AcmeProvider from Tutorial 6, simplified for testing)

class AcmeProvider(BaseProvider):
    """Simplified Acme provider for testing."""

    def _get_completion_endpoint(self) -> str:
        return f"{self._config.base_url.rstrip('/')}/api/predict"

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        return {
            "model_name": request.model,
            "prompt": request.messages[-1]["content"],
            "params": {"max_length": request.max_tokens or 1024},
        }

    def _parse_response(self, data: dict) -> CompletionResponse:
        return CompletionResponse(
            id=data["id"],
            model=data["model_name"],
            choices=[{"message": {"content": data["result"]}}],
            usage=TokenUsage(
                prompt_tokens=data["usage"]["in"],
                completion_tokens=data["usage"]["out"],
                total_tokens=data["usage"]["in"] + data["usage"]["out"],
            ),
        )


# ── Test 1: Verify completion returns expected response ────────────

async def test_acme_complete() -> None:
    """Test that AcmeProvider.complete() correctly translates request and response."""

    # Set up mock HTTP client with a canned response
    mock_http = MockHttpClient()
    mock_http.add_response("/api/predict", {
        "id": "req-001",
        "model_name": "acme-large",
        "result": "Hello from AcmeCorp!",
        "usage": {"in": 10, "out": 20},
    })

    # Create provider and inject mock client
    config = BaseProviderConfig(
        base_url="https://ml.internal.acme.com",
        api_key="test-key",
        models=[ModelInfo(id="acme-large", name="Acme Large", capabilities=["generation.text-generation.chat-completion"])],
    )
    provider = AcmeProvider(config)
    provider._client = mock_http  # Inject mock

    # Execute
    request = mock_completion_request(model="acme-large")
    response = await provider.complete(request)

    # Verify response translation
    assert response.id == "req-001"
    assert response.choices[0]["message"]["content"] == "Hello from AcmeCorp!"
    assert response.usage.total_tokens == 30

    # Verify request translation
    recorded = mock_http.requests[0]
    assert recorded.json["model_name"] == "acme-large"
    assert "prompt" in recorded.json

    print("test_acme_complete: PASSED")


# ── Test 2: Verify error classification ────────────────────────────

async def test_acme_error_handling() -> None:
    """Test that errors from the Acme API are classified correctly."""

    config = BaseProviderConfig(
        base_url="https://ml.internal.acme.com",
        api_key="test-key",
    )
    provider = AcmeProvider(config)

    # Simulate a 429 rate-limit error
    import httpx
    mock_response = httpx.Response(
        status_code=429,
        headers={"Retry-After": "15"},
        request=httpx.Request("POST", "https://example.com"),
    )
    error = httpx.HTTPStatusError(
        "rate limited", request=mock_response.request, response=mock_response
    )

    result = provider.classify_error(error)
    assert result.retryable is True
    assert result.category == "rate_limit"
    assert result.retry_after == 15.0

    # Simulate a 400 bad request error
    mock_400 = httpx.Response(
        status_code=400,
        request=httpx.Request("POST", "https://example.com"),
    )
    error_400 = httpx.HTTPStatusError(
        "bad request", request=mock_400.request, response=mock_400
    )

    result_400 = provider.classify_error(error_400)
    assert result_400.retryable is False
    assert result_400.category == "client_error"

    print("test_acme_error_handling: PASSED")


# ── Test 3: Run the full test harness ──────────────────────────────

async def test_acme_harness() -> None:
    """Run the ConnectorTestHarness against the AcmeProvider."""

    # Set up mock HTTP client with responses for all harness tests
    mock_http = MockHttpClient()

    # Response for test_provider_complete
    mock_http.add_response("/api/predict", {
        "id": "harness-001",
        "model_name": "gpt-4",
        "result": "Test response",
        "usage": {"in": 5, "out": 10},
    })

    # Stream response for test_provider_stream (SSE chunks)
    mock_http.add_stream_response("/api/predict", [
        '{"id":"s-001","model":"gpt-4","choices":[{"delta":{"content":"Hi"}}]}',
        '{"id":"s-001","model":"gpt-4","choices":[{"delta":{"content":"!"}}]}',
    ])

    config = BaseProviderConfig(
        base_url="https://ml.internal.acme.com",
        api_key="test-key",
        models=[ModelInfo(id="gpt-4", name="GPT-4", capabilities=["generation.text-generation.chat-completion"])],
    )
    provider = AcmeProvider(config)
    provider._client = mock_http

    # Run all provider tests
    harness = ConnectorTestHarness()
    results = await harness.run_all(provider, "provider")

    # Print results
    for test_name, (passed, message) in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {test_name}: {status} -- {message}")

    # Assert all passed
    assert all(passed for passed, _ in results.values()), (
        "Not all harness tests passed"
    )

    print("test_acme_harness: PASSED (all harness tests)")


# ── Run all tests ──────────────────────────────────────────────────

async def main() -> None:
    await test_acme_complete()
    await test_acme_error_handling()
    await test_acme_harness()
    print("\nAll tests passed.")

asyncio.run(main())
```

### TypeScript

```typescript
import {
    BaseProvider,
    BaseProviderConfig,
} from "@nistrapa/modelmesh-core/cdk";
import {
    ConnectorTestHarness,
    MockHttpClient,
    mockCompletionRequest,
    mockModelSnapshot,
} from "@nistrapa/modelmesh-core/cdk/helpers";
import {
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    TokenUsage,
} from "@nistrapa/modelmesh-core/interfaces/provider";

// ── The provider under test ──────────────────────────────────────

class AcmeProvider extends BaseProvider {
    protected getCompletionEndpoint(): string {
        return `${this.config.baseUrl.replace(/\/$/, "")}/api/predict`;
    }

    protected buildRequestPayload(request: CompletionRequest): Record<string, unknown> {
        return {
            model_name: request.model,
            prompt: request.messages[request.messages.length - 1].content,
            params: { max_length: request.max_tokens ?? 1024 },
        };
    }

    protected parseResponse(data: Record<string, unknown>): CompletionResponse {
        const usage = data.usage as { in: number; out: number };
        return {
            id: data.id as string,
            model: data.model_name as string,
            choices: [{ message: { content: data.result as string } }],
            usage: { prompt_tokens: usage.in, completion_tokens: usage.out, total_tokens: usage.in + usage.out },
        };
    }
}

// ── Test 1: Verify completion returns expected response ──────────

async function testAcmeComplete(): Promise<void> {
    const mockHttp = new MockHttpClient();
    mockHttp.addResponse("/api/predict", {
        id: "req-001",
        model_name: "acme-large",
        result: "Hello from AcmeCorp!",
        usage: { in: 10, out: 20 },
    });

    const config: BaseProviderConfig = {
        baseUrl: "https://ml.internal.acme.com",
        apiKey: "test-key",
        models: [{ id: "acme-large", name: "Acme Large", capabilities: ["generation.text-generation.chat-completion"] } as ModelInfo],
    };
    const provider = new AcmeProvider(config);
    (provider as any).client = mockHttp; // Inject mock

    const request = mockCompletionRequest({ model: "acme-large" });
    const response = await provider.complete(request);

    console.assert(response.id === "req-001", "Response ID mismatch");
    console.assert(response.choices[0].message.content === "Hello from AcmeCorp!", "Content mismatch");
    console.assert(response.usage.total_tokens === 30, "Token count mismatch");

    const recorded = mockHttp.requests[0];
    console.assert(recorded.body?.model_name === "acme-large", "Request model mismatch");

    console.log("testAcmeComplete: PASSED");
}

// ── Test 2: Verify error classification ──────────────────────────

async function testAcmeErrorHandling(): Promise<void> {
    const config: BaseProviderConfig = {
        baseUrl: "https://ml.internal.acme.com",
        apiKey: "test-key",
    };
    const provider = new AcmeProvider(config);

    // Simulate a 429 error
    const error429 = new Error("rate limited") as any;
    error429.response = { status_code: 429, headers: { get: (h: string) => h === "Retry-After" ? "15" : null } };

    const result = provider.classifyError(error429);
    console.assert(result.retryable === true, "429 should be retryable");
    console.assert(result.category === "rate_limit", "429 should be rate_limit");

    // Simulate a 400 error
    const error400 = new Error("bad request") as any;
    error400.response = { status_code: 400, headers: { get: () => null } };

    const result400 = provider.classifyError(error400);
    console.assert(result400.retryable === false, "400 should not be retryable");
    console.assert(result400.category === "client_error", "400 should be client_error");

    console.log("testAcmeErrorHandling: PASSED");
}

// ── Test 3: Run the full test harness ────────────────────────────

async function testAcmeHarness(): Promise<void> {
    const mockHttp = new MockHttpClient();

    mockHttp.addResponse("/api/predict", {
        id: "harness-001",
        model_name: "gpt-4",
        result: "Test response",
        usage: { in: 5, out: 10 },
    });

    mockHttp.addStreamResponse("/api/predict", [
        '{"id":"s-001","model":"gpt-4","choices":[{"delta":{"content":"Hi"}}]}',
        '{"id":"s-001","model":"gpt-4","choices":[{"delta":{"content":"!"}}]}',
    ]);

    const config: BaseProviderConfig = {
        baseUrl: "https://ml.internal.acme.com",
        apiKey: "test-key",
        models: [{ id: "gpt-4", name: "GPT-4", capabilities: ["generation.text-generation.chat-completion"] } as ModelInfo],
    };
    const provider = new AcmeProvider(config);
    (provider as any).client = mockHttp;

    const harness = new ConnectorTestHarness();
    const results = await harness.runAll(provider, "provider");

    for (const [testName, [passed, message]] of results) {
        console.log(`  ${testName}: ${passed ? "PASSED" : "FAILED"} -- ${message}`);
    }

    const allPassed = [...results.values()].every(([passed]) => passed);
    console.assert(allPassed, "Not all harness tests passed");

    console.log("testAcmeHarness: PASSED (all harness tests)");
}

// ── Run all tests ────────────────────────────────────────────────

async function main(): Promise<void> {
    await testAcmeComplete();
    await testAcmeErrorHandling();
    await testAcmeHarness();
    console.log("\nAll tests passed.");
}

main();
```

### Key takeaway

Three test patterns were demonstrated:

1. **Unit test with mock HTTP** -- Inject `MockHttpClient`, configure canned responses, verify both request translation (what was sent) and response translation (what was returned).
2. **Error classification test** -- Construct synthetic error objects and verify the provider's `classify_error()` returns the correct retryable/non-retryable classification.
3. **Interface compliance harness** -- Run `ConnectorTestHarness.run_all()` to verify the connector satisfies the full `ProviderConnector` contract.

These same patterns apply to all six connector types. The test harness includes dedicated test methods for rotation policies (`test_rotation_deactivation`, `test_rotation_recovery`, `test_rotation_selection`), secret stores (`test_secret_store_get`), storage (`test_storage_crud`), observability (`test_observability_emit_log_flush_trace`), and discovery (`test_discovery_probe`).

### What's next

[Tutorial 8](#tutorial-8-teen-programmer-guide----build-your-first-ai-app) is a self-contained beginner guide for new programmers building their first AI app with ModelMesh.

---

## Tutorial 8: Teen Programmer Guide -- Build Your First AI App

This tutorial is written for beginners (ages 14+) with basic Python knowledge (variables, functions, `print`, `for` loops). No prior experience with APIs, async programming, YAML, or environment variables is required.

### What are we building?

A chatbot that answers questions about anything. You type a question, the chatbot responds. By the end of this tutorial you will have a fully interactive AI chatbot running in your terminal with streaming responses, a custom personality, and conversation memory.

### What you need

- **Python 3.11 or later** -- check by running `python --version` in your terminal
- **A free API key** from one of these providers:
  - [OpenAI](https://platform.openai.com/api-keys) -- sign up and create a key starting with `sk-`
  - [Groq](https://console.groq.com/keys) -- sign up for free and create a key starting with `gsk_`

### Step 1: Install ModelMesh

Open your terminal (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
pip install modelmesh-lite
```

If that does not work, try `pip3 install modelmesh-lite` or `python -m pip install modelmesh-lite`.

### Step 2: Set your API key

An **environment variable** is a value stored in your computer's settings that programs can read. Think of it like a sticky note your computer keeps in its pocket -- programs can check the note without you having to type the value every time.

You need to set one environment variable so ModelMesh knows which AI service to use.

**Windows (Command Prompt):**

```cmd
set OPENAI_API_KEY=sk-your-key-here
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "sk-your-key-here"
```

**Mac / Linux:**

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

If you are using Groq instead, replace `OPENAI_API_KEY` with `GROQ_API_KEY` and use your Groq key.

> **Note:** This sets the key only for your current terminal session. When you close the terminal, you will need to set it again. That is fine for learning.

### Step 3: Your first chat (4 lines of real code)

Create a file called `chatbot.py` and paste this:

#### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "What is the tallest mountain?"}],
)
print(response.choices[0].message.content)
```

#### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";

const client = create("chat-completion");
const response = await client.chat.completions.create({
    model: "chat-completion",
    messages: [{ role: "user", content: "What is the tallest mountain?" }],
});
console.log(response.choices[0].message.content);
```

Run it:

```bash
python chatbot.py
```

You should see something like: "Mount Everest is the tallest mountain on Earth, standing at 8,849 meters (29,032 feet) above sea level."

**What each line does:**

1. `import modelmesh` -- loads the ModelMesh library
2. `client = modelmesh.create("chat-completion")` -- creates a client that can talk to AI models. The `"chat-completion"` part tells ModelMesh you want a model that can have conversations. ModelMesh automatically finds your API key and connects to the right service.
3. `client.chat.completions.create(...)` -- sends your question to the AI model. The `messages` list contains the conversation so far (just your one question for now).
4. `print(response.choices[0].message.content)` -- prints the AI's response text.

### Step 4: Make it interactive

Let's make the chatbot keep asking for questions instead of stopping after one. Replace the contents of `chatbot.py` with:

#### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

while True:
    user_input = input("You: ")
    if user_input.lower() in ("quit", "exit", "bye"):
        print("Chatbot: Goodbye!")
        break

    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": user_input}],
    )
    print(f"Chatbot: {response.choices[0].message.content}")
    print()
```

#### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";
import * as readline from "readline";

const client = create("chat-completion");

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (prompt: string) => new Promise<string>((resolve) => rl.question(prompt, resolve));

while (true) {
    const userInput = await ask("You: ");
    if (["quit", "exit", "bye"].includes(userInput.toLowerCase())) {
        console.log("Chatbot: Goodbye!");
        rl.close();
        break;
    }

    const response = await client.chat.completions.create({
        model: "chat-completion",
        messages: [{ role: "user", content: userInput }],
    });
    console.log(`Chatbot: ${response.choices[0].message.content}\n`);
}
```

Now you can have a back-and-forth conversation. Type "quit" to stop.

### Step 5: Add streaming

Right now, the chatbot waits until the entire answer is ready before showing it. **Streaming** means the answer appears word-by-word as it is generated, like watching someone type in real time.

#### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

while True:
    user_input = input("You: ")
    if user_input.lower() in ("quit", "exit", "bye"):
        print("Chatbot: Goodbye!")
        break

    print("Chatbot: ", end="")
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": user_input}],
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")
```

#### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";
import * as readline from "readline";

const client = create("chat-completion");

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (prompt: string) => new Promise<string>((resolve) => rl.question(prompt, resolve));

while (true) {
    const userInput = await ask("You: ");
    if (["quit", "exit", "bye"].includes(userInput.toLowerCase())) {
        console.log("Chatbot: Goodbye!");
        rl.close();
        break;
    }

    process.stdout.write("Chatbot: ");
    const stream = await client.chat.completions.create({
        model: "chat-completion",
        messages: [{ role: "user", content: userInput }],
        stream: true,
    });
    for await (const chunk of stream) {
        const content = chunk.choices[0]?.delta?.content;
        if (content) {
            process.stdout.write(content);
        }
    }
    console.log("\n");
}
```

The key change is `stream=True`. Instead of getting one big response, you get a stream of small chunks. Each chunk contains a piece of the answer, and you print it immediately.

### Step 6: Add a system prompt (give it a personality)

A **system prompt** is a special instruction that tells the AI how to behave. It goes at the beginning of the messages list with `"role": "system"`.

#### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

system_prompt = (
    "You are a friendly science tutor for teenagers. "
    "Explain things using simple language and fun examples. "
    "Keep answers under 3 sentences unless asked for more detail."
)

while True:
    user_input = input("You: ")
    if user_input.lower() in ("quit", "exit", "bye"):
        print("Tutor: Goodbye! Keep being curious!")
        break

    print("Tutor: ", end="")
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")
```

#### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";
import * as readline from "readline";

const client = create("chat-completion");

const systemPrompt =
    "You are a friendly science tutor for teenagers. " +
    "Explain things using simple language and fun examples. " +
    "Keep answers under 3 sentences unless asked for more detail.";

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (prompt: string) => new Promise<string>((resolve) => rl.question(prompt, resolve));

while (true) {
    const userInput = await ask("You: ");
    if (["quit", "exit", "bye"].includes(userInput.toLowerCase())) {
        console.log("Tutor: Goodbye! Keep being curious!");
        rl.close();
        break;
    }

    process.stdout.write("Tutor: ");
    const stream = await client.chat.completions.create({
        model: "chat-completion",
        messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: userInput },
        ],
        stream: true,
    });
    for await (const chunk of stream) {
        const content = chunk.choices[0]?.delta?.content;
        if (content) {
            process.stdout.write(content);
        }
    }
    console.log("\n");
}
```

Try changing the system prompt to make the chatbot talk like a pirate, a detective, or your favorite character.

### Step 7: Keep conversation history (memory)

Right now, the chatbot forgets everything after each question. To give it **memory**, you keep a list of all messages and add to it each turn.

#### Python

```python
import modelmesh

client = modelmesh.create("chat-completion")

system_prompt = (
    "You are a friendly science tutor for teenagers. "
    "Explain things using simple language and fun examples. "
    "Keep answers under 3 sentences unless asked for more detail."
)

# Start with just the system prompt
messages = [{"role": "system", "content": system_prompt}]

while True:
    user_input = input("You: ")
    if user_input.lower() in ("quit", "exit", "bye"):
        print("Tutor: Goodbye! Keep being curious!")
        break

    # Add the user's message to the conversation history
    messages.append({"role": "user", "content": user_input})

    print("Tutor: ", end="")
    assistant_response = ""
    stream = client.chat.completions.create(
        model="chat-completion",
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            piece = chunk.choices[0].delta.content
            print(piece, end="", flush=True)
            assistant_response += piece
    print("\n")

    # Add the assistant's response to the conversation history
    messages.append({"role": "assistant", "content": assistant_response})
```

#### TypeScript

```typescript
import { create } from "@nistrapa/modelmesh-core";
import * as readline from "readline";

const client = create("chat-completion");

const systemPrompt =
    "You are a friendly science tutor for teenagers. " +
    "Explain things using simple language and fun examples. " +
    "Keep answers under 3 sentences unless asked for more detail.";

// Start with just the system prompt
const messages: Array<{ role: string; content: string }> = [
    { role: "system", content: systemPrompt },
];

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (prompt: string) => new Promise<string>((resolve) => rl.question(prompt, resolve));

while (true) {
    const userInput = await ask("You: ");
    if (["quit", "exit", "bye"].includes(userInput.toLowerCase())) {
        console.log("Tutor: Goodbye! Keep being curious!");
        rl.close();
        break;
    }

    // Add the user's message to the conversation history
    messages.push({ role: "user", content: userInput });

    process.stdout.write("Tutor: ");
    let assistantResponse = "";
    const stream = await client.chat.completions.create({
        model: "chat-completion",
        messages: messages,
        stream: true,
    });
    for await (const chunk of stream) {
        const content = chunk.choices[0]?.delta?.content;
        if (content) {
            process.stdout.write(content);
            assistantResponse += content;
        }
    }
    console.log("\n");

    // Add the assistant's response to the conversation history
    messages.push({ role: "assistant", content: assistantResponse });
}
```

Now the chatbot remembers what you talked about. Try asking "What is the Sun made of?" and then "How hot is it?" -- the chatbot will know "it" means the Sun.

**How it works:** Every time you send a message, you send the entire conversation so far. The AI reads through all previous messages to understand the context. The `messages` list grows with each exchange: system prompt, then alternating user/assistant messages.

### What's next

You have built a fully interactive AI chatbot with streaming, a custom personality, and conversation memory. Here are some ideas for what to explore next:

- [Tutorial 0](#tutorial-0-chat-completion-in-4-lines----openai-compatible) -- understand what happens under the hood when you call `modelmesh.create()`
- [Tutorial 1](#tutorial-1-multi-provider-rotation-with-capabilities) -- learn how to use multiple AI providers and choose between them
- [Tutorial 2](#tutorial-2-your-first-provider-in-10-lines) -- if you want to build your own connector for a custom AI service

---

## Tutorial 9: Building a Browser-Compatible Provider

### What you will learn

- How to use `BrowserBaseProvider` to build a provider that runs in web browsers
- How to configure CORS proxy support via `proxyUrl`
- How to use `createBrowser()` as a browser-optimized alternative to `modelmesh.create()`

### Background

`BrowserBaseProvider` is the browser equivalent of `BaseProvider`. It uses `fetch()` instead of Node.js HTTP modules and `ReadableStream` instead of Node streams. The same protected hooks are available for subclassing. Use it when your provider will run in a browser, Deno, Bun, or Cloudflare Workers.

### TypeScript

**Step 1: Create a custom browser provider**

```typescript
import { BrowserBaseProvider, createBrowserProviderConfig } from '@nistrapa/modelmesh-core/browser';

class MyBrowserProvider extends BrowserBaseProvider {
    _buildHeaders() {
        return {
            ...super._buildHeaders(),
            'X-Custom-Header': 'my-value',
        };
    }

    _getCompletionEndpoint() {
        return `${this.config.baseUrl}/api/generate`;
    }
}

const provider = new MyBrowserProvider(createBrowserProviderConfig({
    baseUrl: 'https://my-api.example.com',
    apiKey: 'user-provided-key',
    proxyUrl: 'http://localhost:9090',
}));
```

**Step 2: Use with createBrowser()**

```typescript
import { createBrowser } from '@nistrapa/modelmesh-core/browser';

const client = createBrowser({
    providers: {
        'my-provider': {
            connector: 'browser-base',
            config: {
                baseUrl: 'https://api.openai.com',
                apiKey: userApiKey,
                proxyUrl: 'http://localhost:9090',
            },
        },
    },
    models: {
        'openai.gpt-4o': {
            provider: 'my-provider',
            capabilities: ['generation.text-generation.chat-completion'],
        },
    },
});

const response = await client.chat.completions.create({
    model: 'chat-completion',
    messages: [{ role: 'user', content: 'Hello!' }],
});
```

### CORS Proxy Configuration

The library ships a minimal CORS proxy in `tools/cors-proxy/`:

```bash
# Node.js (zero dependencies)
node tools/cors-proxy/cors-proxy.js

# Docker
cd tools/cors-proxy && docker compose up

# Third-party alternative
npx local-cors-proxy --proxyUrl https://api.openai.com --port 9090
```

When `proxyUrl` is set, all API requests route through `{proxyUrl}/{baseUrl}/path`. Omit `proxyUrl` for browser extensions with `host_permissions` or providers that send CORS headers natively.

> **See also:** [Browser Usage Guide](../guides/BrowserUsage.html) for security considerations, provider-specific notes, and full architecture details.

---

## Tutorial 10: Audio Provider Development

### What you will learn

- How audio requests bridge into the `CompletionRequest`/`CompletionResponse` pipeline
- How to build a TTS or STT provider using the CDK
- How audio pools and routing work

### Background

Audio capabilities (TTS, STT) use the same provider interface as text generation. The `AudioRequest` and `AudioResponse` types carry audio-specific parameters through the `extra` field of `CompletionRequest`/`CompletionResponse`. Audio providers register capabilities at `generation.audio.text-to-speech` or `understanding.audio.speech-to-text` and participate in the standard pool routing.

### Python -- TTS Provider

```python
from modelmesh.cdk import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse

class MyTTSProvider(BaseProvider):
    """Custom TTS provider using the standard provider interface."""

    def __init__(self, config):
        super().__init__(BaseProviderConfig(
            base_url=config["base_url"],
            api_key=config["api_key"],
            capabilities=["generation.audio.text-to-speech"],
        ))

    def _get_completion_endpoint(self):
        return f"{self._config.base_url}/v1/audio/speech"

    def _build_request_payload(self, request):
        extra = request.extra or {}
        return {
            "input": extra.get("input", ""),
            "voice": extra.get("voice", "default"),
            "model": request.model,
            "response_format": extra.get("format", "mp3"),
        }

    def _parse_response(self, data):
        return CompletionResponse(
            id="audio-" + str(id(data)),
            model=self._config.models[0].id if self._config.models else "tts",
            choices=[],
            extra={"audio": data, "format": "mp3"},
        )
```

### Routing Audio Requests

Audio requests route through capability pools like any other request. Configure a pool targeting `generation.audio` to collect all TTS providers, or target the specific leaf `generation.audio.text-to-speech`:

```yaml
pools:
  tts:
    capability: generation.audio.text-to-speech
    strategy: modelmesh.stick-until-failure.v1

  stt:
    capability: understanding.audio.speech-to-text
    strategy: modelmesh.priority-selection.v1
```

The `client.audio.speech.create()` and `client.audio.transcriptions.create()` methods on `MeshClient` route through these pools automatically.

---

## Cross-References

| Document | Description |
| --- | --- |
| [Overview.md](Overview.html) | CDK philosophy, class hierarchy, and decision trees for choosing a starting point |
| [BaseClasses.md](BaseClasses.html) | Full API reference for all 6 base classes and 7 specialized classes |
| [Mixins.md](Mixins.html) | Cross-cutting mixins: RetryMixin, CacheMixin, RateLimiterMixin, MetricsMixin, SerializationMixin |
| [Helpers.md](Helpers.html) | Utility functions (parse_duration, format_duration) and test utilities (MockHttpClient, ConnectorTestHarness) |
| [Enums.md](Enums.html) | Consolidated enum reference for all CDK and interface enums |
| [interfaces/](../interfaces/) | Authoritative interface definitions for all six connector types |
| [ConnectorCatalogue.md](../ConnectorCatalogue.html) | Registry of all pre-shipped connector implementations |
| [SystemConcept.md](../SystemConcept.html) | System architecture and connector extensibility model |
