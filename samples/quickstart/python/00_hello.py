"""
00 - Hello World Chat Completion
=================================

Simplest possible ModelMesh Lite usage: specify a capability, get an
OpenAI-compatible client, make a chat completion call.

This sample is nearly identical to using the OpenAI SDK directly.
The only differences: the import, the create() call, and the model parameter.

Prerequisites:
  - Set at least one provider API key (e.g., OPENAI_API_KEY).
"""

import modelmesh

# Create a client for the "chat-completion" capability.
# Providers are auto-detected from environment variables.
client = modelmesh.create("chat-completion")

# Standard OpenAI-compatible call — virtual model name = capability name.
response = client.chat.completions.create(
    model="chat-completion",
    messages=[{"role": "user", "content": "Explain what an API is in two sentences."}],
)

print(response.choices[0].message.content)
