"""Dotenv file secret store connector.

Resolves secrets from ``.env`` files by parsing ``KEY=VALUE`` lines.
Supports comments (``#``), quoted values (single and double quotes),
and multiline values using backslash continuation.

Connector ID: ``modelmesh.dotenv.v1``
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig

__all__ = [
    "DotenvSecretStoreConfig",
    "DotenvSecretStore",
]


@dataclass
class DotenvSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for the dotenv file secret store.

    Attributes:
        file_path: Path to the ``.env`` file. Defaults to ``".env"``
            in the current working directory.
        override_env: If True, values from the file take precedence
            over existing environment variables. Defaults to False.
    """

    file_path: str = ".env"
    override_env: bool = False


class DotenvSecretStore(BaseSecretStore):
    """Secret store that resolves values from a ``.env`` file.

    Parses a dotenv-formatted file with ``KEY=VALUE`` pairs. Supports:

    - Comments: lines starting with ``#`` are ignored.
    - Quoted values: single (``'``) and double (``"``) quotes are stripped.
    - Multiline: trailing backslash (``\\``) continues the value on the
      next line.
    - Blank lines are ignored.
    - Inline comments after unquoted values are stripped.

    Connector ID: ``modelmesh.dotenv.v1``

    Usage::

        store = DotenvSecretStore(DotenvSecretStoreConfig(
            file_path="/app/.env",
            override_env=True,
        ))
        api_key = store.get("OPENAI_API_KEY")
    """

    CONNECTOR_ID: str = "modelmesh.dotenv.v1"

    def __init__(self, config: DotenvSecretStoreConfig | None = None) -> None:
        if config is None:
            config = DotenvSecretStoreConfig()
        super().__init__(config)
        self._dotenv_config = config
        self._values: dict[str, str] = {}
        self._load_file()

    def _load_file(self) -> None:
        """Parse the .env file into the internal dictionary."""
        path = self._dotenv_config.file_path
        if not os.path.isfile(path):
            return

        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].rstrip("\n\r")
            i += 1

            # Skip blank lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Must contain '=' to be a valid assignment
            if "=" not in stripped:
                continue

            key, _, raw_value = stripped.partition("=")
            key = key.strip()
            raw_value = raw_value.strip()

            # Handle backslash continuation
            while raw_value.endswith("\\") and i < len(lines):
                raw_value = raw_value[:-1] + lines[i].rstrip("\n\r")
                i += 1

            # Handle quoted values
            if (
                len(raw_value) >= 2
                and raw_value[0] == raw_value[-1]
                and raw_value[0] in ("'", '"')
            ):
                raw_value = raw_value[1:-1]
            else:
                # Strip inline comments for unquoted values
                for comment_char in (" #", "\t#"):
                    comment_idx = raw_value.find(comment_char)
                    if comment_idx >= 0:
                        raw_value = raw_value[:comment_idx].rstrip()
                        break

            if key:
                self._values[key] = raw_value

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret by name from the parsed .env file.

        If ``override_env`` is False (default), environment variables
        take precedence over file values. If True, file values win.

        Returns:
            The secret value, or None if not found.
        """
        env_value = os.environ.get(name)
        file_value = self._values.get(name)

        if self._dotenv_config.override_env:
            # File takes precedence
            return file_value if file_value is not None else env_value
        else:
            # Environment takes precedence
            return env_value if env_value is not None else file_value
