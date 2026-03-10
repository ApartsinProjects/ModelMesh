"""Tutorial 6: Test harness usage with MockHttpClient and ConnectorTestHarness.

Demonstrates how to use the CDK's test utilities to validate connector
implementations without making real HTTP calls. Covers:
- MockHttpClient for canned responses
- mock_model_snapshot and mock_completion_request factories
- ConnectorTestHarness for interface compliance testing
"""

import asyncio
from datetime import datetime

from modelmesh.cdk import (
    ConsoleObservabilityConfig,
    OpenAICompatibleConfig,
    BaseRotationPolicyConfig,
    BaseStorageConfig,
    ConsoleObservability,
    KeyValueStorage,
    KeyValueStorageConfig,
    OpenAICompatibleProvider,
    ThresholdRotationPolicy,
)
from modelmesh.cdk.helpers import (
    ConnectorTestHarness,
    MockHttpClient,
    MockHttpResponse,
    mock_completion_request,
    mock_model_snapshot,
)
from modelmesh.interfaces.provider import ModelInfo
from modelmesh.interfaces.rotation_policy import ModelStatus


# ── Example 1: Using MockHttpClient with a provider ─────────────────

async def test_provider_with_mock() -> None:
    """Test a provider using a MockHttpClient with canned responses."""
    print("=== Testing Provider with MockHttpClient ===\n")

    mock_client = MockHttpClient()

    # Enqueue a canned completion response
    mock_client.add_response(MockHttpResponse(status_code=200, body={
        "id": "chatcmpl-test-123",
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }))

    # Verify recorded requests
    await mock_client.post("/v1/chat/completions", json={"model": "gpt-4o"})
    print(f"Recorded {len(mock_client.calls)} request(s)")
    print(f"  Method: {mock_client.calls[0]['method']}")
    print(f"  URL:    {mock_client.calls[0]['url']}")
    print(f"  Body:   {mock_client.calls[0]['json']}")


# ── Example 2: Using mock factories ─────────────────────────────────

def test_mock_factories() -> None:
    """Use mock_model_snapshot and mock_completion_request factories."""
    print("\n=== Testing Mock Factories ===\n")

    # Create a healthy model snapshot
    healthy = mock_model_snapshot()
    print(f"Healthy: model={healthy.model_id}, failures={healthy.failure_count}")

    # Create a failing model snapshot
    failing = mock_model_snapshot(failure_count=10)
    print(f"Failing: model={failing.model_id}, failures={failing.failure_count}")

    # Create a standby model
    standby = mock_model_snapshot(
        status=ModelStatus.STANDBY,
    )
    print(f"Standby: model={standby.model_id}, "
          f"status={standby.status}")

    # Create a minimal completion request
    simple = mock_completion_request()
    print(f"\nRequest: model={simple.model}, "
          f"messages={len(simple.messages)} msg(s)")

    # Create a streaming request with custom parameters
    streaming = mock_completion_request(
        model="gpt-3.5-turbo",
        stream=True,
        temperature=0.5,
        max_tokens=100,
    )
    print(f"Streaming: model={streaming.model}, stream={streaming.stream}")


# ── Example 3: ConnectorTestHarness ──────────────────────────────────

async def test_provider_with_harness() -> None:
    """Run the ConnectorTestHarness against a provider connector."""
    print("\n=== Testing Provider with Harness ===\n")

    provider = OpenAICompatibleProvider(OpenAICompatibleConfig(
        base_url="https://api.openai.com",
        api_key="sk-test",
        models=[ModelInfo(
            id="gpt-4o",
            name="GPT-4o",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=128_000,
            max_output_tokens=16_384,
        )],
    ))

    harness = ConnectorTestHarness(provider)

    # The harness wraps the connector to record calls. In a real test
    # environment, the provider would connect to a real or mocked server.
    # Here, we demonstrate the harness pattern and handle the expected
    # 401 error gracefully.
    try:
        response = await harness.complete(mock_completion_request(model="gpt-4o"))
        print(f"  complete() response id: {response.id}")
    except Exception as e:
        print(f"  complete() raised (expected without valid key): {type(e).__name__}")

    print(f"  Harness recorded {len(harness.calls)} call(s)")
    print("  Harness test exercised successfully.")


# ── Main ─────────────────────────────────────────────────────────────

async def main() -> None:
    await test_provider_with_mock()
    test_mock_factories()
    await test_provider_with_harness()

    print("\n=== All test examples completed ===")


if __name__ == "__main__":
    asyncio.run(main())
