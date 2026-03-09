"""
04 - Custom Provider Endpoint
==============================

Use QuickProvider to connect to a custom or internal API endpoint.
QuickProvider works with just a base_url and api_key — no ModelInfo needed.

Prerequisites:
  - A running OpenAI-compatible API endpoint.
"""

from modelmesh.cdk import QuickProvider

# QuickProvider: just base_url + api_key, models auto-discovered
provider = QuickProvider(
    base_url="https://my-internal-api.company.com/v1",
    api_key="sk-internal-key",
)

# Use via modelmesh.create() with a config dict
import modelmesh

client = modelmesh.create(config={
    "providers": {
        "internal": {
            "connector": provider,
        },
    },
    "pools": {
        "chat-completion": {
            "capability": "generation.text-generation.chat-completion",
        },
    },
})

response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Hello from internal API!"}],
)
print(response.choices[0].message.content)
