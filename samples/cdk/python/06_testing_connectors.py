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
    BaseObservabilityConfig,
    BaseProviderConfig,
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
    mock_completion_request,
    mock_model_snapshot,
)
from modelmesh.interfaces.provider import ModelInfo


# ── Example 1: Using MockHttpClient with a provider ─────────────────

async def test_provider_with_mock() -> None:
    """Test a provider using a MockHttpClient with canned responses."""
    print("=== Testing Provider with MockHttpClient ===\n")

    mock_client = MockHttpClient()

    # Enqueue a canned completion response
    mock_client.add_response("/v1/chat/completions", {
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
    })

    # Enqueue a streaming response
    mock_client.add_stream_response("/v1/chat/completions", [
        '{"id":"chunk-1","model":"gpt-4o","choices":[{"delta":{"content":"Hi"}}]}',
        '{"id":"chunk-2","model":"gpt-4o","choices":[{"delta":{"content":"!"}}]}',
    ])

    # Verify recorded requests
    await mock_client.post("/v1/chat/completions", json={"model": "gpt-4o"})
    print(f"Recorded {len(mock_client.requests)} request(s)")
    print(f"  Method: {mock_client.requests[0].method}")
    print(f"  Path:   {mock_client.requests[0].path}")
    print(f"  Body:   {mock_client.requests[0].json}")


# ── Example 2: Using mock factories ─────────────────────────────────

def test_mock_factories() -> None:
    """Use mock_model_snapshot and mock_completion_request factories."""
    print("\n=== Testing Mock Factories ===\n")

    # Create a healthy model snapshot
    healthy = mock_model_snapshot()
    print(f"Healthy: model={healthy.model_id}, failures={healthy.failure_count}")

    # Create a failing model snapshot
    failing = mock_model_snapshot(failure_count=10, error_rate=0.9)
    print(f"Failing: model={failing.model_id}, failures={failing.failure_count}, "
          f"error_rate={failing.error_rate}")

    # Create a standby model
    standby = mock_model_snapshot(
        status="standby",
        cooldown_remaining=30.0,
    )
    print(f"Standby: model={standby.model_id}, "
          f"cooldown={standby.cooldown_remaining}s")

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

async def test_rotation_with_harness() -> None:
    """Run the ConnectorTestHarness against a rotation policy."""
    print("\n=== Testing Rotation Policy with Harness ===\n")

    policy = ThresholdRotationPolicy(BaseRotationPolicyConfig(
        retry_limit=5,
        error_rate_threshold=0.5,
        cooldown_seconds=60,
        model_priority=["gpt-4", "gpt-3.5-turbo"],
    ))

    harness = ConnectorTestHarness()

    # Run individual tests
    try:
        await harness.test_rotation_deactivation(policy)
        print("  test_rotation_deactivation: PASSED")
    except (AssertionError, Exception) as exc:
        print(f"  test_rotation_deactivation: FAILED - {exc}")

    try:
        await harness.test_rotation_recovery(policy)
        print("  test_rotation_recovery: PASSED")
    except (AssertionError, Exception) as exc:
        print(f"  test_rotation_recovery: FAILED - {exc}")

    try:
        await harness.test_rotation_selection(policy)
        print("  test_rotation_selection: PASSED")
    except (AssertionError, Exception) as exc:
        print(f"  test_rotation_selection: FAILED - {exc}")

    # Print summary
    print(f"\nResults: {len(harness.results)} test(s)")
    for name, (passed, msg) in harness.results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {msg}")


async def test_storage_with_harness() -> None:
    """Run the ConnectorTestHarness against a storage connector."""
    print("\n=== Testing Storage with Harness ===\n")

    storage = KeyValueStorage(KeyValueStorageConfig(
        backend="memory",
        format="json",
    ))

    harness = ConnectorTestHarness()

    try:
        await harness.test_storage_crud(storage)
        print("  test_storage_crud: PASSED")
    except (AssertionError, Exception) as exc:
        print(f"  test_storage_crud: FAILED - {exc}")

    for name, (passed, msg) in harness.results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {msg}")


async def test_observability_with_harness() -> None:
    """Run the ConnectorTestHarness against an observability connector."""
    print("\n=== Testing Observability with Harness ===\n")

    obs = ConsoleObservability(BaseObservabilityConfig(
        log_level="summary",
        redact_secrets=True,
    ))

    harness = ConnectorTestHarness()

    try:
        await harness.test_observability_emit_log_flush(obs)
        print("  test_observability_emit_log_flush: PASSED")
    except (AssertionError, Exception) as exc:
        print(f"  test_observability_emit_log_flush: FAILED - {exc}")

    for name, (passed, msg) in harness.results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {msg}")


# ── Example 4: Run all tests via run_all ─────────────────────────────

async def test_run_all() -> None:
    """Demonstrate the run_all method for batch testing."""
    print("\n=== Batch Testing with run_all ===\n")

    policy = ThresholdRotationPolicy(BaseRotationPolicyConfig(
        retry_limit=5,
        error_rate_threshold=0.5,
        cooldown_seconds=60,
        model_priority=["gpt-4", "gpt-3.5-turbo"],
    ))

    harness = ConnectorTestHarness()
    results = await harness.run_all(policy, "rotation")

    print(f"Ran {len(results)} test(s) for rotation policy:")
    for name, (passed, msg) in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {msg}")


# ── Main ─────────────────────────────────────────────────────────────

async def main() -> None:
    await test_provider_with_mock()
    test_mock_factories()
    await test_rotation_with_harness()
    await test_storage_with_harness()
    await test_observability_with_harness()
    await test_run_all()

    print("\n=== All test examples completed ===")


if __name__ == "__main__":
    asyncio.run(main())
