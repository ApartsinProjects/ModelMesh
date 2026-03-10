"""Observability connector interface and associated data types.

Defines the abstract ObservabilityConnector interface for exporting
routing activity to external outputs. Multiple connectors can be active
simultaneously. The library pushes data at three levels: events for
state changes, logs for request/response data, and statistics for
aggregate metrics.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(Enum):
    """Types of routing events emitted by the library."""

    MODEL_ACTIVATED = "model_activated"
    MODEL_DEACTIVATED = "model_deactivated"
    MODEL_ROTATED = "model_rotated"
    PROVIDER_HEALTH_CHANGED = "provider_health_changed"
    PROVIDER_DEACTIVATED = "provider_deactivated"
    PROVIDER_RECOVERED = "provider_recovered"
    POOL_MEMBERSHIP_CHANGED = "pool_membership_changed"
    DISCOVERY_MODELS_UPDATED = "discovery_models_updated"


class LogLevel(Enum):
    """Detail level for request/response logging."""

    METADATA = "metadata"
    SUMMARY = "summary"
    FULL = "full"


@dataclass
class RoutingEvent:
    """A routing state-change event."""

    event_type: EventType
    timestamp: datetime
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    pool_id: Optional[str] = None
    metadata: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class RequestLogEntry:
    """A single request/response log record."""

    timestamp: datetime
    model_id: str
    provider_id: str
    capability: str
    delivery_mode: str
    latency_ms: float
    status_code: int
    tokens_in: int
    tokens_out: int
    cost: Optional[float] = None
    error: Optional[str] = None


@dataclass
class AggregateStats:
    """Aggregate metrics for a model, provider, or pool over a time window."""

    requests_total: int
    requests_success: int
    requests_failed: int
    tokens_in: int
    tokens_out: int
    cost_total: float
    latency_avg: float
    latency_p95: float
    downtime_total: float
    rotation_events: int


class Severity(Enum):
    """Severity levels for structured trace reporting."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TraceEntry:
    """A structured trace/log entry with severity level."""

    severity: Severity
    timestamp: datetime
    component: str  # e.g. "router", "pool.text-generation", "provider.openai"
    message: str
    metadata: Optional[dict] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


class Events(ABC):
    """Publish routing decisions and state changes."""

    @abstractmethod
    def emit(self, event: RoutingEvent) -> None:
        """Emit a routing event to the configured output."""
        ...


class Logging(ABC):
    """Record request/response data at a configurable detail level."""

    @abstractmethod
    def log(self, entry: RequestLogEntry) -> None:
        """Record a request/response log entry."""
        ...


class Statistics(ABC):
    """Buffer and flush aggregate metrics."""

    @abstractmethod
    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Flush buffered aggregate statistics to the configured output."""
        ...


class Tracing(ABC):
    """Structured trace reporting with severity levels."""

    @abstractmethod
    def trace(self, entry: TraceEntry) -> None:
        """Record a trace entry at the specified severity level."""
        ...


class ObservabilityConnector(Events, Logging, Statistics, Tracing):
    """Full observability connector combining all required interfaces."""

    pass


__all__ = [
    "EventType",
    "LogLevel",
    "Severity",
    "RoutingEvent",
    "RequestLogEntry",
    "AggregateStats",
    "TraceEntry",
    "Events",
    "Logging",
    "Statistics",
    "Tracing",
    "ObservabilityConnector",
]
