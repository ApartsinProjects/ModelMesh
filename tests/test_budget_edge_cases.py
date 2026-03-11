"""Tests for budget enforcement corner cases and cost tracking."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.core.budget import BudgetConfig, BudgetStatus, CostTracker
from modelmesh.exceptions import BudgetExceededError
from modelmesh.interfaces.provider import ModelPricing, TokenUsage


def _make_usage(prompt=100, completion=50):
    """Create a TokenUsage for testing."""
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )


def _make_pricing(input_per_1k=0.01, output_per_1k=0.03, per_request=0.0):
    """Create a ModelPricing for testing."""
    return ModelPricing(
        input_per_1k_tokens=input_per_1k,
        output_per_1k_tokens=output_per_1k,
        per_request=per_request,
    )


class TestBudgetEdgeCases:
    """Test budget enforcement corner cases."""

    def test_budget_exceeded_raises_error(self):
        """BudgetExceededError is raised when per-request budget is exhausted."""
        config = BudgetConfig(per_request_limit=0.001, enforce=True)
        tracker = CostTracker(config)
        usage = _make_usage(prompt=1000, completion=1000)
        pricing = _make_pricing(input_per_1k=1.0, output_per_1k=1.0)

        with pytest.raises(BudgetExceededError, match="per-request limit"):
            tracker.record("gpt-4o", "openai.llm.v1", usage, pricing)

    def test_budget_exceeded_error_fields(self):
        """BudgetExceededError carries limit_type, limit_value, actual_value."""
        config = BudgetConfig(per_request_limit=0.001, enforce=True)
        tracker = CostTracker(config)
        usage = _make_usage(prompt=1000, completion=1000)
        pricing = _make_pricing(input_per_1k=1.0, output_per_1k=1.0)

        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.record("gpt-4o", "openai.llm.v1", usage, pricing)

        err = exc_info.value
        assert err.limit_type == "per_request"
        assert err.limit_value == 0.001
        assert err.actual_value > 0.001

    def test_usage_tracker_accumulates_tokens(self):
        """CostTracker correctly sums token usage across calls."""
        tracker = CostTracker()
        usage1 = _make_usage(prompt=100, completion=50)
        usage2 = _make_usage(prompt=200, completion=100)
        pricing = _make_pricing()

        tracker.record("model-a", "provider-a", usage1, pricing)
        tracker.record("model-a", "provider-a", usage2, pricing)

        with tracker._lock:
            total_tokens = sum(
                r.prompt_tokens + r.completion_tokens for r in tracker._records
            )
        assert total_tokens == (100 + 50 + 200 + 100)

    def test_usage_tracker_tracks_cost(self):
        """CostTracker tracks estimated cost."""
        tracker = CostTracker()
        usage = _make_usage(prompt=1000, completion=500)
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        cost = tracker.record("model-a", "provider-a", usage, pricing)

        expected = (1000 / 1000.0 * 0.01) + (500 / 1000.0 * 0.03)
        assert abs(cost - expected) < 1e-9

    def test_usage_tracker_per_model_breakdown(self):
        """Usage is tracked per model."""
        tracker = CostTracker()
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        tracker.record("model-a", "provider-a", _make_usage(), pricing)
        tracker.record("model-b", "provider-a", _make_usage(), pricing)
        tracker.record("model-a", "provider-a", _make_usage(), pricing)

        summary = tracker.summary()
        assert "model-a" in summary["by_model"]
        assert "model-b" in summary["by_model"]
        # model-a was used twice, model-b once
        assert summary["by_model"]["model-a"] > summary["by_model"]["model-b"]

    def test_usage_tracker_per_provider_breakdown(self):
        """Usage is tracked per provider."""
        tracker = CostTracker()
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        tracker.record("model-a", "provider-a", _make_usage(), pricing)
        tracker.record("model-b", "provider-b", _make_usage(), pricing)

        summary = tracker.summary()
        assert "provider-a" in summary["by_provider"]
        assert "provider-b" in summary["by_provider"]

    def test_usage_tracker_reset(self):
        """Usage can be reset."""
        tracker = CostTracker()
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        tracker.record("model-a", "provider-a", _make_usage(), pricing)
        assert tracker.get_daily_cost() > 0

        tracker.reset_daily()
        assert tracker.get_daily_cost() == 0.0

    def test_daily_budget_status(self):
        """Daily budget status is tracked."""
        config = BudgetConfig(daily_limit=1.0, enforce=True)
        tracker = CostTracker(config)

        status = tracker.check_budget()
        assert status.daily_limit == 1.0
        assert status.daily_used == 0.0
        assert status.daily_remaining == 1.0
        assert status.exceeded is False

    def test_monthly_budget_status(self):
        """Monthly budget status is tracked."""
        config = BudgetConfig(monthly_limit=100.0, enforce=True)
        tracker = CostTracker(config)

        status = tracker.check_budget()
        assert status.monthly_limit == 100.0
        assert status.monthly_used == 0.0
        assert status.monthly_remaining == 100.0
        assert status.exceeded is False

    def test_no_limits_returns_none_remaining(self):
        """Without limits, remaining fields are None."""
        tracker = CostTracker()
        status = tracker.check_budget()
        assert status.daily_remaining is None
        assert status.monthly_remaining is None
        assert status.exceeded is False

    def test_enforce_false_does_not_exceed(self):
        """When enforce=False, exceeded is never True."""
        config = BudgetConfig(per_request_limit=0.001, enforce=False)
        tracker = CostTracker(config)
        usage = _make_usage(prompt=10000, completion=10000)
        pricing = _make_pricing(input_per_1k=1.0, output_per_1k=1.0)

        # Should not raise even though cost exceeds limit
        cost = tracker.record("gpt-4o", "openai.llm.v1", usage, pricing)
        assert cost > 0.001


class TestCostTracking:
    """Test cost estimation and tracking."""

    def test_cost_calculation_with_known_model(self):
        """Cost is calculated for known model pricing."""
        usage = _make_usage(prompt=1000, completion=500)
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        cost = CostTracker.calculate_cost(usage, pricing)
        expected = (1000 / 1000.0 * 0.01) + (500 / 1000.0 * 0.03)
        assert abs(cost - expected) < 1e-9

    def test_zero_tokens_zero_cost(self):
        """Zero tokens results in zero cost."""
        usage = _make_usage(prompt=0, completion=0)
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        cost = CostTracker.calculate_cost(usage, pricing)
        assert cost == 0.0

    def test_per_request_pricing(self):
        """Per-request pricing is included in cost calculation."""
        usage = _make_usage(prompt=0, completion=0)
        pricing = _make_pricing(per_request=0.05)

        cost = CostTracker.calculate_cost(usage, pricing)
        assert cost == 0.05

    def test_cost_combines_all_components(self):
        """Cost calculation combines input, output, and per-request pricing."""
        usage = _make_usage(prompt=1000, completion=1000)
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.02, per_request=0.001)

        cost = CostTracker.calculate_cost(usage, pricing)
        expected = (1000 / 1000.0 * 0.01) + (1000 / 1000.0 * 0.02) + 0.001
        assert abs(cost - expected) < 1e-9

    def test_get_model_cost(self):
        """get_model_cost returns cost for a specific model."""
        tracker = CostTracker()
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        tracker.record("model-a", "provider-a", _make_usage(), pricing)
        tracker.record("model-b", "provider-a", _make_usage(), pricing)

        cost_a = tracker.get_model_cost("model-a")
        cost_b = tracker.get_model_cost("model-b")
        assert cost_a > 0
        assert cost_b > 0
        assert abs(cost_a - cost_b) < 1e-9  # Same usage and pricing

    def test_get_provider_cost(self):
        """get_provider_cost returns cost for a specific provider."""
        tracker = CostTracker()
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        tracker.record("model-a", "provider-a", _make_usage(), pricing)
        tracker.record("model-b", "provider-b", _make_usage(), pricing)

        cost_a = tracker.get_provider_cost("provider-a")
        cost_b = tracker.get_provider_cost("provider-b")
        assert cost_a > 0
        assert cost_b > 0

    def test_summary_structure(self):
        """Summary returns expected keys."""
        tracker = CostTracker()
        summary = tracker.summary()

        assert "daily_cost" in summary
        assert "monthly_cost" in summary
        assert "total_cost" in summary
        assert "by_model" in summary
        assert "by_provider" in summary
        assert "record_count" in summary
        assert "budget_status" in summary

    def test_alert_threshold(self):
        """Alert is raised when usage crosses alert threshold."""
        config = BudgetConfig(daily_limit=0.01, alert_threshold=0.5, enforce=True)
        tracker = CostTracker(config)
        pricing = _make_pricing(input_per_1k=0.01, output_per_1k=0.03)

        # Record enough to cross 50% of 0.01 limit
        tracker.record("model-a", "provider-a", _make_usage(prompt=500, completion=0), pricing)

        status = tracker.check_budget()
        assert status.alert is True
