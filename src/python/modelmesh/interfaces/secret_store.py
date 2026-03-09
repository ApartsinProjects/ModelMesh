"""Secret store connector interface and associated data types.

Defines the abstract SecretStoreConnector interface for resolving API keys
and tokens from a secure backend at runtime. Configuration references
secrets by name; the library resolves them through the configured store
at initialization and on rotation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SecretValue:
    """A resolved secret with optional version and expiration metadata."""

    value: str
    version: Optional[str] = None
    expires_at: Optional[datetime] = None


class SecretResolution(ABC):
    """Retrieve a secret value by name.

    The only required interface -- all secret store connectors must
    implement this. Called at initialization and on rotation when a
    new provider is activated.
    """

    @abstractmethod
    def get(self, name: str) -> str:
        """Resolve a secret by name and return its value.

        Raises:
            KeyError: If the secret is not found and fail_on_missing is True.
        """
        ...


class SecretManagement(ABC):
    """Store, list, and remove secrets.

    Optional interface used by the CLI utility for credential provisioning
    across environments. Not required for runtime operation.
    """

    @abstractmethod
    def set(self, name: str, value: str) -> None:
        """Store or update a secret."""
        ...

    @abstractmethod
    def list(self) -> list[str]:
        """Return the names of all available secrets."""
        ...

    @abstractmethod
    def delete(self, name: str) -> None:
        """Remove a secret by name.

        Raises:
            KeyError: If the secret does not exist.
        """
        ...


class SecretStoreConnector(SecretResolution):
    """Full secret store connector combining the required Resolution interface.

    Implementations that support credential provisioning should also
    inherit from SecretManagement.
    """

    pass


__all__ = [
    "SecretValue",
    "SecretResolution",
    "SecretManagement",
    "SecretStoreConnector",
]
