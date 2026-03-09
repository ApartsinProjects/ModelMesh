"""Console observability connector.

Thin wrapper around the CDK's ConsoleObservability that adds a
connector ID for registration in the connector catalogue.

Connector ID: ``modelmesh.console.v1``
"""
from __future__ import annotations

from dataclasses import dataclass

from modelmesh.cdk.specialized.console_observability import (
    ConsoleObservability,
    ConsoleObservabilityConfig,
)

__all__ = [
    "ConsoleConnectorConfig",
    "ConsoleObservabilityConnector",
]


@dataclass
class ConsoleConnectorConfig(ConsoleObservabilityConfig):
    """Configuration for the console observability connector.

    Inherits all settings from ConsoleObservabilityConfig, including
    ``use_color``, ``show_timestamp``, ``prefix``, ``log_level``,
    ``event_filter``, and ``redact_secrets``.
    """

    pass


class ConsoleObservabilityConnector(ConsoleObservability):
    """Pre-shipped observability connector with colored console output.

    Wraps the CDK's ConsoleObservability class and registers it under
    the ``modelmesh.console.v1`` connector ID. This is the default
    observability connector used during development and debugging.

    Connector ID: ``modelmesh.console.v1``

    Usage::

        obs = ConsoleObservabilityConnector(ConsoleConnectorConfig(
            log_level="summary",
            use_color=True,
        ))
        obs.emit(some_event)
    """

    CONNECTOR_ID: str = "modelmesh.console.v1"

    def __init__(self, config: ConsoleConnectorConfig | None = None) -> None:
        if config is None:
            config = ConsoleConnectorConfig()
        super().__init__(config)
