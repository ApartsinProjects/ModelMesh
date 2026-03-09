---
layout: default
title: "ModelRegistry"
---

# ModelRegistry

Local cache of known model definitions and the source of truth for pool membership and capability resolution. The registry is populated at initialization from YAML configuration and updated by discovery sync (automatic) or manual registration (API). All changes to the registry trigger a refresh of pool memberships, ensuring that models are added to or removed from capability pools as their definitions change. State is persisted through the StateManager across restarts.

**Depends on:** [CapabilityTree](CapabilityTree.html), [CapabilityPool](CapabilityPool.html)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


@dataclass
class ModelDefinition:
    """Static definition of a model as declared in configuration or discovery."""
    name: str
    provider: str
    capabilities: list[str]
    delivery: str = "sync"
    batch: bool = False
    features: dict[str, bool] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class Model:
    """Runtime representation of a registered model.

    Combines the static definition with dynamic state tracking.
    """
    name: str
    provider: str
    capabilities: list[str]
    delivery: str
    batch: bool
    features: dict[str, bool]
    constraints: dict[str, Any]
    pools: list[str] = field(default_factory=list)
    registered_at: Optional[datetime] = None


class ModelRegistry:
    """Local cache of model definitions.

    Source of truth for pool membership and capability resolution.
    Updated by discovery sync (automatic) and manual registration (API).
    Persisted through the StateManager.
    """

    def register(self, definition: ModelDefinition) -> Model:
        """Register a model and update pool memberships.

        Creates a runtime Model from the definition, assigns it to
        all matching capability pools based on its declared capabilities,
        and persists the registration through the StateManager.

        Args:
            definition: Static model definition from configuration or discovery.

        Returns:
            The registered runtime Model instance.
        """
        ...

    def unregister(self, model_name: str) -> bool:
        """Remove a model and update pool memberships.

        Removes the model from all capability pools it belongs to and
        deletes its state from the StateManager.

        Args:
            model_name: Name of the model to unregister.

        Returns:
            True if the model was found and removed, False otherwise.
        """
        ...

    def get_model(self, name: str) -> Optional[Model]:
        """Return a model by name.

        Args:
            name: The registered model name.

        Returns:
            The Model instance, or None if not found.
        """
        ...

    def list_models(self) -> list[Model]:
        """Return all registered models.

        Returns:
            A list of all Model instances in the registry.
        """
        ...

    def find_by_capability(self, capability: str) -> list[Model]:
        """Return models registered at a capability node or its descendants.

        Uses the CapabilityTree to traverse the hierarchy and find all
        models whose capabilities match the requested node.

        Args:
            capability: Capability path (e.g., "generation.text-generation").

        Returns:
            A list of matching Model instances.
        """
        ...

    def find_by_provider(self, provider: str) -> list[Model]:
        """Return all models from a specific provider.

        Args:
            provider: Provider identifier.

        Returns:
            A list of Model instances belonging to the provider.
        """
        ...

    def refresh(self) -> None:
        """Trigger re-evaluation of pool memberships after model changes.

        Iterates all registered models and recalculates their pool
        assignments based on current capability tree state. Called
        automatically after register/unregister and during discovery sync.
        """
        ...
```

## TypeScript

```typescript
/** Static definition of a model as declared in configuration or discovery. */
interface ModelDefinition {
    name: string;
    provider: string;
    capabilities: string[];
    delivery?: string;
    batch?: boolean;
    features?: Record<string, boolean>;
    constraints?: Record<string, unknown>;
}

/** Runtime representation of a registered model. */
interface Model {
    name: string;
    provider: string;
    capabilities: string[];
    delivery: string;
    batch: boolean;
    features: Record<string, boolean>;
    constraints: Record<string, unknown>;
    pools: string[];
    registered_at?: Date;
}

/** Local cache of model definitions. Source of truth for pool membership. */
class ModelRegistry {
    /** Register a model and update pool memberships. */
    register(definition: ModelDefinition): Model {
        throw new Error("Not implemented");
    }

    /** Remove a model and update pool memberships. */
    unregister(modelName: string): boolean {
        throw new Error("Not implemented");
    }

    /** Return a model by name. */
    getModel(name: string): Model | null {
        throw new Error("Not implemented");
    }

    /** Return all registered models. */
    listModels(): Model[] {
        throw new Error("Not implemented");
    }

    /** Return models registered at a capability node or its descendants. */
    findByCapability(capability: string): Model[] {
        throw new Error("Not implemented");
    }

    /** Return all models from a specific provider. */
    findByProvider(provider: string): Model[] {
        throw new Error("Not implemented");
    }

    /** Trigger re-evaluation of pool memberships after model changes. */
    refresh(): void {
        throw new Error("Not implemented");
    }
}
```
