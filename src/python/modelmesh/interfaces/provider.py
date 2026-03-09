"""Provider connector interface and associated data types.

Defines the abstract ProviderConnector interface and all request/response
data types used for OpenAI-compatible model execution. Provider connectors
bridge the library's capability-driven routing model with concrete provider
APIs, handling authentication, format translation, streaming, usage tracking,
and error classification.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class ModelPricing:
    """Per-token and per-request cost metadata for a model."""

    input_per_1k_tokens: float = 0.0
    output_per_1k_tokens: float = 0.0
    per_request: float = 0.0


@dataclass
class ModelInfo:
    """Describes a model exposed by a provider connector.

    Model IDs use dot-notation (e.g. ``"openai.gpt-4o"``) to namespace
    by provider. Capabilities, features, and delivery modes feed pool
    membership and routing decisions.
    """

    id: str
    name: str
    capabilities: list[str] = field(default_factory=list)
    context_window: int = 0
    max_output_tokens: int = 0
    pricing: Optional[ModelPricing] = None
    features: dict[str, bool] = field(default_factory=dict)
    delivery: dict[str, bool] = field(
        default_factory=lambda: {"synchronous": True}
    )


@dataclass
class TokenUsage:
    """Token consumption for a single completion request."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatMessage:
    """A single message in a chat conversation.

    Used both for full messages (in non-streaming responses) and for
    partial deltas (in streaming responses).
    """

    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[list] = None


@dataclass
class CompletionChoice:
    """One candidate completion returned by the model.

    For streaming responses, ``delta`` carries the incremental content
    and ``message`` is ``None``. For non-streaming responses, ``message``
    carries the full content and ``delta`` is ``None``.
    """

    index: int = 0
    message: Optional[ChatMessage] = None
    delta: Optional[ChatMessage] = None
    finish_reason: Optional[str] = None


@dataclass
class CompletionRequest:
    """OpenAI ChatCompletion-compatible request payload.

    Passed to :meth:`ProviderConnector.complete` and
    :meth:`ProviderConnector.stream`. The ``model`` field uses
    dot-notated IDs (e.g. ``"openai.gpt-4o"``).
    """

    model: str
    messages: list[dict]
    temperature: float = 1.0
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list] = None
    top_p: float = 1.0
    stop: Optional[list[str]] = None


@dataclass
class CompletionResponse:
    """OpenAI ChatCompletion-compatible response.

    Attribute access matches the OpenAI SDK shape so callers can use
    ``response.choices[0].message.content`` without adaptation.
    """

    id: str = ""
    model: str = ""
    choices: list[CompletionChoice] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    created: int = 0
    object: str = "chat.completion"


@dataclass
class QuotaStatus:
    """Current quota consumption for a provider."""

    used: int = 0
    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset_at: Optional[str] = None


@dataclass
class RateLimitStatus:
    """Current rate-limit headroom for a provider."""

    requests_remaining: Optional[int] = None
    tokens_remaining: Optional[int] = None
    reset_at: Optional[str] = None


@dataclass
class ErrorClassification:
    """Structured classification of a provider error.

    Used by the router to decide between retry, rotation, or surfacing
    the error to the caller.
    """

    retryable: bool = False
    error_code: Optional[int] = None
    message: str = ""
    category: str = "unknown"  # "auth", "rate_limit", "server", "client", "network"


class ProviderConnector(ABC):
    """Abstract interface for provider connectors.

    A provider connector exposes one or more AI models through a uniform,
    OpenAI-compatible API. It translates requests, manages authentication,
    tracks usage, and reports operational data that drives routing and
    rotation decisions.

    Implementations should subclass this and provide concrete logic for
    each abstract method. The :meth:`is_retryable` convenience method
    and :meth:`close` lifecycle hook have default implementations.
    """

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a chat completion request and return the full response."""
        ...

    @abstractmethod
    async def stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[CompletionResponse]:
        """Execute a streaming chat completion, yielding response chunks."""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return the list of capabilities this provider supports."""
        ...

    @abstractmethod
    def supports(self, capability: str) -> bool:
        """Check whether this provider supports a specific capability."""
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Return all models available through this provider."""
        ...

    @abstractmethod
    def get_model_info(self, model_id: str) -> ModelInfo:
        """Return metadata for a specific model by its dot-notated ID."""
        ...

    @abstractmethod
    def check_quota(self) -> QuotaStatus:
        """Return current quota consumption and remaining capacity."""
        ...

    @abstractmethod
    def get_rate_limits(self) -> RateLimitStatus:
        """Return current rate-limit headroom."""
        ...

    @abstractmethod
    def get_pricing(self, model_id: str) -> ModelPricing:
        """Return pricing metadata for a specific model."""
        ...

    @abstractmethod
    def report_usage(self, model_id: str, usage: TokenUsage) -> None:
        """Record token usage for internal tracking and budget enforcement."""
        ...

    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify a provider error for retry and rotation decisions."""
        ...

    def is_retryable(self, error: Exception) -> bool:
        """Convenience method: return True if the error is retryable."""
        return self.classify_error(error).retryable

    async def close(self) -> None:
        """Release any resources held by this connector.

        Called during library shutdown. The default implementation is a
        no-op; subclasses may override to close HTTP sessions, flush
        buffers, etc.
        """
        pass


__all__ = [
    "ModelPricing",
    "ModelInfo",
    "TokenUsage",
    "ChatMessage",
    "CompletionChoice",
    "CompletionRequest",
    "CompletionResponse",
    "QuotaStatus",
    "RateLimitStatus",
    "ErrorClassification",
    "ProviderConnector",
]
