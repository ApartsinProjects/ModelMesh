"""Base secret store implementation for the CDK.

Implements the SecretStoreConnector interface with an in-memory
dictionary backend and optional TTL-based caching. Subclasses override
the ``_resolve(name)`` hook to read secrets from files, vaults, or
cloud services.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from modelmesh.interfaces.secret_store import SecretStoreConnector


@dataclass
class BaseSecretStoreConfig:
    """Configuration for a BaseSecretStore instance."""

    secrets: dict[str, str] = field(default_factory=dict)
    cache_enabled: bool = True
    cache_ttl_ms: int = 300_000
    fail_on_missing: bool = True


class BaseSecretStore(SecretStoreConnector):
    """Base implementation of the SecretStoreConnector interface.

    Provides in-memory secret storage with optional TTL-based caching.
    Subclasses override ``_resolve`` to read secrets from external
    backends (files, vaults, cloud services).
    """

    def __init__(self, config: BaseSecretStoreConfig) -> None:
        self._config = config
        self._cache: dict[str, tuple[str, float]] = {}

    def get(self, name: str) -> str:
        """Resolve a secret by name and return its value.

        Checks the cache first (if enabled), then delegates to
        ``_resolve``. Caches the result with a TTL if caching is
        enabled.

        Raises:
            KeyError: If the secret is not found and fail_on_missing
                      is True.
        """
        # Check cache
        if self._config.cache_enabled and name in self._cache:
            value, expires_at = self._cache[name]
            if time.monotonic() < expires_at:
                return value
            del self._cache[name]

        # Resolve from backend
        value = self._resolve(name)
        if value is None:
            if self._config.fail_on_missing:
                raise KeyError(f"Secret not found: {name}")
            return ""

        # Cache the result
        if self._config.cache_enabled:
            expires_at = time.monotonic() + (self._config.cache_ttl_ms / 1000.0)
            self._cache[name] = (value, expires_at)

        return value

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret by name from the configured backend.

        The default implementation looks up the name in the
        ``config.secrets`` dictionary. Override this method to read
        from files, environment variables, vaults, or cloud services.

        Returns:
            The secret value, or None if not found.
        """
        return self._config.secrets.get(name)

    def clear_cache(self) -> None:
        """Clear all cached secret values."""
        self._cache.clear()


__all__ = [
    "BaseSecretStoreConfig",
    "BaseSecretStore",
]
