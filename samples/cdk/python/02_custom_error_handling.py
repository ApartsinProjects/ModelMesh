"""Tutorial 2: Custom error classification by overriding _classify_error.

Shows how to subclass BaseProvider and override the classify_error method
to implement provider-specific error handling logic. In this example, a
custom provider treats HTTP 418 as a rate-limit signal and HTTP 422 as a
non-retryable validation error.
"""

import asyncio

from modelmesh.cdk import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ErrorClassification,
    ModelInfo,
    TokenUsage,
)


class CustomErrorProvider(BaseProvider):
    """Provider with custom error classification logic.

    Overrides classify_error to handle provider-specific HTTP codes:
    - 418: Treated as a rate-limit signal (retryable with backoff)
    - 422: Treated as a validation error (non-retryable)
    - 529: Treated as an overloaded signal (retryable)
    """

    def classify_error(self, error: Exception) -> ErrorClassification:
        status_code = getattr(
            getattr(error, "response", None), "status_code", None
        )

        if status_code == 418:
            # This provider uses 418 to signal rate limiting
            return ErrorClassification(
                retryable=True,
                category="rate_limit",
            )

        if status_code == 422:
            # Validation errors should not be retried
            return ErrorClassification(
                retryable=False,
                category="client_error",
            )

        if status_code == 529:
            # Provider-specific "overloaded" code
            return ErrorClassification(
                retryable=True,
                category="server_error",
            )

        # Fall back to default classification for all other codes
        return super().classify_error(error)


async def main() -> None:
    provider = CustomErrorProvider(BaseProviderConfig(
        base_url="https://custom-api.example.com",
        api_key="sk-custom-key",
        models=[ModelInfo(
            id="custom-model-v1",
            name="Custom Model v1",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=32_000,
            max_output_tokens=4_096,
        )],
    ))

    # Demonstrate error classification without making real HTTP calls
    class FakeResponse:
        def __init__(self, status_code: int):
            self.status_code = status_code

    class FakeError(Exception):
        def __init__(self, status_code: int):
            self.response = FakeResponse(status_code)

    # Test custom error codes
    for code in [418, 422, 429, 500, 529]:
        err = FakeError(code)
        result = provider.classify_error(err)
        print(f"HTTP {code}: retryable={result.retryable}, "
              f"category={result.category}")

    print(f"\nIs HTTP 418 retryable? {provider.is_retryable(FakeError(418))}")
    print(f"Is HTTP 422 retryable? {provider.is_retryable(FakeError(422))}")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
