/**
 * Tutorial 3: Time-of-day routing with a custom rotation policy.
 *
 * Shows how to subclass BaseRotationPolicy and override shouldDeactivate
 * and score to implement time-based routing logic. During peak hours
 * (09:00-17:00), the policy prefers cheaper models. Outside peak hours,
 * it selects by lowest error rate (the default).
 */

import {
    BaseRotationPolicy,
    BaseRotationConfig,
    ModelState,
    ModelStatus,
    DeactivationReason,
    CompletionRequest,
    createDefaultModelState,
    createDefaultCompletionRequest,
} from "@modelmesh/core";

/**
 * Rotation policy that routes based on time of day.
 *
 * During peak hours (09:00-17:00 UTC), prefers cheaper models to
 * control costs. Outside peak hours, uses the default selection
 * strategy (priority list with error-rate fallback).
 *
 * Also deactivates models that have accumulated more than a
 * configurable cost during peak hours.
 */
class TimeOfDayRotationPolicy extends BaseRotationPolicy {
    private peakBudget: number;
    private cheapModels: string[];

    constructor(
        config: BaseRotationConfig,
        peakBudget: number = 5.0,
        cheapModels: string[] = [],
    ) {
        super(config);
        this.peakBudget = peakBudget;
        this.cheapModels = cheapModels;
    }

    private isPeakHours(): boolean {
        /** Return true if current UTC hour is within peak range. */
        const hour = new Date().getUTCHours();
        return hour >= 9 && hour < 17;
    }

    shouldDeactivate(state: ModelState): boolean {
        /** Deactivate expensive models during peak hours when over budget. */
        // Always check base thresholds first
        if (super.shouldDeactivate(state)) {
            return true;
        }

        // During peak hours, enforce tighter budget on non-cheap models
        if (this.isPeakHours()) {
            if (!this.cheapModels.includes(state.modelId)) {
                if (state.totalCost >= this.peakBudget) {
                    return true;
                }
            }
        }

        return false;
    }

    score(candidate: ModelState, request: CompletionRequest): number {
        /** Score candidates: prefer cheap models during peak hours. */
        const baseScore = super.score(candidate, request);

        if (this.isPeakHours() && this.cheapModels.includes(candidate.modelId)) {
            // Boost cheap models during peak hours
            return baseScore + 100.0;
        }

        return baseScore;
    }
}

function main(): void {
    const policy = new TimeOfDayRotationPolicy(
        {
            failureThreshold: 5,
            errorRateThreshold: 0.5,
            cooldownSeconds: 60,
            modelPriority: ["gpt-4o", "gpt-3.5-turbo"],
        },
        5.0,
        ["gpt-3.5-turbo"],
    );

    // Create test model states
    const gpt4 = createDefaultModelState({
        modelId: "gpt-4o",
        providerId: "openai",
    });
    const gpt35 = createDefaultModelState({
        modelId: "gpt-3.5-turbo",
        providerId: "openai",
    });

    // Test deactivation
    console.log(`GPT-4o deactivate? ${policy.shouldDeactivate(gpt4)}`);
    console.log(`GPT-3.5 deactivate? ${policy.shouldDeactivate(gpt35)}`);

    // Test selection
    const request = createDefaultCompletionRequest({
        model: "gpt-4o",
        messages: [{ role: "user", content: "Hello" }],
    });
    const candidates = [gpt4, gpt35];
    const result = policy.select(candidates, request);
    if (result) {
        console.log(
            `\nSelected: ${result.modelId} (score=${policy.score(result, request).toFixed(1)})`
        );
    }

    // Show scores for both candidates
    for (const c of candidates) {
        console.log(`  ${c.modelId}: score=${policy.score(c, request).toFixed(1)}`);
    }

    // Test recovery
    const standby = createDefaultModelState({
        modelId: "gpt-4o",
        status: ModelStatus.STANDBY,
        failureCount: 0,
    });
    console.log(`\nStandby model recover? ${policy.shouldRecover(standby)}`);
}

main();
