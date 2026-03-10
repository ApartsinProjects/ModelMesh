"""Quickstart: Create a ConsoleObservability, emit an event, log a request, flush stats.

Demonstrates the three core observability operations using the
ConsoleObservability specialized class with colored console output.
"""

from datetime import datetime

from modelmesh.cdk import ConsoleObservability, ConsoleObservabilityConfig
from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    RequestLogEntry,
    RoutingEvent,
)


def main() -> None:
    obs = ConsoleObservability(ConsoleObservabilityConfig(
        log_level="summary",
        redact_secrets=True,
    ))

    # Emit a routing event
    obs.emit(RoutingEvent(
        event_type=EventType.MODEL_ACTIVATED,
        timestamp=datetime.utcnow(),
        model_id="gpt-4o",
        provider_id="openai",
    ))

    # Log a request
    obs.log(RequestLogEntry(
        timestamp=datetime.utcnow(),
        model_id="gpt-4o",
        provider_id="openai",
        capability="generation.text-generation.chat-completion",
        delivery_mode="sync",
        latency_ms=142.5,
        status_code=200,
        tokens_in=50,
        tokens_out=120,
    ))

    # Flush aggregate stats
    obs.flush({
        "gpt-4o": AggregateStats(
            requests_total=100,
            requests_success=95,
            requests_failed=5,
            tokens_in=5000,
            tokens_out=10000,
            cost_total=1.50,
            latency_avg=150.0,
            latency_p95=300.0,
            downtime_total=0.0,
            rotation_events=2,
        ),
    })


if __name__ == "__main__":
    main()
