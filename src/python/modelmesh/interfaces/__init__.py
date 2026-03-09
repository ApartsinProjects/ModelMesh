"""ModelMesh Lite connector interfaces.

Exports all abstract interface classes and supporting data types for the
six connector types: Provider, Rotation Policy, Secret Store, Storage,
Observability, and Discovery.
"""
from __future__ import annotations

from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    ModelInfo,
    ModelPricing,
    ProviderConnector,
    QuotaStatus,
    RateLimitStatus,
    TokenUsage,
)
from modelmesh.interfaces.rotation import (
    DeactivationPolicy,
    DeactivationReason,
    ModelState,
    ModelStatus,
    RecoveryPolicy,
    RecoveryTrigger,
    SelectionStrategy,
)
from modelmesh.interfaces.secret_store import (
    SecretManagement,
    SecretResolution,
    SecretStoreConnector,
    SecretValue,
)
from modelmesh.interfaces.storage import (
    EntryMetadata,
    Inventory,
    LockHandle,
    Locking,
    Persistence,
    SerializationFormat,
    StatQuery,
    StorageConnector,
    StorageEntry,
    SyncPolicy,
)
from modelmesh.interfaces.observability import (
    AggregateStats,
    EventType,
    Events,
    Logging,
    LogLevel,
    ObservabilityConnector,
    RequestLogEntry,
    RoutingEvent,
    Severity,
    Statistics,
    TraceEntry,
    Tracing,
)
from modelmesh.interfaces.discovery import (
    DeprecationAction,
    DiscoveryConnector,
    HealthMonitoring,
    HealthReport,
    ProbeResult,
    RegistrySync,
    SyncAction,
    SyncResult,
    SyncStatus,
)

__all__ = [
    # Provider
    "ChatMessage",
    "CompletionChoice",
    "CompletionRequest",
    "CompletionResponse",
    "ErrorClassification",
    "ModelInfo",
    "ModelPricing",
    "ProviderConnector",
    "QuotaStatus",
    "RateLimitStatus",
    "TokenUsage",
    # Rotation
    "DeactivationPolicy",
    "DeactivationReason",
    "ModelState",
    "ModelStatus",
    "RecoveryPolicy",
    "RecoveryTrigger",
    "SelectionStrategy",
    # Secret Store
    "SecretManagement",
    "SecretResolution",
    "SecretStoreConnector",
    "SecretValue",
    # Storage
    "EntryMetadata",
    "Inventory",
    "LockHandle",
    "Locking",
    "Persistence",
    "SerializationFormat",
    "StatQuery",
    "StorageConnector",
    "StorageEntry",
    "SyncPolicy",
    # Observability
    "AggregateStats",
    "EventType",
    "Events",
    "Logging",
    "LogLevel",
    "ObservabilityConnector",
    "RequestLogEntry",
    "RoutingEvent",
    "Severity",
    "Statistics",
    "TraceEntry",
    "Tracing",
    # Discovery
    "DeprecationAction",
    "DiscoveryConnector",
    "HealthMonitoring",
    "HealthReport",
    "ProbeResult",
    "RegistrySync",
    "SyncAction",
    "SyncResult",
    "SyncStatus",
]
