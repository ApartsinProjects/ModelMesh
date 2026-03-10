"""
04 - Streaming Chat Completion
==============================

Streaming chat completion with OpenAI and Google Gemini providers.  The
response arrives incrementally as the model generates tokens, which is
displayed chunk by chunk.

This sample demonstrates:
  - Using stream=True with the OpenAI-compatible client
  - Iterating over streaming response chunks
  - Automatic fallback to the next provider on stream error
  - Delivery mode filtering (only stream-capable models are considered)

Prerequisites:
  - Set OPENAI_API_KEY and GOOGLE_API_KEY environment variables.
"""

import asyncio
import sys
import yaml
from modelmesh import ModelMesh, MeshConfig

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}

  google.gemini.v1:
    enabled: true
    api_key: ${secrets:GOOGLE_API_KEY}

models:
  gpt-4o:
    provider: openai.llm.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true        # streaming supported
      batch: true
    features:
      tool_calling: true
      structured_output: true
      system_prompt: true
    constraints:
      context_window: 128000
      max_output_tokens: 16384

  gemini-2.5-flash:
    provider: google.gemini.v1
    capabilities:
      - generation.text-generation.chat-completion
    delivery:
      synchronous: true
      streaming: true        # streaming supported
    features:
      tool_calling: true
      system_prompt: true
    constraints:
      context_window: 1048576
      max_output_tokens: 8192

pools:
  text-generation:
    strategy: modelmesh.stick-until-failure.v1
    deactivation:
      retry_limit: 2
      error_codes: [429, 500, 502, 503]
    recovery:
      cooldown: 30s
    retry:
      max_attempts: 1
      backoff: exponential_jitter
      initial_delay: 500ms
      retryable_codes: [429, 500, 502, 503]
      scope: any             # allow cross-provider retry for streams

observability:
  routing:
    connector: modelmesh.console.v1
"""


async def main() -> None:
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    client = mesh.get_client()

    print("=" * 60)
    print("Streaming chat completion demo")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Example 1: Basic streaming
    # -----------------------------------------------------------------------
    print("\n--- Example 1: Basic streaming ---\n")
    print("User: Write a short poem about distributed systems.\n")
    print("Assistant: ", end="")

    response_stream = client.chat.completions.create(
        model="text-generation",
        messages=[
            {"role": "system", "content": "You are a creative writer."},
            {"role": "user", "content": "Write a short poem about distributed systems."},
        ],
        temperature=0.9,
        max_tokens=256,
        stream=True,
    )

    # The streaming response is an async iterator of CompletionResponse chunks.
    # Each chunk contains partial content that can be printed immediately.
    full_text = ""
    for chunk in response_stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            print(token, end="", flush=True)
            full_text += token

    print("\n")
    print(f"Model used: {chunk.model}")

    # -----------------------------------------------------------------------
    # Example 2: Streaming with metadata inspection
    # -----------------------------------------------------------------------
    print("\n--- Example 2: Streaming with usage metadata ---\n")
    print("User: List three benefits of load balancing.\n")
    print("Assistant: ", end="")

    chunk_count = 0
    response_stream = client.chat.completions.create(
        model="text-generation",
        messages=[{"role": "user", "content": "List three benefits of load balancing."}],
        temperature=0.5,
        max_tokens=200,
        stream=True,
    )

    for chunk in response_stream:
        chunk_count += 1
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

    print(f"\n\nReceived {chunk_count} chunks.")
    print(f"Final chunk usage: {chunk.usage}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
