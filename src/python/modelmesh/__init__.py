"""ModelMesh Lite -- Capability-driven AI model routing.

A single integration point for multiple AI providers with automatic
rotation to aggregate free tiers, minimize cost, and maintain service
continuity. Applications request capabilities; ModelMesh manages
providers, quotas, costs, and failover.

Quick start::

    import modelmesh

    client = modelmesh.create("chat-completion")
    response = client.chat.completions.create(
        model="chat-completion",
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(response.choices[0].message.content)
"""
from __future__ import annotations

from modelmesh import capabilities
from modelmesh.client.mesh_client import MeshClient
from modelmesh.config.mesh_config import MeshConfig
from modelmesh.core.mesh import ModelMesh
from modelmesh.exceptions import (
    AllProvidersExhaustedError,
    AuthenticationError,
    BudgetExceededError,
    ConfigurationError,
    ModelMeshError,
    NoActiveModelError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    RoutingError,
)
from modelmesh.connectors import CONNECTOR_REGISTRY, register_connector
from modelmesh.middleware import Middleware, MiddlewareContext, MiddlewareStack
from modelmesh.testing import MockClient, MockResponse, mock_client
from modelmesh.usage import UsageTracker

__all__ = [
    # Core
    "ModelMesh",
    "MeshClient",
    "MeshConfig",
    "create",
    # Exceptions
    "ModelMeshError",
    "RoutingError",
    "NoActiveModelError",
    "AllProvidersExhaustedError",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "ProviderTimeoutError",
    "ConfigurationError",
    "BudgetExceededError",
    # Middleware
    "Middleware",
    "MiddlewareContext",
    "MiddlewareStack",
    # Usage
    "UsageTracker",
    # Testing
    "MockClient",
    "MockResponse",
    "mock_client",
    # Capabilities
    "capabilities",
    # Connector registry
    "CONNECTOR_REGISTRY",
    "register_connector",
]


def create(
    *capabilities: str,
    pool: str | None = None,
    providers: list[str] | None = None,
    models: list[str] | None = None,
    strategy: str = "stick-until-failure",
    api_keys: dict[str, str] | None = None,
    config: str | dict | MeshConfig | None = None,
    middleware: list[Middleware] | None = None,
) -> MeshClient:
    """Create an OpenAI SDK-compatible client with ModelMesh routing.

    This is the primary entry point. It auto-detects available providers
    from environment variables, builds capability pools, configures
    rotation, and returns a ``MeshClient`` ready for use.

    Parameters are resolved in priority order:

    1. ``config`` -- use a full configuration directly (Layer 2).
    2. ``pool`` -- look up a predefined pool, auto-detect providers.
    3. ``capabilities`` -- create pools for requested capabilities.
    4. Nothing provided -- raise ``ValueError``.

    Args:
        *capabilities: Required capabilities (e.g.
            ``"chat-completion"``, ``"text-embeddings"``). Each creates
            or joins a pool.
        pool: Predefined pool name to use.
        providers: Filter auto-detection to specific providers
            (e.g. ``["openai", "anthropic"]``).
        models: Filter to specific models
            (e.g. ``["openai.gpt-4o"]``).
        strategy: Rotation strategy name.
            Default: ``"stick-until-failure"``.
        api_keys: Override env var detection with explicit keys. Keys
            can be environment variable names (``"OPENAI_API_KEY"``) or
            provider names (``"openai"``).
        config: Full configuration -- YAML file path, dict, or
            ``MeshConfig`` object. When provided, auto-detection is
            skipped.
        middleware: List of :class:`Middleware` instances to attach to the
            router. Middleware runs before and after each provider call.

    Returns:
        ``MeshClient``: OpenAI SDK-compatible client with ModelMesh
        routing.

    Raises:
        ValueError: If no capabilities, pool, or config is specified,
            or if no providers are detected.

    Examples:
        Layer 0 -- single capability::

            client = modelmesh.create("chat-completion")

        Layer 1 -- multi-capability with provider filter::

            client = modelmesh.create(
                "chat-completion", "text-embeddings",
                providers=["openai", "anthropic"],
                strategy="cost-first",
            )

        Layer 1b -- predefined pool::

            client = modelmesh.create(pool="text-generation")

        Layer 2 -- full YAML configuration::

            client = modelmesh.create(config="modelmesh.yaml")
    """
    from modelmesh.config.auto_detect import detect_providers
    from modelmesh.core.mesh import ModelMesh

    mesh = ModelMesh()

    if config is not None:
        # Layer 2: Full configuration
        if isinstance(config, str):
            mesh_config = MeshConfig.from_yaml(config)
        elif isinstance(config, dict):
            mesh_config = MeshConfig.from_dict(config)
        elif isinstance(config, MeshConfig):
            mesh_config = config
        else:
            raise TypeError(
                f"config must be str, dict, or MeshConfig, got "
                f"{type(config).__name__}"
            )
        mesh.initialize(mesh_config)
        client = mesh.get_client()
        if middleware:
            mesh._router._middleware = MiddlewareStack(middleware)
        return client

    if not capabilities and pool is None:
        raise ValueError(
            "Specify capabilities, pool, or config. "
            "Example: modelmesh.create('chat-completion')"
        )

    # Auto-detect available providers
    detected = detect_providers(names=providers, api_keys=api_keys)
    if not detected:
        raise ValueError(
            "No providers detected. Set API key environment variables "
            "(e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY) or pass api_keys=..."
        )

    # Build config from detected providers + capabilities/pool
    raw_config = _build_auto_config(
        capabilities=list(capabilities),
        pool=pool,
        detected_providers=detected,
        model_filter=models,
        strategy=strategy,
    )
    mesh.initialize(MeshConfig(raw=raw_config))
    client = mesh.get_client()
    if middleware:
        mesh._router._middleware = MiddlewareStack(middleware)
    return client


# Well-known short names mapped to full capability tree paths.
_CAPABILITY_ALIASES: dict[str, str] = {
    "chat-completion": "generation.text-generation.chat-completion",
    "text-generation": "generation.text-generation",
    "text-embeddings": "representation.embeddings.text-embeddings",
    "text-to-speech": "generation.audio.text-to-speech",
    "speech-to-text": "understanding.audio.speech-to-text",
    "text-to-image": "generation.image.text-to-image",
    "image-to-text": "representation.image.image-to-text",
    "code-generation": "generation.text-generation.code-generation",
}


def _resolve_capability_path(name: str) -> str:
    """Resolve a short capability name to its full dotted path.

    If *name* is already a dotted path (contains ``"."``) it is returned
    as-is. Otherwise, the ``_CAPABILITY_ALIASES`` lookup is consulted.
    Unknown short names are returned unchanged so that custom capability
    trees can define their own names.

    Args:
        name: Short name or full dotted path.

    Returns:
        Full capability path.
    """
    if "." in name:
        return name
    return _CAPABILITY_ALIASES.get(name, name)


def _build_auto_config(
    capabilities: list[str],
    pool: str | None,
    detected_providers: list[dict],
    model_filter: list[str] | None,
    strategy: str,
) -> dict:
    """Build a MeshConfig dict from auto-detected providers and capabilities.

    Constructs a configuration dictionary with providers, models, and
    pools sections populated from auto-detected provider data so that
    the core ``ModelMesh.initialize()`` path can handle everything
    uniformly.

    Args:
        capabilities: Requested capability names.
        pool: Predefined pool name (mutually exclusive with capabilities
            in practice, but both handled gracefully).
        detected_providers: Provider dicts from :func:`detect_providers`.
        model_filter: Optional model ID filter list.
        strategy: Rotation strategy name.

    Returns:
        A raw config dict suitable for ``MeshConfig(raw=...)``.
    """
    from modelmesh.interfaces.provider import ModelInfo

    providers_section: dict = {}
    models_section: dict = {}
    pools_section: dict = {}

    # Build providers and models sections from detected providers
    for prov in detected_providers:
        provider_name = prov["name"]
        connector_id = prov["connector"]

        providers_section[connector_id] = {
            "connector": connector_id,
            "enabled": True,
            "config": {
                "api_key": prov["api_key"],
                "base_url": prov.get("base_url", ""),
            },
        }

        # Register each default model
        for model_info in prov.get("default_models", []):
            # model_info can be a ModelInfo dataclass or a plain dict
            if isinstance(model_info, ModelInfo):
                model_id = model_info.id
                model_caps = list(model_info.capabilities)
            else:
                model_id = model_info["id"]
                model_caps = list(model_info.get("capabilities", []))

            # Apply model filter if specified
            if model_filter and model_id not in model_filter:
                continue

            models_section[model_id] = {
                "provider": connector_id,
                "capabilities": model_caps,
            }

    # Determine the target capabilities for pool construction.
    # When ``pool`` is given, use it as a single pool.
    # Otherwise, create one pool per capability.
    if pool is not None:
        capability_path = _resolve_capability_path(pool)
        pools_section[pool] = {
            "capability": capability_path,
            "strategy": strategy,
        }
    else:
        for cap in capabilities:
            capability_path = _resolve_capability_path(cap)
            pools_section[cap] = {
                "capability": capability_path,
                "strategy": strategy,
            }

    return {
        "providers": providers_section,
        "models": models_section,
        "pools": pools_section,
        "observability": {"connector": "modelmesh.null.v1"},
    }
