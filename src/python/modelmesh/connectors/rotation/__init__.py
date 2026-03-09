"""Pre-shipped rotation policy connectors for ModelMesh Lite.

Exports the stick-until-failure rotation policy and its configuration class.
"""
from __future__ import annotations

from modelmesh.connectors.rotation.stick_until_failure import (
    StickUntilFailureConfig,
    StickUntilFailurePolicy,
)

__all__ = [
    "StickUntilFailurePolicy",
    "StickUntilFailureConfig",
]
