"""State manager for model health, usage counters, and lifecycle metadata.

Tracks per-model state that drives rotation, recovery, and observability.
State can be persisted through storage connectors using configurable sync
policies.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from modelmesh.interfaces.rotation import ModelState, ModelStatus

if TYPE_CHECKING:
    from modelmesh.interfaces.storage import StorageConnector

__all__ = ["StateManager"]


class StateManager:
    """Centralized state tracker for model health and usage.

    Maintains an in-memory dictionary of ``ModelState`` objects keyed by
    model ID. Optionally syncs to a ``StorageConnector`` using a
    configurable sync policy.

    Args:
        sync_policy: Persistence mode. One of ``"in-memory"`` (default),
            ``"sync-on-boundary"`` (load at startup, save at shutdown),
            ``"periodic"``, or ``"immediate"``.
        storage: Storage connector for persistence. Required for all
            policies except ``"in-memory"``.
    """

    def __init__(
        self,
        sync_policy: str = "in-memory",
        storage: Optional[StorageConnector] = None,
    ) -> None:
        self._states: dict[str, ModelState] = {}
        self._sync_policy = sync_policy
        self._storage = storage
        self._dirty = False

    def get(self, model_id: str) -> Optional[ModelState]:
        """Retrieve the state for a model, or None if not tracked.

        Args:
            model_id: Dot-notated model identifier.
        """
        return self._states.get(model_id)

    def get_or_create(self, model_id: str) -> ModelState:
        """Retrieve or initialize state for a model.

        If the model has not been tracked yet, creates a new
        ``ModelState`` with default values.

        Args:
            model_id: Dot-notated model identifier.
        """
        if model_id not in self._states:
            self._states[model_id] = ModelState(model_id=model_id)
        return self._states[model_id]

    def record_success(self, model_id: str, tokens: int = 0) -> None:
        """Record a successful request.

        Resets failure count, updates counters, and marks the model as
        recently successful.

        Args:
            model_id: Dot-notated model identifier.
            tokens: Total tokens consumed in the request.
        """
        state = self.get_or_create(model_id)
        state.failure_count = 0
        state.error_rate = 0.0
        state.total_requests += 1
        state.total_tokens += tokens
        state.last_success_at = time.time()
        self._dirty = True

    def record_failure(self, model_id: str) -> None:
        """Record a failed request.

        Increments failure count and updates error rate.

        Args:
            model_id: Dot-notated model identifier.
        """
        state = self.get_or_create(model_id)
        state.failure_count += 1
        state.total_requests += 1
        state.last_failure_at = time.time()
        if state.total_requests > 0:
            state.error_rate = state.failure_count / state.total_requests
        self._dirty = True

    def deactivate(self, model_id: str) -> None:
        """Move a model to standby status.

        Args:
            model_id: Dot-notated model identifier.
        """
        state = self.get_or_create(model_id)
        state.status = ModelStatus.STANDBY
        self._dirty = True

    def activate(self, model_id: str) -> None:
        """Move a model to active status and reset failure counters.

        Args:
            model_id: Dot-notated model identifier.
        """
        state = self.get_or_create(model_id)
        state.status = ModelStatus.ACTIVE
        state.failure_count = 0
        state.error_rate = 0.0
        self._dirty = True

    def all_states(self) -> dict[str, ModelState]:
        """Return a copy of all tracked model states."""
        return dict(self._states)

    def active_models(self) -> list[str]:
        """Return IDs of all models currently in active status."""
        return [
            mid
            for mid, state in self._states.items()
            if state.status == ModelStatus.ACTIVE
        ]

    def standby_models(self) -> list[str]:
        """Return IDs of all models currently in standby status."""
        return [
            mid
            for mid, state in self._states.items()
            if state.status == ModelStatus.STANDBY
        ]

    def reset(self, model_id: str) -> None:
        """Reset all state for a model to defaults.

        Args:
            model_id: Dot-notated model identifier.
        """
        self._states[model_id] = ModelState(model_id=model_id)
        self._dirty = True

    def clear(self) -> None:
        """Remove all tracked state."""
        self._states.clear()
        self._dirty = True

    @property
    def is_dirty(self) -> bool:
        """True if state has changed since last sync."""
        return self._dirty

    def mark_clean(self) -> None:
        """Mark the state as synchronized (no pending changes)."""
        self._dirty = False
