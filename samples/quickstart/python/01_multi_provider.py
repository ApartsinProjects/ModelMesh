"""
01 - Multi-Provider with Capabilities
======================================

Use multiple capabilities across multiple providers.  ModelMesh auto-detects
providers from environment variables and routes requests according to the
chosen strategy.

This sample demonstrates:
  - Requesting multiple capabilities: chat-completion and text-embeddings
  - Restricting providers explicitly
  - Using the "cost-first" rotation strategy
  - Calling both chat and embeddings endpoints through the same client
  - Inspecting which model was used and token usage

Prerequisites:
  - Set OPENAI_API_KEY and ANTHROPIC_API_KEY environment variables.
"""

import modelmesh

# Create a client with two capabilities across two providers.
# "cost-first" picks the cheapest available model for each request.
client = modelmesh.create(
    "chat-completion", "text-embeddings",
    providers=["openai", "anthropic"],
    strategy="cost-first",
)

# ---------------------------------------------------------------------------
# Chat completion
# ---------------------------------------------------------------------------
print("=" * 50)
print("Chat Completion")
print("=" * 50)

response = client.chat.completions.create(
    model="chat-completion",
    messages=[
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "What is the difference between TCP and UDP?"},
    ],
    max_tokens=200,
)

print(f"Model used  : {response.model}")
print(f"Prompt tkns : {response.usage.prompt_tokens}")
print(f"Compl. tkns : {response.usage.completion_tokens}")
print(f"\nAssistant:\n{response.choices[0].message.content}")

# ---------------------------------------------------------------------------
# Text embeddings
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("Text Embeddings")
print("=" * 50)

embed_response = client.embeddings.create(
    model="text-embeddings",
    input="ModelMesh routes AI requests to the best provider.",
)

vector = embed_response.data[0].embedding
print(f"Model used : {embed_response.model}")
print(f"Dimensions : {len(vector)}")
print(f"First 5    : {vector[:5]}")


if __name__ == "__main__":
    # Already executed above; this guard is here so linters are happy.
    pass
