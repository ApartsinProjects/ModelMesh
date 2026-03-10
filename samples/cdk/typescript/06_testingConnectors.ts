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
    ModelStatus,
    mockCompletionRequest,
    mockModelSnapshot,
} from "@modelmesh/cdk";

// -- Example 1: Using MockHttpClient with a provider --------------------------

async function testProviderWithMock(): Promise<void> {
    console.log("=== Testing Provider with MockHttpClient ===\n");

    const mockClient = new MockHttpClient();

    // Enqueue a canned completion response
    mockClient.addResponse({
        statusCode: 200,
        body: {
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
        },
    });

    // Verify recorded requests
    await mockClient.post("/v1/chat/completions", { model: "gpt-4o" });
    console.log(`Recorded ${mockClient.calls.length} request(s)`);
    console.log(`  Method: ${mockClient.calls[0]["method"]}`);
    console.log(`  URL:    ${mockClient.calls[0]["url"]}`);
    console.log(`  Body:   ${JSON.stringify(mockClient.calls[0]["json"])}`);
}

// -- Example 2: Using mock factories -----------------------------------------

function testMockFactories(): void {
    console.log("\n=== Testing Mock Factories ===\n");

    // Create a healthy model snapshot
    const healthy = mockModelSnapshot();
    console.log(`Healthy: model=${healthy.model_id}, failures=${healthy.failure_count}`);

    // Create a failing model snapshot
    const failing = mockModelSnapshot({ failureCount: 10 });
    console.log(
        `Failing: model=${failing.model_id}, failures=${failing.failure_count}`
    );

    // Create a standby model
    const standby = mockModelSnapshot({
        status: ModelStatus.STANDBY,
    });
    console.log(
        `Standby: model=${standby.model_id}, ` +
        `status=${standby.status}`
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

async function testProviderWithHarness(): Promise<void> {
    console.log("\n=== Testing Provider with Harness ===\n");

    const mockClient = new MockHttpClient();
    mockClient.addResponse({
        statusCode: 200,
        body: {
            id: "chatcmpl-test-456",
            model: "gpt-4o",
            choices: [
                {
                    index: 0,
                    message: { role: "assistant", content: "Test response." },
                    finish_reason: "stop",
                },
            ],
            usage: {
                prompt_tokens: 10,
                completion_tokens: 5,
                total_tokens: 15,
            },
        },
    });

    const provider = new OpenAICompatibleProvider({
        baseUrl: "https://api.openai.com",
        apiKey: "sk-test",
        models: [
            {
                id: "gpt-4o",
                name: "GPT-4o",
                capabilities: ["generation.text-generation.chat-completion"],
                context_window: 128_000,
                max_output_tokens: 16_384,
            },
        ],
    });

    const harness = new ConnectorTestHarness(provider);

    // Use the harness to test complete and stream
    const response = await harness.complete(mockCompletionRequest({ model: "gpt-4o" }));
    console.log(`  complete() response id: ${response.id}`);

    console.log("  Harness complete/stream tests exercised successfully.");
}

// -- Main ---------------------------------------------------------------------

async function main(): Promise<void> {
    await testProviderWithMock();
    testMockFactories();
    await testProviderWithHarness();

    console.log("\n=== All test examples completed ===");
}

main().catch(console.error);
