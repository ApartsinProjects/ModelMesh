"""Tests for enhanced MockClient features: error injection, chaos testing, backward compat."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.testing import MockClient, MockResponse, mock_client
from modelmesh.exceptions import (
    ProviderError,
    RateLimitError,
    ProviderTimeoutError,
    AuthenticationError,
)


MESSAGES = [{"role": "user", "content": "Hello"}]


class TestMockResponseErrors:
    """Test error simulation in MockResponse."""

    def test_mock_response_raises_error(self):
        """MockResponse with error= raises that exception."""
        client = mock_client(responses=[
            MockResponse(error=RateLimitError("Rate limited", provider_id="mock"))
        ])
        with pytest.raises(RateLimitError, match="Rate limited"):
            client.chat.completions.create(model="chat-completion", messages=MESSAGES)

    def test_mock_response_with_delay(self):
        """MockResponse with delay= takes at least that long."""
        client = mock_client(responses=[MockResponse(content="OK", delay=0.1)])
        start = time.time()
        resp = client.chat.completions.create(model="chat-completion", messages=MESSAGES)
        elapsed = time.time() - start
        assert elapsed >= 0.1
        assert resp.choices[0].message.content == "OK"

    def test_error_after_success(self):
        """Sequence: success, error, success."""
        client = mock_client(responses=[
            MockResponse(content="First"),
            MockResponse(error=ProviderError("Fail", provider_id="mock")),
            MockResponse(content="Third"),
        ])

        resp1 = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp1.choices[0].message.content == "First"

        with pytest.raises(ProviderError, match="Fail"):
            client.chat.completions.create(model="test", messages=MESSAGES)

        resp3 = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp3.choices[0].message.content == "Third"

    def test_error_with_delay(self):
        """Error is delayed by delay parameter."""
        client = mock_client(responses=[
            MockResponse(error=ProviderError("Delayed fail", provider_id="mock"), delay=0.1)
        ])
        start = time.time()
        with pytest.raises(ProviderError, match="Delayed fail"):
            client.chat.completions.create(model="test", messages=MESSAGES)
        elapsed = time.time() - start
        assert elapsed >= 0.1

    def test_mock_response_error_types(self):
        """Different exception types are raised correctly."""
        client = mock_client(responses=[
            MockResponse(error=AuthenticationError("Bad key", provider_id="mock")),
        ])
        with pytest.raises(AuthenticationError, match="Bad key"):
            client.chat.completions.create(model="test", messages=MESSAGES)

    def test_mock_response_timeout_error(self):
        """ProviderTimeoutError is raised correctly."""
        client = mock_client(responses=[
            MockResponse(
                error=ProviderTimeoutError(
                    "Timed out", provider_id="mock", timeout_seconds=30.0
                )
            ),
        ])
        with pytest.raises(ProviderTimeoutError, match="Timed out"):
            client.chat.completions.create(model="test", messages=MESSAGES)


class TestMockClientChaos:
    """Test chaos testing features."""

    def test_failure_rate_zero(self):
        """failure_rate=0.0 never fails."""
        client = mock_client(
            responses=[MockResponse(content="OK")],
            failure_rate=0.0,
        )
        for _ in range(50):
            resp = client.chat.completions.create(model="test", messages=MESSAGES)
            assert resp.choices[0].message.content == "OK"

    def test_failure_rate_one(self):
        """failure_rate=1.0 always fails."""
        client = mock_client(
            responses=[MockResponse(content="OK")],
            failure_rate=1.0,
        )
        for _ in range(20):
            with pytest.raises(ProviderError, match="chaos testing"):
                client.chat.completions.create(model="test", messages=MESSAGES)

    def test_failure_rate_partial(self):
        """failure_rate=0.5 fails roughly half the time (statistical)."""
        client = mock_client(
            responses=[MockResponse(content="OK")],
            failure_rate=0.5,
        )
        failures = 0
        total = 200
        for _ in range(total):
            try:
                client.chat.completions.create(model="test", messages=MESSAGES)
            except ProviderError:
                failures += 1

        # With 200 trials at p=0.5, expect roughly 100 failures.
        # Allow wide range (20-180) to avoid flaky tests.
        assert 20 < failures < 180, f"Expected ~100 failures, got {failures}"

    def test_latency_range(self):
        """latency_range adds random delay within range."""
        client = mock_client(
            responses=[MockResponse(content="OK")],
            latency_range=(0.05, 0.1),
        )
        start = time.time()
        client.chat.completions.create(model="test", messages=MESSAGES)
        elapsed = time.time() - start
        assert elapsed >= 0.05

    def test_chaos_failure_is_provider_error(self):
        """Chaos-induced failures raise ProviderError with retryable=True."""
        client = mock_client(
            responses=[MockResponse(content="OK")],
            failure_rate=1.0,
        )
        with pytest.raises(ProviderError) as exc_info:
            client.chat.completions.create(model="test", messages=MESSAGES)
        assert exc_info.value.retryable is True


class TestMockClientBackwardCompat:
    """Verify all existing MockClient API still works."""

    def test_basic_response(self):
        """Original mock_client usage still works."""
        client = mock_client(responses=[
            MockResponse(content="Hello!"),
        ])
        resp = client.chat.completions.create(model="test-pool", messages=MESSAGES)
        assert resp.choices[0].message.content == "Hello!"
        assert len(client.calls) == 1

    def test_multiple_responses(self):
        """Sequential response list still works."""
        client = mock_client(responses=[
            MockResponse(content="First"),
            MockResponse(content="Second"),
            MockResponse(content="Third"),
        ])
        r1 = client.chat.completions.create(model="test", messages=MESSAGES)
        r2 = client.chat.completions.create(model="test", messages=MESSAGES)
        r3 = client.chat.completions.create(model="test", messages=MESSAGES)

        assert r1.choices[0].message.content == "First"
        assert r2.choices[0].message.content == "Second"
        assert r3.choices[0].message.content == "Third"

    def test_default_mock_response(self):
        """MockResponse() with no args still returns 'Mock response'."""
        client = mock_client(responses=[MockResponse()])
        resp = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp.choices[0].message.content == "Mock response"

    def test_mock_response_with_model(self):
        """MockResponse with model= still sets response.model."""
        client = mock_client(responses=[
            MockResponse(content="Hi", model="gpt-4o"),
        ])
        resp = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp.model == "gpt-4o"

    def test_mock_response_with_tokens(self):
        """MockResponse with tokens= still sets usage."""
        client = mock_client(responses=[
            MockResponse(content="Hi", tokens=100),
        ])
        resp = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp.usage.total_tokens == 100

    def test_mock_response_with_custom_token_split(self):
        """MockResponse with prompt_tokens and completion_tokens."""
        client = mock_client(responses=[
            MockResponse(content="Hi", prompt_tokens=20, completion_tokens=80),
        ])
        resp = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp.usage.prompt_tokens == 20
        assert resp.usage.completion_tokens == 80
        assert resp.usage.total_tokens == 100

    def test_mock_response_finish_reason(self):
        """MockResponse finish_reason is passed through."""
        client = mock_client(responses=[
            MockResponse(content="Hi", finish_reason="length"),
        ])
        resp = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp.choices[0].finish_reason == "length"

    def test_call_records_model(self):
        """MockCall records the model parameter."""
        client = mock_client(responses=[MockResponse()])
        client.chat.completions.create(model="my-pool", messages=MESSAGES)
        assert client.calls[0].model == "my-pool"

    def test_call_records_messages(self):
        """MockCall records the messages parameter."""
        client = mock_client(responses=[MockResponse()])
        client.chat.completions.create(model="test", messages=MESSAGES)
        assert client.calls[0].messages == MESSAGES

    def test_exhausted_responses_cycle_to_last(self):
        """When responses are exhausted, the last response is reused."""
        client = mock_client(responses=[
            MockResponse(content="Only"),
        ])
        r1 = client.chat.completions.create(model="test", messages=MESSAGES)
        r2 = client.chat.completions.create(model="test", messages=MESSAGES)
        assert r1.choices[0].message.content == "Only"
        assert r2.choices[0].message.content == "Only"

    def test_context_manager(self):
        """MockClient works as a context manager."""
        with mock_client(responses=[MockResponse(content="CM")]) as client:
            resp = client.chat.completions.create(model="test", messages=MESSAGES)
            assert resp.choices[0].message.content == "CM"

    def test_pool_status(self):
        """MockClient.pool_status returns mock data."""
        client = mock_client()
        status = client.pool_status()
        assert "mock-pool" in status
        assert status["mock-pool"]["active"] == 1

    def test_active_providers(self):
        """MockClient.active_providers returns mock list."""
        client = mock_client()
        providers = client.active_providers()
        assert "mock-provider" in providers

    def test_describe(self):
        """MockClient.describe returns a string."""
        client = mock_client()
        desc = client.describe()
        assert "mock-pool" in desc

    def test_explain(self):
        """MockClient.explain returns routing explanation."""
        client = mock_client()
        explanation = client.explain(model="test")
        assert explanation["pool_name"] == "mock-pool"
        assert explanation["strategy"] == "mock"

    def test_models_list(self):
        """MockClient.models.list returns empty list."""
        client = mock_client()
        result = client.models.list()
        assert result.data == []

    def test_no_responses_uses_default(self):
        """mock_client() with no responses uses default MockResponse."""
        client = mock_client()
        resp = client.chat.completions.create(model="test", messages=MESSAGES)
        assert resp.choices[0].message.content == "Mock response"
