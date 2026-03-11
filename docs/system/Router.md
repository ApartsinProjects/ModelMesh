---
layout: default
title: "Router"
---

# Router

Central request orchestrator for ModelMesh Lite. Receives capability requests from the application (through `OpenAIClient` or `ProxyServer`), executes the routing pipeline, and returns the result. Handles retry and rotation transparently so that callers never need to manage failover logic.

**Depends on:** [RoutingPipeline](RoutingPipeline.md), [CapabilityPool](CapabilityPool.md), [EventEmitter](EventEmitter.md), [RequestLogger](RequestLogger.md).

---

## Python

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Any


@dataclass
class RoutingOptions:
    """Optional hints that influence routing decisions."""

    delivery_mode: str | None = None
    """Requested delivery mode: 'sync', 'streaming', or 'batch'."""

    preferred_provider: str | None = None
    """Prefer a specific provider when multiple are available."""

    session_id: str | None = None
    """Session identifier for session-sticky routing."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Arbitrary metadata passed through to pipeline stages."""


@dataclass
class RoutingDecision:
    """Result of the routing pipeline -- the resolved model and provider."""

    model_id: str
    """Identifier of the selected model."""

    provider_id: str
    """Identifier of the provider hosting the selected model."""

    pool_id: str
    """Identifier of the capability pool that sourced the model."""

    score: float
    """Numeric score assigned by the selection strategy."""

    fallback_chain: list[str] = field(default_factory=list)
    """Ordered list of fallback model identifiers if the primary fails."""


@dataclass
class CompletionRequest:
    """Unified completion request payload."""

    messages: list[dict[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Unified completion response payload."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchJob:
    """Handle to a submitted batch job."""

    job_id: str
    status: str
    model: str
    provider: str
    request_count: int


class Router:
    """Central request orchestrator."""

    _pipeline: RoutingPipeline
    _pools: dict[str, CapabilityPool]
    _event_emitter: EventEmitter
    _request_logger: RequestLogger
    _observability: ObservabilityConnector | None  # emits traces at DEBUG/INFO/WARNING/ERROR

    def route(
        self,
        capability: str,
        options: RoutingOptions | None = None,
    ) -> RoutingDecision:
        """Execute the routing pipeline and return a resolved model and
        provider.

        Args:
            capability: Capability name or virtual model name.
            options: Optional routing hints.

        Returns:
            A RoutingDecision with the selected model, provider, and score.
        """
        ...

    def complete(
        self,
        capability: str,
        request: CompletionRequest,
    ) -> CompletionResponse:
        """Route and execute a synchronous completion request.

        Args:
            capability: Capability name or virtual model name.
            request: The completion request payload.

        Returns:
            The completion response from the selected provider.
        """
        ...

    async def stream(
        self,
        capability: str,
        request: CompletionRequest,
    ) -> AsyncIterator[CompletionResponse]:
        """Route and execute a streaming request.

        Args:
            capability: Capability name or virtual model name.
            request: The completion request payload.

        Yields:
            Incremental completion response chunks.
        """
        ...

    def batch(
        self,
        capability: str,
        requests: list[CompletionRequest],
    ) -> BatchJob:
        """Route and submit a batch request.

        Args:
            capability: Capability name or virtual model name.
            requests: List of completion request payloads.

        Returns:
            A BatchJob handle for tracking the submitted batch.
        """
        ...

    def get_pool(self, name: str) -> CapabilityPool:
        """Return a specific CapabilityPool by name.

        Args:
            name: Pool identifier.

        Returns:
            The matching CapabilityPool.

        Raises:
            KeyError: If no pool exists with the given name.
        """
        ...

    def list_pools(self) -> list[CapabilityPool]:
        """Return all registered capability pools."""
        ...
```

---

## TypeScript

```typescript
interface RoutingOptions {
  /** Requested delivery mode: 'sync', 'streaming', or 'batch'. */
  deliveryMode?: string;
  /** Prefer a specific provider when multiple are available. */
  preferredProvider?: string;
  /** Session identifier for session-sticky routing. */
  sessionId?: string;
  /** Arbitrary metadata passed through to pipeline stages. */
  metadata?: Record<string, unknown>;
}

interface RoutingDecision {
  /** Identifier of the selected model. */
  modelId: string;
  /** Identifier of the provider hosting the selected model. */
  providerId: string;
  /** Identifier of the capability pool that sourced the model. */
  poolId: string;
  /** Numeric score assigned by the selection strategy. */
  score: number;
  /** Ordered list of fallback model identifiers. */
  fallbackChain: string[];
}

interface CompletionRequest {
  messages: Array<Record<string, unknown>>;
  temperature?: number;
  maxTokens?: number;
  stream?: boolean;
  tools?: Array<Record<string, unknown>>;
  metadata?: Record<string, unknown>;
}

interface CompletionResponse {
  content: string;
  model: string;
  provider: string;
  usage: Record<string, number>;
  latencyMs: number;
  metadata: Record<string, unknown>;
}

interface BatchJob {
  jobId: string;
  status: string;
  model: string;
  provider: string;
  requestCount: number;
}

class Router {
  private pipeline: RoutingPipeline;
  private pools: Map<string, CapabilityPool>;
  private eventEmitter: EventEmitter;
  private requestLogger: RequestLogger;

  /** Execute the routing pipeline and return a resolved model and provider. */
  route(capability: string, options?: RoutingOptions): RoutingDecision;

  /** Route and execute a synchronous completion request. */
  async complete(
    capability: string,
    request: CompletionRequest,
  ): Promise<CompletionResponse>;

  /** Route and execute a streaming request. */
  stream(
    capability: string,
    request: CompletionRequest,
  ): AsyncIterable<CompletionResponse>;

  /** Route and submit a batch request. */
  async batch(
    capability: string,
    requests: CompletionRequest[],
  ): Promise<BatchJob>;

  /** Return a specific CapabilityPool by name. */
  getPool(name: string): CapabilityPool;

  /** Return all registered capability pools. */
  listPools(): CapabilityPool[];
}
```
