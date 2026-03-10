/**
 * Tutorial 6: Testing connectors with factory helpers.
 *
 * Demonstrates how to use the CDK's factory functions to create test data
 * for validating connector implementations without making real HTTP calls.
 * Covers:
 * - createDefaultModelState for building model state snapshots
 * - createDefaultCompletionRequest for building completion requests
 * - createDefaultModelInfo for building model catalogue entries
 * - Using BaseRotationPolicy with test data
 * - Using BaseProvider / OpenAICompatibleProvider for unit testing
 */

import {
    BaseProviderConfig,
    BaseRotationPolicy,
    BaseRotationConfig,
    OpenAICompatibleProvider,
    ModelInfo,
    ModelState,
    ModelStatus,
    CompletionRequest,
    createDefaultModelState,
    createDefaultCompletionRequest,
    createDefaultModelInfo,
    createDefaultTokenUsage,
} from "@nistrapa/modelmesh-core";

// -- Example 1: Using factory functions to create test data --------------------

function testFactoryFunctions(): void {
    console.log("=== Testing Factory Functions ===\n");

    // Create a healthy model state
    const healthy = createDefaultModelState({ modelId: "gpt-4o" });
    console.log(`Healthy: model=${healthy.modelId}, failures=${healthy.failureCount}`);

    // Create a failing model state
    const failing = createDefaultModelState({
        modelId: "gpt-4o",
        failureCount: 10,
        errorRate: 0.5,
    });
    console.log(`Failing: model=${failing.modelId}, failures=${failing.failureCount}`);

    // Create a standby model
    const standby = createDefaultModelState({
        modelId: "gpt-4o",
        status: ModelStatus.STANDBY,
    });
    console.log(`Standby: model=${standby.modelId}, status=${standby.status}`);

    // Create a minimal completion request
    const simple = createDefaultCompletionRequest({
        model: "gpt-4o",
        messages: [{ role: "user", content: "Hello!" }],
    });
    console.log(`\nRequest: model=${simple.model}, messages=${simple.messages.length} msg(s)`);

    // Create a streaming request with custom parameters
    const streaming = createDefaultCompletionRequest({
        model: "gpt-3.5-turbo",
        messages: [{ role: "user", content: "Stream this" }],
        stream: true,
        temperature: 0.5,
        maxTokens: 100,
    });
    console.log(`Streaming: model=${streaming.model}, stream=${streaming.stream}`);

    // Create model info entries
    const modelInfo = createDefaultModelInfo({
        id: "test-model",
        name: "Test Model",
        capabilities: ["generation.text-generation.chat-completion"],
        contextWindow: 128_000,
        maxOutputTokens: 16_384,
    });
    console.log(`\nModelInfo: ${modelInfo.id}, context=${modelInfo.contextWindow}`);

    // Create token usage
    const usage = createDefaultTokenUsage({
        promptTokens: 100,
        completionTokens: 50,
    });
    console.log(`TokenUsage: prompt=${usage.promptTokens}, completion=${usage.completionTokens}, total=${usage.totalTokens}`);
}

// -- Example 2: Testing rotation policy with mock data -------------------------

function testRotationPolicy(): void {
    console.log("\n=== Testing Rotation Policy ===\n");

    const policy = new BaseRotationPolicy({
        failureThreshold: 5,
        errorRateThreshold: 0.3,
        cooldownSeconds: 120,
        modelPriority: ["gpt-4o", "gpt-3.5-turbo"],
    });

    // Test deactivation with a healthy model
    const healthy = createDefaultModelState({
        modelId: "gpt-4o",
        failureCount: 0,
    });
    console.log(`Healthy deactivate? ${policy.shouldDeactivate(healthy)}`);  // false

    // Test deactivation with a failing model
    const failing = createDefaultModelState({
        modelId: "gpt-4o",
        failureCount: 6,
    });
    console.log(`Failing deactivate? ${policy.shouldDeactivate(failing)}`);  // true
    console.log(`Reason: ${policy.getReason(failing)}`);  // ERROR_THRESHOLD

    // Test selection
    const candidates = [
        createDefaultModelState({ modelId: "gpt-4o", providerId: "openai" }),
        createDefaultModelState({ modelId: "gpt-3.5-turbo", providerId: "openai" }),
    ];
    const request = createDefaultCompletionRequest({
        model: "gpt-4o",
        messages: [{ role: "user", content: "Test" }],
    });
    const selected = policy.select(candidates, request);
    if (selected) {
        console.log(`Selected: ${selected.modelId}`);
    }

    // Show scores
    for (const c of candidates) {
        console.log(`  ${c.modelId}: score=${policy.score(c, request).toFixed(1)}`);
    }

    // Test recovery
    const standby = createDefaultModelState({
        modelId: "gpt-4o",
        status: ModelStatus.STANDBY,
    });
    console.log(`\nStandby recover? ${policy.shouldRecover(standby)}`);  // true (no cooldown set)
}

// -- Example 3: Testing a provider's catalogue and error handling --------------

function testProviderCatalogue(): void {
    console.log("\n=== Testing Provider Catalogue ===\n");

    const provider = new OpenAICompatibleProvider({
        baseUrl: "https://api.openai.com",
        apiKey: "sk-test",
        timeout: 30,
        maxRetries: 3,
        authMethod: "api_key",
        retryableCodes: [429, 500, 502, 503],
        nonRetryableCodes: [400, 401, 403],
        capabilities: ["generation.text-generation.chat-completion"],
        models: [
            createDefaultModelInfo({
                id: "gpt-4o",
                name: "GPT-4o",
                capabilities: ["generation.text-generation.chat-completion"],
                contextWindow: 128_000,
                maxOutputTokens: 16_384,
            }),
            createDefaultModelInfo({
                id: "gpt-4o-mini",
                name: "GPT-4o Mini",
                capabilities: ["generation.text-generation.chat-completion"],
                contextWindow: 128_000,
                maxOutputTokens: 16_384,
            }),
        ],
    });

    // List models
    const models = provider.listModels();
    console.log(`Models: ${models.map(m => m.id).join(", ")}`);

    // Get model info
    const info = provider.getModelInfo("gpt-4o");
    console.log(`GPT-4o context: ${info.contextWindow}`);

    // Test capabilities
    console.log(`Supports chat? ${provider.supports("generation.text-generation.chat-completion")}`);
    console.log(`Supports embeddings? ${provider.supports("representation.embeddings.text-embeddings")}`);

    // Test error classification
    const error = new Error("Connection refused");
    const classification = provider.classifyError(error);
    console.log(`\nError classification: retryable=${classification.retryable}, category=${classification.category}`);

    // Test quota
    const quota = provider.checkQuota();
    console.log(`Quota used: ${quota.used}`);
}

// -- Main ---------------------------------------------------------------------

async function main(): Promise<void> {
    testFactoryFunctions();
    testRotationPolicy();
    testProviderCatalogue();

    console.log("\n=== All test examples completed ===");
}

main().catch(console.error);
