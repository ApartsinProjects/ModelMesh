"""
Custom Secret Store Connector -- TOML File with Optional Encryption

Demonstrates how to implement a custom secret store connector for ModelMesh Lite
that reads secrets from a TOML configuration file. Supports optional Fernet
encryption for secrets at rest and an in-memory cache with configurable TTL.

This is useful for development environments, small deployments, or air-gapped
systems where a full secret manager (Vault, AWS Secrets Manager) is not needed.

See: docs/interfaces/SecretStore.md

Requirements:
    pip install cryptography
    Python 3.11+ (tomllib is in the standard library)
"""
# For a simpler CDK-based approach, see samples/cdk/python/

from __future__ import annotations

import os
import time
import tomllib  # Python 3.11+ standard library
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


# ---------------------------------------------------------------------------
# Supporting types (from SecretStore interface)
# ---------------------------------------------------------------------------

@dataclass
class SecretValue:
    """A resolved secret with optional version and expiration metadata."""
    value: str
    version: Optional[str] = None
    expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Interface ABCs (from SecretStore interface)
# ---------------------------------------------------------------------------

class SecretResolution(ABC):
    """Retrieve a secret value by name."""

    @abstractmethod
    def get(self, name: str) -> str:
        """Resolve a secret by name and return its value.

        Raises:
            KeyError: If the secret is not found and fail_on_missing is True.
        """
        ...


class SecretManagement(ABC):
    """Store, list, and remove secrets."""

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
    """Full secret store connector combining the required Resolution interface."""
    pass


# ---------------------------------------------------------------------------
# Cache entry for TTL-based secret caching
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    """An in-memory cached secret with its fetch timestamp."""
    value: str
    fetched_at: float  # time.monotonic() timestamp
    version: Optional[str] = None


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------

class TomlFileSecretStore(SecretStoreConnector, SecretManagement):
    """Secret store backed by a TOML file with optional Fernet encryption.

    Secrets are stored in a TOML file under a ``[secrets]`` table. Each key
    is a secret name and the value is the plaintext or encrypted string.

    When encryption is enabled, secret values are encrypted using Fernet
    symmetric encryption before writing to disk, and decrypted on read. The
    encryption key can be provided directly or loaded from an environment
    variable.

    Resolved secrets are cached in memory with a configurable TTL to avoid
    repeated file I/O and decryption overhead.

    TOML file format (plaintext mode):

        [secrets]
        openai-key = "sk-abc123..."
        anthropic-key = "sk-ant-xyz..."
        vllm-token = "internal-token-value"

    TOML file format (encrypted mode):

        [secrets]
        openai-key = "gAAAAABm..."
        anthropic-key = "gAAAAABm..."

    Configuration example (YAML):

        secret-store:
          connector: custom
          connector_class: TomlFileSecretStore
          config:
            file_path: "./secrets/api-keys.toml"
            encrypted: true
            encryption_key_env: "${env:MODELMESH_SECRET_KEY}"
            cache_ttl_ms: 300000        # 5 minutes
            fail_on_missing: true
          resolution:
            cache_enabled: true         # built-in cache (in addition to connector cache)
            cache_ttl: 300s
            reload_on_rotation: true
            fail_on_missing: true
    """

    def __init__(
        self,
        file_path: str | Path,
        encrypted: bool = False,
        encryption_key: Optional[str] = None,
        encryption_key_env: str = "MODELMESH_SECRET_KEY",
        cache_ttl_ms: float = 300_000.0,
        fail_on_missing: bool = True,
    ) -> None:
        """Initialize the TOML file secret store.

        Args:
            file_path: Path to the TOML secrets file.
            encrypted: If True, encrypt/decrypt secret values with Fernet.
            encryption_key: Direct Fernet key (base64-encoded). If not provided,
                            the key is read from the environment variable specified
                            by ``encryption_key_env``.
            encryption_key_env: Environment variable containing the Fernet key.
            cache_ttl_ms: Time-to-live in milliseconds for cached secrets.
                          Set to 0 to disable caching.
            fail_on_missing: If True, raise KeyError when a secret is not found.
                             If False, return an empty string.
        """
        self._path = Path(file_path)
        self._encrypted = encrypted
        self._cache_ttl_ms = cache_ttl_ms
        self._fail_on_missing = fail_on_missing

        # In-memory cache: name -> _CacheEntry
        self._cache: dict[str, _CacheEntry] = {}

        # Initialize Fernet cipher if encryption is enabled.
        self._fernet: Optional[Fernet] = None
        if self._encrypted:
            key = encryption_key or os.environ.get(encryption_key_env)
            if not key:
                raise ValueError(
                    f"Encryption enabled but no key provided. Set the "
                    f"'{encryption_key_env}' environment variable or pass "
                    f"'encryption_key' directly."
                )
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

        # Ensure the secrets file exists (create an empty one if not).
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("[secrets]\n")

    # ------------------------------------------------------------------
    # SecretResolution (required)
    # ------------------------------------------------------------------

    def get(self, name: str) -> str:
        """Resolve a secret by name.

        Checks the in-memory cache first. On cache miss or expiry, reads
        the TOML file and optionally decrypts the value.

        Args:
            name: The secret name to resolve.

        Returns:
            The secret value as a plaintext string.

        Raises:
            KeyError: If the secret is not found and fail_on_missing is True.
        """
        # Check the cache first.
        cached = self._cache.get(name)
        if cached is not None and self._cache_ttl_ms > 0:
            age_ms = (time.monotonic() - cached.fetched_at) * 1000
            if age_ms < self._cache_ttl_ms:
                return cached.value

        # Cache miss or expired; read from file.
        secrets = self._load_secrets()
        raw_value = secrets.get(name)

        if raw_value is None:
            if self._fail_on_missing:
                raise KeyError(
                    f"Secret '{name}' not found in {self._path}. "
                    f"Available secrets: {list(secrets.keys())}"
                )
            return ""

        # Decrypt if encryption is enabled.
        value = self._decrypt(raw_value) if self._encrypted else raw_value

        # Update cache.
        self._cache[name] = _CacheEntry(
            value=value,
            fetched_at=time.monotonic(),
        )

        return value

    # ------------------------------------------------------------------
    # SecretManagement (optional)
    # ------------------------------------------------------------------

    def set(self, name: str, value: str) -> None:
        """Store or update a secret in the TOML file.

        If encryption is enabled, the value is encrypted before writing.
        The in-memory cache is updated immediately.
        """
        secrets = self._load_secrets()

        # Encrypt if needed.
        stored_value = self._encrypt(value) if self._encrypted else value
        secrets[name] = stored_value

        self._save_secrets(secrets)

        # Update the cache with the plaintext value.
        self._cache[name] = _CacheEntry(
            value=value,
            fetched_at=time.monotonic(),
        )

    def list(self) -> list[str]:
        """Return the names of all secrets in the TOML file."""
        secrets = self._load_secrets()
        return sorted(secrets.keys())

    def delete(self, name: str) -> None:
        """Remove a secret from the TOML file.

        Raises:
            KeyError: If the secret does not exist.
        """
        secrets = self._load_secrets()

        if name not in secrets:
            raise KeyError(f"Secret '{name}' does not exist in {self._path}")

        del secrets[name]
        self._save_secrets(secrets)

        # Remove from cache.
        self._cache.pop(name, None)

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string using Fernet and return the token as a string."""
        if self._fernet is None:
            raise RuntimeError("Encryption is not configured")
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a Fernet token and return the plaintext string.

        Raises:
            ValueError: If the token is invalid or the key is wrong.
        """
        if self._fernet is None:
            raise RuntimeError("Encryption is not configured")
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return plaintext.decode("utf-8")
        except InvalidToken as exc:
            raise ValueError(
                f"Failed to decrypt secret. The encryption key may be wrong "
                f"or the ciphertext is corrupted."
            ) from exc

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------

    def _load_secrets(self) -> dict[str, str]:
        """Read the TOML file and return the [secrets] table as a dict."""
        with open(self._path, "rb") as f:
            data = tomllib.load(f)
        return dict(data.get("secrets", {}))

    def _save_secrets(self, secrets: dict[str, str]) -> None:
        """Write the secrets dict back to the TOML file.

        Note: tomllib is read-only (no writer in the stdlib). We generate
        the TOML manually for this simple flat structure. For production
        use, consider the ``tomli-w`` or ``tomlkit`` library.
        """
        lines = ["[secrets]"]
        for key in sorted(secrets.keys()):
            value = secrets[key]
            # Escape backslashes and quotes for TOML string literals.
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        lines.append("")  # Trailing newline.

        self._path.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Manually clear the in-memory secret cache.

        Useful after a key rotation or when you want to force a re-read
        from the TOML file.
        """
        self._cache.clear()

    def get_cache_stats(self) -> dict[str, int]:
        """Return cache statistics for monitoring."""
        now = time.monotonic()
        total = len(self._cache)
        expired = sum(
            1 for entry in self._cache.values()
            if ((now - entry.fetched_at) * 1000) >= self._cache_ttl_ms
        )
        return {
            "total_entries": total,
            "active_entries": total - expired,
            "expired_entries": expired,
        }

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            A base64-encoded key string suitable for the ``encryption_key``
            parameter or the ``MODELMESH_SECRET_KEY`` environment variable.
        """
        return Fernet.generate_key().decode("utf-8")


# ---------------------------------------------------------------------------
# Usage example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    # Generate a fresh encryption key for this demo.
    encryption_key = TomlFileSecretStore.generate_key()
    print(f"Generated encryption key: {encryption_key[:20]}...")

    # Create a temporary secrets file.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", delete=False
    ) as tmp:
        tmp.write("[secrets]\n")
        secrets_path = tmp.name

    print(f"Secrets file: {secrets_path}")

    # Initialize the store with encryption enabled.
    store = TomlFileSecretStore(
        file_path=secrets_path,
        encrypted=True,
        encryption_key=encryption_key,
        cache_ttl_ms=60_000,
        fail_on_missing=True,
    )

    # Store some secrets.
    print("\n=== Storing Secrets ===")
    store.set("openai-key", "sk-proj-abc123def456")
    store.set("anthropic-key", "sk-ant-xyz789")
    store.set("vllm-token", "internal-bearer-token")
    print("Stored 3 secrets.")

    # List all secret names.
    print(f"\nAvailable secrets: {store.list()}")

    # Resolve a secret (reads from cache on second call).
    print("\n=== Resolving Secrets ===")
    value = store.get("openai-key")
    print(f"openai-key = {value[:10]}...")

    # Resolve again (should come from cache).
    value2 = store.get("openai-key")
    print(f"openai-key (cached) = {value2[:10]}...")

    # Show cache stats.
    print(f"\nCache stats: {store.get_cache_stats()}")

    # Show the encrypted content on disk.
    print("\n=== Encrypted File Content ===")
    with open(secrets_path, "r") as f:
        content = f.read()
    # Show first 200 chars to prove it is encrypted.
    print(content[:300] + "..." if len(content) > 300 else content)

    # Delete a secret.
    print("\n=== Deleting Secret ===")
    store.delete("vllm-token")
    print(f"After deletion: {store.list()}")

    # Demonstrate error handling.
    print("\n=== Error Handling ===")
    try:
        store.get("nonexistent-key")
    except KeyError as e:
        print(f"Expected error: {e}")

    # Clean up.
    os.unlink(secrets_path)
    print("\nDone. Temporary file cleaned up.")
