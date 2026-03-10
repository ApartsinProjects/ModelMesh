"""Tutorial 3: Time-of-day routing with a custom rotation policy.

Shows how to subclass BaseRotationPolicy and override should_deactivate
and select to implement time-based routing logic. During peak hours
(09:00-17:00), the policy prefers cheaper models. Outside peak hours,
it selects by lowest error rate (the default).
"""

from datetime import datetime

from modelmesh.cdk import BaseRotationPolicy, BaseRotationPolicyConfig
from modelmesh.cdk.helpers import mock_model_snapshot, mock_completion_request
from modelmesh.interfaces.rotation_policy import (
    CompletionRequest,
    DeactivationReason,
    ModelSnapshot,
    ModelStatus,
    SelectionResult,
)


class TimeOfDayRotationPolicy(BaseRotationPolicy):
    """Rotation policy that routes based on time of day.

    During peak hours (09:00-17:00 UTC), prefers cheaper models to
    control costs. Outside peak hours, uses the default selection
    strategy (priority list with error-rate fallback).

    Also deactivates models that have accumulated more than a
    configurable cost during peak hours.
    """

    def __init__(
        self,
        config: BaseRotationPolicyConfig,
        peak_budget: float = 5.0,
        cheap_models: list[str] | None = None,
    ) -> None:
        super().__init__(config)
        self._peak_budget = peak_budget
        self._cheap_models = cheap_models or []

    def _is_peak_hours(self) -> bool:
        """Return True if current UTC hour is within peak range."""
        hour = datetime.utcnow().hour
        return 9 <= hour < 17

    def should_deactivate(self, snapshot: ModelSnapshot) -> bool:
        """Deactivate expensive models during peak hours when over budget."""
        # Always check base thresholds first
        if super().should_deactivate(snapshot):
            return True

        # During peak hours, enforce tighter budget on non-cheap models
        if self._is_peak_hours():
            if snapshot.model_id not in self._cheap_models:
                if snapshot.total_cost >= self._peak_budget:
                    return True

        return False

    def score(self, candidate: ModelSnapshot, request: CompletionRequest) -> float:
        """Score candidates: prefer cheap models during peak hours."""
        base_score = super().score(candidate, request)

        if self._is_peak_hours() and candidate.model_id in self._cheap_models:
            # Boost cheap models during peak hours
            return base_score + 100.0

        return base_score


def main() -> None:
    policy = TimeOfDayRotationPolicy(
        config=BaseRotationPolicyConfig(
            failure_threshold=5,
            error_rate_threshold=0.5,
            cooldown_seconds=60,
            model_priority=["gpt-4o", "gpt-3.5-turbo"],
        ),
        peak_budget=5.0,
        cheap_models=["gpt-3.5-turbo"],
    )

    # Create test snapshots
    gpt4 = mock_model_snapshot(
        model_id="gpt-4o",
        provider_id="openai",
    )
    gpt35 = mock_model_snapshot(
        model_id="gpt-3.5-turbo",
        provider_id="openai",
    )

    # Test deactivation
    print(f"GPT-4o deactivate? {policy.should_deactivate(gpt4)}")
    print(f"GPT-3.5 deactivate? {policy.should_deactivate(gpt35)}")

    # Test selection
    request = mock_completion_request(model="gpt-4o")
    candidates = [gpt4, gpt35]
    result = policy.select(candidates, request)
    print(f"\nSelected: {result.model_id} (score={result.score:.1f}, "
          f"reason={result.reason})")

    # Show scores for both candidates
    for c in candidates:
        print(f"  {c.model_id}: score={policy.score(c, request):.1f}")

    # Test recovery
    standby = mock_model_snapshot(
        model_id="gpt-4o",
        status=ModelStatus.STANDBY,
        failure_count=0,
    )
    print(f"\nStandby model recover? {policy.should_recover(standby)}")


if __name__ == "__main__":
    main()
