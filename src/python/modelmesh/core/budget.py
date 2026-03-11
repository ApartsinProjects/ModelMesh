"""Budget and cost tracking for model usage.

Provides a ``CostTracker`` that records per-request costs across models
and providers, enforces daily and monthly budget limits, and exposes
detailed cost breakdowns and budget status checks.

Typical usage::

    from modelmesh.core.budget import BudgetConfig, CostTracker

    tracker = CostTracker(BudgetConfig(daily_limit=10.0, monthly_limit=100.0))

    cost = tracker.record("openai.gpt-4o", "openai.llm.v1", usage, pricing)
    status = tracker.check_budget()
    if status.exceeded:
        print("Budget exceeded!")
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from modelmesh.interfaces.provider import ModelPricing, TokenUsage

logger = logging.getLogger("modelmesh.budget")

__all__ = ["BudgetConfig", "BudgetStatus", "CostTracker"]


@dataclass
class BudgetConfig:
    """Configuration for budget limits and alerting.

    Attributes:
        daily_limit: Maximum spend in USD per day, or ``None`` for
            unlimited.
        monthly_limit: Maximum spend in USD per month, or ``None``
            for unlimited.
        per_request_limit: Maximum cost allowed for a single request,
            or ``None`` for unlimited.
        alert_threshold: Fraction of a budget limit at which an alert
            flag is raised (default ``0.8`` = 80%).
        enforce: If ``True`` (default), :meth:`CostTracker.check_budget`
            marks ``exceeded`` when limits are hit.  If ``False``, costs
            are tracked but not blocked.
    """

    daily_limit: Optional[float] = None
    monthly_limit: Optional[float] = None
    per_request_limit: Optional[float] = None
    alert_threshold: float = 0.8
    enforce: bool = True


@dataclass
class BudgetStatus:
    """Snapshot of current budget consumption.

    Attributes:
        daily_used: Total cost accumulated today.
        daily_limit: Configured daily limit, or ``None``.
        daily_remaining: Remaining daily budget, or ``None`` if no
            daily limit is set.
        monthly_used: Total cost accumulated this month.
        monthly_limit: Configured monthly limit, or ``None``.
        monthly_remaining: Remaining monthly budget, or ``None`` if
            no monthly limit is set.
        exceeded: ``True`` if any enforced limit has been exceeded.
        alert: ``True`` if usage has crossed the alert threshold on
            any configured limit.
    """

    daily_used: float = 0.0
    daily_limit: Optional[float] = None
    daily_remaining: Optional[float] = None
    monthly_used: float = 0.0
    monthly_limit: Optional[float] = None
    monthly_remaining: Optional[float] = None
    exceeded: bool = False
    alert: bool = False


@dataclass
class _CostRecord:
    """Internal record for a single cost event."""

    model_id: str
    provider_id: str
    cost: float
    timestamp: float
    prompt_tokens: int
    completion_tokens: int


class CostTracker:
    """Tracks cost across providers and models with budget enforcement.

    Maintains a rolling log of cost records and provides daily/monthly
    aggregation, per-model and per-provider breakdowns, and budget
    status checks with alert and enforcement support.

    Thread-safe: all mutating operations are protected by a lock.

    Args:
        config: Budget configuration.  Defaults to no limits
            (tracking-only mode).
    """

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self._config = config or BudgetConfig()
        self._records: list[_CostRecord] = []
        self._lock = threading.Lock()
        self._current_day: str = self._today()
        self._current_month: str = self._this_month()

    # -- Static helpers ------------------------------------------------------

    @staticmethod
    def _today() -> str:
        """Return today's date as an ISO string (UTC)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _this_month() -> str:
        """Return the current month as ``YYYY-MM`` (UTC)."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @staticmethod
    def calculate_cost(usage: TokenUsage, pricing: ModelPricing) -> float:
        """Calculate the monetary cost of a token usage event.

        Args:
            usage: Token counts for the request.
            pricing: Per-token and per-request pricing metadata.

        Returns:
            The calculated cost in the provider's billing currency.
        """
        return (
            (usage.prompt_tokens / 1000.0 * pricing.input_per_1k_tokens)
            + (usage.completion_tokens / 1000.0 * pricing.output_per_1k_tokens)
            + pricing.per_request
        )

    # -- Recording -----------------------------------------------------------

    def record(
        self,
        model_id: str,
        provider_id: str,
        usage: TokenUsage,
        pricing: ModelPricing,
    ) -> float:
        """Record token usage and return calculated cost.

        Args:
            model_id: Dot-notated model identifier.
            provider_id: Connector ID for the provider.
            usage: Token counts for the request.
            pricing: Per-token and per-request pricing metadata.

        Returns:
            The calculated cost of the request.

        Raises:
            ValueError: If ``per_request_limit`` is set and the
                calculated cost exceeds it.
        """
        cost = self.calculate_cost(usage, pricing)

        if (
            self._config.per_request_limit is not None
            and cost > self._config.per_request_limit
            and self._config.enforce
        ):
            raise ValueError(
                f"Request cost {cost:.6f} exceeds per-request limit "
                f"{self._config.per_request_limit:.6f}"
            )

        record = _CostRecord(
            model_id=model_id,
            provider_id=provider_id,
            cost=cost,
            timestamp=time.time(),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

        with self._lock:
            self._auto_reset()
            self._records.append(record)

        logger.debug(
            "Recorded cost %.6f for model '%s' via '%s'",
            cost,
            model_id,
            provider_id,
        )
        return cost

    # -- Budget checking -----------------------------------------------------

    def check_budget(self, model_id: str | None = None) -> BudgetStatus:
        """Check current budget status.

        Args:
            model_id: If provided, check budget considering only costs
                for this model.  Otherwise check aggregate budget.

        Returns:
            A :class:`BudgetStatus` snapshot.
        """
        with self._lock:
            self._auto_reset()
            daily = self._daily_cost(model_id)
            monthly = self._monthly_cost(model_id)

        exceeded = False
        alert = False

        daily_remaining: Optional[float] = None
        monthly_remaining: Optional[float] = None

        if self._config.daily_limit is not None:
            daily_remaining = max(0.0, self._config.daily_limit - daily)
            if daily >= self._config.daily_limit and self._config.enforce:
                exceeded = True
            if daily >= self._config.daily_limit * self._config.alert_threshold:
                alert = True

        if self._config.monthly_limit is not None:
            monthly_remaining = max(0.0, self._config.monthly_limit - monthly)
            if monthly >= self._config.monthly_limit and self._config.enforce:
                exceeded = True
            if monthly >= self._config.monthly_limit * self._config.alert_threshold:
                alert = True

        return BudgetStatus(
            daily_used=daily,
            daily_limit=self._config.daily_limit,
            daily_remaining=daily_remaining,
            monthly_used=monthly,
            monthly_limit=self._config.monthly_limit,
            monthly_remaining=monthly_remaining,
            exceeded=exceeded,
            alert=alert,
        )

    # -- Cost queries --------------------------------------------------------

    def get_model_cost(self, model_id: str) -> float:
        """Return the total cost accumulated for a specific model.

        Args:
            model_id: Dot-notated model identifier.
        """
        with self._lock:
            return sum(r.cost for r in self._records if r.model_id == model_id)

    def get_provider_cost(self, provider_id: str) -> float:
        """Return the total cost accumulated for a specific provider.

        Args:
            provider_id: Connector ID for the provider.
        """
        with self._lock:
            return sum(
                r.cost for r in self._records if r.provider_id == provider_id
            )

    def get_daily_cost(self) -> float:
        """Return the total cost accumulated today (UTC)."""
        with self._lock:
            self._auto_reset()
            return self._daily_cost()

    def get_monthly_cost(self) -> float:
        """Return the total cost accumulated this month (UTC)."""
        with self._lock:
            self._auto_reset()
            return self._monthly_cost()

    # -- Resets --------------------------------------------------------------

    def reset_daily(self) -> None:
        """Clear all cost records from today."""
        today = self._today()
        with self._lock:
            self._records = [r for r in self._records if not self._is_today(r, today)]
            self._current_day = today

    def reset_monthly(self) -> None:
        """Clear all cost records from this month."""
        month = self._this_month()
        with self._lock:
            self._records = [
                r for r in self._records if not self._is_this_month(r, month)
            ]
            self._current_month = month

    # -- Summary -------------------------------------------------------------

    def summary(self) -> dict:
        """Return a comprehensive cost summary.

        Returns:
            Dict with ``daily_cost``, ``monthly_cost``, ``total_cost``,
            ``by_model``, ``by_provider``, ``record_count``, and
            ``budget_status`` keys.
        """
        with self._lock:
            self._auto_reset()
            total = sum(r.cost for r in self._records)

            by_model: dict[str, float] = {}
            by_provider: dict[str, float] = {}
            for r in self._records:
                by_model[r.model_id] = by_model.get(r.model_id, 0.0) + r.cost
                by_provider[r.provider_id] = (
                    by_provider.get(r.provider_id, 0.0) + r.cost
                )

            daily = self._daily_cost()
            monthly = self._monthly_cost()

        return {
            "daily_cost": daily,
            "monthly_cost": monthly,
            "total_cost": total,
            "by_model": by_model,
            "by_provider": by_provider,
            "record_count": len(self._records),
            "budget_status": self.check_budget(),
        }

    # -- Internal helpers ----------------------------------------------------

    def _auto_reset(self) -> None:
        """Detect day/month boundary crossings and update tracking."""
        today = self._today()
        month = self._this_month()
        if today != self._current_day:
            self._current_day = today
        if month != self._current_month:
            self._current_month = month

    def _daily_cost(self, model_id: str | None = None) -> float:
        """Sum costs for today (caller holds lock)."""
        today = self._today()
        return sum(
            r.cost
            for r in self._records
            if self._is_today(r, today)
            and (model_id is None or r.model_id == model_id)
        )

    def _monthly_cost(self, model_id: str | None = None) -> float:
        """Sum costs for this month (caller holds lock)."""
        month = self._this_month()
        return sum(
            r.cost
            for r in self._records
            if self._is_this_month(r, month)
            and (model_id is None or r.model_id == model_id)
        )

    @staticmethod
    def _is_today(record: _CostRecord, today: str) -> bool:
        """Check if a record's timestamp falls on the given date (UTC)."""
        record_date = datetime.fromtimestamp(
            record.timestamp, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        return record_date == today

    @staticmethod
    def _is_this_month(record: _CostRecord, month: str) -> bool:
        """Check if a record's timestamp falls in the given month (UTC)."""
        record_month = datetime.fromtimestamp(
            record.timestamp, tz=timezone.utc
        ).strftime("%Y-%m")
        return record_month == month
