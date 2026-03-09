"""CDK Enum Reference -- consolidated re-exports.

Re-exports all enums defined in connector interface modules alongside
CDK-specific enums. Each enum's authoritative source is the interface
module where it is defined; this module provides a single import point
for convenience.
"""
from __future__ import annotations

from enum import Enum

# --- Re-exports from interface modules ------------------------------------

from modelmesh.interfaces.rotation import (  # noqa: F401
    ModelStatus,
    DeactivationReason,
    RecoveryTrigger,
)

from modelmesh.interfaces.observability import (  # noqa: F401
    EventType,
    LogLevel,
)

from modelmesh.interfaces.discovery import (  # noqa: F401
    SyncAction,
    DeprecationAction,
)

from modelmesh.interfaces.storage import (  # noqa: F401
    SyncPolicy,
    SerializationFormat,
)

# --- CDK-specific enums ---------------------------------------------------


class AuthMethod(Enum):
    """Authentication method used by a provider connector."""

    API_KEY = "api_key"
    OAUTH = "oauth"
    SERVICE_ACCOUNT = "service_account"


class ConnectorType(Enum):
    """Identifies the category of a connector for registration and lookup."""

    PROVIDER = "provider"
    ROTATION = "rotation"
    SECRET_STORE = "secret_store"
    STORAGE = "storage"
    OBSERVABILITY = "observability"
    DISCOVERY = "discovery"


__all__ = [
    # Re-exported from interfaces
    "ModelStatus",
    "DeactivationReason",
    "RecoveryTrigger",
    "EventType",
    "LogLevel",
    "SyncAction",
    "DeprecationAction",
    # CDK-specific
    "AuthMethod",
    "SyncPolicy",
    "SerializationFormat",
    "ConnectorType",
]
