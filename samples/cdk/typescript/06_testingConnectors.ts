/**
 * Tutorial 6: Test harness usage with MockHttpClient and ConnectorTestHarness.
 *
 * Demonstrates how to use the CDK's test utilities to validate connector
 * implementations without making real HTTP calls. Covers:
 * - MockHttpClient for canned responses
 * - mockModelSnapshot and mockCompletionRequest factories
 * - ConnectorTestHarness for interface compliance testing
 */

import {
    BaseObservabilityConfig,
    BaseProviderConfig,
    BaseRotationPolicyConfig,
    ConsoleObservability,
    KeyValueStorage,
    KeyValueStorageConfig,
    OpenAICompatibleProvider,
    ThresholdRotationPolicy,
    ModelInfo,
    ConnectorTestHarness,
    MockHttpClient,
    mockCompletionRequest,
    mockModelSnapshot,
} from "@modelmesh/cdk";

// -- Example 1: Using MockHttpClient with a provider --------------------------

async function testProviderWithMock(): Promise<void> {
    console.log("=== Testing Provider with MockHttpClient ===\n");

    const mockClient = new MockHttpClient();

    // Enqueue a canned completion response
    mockClient.addResponse("/v1/chat/completions", {
        id: "chatcmpl-test-123",
        model: "gpt-4o",
        choices: [
            {
                index: 0,
                message: { role: "assistant", content: "Hello!" },
                finish_reason: "stop",
            },
        ],
        usage: {
            prompt_tokens: 10,
            completion_tokens: 5,
            total_tokens: 15,
        },
    });

    // Enqueue a streaming response
    mockClient.addStreamResponse("/v1/chat/completions", [
        '{"id":"chunk-1","model":"gpt-4o","choices":[{"delta":{"content":"Hi"}}]}',
        '{"id":"chunk-2","model":"gpt-4o","choices":[{"delta":{"content":"!"}}]}',
    ]);

    // Verify recorded requests
    await mockClient.post("/v1/chat/completions", { model: "gpt-4o" });
    console.log(`Recorded ${mockClient.requests.length} request(s)`);
    console.log(`  Method: ${mockClient.requests[0].method}`);
    console.log(`  Path:   ${mockClient.requests[0].path}`);
    console.log(`  Body:   ${JSON.stringify(mockClient.requests[0].json)}`);
}

// -- Example 2: Using mock factories -----------------------------------------

function testMockFactories(): void {
    console.log("\n=== Testing Mock Factories ===\n");

    // Create a healthy model snapshot
    const healthy = mockModelSnapshot();
    console.log(`Healthy: model=${healthy.model_id}, failures=${healthy.failure_count}`);

    // Create a failing model snapshot
    const failing = mockModelSnapshot({ failureCount: 10, errorRate: 0.9 });
    console.log(
        `Failing: model=${failing.model_id}, failures=${failing.failure_count}, ` +
        `error_rate=${failing.error_rate}`
    );

    // Create a standby model
    const standby = mockModelSnapshot({
        status: "standby",
        cooldownRemaining: 30.0,
    });
    console.log(
        `Standby: model=${standby.model_id}, ` +
        `cooldown=${standby.cooldown_remaining}s`
    );

    // Create a minimal completion request
    const simple = mockCompletionRequest();
    console.log(
        `\nRequest: model=${simple.model}, ` +
        `messages=${simple.messages.length} msg(s)`
    );

    // Create a streaming request with custom parameters
    const streaming = mockCompletionRequest({
        model: "gpt-3.5-turbo",
        stream: true,
        temperature: 0.5,
        maxTokens: 100,
    });
    console.log(`Streaming: model=${streaming.model}, stream=${streaming.stream}`);
}

// -- Example 3: ConnectorTestHarness ------------------------------------------

async function testRotationWithHarness(): Promise<void> {
    console.log("\n=== Testing Rotation Policy with Harness ===\n");

    const policy = new ThresholdRotationPolicy({
        retryLimit: 5,
        errorRateThreshold: 0.5,
        cooldownSeconds: 60,
        modelPriority: ["gpt-4", "gpt-3.5-turbo"],
    });

    const harness = new ConnectorTestHarness();

    // Run individual tests
    try {
        await harness.testRotationDeactivation(policy);
        console.log("  test_rotation_deactivation: PASSED");
    } catch (err) {
        console.log(`  test_rotation_deactivation: FAILED - ${err}`);
    }

    try {
        await harness.testRotationRecovery(policy);
        console.log("  test_rotation_recovery: PASSED");
    } catch (err) {
        console.log(`  test_rotation_recovery: FAILED - ${err}`);
    }

    try {
        await harness.testRotationSelection(policy);
        console.log("  test_rotation_selection: PASSED");
    } catch (err) {
        console.log(`  test_rotation_selection: FAILED - ${err}`);
    }

    // Print summary
    console.log(`\nResults: ${Object.keys(harness.results).length} test(s)`);
    for (const [name, [passed, msg]] of Object.entries(harness.results)) {
        const status = passed ? "PASS" : "FAIL";
        console.log(`  [${status}] ${name}: ${msg}`);
    }
}

async function testStorageWithHarness(): Promise<void> {
    console.log("\n=== Testing Storage with Harness ===\n");

    const storage = new KeyValueStorage({
        backend: "memory",
        format: "json",
    });

    const harness = new ConnectorTestHarness();

    try {
        await harness.testStorageCrud(storage);
        console.log("  test_storage_crud: PASSED");
    } catch (err) {
        console.log(`  test_storage_crud: FAILED - ${err}`);
    }

    for (const [name, [passed, msg]] of Object.entries(harness.results)) {
        const status = passed ? "PASS" : "FAIL";
        console.log(`  [${status}] ${name}: ${msg}`);
    }
}

async function testObservabilityWithHarness(): Promise<void> {
    console.log("\n=== Testing Observability with Harness ===\n");

    const obs = new ConsoleObservability({
        logLevel: "summary",
        redactSecrets: true,
    });

    const harness = new ConnectorTestHarness();

    try {
        await harness.testObservabilityEmitLogFlush(obs);
        console.log("  test_observability_emit_log_flush: PASSED");
    } catch (err) {
        console.log(`  test_observability_emit_log_flush: FAILED - ${err}`);
    }

    for (const [name, [passed, msg]] of Object.entries(harness.results)) {
        const status = passed ? "PASS" : "FAIL";
        console.log(`  [${status}] ${name}: ${msg}`);
    }
}

// -- Example 4: Run all tests via runAll --------------------------------------

async function testRunAll(): Promise<void> {
    console.log("\n=== Batch Testing with runAll ===\n");

    const policy = new ThresholdRotationPolicy({
        retryLimit: 5,
        errorRateThreshold: 0.5,
        cooldownSeconds: 60,
        modelPriority: ["gpt-4", "gpt-3.5-turbo"],
    });

    const harness = new ConnectorTestHarness();
    const results = await harness.runAll(policy, "rotation");

    console.log(`Ran ${Object.keys(results).length} test(s) for rotation policy:`);
    for (const [name, [passed, msg]] of Object.entries(results)) {
        const status = passed ? "PASS" : "FAIL";
        console.log(`  [${status}] ${name}: ${msg}`);
    }
}

// -- Main ---------------------------------------------------------------------

async function main(): Promise<void> {
    await testProviderWithMock();
    testMockFactories();
    await testRotationWithHarness();
    await testStorageWithHarness();
    await testObservabilityWithHarness();
    await testRunAll();

    console.log("\n=== All test examples completed ===");
}

main().catch(console.error);
