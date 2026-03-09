"""File observability connector.

Thin wrapper around the CDK's FileObservability that adds a connector ID.

Connector ID: ``modelmesh.file.v1``
"""
from __future__ import annotations

from dataclasses import dataclass

from modelmesh.cdk.specialized.file_observability import (
    FileObservability,
    FileObservabilityConfig,
)

__all__ = [
    "FileConnectorConfig",
    "FileObservabilityConnector",
]


@dataclass
class FileConnectorConfig(FileObservabilityConfig):
    """Configuration for the file observability connector."""

    pass


class FileObservabilityConnector(FileObservability):
    """Pre-shipped observability connector that writes to a log file.

    Connector ID: ``modelmesh.file.v1``
    """

    CONNECTOR_ID: str = "modelmesh.file.v1"

    def __init__(self, config: FileConnectorConfig | None = None) -> None:
        if config is None:
            config = FileConnectorConfig()
        super().__init__(config)
