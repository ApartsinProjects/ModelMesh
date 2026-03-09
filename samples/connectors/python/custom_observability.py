"""
Custom Observability Connector -- Slack Webhook + JSON File Logger

Demonstrates how to implement a custom observability connector for ModelMesh Lite
that sends formatted routing events to a Slack webhook and logs all
request/response data to a structured JSON file with rotation.

This connector also aggregates statistics in memory and periodically flushes
them to both Slack (summary) and the JSON log file (detailed).

See: docs/interfaces/Observability.md

Requirements:
    pip install httpx
"""
# For a simpler CDK-based approach, see samples/cdk/python/

from __future__ import annotations

import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import httpx


# ---------------------------------------------------------------------------
# Supporting types (from Observability interface)
# ---------------------------------------------------------------------------

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
    metadata: dict = None

    def __post_init__(self):
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
    """Aggregate metrics for a single model, provider, or pool."""
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


# ---------------------------------------------------------------------------
# Interface ABCs (from Observability interface)
# ---------------------------------------------------------------------------

class Events(ABC):
    @abstractmethod
    def emit(self, event: RoutingEvent) -> None: ...


class Logging(ABC):
    @abstractmethod
    def log(self, entry: RequestLogEntry) -> None: ...


class Statistics(ABC):
    @abstractmethod
    def flush(self, stats: dict[str, AggregateStats]) -> None: ...


class ObservabilityConnector(Events, Logging, Statistics):
    """Full observability connector combining all required interfaces."""
    pass


# ---------------------------------------------------------------------------
# Slack message formatting helpers
# ---------------------------------------------------------------------------

# Map event types to Slack emoji for visual clarity in channels.
_EVENT_EMOJI: dict[EventType, str] = {
    EventType.MODEL_ACTIVATED: ":large_green_circle:",
    EventType.MODEL_DEACTIVATED: ":red_circle:",
    EventType.MODEL_ROTATED: ":arrows_counterclockwise:",
    EventType.PROVIDER_HEALTH_CHANGED: ":warning:",
    EventType.PROVIDER_DEACTIVATED: ":no_entry:",
    EventType.PROVIDER_RECOVERED: ":white_check_mark:",
    EventType.POOL_MEMBERSHIP_CHANGED: ":busts_in_silhouette:",
    EventType.DISCOVERY_MODELS_UPDATED: ":mag:",
}

# Severity coloring for Slack attachments (hex color codes).
_EVENT_SEVERITY_COLOR: dict[EventType, str] = {
    EventType.MODEL_ACTIVATED: "#36a64f",       # green
    EventType.MODEL_DEACTIVATED: "#e01e5a",     # red
    EventType.MODEL_ROTATED: "#f2c744",         # yellow
    EventType.PROVIDER_HEALTH_CHANGED: "#f2c744",
    EventType.PROVIDER_DEACTIVATED: "#e01e5a",
    EventType.PROVIDER_RECOVERED: "#36a64f",
    EventType.POOL_MEMBERSHIP_CHANGED: "#2eb886",
    EventType.DISCOVERY_MODELS_UPDATED: "#4a90d9",
}


def _format_slack_event(event: RoutingEvent) -> dict:
    """Build a Slack Block Kit message payload for a routing event."""
    emoji = _EVENT_EMOJI.get(event.event_type, ":bell:")
    color = _EVENT_SEVERITY_COLOR.get(event.event_type, "#cccccc")
    event_name = event.event_type.value.replace("_", " ").title()

    fields = []
    if event.model_id:
        fields.append({"title": "Model", "value": f"`{event.model_id}`", "short": True})
    if event.provider_id:
        fields.append({"title": "Provider", "value": f"`{event.provider_id}`", "short": True})
    if event.pool_id:
        fields.append({"title": "Pool", "value": f"`{event.pool_id}`", "short": True})

    # Add any extra metadata as fields.
    for key, value in event.metadata.items():
        fields.append({"title": key, "value": str(value), "short": True})

    return {
        "attachments": [
            {
                "color": color,
                "title": f"{emoji} {event_name}",
                "fields": fields,
                "footer": "ModelMesh Lite",
                "ts": int(event.timestamp.timestamp()),
            }
        ]
    }


def _format_slack_stats_summary(stats: dict[str, AggregateStats]) -> dict:
    """Build a Slack message payload summarizing aggregate statistics."""
    total_requests = sum(s.requests_total for s in stats.values())
    total_success = sum(s.requests_success for s in stats.values())
    total_failed = sum(s.requests_failed for s in stats.values())
    total_cost = sum(s.cost_total for s in stats.values())
    total_tokens_in = sum(s.tokens_in for s in stats.values())
    total_tokens_out = sum(s.tokens_out for s in stats.values())

    success_rate = (total_success / total_requests * 100) if total_requests > 0 else 0

    lines = [
        f"*Requests:* {total_requests} total, {total_success} success, {total_failed} failed ({success_rate:.1f}% success rate)",
        f"*Tokens:* {total_tokens_in:,} in, {total_tokens_out:,} out",
        f"*Cost:* ${total_cost:.4f}",
        "",
        "*Per-scope breakdown:*",
    ]

    for scope_id, s in sorted(stats.items()):
        scope_rate = (s.requests_success / s.requests_total * 100) if s.requests_total > 0 else 0
        lines.append(
            f"  `{scope_id}`: {s.requests_total} req, "
            f"avg latency {s.latency_avg:.0f}ms, "
            f"p95 {s.latency_p95:.0f}ms, "
            f"{scope_rate:.0f}% success, "
            f"${s.cost_total:.4f}"
        )

    return {
        "attachments": [
            {
                "color": "#4a90d9",
                "title": ":bar_chart: ModelMesh Lite -- Statistics Flush",
                "text": "\n".join(lines),
                "footer": "ModelMesh Lite",
                "ts": int(time.time()),
            }
        ]
    }


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

class SlackJsonObservabilityConnector(ObservabilityConnector):
    """Observability connector that sends events to Slack and logs to JSON files.

    Events are posted to a Slack Incoming Webhook URL as formatted messages.
    Request/response logs are written to a structured JSON file with rotation.
    Statistics summaries are sent to Slack periodically and appended to the
    log file.

    Configuration example (YAML):

        observability:
          - connector: custom
            connector_class: SlackJsonObservabilityConnector
            config:
              slack_webhook_url: "${secrets:slack-webhook-url}"
              slack_channel: "#modelmesh-alerts"
              slack_event_filter:
                - model_deactivated
                - model_rotated
                - provider_deactivated
                - provider_recovered
              log_directory: "./logs/modelmesh"
              max_log_file_size_bytes: 10485760   # 10 MB
              max_log_files: 10
              send_stats_to_slack: false
              slow_request_threshold_ms: 5000
            events:
              filter: [rotation, deactivation, recovery, health]
              include_metadata: true
            logging:
              level: summary
              redact_secrets: true
            statistics:
              flush_interval: 60s
              retention: 7d
              scopes: [model, provider, pool]
    """

    def __init__(
        self,
        slack_webhook_url: str,
        slack_channel: Optional[str] = None,
        slack_event_filter: Optional[list[str]] = None,
        log_directory: str = "./logs/modelmesh",
        max_log_file_size_bytes: int = 10 * 1024 * 1024,
        max_log_files: int = 10,
        send_stats_to_slack: bool = False,
        slow_request_threshold_ms: Optional[int] = None,
    ) -> None:
        """Initialize the Slack + JSON observability connector.

        Args:
            slack_webhook_url: Slack Incoming Webhook URL.
            slack_channel: Slack channel override (uses webhook default if omitted).
            slack_event_filter: List of event type names to send to Slack.
                                If None, all events are sent.
            log_directory: Directory where JSON log files are written.
            max_log_file_size_bytes: Maximum log file size in bytes before rotation.
            max_log_files: Maximum number of rotated log files to keep.
            send_stats_to_slack: If True, send stats summaries to Slack on flush.
            slow_request_threshold_ms: Minimum latency_ms to trigger a Slack alert
                                       for slow requests. None disables alerting.
        """
        self._slack_url = slack_webhook_url
        self._slack_channel = slack_channel
        self._slack_event_filter: Optional[set[str]] = (
            set(slack_event_filter) if slack_event_filter else None
        )
        self._send_stats_to_slack = send_stats_to_slack
        self._slow_request_threshold_ms = slow_request_threshold_ms
        self._log_level = LogLevel.SUMMARY

        # HTTP client for Slack webhook calls.
        self._http_client = httpx.Client(timeout=10.0)

        # Set up the structured JSON logger with rotation.
        log_dir = Path(log_directory)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "modelmesh.jsonl"

        self._logger = logging.getLogger("modelmesh.observability")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False  # Don't bubble up to root logger.

        # Rotating file handler writes JSON lines.
        handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_log_file_size_bytes,
            backupCount=max_log_files,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

        # Thread lock for safe concurrent writes.
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def emit(self, event: RoutingEvent) -> None:
        """Emit a routing event to both the JSON log and Slack.

        The event is always written to the JSON log. It is sent to Slack
        only if it passes the event type filter.
        """
        # Write to JSON log.
        log_record = {
            "type": "event",
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "model_id": event.model_id,
            "provider_id": event.provider_id,
            "pool_id": event.pool_id,
            "metadata": event.metadata,
        }
        self._write_json_log(log_record)

        # Send to Slack if the event type passes the filter.
        if self._should_send_to_slack(event.event_type):
            payload = _format_slack_event(event)
            self._post_to_slack(payload)

    def _should_send_to_slack(self, event_type: EventType) -> bool:
        """Check whether the event type passes the Slack filter."""
        if self._slack_event_filter is None:
            return True  # No filter means send everything.
        return event_type.value in self._slack_event_filter

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, entry: RequestLogEntry) -> None:
        """Record a request/response log entry to the JSON file.

        The amount of detail written depends on the configured log level:
          - metadata: timestamp, model, provider, latency, status code only.
          - summary: adds tokens, cost, capability, delivery mode.
          - full: adds everything including error details.
        """
        record: dict = {
            "type": "request_log",
            "timestamp": entry.timestamp.isoformat(),
            "model_id": entry.model_id,
            "provider_id": entry.provider_id,
            "latency_ms": entry.latency_ms,
            "status_code": entry.status_code,
        }

        if self._log_level in (LogLevel.SUMMARY, LogLevel.FULL):
            record["capability"] = entry.capability
            record["delivery_mode"] = entry.delivery_mode
            record["tokens_in"] = entry.tokens_in
            record["tokens_out"] = entry.tokens_out
            record["cost"] = entry.cost

        if self._log_level == LogLevel.FULL:
            record["error"] = entry.error

        self._write_json_log(record)

        # Alert on slow requests if threshold is configured.
        if (
            self._slow_request_threshold_ms is not None
            and entry.latency_ms > self._slow_request_threshold_ms
        ):
            self._send_slow_request_alert(entry)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Flush aggregate statistics to the JSON log and optionally to Slack.

        Each scope's stats are written as a separate JSON log line. A summary
        message is posted to Slack if slack_stats_enabled is True.
        """
        for scope_id, scope_stats in stats.items():
            record = {
                "type": "stats_flush",
                "scope_id": scope_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requests_total": scope_stats.requests_total,
                "requests_success": scope_stats.requests_success,
                "requests_failed": scope_stats.requests_failed,
                "tokens_in": scope_stats.tokens_in,
                "tokens_out": scope_stats.tokens_out,
                "cost_total": scope_stats.cost_total,
                "latency_avg": scope_stats.latency_avg,
                "latency_p95": scope_stats.latency_p95,
                "downtime_total": scope_stats.downtime_total,
                "rotation_events": scope_stats.rotation_events,
            }
            self._write_json_log(record)

        # Send summary to Slack.
        if self._send_stats_to_slack and stats:
            payload = _format_slack_stats_summary(stats)
            self._post_to_slack(payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_json_log(self, record: dict) -> None:
        """Write a JSON record to the rotating log file (thread-safe)."""
        with self._lock:
            self._logger.info(json.dumps(record, default=str))

    def _post_to_slack(self, payload: dict) -> None:
        """Post a message payload to the Slack webhook.

        Errors are logged but not raised -- observability should not break
        the main request flow.
        """
        try:
            response = self._http_client.post(self._slack_url, json=payload)
            if response.status_code != 200:
                self._write_json_log({
                    "type": "observability_error",
                    "target": "slack",
                    "status_code": response.status_code,
                    "body": response.text[:500],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except httpx.HTTPError as exc:
            self._write_json_log({
                "type": "observability_error",
                "target": "slack",
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def _send_slow_request_alert(self, entry: RequestLogEntry) -> None:
        """Send a Slack alert for a request that exceeded the latency threshold."""
        payload = {
            "attachments": [
                {
                    "color": "#f2c744",
                    "title": ":warning: Slow Request Alert",
                    "text": (
                        f"Model `{entry.model_id}` via `{entry.provider_id}` "
                        f"took *{entry.latency_ms:.0f}ms* "
                        f"(threshold: {self._slow_request_threshold_ms}ms)"
                    ),
                    "fields": [
                        {"title": "Capability", "value": entry.capability, "short": True},
                        {"title": "Status", "value": str(entry.status_code), "short": True},
                        {"title": "Tokens", "value": f"{entry.tokens_in} in / {entry.tokens_out} out", "short": True},
                    ],
                    "footer": "ModelMesh Lite",
                    "ts": int(time.time()),
                }
            ]
        }
        self._post_to_slack(payload)

    def close(self) -> None:
        """Close the HTTP client and flush log handlers."""
        self._http_client.close()
        for handler in self._logger.handlers:
            handler.flush()
            handler.close()


# ---------------------------------------------------------------------------
# Usage example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    # Use a dummy Slack URL for the demo (requests will fail gracefully).
    DUMMY_SLACK_URL = "https://example.com/slack-webhook-placeholder"

    # Create a temporary log directory.
    tmp_dir = tempfile.mkdtemp()
    log_path = os.path.join(tmp_dir, "modelmesh.jsonl")

    connector = SlackJsonObservabilityConnector(
        slack_webhook_url=DUMMY_SLACK_URL,
        slack_channel="#modelmesh-alerts",
        slack_event_filter=["model_deactivated", "provider_deactivated"],
        log_directory=tmp_dir,
        max_log_file_size_bytes=1024 * 1024,
        max_log_files=10,
        send_stats_to_slack=False,
        slow_request_threshold_ms=5000,
    )

    try:
        # ----- Events -----
        print("=== Emitting Events ===")

        # This event matches the Slack filter.
        connector.emit(RoutingEvent(
            event_type=EventType.MODEL_DEACTIVATED,
            timestamp=datetime.now(timezone.utc),
            model_id="gpt-4o",
            provider_id="openai",
            pool_id="default",
            metadata={"reason": "error_threshold", "failure_count": 5},
        ))
        print("  Emitted: MODEL_DEACTIVATED (sent to Slack + log)")

        # This event does NOT match the filter -- logged only.
        connector.emit(RoutingEvent(
            event_type=EventType.MODEL_ACTIVATED,
            timestamp=datetime.now(timezone.utc),
            model_id="claude-sonnet",
            provider_id="anthropic",
            pool_id="default",
        ))
        print("  Emitted: MODEL_ACTIVATED (log only, filtered from Slack)")

        connector.emit(RoutingEvent(
            event_type=EventType.MODEL_ROTATED,
            timestamp=datetime.now(timezone.utc),
            model_id="gpt-4o-mini",
            provider_id="openai",
            pool_id="default",
            metadata={"from_model": "gpt-4o", "reason": "cost_savings"},
        ))
        print("  Emitted: MODEL_ROTATED (log only)")

        # ----- Logging -----
        print("\n=== Logging Requests ===")

        for i in range(5):
            connector.log(RequestLogEntry(
                timestamp=datetime.now(timezone.utc),
                model_id="gpt-4o-mini",
                provider_id="openai",
                capability="chat",
                delivery_mode="streaming",
                latency_ms=350.0 + i * 50,
                status_code=200,
                tokens_in=150 + i * 10,
                tokens_out=300 + i * 20,
                cost=0.005 + i * 0.001,
            ))
        print(f"  Logged {5} successful requests")

        # Log a failed request.
        connector.log(RequestLogEntry(
            timestamp=datetime.now(timezone.utc),
            model_id="gpt-4o",
            provider_id="openai",
            capability="chat",
            delivery_mode="sync",
            latency_ms=5000.0,
            status_code=429,
            tokens_in=0,
            tokens_out=0,
            error="Rate limit exceeded",
        ))
        print("  Logged 1 failed request (429)")

        # ----- Statistics -----
        print("\n=== Flushing Statistics ===")

        stats = {
            "openai/gpt-4o-mini": AggregateStats(
                requests_total=150,
                requests_success=148,
                requests_failed=2,
                tokens_in=22500,
                tokens_out=45000,
                cost_total=0.75,
                latency_avg=380.0,
                latency_p95=620.0,
                downtime_total=0.0,
                rotation_events=0,
            ),
            "openai/gpt-4o": AggregateStats(
                requests_total=50,
                requests_success=45,
                requests_failed=5,
                tokens_in=10000,
                tokens_out=20000,
                cost_total=1.50,
                latency_avg=850.0,
                latency_p95=1200.0,
                downtime_total=120.0,
                rotation_events=2,
            ),
            "anthropic/claude-sonnet": AggregateStats(
                requests_total=75,
                requests_success=74,
                requests_failed=1,
                tokens_in=15000,
                tokens_out=30000,
                cost_total=1.05,
                latency_avg=920.0,
                latency_p95=1400.0,
                downtime_total=0.0,
                rotation_events=1,
            ),
        }

        connector.flush(stats)
        print("  Flushed stats for 3 scopes")

        # ----- Show log file contents -----
        log_file = os.path.join(tmp_dir, "modelmesh.jsonl")
        print(f"\n=== Log File: {log_file} ===")
        with open(log_file, "r") as f:
            lines = f.readlines()
        print(f"  Total log lines: {len(lines)}")
        print(f"  First line (prettified):")
        first_record = json.loads(lines[0])
        print(f"    {json.dumps(first_record, indent=2, default=str)}")

    finally:
        connector.close()
        # Clean up temp files.
        for f_name in os.listdir(tmp_dir):
            os.unlink(os.path.join(tmp_dir, f_name))
        os.rmdir(tmp_dir)
        print("\nDone. Temp files cleaned up.")
