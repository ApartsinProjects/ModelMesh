"""
11 - Routing Explanation & Debug
=================================

Shows how to use the ``explain()`` method to understand routing
decisions without making actual API calls. Useful for debugging
why a specific model was selected, inspecting pool candidates,
and understanding rotation strategies.

Uses the mock testing client for demonstration.
"""

from __future__ import annotations

import json

from modelmesh.testing import MockResponse, mock_client


def main():
    # Create a mock client
    client = mock_client(responses=[
        MockResponse(content="Hello!", model="gpt-4o", tokens=25),
    ])

    # 1. Explain routing for a model/pool
    print("=== Routing Explanation ===")
    explanation = client.explain()

    print(f"  Pool:           {explanation['pool_name']}")
    print(f"  Strategy:       {explanation['strategy']}")
    print(f"  Capability:     {explanation['capability']}")
    print(f"  Selected Model: {explanation['selected_model']}")
    print(f"  Reason:         {explanation['reason']}")

    # 2. Inspect candidates
    print("\n=== Candidates ===")
    for candidate in explanation["candidates"]:
        print(f"  Model: {candidate['model_id']:20s} "
              f"Provider: {candidate['provider_id']:20s} "
              f"Status: {candidate['status']}")

    # 3. Pool status
    print("\n=== Pool Status ===")
    status = client.pool_status()
    print(json.dumps(status, indent=2))

    # 4. Active providers
    print("\n=== Active Providers ===")
    providers = client.active_providers()
    for p in providers:
        print(f"  {p}")

    # 5. Describe (human-readable)
    print("\n=== Describe ===")
    print(client.describe())

    # --- Real client usage ---
    print("\n--- Real client usage pattern ---")
    print("""
    # With a real client:
    #
    #   client = modelmesh.create("chat-completion")
    #
    #   # See why a model was selected
    #   exp = client.explain(model="chat-completion")
    #   print(f"Selected: {exp['selected_model']}")
    #   print(f"Reason: {exp['reason']}")
    #   print(f"Candidates: {len(exp['candidates'])}")
    #
    #   # See all providers
    #   print(client.describe())
    """)


if __name__ == "__main__":
    main()
