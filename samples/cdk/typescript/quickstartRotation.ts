/**
 * Quickstart: Create a ThresholdRotationPolicy and test deactivation logic.
 *
 * Demonstrates how the threshold-based rotation policy decides whether a
 * model should be deactivated based on its failure count and error rate.
 */

import {
    ThresholdRotationPolicy,
    BaseRotationPolicyConfig,
    ModelSnapshot,
    ModelStatus,
    DeactivationReason,
    mockModelSnapshot,
} from "@modelmesh/cdk";

function main(): void {
    const policy = new ThresholdRotationPolicy({
        failureThreshold: 5,
        errorRateThreshold: 0.3,
        cooldownSeconds: 120,
    });

    const healthy = mockModelSnapshot({ failureCount: 0 });
    console.log(`Healthy model deactivate? ${policy.shouldDeactivate(healthy)}`);  // false

    const failing = mockModelSnapshot({ failureCount: 6 });
    console.log(`Failing model deactivate? ${policy.shouldDeactivate(failing)}`);  // true
    console.log(`Reason: ${policy.getReason(failing)}`);  // ERROR_THRESHOLD
}

main();
