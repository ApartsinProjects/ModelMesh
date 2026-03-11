"""JSON file secret store connector.

Resolves secrets from a JSON file. Supports nested objects with
dot-notation paths (e.g., ``"providers.openai.api_key"``).

Connector ID: ``modelmesh.json-secrets.v1``
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig

__all__ = [
    "JsonSecretStoreConfig",
    "JsonSecretStore",
]


@dataclass
class JsonSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for the JSON file secret store.

    Attributes:
        file_path: Path to the JSON file containing secrets. Required.
        json_path: Optional dot-notation path to a nested object within
            the JSON file. For example, ``"secrets.production"`` would
            scope all lookups to ``data["secrets"]["production"]``.
    """

    file_path: str = ""
    json_path: str = ""


class JsonSecretStore(BaseSecretStore):
    """Secret store that resolves values from a JSON file.

    Reads a JSON file and resolves secret names against its keys.
    Supports nested JSON objects with dot-notation access:

    - A secret name ``"api_key"`` looks up ``data["api_key"]``.
    - A secret name ``"providers.openai.api_key"`` traverses
      ``data["providers"]["openai"]["api_key"]``.
    - The optional ``json_path`` config scopes all lookups to a
      nested sub-object before resolving secret names.

    Connector ID: ``modelmesh.json-secrets.v1``

    Usage::

        store = JsonSecretStore(JsonSecretStoreConfig(
            file_path="/etc/modelmesh/secrets.json",
            json_path="providers",
        ))
        api_key = store.get("openai.api_key")
    """

    CONNECTOR_ID: str = "modelmesh.json-secrets.v1"

    def __init__(self, config: JsonSecretStoreConfig | None = None) -> None:
        if config is None:
            config = JsonSecretStoreConfig()
        super().__init__(config)
        self._json_config = config
        self._data: dict = {}
        self._load_file()

    def _load_file(self) -> None:
        """Load and parse the JSON file into the internal dictionary."""
        path = self._json_config.file_path
        if not path or not os.path.isfile(path):
            return

        with open(path, "r", encoding="utf-8") as fh:
            self._data = json.load(fh)

        # Scope to a nested sub-object if json_path is set
        if self._json_config.json_path:
            self._data = self._traverse(
                self._data, self._json_config.json_path
            )

    @staticmethod
    def _traverse(data: dict, dot_path: str) -> dict:
        """Walk into a nested dict using a dot-notation path.

        Returns an empty dict if any segment is missing or the
        result is not a dict.
        """
        current = data
        for segment in dot_path.split("."):
            if not isinstance(current, dict) or segment not in current:
                return {}
            current = current[segment]
        if not isinstance(current, dict):
            return {}
        return current

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret by name from the loaded JSON data.

        Supports dot-notation traversal for nested keys. The final
        value must be a string (or is converted to one).

        Returns:
            The secret value as a string, or None if not found.
        """
        # Support dot-notation in the secret name itself
        current = self._data
        segments = name.split(".")
        for segment in segments:
            if not isinstance(current, dict) or segment not in current:
                return None
            current = current[segment]

        # Convert the final value to a string
        if current is None:
            return None
        return str(current)
