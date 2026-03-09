"""Quickstart: Create a ThresholdRotationPolicy and test deactivation logic.

Demonstrates how the threshold-based rotation policy decides whether a
model should be deactivated based on its failure count and error rate.
"""

from modelmesh.cdk import ThresholdRotationPolicy, BaseRotationPolicyConfig
from modelmesh.cdk.helpers import mock_model_snapshot


def main() -> None:
    policy = ThresholdRotationPolicy(BaseRotationPolicyConfig(
        retry_limit=5,
        error_rate_threshold=0.3,
        cooldown_seconds=120,
    ))

    healthy = mock_model_snapshot(failure_count=0, error_rate=0.0)
    print(f"Healthy model deactivate? {policy.should_deactivate(healthy)}")  # False

    failing = mock_model_snapshot(failure_count=6, error_rate=0.8)
    print(f"Failing model deactivate? {policy.should_deactivate(failing)}")  # True
    print(f"Reason: {policy.get_reason(failing)}")  # ERROR_THRESHOLD


if __name__ == "__main__":
    main()
