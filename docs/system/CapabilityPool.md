# CapabilityPool

Groups models that fulfill the same capability. Manages active and standby model lists, delegates lifecycle decisions to its rotation policy, and provides the selection interface for the router. Pool membership is automatic: models registered at a capability leaf node join all pools targeting that node or its ancestors. Pools can be static (YAML-defined) or dynamic (custom selection function).

**Depends on:** [Model](Model.md), [RotationPolicyService](RotationPolicyService.md), [EventEmitter](EventEmitter.md).

---

## Python

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PoolState:
    """Aggregate state snapshot of a capability pool."""

    name: str
    """Pool identifier."""

    hierarchy_node: str
    """Capability hierarchy node this pool targets."""

    active_count: int
    """Number of models currently eligible for routing."""

    standby_count: int
    """Number of models currently excluded from routing."""

    total_requests: int
    """Total requests routed through this pool."""

    rotation_events: int
    """Number of rotation events (deactivations + recoveries)."""


class CapabilityPool:
    """A pool of models grouped by capability with rotation management."""

    _name: str
    _hierarchy_node: str
    _active_models: list[Model]
    _standby_models: list[Model]
    _rotation_policy: RotationPolicy
    _event_emitter: EventEmitter
    _observability: ObservabilityConnector | None  # emits traces for add/remove/rotate/deactivate

    def __init__(
        self,
        name: str,
        hierarchy_node: str,
        rotation_policy: RotationPolicy,
        event_emitter: EventEmitter,
    ) -> None:
        self._name = name
        self._hierarchy_node = hierarchy_node
        self._active_models = []
        self._standby_models = []
        self._rotation_policy = rotation_policy
        self._event_emitter = event_emitter

    def get_active_models(self) -> list[Model]:
        """Return all models currently eligible for routing."""
        ...

    def get_standby_models(self) -> list[Model]:
        """Return all models currently excluded from routing."""
        ...

    def add_model(self, model: Model) -> None:
        """Add a model to the pool (triggered by registration or discovery).

        Args:
            model: The model to add to the active set.
        """
        ...

    def remove_model(self, model: Model) -> None:
        """Remove a model from the pool.

        Args:
            model: The model to remove from both active and standby sets.
        """
        ...

    def select(self, request: CompletionRequest) -> Model:
        """Delegate to the selection strategy and return the best candidate.

        Args:
            request: The completion request used for scoring candidates.

        Returns:
            The selected model.

        Raises:
            NoAvailableModelError: If no active models remain.
        """
        ...

    def deactivate(self, model: Model, reason: str) -> None:
        """Move a model from active to standby with a recorded reason.

        Args:
            model: The model to deactivate.
            reason: Deactivation reason (e.g., 'error_threshold',
                    'quota_exhausted', 'budget_exceeded', 'token_limit',
                    'request_limit', 'maintenance_window', 'manual').
        """
        ...

    def recover(self, model: Model) -> None:
        """Move a model from standby back to active.

        Args:
            model: The model to recover.
        """
        ...

    def get_state(self) -> PoolState:
        """Return the pool's aggregate state.

        Returns:
            A PoolState snapshot with counts and rotation history.
        """
        ...
```

---

## TypeScript

```typescript
interface PoolState {
  /** Pool identifier. */
  name: string;
  /** Capability hierarchy node this pool targets. */
  hierarchyNode: string;
  /** Number of models currently eligible for routing. */
  activeCount: number;
  /** Number of models currently excluded from routing. */
  standbyCount: number;
  /** Total requests routed through this pool. */
  totalRequests: number;
  /** Number of rotation events (deactivations + recoveries). */
  rotationEvents: number;
}

class CapabilityPool {
  private name: string;
  private hierarchyNode: string;
  private activeModels: Model[];
  private standbyModels: Model[];
  private rotationPolicy: RotationPolicy;
  private eventEmitter: EventEmitter;

  constructor(
    name: string,
    hierarchyNode: string,
    rotationPolicy: RotationPolicy,
    eventEmitter: EventEmitter,
  );

  /** Return all models currently eligible for routing. */
  getActiveModels(): Model[];

  /** Return all models currently excluded from routing. */
  getStandbyModels(): Model[];

  /** Add a model to the pool. */
  addModel(model: Model): void;

  /** Remove a model from the pool. */
  removeModel(model: Model): void;

  /** Delegate to the selection strategy and return the best candidate. */
  select(request: CompletionRequest): Model;

  /** Move a model from active to standby with a recorded reason. */
  deactivate(model: Model, reason: string): void;

  /** Move a model from standby back to active. */
  recover(model: Model): void;

  /** Return the pool's aggregate state. */
  getState(): PoolState;
}
```

---

## Configuration

Pool parameters are configured under the `pools` section. See [SystemConfiguration.md -- Pools](../SystemConfiguration.md#pools).

| Parameter | Type | Description |
| --- | --- | --- |
| `hierarchy_node` | string | Capability node this pool targets |
| `allowed_providers` | list | Restrict pool to specific providers |
| `excluded_providers` | list | Exclude specific providers from pool |
| `model_priority` | list | Ordered model preference list |
| `provider_priority` | list | Ordered provider preference list |
| `strategy` | string | Selection strategy connector ID |
