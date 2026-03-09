"""Base observability implementation for the CDK.

Implements the full ObservabilityConnector interface (Events, Logging,
Statistics) with configurable event filtering, log-level control,
secret redaction, and scope-based statistics flushing. Subclasses
override protected hook methods to change output format and destination.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from modelmesh.interfaces.observability import (
    AggregateStats,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)


@dataclass
class BaseObservabilityConfig:
    """Configuration for a BaseObservability instance."""

    event_filter: list[str] = field(default_factory=list)
    log_level: str = "metadata"
    min_severity: str = "info"
    redact_secrets: bool = True
    flush_interval_seconds: float = 60.0
    scopes: list[str] = field(
        default_factory=lambda: ["model", "provider", "pool"]
    )


class BaseObservability(ObservabilityConnector):
    """Base implementation of the ObservabilityConnector interface.

    Provides event filtering, log-level control, secret redaction,
    and scope-based statistics flushing. Subclasses override the four
    protected hook methods to change output format and destination.
    """

    _SECRET_PATTERN = re.compile(
        r'("(?:api_key|token|secret|password|authorization)":\s*")([^"]+)(")',
        re.IGNORECASE,
    )

    _SEVERITY_ORDER = {
        Severity.DEBUG: 0,
        Severity.INFO: 1,
        Severity.WARNING: 2,
        Severity.ERROR: 3,
        Severity.CRITICAL: 4,
    }

    def __init__(self, config: BaseObservabilityConfig) -> None:
        self._config = config

    # -- Events --------------------------------------------------------------

    def emit(self, event: RoutingEvent) -> None:
        """Emit a routing event to the configured output."""
        if self._config.event_filter:
            if event.event_type.value not in self._config.event_filter:
                return

        line = self._format_event(event)
        if self._config.redact_secrets:
            line = self._redact(line)
        self._write(line)

    # -- Logging -------------------------------------------------------------

    def log(self, entry: RequestLogEntry) -> None:
        """Record a request/response log entry."""
        line = self._format_log(entry)
        if self._config.redact_secrets:
            line = self._redact(line)
        self._write(line)

    # -- Statistics ----------------------------------------------------------

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Flush buffered aggregate statistics to the configured output."""
        for scope_id, aggregate in stats.items():
            line = self._format_stats(scope_id, aggregate)
            self._write(line)

    # -- Tracing -------------------------------------------------------------

    def trace(self, entry: TraceEntry) -> None:
        """Record a trace entry, filtering by minimum severity."""
        min_level = self._SEVERITY_ORDER.get(
            Severity(self._config.min_severity), 1
        )
        entry_level = self._SEVERITY_ORDER.get(entry.severity, 0)
        if entry_level < min_level:
            return
        line = self._format_trace(entry)
        if self._config.redact_secrets:
            line = self._redact(line)
        self._write(line)

    def _format_trace(self, entry: TraceEntry) -> str:
        """Format a trace entry as a JSON string."""
        data = {
            "type": "trace",
            "severity": entry.severity.value,
            "timestamp": entry.timestamp.isoformat(),
            "component": entry.component,
            "message": entry.message,
        }
        if entry.metadata:
            data["metadata"] = entry.metadata
        if entry.error:
            data["error"] = entry.error
        return json.dumps(data, default=str)

    # -- Protected Hooks -----------------------------------------------------

    def _format_event(self, event: RoutingEvent) -> str:
        """Format a routing event as a JSON string."""
        return json.dumps(
            {
                "type": "event",
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "model_id": event.model_id,
                "provider_id": event.provider_id,
                "pool_id": event.pool_id,
                "metadata": event.metadata,
            },
            default=str,
        )

    def _format_log(self, entry: RequestLogEntry) -> str:
        """Format a log entry as a JSON string filtered by log level."""
        data: dict = {
            "type": "log",
            "timestamp": entry.timestamp.isoformat(),
            "model_id": entry.model_id,
            "provider_id": entry.provider_id,
            "status_code": entry.status_code,
            "latency_ms": entry.latency_ms,
        }

        if self._config.log_level in ("summary", "full"):
            data["tokens_in"] = entry.tokens_in
            data["tokens_out"] = entry.tokens_out
            data["cost"] = entry.cost
            data["capability"] = entry.capability
            data["delivery_mode"] = entry.delivery_mode

        if self._config.log_level == "full":
            data["error"] = entry.error

        return json.dumps(data, default=str)

    def _format_stats(self, scope_id: str, stats: AggregateStats) -> str:
        """Format aggregate statistics as a JSON string."""
        return json.dumps(
            {
                "type": "stats",
                "scope_id": scope_id,
                "requests_total": stats.requests_total,
                "requests_success": stats.requests_success,
                "requests_failed": stats.requests_failed,
                "tokens_in": stats.tokens_in,
                "tokens_out": stats.tokens_out,
                "cost_total": stats.cost_total,
                "latency_avg": stats.latency_avg,
                "latency_p95": stats.latency_p95,
                "downtime_total": stats.downtime_total,
                "rotation_events": stats.rotation_events,
            },
            default=str,
        )

    def _write(self, line: str) -> None:
        """Write a formatted line to the output destination.

        The default implementation is a no-op. Subclasses must
        override this method to write to console, file, HTTP
        endpoint, or message queue.
        """
        pass

    def _redact(self, text: str) -> str:
        """Redact secret values from a formatted string."""
        return self._SECRET_PATTERN.sub(r"\1***REDACTED***\3", text)


__all__ = [
    "BaseObservabilityConfig",
    "BaseObservability",
]
