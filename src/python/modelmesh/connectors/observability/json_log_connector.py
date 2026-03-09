"""JSON Lines observability connector.

Writes traces, events, request logs, and aggregate statistics as
JSON Lines (one JSON object per line) to a file. Supports file
rotation when the file exceeds a configurable size limit.

Connector ID: ``modelmesh.json-log.v1``
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
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
    "JsonLogConnectorConfig",
    "JsonLogConnector",
]


@dataclass
class JsonLogConnectorConfig:
    """Configuration for the JSON Lines observability connector.

    Attributes:
        file_path: Path to the output file. Defaults to
            ``"modelmesh_events.jsonl"``.
        append: Whether to append to an existing file. Defaults to True.
        max_size_mb: Maximum file size in megabytes before rotation.
            0 means no limit. Defaults to 0.
    """

    file_path: str = "modelmesh_events.jsonl"
    append: bool = True
    max_size_mb: float = 0


class JsonLogConnector(ObservabilityConnector):
    """Observability connector that writes JSON Lines to a file.

    Each line is a self-contained JSON object with a ``type`` field
    (``"trace"``, ``"event"``, ``"log"``, or ``"stats"``), a
    ``timestamp``, ``severity``, ``component``, ``message``, and
    a ``metadata`` dict.

    Connector ID: ``modelmesh.json-log.v1``

    Usage::

        obs = JsonLogConnector(JsonLogConnectorConfig(
            file_path="/var/log/modelmesh/events.jsonl",
            max_size_mb=50,
        ))
        obs.trace(some_trace_entry)
    """

    CONNECTOR_ID: str = "modelmesh.json-log.v1"

    def __init__(self, config: JsonLogConnectorConfig | None = None) -> None:
        if config is None:
            config = JsonLogConnectorConfig()
        self._config = config
        self._file = None
        self._open_file()

    def _open_file(self) -> None:
        """Open (or re-open) the output file."""
        mode = "a" if self._config.append else "w"
        parent = os.path.dirname(self._config.file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._file = open(self._config.file_path, mode, encoding="utf-8")

    def _write_line(self, record: dict) -> None:
        """Write a JSON record as a single line to the file."""
        if self._file is None or self._file.closed:
            self._open_file()

        # Check rotation
        if self._config.max_size_mb > 0:
            try:
                max_bytes = int(self._config.max_size_mb * 1024 * 1024)
                pos = self._file.tell()
                if pos >= max_bytes:
                    self._rotate()
            except (OSError, IOError):
                pass

        line = json.dumps(record, default=str)
        self._file.write(line + "\n")
        self._file.flush()

    def _rotate(self) -> None:
        """Rotate the current file by renaming it and opening a new one."""
        if self._file and not self._file.closed:
            self._file.close()

        rotated = self._config.file_path + ".1"
        try:
            if os.path.exists(rotated):
                os.remove(rotated)
            os.rename(self._config.file_path, rotated)
        except OSError:
            pass

        self._open_file()

    # -- ObservabilityConnector interface -----------------------------------

    def trace(self, entry: TraceEntry) -> None:
        """Write a trace entry as a JSON line."""
        self._write_line({
            "type": "trace",
            "timestamp": entry.timestamp.isoformat(),
            "severity": entry.severity.value,
            "component": entry.component,
            "message": entry.message,
            "metadata": entry.metadata or {},
            "error": entry.error,
        })

    def emit(self, event: RoutingEvent) -> None:
        """Write a routing event as a JSON line."""
        self._write_line({
            "type": "event",
            "timestamp": event.timestamp.isoformat(),
            "severity": Severity.INFO.value,
            "component": "router",
            "message": event.event_type.value,
            "metadata": {
                "model_id": event.model_id,
                "provider_id": event.provider_id,
                "pool_id": event.pool_id,
                **(event.metadata or {}),
            },
        })

    def log(self, entry: RequestLogEntry) -> None:
        """Write a request log entry as a JSON line."""
        severity = Severity.ERROR.value if entry.error else Severity.INFO.value
        self._write_line({
            "type": "log",
            "timestamp": entry.timestamp.isoformat(),
            "severity": severity,
            "component": f"provider.{entry.provider_id}",
            "message": f"{entry.capability} {entry.status_code} {entry.latency_ms:.0f}ms",
            "metadata": {
                "model_id": entry.model_id,
                "provider_id": entry.provider_id,
                "capability": entry.capability,
                "delivery_mode": entry.delivery_mode,
                "latency_ms": entry.latency_ms,
                "status_code": entry.status_code,
                "tokens_in": entry.tokens_in,
                "tokens_out": entry.tokens_out,
                "cost": entry.cost,
                "error": entry.error,
            },
        })

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Write aggregate stats as a JSON line per entity."""
        now = datetime.now(tz=timezone.utc).isoformat()
        for entity_id, agg in stats.items():
            self._write_line({
                "type": "stats",
                "timestamp": now,
                "severity": Severity.INFO.value,
                "component": entity_id,
                "message": f"stats flush: {agg.requests_total} requests",
                "metadata": {
                    "requests_total": agg.requests_total,
                    "requests_success": agg.requests_success,
                    "requests_failed": agg.requests_failed,
                    "tokens_in": agg.tokens_in,
                    "tokens_out": agg.tokens_out,
                    "cost_total": agg.cost_total,
                    "latency_avg": agg.latency_avg,
                    "latency_p95": agg.latency_p95,
                    "downtime_total": agg.downtime_total,
                    "rotation_events": agg.rotation_events,
                },
            })

    def close(self) -> None:
        """Close the output file."""
        if self._file and not self._file.closed:
            self._file.close()

    def __del__(self) -> None:
        self.close()
