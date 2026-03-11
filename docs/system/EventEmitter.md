---
layout: default
title: "EventEmitter"
---

# EventEmitter

Publishes routing events to all active observability connectors. Events cover the full model lifecycle -- activation, deactivation, rotation, recovery -- as well as provider health changes, pool membership updates, and discovery sync results. Multiple connectors can subscribe simultaneously (e.g., a webhook connector for alerts and a file connector for dashboards).

**Depends on:** [ObservabilityConnector](../ConnectorInterfaces.md#observability)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventType(Enum):
    """Classification of routing events emitted by the system."""
    MODEL_ACTIVATED = "model_activated"
    MODEL_DEACTIVATED = "model_deactivated"
    MODEL_ROTATED = "model_rotated"
    PROVIDER_HEALTH_CHANGED = "provider_health_changed"
    PROVIDER_DEACTIVATED = "provider_deactivated"
    PROVIDER_RECOVERED = "provider_recovered"
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed"
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated"


@dataclass
class RoutingEvent:
    """A single routing event published to observability connectors."""
    event_type: EventType
    timestamp: datetime
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    pool_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ObservabilityConnector:
    """Base type for observability connectors that receive events.

    See ConnectorInterfaces.md for the full connector contract.
    """
    ...


class EventEmitter:
    """Publishes routing events to observability connectors.

    Events include model activation, deactivation, rotation, recovery,
    and provider health changes. Multiple connectors can subscribe
    simultaneously for different output targets.
    """

    def emit(self, event: RoutingEvent) -> None:
        """Publish an event to all subscribed observability connectors.

        The event is delivered synchronously to each subscriber. If a
        subscriber raises an exception, the error is logged and delivery
        continues to remaining subscribers.

        Args:
            event: The routing event to publish.
        """
        ...

    def subscribe(self, connector: ObservabilityConnector) -> None:
        """Register an observability connector to receive events.

        Duplicate subscriptions for the same connector are ignored.

        Args:
            connector: The observability connector to subscribe.
        """
        ...

    def unsubscribe(self, connector: ObservabilityConnector) -> None:
        """Remove an observability connector from the subscriber list.

        Args:
            connector: The observability connector to unsubscribe.
        """
        ...
```

## TypeScript

```typescript
/** Classification of routing events emitted by the system. */
enum EventType {
    MODEL_ACTIVATED = "model_activated",
    MODEL_DEACTIVATED = "model_deactivated",
    MODEL_ROTATED = "model_rotated",
    PROVIDER_HEALTH_CHANGED = "provider_health_changed",
    PROVIDER_DEACTIVATED = "provider_deactivated",
    PROVIDER_RECOVERED = "provider_recovered",
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed",
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated",
}

/** A single routing event published to observability connectors. */
interface RoutingEvent {
    event_type: EventType;
    timestamp: Date;
    model_id?: string;
    provider_id?: string;
    pool_id?: string;
    metadata: Record<string, unknown>;
}

/** Base type for observability connectors that receive events. */
interface ObservabilityConnector {
    emit(event: RoutingEvent): void;
}

/** Publishes routing events to observability connectors. */
class EventEmitter {
    /**
     * Publish an event to all subscribed observability connectors.
     *
     * Delivery continues to remaining subscribers even if one throws.
     */
    emit(event: RoutingEvent): void {
        throw new Error("Not implemented");
    }

    /** Register an observability connector to receive events. */
    subscribe(connector: ObservabilityConnector): void {
        throw new Error("Not implemented");
    }

    /** Remove an observability connector from the subscriber list. */
    unsubscribe(connector: ObservabilityConnector): void {
        throw new Error("Not implemented");
    }
}
```

---

## Configuration

See [SystemConfiguration.md -- Observability](../SystemConfiguration.md#observability) for full YAML reference.

| Parameter | Type | Description |
| --- | --- | --- |
| `observability.routing.connector` | string | Observability connector ID for routing events. |
| `observability.routing.events` | list | Event types to emit. Default: all types listed above. |
