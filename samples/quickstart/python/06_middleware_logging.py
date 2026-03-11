"""
06 - Middleware: Request/Response Logging
==========================================

Shows how to add a logging middleware that prints every request and
response flowing through ModelMesh. Middleware can also transform
requests, enrich responses, or provide error fallbacks.

This sample uses the mock testing client so it runs without API keys.
"""

from __future__ import annotations

import time

from modelmesh import Middleware, MiddlewareContext
from modelmesh.interfaces.provider import CompletionRequest, CompletionResponse
from modelmesh.testing import MockResponse, mock_client


# ---------------------------------------------------------------------------
# 1. Define a middleware by subclassing Middleware
# ---------------------------------------------------------------------------

class LoggingMiddleware(Middleware):
    """Logs every request and response to stdout."""

    async def before_request(
        self, request: CompletionRequest, context: MiddlewareContext
    ) -> CompletionRequest:
        print(f"[LOG] >>> Sending request to {context.model_id}")
        print(f"         Provider: {context.provider_id}")
        print(f"         Pool:     {context.pool_name}")
        print(f"         Attempt:  {context.attempt}")
        return request  # pass through unchanged

    async def after_response(
        self, response: CompletionResponse, context: MiddlewareContext
    ) -> CompletionResponse:
        tokens = response.usage.total_tokens if response.usage else 0
        print(f"[LOG] <<< Response from {context.model_id}: {tokens} tokens")
        return response

    async def on_error(
        self, error: Exception, context: MiddlewareContext
    ) -> CompletionResponse:
        print(f"[LOG] !!! Error from {context.model_id}: {error}")
        raise error  # re-raise so the router can retry


# ---------------------------------------------------------------------------
# 2. Use the mock client for demonstration
# ---------------------------------------------------------------------------

client = mock_client(responses=[
    MockResponse(content="Hello from middleware demo!", model="gpt-4o", tokens=25),
    MockResponse(content="Second response.", model="claude-3", tokens=15),
])

# Make a call — the mock client returns pre-configured responses
response = client.chat.completions.create(
    model="chat-pool",
    messages=[{"role": "user", "content": "Hi!"}],
)

print(f"\nAssistant: {response.choices[0].message.content}")
print(f"Total calls recorded: {len(client.calls)}")

# ---------------------------------------------------------------------------
# 3. Show how middleware would be used with a real client
# ---------------------------------------------------------------------------

print("\n--- Real client usage (commented out) ---")
print("""
# With a real ModelMesh client:
#
#   import modelmesh
#
#   client = modelmesh.create("chat", middleware=[
#       LoggingMiddleware(),
#   ])
#
#   response = client.chat.completions.create(
#       model="chat-completion",
#       messages=[{"role": "user", "content": "Hello"}],
#   )
#
# Every request and response will be logged automatically.
""")
