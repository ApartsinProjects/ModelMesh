"""Tests for error classification and exception hierarchy edge cases."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.exceptions import (
    AllProvidersExhaustedError,
    AuthenticationError,
    BudgetExceededError,
    ConfigurationError,
    ModelMeshError,
    NoActiveModelError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    RoutingError,
)
from modelmesh.testing import MockResponse, mock_client


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_all_exceptions_inherit_from_modelmesh_error(self):
        """All custom exceptions inherit from ModelMeshError."""
        exception_classes = [
            RoutingError,
            NoActiveModelError,
            AllProvidersExhaustedError,
            ProviderError,
            AuthenticationError,
            RateLimitError,
            ProviderTimeoutError,
            ConfigurationError,
            BudgetExceededError,
        ]
        for cls in exception_classes:
            assert issubclass(cls, ModelMeshError), (
                f"{cls.__name__} does not inherit from ModelMeshError"
            )

    def test_routing_error_hierarchy(self):
        """RoutingError subclasses inherit from RoutingError."""
        assert issubclass(NoActiveModelError, RoutingError)
        assert issubclass(AllProvidersExhaustedError, RoutingError)

    def test_provider_error_hierarchy(self):
        """ProviderError subclasses inherit from ProviderError."""
        assert issubclass(AuthenticationError, ProviderError)
        assert issubclass(RateLimitError, ProviderError)
        assert issubclass(ProviderTimeoutError, ProviderError)

    def test_routing_error_has_pool_info(self):
        """RoutingError includes pool name."""
        err = RoutingError("No models available", pool_name="chat-completion")
        assert err.pool_name == "chat-completion"
        assert str(err) == "No models available"

    def test_provider_error_has_provider_info(self):
        """ProviderError includes provider name."""
        err = ProviderError(
            "API error",
            provider_id="openai.llm.v1",
            model_id="gpt-4o",
        )
        assert err.provider_id == "openai.llm.v1"
        assert err.model_id == "gpt-4o"

    def test_rate_limit_error_fields(self):
        """RateLimitError has retry_after field."""
        err = RateLimitError(
            "Too many requests",
            provider_id="openai.llm.v1",
            retry_after=30.0,
        )
        assert err.retry_after == 30.0
        assert err.provider_id == "openai.llm.v1"
        assert err.retryable is True

    def test_rate_limit_error_default_retry_after(self):
        """RateLimitError default retry_after is None."""
        err = RateLimitError("Rate limited", provider_id="mock")
        assert err.retry_after is None

    def test_budget_exceeded_error_fields(self):
        """BudgetExceededError has budget and usage fields."""
        err = BudgetExceededError(
            "Daily limit exceeded",
            limit_type="daily",
            limit_value=10.0,
            actual_value=12.5,
        )
        assert err.limit_type == "daily"
        assert err.limit_value == 10.0
        assert err.actual_value == 12.5
        assert err.retryable is False

    def test_all_providers_exhausted_error(self):
        """AllProvidersExhaustedError has attempts and last_error fields."""
        last_err = ProviderError("Last failure", provider_id="test")
        err = AllProvidersExhaustedError(
            "All providers failed",
            pool_name="chat-completion",
            attempts=3,
            last_error=last_err,
        )
        assert err.pool_name == "chat-completion"
        assert err.attempts == 3
        assert err.last_error is last_err
        assert err.retryable is False

    def test_authentication_error(self):
        """AuthenticationError has provider field and is not retryable."""
        err = AuthenticationError(
            "Invalid API key",
            provider_id="openai.llm.v1",
        )
        assert err.provider_id == "openai.llm.v1"
        assert err.retryable is False

    def test_configuration_error(self):
        """ConfigurationError message is descriptive."""
        err = ConfigurationError("Missing required field 'api_key'")
        assert "api_key" in str(err)
        assert err.retryable is False

    def test_provider_timeout_error(self):
        """ProviderTimeoutError has timeout_seconds value."""
        err = ProviderTimeoutError(
            "Request timed out",
            provider_id="openai.llm.v1",
            timeout_seconds=30.0,
        )
        assert err.timeout_seconds == 30.0
        assert err.retryable is True

    def test_provider_timeout_default_timeout(self):
        """ProviderTimeoutError default timeout_seconds is None."""
        err = ProviderTimeoutError("Timeout", provider_id="mock")
        assert err.timeout_seconds is None

    def test_no_active_model_error(self):
        """NoActiveModelError is retryable by default."""
        err = NoActiveModelError(
            "No active models",
            pool_name="chat-completion",
        )
        assert err.retryable is True
        assert err.pool_name == "chat-completion"

    def test_modelmesh_error_details(self):
        """ModelMeshError supports optional details dict."""
        err = ModelMeshError(
            "Something went wrong",
            details={"key": "value"},
        )
        assert err.details == {"key": "value"}
        assert err.retryable is False

    def test_modelmesh_error_default_details(self):
        """ModelMeshError defaults to empty details dict."""
        err = ModelMeshError("Error")
        assert err.details == {}

    def test_catch_all_with_modelmesh_error(self):
        """All custom exceptions can be caught with except ModelMeshError."""
        exceptions_to_test = [
            RoutingError("routing"),
            NoActiveModelError("no active"),
            AllProvidersExhaustedError("exhausted"),
            ProviderError("provider"),
            AuthenticationError("auth"),
            RateLimitError("rate limit"),
            ProviderTimeoutError("timeout"),
            ConfigurationError("config"),
            BudgetExceededError("budget"),
        ]
        for exc in exceptions_to_test:
            with pytest.raises(ModelMeshError):
                raise exc


class TestErrorRecoveryPatterns:
    """Test error recovery and retry patterns."""

    def test_retryable_error_detection(self):
        """RateLimitError and ProviderTimeoutError are retryable."""
        rate_limit = RateLimitError("Limited", provider_id="mock")
        timeout = ProviderTimeoutError("Timeout", provider_id="mock")
        no_active = NoActiveModelError("No active", pool_name="test")

        assert rate_limit.retryable is True
        assert timeout.retryable is True
        assert no_active.retryable is True

    def test_non_retryable_error_detection(self):
        """AuthenticationError and ConfigurationError are not retryable."""
        auth = AuthenticationError("Bad key", provider_id="mock")
        config = ConfigurationError("Bad config")
        budget = BudgetExceededError("Over budget")
        exhausted = AllProvidersExhaustedError("All failed")

        assert auth.retryable is False
        assert config.retryable is False
        assert budget.retryable is False
        assert exhausted.retryable is False

    def test_provider_error_retryable_flag(self):
        """ProviderError retryable flag can be set explicitly."""
        retryable = ProviderError("Temporary", provider_id="mock", retryable=True)
        non_retryable = ProviderError("Permanent", provider_id="mock", retryable=False)

        assert retryable.retryable is True
        assert non_retryable.retryable is False

    def test_error_in_mock_client_sequence(self):
        """Mock client handles error -> success sequence."""
        client = mock_client(responses=[
            MockResponse(error=RateLimitError("Limited", provider_id="mock")),
            MockResponse(content="Recovered"),
        ])

        with pytest.raises(RateLimitError):
            client.chat.completions.create(
                model="test",
                messages=[{"role": "user", "content": "Hello"}],
            )

        resp = client.chat.completions.create(
            model="test",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert resp.choices[0].message.content == "Recovered"

    def test_multiple_error_types_in_sequence(self):
        """Mock client handles a sequence of different error types."""
        client = mock_client(responses=[
            MockResponse(error=RateLimitError("Rate limited", provider_id="mock")),
            MockResponse(error=ProviderTimeoutError("Timed out", provider_id="mock")),
            MockResponse(content="Finally worked"),
        ])

        with pytest.raises(RateLimitError):
            client.chat.completions.create(
                model="test",
                messages=[{"role": "user", "content": "Hello"}],
            )

        with pytest.raises(ProviderTimeoutError):
            client.chat.completions.create(
                model="test",
                messages=[{"role": "user", "content": "Hello"}],
            )

        resp = client.chat.completions.create(
            model="test",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert resp.choices[0].message.content == "Finally worked"

    def test_error_message_preserved(self):
        """Exception message is preserved through raise/catch cycle."""
        msg = "Detailed error: connection refused after 3 attempts"
        err = ProviderError(msg, provider_id="openai.llm.v1")

        with pytest.raises(ProviderError, match="connection refused"):
            raise err

    def test_error_details_dict(self):
        """Error details dict carries structured context."""
        err = ProviderError(
            "API error",
            provider_id="openai.llm.v1",
            details={"status_code": 500, "response_body": "Internal Server Error"},
        )
        assert err.details["status_code"] == 500
        assert err.details["response_body"] == "Internal Server Error"
