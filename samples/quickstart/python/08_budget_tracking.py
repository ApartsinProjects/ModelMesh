"""
08 - Budget and Usage Tracking
===============================

Shows how to monitor costs, token usage, and budget status using the
``UsageTracker`` facade. The tracker is available on every MeshClient
via the ``client.usage`` property.

This sample uses the mock testing client for demonstration.
"""

from __future__ import annotations

from modelmesh.testing import MockResponse, mock_client
from modelmesh.usage import UsageTracker


def demo_usage_tracking():
    """Demonstrate the usage tracking API surface."""

    # Create a mock client with some responses
    client = mock_client(responses=[
        MockResponse(content="Hello!", tokens=50),
        MockResponse(content="World!", tokens=30),
    ])

    # Make some requests
    client.chat.completions.create(
        model="chat-pool",
        messages=[{"role": "user", "content": "Hello"}],
    )
    client.chat.completions.create(
        model="chat-pool",
        messages=[{"role": "user", "content": "World"}],
    )

    print(f"Total calls: {len(client.calls)}")
    print(f"Call 1 tokens: {client.calls[0].response.usage.total_tokens}")
    print(f"Call 2 tokens: {client.calls[1].response.usage.total_tokens}")

    # --- Real client usage (with budget configured) ---
    print("\n--- Real client usage pattern ---")
    print("""
    # With a real ModelMesh client that has budget configured:
    #
    #   import modelmesh
    #
    #   client = modelmesh.create("chat")
    #   # ... make requests ...
    #
    #   # Check usage metrics
    #   print(f"Total cost: ${client.usage.total_cost:.4f}")
    #   print(f"Daily cost: ${client.usage.daily_cost:.4f}")
    #   print(f"Monthly cost: ${client.usage.monthly_cost:.4f}")
    #   print(f"Total tokens: {client.usage.total_tokens}")
    #
    #   # Breakdown by model
    #   for model_id, usage in client.usage.by_model.items():
    #       print(f"  {model_id}: ${usage.total_cost:.4f}")
    #
    #   # Breakdown by provider
    #   for provider_id, usage in client.usage.by_provider.items():
    #       print(f"  {provider_id}: ${usage.total_cost:.4f}")
    #
    #   # Check budget status
    #   status = client.usage.budget_status
    #   if status:
    #       print(f"Budget exceeded: {status.exceeded}")
    #       print(f"Daily remaining: ${status.daily_remaining:.2f}")
    #
    #   # Reset counters
    #   client.usage.reset()
    #
    #   # Full summary dict
    #   summary = client.usage.summary()
    #   print(summary)
    """)


if __name__ == "__main__":
    demo_usage_tracking()
    print("Done!")
