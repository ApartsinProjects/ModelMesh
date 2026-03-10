"""In-memory secret store connector.

Resolves secrets from a user-provided dictionary. Keys are supplied at
construction time and held in memory for the lifetime of the store.
This is the simplest store, useful for testing, scripting, and cases
where the caller already has API keys in hand.

Connector ID: ``modelmesh.memory.v1``
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig
from modelmesh.interfaces.secret_store import SecretManagement

__all__ = [
    "MemorySecretStoreConfig",
    "MemorySecretStore",
]


@dataclass
class MemorySecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for the in-memory secret store.

    Attributes:
        secrets: Dictionary of secret name/value pairs provided by the
            caller. This is the primary data source for the store.
    """

    # Inherited ``secrets`` field from BaseSecretStoreConfig already
    # holds the dict; no extra fields needed.
    pass


class MemorySecretStore(BaseSecretStore, SecretManagement):
    """Secret store backed entirely by an in-memory dictionary.

    All secrets are held in a plain ``dict`` and never touch disk or
    network. The caller supplies keys at construction time. The store
    also implements ``SecretManagement`` so secrets can be added,
    listed, and removed at runtime.

    This connector is ideal for:

    - **Unit testing** -- inject known secrets without environment setup.
    - **Scripts / notebooks** -- pass keys directly from user input.
    - **Hardcoded keys** -- embed API keys for personal tools.

    Connector ID: ``modelmesh.memory.v1``

    Usage::

        store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={
                "OPENAI_API_KEY": "sk-abc...",
                "ANTHROPIC_API_KEY": "sk-ant...",
            }
        ))
        api_key = store.get("OPENAI_API_KEY")

        # Add a new secret at runtime
        store.set("NEW_KEY", "value123")

        # List all secret names
        names = store.list()  # ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NEW_KEY"]
    """

    CONNECTOR_ID: str = "modelmesh.memory-secrets.v1"

    def __init__(self, config: MemorySecretStoreConfig | None = None) -> None:
        if config is None:
            config = MemorySecretStoreConfig()
        super().__init__(config)
        self._mem_config = config

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret from the in-memory dictionary."""
        return self._config.secrets.get(name)

    # -- SecretManagement interface ------------------------------------------

    def set(self, name: str, value: str) -> None:
        """Store or update a secret in memory.

        Also clears the cache entry for this name so the next ``get()``
        call picks up the new value.
        """
        self._config.secrets[name] = value
        # Invalidate cache for this key
        if name in self._cache:
            del self._cache[name]

    def list(self) -> list[str]:
        """Return the names of all stored secrets."""
        return sorted(self._config.secrets.keys())

    def delete(self, name: str) -> None:
        """Remove a secret from the store.

        Raises:
            KeyError: If the secret does not exist.
        """
        if name not in self._config.secrets:
            raise KeyError(f"Secret not found: {name}")
        del self._config.secrets[name]
        # Remove from cache too
        self._cache.pop(name, None)
