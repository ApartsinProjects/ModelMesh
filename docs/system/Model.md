# Model

Runtime representation of a model definition combined with its current state. The static definition declares capabilities, delivery modes, features, and constraints; the dynamic state tracks health, quotas, and cooldowns. A model belongs to one provider and participates in one or more capability pools.

**Depends on:** [ProviderService](ProviderService.md), [ModelState](ModelState.md).

---

## Python

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelDefinition:
    """Static model definition loaded from configuration."""

    provider: str
    """Provider identifier this model belongs to."""

    capabilities: list[str]
    """Capability leaf nodes (e.g., ['chat-completion', 'tool-calling'])."""

    delivery: str = "sync"
    """Default delivery mode: 'sync' or 'streaming'."""

    batch: bool = False
    """Whether the model supports batch delivery."""

    features: dict[str, bool] = field(default_factory=dict)
    """Feature flags (tool_calling, structured_output, json_mode, etc.)."""

    constraints: dict[str, Any] = field(default_factory=dict)
    """Operational limits (context_window, max_output_tokens, etc.)."""


class Model:
    """Runtime model with static definition and dynamic state."""

    _name: str
    _definition: ModelDefinition
    _state: ModelState
    _provider: Provider

    def __init__(
        self,
        name: str,
        definition: ModelDefinition,
        provider: Provider,
    ) -> None:
        self._name = name
        self._definition = definition
        self._provider = provider
        self._state = ModelState()

    @property
    def name(self) -> str:
        """Return the model identifier."""
        return self._name

    @property
    def definition(self) -> ModelDefinition:
        """Return the static model definition."""
        return self._definition

    def get_capabilities(self) -> list[str]:
        """Return the model's registered capability leaf nodes.

        Returns:
            List of capability names (e.g., ['chat-completion',
            'tool-calling']).
        """
        ...

    def get_delivery_modes(self) -> list[str]:
        """Return supported delivery modes.

        Returns:
            List of delivery mode strings (e.g., ['sync', 'streaming']).
        """
        ...

    def get_features(self) -> dict[str, bool]:
        """Return supported features.

        Returns:
            Dictionary of feature flags (e.g., {'tool_calling': True,
            'structured_output': True}).
        """
        ...

    def get_constraints(self) -> dict[str, Any]:
        """Return operational constraints.

        Returns:
            Dictionary of constraints (e.g., {'context_window': 128000,
            'max_output_tokens': 4096}).
        """
        ...

    def get_state(self) -> ModelState:
        """Return the current ModelState.

        Returns:
            The model's dynamic state object.
        """
        ...

    def update_state(self, result: RequestResult) -> None:
        """Update state after a request (success/failure, latency, tokens
        used).

        Args:
            result: The outcome of the most recent request.
        """
        ...

    def reset_state(self) -> None:
        """Reset failure counts and cooldown timers.  Called on manual
        recovery or quota reset.
        """
        ...
```

---

## TypeScript

```typescript
interface ModelDefinition {
  /** Provider identifier this model belongs to. */
  provider: string;
  /** Capability leaf nodes. */
  capabilities: string[];
  /** Default delivery mode. */
  delivery: string;
  /** Whether the model supports batch delivery. */
  batch: boolean;
  /** Feature flags. */
  features: Record<string, boolean>;
  /** Operational limits. */
  constraints: Record<string, unknown>;
}

class Model {
  private _name: string;
  private _definition: ModelDefinition;
  private _state: ModelState;
  private _provider: Provider;

  constructor(name: string, definition: ModelDefinition, provider: Provider);

  /** Return the model identifier. */
  get name(): string;

  /** Return the static model definition. */
  get definition(): ModelDefinition;

  /** Return the model's registered capability leaf nodes. */
  getCapabilities(): string[];

  /** Return supported delivery modes. */
  getDeliveryModes(): string[];

  /** Return supported features. */
  getFeatures(): Record<string, boolean>;

  /** Return operational constraints. */
  getConstraints(): Record<string, unknown>;

  /** Return the current ModelState. */
  getState(): ModelState;

  /** Update state after a request. */
  updateState(result: RequestResult): void;

  /** Reset failure counts and cooldown timers. */
  resetState(): void;
}
```

---

## Configuration

Model parameters are configured under the `models` section. See [SystemConfiguration.md -- Models](../SystemConfiguration.md#models).

| Parameter | Type | Description |
| --- | --- | --- |
| `provider` | string | Provider this model belongs to |
| `capabilities` | list | Capability leaf nodes (e.g., `[chat-completion, tool-calling]`) |
| `delivery` | string | Default delivery mode: `sync`, `streaming` |
| `batch` | boolean | Supports batch delivery |
| `features` | map | Feature flags (`tool_calling`, `structured_output`, `json_mode`, etc.) |
| `constraints` | map | Operational limits (`context_window`, `max_output_tokens`, etc.) |
