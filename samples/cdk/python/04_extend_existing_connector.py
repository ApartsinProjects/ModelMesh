"""Tutorial 4: Azure OpenAI provider by extending OpenAICompatibleProvider.

Shows how to derive from an existing pre-shipped connector (the OpenAI
provider) and make minimal modifications for Azure-hosted deployments.
Only the endpoint URL construction and header format differ from
standard OpenAI.
"""

import asyncio

from modelmesh.cdk import OpenAICompatibleProvider, BaseProviderConfig
from modelmesh.interfaces.provider import CompletionRequest, ModelInfo


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """OpenAI-compatible provider adapted for Azure deployments.

    Azure OpenAI uses a different URL pattern and authentication header
    compared to the standard OpenAI API. This subclass overrides only
    the two methods that differ:
    - _get_completion_endpoint: constructs the Azure deployment URL
    - _build_headers: uses the 'api-key' header instead of Bearer token

    Everything else (request/response translation, streaming, error
    classification, retry logic) is inherited.
    """

    def __init__(
        self,
        config: BaseProviderConfig,
        resource: str,
        deployment: str,
        api_version: str = "2024-02-01",
    ) -> None:
        super().__init__(config)
        self._resource = resource
        self._deployment = deployment
        self._api_version = api_version

    def _get_completion_endpoint(self) -> str:
        """Construct the Azure OpenAI deployment endpoint URL."""
        return (
            f"https://{self._resource}.openai.azure.com"
            f"/openai/deployments/{self._deployment}"
            f"/chat/completions?api-version={self._api_version}"
        )

    def _build_headers(self) -> dict[str, str]:
        """Build Azure-specific headers using the api-key header."""
        return {
            "Content-Type": "application/json",
            "api-key": self._config.api_key,
        }


async def main() -> None:
    # Configure for an Azure OpenAI deployment
    provider = AzureOpenAIProvider(
        config=BaseProviderConfig(
            base_url="https://my-resource.openai.azure.com",
            api_key="your-azure-api-key",
            models=[ModelInfo(
                id="gpt-4o",
                name="GPT-4o (Azure)",
                capabilities=["generation.text-generation.chat-completion"],
                features={"tool_calling": True},
                context_window=128_000,
                max_output_tokens=16_384,
            )],
        ),
        resource="my-resource",
        deployment="gpt-4o-deployment",
        api_version="2024-02-01",
    )

    # Verify the endpoint URL was constructed correctly
    endpoint = provider._get_completion_endpoint()
    print(f"Endpoint: {endpoint}")

    # Verify the headers use Azure-style auth
    headers = provider._build_headers()
    print(f"Headers: {headers}")

    # Verify inherited capabilities still work
    print(f"Capabilities: {provider.get_capabilities()}")
    print(f"Supports tools? {provider.supports('tools')}")

    models = await provider.list_models()
    print(f"Models: {[m.id for m in models]}")

    # The complete() call would work against a real Azure deployment:
    # response = await provider.complete(CompletionRequest(
    #     model="gpt-4o",
    #     messages=[{"role": "user", "content": "Hello from Azure!"}],
    # ))

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
