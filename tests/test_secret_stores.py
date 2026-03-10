"""Comprehensive tests for all secret store connectors.

Tests cover: MemorySecretStore, EncryptedFileSecretStore, EnvSecretStore,
DotenvSecretStore, JsonSecretStore, KeyringSecretStore, BaseSecretStore,
custom secret store connectors, and configuration integration.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from modelmesh.interfaces.secret_store import (
    SecretStoreConnector,
    SecretManagement,
    SecretResolution,
    SecretValue,
)
from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig
from modelmesh.connectors.secret_stores.env_store import (
    EnvSecretStore,
    EnvSecretStoreConfig,
)
from modelmesh.connectors.secret_stores.memory_store import (
    MemorySecretStore,
    MemorySecretStoreConfig,
)
from modelmesh.connectors.secret_stores.encrypted_file_store import (
    EncryptedFileSecretStore,
    EncryptedFileSecretStoreConfig,
)
from modelmesh.connectors.secret_stores.json_store import (
    JsonSecretStore,
    JsonSecretStoreConfig,
)
from modelmesh.connectors.secret_stores.dotenv_store import (
    DotenvSecretStore,
    DotenvSecretStoreConfig,
)
from modelmesh.connectors.secret_stores.keyring_store import (
    KeyringSecretStore,
    KeyringSecretStoreConfig,
)


# ===========================================================================
# MemorySecretStore tests
# ===========================================================================


class TestMemorySecretStore(unittest.TestCase):
    """Test the in-memory secret store."""

    def test_connector_id(self):
        self.assertEqual(MemorySecretStore.CONNECTOR_ID, "modelmesh.memory-secrets.v1")

    def test_creation_with_secrets(self):
        store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={"KEY1": "val1", "KEY2": "val2"}
        ))
        self.assertEqual(store.get("KEY1"), "val1")
        self.assertEqual(store.get("KEY2"), "val2")

    def test_creation_empty(self):
        store = MemorySecretStore()
        with self.assertRaises(KeyError):
            store.get("NONEXISTENT")

    def test_fail_on_missing_false(self):
        store = MemorySecretStore(MemorySecretStoreConfig(
            fail_on_missing=False
        ))
        self.assertEqual(store.get("NONEXISTENT"), "")

    def test_set_and_get(self):
        store = MemorySecretStore()
        store.set("NEW_KEY", "new_value")
        self.assertEqual(store.get("NEW_KEY"), "new_value")

    def test_set_overwrites(self):
        store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={"KEY": "old"}
        ))
        store.set("KEY", "new")
        self.assertEqual(store.get("KEY"), "new")

    def test_list_secrets(self):
        store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={"B": "2", "A": "1", "C": "3"}
        ))
        self.assertEqual(store.list(), ["A", "B", "C"])

    def test_delete_secret(self):
        store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={"KEY": "val"}
        ))
        store.delete("KEY")
        with self.assertRaises(KeyError):
            store.get("KEY")

    def test_delete_nonexistent_raises(self):
        store = MemorySecretStore()
        with self.assertRaises(KeyError):
            store.delete("NONEXISTENT")

    def test_implements_interfaces(self):
        store = MemorySecretStore()
        self.assertIsInstance(store, SecretStoreConnector)
        self.assertIsInstance(store, SecretManagement)
        self.assertIsInstance(store, SecretResolution)

    def test_caching_behavior(self):
        """MemorySecretStore inherits BaseSecretStore caching."""
        store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={"K": "original"},
            cache_enabled=True,
        ))
        self.assertEqual(store.get("K"), "original")
        # Modify underlying dict directly
        store._config.secrets["K"] = "modified"
        # Cache should still return original
        self.assertEqual(store.get("K"), "original")

    def test_set_invalidates_cache(self):
        """set() should invalidate cache for that key."""
        store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={"K": "original"},
            cache_enabled=True,
        ))
        self.assertEqual(store.get("K"), "original")
        store.set("K", "updated")
        self.assertEqual(store.get("K"), "updated")


# ===========================================================================
# EncryptedFileSecretStore tests
# ===========================================================================


class TestEncryptedFileSecretStore(unittest.TestCase):
    """Test the encrypted file secret store."""

    def test_connector_id(self):
        self.assertEqual(
            EncryptedFileSecretStore.CONNECTOR_ID,
            "modelmesh.encrypted-file.v1",
        )

    def test_in_memory_only(self):
        """Works without a file -- pure in-memory mode."""
        store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
            passphrase="test-pass"
        ))
        store.set("KEY", "value123")
        self.assertEqual(store.get("KEY"), "value123")

    def test_save_and_load_with_passphrase(self):
        """Round-trip: save encrypted file, reload in new instance."""
        with tempfile.NamedTemporaryFile(
            suffix=".enc", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            # Create and save
            store1 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                file_path=tmp_path,
                passphrase="strong-passphrase-123",
            ))
            store1.set("API_KEY", "sk-test-12345")
            store1.set("SECRET", "super-secret-value")
            store1.save()

            # Verify file exists and is JSON
            with open(tmp_path, "r") as f:
                wrapper = json.load(f)
            self.assertEqual(wrapper["version"], 1)
            self.assertIn("salt", wrapper)
            self.assertIn("data", wrapper)

            # Load in new instance with same passphrase
            store2 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                file_path=tmp_path,
                passphrase="strong-passphrase-123",
            ))
            self.assertEqual(store2.get("API_KEY"), "sk-test-12345")
            self.assertEqual(store2.get("SECRET"), "super-secret-value")
        finally:
            os.unlink(tmp_path)

    def test_save_and_load_with_hex_key(self):
        """Round-trip with raw hex encryption key."""
        hex_key = "a" * 64  # 32 bytes as hex

        with tempfile.NamedTemporaryFile(
            suffix=".enc", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            store1 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                file_path=tmp_path,
                encryption_key=hex_key,
            ))
            store1.set("KEY", "value")
            store1.save()

            store2 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                file_path=tmp_path,
                encryption_key=hex_key,
            ))
            self.assertEqual(store2.get("KEY"), "value")
        finally:
            os.unlink(tmp_path)

    def test_wrong_passphrase_fails_gracefully(self):
        """Loading with wrong passphrase returns empty store."""
        with tempfile.NamedTemporaryFile(
            suffix=".enc", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            store1 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                file_path=tmp_path,
                passphrase="correct-password",
            ))
            store1.set("KEY", "secret")
            store1.save()

            # Load with wrong passphrase
            store2 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                file_path=tmp_path,
                passphrase="wrong-password",
                fail_on_missing=False,
            ))
            # Should return empty string (decryption fails silently)
            self.assertEqual(store2.get("KEY"), "")
        finally:
            os.unlink(tmp_path)

    def test_invalid_hex_key_length(self):
        """Invalid hex key length raises ValueError."""
        with self.assertRaises(ValueError):
            EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                encryption_key="tooshort",
            ))

    def test_list_and_delete(self):
        store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
            passphrase="test"
        ))
        store.set("A", "1")
        store.set("B", "2")
        self.assertEqual(store.list(), ["A", "B"])
        store.delete("A")
        self.assertEqual(store.list(), ["B"])

    def test_delete_nonexistent_raises(self):
        store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
            passphrase="test"
        ))
        with self.assertRaises(KeyError):
            store.delete("NOPE")

    def test_save_without_file_path_raises(self):
        store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
            passphrase="test"
        ))
        with self.assertRaises(ValueError):
            store.save()

    def test_nonexistent_file_creates_empty_store(self):
        store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
            file_path="/nonexistent/path/secrets.enc",
            passphrase="test",
            fail_on_missing=False,
        ))
        self.assertEqual(store.get("KEY"), "")

    def test_implements_interfaces(self):
        store = EncryptedFileSecretStore()
        self.assertIsInstance(store, SecretStoreConnector)
        self.assertIsInstance(store, SecretManagement)

    def test_crypto_available_property(self):
        """crypto_available property should be a boolean."""
        store = EncryptedFileSecretStore()
        self.assertIsInstance(store.crypto_available, bool)

    def test_encrypted_file_not_plaintext(self):
        """Verify the saved file does not contain plaintext secrets."""
        with tempfile.NamedTemporaryFile(
            suffix=".enc", delete=False, mode="w"
        ) as tmp:
            tmp_path = tmp.name

        try:
            store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
                file_path=tmp_path,
                passphrase="test",
            ))
            store.set("MY_SECRET", "super-secret-value-12345")
            store.save()

            with open(tmp_path, "r") as f:
                content = f.read()
            self.assertNotIn("super-secret-value-12345", content)
            self.assertNotIn("MY_SECRET", content)
        finally:
            os.unlink(tmp_path)


# ===========================================================================
# EnvSecretStore tests
# ===========================================================================


class TestEnvSecretStoreComprehensive(unittest.TestCase):
    """Comprehensive tests for the environment variable secret store."""

    def test_connector_id(self):
        self.assertEqual(EnvSecretStore.CONNECTOR_ID, "modelmesh.env.v1")

    def test_read_env_var(self):
        os.environ["TEST_ENV_SECRET_STORE_KEY"] = "test-value"
        try:
            store = EnvSecretStore()
            self.assertEqual(store.get("TEST_ENV_SECRET_STORE_KEY"), "test-value")
        finally:
            del os.environ["TEST_ENV_SECRET_STORE_KEY"]

    def test_missing_env_var_with_fail_on_missing_true(self):
        store = EnvSecretStore(EnvSecretStoreConfig(fail_on_missing=True))
        with self.assertRaises(KeyError):
            store.get("DEFINITELY_NOT_SET_12345")

    def test_missing_env_var_with_fail_on_missing_false(self):
        store = EnvSecretStore(EnvSecretStoreConfig(fail_on_missing=False))
        self.assertEqual(store.get("DEFINITELY_NOT_SET_12345"), "")

    def test_prefix(self):
        os.environ["MM_TEST_KEY"] = "prefixed-value"
        try:
            store = EnvSecretStore(EnvSecretStoreConfig(prefix="MM_"))
            self.assertEqual(store.get("TEST_KEY"), "prefixed-value")
        finally:
            del os.environ["MM_TEST_KEY"]

    def test_default_config(self):
        store = EnvSecretStore()
        self.assertIsInstance(store, SecretStoreConnector)

    def test_implements_interface(self):
        store = EnvSecretStore()
        self.assertIsInstance(store, SecretStoreConnector)
        self.assertIsInstance(store, SecretResolution)


# ===========================================================================
# DotenvSecretStore tests
# ===========================================================================


class TestDotenvSecretStoreComprehensive(unittest.TestCase):
    """Comprehensive tests for the dotenv file secret store."""

    def _write_env_file(self, content: str) -> str:
        """Write content to a temp .env file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".env")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_connector_id(self):
        self.assertEqual(DotenvSecretStore.CONNECTOR_ID, "modelmesh.dotenv.v1")

    def test_basic_parsing(self):
        path = self._write_env_file("API_KEY=sk-test123\nSECRET=mysecret\n")
        try:
            store = DotenvSecretStore(DotenvSecretStoreConfig(file_path=path))
            self.assertEqual(store.get("API_KEY"), "sk-test123")
            self.assertEqual(store.get("SECRET"), "mysecret")
        finally:
            os.unlink(path)

    def test_comments_and_blank_lines(self):
        content = "# This is a comment\n\nKEY=value\n# Another comment\n"
        path = self._write_env_file(content)
        try:
            store = DotenvSecretStore(DotenvSecretStoreConfig(file_path=path))
            self.assertEqual(store.get("KEY"), "value")
        finally:
            os.unlink(path)

    def test_quoted_values(self):
        content = 'KEY1="double quoted"\nKEY2=\'single quoted\'\n'
        path = self._write_env_file(content)
        try:
            store = DotenvSecretStore(DotenvSecretStoreConfig(file_path=path))
            self.assertEqual(store.get("KEY1"), "double quoted")
            self.assertEqual(store.get("KEY2"), "single quoted")
        finally:
            os.unlink(path)

    def test_inline_comments(self):
        content = "KEY=value # this is an inline comment\n"
        path = self._write_env_file(content)
        try:
            store = DotenvSecretStore(DotenvSecretStoreConfig(file_path=path))
            self.assertEqual(store.get("KEY"), "value")
        finally:
            os.unlink(path)

    def test_multiline_backslash(self):
        content = "KEY=first\\\nsecond\n"
        path = self._write_env_file(content)
        try:
            store = DotenvSecretStore(DotenvSecretStoreConfig(file_path=path))
            self.assertEqual(store.get("KEY"), "firstsecond")
        finally:
            os.unlink(path)

    def test_env_var_override(self):
        """Environment variables take precedence by default."""
        path = self._write_env_file("MY_TEST_KEY=from-file\n")
        os.environ["MY_TEST_KEY"] = "from-env"
        try:
            store = DotenvSecretStore(DotenvSecretStoreConfig(
                file_path=path, override_env=False
            ))
            self.assertEqual(store.get("MY_TEST_KEY"), "from-env")
        finally:
            del os.environ["MY_TEST_KEY"]
            os.unlink(path)

    def test_file_override_env(self):
        """File values take precedence when override_env=True."""
        path = self._write_env_file("MY_TEST_KEY2=from-file\n")
        os.environ["MY_TEST_KEY2"] = "from-env"
        try:
            store = DotenvSecretStore(DotenvSecretStoreConfig(
                file_path=path, override_env=True
            ))
            self.assertEqual(store.get("MY_TEST_KEY2"), "from-file")
        finally:
            del os.environ["MY_TEST_KEY2"]
            os.unlink(path)

    def test_missing_file(self):
        store = DotenvSecretStore(DotenvSecretStoreConfig(
            file_path="/nonexistent/.env",
            fail_on_missing=False,
        ))
        self.assertEqual(store.get("ANYTHING"), "")


# ===========================================================================
# JsonSecretStore tests
# ===========================================================================


class TestJsonSecretStoreComprehensive(unittest.TestCase):
    """Comprehensive tests for the JSON file secret store."""

    def _write_json_file(self, data: dict) -> str:
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        return path

    def test_connector_id(self):
        self.assertEqual(JsonSecretStore.CONNECTOR_ID, "modelmesh.json-secrets.v1")

    def test_flat_json(self):
        path = self._write_json_file({"KEY1": "val1", "KEY2": "val2"})
        try:
            store = JsonSecretStore(JsonSecretStoreConfig(file_path=path))
            self.assertEqual(store.get("KEY1"), "val1")
            self.assertEqual(store.get("KEY2"), "val2")
        finally:
            os.unlink(path)

    def test_nested_json_with_dot_notation(self):
        path = self._write_json_file({
            "providers": {
                "openai": {"api_key": "sk-test123"},
                "anthropic": {"api_key": "sk-ant-test"},
            }
        })
        try:
            store = JsonSecretStore(JsonSecretStoreConfig(file_path=path))
            self.assertEqual(
                store.get("providers.openai.api_key"), "sk-test123"
            )
            self.assertEqual(
                store.get("providers.anthropic.api_key"), "sk-ant-test"
            )
        finally:
            os.unlink(path)

    def test_json_path_scoping(self):
        path = self._write_json_file({
            "secrets": {
                "production": {"API_KEY": "prod-key"},
                "development": {"API_KEY": "dev-key"},
            }
        })
        try:
            store = JsonSecretStore(JsonSecretStoreConfig(
                file_path=path, json_path="secrets.production"
            ))
            self.assertEqual(store.get("API_KEY"), "prod-key")
        finally:
            os.unlink(path)

    def test_missing_key_raises(self):
        path = self._write_json_file({"KEY": "val"})
        try:
            store = JsonSecretStore(JsonSecretStoreConfig(
                file_path=path, fail_on_missing=True
            ))
            with self.assertRaises(KeyError):
                store.get("MISSING")
        finally:
            os.unlink(path)

    def test_missing_key_returns_empty(self):
        path = self._write_json_file({"KEY": "val"})
        try:
            store = JsonSecretStore(JsonSecretStoreConfig(
                file_path=path, fail_on_missing=False
            ))
            self.assertEqual(store.get("MISSING"), "")
        finally:
            os.unlink(path)

    def test_numeric_values_converted(self):
        path = self._write_json_file({"PORT": 8080, "ENABLED": True})
        try:
            store = JsonSecretStore(JsonSecretStoreConfig(file_path=path))
            self.assertEqual(store.get("PORT"), "8080")
            self.assertEqual(store.get("ENABLED"), "True")
        finally:
            os.unlink(path)

    def test_missing_file(self):
        store = JsonSecretStore(JsonSecretStoreConfig(
            file_path="/nonexistent/secrets.json",
            fail_on_missing=False,
        ))
        self.assertEqual(store.get("ANYTHING"), "")


# ===========================================================================
# KeyringSecretStore tests
# ===========================================================================


class TestKeyringSecretStoreComprehensive(unittest.TestCase):
    """Tests for the OS keyring secret store."""

    def test_connector_id(self):
        self.assertEqual(KeyringSecretStore.CONNECTOR_ID, "modelmesh.keyring.v1")

    def test_default_service_name(self):
        store = KeyringSecretStore()
        self.assertEqual(store._keyring_config.service_name, "modelmesh")

    def test_custom_service_name(self):
        store = KeyringSecretStore(KeyringSecretStoreConfig(
            service_name="my-app"
        ))
        self.assertEqual(store._keyring_config.service_name, "my-app")

    def test_keyring_available_property(self):
        store = KeyringSecretStore()
        # Property should be boolean regardless of keyring installation
        self.assertIsInstance(store.keyring_available, bool)

    def test_missing_key_without_keyring(self):
        """When keyring is not installed, fails gracefully."""
        store = KeyringSecretStore(KeyringSecretStoreConfig(
            fail_on_missing=False
        ))
        if not store.keyring_available:
            result = store.get("ANYTHING")
            self.assertEqual(result, "")

    def test_implements_interface(self):
        store = KeyringSecretStore()
        self.assertIsInstance(store, SecretStoreConnector)


# ===========================================================================
# BaseSecretStore tests
# ===========================================================================


class TestBaseSecretStoreComprehensive(unittest.TestCase):
    """Test the CDK BaseSecretStore implementation."""

    def test_resolve_from_config(self):
        store = BaseSecretStore(BaseSecretStoreConfig(
            secrets={"KEY": "val"}
        ))
        self.assertEqual(store.get("KEY"), "val")

    def test_fail_on_missing_true(self):
        store = BaseSecretStore(BaseSecretStoreConfig(
            fail_on_missing=True
        ))
        with self.assertRaises(KeyError):
            store.get("MISSING")

    def test_fail_on_missing_false(self):
        store = BaseSecretStore(BaseSecretStoreConfig(
            fail_on_missing=False
        ))
        self.assertEqual(store.get("MISSING"), "")

    def test_caching(self):
        store = BaseSecretStore(BaseSecretStoreConfig(
            secrets={"K": "original"},
            cache_enabled=True,
        ))
        self.assertEqual(store.get("K"), "original")
        # Modify the backing dict
        store._config.secrets["K"] = "changed"
        # Should still return cached value
        self.assertEqual(store.get("K"), "original")

    def test_cache_disabled(self):
        store = BaseSecretStore(BaseSecretStoreConfig(
            secrets={"K": "original"},
            cache_enabled=False,
        ))
        self.assertEqual(store.get("K"), "original")
        store._config.secrets["K"] = "changed"
        self.assertEqual(store.get("K"), "changed")

    def test_clear_cache(self):
        store = BaseSecretStore(BaseSecretStoreConfig(
            secrets={"K": "original"},
            cache_enabled=True,
        ))
        store.get("K")
        store._config.secrets["K"] = "changed"
        store.clear_cache()
        self.assertEqual(store.get("K"), "changed")

    def test_custom_subclass(self):
        """Users can create custom secret store connectors by subclassing."""

        class VaultSecretStore(BaseSecretStore):
            """Example custom connector backed by a mock vault."""

            CONNECTOR_ID = "mycompany.vault.v1"

            def __init__(self, vault_url: str):
                super().__init__(BaseSecretStoreConfig())
                self._vault = {"db_password": "s3cr3t", "api_token": "tok-123"}

            def _resolve(self, name: str) -> str | None:
                return self._vault.get(name)

        store = VaultSecretStore(vault_url="https://vault.example.com")
        self.assertEqual(store.get("db_password"), "s3cr3t")
        self.assertEqual(store.get("api_token"), "tok-123")
        self.assertIsInstance(store, SecretStoreConnector)

    def test_custom_subclass_with_secret_management(self):
        """Custom connector can implement both interfaces."""

        class ManagedStore(BaseSecretStore, SecretManagement):
            CONNECTOR_ID = "custom.managed.v1"

            def __init__(self):
                super().__init__(BaseSecretStoreConfig())
                self._data: dict[str, str] = {}

            def _resolve(self, name: str) -> str | None:
                return self._data.get(name)

            def set(self, name: str, value: str) -> None:
                self._data[name] = value

            def list(self) -> list[str]:
                return sorted(self._data.keys())

            def delete(self, name: str) -> None:
                del self._data[name]

        store = ManagedStore()
        store.set("test", "value")
        self.assertEqual(store.get("test"), "value")
        self.assertEqual(store.list(), ["test"])
        store.delete("test")
        self.assertEqual(store.list(), [])


# ===========================================================================
# SecretValue data type tests
# ===========================================================================


class TestSecretValue(unittest.TestCase):
    """Test the SecretValue dataclass."""

    def test_basic_creation(self):
        sv = SecretValue(value="secret123")
        self.assertEqual(sv.value, "secret123")
        self.assertIsNone(sv.version)
        self.assertIsNone(sv.expires_at)

    def test_with_metadata(self):
        from datetime import datetime

        now = datetime.now()
        sv = SecretValue(value="s", version="v2", expires_at=now)
        self.assertEqual(sv.version, "v2")
        self.assertEqual(sv.expires_at, now)


# ===========================================================================
# ConnectorRegistry integration tests
# ===========================================================================


class TestSecretStoreRegistry(unittest.TestCase):
    """Test that all secret stores are in the connector registry."""

    def test_all_stores_registered(self):
        from modelmesh.connectors import CONNECTOR_REGISTRY

        expected_ids = [
            "modelmesh.env.v1",
            "modelmesh.dotenv.v1",
            "modelmesh.json-secrets.v1",
            "modelmesh.keyring.v1",
            "modelmesh.memory-secrets.v1",
            "modelmesh.encrypted-file.v1",
        ]
        for connector_id in expected_ids:
            self.assertIn(
                connector_id,
                CONNECTOR_REGISTRY,
                f"Missing from registry: {connector_id}",
            )

    def test_registry_classes_match(self):
        from modelmesh.connectors import CONNECTOR_REGISTRY

        self.assertIs(
            CONNECTOR_REGISTRY["modelmesh.memory-secrets.v1"], MemorySecretStore
        )
        self.assertIs(
            CONNECTOR_REGISTRY["modelmesh.encrypted-file.v1"],
            EncryptedFileSecretStore,
        )
        self.assertIs(
            CONNECTOR_REGISTRY["modelmesh.env.v1"], EnvSecretStore
        )


# ===========================================================================
# MeshConfig secrets integration tests
# ===========================================================================


class TestMeshConfigSecrets(unittest.TestCase):
    """Test that MeshConfig properly exposes secrets configuration."""

    def test_secrets_section_accessible(self):
        from modelmesh.config.mesh_config import MeshConfig

        config = MeshConfig(raw={
            "secrets": {
                "connector": "modelmesh.memory-secrets.v1",
                "config": {
                    "secrets": {
                        "OPENAI_API_KEY": "sk-test",
                    },
                },
            },
        })
        self.assertEqual(config.secrets["connector"], "modelmesh.memory-secrets.v1")

    def test_empty_secrets_section(self):
        from modelmesh.config.mesh_config import MeshConfig

        config = MeshConfig(raw={})
        self.assertEqual(config.secrets, {})

    def test_resolve_store_from_config(self):
        """Verify that a secret store can be instantiated from config."""
        from modelmesh.connectors import CONNECTOR_REGISTRY

        config = {
            "connector": "modelmesh.memory-secrets.v1",
            "config": {
                "secrets": {
                    "OPENAI_API_KEY": "sk-from-config",
                },
            },
        }
        connector_id = config["connector"]
        store_cls = CONNECTOR_REGISTRY[connector_id]
        store_config = MemorySecretStoreConfig(**config["config"])
        store = store_cls(store_config)
        self.assertEqual(store.get("OPENAI_API_KEY"), "sk-from-config")


# ===========================================================================
# Cross-store comparison tests
# ===========================================================================


class TestSecretStoreInteroperability(unittest.TestCase):
    """Test that different stores work together and are interchangeable."""

    def test_all_stores_share_interface(self):
        """All stores implement the same base interface."""
        stores = [
            MemorySecretStore(MemorySecretStoreConfig(
                secrets={"K": "v"}, fail_on_missing=False
            )),
            EnvSecretStore(EnvSecretStoreConfig(fail_on_missing=False)),
            BaseSecretStore(BaseSecretStoreConfig(
                secrets={"K": "v"}, fail_on_missing=False
            )),
        ]
        for store in stores:
            self.assertIsInstance(store, SecretStoreConnector)
            # All should handle missing keys gracefully
            result = store.get("NONEXISTENT_KEY_12345")
            self.assertIsInstance(result, str)

    def test_memory_store_as_drop_in_replacement(self):
        """MemorySecretStore can replace any other store in config."""
        # Simulate switching from env to memory store
        def get_api_key(store: SecretStoreConnector) -> str:
            return store.get("API_KEY")

        mem_store = MemorySecretStore(MemorySecretStoreConfig(
            secrets={"API_KEY": "sk-memory"}
        ))
        self.assertEqual(get_api_key(mem_store), "sk-memory")


if __name__ == "__main__":
    unittest.main()
