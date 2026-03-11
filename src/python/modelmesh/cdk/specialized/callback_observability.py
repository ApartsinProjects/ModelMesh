"""Callback-based observability sink.

Routes events, logs, and traces to a user-supplied callback function,
enabling integration with custom dashboards, message queues, or alerting
systems without subclassing.

Usage::

    from modelmesh.cdk import CallbackObservability, CallbackObservabilityConfig

    def on_event(event):
        my_dashboard.send(event.event_type, event.model_id, event.timestamp)

    obs = CallbackObservability(CallbackObservabilityConfig(
        callback=on_event,
    ))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from modelmesh.cdk.base_observability import (
    BaseObservability,
    BaseObservabilityConfig,
)
from modelmesh.interfaces.observability import (
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)

__all__ = [
    "CallbackObservabilityConfig",
    "CallbackObservability",
]


@dataclass
class CallbackObservabilityConfig(BaseObservabilityConfig):
    """Configuration for CallbackObservability.

    Attributes:
        callback: Function called with each event, log entry, or trace.
            Receives the original object (RoutingEvent, RequestLogEntry,
            or TraceEntry), not a formatted string.
    """

    callback: Optional[Callable[[Any], None]] = None


class CallbackObservability(BaseObservability):
    """Observability sink that routes events to a user-supplied callback.

    The callback receives the original event/log/trace object (not a
    formatted string), enabling integration with custom dashboards,
    message queues, or alerting systems.

    Respects all BaseObservability filters (event_filter, min_severity,
    redact_secrets) before invoking the callback.
    """

    def __init__(self, config: CallbackObservabilityConfig) -> None:
        super().__init__(config)
        self._callback_fn = config.callback

    def emit(self, event: RoutingEvent) -> None:
        """Emit a routing event to the callback.

        Applies event_filter from config before invoking.
        """
        if self._config.event_filter:
            if event.event_type.value not in self._config.event_filter:
                return
        if self._callback_fn:
            self._callback_fn(event)

    def log(self, entry: RequestLogEntry) -> None:
        """Route a request/response log entry to the callback."""
        if self._callback_fn:
            self._callback_fn(entry)

    def trace(self, entry: TraceEntry) -> None:
        """Route a trace entry to the callback, filtering by min_severity."""
        min_level = self._SEVERITY_ORDER.get(
            Severity(self._config.min_severity), 1
        )
        entry_level = self._SEVERITY_ORDER.get(entry.severity, 0)
        if entry_level < min_level:
            return
        if self._callback_fn:
            self._callback_fn(entry)

    def _write(self, line: str) -> None:
        """No-op: output goes through callback, not formatted _write."""
        pass
