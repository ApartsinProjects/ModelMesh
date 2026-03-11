"""Request router — resolves capabilities to pools and executes requests.

The router implements the full request pipeline: capability resolution,
pool selection, model selection, provider execution, and retry/rotation
on failure. It is the central orchestration component of ModelMesh Lite.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, AsyncIterator, Optional

from modelmesh.core.capability_tree import CapabilityTree
from modelmesh.core.event_emitter import EventEmitter, EventType
from modelmesh.core.pool import CapabilityPool, PoolModel
from modelmesh.exceptions import (
    AllProvidersExhaustedError,
    NoActiveModelError,
)
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
    ProviderConnector,
)

if TYPE_CHECKING:
    from modelmesh.middleware import MiddlewareStack

logger = logging.getLogger("modelmesh.router")

__all__ = ["NoActiveModelError", "Router"]


class Router:
    """Routes requests through the capability resolution / model selection pipeline.

    The routing pipeline:

    1. Resolve the virtual model name to a capability pool.
    2. Select the best active model from the pool using the pool's strategy.
    3. Build a provider-specific request with the real model name.
    4. Execute through the provider connector.
    5. On success, record the result and return.
    6. On failure, record the failure, attempt rotation, and retry.

    Args:
        pools: Mapping of pool IDs to CapabilityPool instances.
        capability_tree: The capability hierarchy for path-based resolution.
        providers: Mapping of connector IDs to ProviderConnector instances.
        event_emitter: Optional event emitter for observability.
        max_retries: Maximum retry attempts across rotation (default: 3).
    """

    def __init__(
        self,
        pools: dict[str, CapabilityPool],
        capability_tree: CapabilityTree,
        providers: dict[str, ProviderConnector],
        event_emitter: Optional[EventEmitter] = None,
        observability=None,
        max_retries: int = 3,
        middleware: Optional[MiddlewareStack] = None,
    ) -> None:
        self._pools = pools
        self._capability_tree = capability_tree
        self._providers = providers
        self._emitter = event_emitter or EventEmitter()
        self._observability = observability
        self._max_retries = max_retries
        self._middleware = middleware

    def _trace(
        self,
        severity,
        component: str,
        message: str,
        error: str | None = None,
        **metadata,
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
            error=error,
            metadata=metadata if metadata else None,
        )
        if self._observability:
            self._observability.trace(entry)

    @property
    def pools(self) -> dict[str, CapabilityPool]:
        """Mapping of pool IDs to CapabilityPool instances."""
        return self._pools

    @property
    def providers(self) -> dict[str, ProviderConnector]:
        """Mapping of connector IDs to ProviderConnector instances."""
        return self._providers

    async def route(self, request: CompletionRequest) -> CompletionResponse:
        """Route a non-streaming request through the full pipeline.

        Args:
            request: The incoming completion request. The ``model`` field
                is treated as a virtual model name (pool ID).

        Returns:
            The completion response from the selected provider.

        Raises:
            NoActiveModelError: If no active model is available.
            KeyError: If no pool matches the virtual model name.
        """
        self._trace(
            "DEBUG",
            "router",
            f"Routing request for model '{request.model}'",
            model=request.model,
        )
        pool = self.resolve_pool(request.model)
        model = pool.select(request)

        if model is None:
            self._emitter.emit(
                EventType.POOL_EXHAUSTED,
                pool_id=pool.pool_id,
            )
            self._trace(
                "ERROR",
                "router",
                f"No active model available in pool '{request.model}'",
                error=f"NoActiveModelError: pool '{request.model}'",
                pool_id=pool.pool_id,
            )
            raise NoActiveModelError(
                f"No active model available in pool '{request.model}'"
            )

        return await self._execute_with_rotation(request, pool, model)

    async def route_stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[CompletionResponse]:
        """Route a streaming request through the full pipeline.

        Yields completion response chunks from the selected provider.
        On failure during streaming, rotation is attempted and the
        stream restarts with the next model.

        Args:
            request: The incoming completion request with ``stream=True``.

        Yields:
            CompletionResponse chunks.

        Raises:
            NoActiveModelError: If no active model is available.
            KeyError: If no pool matches the virtual model name.
        """
        self._trace(
            "DEBUG",
            "router",
            f"Streaming request for model '{request.model}'",
            model=request.model,
        )
        pool = self.resolve_pool(request.model)
        model = pool.select(request)

        if model is None:
            self._emitter.emit(
                EventType.POOL_EXHAUSTED,
                pool_id=pool.pool_id,
            )
            self._trace(
                "ERROR",
                "router",
                f"No active model available in pool '{request.model}'",
                error=f"NoActiveModelError: pool '{request.model}'",
                pool_id=pool.pool_id,
            )
            raise NoActiveModelError(
                f"No active model available in pool '{request.model}'"
            )

        attempts = 0
        current_model = model

        while current_model is not None and attempts < self._max_retries:
            provider = self._providers.get(current_model.provider_id)
            if provider is None:
                logger.warning(
                    "Provider '%s' not found for model '%s'",
                    current_model.provider_id,
                    current_model.model_id,
                )
                pool.record_failure(current_model.model_id, RuntimeError("Provider not found"))
                current_model = pool.select(request)
                attempts += 1
                continue

            provider_request = self._build_provider_request(
                request, current_model
            )

            try:
                async for chunk in provider.stream(provider_request):
                    yield chunk
                pool.record_success(current_model.model_id)
                self._emitter.emit(
                    EventType.REQUEST_SUCCESS,
                    pool_id=pool.pool_id,
                    model_id=current_model.model_id,
                    provider_id=current_model.provider_id,
                )
                return
            except Exception as e:
                logger.warning(
                    "Streaming failure on '%s': %s",
                    current_model.model_id,
                    e,
                )
                self._trace(
                    "WARNING",
                    "router",
                    f"Stream failure on '{current_model.model_id}': {e}",
                    error=str(e),
                    model_id=current_model.model_id,
                    provider_id=current_model.provider_id,
                    attempt=attempts + 1,
                )
                pool.record_failure(current_model.model_id, e)
                self._emitter.emit(
                    EventType.REQUEST_FAILURE,
                    pool_id=pool.pool_id,
                    model_id=current_model.model_id,
                    error=str(e),
                )
                current_model = pool.select(request)
                attempts += 1

        self._trace(
            "ERROR",
            "router",
            f"All models exhausted in pool '{request.model}' after "
            f"{attempts} attempts",
            error="All models exhausted",
            pool_id=pool.pool_id,
            attempts=attempts,
        )
        raise AllProvidersExhaustedError(
            f"All models exhausted in pool '{request.model}' after "
            f"{attempts} attempts",
            pool_name=request.model,
            attempts=attempts,
        )

    def resolve_pool(self, model_name: str) -> CapabilityPool:
        """Resolve a virtual model name to a capability pool.

        Looks up by direct pool ID first, then falls back to resolving
        the name through the capability tree (matching against pool
        capability paths).

        Args:
            model_name: The pool ID, capability path, or virtual model
                name from the request's ``model`` field.

        Returns:
            The matching CapabilityPool.

        Raises:
            KeyError: If no pool matches.
        """
        # Direct pool ID lookup
        if model_name in self._pools:
            self._trace(
                "DEBUG",
                "router",
                f"Resolved pool '{model_name}' by direct ID",
                model_name=model_name,
            )
            return self._pools[model_name]

        # Capability tree resolution: find leaf capabilities that match
        # and then locate a pool whose capability covers that path.
        resolved_caps = self._capability_tree.resolve(model_name)
        if resolved_caps:
            for pool_id, pool in self._pools.items():
                pool_cap = pool.config.get("capability", pool_id)
                pool_leaves = self._capability_tree.resolve(pool_cap)
                if set(resolved_caps) & set(pool_leaves):
                    self._trace(
                        "DEBUG",
                        "router",
                        f"Resolved pool '{pool_id}' for model "
                        f"'{model_name}' via capability tree",
                        model_name=model_name,
                        pool_id=pool_id,
                    )
                    return pool

        self._trace(
            "ERROR",
            "router",
            f"No pool found for virtual model: {model_name}",
            error=f"KeyError: {model_name}",
            model_name=model_name,
        )
        raise KeyError(f"No pool found for virtual model: {model_name}")

    async def _execute_with_rotation(
        self,
        request: CompletionRequest,
        pool: CapabilityPool,
        model: PoolModel,
    ) -> CompletionResponse:
        """Execute a request with retry and rotation on failure.

        Tries the selected model first, then rotates through remaining
        active models in the pool up to ``max_retries`` attempts.

        Args:
            request: The original completion request.
            pool: The resolved capability pool.
            model: The initially selected model.

        Returns:
            The completion response.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        attempts = 0
        current_model: Optional[PoolModel] = model
        last_error: Optional[Exception] = None

        while current_model is not None and attempts < self._max_retries:
            provider = self._providers.get(current_model.provider_id)
            if provider is None:
                logger.warning(
                    "Provider '%s' not found for model '%s'",
                    current_model.provider_id,
                    current_model.model_id,
                )
                pool.record_failure(
                    current_model.model_id,
                    RuntimeError("Provider not found"),
                )
                current_model = pool.select(request)
                attempts += 1
                continue

            provider_request = self._build_provider_request(
                request, current_model
            )

            self._trace(
                "DEBUG",
                "router",
                f"Request routed to model '{current_model.model_id}' "
                f"via provider '{current_model.provider_id}'",
                model_id=current_model.model_id,
                provider_id=current_model.provider_id,
                pool_id=pool.pool_id,
                attempt=attempts + 1,
            )

            self._emitter.emit(
                EventType.REQUEST_ROUTED,
                pool_id=pool.pool_id,
                model_id=current_model.model_id,
                provider_id=current_model.provider_id,
                attempt=attempts + 1,
            )

            try:
                # Run middleware before_request hooks
                effective_request = provider_request
                mw_context = None
                if self._middleware and len(self._middleware) > 0:
                    from modelmesh.middleware import MiddlewareContext

                    mw_context = MiddlewareContext(
                        model_id=current_model.model_id,
                        provider_id=current_model.provider_id,
                        pool_name=request.model,
                        attempt=attempts + 1,
                    )
                    effective_request = await self._middleware.run_before_request(
                        provider_request, mw_context
                    )

                response = await provider.complete(effective_request)

                # Run middleware after_response hooks
                if self._middleware and mw_context and len(self._middleware) > 0:
                    response = await self._middleware.run_after_response(
                        response, mw_context
                    )

                pool.record_success(current_model.model_id)
                self._emitter.emit(
                    EventType.REQUEST_SUCCESS,
                    pool_id=pool.pool_id,
                    model_id=current_model.model_id,
                    provider_id=current_model.provider_id,
                )
                self._trace(
                    "INFO",
                    "router",
                    f"Request succeeded on '{current_model.model_id}'",
                    model_id=current_model.model_id,
                    provider_id=current_model.provider_id,
                    pool_id=pool.pool_id,
                )
                return response
            except Exception as e:
                # Run middleware on_error hooks — may return fallback
                if self._middleware and mw_context and len(self._middleware) > 0:
                    try:
                        fallback = await self._middleware.run_on_error(
                            e, mw_context
                        )
                        pool.record_success(current_model.model_id)
                        return fallback
                    except Exception:
                        pass  # Middleware didn't handle it; continue with rotation

                last_error = e
                logger.warning(
                    "Request failure on '%s' (attempt %d): %s",
                    current_model.model_id,
                    attempts + 1,
                    e,
                )
                self._trace(
                    "WARNING",
                    "router",
                    f"Request failure on '{current_model.model_id}' "
                    f"(attempt {attempts + 1}): {e}",
                    error=str(e),
                    model_id=current_model.model_id,
                    provider_id=current_model.provider_id,
                    pool_id=pool.pool_id,
                    attempt=attempts + 1,
                )
                pool.record_failure(current_model.model_id, e)
                self._emitter.emit(
                    EventType.REQUEST_FAILURE,
                    pool_id=pool.pool_id,
                    model_id=current_model.model_id,
                    error=str(e),
                )

                # Attempt rotation
                current_model = pool.select(request)
                if current_model is not None:
                    self._emitter.emit(
                        EventType.MODEL_ROTATED,
                        pool_id=pool.pool_id,
                        new_model_id=current_model.model_id,
                        reason=str(e),
                    )
                attempts += 1

        error_msg = (
            f"All models exhausted in pool '{request.model}' after "
            f"{attempts} attempts"
        )
        if last_error:
            error_msg += f". Last error: {last_error}"
        self._trace(
            "ERROR",
            "router",
            error_msg,
            error=str(last_error) if last_error else "All models exhausted",
            pool_id=pool.pool_id,
            attempts=attempts,
        )
        raise AllProvidersExhaustedError(
            error_msg,
            pool_name=request.model,
            attempts=attempts,
            last_error=last_error,
        )

    @staticmethod
    def _build_provider_request(
        request: CompletionRequest, model: PoolModel
    ) -> CompletionRequest:
        """Build a provider-specific request with the real model name.

        Copies the original request but replaces the virtual model name
        with the provider's actual model identifier.

        Args:
            request: The original request with virtual model name.
            model: The selected PoolModel with real model details.

        Returns:
            A new CompletionRequest with the real model name.
        """
        return CompletionRequest(
            model=model.real_model_id,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
            tools=request.tools,
            top_p=request.top_p,
            stop=request.stop,
        )
