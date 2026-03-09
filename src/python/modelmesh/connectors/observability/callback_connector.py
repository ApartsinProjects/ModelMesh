"""Callback observability connector.

Invokes user-provided Python callables for each observability event
type. Useful for testing, custom integrations, and in-process event
processing.

Connector ID: ``modelmesh.callback.v1``
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from modelmesh.interfaces.observability import (
    AggregateStats,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    TraceEntry,
)

__all__ = [
    "CallbackConnectorConfig",
    "CallbackConnector",
]


@dataclass
class CallbackConnectorConfig:
    """Configuration for the callback observability connector.

    All callbacks are optional. If a callback is ``None``, the
    corresponding method is a no-op.

    Attributes:
        on_trace: Callable invoked for each trace entry.
            Signature: ``(TraceEntry) -> None``.
        on_event: Callable invoked for each routing event.
            Signature: ``(RoutingEvent) -> None``.
        on_log: Callable invoked for each request log entry.
            Signature: ``(RequestLogEntry) -> None``.
        on_stats: Callable invoked for each stats flush.
            Signature: ``(dict[str, AggregateStats]) -> None``.
    """

    on_trace: Optional[Callable] = None
    on_event: Optional[Callable] = None
    on_log: Optional[Callable] = None
    on_stats: Optional[Callable] = None


class CallbackConnector(ObservabilityConnector):
    """Observability connector that delegates to user-provided callables.

    Each event type can have its own callback function. If a callback
    is not provided, the corresponding method is silently skipped.
    This makes the connector ideal for:

    - **Testing**: Capture events in a list for assertion.
    - **Custom integrations**: Forward events to in-process queues,
      metrics libraries, or domain-specific handlers.

    Connector ID: ``modelmesh.callback.v1``

    Usage::

        events = []
        obs = CallbackConnector(CallbackConnectorConfig(
            on_event=lambda e: events.append(e),
            on_trace=lambda t: print(t.message),
        ))
        obs.emit(some_event)
        assert len(events) == 1
    """

    CONNECTOR_ID: str = "modelmesh.callback.v1"

    def __init__(self, config: CallbackConnectorConfig | None = None) -> None:
        if config is None:
            config = CallbackConnectorConfig()
        self._config = config

    # -- ObservabilityConnector interface -----------------------------------

    def trace(self, entry: TraceEntry) -> None:
        """Invoke the ``on_trace`` callback if configured."""
        if self._config.on_trace is not None:
            self._config.on_trace(entry)

    def emit(self, event: RoutingEvent) -> None:
        """Invoke the ``on_event`` callback if configured."""
        if self._config.on_event is not None:
            self._config.on_event(event)

    def log(self, entry: RequestLogEntry) -> None:
        """Invoke the ``on_log`` callback if configured."""
        if self._config.on_log is not None:
            self._config.on_log(entry)

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Invoke the ``on_stats`` callback if configured."""
        if self._config.on_stats is not None:
            self._config.on_stats(stats)
