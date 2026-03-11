"""Webhook observability connector.

Posts observability data (traces, events, logs, statistics) to HTTP
endpoints via POST requests. Suitable for forwarding alerts to Slack,
Discord, PagerDuty, or any custom webhook receiver.

Uses only ``urllib`` from the standard library -- zero external
dependencies.

Connector ID: ``modelmesh.webhook.v1``
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone

from modelmesh.interfaces.observability import (
    AggregateStats,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)

__all__ = [
    "WebhookConnectorConfig",
    "WebhookConnector",
]

# Ordered severity levels for comparison
_SEVERITY_ORDER: dict[str, int] = {
    Severity.DEBUG.value: 0,
    Severity.INFO.value: 1,
    Severity.WARNING.value: 2,
    Severity.ERROR.value: 3,
    Severity.CRITICAL.value: 4,
}


@dataclass
class WebhookConnectorConfig:
    """Configuration for the webhook observability connector.

    Attributes:
        url: The webhook endpoint URL. Required.
        method: HTTP method. Defaults to ``"POST"``.
        headers: Additional HTTP headers. Defaults to an empty dict.
        min_severity: Minimum severity level to send. Events below
            this level are silently dropped. Defaults to ``"error"``.
        batch_size: Number of records to queue before flushing to the
            webhook. 1 means send immediately. Defaults to 1.
        timeout_seconds: HTTP request timeout. Defaults to 10.
    """

    url: str = ""
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    min_severity: str = "error"
    batch_size: int = 1
    timeout_seconds: float = 10.0


class WebhookConnector(ObservabilityConnector):
    """Observability connector that posts data to HTTP webhooks.

    Filters events by severity level and supports batching. When
    ``batch_size`` is greater than 1, records are queued and flushed
    as a JSON array when the queue reaches the configured size. Call
    ``flush_batch()`` to force-send any queued records.

    Connector ID: ``modelmesh.webhook.v1``

    Usage::

        obs = WebhookConnector(WebhookConnectorConfig(
            url="https://hooks.slack.com/services/T00/B00/xxx",
            min_severity="warning",
            batch_size=5,
            headers={"Authorization": "Bearer token"},
        ))
        obs.trace(some_trace_entry)
    """

    CONNECTOR_ID: str = "modelmesh.webhook.v1"

    def __init__(self, config: WebhookConnectorConfig | None = None) -> None:
        if config is None:
            config = WebhookConnectorConfig()
        self._config = config
        self._batch: list[dict] = []

    def _meets_severity(self, severity: str) -> bool:
        """Return True if the given severity meets the minimum threshold."""
        level = _SEVERITY_ORDER.get(severity, 0)
        threshold = _SEVERITY_ORDER.get(self._config.min_severity, 3)
        return level >= threshold

    def _enqueue(self, record: dict) -> None:
        """Add a record to the batch queue, flushing if full."""
        self._batch.append(record)
        if len(self._batch) >= self._config.batch_size:
            self.flush_batch()

    def flush_batch(self) -> None:
        """Send all queued records to the webhook endpoint.

        Silently discards records on HTTP errors to avoid disrupting
        the application. Call this explicitly to flush any remaining
        records when batch_size > 1.
        """
        if not self._batch or not self._config.url:
            return

        payload = self._batch if len(self._batch) > 1 else self._batch[0]
        self._batch = []

        try:
            body = json.dumps(payload, default=str).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                **self._config.headers,
            }
            req = urllib.request.Request(
                self._config.url,
                data=body,
                headers=headers,
                method=self._config.method,
            )
            urllib.request.urlopen(
                req, timeout=self._config.timeout_seconds
            )
        except (urllib.error.URLError, OSError, ValueError):
            # Silently discard on failure -- observability must not
            # crash the application.
            pass

    def _make_record(
        self,
        record_type: str,
        severity: str,
        component: str,
        message: str,
        metadata: dict | None = None,
    ) -> dict:
        """Build a standard record dict."""
        return {
            "type": record_type,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "severity": severity,
            "component": component,
            "message": message,
            "metadata": metadata or {},
        }

    # -- ObservabilityConnector interface -----------------------------------

    def trace(self, entry: TraceEntry) -> None:
        """Post a trace entry to the webhook if it meets min_severity."""
        if not self._meets_severity(entry.severity.value):
            return
        record = self._make_record(
            "trace",
            entry.severity.value,
            entry.component,
            entry.message,
            {**(entry.metadata or {}), "error": entry.error},
        )
        record["timestamp"] = entry.timestamp.isoformat()
        self._enqueue(record)

    def emit(self, event: RoutingEvent) -> None:
        """Post a routing event to the webhook (treated as INFO)."""
        severity = Severity.INFO.value
        if not self._meets_severity(severity):
            return
        record = self._make_record(
            "event",
            severity,
            "router",
            event.event_type.value,
            {
                "model_id": event.model_id,
                "provider_id": event.provider_id,
                "pool_id": event.pool_id,
                **(event.metadata or {}),
            },
        )
        record["timestamp"] = event.timestamp.isoformat()
        self._enqueue(record)

    def log(self, entry: RequestLogEntry) -> None:
        """Post a request log entry to the webhook."""
        severity = Severity.ERROR.value if entry.error else Severity.INFO.value
        if not self._meets_severity(severity):
            return
        record = self._make_record(
            "log",
            severity,
            f"provider.{entry.provider_id}",
            f"{entry.capability} {entry.status_code} {entry.latency_ms:.0f}ms",
            {
                "model_id": entry.model_id,
                "provider_id": entry.provider_id,
                "latency_ms": entry.latency_ms,
                "status_code": entry.status_code,
                "tokens_in": entry.tokens_in,
                "tokens_out": entry.tokens_out,
                "cost": entry.cost,
                "error": entry.error,
            },
        )
        record["timestamp"] = entry.timestamp.isoformat()
        self._enqueue(record)

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Post aggregate statistics to the webhook (treated as INFO)."""
        severity = Severity.INFO.value
        if not self._meets_severity(severity):
            return
        for entity_id, agg in stats.items():
            record = self._make_record(
                "stats",
                severity,
                entity_id,
                f"stats flush: {agg.requests_total} requests",
                {
                    "requests_total": agg.requests_total,
                    "requests_success": agg.requests_success,
                    "requests_failed": agg.requests_failed,
                    "tokens_in": agg.tokens_in,
                    "tokens_out": agg.tokens_out,
                    "cost_total": agg.cost_total,
                    "latency_avg": agg.latency_avg,
                    "latency_p95": agg.latency_p95,
                },
            )
            self._enqueue(record)
