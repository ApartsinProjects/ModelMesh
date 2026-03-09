"""Quickstart: Create an OpenAI-compatible provider and call complete().

Demonstrates the simplest way to create a provider connector using the
OpenAICompatibleProvider specialized class with a BaseProviderConfig.
"""

import asyncio

from modelmesh.cdk import OpenAICompatibleProvider, BaseProviderConfig
from modelmesh.interfaces.provider import CompletionRequest, ModelInfo


async def main() -> None:
    provider = OpenAICompatibleProvider(BaseProviderConfig(
        base_url="https://api.openai.com",
        api_key="sk-your-api-key",
        models=[ModelInfo(
            id="gpt-4o",
            name="GPT-4o",
            capabilities=["generation.text-generation.chat-completion"],
            features={"tool_calling": True},
            context_window=128_000,
            max_output_tokens=16_384,
        )],
    ))

    request = CompletionRequest(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Say hello!"}],
    )

    response = await provider.complete(request)
    print(f"Response: {response.choices[0]}")
    print(f"Tokens used: {response.usage.total_tokens}")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
