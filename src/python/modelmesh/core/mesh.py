"""ModelMesh — library facade.

The ``ModelMesh`` class is the central orchestration object. It manages
providers, capability pools, routing, state tracking, and event emission.
Applications typically interact through the ``MeshClient`` returned by
:meth:`get_client` rather than calling ``ModelMesh`` directly.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING, AsyncIterator, Optional

from modelmesh.core.capability_tree import CapabilityTree
from modelmesh.core.event_emitter import EventEmitter
from modelmesh.core.pool import CapabilityPool, PoolModel
from modelmesh.core.router import Router
from modelmesh.core.state_manager import StateManager
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ProviderConnector,
)

if TYPE_CHECKING:
    from modelmesh.client.mesh_client import MeshClient
    from modelmesh.config.mesh_config import MeshConfig
    from modelmesh.interfaces.observability import ObservabilityConnector

logger = logging.getLogger("modelmesh.core")

__all__ = ["ModelMesh"]


class ModelMesh:
    """Library facade. Manages providers, pools, routing, and state.

    Lifecycle::

        mesh = ModelMesh()
        mesh.initialize(config)
        client = mesh.get_client()
        # ... use client ...
        mesh.shutdown()

    The facade is intentionally thin: it delegates routing to :class:`Router`,
    state tracking to :class:`StateManager`, and event publishing to
    :class:`EventEmitter`.
    """

    def __init__(self) -> None:
        self._config: Optional[MeshConfig] = None
        self._router: Optional[Router] = None
        self._pools: dict[str, CapabilityPool] = {}
        self._providers: dict[str, ProviderConnector] = {}
        self._state_manager = StateManager()
        self._event_emitter = EventEmitter()
        self._capability_tree = CapabilityTree()
        self._observability: ObservabilityConnector | None = None
        self._storage = None
        self._secret_store = None
        self._discovery = None
        self._initialized = False

    # -- Lifecycle -----------------------------------------------------------

    def initialize(self, config: MeshConfig) -> None:
        """Initialize the mesh from a MeshConfig.

        Sets up providers, pools, the capability tree, and the router.
        Must be called before :meth:`get_client` or :meth:`route`.

        Args:
            config: Fully resolved MeshConfig object.
        """
        self._config = config

        # Set up observability connector from config (only if not pre-set).
        # If the caller set ``_observability`` before ``initialize()``, that
        # instance is used as-is; otherwise we resolve from config.
        if self._observability is None:
            obs_cfg = config.raw.get("observability", {})
            # Support pre-built instance injection
            if "instance" in obs_cfg and obs_cfg["instance"] is not None:
                self._observability = obs_cfg["instance"]
            elif obs_cfg.get("connector"):
                from modelmesh.connectors import CONNECTOR_REGISTRY

                obs_cls = CONNECTOR_REGISTRY.get(obs_cfg["connector"])
                if obs_cls:
                    self._observability = obs_cls()
            if self._observability is None:
                from modelmesh.connectors.observability.null_connector import (
                    NullObservabilityConnector,
                )

                self._observability = NullObservabilityConnector()

        self._setup_storage()
        self._setup_secrets()
        self._setup_discovery()
        self._setup_providers()
        self._setup_pools()
        self._router = Router(
            self._pools,
            self._capability_tree,
            self._providers,
            event_emitter=self._event_emitter,
            observability=self._observability,
        )
        self._initialized = True
        logger.info(
            "ModelMesh initialized: %d provider(s), %d pool(s)",
            len(self._providers),
            len(self._pools),
        )
        self._trace(
            "INFO",
            "mesh",
            f"Initialized: {len(self._providers)} provider(s), "
            f"{len(self._pools)} pool(s)",
        )

    def get_client(self) -> MeshClient:
        """Return an OpenAI SDK-compatible client backed by this mesh.

        Returns:
            A :class:`MeshClient` instance.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
        """
        if not self._initialized:
            raise RuntimeError(
                "ModelMesh not initialized. Call initialize() first."
            )
        from modelmesh.client.mesh_client import MeshClient

        return MeshClient(self)

    def get_router(self) -> Router:
        """Return the underlying Router instance.

        Returns:
            The :class:`Router` that handles request routing.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
        """
        if not self._initialized:
            raise RuntimeError(
                "ModelMesh not initialized. Call initialize() first."
            )
        assert self._router is not None
        return self._router

    @property
    def pools(self) -> dict[str, CapabilityPool]:
        """All configured capability pools, keyed by pool ID."""
        return dict(self._pools)

    @property
    def providers(self) -> dict[str, ProviderConnector]:
        """All registered provider connectors, keyed by connector ID."""
        return dict(self._providers)

    def shutdown(self) -> None:
        """Graceful shutdown.

        Closes all registered provider connectors and marks the mesh as
        uninitialized. Future calls to :meth:`route` or
        :meth:`get_client` will raise ``RuntimeError``.
        """
        self._trace("INFO", "mesh", "ModelMesh shutting down")
        for pid, provider in self._providers.items():
            try:
                result = provider.close()
                # Handle async close() methods gracefully
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception:
                logger.debug("Error closing provider %s", pid, exc_info=True)
        self._initialized = False
        self._router = None
        self._providers.clear()
        logger.info("ModelMesh shut down")

    # -- Routing -------------------------------------------------------------

    async def route(self, request: CompletionRequest) -> CompletionResponse:
        """Route a non-streaming request through the pipeline.

        Args:
            request: The completion request. The ``model`` field is
                treated as a virtual model name (pool ID).

        Returns:
            The completion response from the selected provider.

        Raises:
            RuntimeError: If the mesh is not initialized or no model
                is available.
        """
        self._check_initialized()
        assert self._router is not None
        return await self._router.route(request)

    async def route_stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[CompletionResponse]:
        """Route a streaming request through the pipeline.

        Args:
            request: The completion request with ``stream=True``.

        Yields:
            CompletionResponse chunks.

        Raises:
            RuntimeError: If the mesh is not initialized.
        """
        self._check_initialized()
        assert self._router is not None
        async for chunk in self._router.route_stream(request):
            yield chunk

    # -- Introspection -------------------------------------------------------

    def pool_status(self) -> dict[str, dict]:
        """Return health status for all pools.

        Returns:
            Dict mapping pool IDs to status dicts with ``active``,
            ``standby``, ``total``, and ``current_model`` keys.
        """
        return {
            pool_id: pool.status()
            for pool_id, pool in self._pools.items()
        }

    def active_providers(self) -> list[str]:
        """Return the list of active provider connector IDs.

        A provider is considered active if at least one of its models
        is in active status across any pool.
        """
        active_provider_ids: set[str] = set()
        for pool in self._pools.values():
            for model in pool.active_models:
                active_provider_ids.add(model.provider_id)
        return sorted(active_provider_ids)

    def list_pools(self) -> list[CapabilityPool]:
        """Return all configured capability pools."""
        return list(self._pools.values())

    def list_models(self) -> list[dict]:
        """Return metadata for all models across all pools.

        Returns:
            List of dicts with ``id``, ``owned_by``, and ``object`` keys
            matching the OpenAI ``/v1/models`` shape.
        """
        seen: set[str] = set()
        models: list[dict] = []
        for pool in self._pools.values():
            for model in pool.models:
                if model.model_id not in seen:
                    seen.add(model.model_id)
                    # Extract vendor from dot-notated ID
                    vendor = model.model_id.split(".")[0] if "." in model.model_id else "unknown"
                    models.append(
                        {
                            "id": model.model_id,
                            "object": "model",
                            "owned_by": vendor,
                        }
                    )
        return models

    def rotate(self, pool_id: str) -> Optional[str]:
        """Force an immediate rotation in a pool.

        Deactivates the current model and selects the next active one.

        Args:
            pool_id: The pool to rotate.

        Returns:
            The model ID of the newly selected model, or None if no
            alternative is available.

        Raises:
            KeyError: If the pool does not exist.
        """
        if pool_id not in self._pools:
            raise KeyError(f"Pool '{pool_id}' not found")
        pool = self._pools[pool_id]
        new_model = pool.rotate()
        if new_model:
            self._trace(
                "INFO",
                "mesh",
                f"Rotated pool '{pool_id}' to model '{new_model.model_id}'",
                pool_id=pool_id,
                new_model_id=new_model.model_id,
            )
        else:
            self._trace(
                "WARNING",
                "mesh",
                f"No alternative model available in pool '{pool_id}'",
                pool_id=pool_id,
            )
        return new_model.model_id if new_model else None

    @property
    def event_emitter(self) -> EventEmitter:
        """The event emitter for subscribing to routing events."""
        return self._event_emitter

    @property
    def state_manager(self) -> StateManager:
        """The state manager for inspecting model state."""
        return self._state_manager

    @property
    def capability_tree(self) -> CapabilityTree:
        """The capability tree for inspecting the hierarchy."""
        return self._capability_tree

    @property
    def storage(self):
        """The storage connector, or None if not configured."""
        return self._storage

    @property
    def secret_store(self):
        """The secret store connector, or None if not configured."""
        return self._secret_store

    @property
    def discovery(self):
        """The discovery connector, or None if not configured."""
        return self._discovery

    @property
    def observability(self) -> ObservabilityConnector:
        """The observability connector for tracing and monitoring."""
        if self._observability is None:
            from modelmesh.connectors.observability.null_connector import (
                NullObservabilityConnector,
            )

            self._observability = NullObservabilityConnector()
        return self._observability

    def _trace(
        self, severity, component: str, message: str, **metadata
    ) -> None:
        """Emit a trace entry through the observability connector."""
        from datetime import datetime

        from modelmesh.interfaces.observability import Severity as SevEnum
        from modelmesh.interfaces.observability import TraceEntry

        sev = severity if isinstance(severity, SevEnum) else SevEnum(severity.lower())
        entry = TraceEntry(
            severity=sev,
            timestamp=datetime.now(),
            component=component,
            message=message,
            metadata=metadata if metadata else None,
        )
        if self._observability:
            self._observability.trace(entry)

    # -- Internal setup ------------------------------------------------------

    def _check_initialized(self) -> None:
        """Raise if the mesh is not initialized."""
        if not self._initialized:
            raise RuntimeError(
                "ModelMesh not initialized. Call initialize() first."
            )

    def _setup_providers(self) -> None:
        """Configure providers from the MeshConfig.

        Iterates ``config.raw["providers"]``, resolving connector IDs
        to provider instances. Concrete connector instantiation is
        delegated to the CDK layer (being built in parallel); this
        method stores any pre-built ``instance`` references and
        creates placeholder entries for connectors that will be
        resolved later.
        """
        assert self._config is not None
        providers_cfg = self._config.raw.get("providers", {})

        for provider_name, provider_def in providers_cfg.items():
            # If an instance is provided directly (e.g. from QuickProvider),
            # use it as-is.
            if "instance" in provider_def:
                connector_id = provider_def.get(
                    "connector", f"{provider_name}.v1"
                )
                self._providers[connector_id] = provider_def["instance"]
                logger.debug(
                    "Registered pre-built provider '%s' as '%s'",
                    provider_name,
                    connector_id,
                )
                self._trace(
                    "DEBUG",
                    "mesh",
                    f"Registered pre-built provider '{provider_name}' "
                    f"as '{connector_id}'",
                    provider_name=provider_name,
                    connector_id=connector_id,
                )
                continue

            # Otherwise, register a stub entry. The CDK layer will
            # provide a connector factory that maps connector IDs to
            # concrete implementations. For now, store the config for
            # later resolution.
            connector_id = provider_def.get("connector", provider_name)
            enabled = provider_def.get("enabled", True)
            if not enabled:
                logger.debug("Provider '%s' is disabled, skipping", provider_name)
                continue

            # Placeholder: real connector instantiation happens via CDK.
            # We mark the connector ID as known so pools can reference it.
            logger.debug(
                "Registered provider config '%s' (connector: %s)",
                provider_name,
                connector_id,
            )
            self._trace(
                "DEBUG",
                "mesh",
                f"Registered provider config '{provider_name}' "
                f"(connector: {connector_id})",
                provider_name=provider_name,
                connector_id=connector_id,
            )

    def _resolve_model_capabilities(
        self, model_id: str, model_def: dict
    ) -> list[str]:
        """Resolve capabilities for a model: config first, then provider.

        Priority:
          1. Config ``model_def["capabilities"]`` (explicit override).
          2. Provider's per-model ``ModelInfo.capabilities`` (via
             ``list_models()``).
          3. Provider's ``get_capabilities()`` (provider-level fallback).

        Returns:
            List of capability tree paths.
        """
        # 1. Config override
        config_caps = model_def.get("capabilities", [])
        if config_caps:
            return list(config_caps)

        # 2. Query provider connector instance
        provider_id = model_def.get("provider", "")
        provider = self._providers.get(provider_id)
        if provider is None:
            return []

        # Try per-model capabilities from provider's model list
        try:
            parts = model_id.split(".", 1)
            bare_name = parts[1] if len(parts) > 1 else model_id
            for model_info in provider.list_models():
                if model_info.id in (model_id, bare_name):
                    if model_info.capabilities:
                        return list(model_info.capabilities)
        except Exception:
            pass  # Provider may not support list_models

        # 3. Provider-level fallback
        try:
            caps = provider.get_capabilities()
            if caps:
                return list(caps)
        except Exception:
            pass

        return []

    def _setup_pools(self) -> None:
        """Configure capability pools from the MeshConfig.

        Iterates ``config.raw["pools"]``, creates ``CapabilityPool``
        objects, and populates them with models from
        ``config.raw["models"]``.

        Pools support three definition modes:

        1. **Capability-based** — ``capability`` field matches models
           whose capabilities overlap with the target.
        2. **Explicit models** — ``models`` list names specific model
           IDs to include.
        3. **Hybrid** — both ``capability`` and ``models`` are given;
           capability matching auto-discovers models and explicit
           entries are added on top.

        Model capabilities are resolved via
        :meth:`_resolve_model_capabilities`: config-declared
        capabilities win; otherwise the provider connector is queried.
        """
        assert self._config is not None
        pools_cfg = self._config.raw.get("pools", {})
        models_cfg = self._config.raw.get("models", {})

        # Resolve capabilities for every model (use a separate dict to
        # avoid mutating config.raw with internal keys).
        resolved_caps: dict[str, list[str]] = {}
        for model_id, model_def in models_cfg.items():
            resolved = self._resolve_model_capabilities(model_id, model_def)
            resolved_caps[model_id] = resolved
            for cap in resolved:
                self._capability_tree.register(cap)

        # Build pools
        for pool_id, pool_def in pools_cfg.items():
            pool = CapabilityPool(
                pool_id, pool_def, observability=self._observability
            )

            added_model_ids: set[str] = set()
            target_capability = pool_def.get("capability", None)
            explicit_models = pool_def.get("models", None)

            # --- Capability-based matching ---
            if target_capability is not None:
                self._capability_tree.register(target_capability)
                matching_caps = self._capability_tree.resolve(
                    target_capability
                )
                pool_providers = pool_def.get("providers", None)

                for model_id, model_def in models_cfg.items():
                    model_caps = set(
                        resolved_caps.get(
                            model_id,
                            model_def.get("capabilities", []),
                        )
                    )
                    if not model_caps.intersection(matching_caps):
                        continue

                    provider_id = model_def.get("provider", "")
                    if pool_providers and provider_id not in pool_providers:
                        continue

                    parts = model_id.split(".", 1)
                    real_model_id = (
                        parts[1] if len(parts) > 1 else model_id
                    )

                    pool.add_model(
                        PoolModel(
                            model_id=model_id,
                            real_model_id=real_model_id,
                            provider_id=provider_id,
                        )
                    )
                    added_model_ids.add(model_id)

            # --- Explicit model list ---
            if explicit_models is not None:
                for model_id in explicit_models:
                    if model_id in added_model_ids:
                        continue
                    model_def = models_cfg.get(model_id, {})
                    provider_id = model_def.get("provider", "")

                    parts = model_id.split(".", 1)
                    real_model_id = (
                        parts[1] if len(parts) > 1 else model_id
                    )

                    pool.add_model(
                        PoolModel(
                            model_id=model_id,
                            real_model_id=real_model_id,
                            provider_id=provider_id,
                        )
                    )
                    added_model_ids.add(model_id)

            # --- Fallback: use pool_id as capability if nothing matched ---
            if not target_capability and not explicit_models:
                self._capability_tree.register(pool_id)
                matching_caps = self._capability_tree.resolve(pool_id)

                for model_id, model_def in models_cfg.items():
                    model_caps = set(
                        resolved_caps.get(
                            model_id,
                            model_def.get("capabilities", []),
                        )
                    )
                    if not model_caps.intersection(matching_caps):
                        continue

                    provider_id = model_def.get("provider", "")
                    parts = model_id.split(".", 1)
                    real_model_id = (
                        parts[1] if len(parts) > 1 else model_id
                    )

                    pool.add_model(
                        PoolModel(
                            model_id=model_id,
                            real_model_id=real_model_id,
                            provider_id=provider_id,
                        )
                    )

            # Resolve selection strategy for this pool
            self._resolve_pool_strategy(pool, pool_def)

            self._pools[pool_id] = pool
            logger.debug(
                "Pool '%s' configured with %d model(s)",
                pool_id,
                len(pool.models),
            )
            self._trace(
                "DEBUG",
                "mesh",
                f"Pool '{pool_id}' configured with "
                f"{len(pool.models)} model(s)",
                pool_id=pool_id,
                model_count=len(pool.models),
            )

    def _resolve_pool_strategy(
        self, pool: CapabilityPool, pool_def: dict
    ) -> None:
        """Resolve the selection strategy for a pool.

        Priority:
          1. Pre-built ``strategy_instance`` in pool config.
          2. Connector ID in ``strategy`` field → look up in CONNECTOR_REGISTRY.
          3. Fall back to pool's default (StickUntilFailure).
        """
        # 1. Pre-built instance injection
        strategy_instance = pool_def.get("strategy_instance")
        if strategy_instance is not None:
            pool.set_strategy(strategy_instance)
            self._trace(
                "DEBUG",
                "mesh",
                f"Pool '{pool.pool_id}' using pre-built strategy instance",
                pool_id=pool.pool_id,
            )
            return

        # 2. Connector ID from config
        strategy_id = pool_def.get("strategy")
        if strategy_id and isinstance(strategy_id, str):
            from modelmesh.connectors import CONNECTOR_REGISTRY

            strategy_cls = CONNECTOR_REGISTRY.get(strategy_id)
            if strategy_cls:
                try:
                    pool.set_strategy(strategy_cls())
                    self._trace(
                        "DEBUG",
                        "mesh",
                        f"Pool '{pool.pool_id}' using strategy '{strategy_id}'",
                        pool_id=pool.pool_id,
                        strategy_id=strategy_id,
                    )
                    return
                except Exception:
                    logger.debug(
                        "Failed to instantiate strategy '%s' for pool '%s'",
                        strategy_id,
                        pool.pool_id,
                        exc_info=True,
                    )

        # 3. Fall back to default (already set in pool __init__)

    def _setup_storage(self) -> None:
        """Resolve storage connector from config.

        Supports pre-built instance injection via ``"instance"`` key,
        or connector ID lookup in CONNECTOR_REGISTRY.
        """
        assert self._config is not None
        storage_cfg = self._config.raw.get("storage", {})
        if not storage_cfg:
            return

        # Pre-built instance
        if "instance" in storage_cfg and storage_cfg["instance"] is not None:
            self._storage = storage_cfg["instance"]
            self._trace(
                "DEBUG", "mesh", "Using pre-built storage instance"
            )
            return

        # Connector ID lookup
        connector_id = storage_cfg.get("connector")
        if connector_id:
            from modelmesh.connectors import CONNECTOR_REGISTRY

            storage_cls = CONNECTOR_REGISTRY.get(connector_id)
            if storage_cls:
                try:
                    self._storage = storage_cls(storage_cfg.get("config", {}))
                    self._trace(
                        "DEBUG",
                        "mesh",
                        f"Storage connector '{connector_id}' initialized",
                    )
                except Exception:
                    logger.debug(
                        "Failed to init storage '%s'",
                        connector_id,
                        exc_info=True,
                    )

    def _setup_secrets(self) -> None:
        """Resolve secret store connector from config.

        Supports pre-built instance injection via ``"instance"`` key,
        or connector ID lookup in CONNECTOR_REGISTRY.
        """
        assert self._config is not None
        secrets_cfg = self._config.raw.get("secrets", {})
        if not secrets_cfg:
            return

        # Pre-built instance
        if "instance" in secrets_cfg and secrets_cfg["instance"] is not None:
            self._secret_store = secrets_cfg["instance"]
            self._trace(
                "DEBUG", "mesh", "Using pre-built secret store instance"
            )
            return

        # Connector ID lookup
        store_id = secrets_cfg.get("store")
        if store_id:
            from modelmesh.connectors import CONNECTOR_REGISTRY

            store_cls = CONNECTOR_REGISTRY.get(store_id)
            if store_cls:
                try:
                    self._secret_store = store_cls(
                        secrets_cfg.get("config", {})
                    )
                    self._trace(
                        "DEBUG",
                        "mesh",
                        f"Secret store '{store_id}' initialized",
                    )
                except Exception:
                    logger.debug(
                        "Failed to init secret store '%s'",
                        store_id,
                        exc_info=True,
                    )

    def _setup_discovery(self) -> None:
        """Resolve discovery connector from config.

        Supports pre-built instance injection via ``"instance"`` key,
        or connector ID lookup in CONNECTOR_REGISTRY.
        """
        assert self._config is not None
        disc_cfg = self._config.raw.get("discovery", {})
        if not disc_cfg:
            return

        # Pre-built instance
        if "instance" in disc_cfg and disc_cfg["instance"] is not None:
            self._discovery = disc_cfg["instance"]
            self._trace(
                "DEBUG", "mesh", "Using pre-built discovery instance"
            )
            return

        # Connector ID lookup
        connector_id = disc_cfg.get("connector")
        if connector_id:
            from modelmesh.connectors import CONNECTOR_REGISTRY

            disc_cls = CONNECTOR_REGISTRY.get(connector_id)
            if disc_cls:
                try:
                    self._discovery = disc_cls(disc_cfg.get("config", {}))
                    self._trace(
                        "DEBUG",
                        "mesh",
                        f"Discovery connector '{connector_id}' initialized",
                    )
                except Exception:
                    logger.debug(
                        "Failed to init discovery '%s'",
                        connector_id,
                        exc_info=True,
                    )
