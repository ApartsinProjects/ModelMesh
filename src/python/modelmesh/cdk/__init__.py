"""Connector Development Kit (CDK) base classes.

Provides base implementations of all connector interfaces with sensible
defaults.  Each base class handles boilerplate -- HTTP transport, caching,
serialization, error classification -- so that custom connectors only
override the methods that differ from the defaults.

Also re-exports mixins (retry, cache, rate-limiter, metrics) and
specialized pre-configured classes (OpenAICompatibleProvider, etc.) for
convenient single-import access::

    from modelmesh.cdk import (
        BaseProvider,
        OpenAICompatibleProvider,
        RetryMixin,
    )
"""
from __future__ import annotations

# -- Base classes ------------------------------------------------------------

from modelmesh.cdk.base_discovery import BaseDiscovery, BaseDiscoveryConfig
from modelmesh.cdk.base_observability import (
    BaseObservability,
    BaseObservabilityConfig,
)
from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.cdk.base_rotation import (
    BaseDeactivationPolicy,
    BaseRecoveryPolicy,
    BaseRotationConfig,
    BaseRotationPolicy,
    BaseSelectionStrategy,
)

# Alias for backward compatibility with samples/docs
BaseRotationPolicyConfig = BaseRotationConfig
from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig
from modelmesh.cdk.base_storage import BaseStorage, BaseStorageConfig

# -- Mixins ------------------------------------------------------------------

from modelmesh.cdk.mixins import (
    CacheMixin,
    CacheStats,
    CircuitBreakerMixin,
    CircuitOpenError,
    CircuitState,
    HttpClientMixin,
    MetricsMixin,
    MetricSnapshot,
    RateLimiterMixin,
    RequestTimeoutError,
    RetryMixin,
    StreamCheckpoint,
    StreamingCheckpointMixin,
    TimeoutMixin,
)

# -- Specialized classes -----------------------------------------------------

from modelmesh.cdk.specialized import (
    CallbackObservability,
    CallbackObservabilityConfig,
    ConsoleObservability,
    ConsoleObservabilityConfig,
    FileObservability,
    FileObservabilityConfig,
    FileSecretStore,
    FileSecretStoreConfig,
    HttpApiProvider,
    HttpApiProviderConfig,
    HttpHealthDiscovery,
    HttpHealthDiscoveryConfig,
    KeyValueStorage,
    KeyValueStorageConfig,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    QuickProvider,
    QuickProviderConfig,
    ThresholdRotationConfig,
    ThresholdRotationPolicy,
)

__all__ = [
    # ── Base classes ────────────────────────────────────────────────
    # Provider
    "BaseProviderConfig",
    "BaseProvider",
    # Rotation
    "BaseRotationConfig",
    "BaseRotationPolicyConfig",
    "BaseDeactivationPolicy",
    "BaseRecoveryPolicy",
    "BaseSelectionStrategy",
    "BaseRotationPolicy",
    # Secret Store
    "BaseSecretStoreConfig",
    "BaseSecretStore",
    # Storage
    "BaseStorageConfig",
    "BaseStorage",
    # Observability
    "BaseObservabilityConfig",
    "BaseObservability",
    # Discovery
    "BaseDiscoveryConfig",
    "BaseDiscovery",
    # ── Mixins ──────────────────────────────────────────────────────
    "CacheMixin",
    "CacheStats",
    "CircuitBreakerMixin",
    "CircuitOpenError",
    "CircuitState",
    "HttpClientMixin",
    "MetricsMixin",
    "MetricSnapshot",
    "RateLimiterMixin",
    "RequestTimeoutError",
    "RetryMixin",
    "StreamCheckpoint",
    "StreamingCheckpointMixin",
    "TimeoutMixin",
    # ── Specialized classes ─────────────────────────────────────────
    "OpenAICompatibleConfig",
    "OpenAICompatibleProvider",
    "HttpApiProviderConfig",
    "HttpApiProvider",
    "QuickProviderConfig",
    "QuickProvider",
    "ThresholdRotationConfig",
    "ThresholdRotationPolicy",
    "FileSecretStoreConfig",
    "FileSecretStore",
    "KeyValueStorageConfig",
    "KeyValueStorage",
    "CallbackObservabilityConfig",
    "CallbackObservability",
    "ConsoleObservabilityConfig",
    "ConsoleObservability",
    "FileObservabilityConfig",
    "FileObservability",
    "HttpHealthDiscoveryConfig",
    "HttpHealthDiscovery",
]
