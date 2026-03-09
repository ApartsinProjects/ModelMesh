"""
03 - Text Embeddings
=====================

Generate text embeddings through ModelMesh Lite.  Embeddings turn text into
numerical vectors that capture semantic meaning, useful for search, clustering,
and similarity comparisons.

This sample demonstrates:
  - Creating a client for the "text-embeddings" capability
  - Embedding a single string
  - Inspecting the embedding vector and its dimensions
  - Embedding a batch of strings in one call

Prerequisites:
  - Set at least one provider API key that supports embeddings
    (e.g., OPENAI_API_KEY).
"""

import modelmesh

# Create a client for the "text-embeddings" capability.
client = modelmesh.create("text-embeddings")

# ---------------------------------------------------------------------------
# Single embedding
# ---------------------------------------------------------------------------
print("=" * 50)
print("Single Embedding")
print("=" * 50)

response = client.embeddings.create(
    model="text-embeddings",
    input="Artificial intelligence is transforming software engineering.",
)

# response.data is a list of embedding objects; we want the first one.
vector = response.data[0].embedding
print(f"Dimensions : {len(vector)}")
print(f"First 5    : {vector[:5]}")
print(f"Model used : {response.model}")

# ---------------------------------------------------------------------------
# Batch embeddings
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("Batch Embeddings")
print("=" * 50)

texts = [
    "The quick brown fox jumps over the lazy dog.",
    "A fast auburn fox leaps above a sleepy hound.",
    "Quantum computing leverages superposition and entanglement.",
]

response = client.embeddings.create(
    model="text-embeddings",
    input=texts,
)

print(f"Texts sent : {len(texts)}")
print(f"Vectors    : {len(response.data)}")

# Show the dimension of each returned vector.
for i, item in enumerate(response.data):
    print(f"  [{i}] {len(item.embedding)} dimensions  —  \"{texts[i][:40]}...\"")


if __name__ == "__main__":
    # Already executed above; this guard is here so linters are happy.
    pass
