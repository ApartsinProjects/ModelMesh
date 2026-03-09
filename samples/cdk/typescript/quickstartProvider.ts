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
} from "@modelmesh/cdk";

async function main(): Promise<void> {
    const provider = new OpenAICompatibleProvider({
        baseUrl: "https://api.openai.com",
        apiKey: "sk-your-api-key",
        models: [
            {
                id: "gpt-4o",
                name: "GPT-4o",
                capabilities: ["generation.text-generation.chat-completion"],
                features: { tool_calling: true },
                context_window: 128_000,
                max_output_tokens: 16_384,
            },
        ],
    });

    const request: CompletionRequest = {
        model: "gpt-4o",
        messages: [{ role: "user", content: "Say hello!" }],
    };

    const response = await provider.complete(request);
    console.log(`Response: ${response.choices[0]}`);
    console.log(`Tokens used: ${response.usage.total_tokens}`);

    await provider.close();
}

main().catch(console.error);
