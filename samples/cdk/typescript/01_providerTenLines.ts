/**
 * Tutorial 1: Full working provider in minimal code.
 *
 * Shows how to create an OpenAI-compatible provider, configure it with
 * a model catalogue, send a chat completion request, and inspect the
 * response -- all using the CDK's zero-code specialized class.
 *
 * This is the simplest possible provider setup: instantiate
 * OpenAICompatibleProvider with a BaseProviderConfig, call complete(),
 * and read the result.
 */

import {
    OpenAICompatibleProvider,
    BaseProviderConfig,
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    ModelPricing,
    createDefaultModelInfo,
    createDefaultCompletionRequest,
} from "@modelmesh/core";

async function main(): Promise<void> {
    // -- Step 1: Configure the provider --
    const provider = new OpenAICompatibleProvider({
        baseUrl: "https://api.openai.com",
        apiKey: "sk-your-api-key",
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
                features: { tool_calling: true, vision: true, system_prompt: true },
                contextWindow: 128_000,
                maxOutputTokens: 16_384,
                pricing: {
                    inputPer1kTokens: 0.0025,
                    outputPer1kTokens: 0.01,
                    perRequest: 0,
                },
            }),
        ],
    });

    // -- Step 2: Inspect capabilities and catalogue --
    console.log(`Capabilities: ${provider.getCapabilities()}`);
    console.log(`Supports chat? ${provider.supports("generation.text-generation.chat-completion")}`);

    const models: ModelInfo[] = provider.listModels();
    for (const model of models) {
        console.log(`Model: ${model.id} (${model.name}), context: ${model.contextWindow}`);
    }

    // -- Step 3: Send a completion request --
    const request: CompletionRequest = createDefaultCompletionRequest({
        model: "gpt-4o",
        messages: [
            { role: "system", content: "You are a helpful assistant." },
            { role: "user", content: "What is ModelMesh?" },
        ],
        temperature: 0.7,
        maxTokens: 256,
    });

    const response: CompletionResponse = await provider.complete(request);

    // -- Step 4: Inspect the response --
    console.log(`\nResponse ID: ${response.id}`);
    console.log(`Model: ${response.model}`);
    console.log(`Content: ${response.choices[0]?.message?.content}`);
    console.log(
        `Tokens: prompt=${response.usage.promptTokens}, ` +
        `completion=${response.usage.completionTokens}, ` +
        `total=${response.usage.totalTokens}`
    );

    // -- Step 5: Check quota after usage --
    const quota = provider.checkQuota();
    console.log(`\nRequests used: ${quota.used}`);

    const pricing: ModelPricing = provider.getPricing("gpt-4o");
    console.log(
        `Pricing: $${pricing.inputPer1kTokens}/1k input tokens, ` +
        `$${pricing.outputPer1kTokens}/1k output tokens`
    );

    await provider.close();
}

main().catch(console.error);
