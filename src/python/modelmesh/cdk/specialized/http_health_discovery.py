"""HTTP health discovery for the CDK.

Extends BaseDiscovery with real HTTP health probes against provider
endpoints.  Overrides ``probe()`` to send HTTP GET requests to a
configurable health path and evaluate the response status code and
latency.

HTTP transport uses :mod:`urllib.request` from the standard library so
the package has zero external dependencies.
"""
from __future__ import annotations

import asyncio
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_discovery import BaseDiscovery, BaseDiscoveryConfig
from modelmesh.interfaces.discovery import ProbeResult

__all__ = [
    "HttpHealthDiscoveryConfig",
    "HttpHealthDiscovery",
]


@dataclass
class HttpHealthDiscoveryConfig(BaseDiscoveryConfig):
    """Configuration for an HttpHealthDiscovery instance.

    Extends BaseDiscoveryConfig with HTTP health probe settings.

    Attributes:
        health_path: URL path appended to the provider's base URL
            when sending a health probe.  Defaults to ``"/health"``.
        expected_status: HTTP status code that indicates a healthy
            provider.  Defaults to ``200``.
    """

    health_path: str = "/health"
    expected_status: int = 200


class HttpHealthDiscovery(BaseDiscovery):
    """Discovery connector that probes providers via HTTP GET.

    Overrides ``probe`` to send an HTTP GET request to each provider's
    health endpoint and evaluate the response status and latency.
    Uses the provider's registered base URL combined with
    ``health_path``.

    Provider URLs must be registered via :meth:`register_provider_url`
    before probing.

    Usage::

        discovery = HttpHealthDiscovery(HttpHealthDiscoveryConfig(
            providers=["openai", "anthropic"],
            health_path="/v1/models",
            expected_status=200,
            health_interval_seconds=30,
            failure_threshold=3,
        ))
        discovery.register_provider_url("openai", "https://api.openai.com")
        discovery.register_provider_url("anthropic", "https://api.anthropic.com")
    """

    def __init__(self, config: HttpHealthDiscoveryConfig | None = None) -> None:
        super().__init__(config or HttpHealthDiscoveryConfig())
        self._http_config: HttpHealthDiscoveryConfig = (
            config or HttpHealthDiscoveryConfig()
        )
        self._provider_urls: dict[str, str] = {}

    def register_provider_url(self, provider_id: str, base_url: str) -> None:
        """Register a provider's base URL for health probing.

        Args:
            provider_id: The provider identifier (matching the ID
                used in the ``providers`` configuration list).
            base_url: The base URL of the provider API
                (e.g. ``"https://api.openai.com"``).
        """
        self._provider_urls[provider_id] = base_url.rstrip("/")

    async def probe(self, provider_id: str) -> ProbeResult:
        """Send an HTTP GET health probe to the provider.

        Measures response latency and checks the status code against
        ``expected_status``.  The probe is executed in a thread via
        :func:`asyncio.to_thread` to avoid blocking the event loop.

        Args:
            provider_id: The provider to probe.

        Returns:
            A :class:`ProbeResult` with success status, latency,
            status code, and any error message.
        """
        base_url = self._provider_urls.get(provider_id)
        if base_url is None:
            return ProbeResult(
                provider_id=provider_id,
                success=False,
                error=f"No URL registered for provider: {provider_id}",
            )

        url = f"{base_url}{self._http_config.health_path}"
        return await asyncio.to_thread(self._sync_probe, provider_id, url)

    def _sync_probe(self, provider_id: str, url: str) -> ProbeResult:
        """Execute a synchronous HTTP GET health probe.

        Called from async code via :func:`asyncio.to_thread`.

        Args:
            provider_id: The provider identifier.
            url: The full URL to probe.

        Returns:
            A :class:`ProbeResult` with the probe outcome.
        """
        start = time.monotonic()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(
                req, timeout=self._http_config.health_timeout_seconds
            ) as resp:
                elapsed_ms = (time.monotonic() - start) * 1000
                status_code: int = resp.status
                success = status_code == self._http_config.expected_status
                return ProbeResult(
                    provider_id=provider_id,
                    success=success,
                    latency_ms=elapsed_ms,
                    status_code=status_code,
                    error=(
                        None
                        if success
                        else f"Unexpected status: {status_code}"
                    ),
                )
        except urllib.error.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            return ProbeResult(
                provider_id=provider_id,
                success=False,
                latency_ms=elapsed_ms,
                status_code=exc.code,
                error=f"HTTP {exc.code}: {exc.reason}",
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            return ProbeResult(
                provider_id=provider_id,
                success=False,
                latency_ms=elapsed_ms,
                error=str(exc),
            )
