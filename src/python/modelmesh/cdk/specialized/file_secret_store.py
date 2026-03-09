"""File-backed secret store for the CDK.

Extends BaseSecretStore to read secrets from local files in .env,
JSON, or TOML format. Parses the file once at initialization and
resolves secrets from the parsed data on each ``get()`` call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig

__all__ = [
    "FileSecretStoreConfig",
    "FileSecretStore",
]


@dataclass
class FileSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for a file-backed secret store.

    Attributes:
        file_path: Absolute or relative path to the secrets file.
        format: File format -- ``"env"``, ``"json"``, or ``"toml"``.
    """

    file_path: str = ""
    format: str = "env"


class FileSecretStore(BaseSecretStore):
    """Secret store backed by a local file.

    Reads secrets from ``.env``, JSON, or TOML files. The file is
    parsed once during initialization; resolved values are then
    served from the in-memory cache with the standard BaseSecretStore
    TTL behavior.

    Supported formats:

    - **env**: Lines of ``KEY=value``, ignoring comments (``#``) and
      blank lines. Values may optionally be quoted.
    - **json**: A flat JSON object ``{"key": "value", ...}``.
    - **toml**: A flat TOML file. Requires Python 3.11+ (``tomllib``)
      or the third-party ``tomli`` package. Falls back gracefully if
      neither is available.

    Usage::

        store = FileSecretStore(FileSecretStoreConfig(
            file_path="/etc/secrets/.env",
            format="env",
        ))
        api_key = store.get("OPENAI_API_KEY")
    """

    def __init__(self, config: FileSecretStoreConfig) -> None:
        super().__init__(config)
        self._file_config = config
        self._file_data: dict[str, str] = {}
        self._load_file()

    def _load_file(self) -> None:
        """Parse the secrets file and populate ``_file_data``."""
        if not self._file_config.file_path:
            return

        try:
            with open(self._file_config.file_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except (OSError, IOError):
            return

        fmt = self._file_config.format.lower()
        if fmt == "env":
            self._file_data = self._parse_env(raw)
        elif fmt == "json":
            self._file_data = self._parse_json(raw)
        elif fmt == "toml":
            self._file_data = self._parse_toml(raw)

    def _resolve(self, name: str) -> str | None:
        """Look up a secret name in the parsed file data.

        Falls back to the parent class ``_resolve`` (in-memory dict)
        if the name is not found in the file.
        """
        value = self._file_data.get(name)
        if value is not None:
            return value
        return super()._resolve(name)

    # -- Format Parsers ------------------------------------------------------

    @staticmethod
    def _parse_env(raw: str) -> dict[str, str]:
        """Parse .env format: ``KEY=value`` lines.

        Ignores blank lines and lines starting with ``#``. Strips
        optional surrounding quotes (single or double) from values.
        """
        data: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key:
                data[key] = value
        return data

    @staticmethod
    def _parse_json(raw: str) -> dict[str, str]:
        """Parse a flat JSON object ``{"key": "value", ...}``.

        Non-string values are converted to their string representation.
        """
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}

        if not isinstance(obj, dict):
            return {}

        return {str(k): str(v) for k, v in obj.items()}

    @staticmethod
    def _parse_toml(raw: str) -> dict[str, str]:
        """Parse a flat TOML file using stdlib tomllib or third-party tomli.

        Returns an empty dict if neither library is available or if
        parsing fails.
        """
        toml_loads = None

        # Try Python 3.11+ stdlib tomllib first
        try:
            import tomllib

            toml_loads = tomllib.loads
        except ImportError:
            pass

        # Fall back to third-party tomli
        if toml_loads is None:
            try:
                import tomli  # type: ignore[import-untyped]

                toml_loads = tomli.loads
            except ImportError:
                return {}

        try:
            obj = toml_loads(raw)
        except Exception:
            return {}

        if not isinstance(obj, dict):
            return {}

        # Flatten top-level keys only; nested tables are stringified
        result: dict[str, str] = {}
        for k, v in obj.items():
            if isinstance(v, dict):
                # Flatten one level of nesting
                for sub_k, sub_v in v.items():
                    result[f"{k}.{sub_k}"] = str(sub_v)
            else:
                result[str(k)] = str(v)
        return result
