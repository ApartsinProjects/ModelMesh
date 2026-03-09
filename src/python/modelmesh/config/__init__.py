"""Configuration layer — MeshConfig and provider auto-detection.

Re-exports the configuration objects used by the convenience layer.
"""
from __future__ import annotations

from modelmesh.config.auto_detect import PROVIDER_REGISTRY, detect_providers
from modelmesh.config.mesh_config import MeshConfig

__all__ = [
    "MeshConfig",
    "PROVIDER_REGISTRY",
    "detect_providers",
]
