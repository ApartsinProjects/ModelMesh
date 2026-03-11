---
layout: default
title: "SelectionStrategy"
---

# SelectionStrategy

Chooses the best model from active candidates for a given request. The strategy is pluggable: eight pre-shipped strategies cover common patterns (priority, round-robin, cost-first, latency-first, session stickiness, rate-limit-aware, load-balanced, and stick-until-failure), and custom implementations can be registered through the connector system. Each strategy receives the full candidate list with snapshots and the incoming request, returning a scored selection result.

**Depends on:** [RotationPolicyService](RotationPolicyService.md), [CapabilityPool](CapabilityPool.md)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class BalanceMode(Enum):
    """Distribution mode for the load-balanced strategy."""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


@dataclass
class ModelSnapshot:
    """Point-in-time view of a model's runtime state used for selection."""
    model_id: str
    provider_id: str
    status: str
    failure_count: int
    error_rate: float
    cooldown_remaining: float
    quota_used: int
    tokens_used: int
    cost_accumulated: float
    latency_history: list[float] = field(default_factory=list)
    last_request: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    deactivation_reason: Optional[str] = None


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
class SelectionResult:
    """Result of a model selection decision."""
    model_id: str
    provider_id: str
    score: float
    reason: str


class SelectionStrategy:
    """Chooses the best model from active candidates for a given request.

    Pluggable with eight pre-shipped strategies and custom implementations
    registered through the connector system. Scores all candidates and
    returns the highest-scoring model.
    """

    def select(
        self, candidates: list[ModelSnapshot], request: CompletionRequest
    ) -> SelectionResult:
        """Select the best model from the candidate list.

        Scores each candidate and returns the one with the highest score.
        When multiple candidates have equal scores, the first in the
        candidate list (priority order) wins.

        Args:
            candidates: Active models eligible for this request.
            request: The incoming completion request.

        Returns:
            A SelectionResult identifying the chosen model with its score.
        """
        ...

    def score(
        self, candidate: ModelSnapshot, request: CompletionRequest
    ) -> float:
        """Return a numeric score for a single candidate.

        Higher scores indicate better suitability. The scoring function
        varies by strategy (e.g., cost-first penalizes expensive models,
        latency-first rewards low-latency models).

        Args:
            candidate: A single active model snapshot.
            request: The incoming completion request.

        Returns:
            A float score used for ranking candidates.
        """
        ...
```

## TypeScript

```typescript
/** Distribution mode for the load-balanced strategy. */
enum BalanceMode {
    ABSOLUTE = "absolute",
    RELATIVE = "relative",
}

/** Point-in-time view of a model's runtime state used for selection. */
interface ModelSnapshot {
    model_id: string;
    provider_id: string;
    status: string;
    failure_count: number;
    error_rate: number;
    cooldown_remaining: number;
    quota_used: number;
    tokens_used: number;
    cost_accumulated: number;
    latency_history: number[];
    last_request?: Date;
    last_failure?: Date;
    deactivation_reason?: string;
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

/** Result of a model selection decision. */
interface SelectionResult {
    model_id: string;
    provider_id: string;
    score: number;
    reason: string;
}

/** Chooses the best model from active candidates for a given request. */
class SelectionStrategy {
    /**
     * Select the best model from the candidate list.
     *
     * Scores each candidate and returns the one with the highest score.
     */
    select(candidates: ModelSnapshot[], request: CompletionRequest): SelectionResult {
        throw new Error("Not implemented");
    }

    /**
     * Return a numeric score for a single candidate.
     *
     * Higher scores indicate better suitability.
     */
    score(candidate: ModelSnapshot, request: CompletionRequest): number {
        throw new Error("Not implemented");
    }
}
```

---

## Pre-shipped Strategies

| Strategy ID | Behavior |
| --- | --- |
| `modelmesh.stick-until-failure.v1` | Use the same model until it fails, then rotate. This is the default strategy. |
| `modelmesh.priority-selection.v1` | Always prefer the highest-priority available model from the configured priority list. |
| `modelmesh.round-robin.v1` | Cycle through active models in order, distributing requests evenly. |
| `modelmesh.cost-first.v1` | Select the cheapest available model based on per-token pricing. |
| `modelmesh.latency-first.v1` | Select the model with the lowest recent latency from its latency history. |
| `modelmesh.session-stickiness.v1` | Route all requests in a session to the same model for consistency. |
| `modelmesh.rate-limit-aware.v1` | Switch models preemptively before hitting rate limits based on headroom. |
| `modelmesh.load-balanced.v1` | Distribute requests proportionally to rate-limit headroom using absolute or relative balance mode. |

---

## Configuration

Parameters configured per pool under the selection and strategy keys. See [SystemConfiguration.md -- Pools](../SystemConfiguration.md#pools) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `strategy` | string | Selection strategy connector ID (e.g., `modelmesh.stick-until-failure.v1`). |
| `model_priority` | list | Ordered model preference list for priority-based strategies. |
| `provider_priority` | list | Ordered provider preference list for priority-based strategies. |
| `fallback_strategy` | string | Strategy to use after the priority list is exhausted. |
| `balance_mode` | string | For load-balanced strategy: `absolute` (equal distribution) or `relative` (proportional to headroom). |
| `rate_limit.threshold` | float | Switch models at this fraction of the rate limit (0.0--1.0). |
| `rate_limit.min_delta` | duration | Minimum time between requests to the same model. |
| `rate_limit.max_rpm` | integer | Maximum requests per minute before switching to the next model. |
