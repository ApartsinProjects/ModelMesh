/**
 * Tutorial 4: Azure OpenAI provider by extending OpenAICompatibleProvider.
 *
 * Shows how to derive from an existing pre-shipped connector (the OpenAI
 * provider) and make minimal modifications for Azure-hosted deployments.
 * Only the endpoint URL construction and header format differ from
 * standard OpenAI.
 */

import {
    OpenAICompatibleProvider,
    BaseProviderConfig,
    CompletionRequest,
    ModelInfo,
    createDefaultModelInfo,
} from "@modelmesh/core";

/**
 * OpenAI-compatible provider adapted for Azure deployments.
 *
 * Azure OpenAI uses a different URL pattern and authentication header
 * compared to the standard OpenAI API. This subclass overrides only
 * the two methods that differ:
 * - _getCompletionEndpoint: constructs the Azure deployment URL
 * - _buildHeaders: uses the 'api-key' header instead of Bearer token
 *
 * Everything else (request/response translation, streaming, error
 * classification, retry logic) is inherited.
 */
class AzureOpenAIProvider extends OpenAICompatibleProvider {
    private resource: string;
    private deployment: string;
    private azureApiVersion: string;

    constructor(
        config: BaseProviderConfig,
        resource: string,
        deployment: string,
        apiVersion: string = "2024-02-01",
    ) {
        super(config);
        this.resource = resource;
        this.deployment = deployment;
        this.azureApiVersion = apiVersion;
    }

    /** Construct the Azure OpenAI deployment endpoint URL. */
    protected _getCompletionEndpoint(): string {
        return (
            `https://${this.resource}.openai.azure.com` +
            `/openai/deployments/${this.deployment}` +
            `/chat/completions?api-version=${this.azureApiVersion}`
        );
    }

    /** Build Azure-specific headers using the api-key header. */
    protected _buildHeaders(): Record<string, string> {
        return {
            "Content-Type": "application/json",
            "api-key": this._config.apiKey,
        };
    }
}

async function main(): Promise<void> {
    // Configure for an Azure OpenAI deployment
    const provider = new AzureOpenAIProvider(
        {
            baseUrl: "https://my-resource.openai.azure.com",
            apiKey: "your-azure-api-key",
            timeout: 30,
            maxRetries: 3,
            authMethod: "api_key",
            retryableCodes: [429, 500, 502, 503],
            nonRetryableCodes: [400, 401, 403],
            capabilities: ["generation.text-generation.chat-completion"],
            models: [
                createDefaultModelInfo({
                    id: "gpt-4o",
                    name: "GPT-4o (Azure)",
                    capabilities: ["generation.text-generation.chat-completion"],
                    features: { tool_calling: true },
                    contextWindow: 128_000,
                    maxOutputTokens: 16_384,
                }),
            ],
        },
        "my-resource",
        "gpt-4o-deployment",
        "2024-02-01",
    );

    // Verify the endpoint URL was constructed correctly
    const endpoint = (provider as any)._getCompletionEndpoint();
    console.log(`Endpoint: ${endpoint}`);

    // Verify the headers use Azure-style auth
    const headers = (provider as any)._buildHeaders();
    console.log(`Headers: ${JSON.stringify(headers)}`);

    // Verify inherited capabilities still work
    console.log(`Capabilities: ${provider.getCapabilities()}`);
    console.log(`Supports chat? ${provider.supports("generation.text-generation.chat-completion")}`);

    const models: ModelInfo[] = provider.listModels();
    console.log(`Models: ${JSON.stringify(models.map(m => m.id))}`);

    // The complete() call would work against a real Azure deployment:
    // const response = await provider.complete({
    //     model: "gpt-4o",
    //     messages: [{ role: "user", content: "Hello from Azure!" }],
    //     temperature: 1.0,
    //     stream: false,
    //     topP: 1.0,
    // });

    await provider.close();
}

main().catch(console.error);
