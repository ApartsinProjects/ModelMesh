"""Environment variable secret store connector.

Resolves secrets from environment variables. An optional ``prefix``
can be configured to scope lookups (e.g., prefix ``"MODELMESH_"``
causes a lookup for ``"OPENAI_KEY"`` to read
``os.environ["MODELMESH_OPENAI_KEY"]``).

Connector ID: ``modelmesh.env.v1``
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig

__all__ = [
    "EnvSecretStoreConfig",
    "EnvSecretStore",
]


@dataclass
class EnvSecretStoreConfig(BaseSecretStoreConfig):
    """Configuration for the environment variable secret store.

    Attributes:
        prefix: Optional prefix to prepend to all secret name lookups.
            For example, if ``prefix="MODELMESH_"``, a lookup for
            ``"OPENAI_KEY"`` will read ``os.environ["MODELMESH_OPENAI_KEY"]``.
    """

    prefix: str = ""


class EnvSecretStore(BaseSecretStore):
    """Secret store that resolves values from environment variables.

    This is the simplest secret store and is suitable for local
    development, CI/CD pipelines, and containerized deployments where
    secrets are injected as environment variables.

    Connector ID: ``modelmesh.env.v1``

    Usage::

        store = EnvSecretStore(EnvSecretStoreConfig())
        api_key = store.get("OPENAI_API_KEY")

        # With prefix
        store = EnvSecretStore(EnvSecretStoreConfig(prefix="MODELMESH_"))
        api_key = store.get("OPENAI_KEY")  # reads MODELMESH_OPENAI_KEY
    """

    CONNECTOR_ID: str = "modelmesh.env.v1"

    def __init__(self, config: EnvSecretStoreConfig | None = None) -> None:
        if config is None:
            config = EnvSecretStoreConfig()
        super().__init__(config)
        self._env_config = config

    def _resolve(self, name: str) -> str | None:
        """Resolve a secret by reading the named environment variable.

        Prepends the configured ``prefix`` to the variable name before
        looking it up. Returns ``None`` if the variable is not set,
        which causes the base class to raise ``KeyError`` when
        ``fail_on_missing`` is ``True``.
        """
        env_name = f"{self._env_config.prefix}{name}"
        return os.environ.get(env_name)
