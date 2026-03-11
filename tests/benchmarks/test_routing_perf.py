"""
Performance benchmarks for ModelMesh routing.

Measures latency of key operations:
  - Client creation
  - Single request cycle (mock provider)
  - describe() latency
  - Batch request throughput

Run with: pytest tests/benchmarks/ -v
"""

import time
import pytest
from modelmesh.testing import mock_client, MockResponse


class TestRoutingPerformance:
    """Benchmark core routing operations."""

    def test_mock_client_creation_under_50ms(self):
        """mock_client() creates a usable client in under 50ms."""
        start = time.perf_counter()
        for _ in range(10):
            client = mock_client(responses=[MockResponse()])
        elapsed = (time.perf_counter() - start) / 10
        assert elapsed < 0.05, f"Client creation took {elapsed:.4f}s (limit: 0.05s)"

    def test_single_request_under_10ms(self):
        """Single mock request completes in under 10ms."""
        responses = [MockResponse(content="response") for _ in range(110)]
        client = mock_client(responses=responses)
        # Warm up
        client.chat.completions.create(
            model="chat-completion",
            messages=[{"role": "user", "content": "warmup"}],
        )

        start = time.perf_counter()
        for _ in range(50):
            client.chat.completions.create(
                model="chat-completion",
                messages=[{"role": "user", "content": "test"}],
            )
        elapsed = (time.perf_counter() - start) / 50
        assert elapsed < 0.01, f"Single request took {elapsed:.6f}s (limit: 0.01s)"

    def test_describe_under_5ms(self):
        """client.describe() returns in under 5ms."""
        client = mock_client(responses=[MockResponse()])

        start = time.perf_counter()
        for _ in range(100):
            client.describe()
        elapsed = (time.perf_counter() - start) / 100
        assert elapsed < 0.005, f"describe() took {elapsed:.6f}s (limit: 0.005s)"

    def test_100_sequential_requests_under_1s(self):
        """100 sequential requests complete in under 1 second total."""
        responses = [MockResponse(content="response") for _ in range(100)]
        client = mock_client(responses=responses)

        start = time.perf_counter()
        for _ in range(100):
            client.chat.completions.create(
                model="chat-completion",
                messages=[{"role": "user", "content": "bench"}],
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"100 requests took {elapsed:.3f}s (limit: 1.0s)"
