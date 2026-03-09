"""
Custom Provider Connector -- Self-Hosted vLLM Instance

Demonstrates how to implement a custom provider connector for ModelMesh Lite
that wraps a self-hosted vLLM inference server exposed via a REST API.

This connector translates ModelMesh Lite's normalized request/response format
into vLLM's native API format, implements streaming via async generators, and
classifies errors from a non-standard API surface.

See: docs/interfaces/Provider.md

Requirements:
    pip install httpx
"""
# For a simpler CDK-based approach, see samples/cdk/python/

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator, Optional

import httpx


# ---------------------------------------------------------------------------
# Supporting types (from Provider interface)
# ---------------------------------------------------------------------------

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
    """Per-unit pricing for a model."""
    input_per_token: float
    output_per_token: float
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


# ---------------------------------------------------------------------------
# Interface ABCs (from Provider interface)
# ---------------------------------------------------------------------------

class ModelExecution(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionResponse]: ...


class Capabilities(ABC):
    @abstractmethod
    def get_capabilities(self) -> list[str]: ...

    @abstractmethod
    def supports(self, capability: str) -> bool: ...


class ModelCatalogue(ABC):
    @abstractmethod
    async def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def get_model_info(self, model_id: str) -> ModelInfo: ...


class QuotaRateLimits(ABC):
    @abstractmethod
    async def check_quota(self) -> QuotaStatus: ...

    @abstractmethod
    async def get_rate_limits(self) -> RateLimitStatus: ...


class CostPricing(ABC):
    @abstractmethod
    async def get_pricing(self, model_id: str) -> ModelPricing: ...

    @abstractmethod
    def report_usage(self, model_id: str, usage: TokenUsage) -> None: ...


class ErrorClassification(ABC):
    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorClassificationResult: ...

    @abstractmethod
    def is_retryable(self, error: Exception) -> bool: ...


class ProviderConnector(
    ModelExecution,
    Capabilities,
    ModelCatalogue,
    QuotaRateLimits,
    CostPricing,
    ErrorClassification,
):
    """Full provider connector combining all required interfaces."""
    pass


# ---------------------------------------------------------------------------
# Custom error type for vLLM-specific errors
# ---------------------------------------------------------------------------

class VllmHttpError(Exception):
    """Error returned by the vLLM REST API."""

    def __init__(self, status_code: int, message: str, detail: Optional[str] = None):
        self.status_code = status_code
        self.message = message
        self.detail = detail
        super().__init__(f"vLLM API error {status_code}: {message}")


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

class VllmProviderConnector(ProviderConnector):
    """Provider connector for a self-hosted vLLM inference server.

    vLLM exposes an OpenAI-compatible API, but this connector demonstrates how
    to handle differences such as custom health endpoints, non-standard error
    payloads, and internal pricing models for chargeback tracking.

    Configuration example (YAML):

        providers:
          my-vllm:
            connector: custom
            connector_class: VllmProviderConnector
            execution:
              base_url: "http://gpu-cluster.internal:8000"
              timeout: 60s
              max_retries: 2
            auth:
              method: api_key
              api_key: "${secrets:vllm-api-key}"
            models:
              - id: "meta-llama/Llama-3.1-70B-Instruct"
                name: "Llama 3.1 70B (self-hosted)"
                context_window: 131072
                max_output_tokens: 4096
                capabilities: ["generation.text-generation.chat-completion"]
                features:
                  streaming: true
              - id: "mistralai/Mistral-7B-Instruct-v0.3"
                name: "Mistral 7B (self-hosted)"
                context_window: 32768
                max_output_tokens: 4096
                capabilities: ["generation.text-generation.chat-completion"]
                features:
                  streaming: true
            budget:
              gpu_hour_cost: 2.50
              daily_request_limit: 50000
              daily_token_limit: 100000000
    """

    # Internal chargeback pricing per token (not real provider pricing, but
    # used by the organization to track GPU cost allocation across teams).
    _DEFAULT_PRICING: dict[str, ModelPricing] = {
        "meta-llama/Llama-3.1-70B-Instruct": ModelPricing(
            input_per_token=0.00002,
            output_per_token=0.00004,
            per_request=0.001,
        ),
        "mistralai/Mistral-7B-Instruct-v0.3": ModelPricing(
            input_per_token=0.000005,
            output_per_token=0.00001,
            per_request=0.0005,
        ),
    }

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 60.0,
        max_retries: int = 2,
        models: Optional[list[dict]] = None,
        gpu_hour_cost: float = 2.50,
        daily_request_limit: Optional[int] = None,
        daily_token_limit: Optional[int] = None,
    ) -> None:
        """Initialize the vLLM provider connector.

        Args:
            base_url: Root URL of the vLLM server (e.g., "http://gpu-cluster:8000").
            api_key: Optional bearer token for authentication.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum retries at the connector level (default: 2).
            models: Static list of model definitions. Each dict must contain
                     'id', 'name', 'context_window', 'max_output_tokens', and
                     optionally 'capabilities'.
            gpu_hour_cost: Self-hosted cost estimate per GPU-hour in USD (default: 2.50).
            daily_request_limit: Daily request budget (optional; unlimited if omitted).
            daily_token_limit: Daily token budget (optional; unlimited if omitted).
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._gpu_hour_cost = gpu_hour_cost
        self._daily_request_limit = daily_request_limit
        self._daily_token_limit = daily_token_limit

        # Build the model catalogue from the static configuration.
        self._models: dict[str, ModelInfo] = {}
        for m in (models or []):
            model_id = m["id"]
            self._models[model_id] = ModelInfo(
                id=model_id,
                name=m.get("name", model_id),
                capabilities=m.get("capabilities", ["generation.text-generation.chat-completion"]),
                context_window=m.get("context_window", 4096),
                max_output_tokens=m.get("max_output_tokens", 2048),
                pricing=self._DEFAULT_PRICING.get(model_id),
            )

        # Accumulate usage for cost tracking and quota reporting.
        self._usage_accumulator: dict[str, TokenUsage] = {}
        self._request_count: int = 0
        self._tokens_in: int = 0
        self._tokens_out: int = 0

        # Shared HTTP client -- reused across requests for connection pooling.
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(self._timeout),
        )

    # ------------------------------------------------------------------
    # ModelExecution
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a chat completion request to vLLM and return the result.

        Translates the normalized CompletionRequest into vLLM's
        /v1/chat/completions payload and maps the response back.
        """
        payload = self._build_payload(request, stream=False)

        try:
            response = await self._client.post("/v1/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise VllmHttpError(408, "Request timed out", str(exc)) from exc
        except httpx.ConnectError as exc:
            raise VllmHttpError(503, "Connection refused", str(exc)) from exc

        if response.status_code != 200:
            self._raise_api_error(response)

        data = response.json()
        usage = TokenUsage(
            prompt_tokens=data["usage"]["prompt_tokens"],
            completion_tokens=data["usage"]["completion_tokens"],
            total_tokens=data["usage"]["total_tokens"],
        )

        # Track usage for cost reporting.
        self.report_usage(request.model, usage)
        self._request_count += 1

        return CompletionResponse(
            id=data.get("id", f"vllm-{uuid.uuid4().hex[:12]}"),
            model=data.get("model", request.model),
            choices=data.get("choices", []),
            usage=usage,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionResponse]:
        """Stream chat completion chunks from vLLM.

        Uses server-sent events (SSE) via vLLM's streaming API.
        Yields partial CompletionResponse objects as each chunk arrives.
        """
        payload = self._build_payload(request, stream=True)

        accumulated_prompt = 0
        accumulated_completion = 0

        try:
            async with self._client.stream(
                "POST", "/v1/chat/completions", json=payload
            ) as response:
                if response.status_code != 200:
                    # Read the full body to get the error detail.
                    await response.aread()
                    self._raise_api_error(response)

                async for line in response.aiter_lines():
                    # SSE format: each event line starts with "data: ".
                    if not line.startswith("data: "):
                        continue

                    data_str = line[len("data: "):]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # Extract partial usage if vLLM reports it per chunk.
                    chunk_usage = chunk.get("usage")
                    if chunk_usage:
                        accumulated_prompt = chunk_usage.get(
                            "prompt_tokens", accumulated_prompt
                        )
                        accumulated_completion = chunk_usage.get(
                            "completion_tokens", accumulated_completion
                        )

                    yield CompletionResponse(
                        id=chunk.get("id", f"vllm-{uuid.uuid4().hex[:12]}"),
                        model=chunk.get("model", request.model),
                        choices=chunk.get("choices", []),
                        usage=TokenUsage(
                            prompt_tokens=accumulated_prompt,
                            completion_tokens=accumulated_completion,
                            total_tokens=accumulated_prompt + accumulated_completion,
                        ),
                    )

        except httpx.TimeoutException as exc:
            raise VllmHttpError(408, "Stream timed out", str(exc)) from exc
        except httpx.ConnectError as exc:
            raise VllmHttpError(503, "Connection refused during stream", str(exc)) from exc

        # Report final usage after stream completes.
        final_usage = TokenUsage(
            prompt_tokens=accumulated_prompt,
            completion_tokens=accumulated_completion,
            total_tokens=accumulated_prompt + accumulated_completion,
        )
        self.report_usage(request.model, final_usage)
        self._request_count += 1

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def get_capabilities(self) -> list[str]:
        """vLLM supports chat completions and text completions."""
        return ["generation.text-generation.chat-completion"]

    def supports(self, capability: str) -> bool:
        """Check whether a specific capability is supported."""
        return capability in self.get_capabilities()

    # ------------------------------------------------------------------
    # ModelCatalogue
    # ------------------------------------------------------------------

    async def list_models(self) -> list[ModelInfo]:
        """Return all models from the static configuration."""
        return list(self._models.values())

    async def get_model_info(self, model_id: str) -> ModelInfo:
        """Return information for a specific model.

        Raises:
            KeyError: If the model ID is not in the catalogue.
        """
        if model_id not in self._models:
            raise KeyError(f"Model '{model_id}' not found in vLLM catalogue")
        return self._models[model_id]

    # ------------------------------------------------------------------
    # QuotaRateLimits
    # ------------------------------------------------------------------

    async def check_quota(self) -> QuotaStatus:
        """Return quota consumption based on accumulated request count.

        vLLM itself does not enforce quotas, but the organization may impose
        a daily request cap for chargeback purposes.
        """
        limit = self._daily_request_limit
        return QuotaStatus(
            used=self._request_count,
            remaining=max(0, limit - self._request_count) if limit is not None else None,
            limit=limit,
            resets_at=None,  # Managed externally by a scheduler.
        )

    async def get_rate_limits(self) -> RateLimitStatus:
        """Return rate-limit headroom.

        vLLM does not enforce rate limits natively, but we can derive token
        headroom from the configured daily token budget.
        """
        total_tokens = self._tokens_in + self._tokens_out
        tokens_remaining = (
            max(0, self._daily_token_limit - total_tokens)
            if self._daily_token_limit is not None
            else None
        )
        requests_remaining = (
            max(0, self._daily_request_limit - self._request_count)
            if self._daily_request_limit is not None
            else None
        )

        return RateLimitStatus(
            requests_remaining=requests_remaining,
            tokens_remaining=tokens_remaining,
            reset_seconds=None,
        )

    # ------------------------------------------------------------------
    # CostPricing
    # ------------------------------------------------------------------

    async def get_pricing(self, model_id: str) -> ModelPricing:
        """Return pricing for a model.

        For self-hosted vLLM, we estimate cost based on GPU-hour cost divided
        by throughput. These are rough estimates; adjust gpu_hour_cost in config.
        """
        # Rough estimate: GPU-hour cost spread across tokens.
        # Assumes ~2000 tokens/second throughput on a modern GPU.
        tokens_per_second = 2000
        cost_per_token = self._gpu_hour_cost / (tokens_per_second * 3600)

        return ModelPricing(
            input_per_token=cost_per_token,
            output_per_token=cost_per_token * 1.5,  # output is ~1.5x more expensive
            per_request=0,  # no per-request overhead for self-hosted
        )

    def report_usage(self, model_id: str, usage: TokenUsage) -> None:
        """Accumulate token usage for cost tracking.

        Accumulates into the daily usage counters that drive quota checks
        and cost reporting.
        """
        self._tokens_in += usage.prompt_tokens
        self._tokens_out += usage.completion_tokens

        if model_id not in self._usage_accumulator:
            self._usage_accumulator[model_id] = TokenUsage(
                prompt_tokens=0, completion_tokens=0, total_tokens=0
            )

        acc = self._usage_accumulator[model_id]
        acc.prompt_tokens += usage.prompt_tokens
        acc.completion_tokens += usage.completion_tokens
        acc.total_tokens += usage.total_tokens

    # ------------------------------------------------------------------
    # ErrorClassification
    # ------------------------------------------------------------------

    def classify_error(self, error: Exception) -> ErrorClassificationResult:
        """Classify a vLLM error into a routing-actionable category.

        vLLM may return non-standard error payloads. This method maps them
        to categories the rotation policy understands.

        Categories: rate_limited, invalid_request, auth_failure, model_not_found,
        server_overloaded, gpu_oom, internal_error, gateway_error, timeout,
        network_error, unknown.
        """
        if isinstance(error, VllmHttpError):
            status = error.status_code

            # Rate limiting (if an external proxy adds it).
            if status == 429:
                return ErrorClassificationResult(
                    retryable=True,
                    category="rate_limited",
                    retry_after=15.0,
                )

            # Bad request -- malformed prompt or unsupported parameter.
            if status == 400:
                return ErrorClassificationResult(
                    retryable=False,
                    category="invalid_request",
                )

            # Authentication failure.
            if status in (401, 403):
                return ErrorClassificationResult(
                    retryable=False,
                    category="auth_failure",
                )

            # Model not found on the server.
            if status == 404:
                return ErrorClassificationResult(
                    retryable=False,
                    category="model_not_found",
                )

            # Server overloaded or CUDA out-of-memory.
            if status == 503:
                return ErrorClassificationResult(
                    retryable=True,
                    category="server_overloaded",
                    retry_after=30.0,
                )

            # Internal server error (possible CUDA crash).
            if status == 500:
                # Check for CUDA OOM in the response body.
                if error.detail and "CUDA out of memory" in error.detail:
                    return ErrorClassificationResult(
                        retryable=True,
                        category="gpu_oom",
                        retry_after=60.0,
                    )
                return ErrorClassificationResult(
                    retryable=True,
                    category="internal_error",
                    retry_after=10.0,
                )

            # Bad gateway / gateway timeout (reverse proxy issues).
            if status in (502, 504):
                return ErrorClassificationResult(
                    retryable=True,
                    category="gateway_error",
                    retry_after=10.0,
                )

        # Timeout errors.
        if isinstance(error, httpx.TimeoutException):
            return ErrorClassificationResult(
                retryable=True,
                category="timeout",
                retry_after=5.0,
            )

        # Network-level errors (DNS failure, connection refused).
        if isinstance(error, httpx.ConnectError):
            return ErrorClassificationResult(
                retryable=True,
                category="network_error",
                retry_after=10.0,
            )

        # Unknown errors: treat as non-retryable to avoid infinite loops.
        return ErrorClassificationResult(
            retryable=False,
            category="unknown",
        )

    def is_retryable(self, error: Exception) -> bool:
        """Convenience method: return True if the error is eligible for retry."""
        return self.classify_error(error).retryable

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(self, request: CompletionRequest, stream: bool) -> dict:
        """Translate a CompletionRequest into a vLLM-compatible JSON payload.

        vLLM's /v1/chat/completions endpoint is largely OpenAI-compatible,
        but some parameters (e.g., 'tools') may need adjustment depending
        on the deployed model's capabilities.
        """
        payload: dict = {
            "model": request.model,
            "messages": request.messages,
            "stream": stream,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        # vLLM supports tool calling only for certain models.
        # Include tools only if the model is in the catalogue and supports them.
        if request.tools:
            model_info = self._models.get(request.model)
            if model_info and "tool_calling" in model_info.capabilities:
                payload["tools"] = request.tools
            # Otherwise silently omit tools; the model cannot use them.

        return payload

    def _raise_api_error(self, response: httpx.Response) -> None:
        """Parse a vLLM error response and raise a VllmHttpError.

        vLLM error payloads vary:
          - Standard OpenAI format: {"error": {"message": "...", "type": "..."}}
          - Plain text errors during model loading
          - Empty bodies on connection-level failures
        """
        try:
            body = response.json()
            error_obj = body.get("error", body)
            message = error_obj.get("message", str(body)) if isinstance(error_obj, dict) else str(body)
            detail = error_obj.get("type") if isinstance(error_obj, dict) else None
        except (json.JSONDecodeError, AttributeError):
            message = response.text or f"HTTP {response.status_code}"
            detail = None

        raise VllmHttpError(
            status_code=response.status_code,
            message=message,
            detail=detail,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client and release connection pool resources."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Usage example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        # Create the connector pointing at a local vLLM instance.
        connector = VllmProviderConnector(
            base_url="http://localhost:8000",
            api_key="my-internal-token",
            models=[
                {
                    "id": "meta-llama/Llama-3.1-70B-Instruct",
                    "name": "Llama 3.1 70B",
                    "capabilities": ["generation.text-generation.chat-completion"],
                    "context_window": 131072,
                    "max_output_tokens": 4096,
                },
                {
                    "id": "mistralai/Mistral-7B-Instruct-v0.3",
                    "name": "Mistral 7B",
                    "capabilities": ["generation.text-generation.chat-completion"],
                    "context_window": 32768,
                    "max_output_tokens": 4096,
                },
            ],
        )

        try:
            # List available models.
            models = await connector.list_models()
            print("Available models:")
            for m in models:
                print(f"  - {m.name} ({m.id}), context={m.context_window}")

            # Check capabilities.
            print(f"\nSupports streaming: {connector.supports('streaming')}")

            # Send a non-streaming completion request.
            request = CompletionRequest(
                model="meta-llama/Llama-3.1-70B-Instruct",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Explain what vLLM is in one sentence."},
                ],
                temperature=0.7,
                max_tokens=128,
                stream=False,
            )

            print("\nSending completion request...")
            response = await connector.complete(request)
            print(f"Response ID: {response.id}")
            print(f"Tokens used: {response.usage.total_tokens}")

            # Check quota after the request.
            quota = await connector.check_quota()
            print(f"\nQuota: {quota.used}/{quota.limit} requests used")

            # Demonstrate error classification.
            err = VllmHttpError(503, "Model loading", "Model is still loading weights")
            classification = connector.classify_error(err)
            print(f"\nError classification: retryable={classification.retryable}, "
                  f"category={classification.category}")

        finally:
            await connector.close()

    asyncio.run(main())
