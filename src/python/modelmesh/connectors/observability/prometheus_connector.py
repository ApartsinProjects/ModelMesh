"""Prometheus observability connector.

Exposes metrics in Prometheus text exposition format without requiring
the ``prometheus_client`` library. All counters, gauges, and histograms
are maintained as plain Python data structures and rendered on demand
via :meth:`render_metrics`.

Connector ID: ``modelmesh.prometheus.v1``
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)

__all__ = [
    "PrometheusConfig",
    "PrometheusConnector",
]

# Default histogram bucket boundaries (seconds).
_DEFAULT_BUCKETS: list[float] = [
    0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
]


@dataclass
class PrometheusConfig:
    """Configuration for the Prometheus observability connector.

    Attributes:
        prefix: Metric name prefix (default ``"modelmesh"``).
        include_model_labels: Include ``model`` label on metrics.
        include_provider_labels: Include ``provider`` label on metrics.
        histogram_buckets: Bucket boundaries for duration histograms.
    """

    prefix: str = "modelmesh"
    include_model_labels: bool = True
    include_provider_labels: bool = True
    histogram_buckets: list[float] = field(
        default_factory=lambda: list(_DEFAULT_BUCKETS)
    )


# ---------------------------------------------------------------------------
# Internal metric primitives
# ---------------------------------------------------------------------------


class _Counter:
    """Thread-safe monotonically increasing counter with label sets."""

    def __init__(self) -> None:
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def inc(self, labels: dict[str, str], amount: float = 1.0) -> None:
        """Increment the counter for the given label set."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def items(self) -> list[tuple[dict[str, str], float]]:
        """Return all (labels, value) pairs."""
        with self._lock:
            return [
                (dict(k), v) for k, v in self._values.items()
            ]


class _Gauge:
    """Thread-safe gauge that can go up and down."""

    def __init__(self) -> None:
        self._values: dict[tuple[tuple[str, str], ...], float] = {}
        self._lock = threading.Lock()

    def set(self, labels: dict[str, str], value: float) -> None:
        """Set the gauge to *value* for the given label set."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = value

    def inc(self, labels: dict[str, str], amount: float = 1.0) -> None:
        """Increment the gauge for the given label set."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, labels: dict[str, str], amount: float = 1.0) -> None:
        """Decrement the gauge for the given label set."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - amount

    def items(self) -> list[tuple[dict[str, str], float]]:
        """Return all (labels, value) pairs."""
        with self._lock:
            return [
                (dict(k), v) for k, v in self._values.items()
            ]


class _Histogram:
    """Thread-safe histogram with configurable buckets."""

    def __init__(self, buckets: list[float]) -> None:
        self._buckets = sorted(buckets)
        # Per label-set: (bucket_counts, sum, count)
        self._data: dict[
            tuple[tuple[str, str], ...],
            tuple[list[int], float, int],
        ] = {}
        self._lock = threading.Lock()

    def observe(self, labels: dict[str, str], value: float) -> None:
        """Record an observation."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            if key not in self._data:
                self._data[key] = (
                    [0] * len(self._buckets),
                    0.0,
                    0,
                )
            bucket_counts, total_sum, total_count = self._data[key]
            for i, bound in enumerate(self._buckets):
                if value <= bound:
                    bucket_counts[i] += 1
            self._data[key] = (
                bucket_counts,
                total_sum + value,
                total_count + 1,
            )

    def items(
        self,
    ) -> list[tuple[dict[str, str], list[float], list[int], float, int]]:
        """Return (labels, bucket_bounds, bucket_counts, sum, count)."""
        with self._lock:
            result = []
            for key, (counts, s, c) in self._data.items():
                result.append(
                    (dict(key), list(self._buckets), list(counts), s, c)
                )
            return result


# ---------------------------------------------------------------------------
# Prometheus text format helpers
# ---------------------------------------------------------------------------


def _format_labels(labels: dict[str, str]) -> str:
    """Format a label dict as a Prometheus label string."""
    if not labels:
        return ""
    parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"


def _render_counter(
    name: str, help_text: str, counter: _Counter
) -> list[str]:
    """Render a counter family in exposition format."""
    items = counter.items()
    if not items:
        return []
    lines: list[str] = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} counter",
    ]
    for labels, value in items:
        lbl = _format_labels(labels)
        lines.append(f"{name}{lbl} {value}")
    return lines


def _render_gauge(
    name: str, help_text: str, gauge: _Gauge
) -> list[str]:
    """Render a gauge family in exposition format."""
    items = gauge.items()
    if not items:
        return []
    lines: list[str] = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} gauge",
    ]
    for labels, value in items:
        lbl = _format_labels(labels)
        lines.append(f"{name}{lbl} {value}")
    return lines


def _render_histogram(
    name: str, help_text: str, histogram: _Histogram
) -> list[str]:
    """Render a histogram family in exposition format."""
    items = histogram.items()
    if not items:
        return []
    lines: list[str] = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} histogram",
    ]
    for labels, buckets, counts, total_sum, total_count in items:
        cumulative = 0
        for bound, count in zip(buckets, counts):
            cumulative += count
            lbl = {**labels, "le": str(bound)}
            lines.append(
                f"{name}_bucket{_format_labels(lbl)} {cumulative}"
            )
        lbl_inf = {**labels, "le": "+Inf"}
        lines.append(
            f"{name}_bucket{_format_labels(lbl_inf)} {total_count}"
        )
        lbl = _format_labels(labels)
        lines.append(f"{name}_sum{lbl} {total_sum}")
        lines.append(f"{name}_count{lbl} {total_count}")
    return lines


# ---------------------------------------------------------------------------
# PrometheusConnector
# ---------------------------------------------------------------------------


class PrometheusConnector(ObservabilityConnector):
    """Exposes metrics in Prometheus text exposition format.

    Implements the :class:`ObservabilityConnector` interface and maintains
    internal counters, gauges, and histograms. Call :meth:`render_metrics`
    to produce the text exposition string suitable for a ``/metrics``
    HTTP endpoint.

    No external dependencies are required; all metric storage is handled
    with plain Python dicts and threading locks.

    Connector ID: ``modelmesh.prometheus.v1``

    Usage::

        connector = PrometheusConnector(PrometheusConfig(prefix="myapp"))
        # ... events flow in via emit/log/flush/trace ...
        print(connector.render_metrics())
    """

    CONNECTOR_ID: str = "modelmesh.prometheus.v1"

    def __init__(self, config: PrometheusConfig | None = None) -> None:
        self._config = config or PrometheusConfig()
        p = self._config.prefix

        # Counters
        self._requests_total = _Counter()
        self._tokens_total = _Counter()
        self._cost_dollars_total = _Counter()
        self._rotation_events_total = _Counter()
        self._errors_total = _Counter()
        self._trace_total = _Counter()

        # Histograms
        self._request_duration_seconds = _Histogram(
            self._config.histogram_buckets
        )

        # Gauges
        self._active_models = _Gauge()
        self._standby_models = _Gauge()

        self._prefix = p

    # -- Label helpers -------------------------------------------------------

    def _base_labels(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        pool: Optional[str] = None,
    ) -> dict[str, str]:
        """Build a label dict respecting include_* flags."""
        labels: dict[str, str] = {}
        if model and self._config.include_model_labels:
            labels["model"] = model
        if provider and self._config.include_provider_labels:
            labels["provider"] = provider
        if pool:
            labels["pool"] = pool
        return labels

    # -- ObservabilityConnector implementation --------------------------------

    def trace(self, entry: TraceEntry) -> None:
        """Count trace entries by severity."""
        self._trace_total.inc({"severity": entry.severity.value})

    def emit(self, event: RoutingEvent) -> None:
        """Process routing events: count rotations, update model gauges."""
        if event.event_type == EventType.MODEL_ROTATED:
            labels = self._base_labels(pool=event.pool_id)
            self._rotation_events_total.inc(labels)

        # Update active/standby gauges from event metadata when provided.
        if event.metadata:
            pool = event.pool_id or ""
            if "active_count" in event.metadata:
                self._active_models.set(
                    {"pool": pool},
                    float(event.metadata["active_count"]),
                )
            if "standby_count" in event.metadata:
                self._standby_models.set(
                    {"pool": pool},
                    float(event.metadata["standby_count"]),
                )

    def log(self, entry: RequestLogEntry) -> None:
        """Update request counters, token counters, and duration histogram."""
        status = "success" if entry.error is None else "error"
        labels = self._base_labels(
            model=entry.model_id,
            provider=entry.provider_id,
        )

        # requests_total
        self._requests_total.inc({**labels, "status": status})

        # tokens_total
        if entry.tokens_in > 0:
            self._tokens_total.inc(
                {**labels, "direction": "input"},
                amount=float(entry.tokens_in),
            )
        if entry.tokens_out > 0:
            self._tokens_total.inc(
                {**labels, "direction": "output"},
                amount=float(entry.tokens_out),
            )

        # cost_dollars_total
        if entry.cost is not None and entry.cost > 0:
            self._cost_dollars_total.inc(labels, amount=entry.cost)

        # request_duration_seconds
        self._request_duration_seconds.observe(
            labels, entry.latency_ms / 1000.0
        )

        # errors_total
        if entry.error is not None:
            error_type = entry.error.split(":")[0] if entry.error else "unknown"
            self._errors_total.inc(
                {**labels, "error_type": error_type}
            )

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Update metrics from aggregate statistics."""
        for key, agg in stats.items():
            # key is typically "pool_id" or "pool_id.model_id"
            labels = {"source": key}

            self._requests_total.inc(
                {**labels, "status": "success"},
                amount=float(agg.requests_success),
            )
            self._requests_total.inc(
                {**labels, "status": "error"},
                amount=float(agg.requests_failed),
            )
            self._tokens_total.inc(
                {**labels, "direction": "input"},
                amount=float(agg.tokens_in),
            )
            self._tokens_total.inc(
                {**labels, "direction": "output"},
                amount=float(agg.tokens_out),
            )
            if agg.cost_total > 0:
                self._cost_dollars_total.inc(
                    labels, amount=agg.cost_total
                )
            if agg.rotation_events > 0:
                self._rotation_events_total.inc(
                    labels, amount=float(agg.rotation_events)
                )

    # -- Rendering -----------------------------------------------------------

    def render_metrics(self) -> str:
        """Render all metrics in Prometheus text exposition format.

        Returns:
            A string suitable for serving at ``/metrics`` with
            content type ``text/plain; version=0.0.4; charset=utf-8``.
        """
        p = self._prefix
        sections: list[list[str]] = []

        sections.append(
            _render_counter(
                f"{p}_requests_total",
                "Total number of requests processed.",
                self._requests_total,
            )
        )
        sections.append(
            _render_counter(
                f"{p}_tokens_total",
                "Total tokens processed.",
                self._tokens_total,
            )
        )
        sections.append(
            _render_counter(
                f"{p}_cost_dollars_total",
                "Total cost in US dollars.",
                self._cost_dollars_total,
            )
        )
        sections.append(
            _render_histogram(
                f"{p}_request_duration_seconds",
                "Request duration in seconds.",
                self._request_duration_seconds,
            )
        )
        sections.append(
            _render_gauge(
                f"{p}_active_models",
                "Number of active models per pool.",
                self._active_models,
            )
        )
        sections.append(
            _render_gauge(
                f"{p}_standby_models",
                "Number of standby models per pool.",
                self._standby_models,
            )
        )
        sections.append(
            _render_counter(
                f"{p}_rotation_events_total",
                "Total model rotation events.",
                self._rotation_events_total,
            )
        )
        sections.append(
            _render_counter(
                f"{p}_errors_total",
                "Total errors by type.",
                self._errors_total,
            )
        )
        sections.append(
            _render_counter(
                f"{p}_traces_total",
                "Total trace entries by severity.",
                self._trace_total,
            )
        )

        # Join non-empty sections separated by blank lines.
        output_parts: list[str] = []
        for section in sections:
            if section:
                output_parts.append("\n".join(section))

        return "\n\n".join(output_parts) + "\n" if output_parts else ""
