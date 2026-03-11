"""Usage tracking facade for ModelMesh.

Exposes cost and token usage data from the internal ``CostTracker``
through a clean, read-only API suitable for application dashboards
and monitoring.

Usage::

    client = modelmesh.create("chat")
    # ... after some requests ...
    print(client.usage.total_cost)
    print(client.usage.total_tokens)
    print(client.usage.by_model)
    print(client.usage.budget_status)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from modelmesh.core.budget import BudgetStatus, CostTracker
    from modelmesh.core.mesh import ModelMesh


@dataclass
class ModelUsage:
    """Usage breakdown for a single model.

    Attributes:
        model_id: The model identifier.
        total_cost: Accumulated cost for this model.
        total_requests: Number of requests routed to this model.
    """

    model_id: str
    total_cost: float = 0.0
    total_requests: int = 0


@dataclass
class ProviderUsage:
    """Usage breakdown for a single provider.

    Attributes:
        provider_id: The provider connector ID.
        total_cost: Accumulated cost for this provider.
    """

    provider_id: str
    total_cost: float = 0.0


class UsageTracker:
    """Read-only facade over ModelMesh cost and usage tracking.

    Wraps the internal ``CostTracker`` (if budget is configured)
    and the ``StateManager`` to provide clean usage queries.

    Args:
        mesh: The initialized ModelMesh instance.
    """

    def __init__(self, mesh: ModelMesh) -> None:
        self._mesh = mesh

    def _get_cost_tracker(self) -> Optional[CostTracker]:
        """Retrieve the internal CostTracker, if available."""
        if hasattr(self._mesh, "_cost_tracker"):
            return self._mesh._cost_tracker
        return None

    @property
    def total_cost(self) -> float:
        """Total cost accumulated across all models and providers."""
        tracker = self._get_cost_tracker()
        if tracker is None:
            return 0.0
        summary = tracker.summary()
        return summary.get("total_cost", 0.0)

    @property
    def daily_cost(self) -> float:
        """Cost accumulated today (UTC)."""
        tracker = self._get_cost_tracker()
        if tracker is None:
            return 0.0
        return tracker.get_daily_cost()

    @property
    def monthly_cost(self) -> float:
        """Cost accumulated this month (UTC)."""
        tracker = self._get_cost_tracker()
        if tracker is None:
            return 0.0
        return tracker.get_monthly_cost()

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed across all requests.

        Computed from cost records if a tracker is available.
        """
        tracker = self._get_cost_tracker()
        if tracker is None:
            return 0
        with tracker._lock:
            return sum(
                r.prompt_tokens + r.completion_tokens for r in tracker._records
            )

    @property
    def by_model(self) -> dict[str, ModelUsage]:
        """Usage breakdown by model ID."""
        tracker = self._get_cost_tracker()
        if tracker is None:
            return {}
        summary = tracker.summary()
        by_model_cost = summary.get("by_model", {})
        result: dict[str, ModelUsage] = {}
        for model_id, cost in by_model_cost.items():
            result[model_id] = ModelUsage(model_id=model_id, total_cost=cost)
        return result

    @property
    def by_provider(self) -> dict[str, ProviderUsage]:
        """Usage breakdown by provider connector ID."""
        tracker = self._get_cost_tracker()
        if tracker is None:
            return {}
        summary = tracker.summary()
        by_provider_cost = summary.get("by_provider", {})
        result: dict[str, ProviderUsage] = {}
        for provider_id, cost in by_provider_cost.items():
            result[provider_id] = ProviderUsage(
                provider_id=provider_id, total_cost=cost
            )
        return result

    @property
    def budget_status(self) -> Optional[BudgetStatus]:
        """Current budget status, or None if no budget is configured."""
        tracker = self._get_cost_tracker()
        if tracker is None:
            return None
        return tracker.check_budget()

    def reset(self) -> None:
        """Reset all usage counters."""
        tracker = self._get_cost_tracker()
        if tracker is not None:
            tracker.reset_daily()
            tracker.reset_monthly()

    def summary(self) -> dict:
        """Return a comprehensive usage summary dict."""
        tracker = self._get_cost_tracker()
        if tracker is None:
            return {
                "total_cost": 0.0,
                "daily_cost": 0.0,
                "monthly_cost": 0.0,
                "total_tokens": 0,
                "by_model": {},
                "by_provider": {},
                "budget_status": None,
            }
        result = tracker.summary()
        result["total_tokens"] = self.total_tokens
        return result


__all__ = [
    "ModelUsage",
    "ProviderUsage",
    "UsageTracker",
]
