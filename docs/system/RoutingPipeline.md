---
layout: default
title: "RoutingPipeline"
---

# RoutingPipeline

Ordered sequence of stages that process each routing request. The default pipeline runs six stages: capability resolution, pool selection, delivery mode filter, state filter, selection strategy, and intelligent retry. Stages are composable -- custom stages can be inserted at any position or replace existing ones.

**Depends on:** [CapabilityResolver](CapabilityResolver.md), [DeliveryFilter](DeliveryFilter.md), [StateFilter](StateFilter.md), [SelectionStrategy](SelectionStrategy.md), [RetryPolicy](RetryPolicy.md).

---

## Python

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    """Mutable context passed through each pipeline stage."""

    capability: str
    """The requested capability name."""

    pool: CapabilityPool | None = None
    """The selected capability pool (set by pool selection stage)."""

    candidates: list[Model] = field(default_factory=list)
    """Current list of candidate models (filtered by each stage)."""

    delivery_mode: str = "sync"
    """Requested delivery mode: 'sync', 'streaming', or 'batch'."""

    selected_model: Model | None = None
    """The final selected model (set by selection stage)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Arbitrary metadata for custom stages."""


@dataclass
class PipelineRequest:
    """Input to the routing pipeline."""

    capability: str
    delivery_mode: str = "sync"
    preferred_provider: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Output from the routing pipeline."""

    model: Model
    provider: Provider
    pool: CapabilityPool
    score: float
    fallback_chain: list[Model] = field(default_factory=list)
    stages_executed: list[str] = field(default_factory=list)


class PipelineStage(ABC):
    """Abstract base class for a routing pipeline stage."""

    name: str

    @abstractmethod
    def process(self, context: PipelineContext) -> PipelineContext:
        """Process the pipeline context and return the (possibly modified)
        context for the next stage.

        Args:
            context: Current pipeline context with candidates and metadata.

        Returns:
            Updated pipeline context.
        """
        ...


class RoutingPipeline:
    """Ordered sequence of pipeline stages that resolve a capability request
    to a concrete model and provider.
    """

    _stages: list[PipelineStage]

    def __init__(self) -> None:
        self._stages = []

    def execute(self, request: PipelineRequest) -> PipelineResult:
        """Run all stages in order and return the routing decision.

        Args:
            request: The pipeline request containing capability and options.

        Returns:
            A PipelineResult with the selected model, provider, and score.

        Raises:
            RoutingError: If no suitable model is found after all stages.
        """
        ...

    def add_stage(self, stage: PipelineStage, position: int) -> None:
        """Insert a custom stage at a specific position.

        Args:
            stage: The pipeline stage to insert.
            position: Zero-based index at which to insert the stage.
        """
        ...

    def remove_stage(self, name: str) -> None:
        """Remove a stage by name.

        Args:
            name: The name of the stage to remove.

        Raises:
            KeyError: If no stage exists with the given name.
        """
        ...

    def get_stages(self) -> list[PipelineStage]:
        """Return the ordered list of stages."""
        ...
```

---

## TypeScript

```typescript
interface PipelineContext {
  /** The requested capability name. */
  capability: string;
  /** The selected capability pool. */
  pool: CapabilityPool | null;
  /** Current list of candidate models. */
  candidates: Model[];
  /** Requested delivery mode. */
  deliveryMode: string;
  /** The final selected model. */
  selectedModel: Model | null;
  /** Arbitrary metadata for custom stages. */
  metadata: Record<string, unknown>;
}

interface PipelineRequest {
  capability: string;
  deliveryMode?: string;
  preferredProvider?: string;
  sessionId?: string;
  metadata?: Record<string, unknown>;
}

interface PipelineResult {
  model: Model;
  provider: Provider;
  pool: CapabilityPool;
  score: number;
  fallbackChain: Model[];
  stagesExecuted: string[];
}

interface PipelineStage {
  /** Unique name identifying this stage. */
  name: string;
  /** Process the pipeline context and return the updated context. */
  process(context: PipelineContext): PipelineContext;
}

class RoutingPipeline {
  private stages: PipelineStage[];

  /** Run all stages in order and return the routing decision. */
  execute(request: PipelineRequest): PipelineResult;

  /** Insert a custom stage at a specific position. */
  addStage(stage: PipelineStage, position: number): void;

  /** Remove a stage by name. */
  removeStage(name: string): void;

  /** Return the ordered list of stages. */
  getStages(): PipelineStage[];
}
```

---

## Default Stages

| Order | Stage | Purpose |
| --- | --- | --- |
| 1 | [CapabilityResolver](CapabilityResolver.md) | Map the requested capability to matching pools using the capability hierarchy |
| 2 | Pool selection | Choose the target pool (single match or priority-based) |
| 3 | [DeliveryFilter](DeliveryFilter.md) | Exclude models that do not support the requested delivery mode |
| 4 | [StateFilter](StateFilter.md) | Exclude standby models and models from deactivated providers |
| 5 | [SelectionStrategy](SelectionStrategy.md) | Choose the best model from remaining candidates (see [RotationPolicyService](RotationPolicyService.md)) |
| 6 | [RetryPolicy](RetryPolicy.md) | On failure, retry with backoff or rotate to the next candidate |
