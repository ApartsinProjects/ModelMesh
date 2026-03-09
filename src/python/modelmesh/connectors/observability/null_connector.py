"""Null observability connector — discards all output.

This is the default observability connector used when no other connector
is configured. It implements all ObservabilityConnector methods as no-ops
for zero overhead.

Connector ID: ``modelmesh.null.v1``
"""
from __future__ import annotations

from modelmesh.interfaces.observability import (
    AggregateStats,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    TraceEntry,
)

__all__ = ["NullObservabilityConnector"]


class NullObservabilityConnector(ObservabilityConnector):
    """No-op observability connector.

    All methods silently discard their input. This is the default
    connector used when observability is not explicitly configured.

    Connector ID: ``modelmesh.null.v1``
    """

    CONNECTOR_ID: str = "modelmesh.null.v1"

    def emit(self, event: RoutingEvent) -> None:
        pass

    def log(self, entry: RequestLogEntry) -> None:
        pass

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        pass

    def trace(self, entry: TraceEntry) -> None:
        """Discard trace entry (no-op)."""
        pass
