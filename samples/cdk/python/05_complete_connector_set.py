"""Tutorial 5: AcmeCorp complete connector set -- all 6 connector types.

Demonstrates building a full set of connectors for a hypothetical
"AcmeCorp" integration. Each connector uses a CDK base or specialized
class, showing how all six types work together.

Connector types covered:
1. Provider -- AcmeCorp's OpenAI-compatible inference API
2. Rotation Policy -- threshold-based with AcmeCorp priority list
3. Secret Store -- file-backed store for AcmeCorp credentials
4. Storage -- key-value storage for state persistence
5. Observability -- console output for development debugging
6. Discovery -- HTTP health probes against AcmeCorp endpoints
"""

import asyncio
from datetime import datetime

from modelmesh.cdk import (
    BaseObservabilityConfig,
    BaseProviderConfig,
    BaseRotationPolicyConfig,
    ConsoleObservability,
    FileSecretStore,
    FileSecretStoreConfig,
    HttpHealthDiscovery,
    HttpHealthDiscoveryConfig,
    KeyValueStorage,
    KeyValueStorageConfig,
    OpenAICompatibleProvider,
    ThresholdRotationPolicy,
)
from modelmesh.cdk.helpers import mock_completion_request, mock_model_snapshot
from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    RequestLogEntry,
    RoutingEvent,
)
from modelmesh.interfaces.provider import CompletionRequest, ModelInfo
from modelmesh.interfaces.storage import StorageEntry


# ── 1. Provider ──────────────────────────────────────────────────────

def create_provider() -> OpenAICompatibleProvider:
    """Create an AcmeCorp provider using the OpenAI-compatible format."""
    return OpenAICompatibleProvider(BaseProviderConfig(
        base_url="https://api.acmecorp.example.com",
        api_key="acme-api-key-placeholder",
        timeout=30.0,
        max_retries=3,
        capabilities=["generation.text-generation.chat-completion"],
        models=[
            ModelInfo(
                id="acme-large",
                name="AcmeCorp Large",
                capabilities=["generation.text-generation.chat-completion"],
                features={"tool_calling": True},
                context_window=64_000,
                max_output_tokens=8_192,
            ),
            ModelInfo(
                id="acme-small",
                name="AcmeCorp Small",
                capabilities=["generation.text-generation.chat-completion"],
                context_window=16_000,
                max_output_tokens=4_096,
            ),
        ],
    ))


# ── 2. Rotation Policy ──────────────────────────────────────────────

def create_rotation_policy() -> ThresholdRotationPolicy:
    """Create a threshold-based rotation policy with AcmeCorp priority."""
    return ThresholdRotationPolicy(BaseRotationPolicyConfig(
        retry_limit=5,
        error_rate_threshold=0.3,
        cooldown_seconds=120,
        budget_limit=50.0,
        model_priority=["acme-large", "acme-small"],
    ))


# ── 3. Secret Store ─────────────────────────────────────────────────

def create_secret_store() -> FileSecretStore:
    """Create a file-backed secret store for AcmeCorp credentials."""
    return FileSecretStore(FileSecretStoreConfig(
        file_path=".env",
        file_format="dotenv",
        cache_ttl_ms=120_000,
        fail_on_missing=False,
    ))


# ── 4. Storage ───────────────────────────────────────────────────────

def create_storage() -> KeyValueStorage:
    """Create a key-value storage for AcmeCorp state persistence."""
    return KeyValueStorage(KeyValueStorageConfig(
        backend="memory",
        format="json",
        locking_enabled=True,
    ))


# ── 5. Observability ────────────────────────────────────────────────

def create_observability() -> ConsoleObservability:
    """Create a console observability connector for development."""
    return ConsoleObservability(BaseObservabilityConfig(
        log_level="summary",
        redact_secrets=True,
        scopes=["model", "provider"],
    ))


# ── 6. Discovery ────────────────────────────────────────────────────

def create_discovery() -> HttpHealthDiscovery:
    """Create an HTTP health discovery connector for AcmeCorp."""
    discovery = HttpHealthDiscovery(HttpHealthDiscoveryConfig(
        providers=["acmecorp"],
        health_path="/health",
        expected_status=200,
        health_interval_seconds=30,
        failure_threshold=3,
    ))
    discovery.register_provider_url(
        "acmecorp", "https://api.acmecorp.example.com"
    )
    return discovery


# ── Main: Wire everything together ──────────────────────────────────

async def main() -> None:
    provider = create_provider()
    policy = create_rotation_policy()
    secret_store = create_secret_store()
    storage = create_storage()
    obs = create_observability()
    discovery = create_discovery()

    print("=== AcmeCorp Connector Set ===\n")

    # Provider: list models
    models = await provider.list_models()
    print(f"Provider models: {[m.id for m in models]}")

    # Rotation: test deactivation
    snapshot = mock_model_snapshot(
        model_id="acme-large",
        provider_id="acmecorp",
        failure_count=6,
        error_rate=0.4,
    )
    print(f"Should deactivate acme-large? {policy.should_deactivate(snapshot)}")

    # Storage: save and load state
    entry = StorageEntry(
        key="acmecorp/state",
        data=b'{"last_rotation": "2024-01-01T00:00:00Z"}',
        metadata={"connector": "acmecorp"},
    )
    await storage.save("acmecorp/state", entry)
    loaded = await storage.load("acmecorp/state")
    print(f"Storage load: {loaded.data.decode('utf-8')}")

    # Observability: emit event and log request
    obs.emit(RoutingEvent(
        event_type=EventType.MODEL_ACTIVATED,
        timestamp=datetime.utcnow(),
        model_id="acme-large",
        provider_id="acmecorp",
    ))
    obs.log(RequestLogEntry(
        timestamp=datetime.utcnow(),
        model_id="acme-large",
        provider_id="acmecorp",
        capability="generation.text-generation.chat-completion",
        delivery_mode="sync",
        latency_ms=200.0,
        status_code=200,
        tokens_in=100,
        tokens_out=250,
    ))

    # Discovery: probe health
    result = await discovery.probe("acmecorp")
    print(f"\nHealth probe: success={result.success}")

    # Clean up
    await provider.close()
    await discovery.close()

    print("\nAll 6 connectors created and exercised successfully.")


if __name__ == "__main__":
    asyncio.run(main())
