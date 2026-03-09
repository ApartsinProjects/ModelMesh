"""Tutorial 1: Full working provider in minimal code.

Shows how to create an OpenAI-compatible provider, configure it with
a model catalogue, send a chat completion request, and inspect the
response -- all using the CDK's zero-code specialized class.

This is the simplest possible provider setup: instantiate
OpenAICompatibleProvider with a BaseProviderConfig, call complete(),
and read the result.
"""

import asyncio

from modelmesh.cdk import OpenAICompatibleProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    CompletionRequest,
    ModelInfo,
    ModelPricing,
)


async def main() -> None:
    # -- Step 1: Configure the provider --
    provider = OpenAICompatibleProvider(BaseProviderConfig(
        base_url="https://api.openai.com",
        api_key="sk-your-api-key",
        timeout=30.0,
        max_retries=3,
        capabilities=["generation.text-generation.chat-completion"],
        models=[
            ModelInfo(
                id="gpt-4o",
                name="GPT-4o",
                capabilities=["generation.text-generation.chat-completion"],
                features={"tool_calling": True, "vision": True, "system_prompt": True},
                context_window=128_000,
                max_output_tokens=16_384,
                pricing=ModelPricing(
                    input_per_token=0.0000025,
                    output_per_token=0.00001,
                ),
            ),
        ],
    ))

    # -- Step 2: Inspect capabilities and catalogue --
    print(f"Capabilities: {provider.get_capabilities()}")
    print(f"Supports chat? {provider.supports('generation.text-generation.chat-completion')}")

    models = await provider.list_models()
    for model in models:
        print(f"Model: {model.id} ({model.name}), context: {model.context_window}")

    # -- Step 3: Send a completion request --
    request = CompletionRequest(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is ModelMesh?"},
        ],
        temperature=0.7,
        max_tokens=256,
    )

    response = await provider.complete(request)

    # -- Step 4: Inspect the response --
    print(f"\nResponse ID: {response.id}")
    print(f"Model: {response.model}")
    print(f"Content: {response.choices[0]}")
    print(f"Tokens: prompt={response.usage.prompt_tokens}, "
          f"completion={response.usage.completion_tokens}, "
          f"total={response.usage.total_tokens}")

    # -- Step 5: Check quota after usage --
    quota = await provider.check_quota()
    print(f"\nRequests used: {quota.used}")

    pricing = await provider.get_pricing("gpt-4o")
    print(f"Pricing: ${pricing.input_per_token}/input token, "
          f"${pricing.output_per_token}/output token")

    await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
