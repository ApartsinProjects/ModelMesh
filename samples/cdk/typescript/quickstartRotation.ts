/**
 * Quickstart: Create a BaseRotationPolicy and test deactivation logic.
 *
 * Demonstrates how the threshold-based rotation policy decides whether a
 * model should be deactivated based on its failure count and error rate.
 */

import {
    BaseRotationPolicy,
    BaseRotationConfig,
    ModelState,
    ModelStatus,
    DeactivationReason,
    createDefaultModelState,
} from "@nistrapa/modelmesh-core";

function main(): void {
    const policy = new BaseRotationPolicy({
        failureThreshold: 5,
        errorRateThreshold: 0.3,
        cooldownSeconds: 120,
    });

    const healthy = createDefaultModelState({ modelId: "gpt-4o", failureCount: 0 });
    console.log(`Healthy model deactivate? ${policy.shouldDeactivate(healthy)}`);  // false

    const failing = createDefaultModelState({ modelId: "gpt-4o", failureCount: 6 });
    console.log(`Failing model deactivate? ${policy.shouldDeactivate(failing)}`);  // true
    console.log(`Reason: ${policy.getReason(failing)}`);  // ERROR_THRESHOLD
}

main();
