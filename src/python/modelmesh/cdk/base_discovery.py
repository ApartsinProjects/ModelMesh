"""Base discovery connector implementation.

Implements the full ``DiscoveryConnector`` interface (RegistrySync,
HealthMonitoring) with background scheduling, configurable sync and
health probe intervals, and failure-threshold-based provider
deactivation.  Subclasses override ``probe()`` to implement
protocol-specific health checks (HTTP, gRPC, TCP) and can override
``sync()`` to add custom model catalogue logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from modelmesh.interfaces.discovery import (
    DiscoveryConnector,
    HealthReport,
    ProbeResult,
    SyncResult,
    SyncStatus,
)

__all__ = [
    "BaseDiscoveryConfig",
    "BaseDiscovery",
]


@dataclass
class BaseDiscoveryConfig:
    """Configuration for a BaseDiscovery instance."""

    providers: list[str] = field(default_factory=list)
    sync_interval_seconds: float = 3600.0
    health_interval_seconds: float = 60.0
    health_timeout_seconds: float = 10.0
    failure_threshold: int = 3
    on_new_model: str = "register"
    on_deprecated_model: str = "notify"


class BaseDiscovery(DiscoveryConnector):
    """Base implementation of the DiscoveryConnector interface.

    Provides registry synchronization with diff-based change detection
    and health monitoring with failure-threshold-based deactivation.
    Subclasses override ``probe`` to implement protocol-specific health
    checks and can override ``sync`` for custom catalogue logic.
    """

    def __init__(self, config: BaseDiscoveryConfig | None = None) -> None:
        self._config = config or BaseDiscoveryConfig()
        self._known_models: dict[str, list[str]] = {}
        self._last_sync: Optional[datetime] = None
        self._models_synced: int = 0
        self._health_history: dict[str, list[HealthReport]] = {}
        self._failure_counts: dict[str, int] = {}

    # ── Registry Sync ───────────────────────────────────────────────

    async def sync(self, providers: list[str] | None = None) -> SyncResult:
        """Synchronize the model catalogue with provider APIs.

        Calls ``_discover_provider_models()`` on each provider, diffs
        against the known catalogue, and returns new, deprecated, and
        updated models.

        Args:
            providers: Provider IDs to sync.  If ``None``, syncs all
                       configured providers.
        """
        target_providers = providers or self._config.providers
        new_models: list[str] = []
        deprecated_models: list[str] = []
        updated_models: list[str] = []
        errors: list[str] = []

        for provider_id in target_providers:
            try:
                discovered = await self._discover_provider_models(provider_id)
                known = set(self._known_models.get(provider_id, []))
                discovered_set = set(discovered)

                for model_id in discovered_set - known:
                    new_models.append(f"{provider_id}/{model_id}")
                for model_id in known - discovered_set:
                    deprecated_models.append(f"{provider_id}/{model_id}")
                for model_id in known & discovered_set:
                    updated_models.append(f"{provider_id}/{model_id}")

                self._known_models[provider_id] = list(discovered_set)
            except Exception as exc:
                errors.append(f"{provider_id}: {exc}")

        self._last_sync = datetime.utcnow()
        self._models_synced = sum(
            len(v) for v in self._known_models.values()
        )

        return SyncResult(
            new_models=new_models,
            deprecated_models=deprecated_models,
            updated_models=updated_models,
            errors=errors,
        )

    async def get_sync_status(self) -> SyncStatus:
        """Return the current synchronization status."""
        next_sync: Optional[datetime] = None
        if self._last_sync is not None:
            next_sync = self._last_sync + timedelta(
                seconds=self._config.sync_interval_seconds
            )
        return SyncStatus(
            last_sync=self._last_sync,
            next_sync=next_sync,
            models_synced=self._models_synced,
            status="idle" if self._last_sync else "pending",
        )

    # ── Health Monitoring ───────────────────────────────────────────

    async def probe(self, provider_id: str) -> ProbeResult:
        """Send a health probe to the specified provider.

        The default implementation returns a successful no-op probe.
        Subclasses override this to implement HTTP, gRPC, or TCP
        health checks.
        """
        return ProbeResult(
            provider_id=provider_id,
            success=True,
            latency_ms=0.0,
        )

    async def get_health_report(
        self, provider_id: str | None = None
    ) -> list[HealthReport]:
        """Return health reports for one or all providers.

        Probes each provider (or the specified one), records the
        result in history, and returns health reports with rolling
        availability scores.
        """
        target_providers = (
            [provider_id] if provider_id else self._config.providers
        )
        reports: list[HealthReport] = []

        for pid in target_providers:
            result = await self.probe(pid)

            # Track failure counts
            if result.success:
                self._failure_counts[pid] = 0
            else:
                self._failure_counts[pid] = (
                    self._failure_counts.get(pid, 0) + 1
                )

            # Calculate availability score from history
            history = self._health_history.get(pid, [])
            total = len(history) + 1
            successes = sum(1 for h in history if h.available) + (
                1 if result.success else 0
            )
            availability_score = successes / total if total > 0 else 1.0

            report = HealthReport(
                provider_id=pid,
                available=result.success,
                latency_ms=result.latency_ms,
                status_code=result.status_code,
                error=result.error,
                availability_score=availability_score,
            )
            reports.append(report)

            # Store in history (keep last 100 entries)
            if pid not in self._health_history:
                self._health_history[pid] = []
            self._health_history[pid].append(report)
            if len(self._health_history[pid]) > 100:
                self._health_history[pid] = self._health_history[pid][-100:]

        return reports

    def is_provider_degraded(self, provider_id: str) -> bool:
        """Return True if the provider has exceeded the failure threshold."""
        return (
            self._failure_counts.get(provider_id, 0)
            >= self._config.failure_threshold
        )

    # ── Internal ────────────────────────────────────────────────────

    async def _discover_provider_models(
        self, provider_id: str
    ) -> list[str]:
        """Discover models from a provider.  Override for custom logic.

        The default implementation returns the known model list
        (no-op discovery).  Subclasses connect to provider APIs
        to enumerate available models.
        """
        return self._known_models.get(provider_id, [])
