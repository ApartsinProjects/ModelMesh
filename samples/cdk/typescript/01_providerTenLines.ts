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
} from "@modelmesh/cdk";

async function main(): Promise<void> {
    // -- Step 1: Configure the provider --
    const provider = new OpenAICompatibleProvider({
        baseUrl: "https://api.openai.com",
        apiKey: "sk-your-api-key",
        timeout: 30,
        maxRetries: 3,
        capabilities: ["generation.text-generation.chat-completion"],
        models: [
            {
                id: "gpt-4o",
                name: "GPT-4o",
                capabilities: ["generation.text-generation.chat-completion"],
                features: { tool_calling: true, vision: true, system_prompt: true },
                context_window: 128_000,
                max_output_tokens: 16_384,
                pricing: {
                    input_per_1k_tokens: 0.0025,
                    output_per_1k_tokens: 0.01,
                },
            },
        ],
    });

    // -- Step 2: Inspect capabilities and catalogue --
    console.log(`Capabilities: ${provider.getCapabilities()}`);
    console.log(`Supports chat? ${provider.supports("generation.text-generation.chat-completion")}`);

    const models: ModelInfo[] = await provider.listModels();
    for (const model of models) {
        console.log(`Model: ${model.id} (${model.name}), context: ${model.context_window}`);
    }

    // -- Step 3: Send a completion request --
    const request: CompletionRequest = {
        model: "gpt-4o",
        messages: [
            { role: "system", content: "You are a helpful assistant." },
            { role: "user", content: "What is ModelMesh?" },
        ],
        temperature: 0.7,
        max_tokens: 256,
    };

    const response: CompletionResponse = await provider.complete(request);

    // -- Step 4: Inspect the response --
    console.log(`\nResponse ID: ${response.id}`);
    console.log(`Model: ${response.model}`);
    console.log(`Content: ${response.choices[0]}`);
    console.log(
        `Tokens: prompt=${response.usage.prompt_tokens}, ` +
        `completion=${response.usage.completion_tokens}, ` +
        `total=${response.usage.total_tokens}`
    );

    // -- Step 5: Check quota after usage --
    const quota = await provider.checkQuota();
    console.log(`\nRequests used: ${quota.used}`);

    const pricing: ModelPricing = await provider.getPricing("gpt-4o");
    console.log(
        `Pricing: $${pricing.input_per_1k_tokens}/1k input tokens, ` +
        `$${pricing.output_per_1k_tokens}/1k output tokens`
    );

    await provider.close();
}

main().catch(console.error);
