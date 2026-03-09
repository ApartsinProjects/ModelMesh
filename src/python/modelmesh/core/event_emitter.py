"""Event emitter for publishing routing events to observability connectors.

Provides a simple publish/subscribe mechanism for internal events such as
routing decisions, model rotations, and provider health changes. Multiple
observability connectors can subscribe simultaneously.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

__all__ = ["EventEmitter", "EventType", "Event"]


class EventType(Enum):
    """Types of events emitted by the system."""

    REQUEST_ROUTED = "request.routed"
    REQUEST_SUCCESS = "request.success"
    REQUEST_FAILURE = "request.failure"
    MODEL_DEACTIVATED = "model.deactivated"
    MODEL_REACTIVATED = "model.reactivated"
    MODEL_ROTATED = "model.rotated"
    PROVIDER_ERROR = "provider.error"
    POOL_EXHAUSTED = "pool.exhausted"
    RETRY_ATTEMPTED = "retry.attempted"


@dataclass
class Event:
    """An event emitted by the system.

    Attributes:
        type: The event type.
        timestamp: Unix timestamp when the event occurred.
        data: Arbitrary event payload (varies by event type).
    """

    type: EventType
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)


# Type alias for event handler callbacks
EventHandler = Callable[[Event], None]


class EventEmitter:
    """Publish/subscribe event bus for system observability.

    Handlers subscribe to specific event types and receive events as they
    are emitted. A wildcard subscription (``None`` event type) receives
    all events.

    Example::

        emitter = EventEmitter()

        def on_rotation(event: Event):
            print(f"Model rotated: {event.data}")

        emitter.on(EventType.MODEL_ROTATED, on_rotation)
        emitter.emit(EventType.MODEL_ROTATED, model_id="openai.gpt-4o")
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType | None, list[EventHandler]] = {}

    def on(
        self, event_type: EventType | None, handler: EventHandler
    ) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: The event type to listen for, or ``None`` to
                receive all events.
            handler: Callable that accepts an ``Event``.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(
        self, event_type: EventType | None, handler: EventHandler
    ) -> None:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The event type to unsubscribe from.
            handler: The handler to remove.
        """
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event_type: EventType, **data: Any) -> None:
        """Emit an event to all subscribed handlers.

        Constructs an ``Event`` with the given type and data, then
        dispatches to type-specific handlers and wildcard handlers.

        Args:
            event_type: The type of event to emit.
            **data: Key-value pairs forming the event payload.
        """
        event = Event(type=event_type, data=data)

        # Dispatch to type-specific handlers
        for handler in self._handlers.get(event_type, []):
            handler(event)

        # Dispatch to wildcard handlers
        for handler in self._handlers.get(None, []):
            handler(event)

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()
