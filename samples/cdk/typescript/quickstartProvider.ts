/**
 * Quickstart: Create an OpenAI-compatible provider and call complete().
 *
 * Demonstrates the simplest way to create a provider connector using the
 * OpenAICompatibleProvider specialized class with a BaseProviderConfig.
 */

import {
    OpenAICompatibleProvider,
    BaseProviderConfig,
    CompletionRequest,
    ModelInfo,
    createDefaultModelInfo,
    createDefaultCompletionRequest,
} from "@nistrapa/modelmesh-core";

async function main(): Promise<void> {
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
                features: { tool_calling: true },
                contextWindow: 128_000,
                maxOutputTokens: 16_384,
            }),
        ],
    });

    const request: CompletionRequest = createDefaultCompletionRequest({
        model: "gpt-4o",
        messages: [{ role: "user", content: "Say hello!" }],
    });

    const response = await provider.complete(request);
    console.log(`Response: ${response.choices[0]?.message?.content}`);
    console.log(`Tokens used: ${response.usage.totalTokens}`);

    await provider.close();
}

main().catch(console.error);
