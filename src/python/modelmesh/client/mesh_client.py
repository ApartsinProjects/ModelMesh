"""MeshClient -- OpenAI SDK-compatible client backed by ModelMesh routing.

Provides the same interface as ``openai.OpenAI()`` so that existing code
can migrate by changing two lines: the import and the client creation.
Supports ``client.chat.completions.create()``, ``client.embeddings.create()``,
``client.models.list()``, and ModelMesh extensions like ``client.pool_status()``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from modelmesh._sync import _run_sync
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
)

if TYPE_CHECKING:
    from modelmesh.core.mesh import ModelMesh

__all__ = [
    "MeshClient",
]


class MeshClient:
    """OpenAI SDK-compatible client backed by ModelMesh routing.

    Exposes the standard OpenAI namespaces (``chat``, ``embeddings``,
    ``models``) and ModelMesh extensions (``mesh``, ``pool_status``,
    ``active_providers``, ``rotate``).

    Args:
        mesh: The initialized ModelMesh instance to route through.
    """

    def __init__(self, mesh: ModelMesh) -> None:
        self._mesh = mesh
        self.chat = _ChatNamespace(self)
        self.embeddings = _EmbeddingsNamespace(self)
        self.models = _ModelsNamespace(self)

    @property
    def mesh(self) -> ModelMesh:
        """Access the underlying ModelMesh instance for full control."""
        return self._mesh

    def pool_status(self, pool: str | None = None) -> dict:
        """Return health status for pools.

        Args:
            pool: If provided, return status for only this pool.
                If ``None``, return status for all pools.

        Returns:
            Dict mapping pool IDs to status dicts with ``active``,
            ``standby``, ``total``, and ``current_model`` keys.
            If *pool* is specified, returns just that pool's status dict.
        """
        all_status = self._mesh.pool_status()
        if pool is not None:
            if pool not in all_status:
                raise KeyError(f"Pool '{pool}' not found")
            return all_status[pool]
        return all_status

    def active_providers(self) -> list[str]:
        """Return the list of currently active provider connector IDs."""
        return self._mesh.active_providers()

    def describe(self, pool: str | None = None) -> str:
        """Describe the models and strategy behind each virtual model (pool).

        Args:
            pool: If provided, describe only this pool. Otherwise all pools.

        Returns:
            Human-readable multi-line string showing pool composition.
        """
        pools = self._mesh.pools
        if pool is not None:
            if pool not in pools:
                raise KeyError(f"Pool '{pool}' not found")
            pools = {pool: pools[pool]}

        lines: list[str] = []
        for pool_id, pool_obj in pools.items():
            strategy = pool_obj.config.get("strategy", "stick-until-failure")
            cap = pool_obj.config.get("capability", pool_id)
            lines.append(f'Pool "{pool_id}" (strategy: {strategy})')
            lines.append(f"  capability: {cap}")
            for i, m in enumerate(pool_obj.models):
                marker = "\u2192" if i == 0 and m.status.value == "active" else " "
                lines.append(
                    f"  {marker} {m.model_id} [{m.provider_id}] ({m.status.value})"
                )
            if not pool_obj.models:
                lines.append("  (no models)")
        return "\n".join(lines)

    def rotate(self, pool: str) -> Optional[str]:
        """Force an immediate rotation in a pool.

        Args:
            pool: The pool ID to rotate.

        Returns:
            The model ID of the newly selected model, or None.
        """
        return self._mesh.rotate(pool)


# ---------------------------------------------------------------------------
# Chat namespace
# ---------------------------------------------------------------------------


class _ChatNamespace:
    """Namespace for ``client.chat.completions``."""

    def __init__(self, client: MeshClient) -> None:
        self.completions = _ChatCompletions(client)


class _ChatCompletions:
    """Implements ``client.chat.completions.create()``.

    Synchronous interface that wraps the async ModelMesh routing
    pipeline using ``_run_sync()``.
    """

    def __init__(self, client: MeshClient) -> None:
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 1.0,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list | None = None,
        top_p: float = 1.0,
        stop: list[str] | None = None,
        **kwargs,
    ) -> CompletionResponse | _StreamIterator:
        """Create a chat completion.

        Accepts all standard OpenAI parameters. The ``model`` field is
        a virtual model name that resolves to a capability pool.

        Args:
            model: Virtual model name (pool ID).
            messages: Conversation messages.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stream: If True, return a streaming iterator.
            tools: Tool definitions for function calling.
            top_p: Nucleus sampling threshold.
            stop: Stop sequences.
            **kwargs: Additional provider-specific parameters.

        Returns:
            A ``CompletionResponse`` (non-streaming) or a
            ``_StreamIterator`` (streaming).
        """
        request = CompletionRequest(
            model=model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            top_p=top_p,
            stop=stop,
        )

        mesh = self._client.mesh

        if stream:
            return _StreamIterator(mesh, request)

        return _run_sync(mesh.route(request))


class _StreamIterator:
    """Synchronous iterator wrapping the async streaming pipeline.

    Provides OpenAI SDK-compatible iteration::

        for chunk in stream:
            print(chunk.choices[0].delta.content, end="")

    Internally uses ``_run_sync()`` to bridge the async generator.
    """

    def __init__(self, mesh: ModelMesh, request: CompletionRequest) -> None:
        self._mesh = mesh
        self._request = request
        self._aiter = None

    def __iter__(self):
        return self

    def __next__(self) -> CompletionResponse:
        if self._aiter is None:
            # Create the async generator
            self._aiter = self._mesh.route_stream(self._request).__aiter__()
        try:
            return _run_sync(self._aiter.__anext__())
        except StopAsyncIteration:
            raise StopIteration


# ---------------------------------------------------------------------------
# Embeddings namespace
# ---------------------------------------------------------------------------


class _EmbeddingsNamespace:
    """Namespace for ``client.embeddings.create()``.

    Routes embedding requests through the appropriate capability pool.
    """

    def __init__(self, client: MeshClient) -> None:
        self._client = client

    def create(
        self,
        *,
        model: str,
        input: str | list[str],
        **kwargs,
    ) -> CompletionResponse:
        """Create embeddings.

        Routes through the pool identified by *model* (e.g.
        ``"text-embeddings"``). The underlying provider must support
        the embeddings capability.

        Args:
            model: Virtual model name for the embeddings pool.
            input: Text or list of texts to embed.
            **kwargs: Additional provider-specific parameters.

        Returns:
            A CompletionResponse containing embedding data.
        """
        # Normalize input to a list
        if isinstance(input, str):
            input = [input]

        request = CompletionRequest(
            model=model,
            messages=[{"role": "user", "content": text} for text in input],
            temperature=0.0,
        )

        return _run_sync(self._client.mesh.route(request))


# ---------------------------------------------------------------------------
# Models namespace
# ---------------------------------------------------------------------------


@dataclass
class _ModelEntry:
    """A single model entry returned by ``client.models.list()``.

    Matches the OpenAI ``Model`` object shape.
    """

    id: str
    object: str = "model"
    owned_by: str = "unknown"


@dataclass
class _ModelList:
    """Response from ``client.models.list()``.

    Matches the OpenAI ``ListModelsResponse`` shape.
    """

    data: list[_ModelEntry] = field(default_factory=list)
    object: str = "list"


class _ModelsNamespace:
    """Namespace for ``client.models.list()``.

    Returns all models available across all configured pools.
    """

    def __init__(self, client: MeshClient) -> None:
        self._client = client

    def list(self) -> _ModelList:
        """List all available models.

        Returns:
            A ``_ModelList`` with OpenAI-compatible model entries.
        """
        raw_models = self._client.mesh.list_models()
        entries = [
            _ModelEntry(
                id=m["id"],
                object=m.get("object", "model"),
                owned_by=m.get("owned_by", "unknown"),
            )
            for m in raw_models
        ]
        return _ModelList(data=entries)
