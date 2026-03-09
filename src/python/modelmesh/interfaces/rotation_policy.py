"""Backward-compatibility re-export for ``modelmesh.interfaces.rotation``.

Some samples and documentation reference ``rotation_policy`` instead of
``rotation``.  This module re-exports all public names so those imports
continue to work.
"""
from modelmesh.interfaces.rotation import *  # noqa: F401,F403
from modelmesh.interfaces.rotation import (
    DeactivationPolicy,
    DeactivationReason,
    ModelState,
    ModelStatus,
    RecoveryPolicy,
    RecoveryTrigger,
    SelectionStrategy,
)

# Aliases used by some samples
ModelSnapshot = ModelState
SelectionResult = ModelState

__all__ = [
    "DeactivationPolicy",
    "DeactivationReason",
    "ModelSnapshot",
    "ModelState",
    "ModelStatus",
    "RecoveryPolicy",
    "RecoveryTrigger",
    "SelectionResult",
    "SelectionStrategy",
]
