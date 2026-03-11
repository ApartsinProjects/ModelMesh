"""Structured exception hierarchy for ModelMesh.

All ModelMesh-specific exceptions inherit from :class:`ModelMeshError`,
enabling broad ``except ModelMeshError`` catches while still allowing
fine-grained handling of specific failure modes.

Exception tree::

    ModelMeshError
    ├── RoutingError
    │   ├── NoActiveModelError
    │   └── AllProvidersExhaustedError
    ├── ProviderError
    │   ├── AuthenticationError
    │   ├── RateLimitError
    │   └── ProviderTimeoutError
    ├── ConfigurationError
    └── BudgetExceededError
"""
from __future__ import annotations

from typing import Optional


class ModelMeshError(Exception):
    """Base exception for all ModelMesh errors.

    All ModelMesh-specific exceptions inherit from this class so that
    callers can write a single ``except ModelMeshError`` handler.

    Attributes:
        message: Human-readable error description.
        details: Optional structured context about the error.
        retryable: Hint indicating whether the operation may succeed
            on retry.
    """

    def __init__(
        self,
        message: str = "",
        *,
        details: Optional[dict] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.retryable = retryable


# -- Routing errors ----------------------------------------------------------


class RoutingError(ModelMeshError):
    """Error during request routing (pool resolution or model selection).

    Attributes:
        pool_name: The pool ID that was being resolved.
    """

    def __init__(
        self,
        message: str = "",
        *,
        pool_name: Optional[str] = None,
        details: Optional[dict] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message, details=details, retryable=retryable)
        self.pool_name = pool_name


class NoActiveModelError(RoutingError):
    """No active model is available in the requested pool.

    Raised when all models in a pool are in standby or have been
    deactivated, and no candidate can serve the request.
    """

    def __init__(
        self,
        message: str = "",
        *,
        pool_name: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(
            message, pool_name=pool_name, details=details, retryable=True
        )


class AllProvidersExhaustedError(RoutingError):
    """All providers failed after retry/rotation attempts.

    Raised when the router has exhausted all retry attempts across
    available models in the pool.

    Attributes:
        attempts: Number of attempts made before giving up.
        last_error: The last provider error encountered.
    """

    def __init__(
        self,
        message: str = "",
        *,
        pool_name: Optional[str] = None,
        attempts: int = 0,
        last_error: Optional[Exception] = None,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(
            message, pool_name=pool_name, details=details, retryable=False
        )
        self.attempts = attempts
        self.last_error = last_error


# -- Provider errors ---------------------------------------------------------


class ProviderError(ModelMeshError):
    """Error originating from a provider connector.

    Attributes:
        provider_id: Connector ID of the provider that failed.
        model_id: Model identifier that was being used.
    """

    def __init__(
        self,
        message: str = "",
        *,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        details: Optional[dict] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message, details=details, retryable=retryable)
        self.provider_id = provider_id
        self.model_id = model_id


class AuthenticationError(ProviderError):
    """API key or authentication credentials are invalid or expired."""

    def __init__(
        self,
        message: str = "",
        *,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(
            message,
            provider_id=provider_id,
            model_id=model_id,
            details=details,
            retryable=False,
        )


class RateLimitError(ProviderError):
    """Provider rate limit or quota has been exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by
            the upstream API.
    """

    def __init__(
        self,
        message: str = "",
        *,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        retry_after: Optional[float] = None,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(
            message,
            provider_id=provider_id,
            model_id=model_id,
            details=details,
            retryable=True,
        )
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderError):
    """Request to the provider timed out."""

    def __init__(
        self,
        message: str = "",
        *,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(
            message,
            provider_id=provider_id,
            model_id=model_id,
            details=details,
            retryable=True,
        )
        self.timeout_seconds = timeout_seconds


# -- Configuration errors ----------------------------------------------------


class ConfigurationError(ModelMeshError):
    """Invalid or missing configuration.

    Raised during initialization when the config is malformed,
    required fields are missing, or referenced connectors do not exist.
    """

    def __init__(
        self,
        message: str = "",
        *,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(message, details=details, retryable=False)


# -- Budget errors -----------------------------------------------------------


class BudgetExceededError(ModelMeshError):
    """Budget limit has been exceeded.

    Raised when a per-request, daily, or monthly cost limit is breached
    and enforcement is enabled.

    Attributes:
        limit_type: Which limit was exceeded (``"per_request"``,
            ``"daily"``, ``"monthly"``).
        limit_value: The configured limit value.
        actual_value: The actual cost or accumulated spend.
    """

    def __init__(
        self,
        message: str = "",
        *,
        limit_type: Optional[str] = None,
        limit_value: Optional[float] = None,
        actual_value: Optional[float] = None,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(message, details=details, retryable=False)
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.actual_value = actual_value


__all__ = [
    "ModelMeshError",
    "RoutingError",
    "NoActiveModelError",
    "AllProvidersExhaustedError",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "ProviderTimeoutError",
    "ConfigurationError",
    "BudgetExceededError",
]
