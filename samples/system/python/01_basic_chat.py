"""
01 - Basic Chat Completion
==========================

Simplest possible ModelMesh Lite setup: a single OpenAI provider, one model,
and a chat completion request.

This sample demonstrates:
  - Initializing ModelMesh from an inline configuration dict
  - Obtaining the OpenAI-compatible client
  - Making a chat completion call using a virtual model name
  - Printing the response

The virtual model name "text-generation" maps to a capability pool.  ModelMesh
resolves it to the best (and in this case only) active real model and provider,
then forwards the request transparently.

Prerequisites:
  - Set the OPENAI_API_KEY environment variable.
"""

import asyncio
import yaml
from modelmesh import ModelMesh, MeshConfig

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Inline YAML keeps the sample self-contained.  In production you would use
# ModelMesh.from_yaml("config.yaml") or load from a storage connector.

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1          # read API keys from environment variables

providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}

models:
  gpt-4o-mini:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

pools:
  text-generation:
    strategy: modelmesh.stick-until-failure.v1

observability:
  routing:
    connector: modelmesh.console.v1   # print routing decisions to stdout
"""


async def main() -> None:
    # 1. Parse the YAML into a MeshConfig and initialize ModelMesh.
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    print("ModelMesh initialized with a single OpenAI provider.\n")

    # 2. Get the OpenAI-compatible client.
    #    This client mirrors the official OpenAI SDK interface.
    client = mesh.get_client()

    # 3. Make a chat completion request.
    #    "text-generation" is a virtual model name that resolves to the
    #    text-generation capability pool.  ModelMesh selects gpt-4o-mini
    #    because it is the only model registered in that pool.
    print("Sending chat completion request...")
    response = client.chat.completions.create(
        model="text-generation",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain what an API gateway is in two sentences."},
        ],
        temperature=0.7,
        max_tokens=256,
    )

    # 4. Print the result.
    print(f"\nModel used : {response.model}")
    print(f"Tokens in  : {response.usage.prompt_tokens}")
    print(f"Tokens out : {response.usage.completion_tokens}")
    print(f"\nAssistant:\n{response.choices[0].message.content}")

    # 5. Shut down gracefully (flushes state and statistics).
    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
