"""Capability pool — groups models that fulfill a capability.

A CapabilityPool collects models registered at a capability node (or its
descendants), manages their lifecycle state, and delegates model selection
to a pluggable SelectionStrategy.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from modelmesh.interfaces.rotation import (
    DeactivationReason,
    ModelState,
    ModelStatus,
    SelectionStrategy,
)

if TYPE_CHECKING:
    from modelmesh.interfaces.provider import CompletionRequest

__all__ = ["CapabilityPool", "PoolModel"]


@dataclass
class PoolModel:
    """A model entry within a capability pool.

    Attributes:
        model_id: Dot-notated model identifier (e.g. ``"openai.gpt-4o"``).
        real_model_id: Vendor-specific model name (e.g. ``"gpt-4o"``).
        provider_id: Connector ID for the provider (e.g. ``"openai.llm.v1"``).
        status: Current lifecycle status (ACTIVE or STANDBY).
        failure_count: Consecutive failures since last success.
        total_requests: Lifetime request count.
        total_tokens: Lifetime token consumption.
        last_failure_at: Timestamp of last failure, or None.
        last_success_at: Timestamp of last success, or None.
    """

    model_id: str
    real_model_id: str
    provider_id: str
    status: ModelStatus = ModelStatus.ACTIVE
    failure_count: int = 0
    total_requests: int = 0
    total_tokens: int = 0
    last_failure_at: Optional[float] = None
    last_success_at: Optional[float] = None

    def to_model_state(self) -> ModelState:
        """Convert to a ModelState for use with rotation policies."""
        return ModelState(
            model_id=self.model_id,
            status=self.status,
            failure_count=self.failure_count,
            total_requests=self.total_requests,
            total_tokens=self.total_tokens,
            last_failure_at=self.last_failure_at,
            last_success_at=self.last_success_at,
        )


class _StickUntilFailureStrategy:
    """Default selection strategy: stick with the first active model.

    Returns the first active candidate in insertion order. This is the
    built-in fallback when no explicit strategy is configured.
    """

    def select(
        self,
        candidates: list[ModelState],
        request: CompletionRequest,
    ) -> Optional[ModelState]:
        active = [c for c in candidates if c.status == ModelStatus.ACTIVE]
        return active[0] if active else None

    def score(self, state: ModelState, request: CompletionRequest) -> float:
        return 1.0 if state.status == ModelStatus.ACTIVE else 0.0


class CapabilityPool:
    """Groups models that fulfill a capability.

    Manages model lifecycle (active/standby), delegates selection to a
    pluggable strategy, and records success/failure events for rotation
    decisions.

    Args:
        pool_id: Dot-notated pool identifier
                 (e.g. ``"generation.text-generation"``).
        config: Pool configuration dict from MeshConfig.
    """

    def __init__(
        self, pool_id: str, config: dict, observability=None
    ) -> None:
        self._id = pool_id
        self._config = config
        self._models: list[PoolModel] = []
        self._models_by_id: dict[str, PoolModel] = {}
        self._strategy: SelectionStrategy | _StickUntilFailureStrategy = (
            _StickUntilFailureStrategy()
        )
        self._failure_threshold: int = config.get("failure_threshold", 3)
        self._observability = observability

    def _trace(
        self,
        severity,
        component: str,
        message: str,
        error: str | None = None,
        **metadata,
    ) -> None:
        """Emit a trace entry through the observability connector."""
        from datetime import datetime

        from modelmesh.interfaces.observability import Severity as SevEnum
        from modelmesh.interfaces.observability import TraceEntry

        sev = severity if isinstance(severity, SevEnum) else SevEnum(severity.lower())
        entry = TraceEntry(
            severity=sev,
            timestamp=datetime.now(),
            component=component,
            message=message,
            error=error,
            metadata=metadata if metadata else None,
        )
        if self._observability:
            self._observability.trace(entry)

    @property
    def pool_id(self) -> str:
        """The pool's dot-notated identifier."""
        return self._id

    @property
    def config(self) -> dict:
        """The pool's configuration dict."""
        return self._config

    @property
    def models(self) -> list[PoolModel]:
        """All models in this pool (both active and standby)."""
        return list(self._models)

    @property
    def active_models(self) -> list[PoolModel]:
        """Only the active models in this pool."""
        return [m for m in self._models if m.status == ModelStatus.ACTIVE]

    @property
    def standby_models(self) -> list[PoolModel]:
        """Only the standby models in this pool."""
        return [m for m in self._models if m.status == ModelStatus.STANDBY]

    def set_strategy(self, strategy: SelectionStrategy) -> None:
        """Replace the selection strategy for this pool.

        Args:
            strategy: A SelectionStrategy implementation.
        """
        self._strategy = strategy

    def add_model(self, model: PoolModel) -> None:
        """Add a model to the pool.

        Args:
            model: The PoolModel to add.

        Raises:
            ValueError: If a model with the same ID already exists.
        """
        if model.model_id in self._models_by_id:
            raise ValueError(
                f"Model '{model.model_id}' already exists in pool "
                f"'{self._id}'"
            )
        self._models.append(model)
        self._models_by_id[model.model_id] = model
        self._trace(
            "DEBUG",
            f"pool.{self._id}",
            f"Model '{model.model_id}' added to pool",
            model_id=model.model_id,
            provider_id=model.provider_id,
        )

    def remove_model(self, model_id: str) -> None:
        """Remove a model from the pool by ID.

        Args:
            model_id: Dot-notated model identifier.

        Raises:
            KeyError: If the model is not in this pool.
        """
        if model_id not in self._models_by_id:
            raise KeyError(
                f"Model '{model_id}' not found in pool '{self._id}'"
            )
        model = self._models_by_id.pop(model_id)
        self._models.remove(model)

    def select(self, request: CompletionRequest) -> Optional[PoolModel]:
        """Select the best active model for a request.

        Delegates to the configured selection strategy. Returns None if
        no active model is available.

        Args:
            request: The incoming completion request.

        Returns:
            The selected PoolModel, or None.
        """
        candidates = [m.to_model_state() for m in self._models]
        selected = self._strategy.select(candidates, request)
        if selected is None:
            return None
        return self._models_by_id.get(selected.model_id)

    def record_success(self, model_id: str) -> None:
        """Record a successful request for a model.

        Resets the consecutive failure count and updates counters.

        Args:
            model_id: Dot-notated model identifier.
        """
        model = self._models_by_id.get(model_id)
        if model is None:
            return
        model.failure_count = 0
        model.total_requests += 1
        model.last_success_at = time.time()
        self._trace(
            "DEBUG",
            f"pool.{self._id}",
            f"Request succeeded for model '{model_id}'",
            model_id=model_id,
            total_requests=model.total_requests,
        )

    def record_failure(self, model_id: str, error: Exception) -> None:
        """Record a failed request for a model.

        Increments the failure count and may deactivate the model if the
        failure threshold is reached.

        Args:
            model_id: Dot-notated model identifier.
            error: The exception that caused the failure.
        """
        model = self._models_by_id.get(model_id)
        if model is None:
            return
        model.failure_count += 1
        model.total_requests += 1
        model.last_failure_at = time.time()

        self._trace(
            "WARNING",
            f"pool.{self._id}",
            f"Failure recorded for model '{model_id}' "
            f"(count: {model.failure_count}/{self._failure_threshold})",
            error=str(error),
            model_id=model_id,
            failure_count=model.failure_count,
            threshold=self._failure_threshold,
        )

        if model.failure_count >= self._failure_threshold:
            model.status = ModelStatus.STANDBY
            self._trace(
                "ERROR",
                f"pool.{self._id}",
                f"Model '{model_id}' deactivated after "
                f"{model.failure_count} consecutive failures",
                error=str(error),
                model_id=model_id,
                failure_count=model.failure_count,
            )

    def rotate(self) -> Optional[PoolModel]:
        """Force rotation: deactivate the current model and return the next.

        Moves the first active model to standby and returns the next
        active model (if any).

        Returns:
            The next active PoolModel, or None if no alternative exists.
        """
        active = self.active_models
        old_model_id = active[0].model_id if active else None
        if active:
            active[0].status = ModelStatus.STANDBY
        remaining = self.active_models
        new_model = remaining[0] if remaining else None
        self._trace(
            "INFO",
            f"pool.{self._id}",
            f"Manual rotation: '{old_model_id}' -> "
            f"'{new_model.model_id if new_model else None}'",
            old_model_id=old_model_id,
            new_model_id=new_model.model_id if new_model else None,
        )
        return new_model

    def reactivate(self, model_id: str) -> None:
        """Manually reactivate a standby model.

        Args:
            model_id: Dot-notated model identifier.

        Raises:
            KeyError: If the model is not in this pool.
        """
        model = self._models_by_id.get(model_id)
        if model is None:
            raise KeyError(
                f"Model '{model_id}' not found in pool '{self._id}'"
            )
        model.status = ModelStatus.ACTIVE
        model.failure_count = 0
        self._trace(
            "INFO",
            f"pool.{self._id}",
            f"Model '{model_id}' reactivated",
            model_id=model_id,
        )

    def status(self) -> dict:
        """Return a summary of pool health.

        Returns:
            Dict with ``active``, ``standby``, ``total``, and
            ``current_model`` keys.
        """
        active = self.active_models
        return {
            "active": len(active),
            "standby": len(self.standby_models),
            "total": len(self._models),
            "current_model": active[0].model_id if active else None,
        }
