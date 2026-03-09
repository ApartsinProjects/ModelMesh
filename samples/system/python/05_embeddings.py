"""
05 - Text Embeddings with Failover
===================================

Generate text embeddings using OpenAI and Cohere as providers.  The same
embedding request routes through whichever provider is currently active,
with automatic failover if one becomes unavailable.

This sample demonstrates:
  - Using the embeddings API through the OpenAI-compatible client
  - Registering embedding models in a shared capability pool
  - Failover between embedding providers
  - Inspecting embedding dimensions and usage metadata

Prerequisites:
  - Set OPENAI_API_KEY and COHERE_API_KEY environment variables.
"""

import asyncio
import yaml
from modelmesh import ModelMesh, MeshConfig

CONFIG_YAML = """
secrets:
  store: modelmesh.env.v1

providers:
  openai.llm.v1:
    enabled: true
    api_key: ${secrets:OPENAI_API_KEY}

  cohere.nlp.v1:
    enabled: true
    api_key: ${secrets:COHERE_API_KEY}

models:
  text-embedding-3-small:
    provider: openai.llm.v1
    capabilities:
      - representation.embeddings.text-embeddings
    delivery:
      synchronous: true
      batch: true
    constraints:
      context_window: 8191

  embed-v3-english:
    provider: cohere.nlp.v1
    capabilities:
      - representation.embeddings.text-embeddings
    delivery:
      synchronous: true
      batch: true
    constraints:
      context_window: 512

pools:
  # The pool targets the text-embeddings leaf node.
  text-embeddings:
    capability: representation.embeddings.text-embeddings
    strategy: modelmesh.stick-until-failure.v1
    deactivation:
      retry_limit: 2
      error_codes: [429, 500, 503]
    recovery:
      cooldown: 30s
    retry:
      max_attempts: 1
      backoff: fixed
      initial_delay: 1s
      scope: any

observability:
  routing:
    connector: modelmesh.console.v1
"""


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def main() -> None:
    config = MeshConfig(raw=yaml.safe_load(CONFIG_YAML))
    mesh = ModelMesh()
    mesh.initialize(config)

    client = mesh.get_client()

    print("=" * 60)
    print("Text embeddings with provider failover")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Example 1: Single text embedding
    # -----------------------------------------------------------------------
    print("\n--- Example 1: Single text embedding ---\n")

    text = "ModelMesh routes AI requests to the best available provider."

    response = await client.embeddings.create(
        model="text-embeddings",          # virtual model name -> pool
        input=text,
        encoding_format="float",
    )

    embedding = response.data[0].embedding
    print(f"Text       : {text}")
    print(f"Model used : {response.model}")
    print(f"Dimensions : {len(embedding)}")
    print(f"First 5    : {embedding[:5]}")
    print(f"Usage      : {response.usage}")

    # -----------------------------------------------------------------------
    # Example 2: Batch embeddings for similarity comparison
    # -----------------------------------------------------------------------
    print("\n--- Example 2: Batch embeddings + similarity ---\n")

    texts = [
        "The cat sat on the mat.",
        "A kitten rested on a rug.",
        "Quantum computing uses qubits for computation.",
    ]

    response = await client.embeddings.create(
        model="text-embeddings",
        input=texts,
        encoding_format="float",
    )

    print(f"Model used : {response.model}")
    print(f"Texts embedded: {len(response.data)}")

    # Compare similarities between the three texts.
    vectors = [item.embedding for item in response.data]

    sim_01 = cosine_similarity(vectors[0], vectors[1])
    sim_02 = cosine_similarity(vectors[0], vectors[2])
    sim_12 = cosine_similarity(vectors[1], vectors[2])

    print(f"\nSimilarity between:")
    print(f"  '{texts[0]}' and '{texts[1]}'")
    print(f"  -> {sim_01:.4f}  (expected: high, both about a small animal on fabric)\n")
    print(f"  '{texts[0]}' and '{texts[2]}'")
    print(f"  -> {sim_02:.4f}  (expected: low, unrelated topics)\n")
    print(f"  '{texts[1]}' and '{texts[2]}'")
    print(f"  -> {sim_12:.4f}  (expected: low, unrelated topics)")

    # -----------------------------------------------------------------------
    # Example 3: Requesting specific dimensions (if supported)
    # -----------------------------------------------------------------------
    print("\n--- Example 3: Reduced dimensions ---\n")

    response = await client.embeddings.create(
        model="text-embeddings",
        input="Dimensionality reduction test.",
        encoding_format="float",
        dimensions=256,
    )

    embedding = response.data[0].embedding
    print(f"Requested dimensions : 256")
    print(f"Actual dimensions    : {len(embedding)}")
    print(f"Model used           : {response.model}")

    mesh.shutdown()
    print("\nModelMesh shut down.")


if __name__ == "__main__":
    asyncio.run(main())
