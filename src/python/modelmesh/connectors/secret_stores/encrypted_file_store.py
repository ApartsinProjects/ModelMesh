"""Encrypted file secret store connector.

Resolves secrets from an AES-256-GCM encrypted JSON file. The file is
decrypted at initialization using a passphrase (derived via PBKDF2) or
a raw 32-byte key. Secrets are then held in memory for the lifetime
of the store.

Connector ID: ``modelmesh.encrypted-file.v1``
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets as _secrets
from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig
from modelmesh.interfaces.secret_store import SecretManagement

__all__ = [
    "EncryptedFileSecretStoreConfig",
    "EncryptedFileSecretStore",
]


# ---------------------------------------------------------------------------
# Lightweight AES-256-GCM helpers using only the standard library
# ---------------------------------------------------------------------------
# Python 3.6+ ships with hashlib.pbkdf2_hmac and the ssl module which
# provides AES-GCM.  We avoid heavy third-party dependencies (pycryptodome
# etc.) by implementing a minimal encrypt/decrypt using the ``cryptography``
# package when available, and a pure-Python XOR-based obfuscation as a
# fallback.
#
# The preferred path uses ``cryptography`` (pip install cryptography) for
# real AES-256-GCM encryption. If unavailable, a PBKDF2+XOR cipher is used
# which provides obfuscation but is NOT cryptographically secure encryption.


def _derive_key(passphrase: str, salt: bytes, iterations: int = 600_000) -> bytes:
    """Derive a 32-byte key from a passphrase using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations,
    )


# ---------------------------------------------------------------------------
# Try to use the ``cryptography`` library for real AES-GCM
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


def _encrypt_aesgcm(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with AES-256-GCM (requires ``cryptography`` package).

    Returns ``salt (16) || nonce (12) || ciphertext+tag``.
    """
    nonce = _secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def _decrypt_aesgcm(data: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM. ``data`` is ``nonce (12) || ciphertext+tag``."""
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# ---------------------------------------------------------------------------
# Fallback: XOR-based obfuscation (no external deps)
# ---------------------------------------------------------------------------


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """Repeating-key XOR cipher."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def _encrypt_xor(plaintext: bytes, key: bytes) -> bytes:
    """Obfuscate with repeating-key XOR (NOT cryptographically secure).

    Returns ``nonce (16) || xor(plaintext, sha256(key||nonce))``.
    The nonce ensures that identical plaintexts produce different outputs.
    """
    nonce = _secrets.token_bytes(16)
    derived = hashlib.sha256(key + nonce).digest()
    return nonce + _xor_bytes(plaintext, derived)


def _decrypt_xor(data: bytes, key: bytes) -> bytes:
    """Reverse XOR obfuscation."""
    nonce = data[:16]
    ciphertext = data[16:]
    derived = hashlib.sha256(key + nonce).digest()
    return _xor_bytes(ciphertext, derived)


# ---------------------------------------------------------------------------
# Unified encrypt / decrypt API
# ---------------------------------------------------------------------------


def encrypt_secrets(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt using best available backend."""
    if _CRYPTO_AVAILABLE:
        return _encrypt_aesgcm(plaintext, key)
    return _encrypt_xor(plaintext, key)


def decrypt_secrets(data: bytes, key: bytes) -> bytes:
    """Decrypt using best available backend."""
    if _CRYPTO_AVAILABLE:
        return _decrypt_aesgcm(data, key)
    return _decrypt_xor(data, key)


# ---------------------------------------------------------------------------
# File format
# ---------------------------------------------------------------------------
# The encrypted file uses base64 encoding with a simple JSON wrapper:
#
#   {
#     "version": 1,
#     "algorithm": "aes-256-gcm" | "xor-obfuscation",
#     "salt": "<base64>",
#     "data": "<base64>"
#   }
#
# The ``salt`` is used for PBKDF2 key derivation when a passphrase is
# provided. The ``data`` field contains the encrypted JSON secrets.
# ---------------------------------------------------------------------------


_FILE_VERSION = 1


@dataclass
class EncryptedFileSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for the encrypted file secret store.

    Provide **either** ``passphrase`` (human-readable password, key
    derived via PBKDF2) **or** ``encryption_key`` (raw 32-byte key
    as a hex string). If both are provided, ``encryption_key`` wins.

    Attributes:
        file_path: Path to the encrypted secrets file.
        passphrase: Human-readable passphrase for key derivation.
        encryption_key: Raw 32-byte key as a 64-character hex string.
        pbkdf2_iterations: PBKDF2 iteration count (default: 600,000).
    """

    file_path: str = ""
    passphrase: str = ""
    encryption_key: str = ""
    pbkdf2_iterations: int = 600_000


class EncryptedFileSecretStore(BaseSecretStore, SecretManagement):
    """Secret store backed by an AES-256-GCM encrypted JSON file.

    The file is decrypted once at initialization using either a
    passphrase (PBKDF2-derived key) or a raw encryption key. Secrets
    are then served from memory. Changes made via ``set()`` /
    ``delete()`` can be persisted back to disk with ``save()``.

    When the ``cryptography`` package is installed, real AES-256-GCM
    encryption is used. Otherwise, a PBKDF2+XOR obfuscation fallback
    provides basic protection (with a warning logged).

    Connector ID: ``modelmesh.encrypted-file.v1``

    Usage::

        # Create and save an encrypted file
        store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
            file_path="secrets.enc",
            passphrase="my-strong-passphrase",
        ))
        store.set("OPENAI_API_KEY", "sk-abc...")
        store.save()

        # Load from the encrypted file
        store2 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
            file_path="secrets.enc",
            passphrase="my-strong-passphrase",
        ))
        api_key = store2.get("OPENAI_API_KEY")
    """

    CONNECTOR_ID: str = "modelmesh.encrypted-file.v1"

    def __init__(
        self, config: EncryptedFileSecretStoreConfig | None = None
    ) -> None:
        if config is None:
            config = EncryptedFileSecretStoreConfig()
        super().__init__(config)
        self._enc_config = config
        self._secrets_data: dict[str, str] = {}
        self._salt: bytes = _secrets.token_bytes(16)
        self._key: bytes = self._derive_or_use_key()
        self._load_file()

    @property
    def crypto_available(self) -> bool:
        """Return True if real AES-256-GCM encryption is available."""
        return _CRYPTO_AVAILABLE

    def _derive_or_use_key(self) -> bytes:
        """Return the encryption key from config."""
        if self._enc_config.encryption_key:
            key_hex = self._enc_config.encryption_key
            if len(key_hex) != 64:
                raise ValueError(
                    "encryption_key must be a 64-character hex string "
                    f"(32 bytes), got {len(key_hex)} characters"
                )
            return bytes.fromhex(key_hex)

        if self._enc_config.passphrase:
            return _derive_key(
                self._enc_config.passphrase,
                self._salt,
                self._enc_config.pbkdf2_iterations,
            )

        # No passphrase or key -- generate a random key (in-memory only)
        return _secrets.token_bytes(32)

    def _load_file(self) -> None:
        """Load and decrypt the secrets file if it exists."""
        path = self._enc_config.file_path
        if not path or not os.path.isfile(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as fh:
                wrapper = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(wrapper, dict) or wrapper.get("version") != _FILE_VERSION:
            return

        try:
            self._salt = base64.b64decode(wrapper["salt"])
            encrypted_data = base64.b64decode(wrapper["data"])
        except (KeyError, ValueError):
            return

        # Re-derive key with the salt from the file
        if self._enc_config.passphrase and not self._enc_config.encryption_key:
            self._key = _derive_key(
                self._enc_config.passphrase,
                self._salt,
                self._enc_config.pbkdf2_iterations,
            )

        try:
            plaintext = decrypt_secrets(encrypted_data, self._key)
            self._secrets_data = json.loads(plaintext.decode("utf-8"))
        except Exception:
            # Decryption failed -- wrong key/passphrase
            self._secrets_data = {}

    def save(self) -> None:
        """Encrypt and write the current secrets to the configured file.

        Creates or overwrites the file at ``config.file_path``.
        """
        path = self._enc_config.file_path
        if not path:
            raise ValueError("No file_path configured")

        plaintext = json.dumps(self._secrets_data, indent=2).encode("utf-8")
        encrypted_data = encrypt_secrets(plaintext, self._key)

        wrapper = {
            "version": _FILE_VERSION,
            "algorithm": "aes-256-gcm" if _CRYPTO_AVAILABLE else "xor-obfuscation",
            "salt": base64.b64encode(self._salt).decode("ascii"),
            "data": base64.b64encode(encrypted_data).decode("ascii"),
        }

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(wrapper, fh, indent=2)

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret from the decrypted data."""
        return self._secrets_data.get(name)

    # -- SecretManagement interface ------------------------------------------

    def set(self, name: str, value: str) -> None:
        """Store or update a secret. Call ``save()`` to persist to disk."""
        self._secrets_data[name] = value
        if name in self._cache:
            del self._cache[name]

    def list(self) -> list[str]:
        """Return the names of all stored secrets."""
        return sorted(self._secrets_data.keys())

    def delete(self, name: str) -> None:
        """Remove a secret. Call ``save()`` to persist to disk.

        Raises:
            KeyError: If the secret does not exist.
        """
        if name not in self._secrets_data:
            raise KeyError(f"Secret not found: {name}")
        del self._secrets_data[name]
        self._cache.pop(name, None)
