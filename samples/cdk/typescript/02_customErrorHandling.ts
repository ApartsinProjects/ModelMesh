/**
 * Tutorial 2: Custom error classification by overriding classifyError.
 *
 * Shows how to subclass BaseProvider and override the classifyError method
 * to implement provider-specific error handling logic. In this example, a
 * custom provider treats HTTP 418 as a rate-limit signal and HTTP 422 as a
 * non-retryable validation error.
 */

import {
    BaseProvider,
    BaseProviderConfig,
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    HttpError,
    ModelInfo,
} from "@modelmesh/cdk";

/**
 * Provider with custom error classification logic.
 *
 * Overrides classifyError to handle provider-specific HTTP codes:
 * - 418: Treated as a rate-limit signal (retryable with backoff)
 * - 422: Treated as a validation error (non-retryable)
 * - 529: Treated as an overloaded signal (retryable)
 */
class CustomErrorProvider extends BaseProvider {
    classifyError(error: Error): ErrorClassification {
        const statusCode = (error as HttpError).statusCode;

        if (statusCode === 418) {
            // This provider uses 418 to signal rate limiting
            return {
                retryable: true,
                category: "rate_limit",
            };
        }

        if (statusCode === 422) {
            // Validation errors should not be retried
            return {
                retryable: false,
                category: "client_error",
            };
        }

        if (statusCode === 529) {
            // Provider-specific "overloaded" code
            return {
                retryable: true,
                category: "server_error",
            };
        }

        // Fall back to default classification for all other codes
        return super.classifyError(error);
    }
}

async function main(): Promise<void> {
    const provider = new CustomErrorProvider({
        baseUrl: "https://custom-api.example.com",
        apiKey: "sk-custom-key",
        models: [
            {
                id: "custom-model-v1",
                name: "Custom Model v1",
                capabilities: ["generation.text-generation.chat-completion"],
                context_window: 32_000,
                max_output_tokens: 4_096,
            },
        ],
    });

    // Test custom error codes
    const codes = [418, 422, 429, 500, 529];
    for (const code of codes) {
        const err = new HttpError(code, `HTTP ${code}`);
        const result = provider.classifyError(err);
        console.log(
            `HTTP ${code}: retryable=${result.retryable}, ` +
            `category=${result.category}`
        );
    }

    console.log(`\nIs HTTP 418 retryable? ${provider.isRetryable(new HttpError(418, ""))}`);
    console.log(`Is HTTP 422 retryable? ${provider.isRetryable(new HttpError(422, ""))}`);

    await provider.close();
}

main().catch(console.error);
