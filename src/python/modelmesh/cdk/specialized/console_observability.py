"""Console observability for the CDK.

Extends BaseObservability with ANSI-colored console output for
development and debugging. Events, logs, and statistics are printed
to stdout with color coding by type.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from modelmesh.cdk.base_observability import (
    BaseObservability,
    BaseObservabilityConfig,
)
from modelmesh.interfaces.observability import (
    AggregateStats,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    TraceEntry,
)

__all__ = [
    "ConsoleObservabilityConfig",
    "ConsoleObservability",
]


# ANSI color codes
class _Colors:
    """ANSI escape codes for colored terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


# Event type to color mapping
_EVENT_COLORS: dict[str, str] = {
    "model_activated": _Colors.GREEN,
    "provider_recovered": _Colors.GREEN,
    "model_deactivated": _Colors.RED,
    "provider_deactivated": _Colors.RED,
    "model_rotated": _Colors.YELLOW,
    "provider_health_changed": _Colors.YELLOW,
    "pool_membership_changed": _Colors.CYAN,
    "discovery_models_updated": _Colors.BLUE,
}

# Severity level to color mapping
_SEVERITY_COLORS: dict[str, str] = {
    "debug": _Colors.DIM,
    "info": _Colors.BLUE,
    "warning": _Colors.YELLOW,
    "error": _Colors.RED,
    "critical": _Colors.BG_RED + _Colors.WHITE,
}


@dataclass
class ConsoleObservabilityConfig(BaseObservabilityConfig):
    """Configuration for console observability output.

    Attributes:
        use_color: Whether to use ANSI color codes. Defaults to True.
            Set to False for environments that do not support ANSI
            escape sequences.
        show_timestamp: Whether to include timestamps in output.
        prefix: Optional string prefix for all output lines.
    """

    use_color: bool = True
    show_timestamp: bool = True
    prefix: str = "[ModelMesh]"


class ConsoleObservability(BaseObservability):
    """Observability connector with ANSI-colored console output.

    Designed for development and debugging. Prints routing events,
    request/response logs, and aggregate statistics to stdout with
    color coding:

    - **Green**: activation and recovery events
    - **Red**: deactivation and error events
    - **Yellow**: rotation and health-change events
    - **Cyan**: pool membership changes
    - **Blue**: discovery updates

    Usage::

        obs = ConsoleObservability(ConsoleObservabilityConfig(
            log_level="summary",
            use_color=True,
        ))
        obs.emit(some_event)
    """

    def __init__(self, config: ConsoleObservabilityConfig) -> None:
        super().__init__(config)
        self._console_config = config

    def _write_event(self, event: RoutingEvent) -> None:
        """Print a colored event line to stdout.

        Color is determined by the event type: green for activation,
        red for deactivation, yellow for rotation.
        """
        event_name = event.event_type.value
        color = _EVENT_COLORS.get(event_name, _Colors.WHITE)

        parts: list[str] = []

        if self._console_config.show_timestamp:
            ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            parts.append(self._dim(ts))

        if self._console_config.prefix:
            parts.append(self._console_config.prefix)

        parts.append(self._colorize(f"EVENT:{event_name}", color, bold=True))

        details: list[str] = []
        if event.model_id:
            details.append(f"model={event.model_id}")
        if event.provider_id:
            details.append(f"provider={event.provider_id}")
        if event.pool_id:
            details.append(f"pool={event.pool_id}")
        if event.metadata:
            for k, v in event.metadata.items():
                details.append(f"{k}={v}")

        if details:
            parts.append(self._dim(" ".join(details)))

        print(" ".join(parts), file=sys.stdout, flush=True)

    def _write_log(self, entry: RequestLogEntry) -> None:
        """Print request/response metadata to stdout.

        Includes model ID, provider ID, status code, and latency.
        Additional fields are shown based on the configured log level.
        """
        parts: list[str] = []

        if self._console_config.show_timestamp:
            ts = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
            parts.append(self._dim(ts))

        if self._console_config.prefix:
            parts.append(self._console_config.prefix)

        # Color status code
        if entry.status_code >= 500:
            status_color = _Colors.RED
        elif entry.status_code >= 400:
            status_color = _Colors.YELLOW
        else:
            status_color = _Colors.GREEN

        parts.append(self._colorize(f"LOG", _Colors.BLUE, bold=True))
        parts.append(
            self._colorize(str(entry.status_code), status_color)
        )
        parts.append(f"{entry.latency_ms:.0f}ms")
        parts.append(f"model={entry.model_id}")
        parts.append(f"provider={entry.provider_id}")

        if self._console_config.log_level in ("summary", "full"):
            parts.append(f"in={entry.tokens_in}")
            parts.append(f"out={entry.tokens_out}")
            if entry.cost is not None:
                parts.append(f"cost=${entry.cost:.6f}")

        if self._console_config.log_level == "full" and entry.error:
            parts.append(self._colorize(f"error={entry.error}", _Colors.RED))

        print(" ".join(parts), file=sys.stdout, flush=True)

    def _write_stats(self, stats: dict[str, AggregateStats]) -> None:
        """Print a formatted statistics table to stdout.

        Displays aggregate metrics for each scope (model, provider,
        or pool) in a tabular format.
        """
        if not stats:
            return

        # Header
        header = (
            f"{'Scope':<30} {'Reqs':>8} {'OK':>8} {'Fail':>8} "
            f"{'Tok In':>10} {'Tok Out':>10} {'Cost':>10} "
            f"{'Avg ms':>8} {'P95 ms':>8} {'Rotations':>10}"
        )

        separator = "-" * len(header)

        parts: list[str] = []
        if self._console_config.prefix:
            parts.append(self._console_config.prefix)
        parts.append(
            self._colorize("STATS", _Colors.MAGENTA, bold=True)
        )

        print(" ".join(parts), file=sys.stdout, flush=True)
        print(
            self._colorize(separator, _Colors.DIM),
            file=sys.stdout,
            flush=True,
        )
        print(
            self._colorize(header, _Colors.BOLD),
            file=sys.stdout,
            flush=True,
        )
        print(
            self._colorize(separator, _Colors.DIM),
            file=sys.stdout,
            flush=True,
        )

        for scope_id, agg in stats.items():
            row = (
                f"{scope_id:<30} {agg.requests_total:>8} "
                f"{agg.requests_success:>8} {agg.requests_failed:>8} "
                f"{agg.tokens_in:>10} {agg.tokens_out:>10} "
                f"{agg.cost_total:>10.4f} "
                f"{agg.latency_avg:>8.1f} {agg.latency_p95:>8.1f} "
                f"{agg.rotation_events:>10}"
            )
            print(row, file=sys.stdout, flush=True)

        print(
            self._colorize(separator, _Colors.DIM),
            file=sys.stdout,
            flush=True,
        )

    # -- BaseObservability overrides -----------------------------------------

    def emit(self, event: RoutingEvent) -> None:
        """Emit a routing event with colored console output."""
        if self._config.event_filter:
            if event.event_type.value not in self._config.event_filter:
                return
        self._write_event(event)

    def log(self, entry: RequestLogEntry) -> None:
        """Record a request/response log entry with colored output."""
        self._write_log(entry)

    def flush(self, stats: dict[str, AggregateStats]) -> None:
        """Flush aggregate statistics as a formatted table."""
        self._write_stats(stats)

    def trace(self, entry: TraceEntry) -> None:
        """Print a colored trace entry to stdout."""
        # Apply severity filter from base config
        from modelmesh.cdk.base_observability import BaseObservability

        min_level = BaseObservability._SEVERITY_ORDER.get(
            Severity(self._config.min_severity), 1
        )
        entry_level = BaseObservability._SEVERITY_ORDER.get(entry.severity, 0)
        if entry_level < min_level:
            return

        parts: list[str] = []
        if self._console_config.show_timestamp:
            ts = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
            parts.append(self._dim(ts))
        if self._console_config.prefix:
            parts.append(self._console_config.prefix)

        sev_color = _SEVERITY_COLORS.get(entry.severity.value, _Colors.WHITE)
        parts.append(
            self._colorize(
                f"TRACE:{entry.severity.value.upper()}", sev_color, bold=True
            )
        )
        parts.append(self._dim(f"[{entry.component}]"))
        parts.append(entry.message)

        if entry.error:
            parts.append(self._colorize(f"error={entry.error}", _Colors.RED))
        if entry.metadata:
            for k, v in entry.metadata.items():
                parts.append(self._dim(f"{k}={v}"))

        print(" ".join(parts), file=sys.stdout, flush=True)

    def _write(self, line: str) -> None:
        """Write a raw formatted line to stdout.

        Used by the parent class for JSON-formatted fallback output.
        """
        print(line, file=sys.stdout, flush=True)

    # -- Color Helpers -------------------------------------------------------

    def _colorize(
        self, text: str, color: str, bold: bool = False
    ) -> str:
        """Wrap text in ANSI color codes if color is enabled."""
        if not self._console_config.use_color:
            return text
        prefix = _Colors.BOLD + color if bold else color
        return f"{prefix}{text}{_Colors.RESET}"

    def _dim(self, text: str) -> str:
        """Wrap text in ANSI dim code if color is enabled."""
        if not self._console_config.use_color:
            return text
        return f"{_Colors.DIM}{text}{_Colors.RESET}"
