"""Configuration layer — MeshConfig, validation, hot-reload, and templates.

Re-exports the configuration objects used by the convenience layer.
"""
from __future__ import annotations

from modelmesh.config.auto_detect import PROVIDER_REGISTRY, detect_providers
from modelmesh.config.hot_reload import ConfigWatcher, reconfigure
from modelmesh.config.mesh_config import MeshConfig
from modelmesh.config.validation import ConfigError, ConfigValidator

__all__ = [
    "MeshConfig",
    "PROVIDER_REGISTRY",
    "detect_providers",
    "ConfigValidator",
    "ConfigError",
    "ConfigWatcher",
    "reconfigure",
]
