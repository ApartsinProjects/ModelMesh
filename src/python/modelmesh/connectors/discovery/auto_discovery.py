"""Provider auto-discovery and model registry connector.

Discovers available models by querying provider APIs at startup,
building a registry that pools can use for automatic model assignment.
Supports static model registries, environment-based detection, and
live API enumeration.

Connector ID: ``modelmesh.auto-discovery.v1``

Usage::

    from modelmesh.connectors.discovery.auto_discovery import (
        AutoDiscovery,
        DiscoveryConfig,
    )

    discovery = AutoDiscovery(DiscoveryConfig(
        providers=["openai", "anthropic", "groq"],
        cache_ttl=300,
    ))
    models = discovery.discover()
    # → [DiscoveredModel(id="gpt-4o", provider="openai", ...), ...]
"""
from __future__ import annotations

import logging
import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("modelmesh.discovery")

__all__ = [
    "AutoDiscovery",
    "DiscoveryConfig",
    "DiscoveredModel",
    "ModelRegistry",
]


# ── Data types ────────────────────────────────────────────────────────


@dataclass
class DiscoveredModel:
    """A model discovered from a provider API or static registry.

    Attributes:
        id: Provider-specific model identifier.
        provider: Provider connector ID (e.g. ``"openai.llm.v1"``).
        name: Human-readable display name.
        capabilities: Inferred capability tree paths.
        context_window: Maximum context window size.
        max_output_tokens: Maximum output token count.
        pricing_input: Input cost per 1K tokens.
        pricing_output: Output cost per 1K tokens.
        metadata: Extra provider-specific metadata.
    """

    id: str
    provider: str
    name: str = ""
    capabilities: list[str] = field(default_factory=list)
    context_window: int = 0
    max_output_tokens: int = 0
    pricing_input: float = 0.0
    pricing_output: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_config_entry(self) -> dict[str, Any]:
        """Convert to a ``models`` config entry dict."""
        entry: dict[str, Any] = {"provider": self.provider}
        if self.capabilities:
            entry["capabilities"] = self.capabilities
        constraints: dict[str, Any] = {}
        if self.context_window:
            constraints["context_window"] = self.context_window
        if self.max_output_tokens:
            constraints["max_output_tokens"] = self.max_output_tokens
        if constraints:
            entry["constraints"] = constraints
        return entry


@dataclass
class DiscoveryConfig:
    """Configuration for auto-discovery.

    Attributes:
        providers: List of provider short names to probe.
        cache_ttl: How long (seconds) to cache discovered models.
        env_prefix: Environment variable prefix for API key detection.
        include_patterns: Model ID patterns to include (glob-style).
        exclude_patterns: Model ID patterns to exclude.
    """

    providers: list[str] = field(default_factory=list)
    cache_ttl: float = 300.0
    env_prefix: str = ""
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)


# ── Static model registry ────────────────────────────────────────────

# Well-known models with their capabilities and constraints.
# This is used when live API enumeration is not available.

_STATIC_REGISTRY: dict[str, list[DiscoveredModel]] = {
    "openai": [
        DiscoveredModel(
            id="gpt-4o",
            provider="openai.llm.v1",
            name="GPT-4o",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=128000,
            max_output_tokens=16384,
            pricing_input=2.50,
            pricing_output=10.00,
        ),
        DiscoveredModel(
            id="gpt-4o-mini",
            provider="openai.llm.v1",
            name="GPT-4o Mini",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=128000,
            max_output_tokens=16384,
            pricing_input=0.15,
            pricing_output=0.60,
        ),
        DiscoveredModel(
            id="o3-mini",
            provider="openai.llm.v1",
            name="o3-mini",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=200000,
            max_output_tokens=100000,
            pricing_input=1.10,
            pricing_output=4.40,
        ),
    ],
    "anthropic": [
        DiscoveredModel(
            id="claude-sonnet-4-20250514",
            provider="anthropic.claude.v1",
            name="Claude Sonnet 4",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=200000,
            max_output_tokens=8192,
            pricing_input=3.00,
            pricing_output=15.00,
        ),
        DiscoveredModel(
            id="claude-3-5-haiku-20241022",
            provider="anthropic.claude.v1",
            name="Claude 3.5 Haiku",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=200000,
            max_output_tokens=8192,
            pricing_input=0.80,
            pricing_output=4.00,
        ),
    ],
    "groq": [
        DiscoveredModel(
            id="llama-3.3-70b-versatile",
            provider="groq.api.v1",
            name="Llama 3.3 70B",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=131072,
            max_output_tokens=32768,
            pricing_input=0.59,
            pricing_output=0.79,
        ),
        DiscoveredModel(
            id="mixtral-8x7b-32768",
            provider="groq.api.v1",
            name="Mixtral 8x7B",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=32768,
            max_output_tokens=32768,
            pricing_input=0.24,
            pricing_output=0.24,
        ),
    ],
    "deepseek": [
        DiscoveredModel(
            id="deepseek-chat",
            provider="deepseek.api.v1",
            name="DeepSeek Chat",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=64000,
            max_output_tokens=8192,
            pricing_input=0.14,
            pricing_output=0.28,
        ),
        DiscoveredModel(
            id="deepseek-reasoner",
            provider="deepseek.api.v1",
            name="DeepSeek Reasoner",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=64000,
            max_output_tokens=8192,
            pricing_input=0.55,
            pricing_output=2.19,
        ),
    ],
    "mistral": [
        DiscoveredModel(
            id="mistral-large-latest",
            provider="mistral.api.v1",
            name="Mistral Large",
            capabilities=["generation.text-generation.chat-completion"],
            context_window=128000,
            max_output_tokens=8192,
            pricing_input=2.00,
            pricing_output=6.00,
        ),
    ],
}

# Map of environment variable names → provider short names
_ENV_KEY_MAP: dict[str, str] = {
    "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "GROQ_API_KEY": "groq",
    "DEEPSEEK_API_KEY": "deepseek",
    "MISTRAL_API_KEY": "mistral",
    "TOGETHER_API_KEY": "together",
    "XAI_API_KEY": "xai",
    "COHERE_API_KEY": "cohere",
    "GOOGLE_API_KEY": "gemini",
    "PERPLEXITY_API_KEY": "perplexity",
}


# ── ModelRegistry ─────────────────────────────────────────────────────


class ModelRegistry:
    """In-memory registry of discovered models.

    Thread-safe. Supports querying by provider, capability, or
    price range.
    """

    def __init__(self) -> None:
        self._models: dict[str, DiscoveredModel] = {}
        self._lock = threading.Lock()

    def register(self, model: DiscoveredModel) -> None:
        """Add or update a model in the registry."""
        with self._lock:
            self._models[model.id] = model

    def register_many(self, models: list[DiscoveredModel]) -> None:
        """Bulk register models."""
        with self._lock:
            for m in models:
                self._models[m.id] = m

    def get(self, model_id: str) -> Optional[DiscoveredModel]:
        """Look up a model by ID."""
        with self._lock:
            return self._models.get(model_id)

    def list_all(self) -> list[DiscoveredModel]:
        """Return all registered models."""
        with self._lock:
            return list(self._models.values())

    def by_provider(self, provider: str) -> list[DiscoveredModel]:
        """Return models from a specific provider."""
        with self._lock:
            return [
                m for m in self._models.values()
                if m.provider == provider
                or m.provider.startswith(provider + ".")
            ]

    def by_capability(self, capability: str) -> list[DiscoveredModel]:
        """Return models matching a capability path."""
        with self._lock:
            return [
                m for m in self._models.values()
                if any(
                    cap == capability or cap.startswith(capability + ".")
                    for cap in m.capabilities
                )
            ]

    def cheapest(self, n: int = 5) -> list[DiscoveredModel]:
        """Return the N cheapest models by input pricing."""
        with self._lock:
            models = sorted(
                self._models.values(), key=lambda m: m.pricing_input
            )
            return models[:n]

    def to_config(self) -> dict[str, dict[str, Any]]:
        """Convert registry to a ``models`` config section."""
        with self._lock:
            return {
                m.id: m.to_config_entry() for m in self._models.values()
            }

    def clear(self) -> None:
        """Remove all models from the registry."""
        with self._lock:
            self._models.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._models)


# ── AutoDiscovery ─────────────────────────────────────────────────────


class AutoDiscovery:
    """Provider auto-discovery and model enumeration.

    Discovers available providers by checking for API keys in the
    environment, then enumerates their models from the static registry.
    Results are cached for ``cache_ttl`` seconds.

    Connector ID: ``modelmesh.auto-discovery.v1``
    """

    CONNECTOR_ID: str = "modelmesh.auto-discovery.v1"

    def __init__(self, config: Optional[DiscoveryConfig] = None) -> None:
        self._config = config or DiscoveryConfig()
        self._registry = ModelRegistry()
        self._last_discovery: float = 0.0
        self._lock = threading.Lock()

    @property
    def registry(self) -> ModelRegistry:
        """The model registry populated by discovery."""
        return self._registry

    def detect_providers(self) -> list[str]:
        """Detect available providers from environment variables.

        Returns:
            List of provider short names with API keys present.
        """
        detected: list[str] = []
        for env_var, provider in _ENV_KEY_MAP.items():
            if os.environ.get(env_var):
                detected.append(provider)
        return detected

    def discover(self, force: bool = False) -> list[DiscoveredModel]:
        """Run discovery and populate the registry.

        Uses the static registry for model enumeration. Respects
        ``cache_ttl`` unless ``force=True``.

        Args:
            force: Bypass cache and re-discover.

        Returns:
            List of all discovered models.
        """
        with self._lock:
            now = time.monotonic()
            if (
                not force
                and self._last_discovery > 0
                and (now - self._last_discovery) < self._config.cache_ttl
            ):
                return self._registry.list_all()

        # Determine which providers to probe
        providers = self._config.providers
        if not providers:
            providers = self.detect_providers()

        discovered: list[DiscoveredModel] = []
        for provider in providers:
            models = _STATIC_REGISTRY.get(provider, [])
            for model in models:
                if self._should_include(model):
                    discovered.append(model)

        self._registry.clear()
        self._registry.register_many(discovered)

        with self._lock:
            self._last_discovery = time.monotonic()

        logger.info(
            "Auto-discovery found %d model(s) from %d provider(s)",
            len(discovered),
            len(providers),
        )
        return discovered

    def generate_config(self) -> dict[str, Any]:
        """Generate a complete ModelMesh config from discovered models.

        Returns:
            A config dict suitable for ``MeshConfig.from_dict()``.
        """
        models = self.discover()
        if not models:
            return {}

        # Collect unique providers
        providers_cfg: dict[str, dict[str, Any]] = {}
        models_cfg: dict[str, dict[str, Any]] = {}

        for model in models:
            # Register provider
            if model.provider not in providers_cfg:
                providers_cfg[model.provider] = {
                    "connector": model.provider,
                }

            # Register model
            models_cfg[model.id] = model.to_config_entry()

        # Create a default pool spanning all capabilities
        pools_cfg: dict[str, dict[str, Any]] = {
            "text-generation": {
                "strategy": "modelmesh.stick-until-failure.v1",
                "capability": "generation.text-generation",
            },
        }

        return {
            "secrets": {"store": "modelmesh.env.v1"},
            "providers": providers_cfg,
            "models": models_cfg,
            "pools": pools_cfg,
        }

    def _should_include(self, model: DiscoveredModel) -> bool:
        """Check include/exclude patterns."""
        if self._config.exclude_patterns:
            for pattern in self._config.exclude_patterns:
                if _glob_match(model.id, pattern):
                    return False

        if self._config.include_patterns:
            for pattern in self._config.include_patterns:
                if _glob_match(model.id, pattern):
                    return True
            return False  # Nothing matched include patterns

        return True  # No patterns configured, include everything


def _glob_match(text: str, pattern: str) -> bool:
    """Simple glob matching supporting ``*`` as wildcard."""
    if pattern == "*":
        return True
    if "*" not in pattern:
        return text == pattern

    parts = pattern.split("*")
    if len(parts) == 2:
        prefix, suffix = parts
        return text.startswith(prefix) and text.endswith(suffix)

    # Multi-wildcard: check parts appear in order
    pos = 0
    for i, part in enumerate(parts):
        if not part:
            continue
        idx = text.find(part, pos)
        if idx == -1:
            return False
        if i == 0 and idx != 0:
            return False  # Must start with first part
        pos = idx + len(part)

    if parts[-1] and not text.endswith(parts[-1]):
        return False

    return True
