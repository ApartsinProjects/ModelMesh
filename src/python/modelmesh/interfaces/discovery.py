"""Discovery connector interface and associated data types.

Defines the abstract DiscoveryConnector interface for keeping the model
catalogue accurate and provider health visible without manual
intervention. Discovery connectors run as background processes on
configurable schedules.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SyncAction(Enum):
    """Action to take when a new model is discovered during sync."""

    REGISTER = "register"
    NOTIFY = "notify"
    IGNORE = "ignore"


class DeprecationAction(Enum):
    """Action to take when a model is detected as deprecated."""

    DEACTIVATE = "deactivate"
    NOTIFY = "notify"
    IGNORE = "ignore"


@dataclass
class SyncResult:
    """Outcome of a registry synchronization run."""

    new_models: list[str]
    deprecated_models: list[str]
    updated_models: list[str]
    errors: list[str]


@dataclass
class SyncStatus:
    """Current status of the registry synchronization process."""

    last_sync: Optional[datetime] = None
    next_sync: Optional[datetime] = None
    models_synced: int = 0
    status: str = "idle"


@dataclass
class HealthReport:
    """Health assessment for a single provider over a monitoring window."""

    provider_id: str
    available: bool
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    availability_score: float = 1.0
    timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class ProbeResult:
    """Result of a single health probe against a provider."""

    provider_id: str
    success: bool
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None


class RegistrySync(ABC):
    """Synchronize the local model catalogue with provider APIs."""

    @abstractmethod
    async def sync(self, providers: list[str] | None = None) -> SyncResult:
        """Synchronize the model catalogue with the given providers."""
        ...

    @abstractmethod
    async def get_sync_status(self) -> SyncStatus:
        """Return the current synchronization status."""
        ...


class HealthMonitoring(ABC):
    """Probe provider availability and performance."""

    @abstractmethod
    async def probe(self, provider_id: str) -> ProbeResult:
        """Send a health probe to the specified provider."""
        ...

    @abstractmethod
    async def get_health_report(
        self, provider_id: str | None = None
    ) -> list[HealthReport]:
        """Return health reports for one or all providers."""
        ...


class DiscoveryConnector(RegistrySync, HealthMonitoring):
    """Full discovery connector combining Registry Sync and Health Monitoring."""

    pass


__all__ = [
    "SyncAction",
    "DeprecationAction",
    "SyncResult",
    "SyncStatus",
    "HealthReport",
    "ProbeResult",
    "RegistrySync",
    "HealthMonitoring",
    "DiscoveryConnector",
]
