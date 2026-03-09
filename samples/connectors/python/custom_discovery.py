"""
Custom Discovery Connector -- YAML Registry + HTTP Health Probing

Demonstrates how to implement a custom discovery connector for ModelMesh Lite
that synchronizes models from a YAML registry file and monitors provider
health via HTTP pings with rolling availability score calculation.

This is useful for organizations that manage a curated model catalogue in
version control (e.g., a Git-tracked YAML file) and need lightweight health
monitoring without a dedicated observability platform.

See: docs/interfaces/Discovery.md

Requirements:
    pip install httpx pyyaml
"""
# For a simpler CDK-based approach, see samples/cdk/python/

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
import yaml


# ---------------------------------------------------------------------------
# Supporting types (from Discovery interface)
# ---------------------------------------------------------------------------

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
    timestamp: datetime = None

    def __post_init__(self):
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


# ---------------------------------------------------------------------------
# Interface ABCs (from Discovery interface)
# ---------------------------------------------------------------------------

class RegistrySync(ABC):
    @abstractmethod
    async def sync(self, providers: list[str] | None = None) -> SyncResult: ...

    @abstractmethod
    async def get_sync_status(self) -> SyncStatus: ...


class HealthMonitoring(ABC):
    @abstractmethod
    async def probe(self, provider_id: str) -> ProbeResult: ...

    @abstractmethod
    async def get_health_report(
        self, provider_id: str | None = None
    ) -> list[HealthReport]: ...


class DiscoveryConnector(RegistrySync, HealthMonitoring):
    """Full discovery connector combining Registry Sync and Health Monitoring."""
    pass


# ---------------------------------------------------------------------------
# YAML registry data types
# ---------------------------------------------------------------------------

@dataclass
class ModelPricing:
    """Pricing information for a model."""
    input_per_token: float
    output_per_token: float
    per_request: Optional[float] = None


@dataclass
class RegistryModel:
    """A model definition as represented in the YAML registry file."""
    id: str
    name: str
    provider: str
    capabilities: list[str]
    context_window: int
    max_output_tokens: int
    status: str = "active"  # "active", "deprecated", or "preview"
    pricing: Optional[ModelPricing] = None


@dataclass
class ProviderEndpoint:
    """Health check endpoint for a provider in the YAML registry."""
    id: str
    name: str
    base_url: str
    health_endpoint: str
    health_method: str = "GET"
    health_expected_status: int = 200


# ---------------------------------------------------------------------------
# Probe history for rolling availability score
# ---------------------------------------------------------------------------

@dataclass
class _ProbeHistory:
    """Sliding window of probe results for availability calculation."""
    window_size: int = 20
    results: deque = field(default_factory=lambda: deque(maxlen=20))

    def record(self, success: bool) -> None:
        """Record a probe result (True=success, False=failure)."""
        self.results.append(success)

    @property
    def availability_score(self) -> float:
        """Calculate rolling availability as the fraction of successful probes."""
        if not self.results:
            return 1.0  # Assume available until proven otherwise.
        return sum(self.results) / len(self.results)


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

class YamlDiscoveryConnector(DiscoveryConnector):
    """Discovery connector that syncs models from a YAML file and probes
    provider health via HTTP.

    The YAML registry file contains two sections:
      - ``models``: A list of model definitions with provider associations.
      - ``providers``: A list of provider health check endpoints.

    On each sync, the connector compares the YAML registry against the
    current known model set to detect new, deprecated, and updated models.

    Health probes send HTTP GET requests to each provider's health endpoint
    and maintain a rolling window of results to compute availability scores.

    YAML registry file format (config/model-registry.yaml):

        version: 1

        providers:
          - id: openai-primary
            name: OpenAI (Primary Key)
            base_url: "https://api.openai.com"
            health_endpoint: "/v1/models"
            health_method: GET
            health_expected_status: 200
            models:
              - gpt-4o
              - gpt-4o-mini

          - id: anthropic-primary
            name: Anthropic (Primary Key)
            base_url: "https://api.anthropic.com"
            health_endpoint: "/v1/messages"
            health_method: GET
            health_expected_status: 405
            models:
              - claude-sonnet-4-20250514

        models:
          - id: "gpt-4o"
            name: "GPT-4o"
            provider: "openai-primary"
            capabilities: ["generation.text-generation.chat-completion"]
            context_window: 128000
            max_output_tokens: 16384
            status: active
            pricing:
              input_per_token: 0.0000025
              output_per_token: 0.00001

          - id: "gpt-4o-mini"
            name: "GPT-4o Mini"
            provider: "openai-primary"
            capabilities: ["generation.text-generation.chat-completion"]
            context_window: 128000
            max_output_tokens: 16384
            status: active
            pricing:
              input_per_token: 0.00000015
              output_per_token: 0.0000006

          - id: "claude-sonnet-4-20250514"
            name: "Claude Sonnet 4"
            provider: "anthropic-primary"
            capabilities: ["generation.text-generation.chat-completion"]
            context_window: 200000
            max_output_tokens: 8192
            status: active
            pricing:
              input_per_token: 0.000003
              output_per_token: 0.000015

          - id: "gpt-3.5-turbo"
            name: "GPT-3.5 Turbo"
            provider: "openai-primary"
            capabilities: ["generation.text-generation.chat-completion"]
            context_window: 16385
            max_output_tokens: 4096
            status: deprecated

    Configuration example (YAML -- modelmesh config):

        discovery:
          connector: custom
          connector_class: YamlDiscoveryConnector
          config:
            registry_file_path: "./config/model-registry.yaml"
            sync_interval_ms: 3600000
            probe_timeout_ms: 10000
            probe_history_size: 20
            failure_threshold: 3
            on_new_model: register
            on_deprecated_model: notify
          sync:
            enabled: true
            interval: 1h
            auto_register: true
          health:
            enabled: true
            interval: 60s
            timeout: 10s
            failure_threshold: 3
    """

    def __init__(
        self,
        registry_file_path: str | Path,
        sync_interval_ms: int = 3_600_000,
        probe_timeout_ms: int = 10_000,
        probe_history_size: int = 20,
        failure_threshold: int = 3,
        on_new_model: str = "register",
        on_deprecated_model: str = "notify",
    ) -> None:
        """Initialize the YAML registry discovery connector.

        Args:
            registry_file_path: Path to the YAML registry file.
            sync_interval_ms: How often to re-sync the registry (in ms).
            probe_timeout_ms: Health probe timeout in milliseconds.
            probe_history_size: Number of recent probe results to keep.
            failure_threshold: Consecutive failures before marking unavailable.
            on_new_model: Action when a new model is found: "register", "notify",
                          or "ignore".
            on_deprecated_model: Action when a model is deprecated: "deactivate",
                                 "notify", or "ignore".
        """
        self._registry_path = Path(registry_file_path)
        self._sync_interval_ms = sync_interval_ms
        self._probe_timeout = probe_timeout_ms / 1000.0
        self._probe_history_size = probe_history_size
        self._failure_threshold = failure_threshold
        self._on_new_model = SyncAction(on_new_model)
        self._on_deprecated_model = DeprecationAction(on_deprecated_model)

        # Internal state: known models from the last sync.
        self._known_models: dict[str, RegistryModel] = {}

        # Provider health check endpoints (loaded from the registry).
        self._provider_endpoints: dict[str, ProviderEndpoint] = {}

        # Probe history per provider for rolling availability scores.
        self._probe_history: dict[str, _ProbeHistory] = {}

        # Last probe results for health reports.
        self._last_probe: dict[str, ProbeResult] = {}

        # Sync status tracking.
        self._sync_status = SyncStatus()

        # HTTP client for health probes.
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._probe_timeout),
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # RegistrySync
    # ------------------------------------------------------------------

    async def sync(self, providers: list[str] | None = None) -> SyncResult:
        """Synchronize the model catalogue with the YAML registry file.

        Reads the registry file, compares against the known model set,
        and returns a SyncResult describing changes.

        Args:
            providers: If provided, only sync models belonging to these
                       providers. If None, sync all.
        """
        self._sync_status.status = "syncing"

        try:
            registry_data = self._load_registry()
        except Exception as exc:
            self._sync_status.status = "error"
            return SyncResult(
                new_models=[],
                deprecated_models=[],
                updated_models=[],
                errors=[f"Failed to load registry: {exc}"],
            )

        # Parse models from the registry.
        registry_models: dict[str, RegistryModel] = {}
        for m in registry_data.get("models", []):
            pricing = None
            if m.get("pricing"):
                pricing = ModelPricing(
                    input_per_token=m["pricing"].get("input_per_token", 0),
                    output_per_token=m["pricing"].get("output_per_token", 0),
                    per_request=m["pricing"].get("per_request"),
                )

            model = RegistryModel(
                id=m["id"],
                name=m.get("name", m["id"]),
                provider=m["provider"],
                capabilities=m.get("capabilities", []),
                context_window=m.get("context_window", 4096),
                max_output_tokens=m.get("max_output_tokens", 2048),
                status=m.get("status", "active"),
                pricing=pricing,
            )

            # Filter by provider if requested.
            if providers and model.provider not in providers:
                continue

            registry_models[model.id] = model

        # Parse provider endpoints.
        for p in registry_data.get("providers", []):
            base_url = p["base_url"].rstrip("/")
            health_endpoint = p["health_endpoint"]
            if not health_endpoint.startswith("/"):
                health_endpoint = "/" + health_endpoint

            endpoint = ProviderEndpoint(
                id=p["id"],
                name=p.get("name", p["id"]),
                base_url=base_url,
                health_endpoint=health_endpoint,
                health_method=p.get("health_method", "GET"),
                health_expected_status=p.get("health_expected_status", 200),
            )
            self._provider_endpoints[endpoint.id] = endpoint

            # Initialize probe history if not already tracked.
            if endpoint.id not in self._probe_history:
                self._probe_history[endpoint.id] = _ProbeHistory(
                    window_size=self._probe_history_size
                )

        # Compare against known models.
        new_models: list[str] = []
        deprecated_models: list[str] = []
        updated_models: list[str] = []
        errors: list[str] = []

        # Detect new and updated models.
        for model_id, model in registry_models.items():
            if model.status == "deprecated":
                # Model is marked deprecated in the registry.
                if model_id in self._known_models:
                    deprecated_models.append(model_id)
                continue

            if model_id not in self._known_models:
                new_models.append(model_id)
            else:
                # Check if any attributes changed.
                old = self._known_models[model_id]
                if (
                    old.status != model.status
                    or old.context_window != model.context_window
                    or old.max_output_tokens != model.max_output_tokens
                    or old.capabilities != model.capabilities
                    or old.pricing != model.pricing
                ):
                    updated_models.append(model_id)

        # Detect models removed from the registry.
        for model_id in self._known_models:
            if model_id not in registry_models:
                deprecated_models.append(model_id)

        # Update known models.
        self._known_models = {
            mid: m for mid, m in registry_models.items()
            if m.status != "deprecated"
        }

        # Update sync status.
        self._sync_status.last_sync = datetime.now(timezone.utc)
        self._sync_status.models_synced = len(self._known_models)
        self._sync_status.status = "idle"

        return SyncResult(
            new_models=new_models,
            deprecated_models=deprecated_models,
            updated_models=updated_models,
            errors=errors,
        )

    async def get_sync_status(self) -> SyncStatus:
        """Return the current synchronization status."""
        return self._sync_status

    # ------------------------------------------------------------------
    # HealthMonitoring
    # ------------------------------------------------------------------

    async def probe(self, provider_id: str) -> ProbeResult:
        """Send a health probe to the specified provider.

        Makes an HTTP GET request to the provider's health endpoint and
        records the result in the rolling availability window.
        """
        endpoint = self._provider_endpoints.get(provider_id)
        if endpoint is None:
            result = ProbeResult(
                provider_id=provider_id,
                success=False,
                error=f"No health endpoint configured for provider '{provider_id}'",
            )
            self._last_probe[provider_id] = result
            return result

        start_time = time.monotonic()

        try:
            health_url = endpoint.base_url + endpoint.health_endpoint
            method = endpoint.health_method.upper()
            response = await self._http_client.request(method, health_url)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            # Consider the probe successful if the status code matches
            # the expected value. Some APIs return 401 without auth but
            # that still proves the API is reachable.
            is_success = response.status_code == endpoint.health_expected_status

            result = ProbeResult(
                provider_id=provider_id,
                success=is_success,
                latency_ms=round(elapsed_ms, 2),
                status_code=response.status_code,
                error=None if is_success else f"Unexpected status {response.status_code}",
            )

        except httpx.TimeoutException:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            result = ProbeResult(
                provider_id=provider_id,
                success=False,
                latency_ms=round(elapsed_ms, 2),
                error="Health probe timed out",
            )

        except httpx.ConnectError as exc:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            result = ProbeResult(
                provider_id=provider_id,
                success=False,
                latency_ms=round(elapsed_ms, 2),
                error=f"Connection failed: {exc}",
            )

        except httpx.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            result = ProbeResult(
                provider_id=provider_id,
                success=False,
                latency_ms=round(elapsed_ms, 2),
                error=f"HTTP error: {exc}",
            )

        # Record in the rolling window.
        history = self._probe_history.get(provider_id)
        if history is None:
            history = _ProbeHistory(window_size=self._probe_history_size)
            self._probe_history[provider_id] = history
        history.record(result.success)

        # Store last probe for health reports.
        self._last_probe[provider_id] = result

        return result

    async def get_health_report(
        self, provider_id: str | None = None
    ) -> list[HealthReport]:
        """Return health reports for one or all providers.

        Each report includes the last probe result and the rolling
        availability score computed from the probe history window.
        """
        if provider_id is not None:
            return [self._build_health_report(provider_id)]

        # Return reports for all known providers.
        reports = []
        for pid in self._provider_endpoints:
            reports.append(self._build_health_report(pid))
        return reports

    def _build_health_report(self, provider_id: str) -> HealthReport:
        """Build a HealthReport from the latest probe and history."""
        last = self._last_probe.get(provider_id)
        history = self._probe_history.get(provider_id)

        if last is None:
            # No probes have been run yet for this provider.
            return HealthReport(
                provider_id=provider_id,
                available=True,  # Optimistic default.
                availability_score=1.0,
            )

        availability = history.availability_score if history else 1.0

        return HealthReport(
            provider_id=provider_id,
            available=last.success,
            latency_ms=last.latency_ms,
            status_code=last.status_code,
            error=last.error,
            availability_score=round(availability, 4),
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_registry(self) -> dict:
        """Read and parse the YAML registry file."""
        if not self._registry_path.exists():
            raise FileNotFoundError(
                f"Registry file not found: {self._registry_path}"
            )
        with open(self._registry_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http_client.aclose()


# ---------------------------------------------------------------------------
# Usage example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import tempfile
    import os

    # Create a sample YAML registry file for the demo.
    SAMPLE_REGISTRY = """
version: 1

providers:
  - id: openai-primary
    name: OpenAI (Primary Key)
    base_url: "https://api.openai.com"
    health_endpoint: "/v1/models"
    health_method: GET
    health_expected_status: 200
    models:
      - gpt-4o
      - gpt-4o-mini

  - id: anthropic-primary
    name: Anthropic (Primary Key)
    base_url: "https://api.anthropic.com"
    health_endpoint: "/v1/messages"
    health_method: GET
    health_expected_status: 405
    models:
      - claude-sonnet-4-20250514

models:
  - id: "gpt-4o"
    name: "GPT-4o"
    provider: "openai-primary"
    capabilities: ["generation.text-generation.chat-completion"]
    context_window: 128000
    max_output_tokens: 16384
    status: active
    pricing:
      input_per_token: 0.0000025
      output_per_token: 0.00001

  - id: "gpt-4o-mini"
    name: "GPT-4o Mini"
    provider: "openai-primary"
    capabilities: ["generation.text-generation.chat-completion"]
    context_window: 128000
    max_output_tokens: 16384
    status: active
    pricing:
      input_per_token: 0.00000015
      output_per_token: 0.0000006

  - id: "claude-sonnet-4-20250514"
    name: "Claude Sonnet 4"
    provider: "anthropic-primary"
    capabilities: ["generation.text-generation.chat-completion"]
    context_window: 200000
    max_output_tokens: 8192
    status: active
    pricing:
      input_per_token: 0.000003
      output_per_token: 0.000015

  - id: "gpt-3.5-turbo"
    name: "GPT-3.5 Turbo"
    provider: "openai-primary"
    capabilities: ["generation.text-generation.chat-completion"]
    context_window: 16385
    max_output_tokens: 4096
    status: deprecated
"""

    async def main() -> None:
        # Write sample registry to a temp file.
        tmp_dir = tempfile.mkdtemp()
        registry_path = os.path.join(tmp_dir, "models_registry.yaml")
        with open(registry_path, "w") as f:
            f.write(SAMPLE_REGISTRY)

        connector = YamlDiscoveryConnector(
            registry_file_path=registry_path,
            probe_timeout_ms=10_000,
            probe_history_size=10,
        )

        try:
            # ----- Registry Sync -----
            print("=== Initial Sync ===")
            result = await connector.sync()
            print(f"  New models:        {result.new_models}")
            print(f"  Deprecated models: {result.deprecated_models}")
            print(f"  Updated models:    {result.updated_models}")
            print(f"  Errors:            {result.errors}")

            status = await connector.get_sync_status()
            print(f"\n  Sync status: {status.status}")
            print(f"  Models synced: {status.models_synced}")
            print(f"  Last sync: {status.last_sync}")

            # Second sync with no changes should find nothing new.
            print("\n=== Second Sync (no changes) ===")
            result2 = await connector.sync()
            print(f"  New models:        {result2.new_models}")
            print(f"  Deprecated models: {result2.deprecated_models}")
            print(f"  Updated models:    {result2.updated_models}")

            # ----- Health Probing -----
            print("\n=== Health Probes ===")

            # Probe each provider. These will make real HTTP requests.
            for provider_id in ["openai", "anthropic"]:
                probe_result = await connector.probe(provider_id)
                print(
                    f"  {provider_id}: success={probe_result.success}, "
                    f"latency={probe_result.latency_ms}ms, "
                    f"status={probe_result.status_code}, "
                    f"error={probe_result.error}"
                )

            # Run a few more probes to build up the rolling window.
            print("\n  Running additional probes for rolling score...")
            for _ in range(4):
                for provider_id in ["openai", "anthropic"]:
                    await connector.probe(provider_id)

            # ----- Health Reports -----
            print("\n=== Health Reports ===")
            reports = await connector.get_health_report()
            for report in reports:
                print(
                    f"  {report.provider_id}: "
                    f"available={report.available}, "
                    f"score={report.availability_score:.2f}, "
                    f"latency={report.latency_ms}ms"
                )

            # Get a report for a single provider.
            print("\n=== Single Provider Report ===")
            single = await connector.get_health_report("openai")
            report = single[0]
            print(f"  Provider: {report.provider_id}")
            print(f"  Available: {report.available}")
            print(f"  Availability score: {report.availability_score:.4f}")
            print(f"  Last latency: {report.latency_ms}ms")
            print(f"  Last status code: {report.status_code}")
            print(f"  Timestamp: {report.timestamp}")

            # Simulate a sync with a provider filter.
            print("\n=== Filtered Sync (anthropic only) ===")
            result3 = await connector.sync(providers=["anthropic"])
            print(f"  Models synced: {(await connector.get_sync_status()).models_synced}")
            print(f"  (Only Anthropic models are in scope)")

        finally:
            await connector.close()
            # Clean up.
            os.unlink(registry_path)
            os.rmdir(tmp_dir)
            print("\nDone. Temp files cleaned up.")

    asyncio.run(main())
