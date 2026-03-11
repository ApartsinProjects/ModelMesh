"""CDK specialized classes -- pre-configured for common backends.

Exports all specialized connector classes that extend the CDK base
classes with ready-to-use behavior for common scenarios.  These classes
can be used with configuration alone (zero code) or subclassed for
minor customizations.

Re-exports:
    OpenAICompatibleProvider: OpenAI-format API with org/version headers.
    HttpApiProvider: Abstract REST API with custom request/response translation.
    HttpHealthDiscovery: HTTP GET-based provider health probes.
    QuickProvider: Minimal provider with auto model discovery.
    ThresholdRotationPolicy: Threshold-based combined rotation policy.
    FileSecretStore: File-backed secret store (.env / JSON / TOML).
    KeyValueStorage: In-memory or file-backed key-value storage.
    ConsoleObservability: ANSI-colored console output for development.
"""
from __future__ import annotations

from modelmesh.cdk.specialized.callback_observability import (
    CallbackObservability,
    CallbackObservabilityConfig,
)
from modelmesh.cdk.specialized.console_observability import (
    ConsoleObservability,
    ConsoleObservabilityConfig,
)
from modelmesh.cdk.specialized.file_observability import (
    FileObservability,
    FileObservabilityConfig,
)
from modelmesh.cdk.specialized.file_secret_store import (
    FileSecretStore,
    FileSecretStoreConfig,
)
from modelmesh.cdk.specialized.http_api_provider import (
    HttpApiProvider,
    HttpApiProviderConfig,
)
from modelmesh.cdk.specialized.http_health_discovery import (
    HttpHealthDiscovery,
    HttpHealthDiscoveryConfig,
)
from modelmesh.cdk.specialized.kv_storage import (
    KeyValueStorage,
    KeyValueStorageConfig,
)
from modelmesh.cdk.specialized.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from modelmesh.cdk.specialized.quick_provider import (
    QuickProvider,
    QuickProviderConfig,
)
from modelmesh.cdk.specialized.threshold_rotation import (
    ThresholdRotationConfig,
    ThresholdRotationPolicy,
)

__all__ = [
    # Provider specialized classes
    "OpenAICompatibleConfig",
    "OpenAICompatibleProvider",
    "HttpApiProviderConfig",
    "HttpApiProvider",
    "HttpHealthDiscoveryConfig",
    "HttpHealthDiscovery",
    "QuickProviderConfig",
    "QuickProvider",
    # Rotation policy
    "ThresholdRotationConfig",
    "ThresholdRotationPolicy",
    # Secret store
    "FileSecretStoreConfig",
    "FileSecretStore",
    # Storage
    "KeyValueStorageConfig",
    "KeyValueStorage",
    # Observability
    "CallbackObservabilityConfig",
    "CallbackObservability",
    "ConsoleObservabilityConfig",
    "ConsoleObservability",
    "FileObservabilityConfig",
    "FileObservability",
]
