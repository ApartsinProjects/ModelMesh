"""Discovery connectors for ModelMesh Lite.

Provides auto-discovery and model registry connectors for automatic
provider and model enumeration.
"""
from __future__ import annotations

from modelmesh.connectors.discovery.auto_discovery import (
    AutoDiscovery,
    DiscoveredModel,
    DiscoveryConfig,
    ModelRegistry,
)

__all__ = [
    "AutoDiscovery",
    "DiscoveredModel",
    "DiscoveryConfig",
    "ModelRegistry",
]
