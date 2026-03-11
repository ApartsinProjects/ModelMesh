"""Quick provider for the CDK.

Minimal provider requiring only ``base_url`` and ``api_key``. Supports
automatic model discovery via the ``GET /v1/models`` endpoint when no
models are configured explicitly.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import ModelInfo

__all__ = [
    "QuickProviderConfig",
    "QuickProvider",
]


@dataclass
class QuickProviderConfig(BaseProviderConfig):
    """Configuration for a QuickProvider instance.

    The minimal configuration: just ``base_url`` and ``api_key``.
    If ``models`` is left empty, the provider will attempt to
    auto-discover available models by calling ``GET /v1/models``
    on first use.
    """

    base_url: str = ""
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)


class QuickProvider(BaseProvider):
    """Minimal provider -- just base_url + api_key.

    The simplest way to connect to an OpenAI-compatible API. If no
    models are listed in configuration, the provider will attempt to
    discover them automatically by querying the ``/v1/models`` endpoint
    on the first call to ``list_models()``.

    Usage::

        provider = QuickProvider(QuickProviderConfig(
            base_url="https://api.example.com",
            api_key="sk-...",
        ))
        models = provider.list_models()  # auto-discovers if empty
    """

    def __init__(self, config: QuickProviderConfig) -> None:
        super().__init__(config)
        self._discovered: bool = len(config.models) > 0

    def list_models(self) -> list[ModelInfo]:
        """Return all models, attempting auto-discovery if none configured.

        On the first call, if ``models`` is empty, tries to discover
        available models by sending ``GET /v1/models`` to the
        provider's base URL. Discovered models are cached for
        subsequent calls.

        Returns:
            A list of ModelInfo instances.
        """
        if not self._discovered:
            self._discover_models()
        return list(self._config.models)

    def _discover_models(self) -> None:
        """Attempt to discover models via GET /v1/models.

        Parses an OpenAI-compatible model listing response and
        populates the internal model catalogue. Silently falls back
        to an empty list if the endpoint is unavailable or returns
        an unexpected format.
        """
        self._discovered = True
        base = self._config.base_url.rstrip("/")
        url = f"{base}/v1/models"
        headers = self._build_headers()

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(
                req, timeout=self._config.timeout
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            # Discovery is best-effort; if it fails, leave models empty
            return

        if not isinstance(data, dict) or "data" not in data:
            return

        discovered: list[ModelInfo] = []
        for item in data["data"]:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id", "")
            if not model_id:
                continue
            discovered.append(
                ModelInfo(
                    id=model_id,
                    name=item.get("name", model_id),
                    capabilities=item.get("capabilities", ["generation.text-generation.chat-completion"]),
                    context_window=item.get("context_window", 0),
                    max_output_tokens=item.get("max_output_tokens", 0),
                )
            )

        if discovered:
            self._config.models = discovered
            self._models_by_id = {m.id: m for m in discovered}
