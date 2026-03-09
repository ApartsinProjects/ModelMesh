"""OS keychain secret store connector.

Resolves secrets from the operating system's native credential store
using the ``keyring`` library. Falls back gracefully if the library is
not installed.

Connector ID: ``modelmesh.keyring.v1``
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig

__all__ = [
    "KeyringSecretStoreConfig",
    "KeyringSecretStore",
]

# Attempt to import keyring at module level so we can detect
# availability without re-importing on every call.
try:
    import keyring as _keyring

    _KEYRING_AVAILABLE = True
except ImportError:
    _keyring = None  # type: ignore[assignment]
    _KEYRING_AVAILABLE = False


@dataclass
class KeyringSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for the OS keychain secret store.

    Attributes:
        service_name: The service/application name under which secrets
            are stored in the OS keychain. Defaults to ``"modelmesh"``.
    """

    service_name: str = "modelmesh"


class KeyringSecretStore(BaseSecretStore):
    """Secret store backed by the operating system's keychain.

    Uses the ``keyring`` library to read secrets from the OS-native
    credential store (macOS Keychain, Windows Credential Locker,
    Linux SecretService / KWallet).

    If the ``keyring`` package is not installed, initialization
    succeeds but all lookups return ``None`` (or raise ``KeyError``
    if ``fail_on_missing`` is ``True``). A warning attribute
    ``keyring_available`` indicates whether the backend is usable.

    Connector ID: ``modelmesh.keyring.v1``

    Usage::

        store = KeyringSecretStore(KeyringSecretStoreConfig(
            service_name="modelmesh-prod",
        ))
        if store.keyring_available:
            api_key = store.get("OPENAI_API_KEY")
    """

    CONNECTOR_ID: str = "modelmesh.keyring.v1"

    def __init__(self, config: KeyringSecretStoreConfig | None = None) -> None:
        if config is None:
            config = KeyringSecretStoreConfig()
        super().__init__(config)
        self._keyring_config = config

    @property
    def keyring_available(self) -> bool:
        """Return True if the ``keyring`` library is installed."""
        return _KEYRING_AVAILABLE

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret by looking it up in the OS keychain.

        Returns ``None`` if the ``keyring`` library is not installed
        or if the secret is not found in the keychain.
        """
        if not _KEYRING_AVAILABLE:
            return None

        try:
            value = _keyring.get_password(
                self._keyring_config.service_name, name
            )
            return value
        except Exception:
            # Gracefully handle any keyring backend errors
            return None
