"""MeshClient -- OpenAI SDK-compatible client backed by ModelMesh routing.

Provides the same interface as ``openai.OpenAI()`` so that existing code
can migrate by changing two lines: the import and the client creation.
Supports ``client.chat.completions.create()``, ``client.embeddings.create()``,
``client.models.list()``, and ModelMesh extensions like ``client.pool_status()``.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from modelmesh._sync import _run_sync
from modelmesh.interfaces.provider import (
    AudioSpeechResponse,
    AudioTranscriptionResponse,
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
        self.audio = _AudioNamespace(self)
        self.models = _ModelsNamespace(self)

    # -- Context manager protocol ------------------------------------------------

    def __enter__(self) -> MeshClient:
        """Enter the runtime context (sync)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the runtime context and shut down the mesh."""
        self._mesh.shutdown()
        return False

    async def __aenter__(self) -> MeshClient:
        """Enter the runtime context (async)."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the runtime context and shut down the mesh."""
        self._mesh.shutdown()
        return False

    # -- Properties --------------------------------------------------------------

    @property
    def mesh(self) -> ModelMesh:
        """Access the underlying ModelMesh instance for full control."""
        return self._mesh

    @property
    def usage(self):
        """Return a :class:`~modelmesh.usage.UsageTracker` for cost/usage data.

        Lazily creates the tracker on first access.
        """
        if not hasattr(self, "_usage_tracker"):
            from modelmesh.usage import UsageTracker

            self._usage_tracker = UsageTracker(self._mesh)
        return self._usage_tracker

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

    def explain(
        self,
        *,
        model: str,
        messages: list[dict] | None = None,
        **kwargs,
    ) -> dict:
        """Dry-run the routing pipeline and explain the selection.

        Returns a dict describing which pool, strategy, candidates,
        and model would be chosen — without calling the provider.

        Args:
            model: Virtual model name (pool ID).
            messages: Optional messages (used by selection strategies
                that inspect the request).
            **kwargs: Additional request parameters.

        Returns:
            A dict with ``pool_name``, ``strategy``, ``selected_model``,
            ``candidates``, and ``reason`` keys.
        """
        from modelmesh.interfaces.provider import CompletionRequest

        request = CompletionRequest(
            model=model,
            messages=messages or [{"role": "user", "content": ""}],
            **kwargs,
        )

        router = self._mesh.get_router()
        pool = router.resolve_pool(request.model)

        strategy = pool.config.get("strategy", "stick-until-failure")
        capability = pool.config.get("capability", model)

        candidates = []
        for m in pool.models:
            candidates.append({
                "model_id": m.model_id,
                "provider_id": m.provider_id,
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            })

        selected = pool.select(request)
        selected_model = selected.model_id if selected else None
        reason = (
            f"Selected by '{strategy}' strategy"
            if selected
            else "No active model available"
        )

        return {
            "pool_name": pool.pool_id,
            "strategy": strategy,
            "capability": capability,
            "selected_model": selected_model,
            "candidates": candidates,
            "reason": reason,
        }


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

    Uses a dedicated background event loop so the async generator
    remains valid across multiple ``__next__`` calls.
    """

    def __init__(self, mesh: ModelMesh, request: CompletionRequest) -> None:
        self._mesh = mesh
        self._request = request
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._aiter = None

    def _ensure_loop(self) -> None:
        """Start a persistent background event loop if not yet running."""
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()

        def _run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()

    def __iter__(self):
        return self

    def __next__(self) -> CompletionResponse:
        self._ensure_loop()
        assert self._loop is not None
        if self._aiter is None:
            # Create the async generator on the persistent loop
            self._aiter = self._mesh.route_stream(self._request).__aiter__()
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._aiter.__anext__(), self._loop
            )
            return future.result()
        except StopAsyncIteration:
            self._cleanup()
            raise StopIteration

    # -- Context manager protocol for safe resource cleanup ----------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self) -> None:
        """Explicitly shut down the background loop and thread.

        Prefer using the context manager (``with``) or calling
        ``close()`` instead of relying on garbage collection.
        """
        self._cleanup()

    def _cleanup(self) -> None:
        """Shut down the background loop and thread."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._loop.close()
            self._loop = None
            self._thread = None

    def __del__(self):
        self._cleanup()


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
# Audio namespace
# ---------------------------------------------------------------------------


class _AudioSpeechNamespace:
    """Namespace for ``client.audio.speech.create()``.

    Routes text-to-speech requests through the appropriate capability pool.
    """

    def __init__(self, client: MeshClient) -> None:
        self._client = client

    def create(
        self,
        *,
        model: str,
        input: str,
        voice: str,
        response_format: str = "mp3",
        speed: float = 1.0,
        **kwargs,
    ) -> AudioSpeechResponse:
        """Create speech from text (text-to-speech).

        Routes through a pool with the ``text-to-speech`` capability.
        The text is passed as a user message to the underlying provider.

        Args:
            model: Virtual model name for the TTS pool.
            input: Text to synthesize.
            voice: Voice identifier (provider-specific).
            response_format: Output audio format (e.g. "mp3", "wav").
            speed: Speech speed multiplier (0.25–4.0).

        Returns:
            An ``AudioSpeechResponse`` with audio metadata.
        """
        request = CompletionRequest(
            model=model,
            messages=[{"role": "user", "content": input}],
            temperature=0.0,
        )

        response = _run_sync(self._client.mesh.route(request))

        return AudioSpeechResponse(
            format=response_format,
            model=response.model or model,
            input_characters=len(input),
            size_bytes=response.usage.completion_tokens,
        )


class _AudioTranscriptionsNamespace:
    """Namespace for ``client.audio.transcriptions.create()``.

    Routes speech-to-text requests through the appropriate capability pool.
    """

    def __init__(self, client: MeshClient) -> None:
        self._client = client

    def create(
        self,
        *,
        model: str,
        file: str,
        language: str | None = None,
        response_format: str = "json",
        prompt: str | None = None,
        **kwargs,
    ) -> AudioTranscriptionResponse:
        """Transcribe audio to text (speech-to-text).

        Routes through a pool with the ``speech-to-text`` capability.
        The audio URL is passed as a user message to the underlying provider.

        Args:
            model: Virtual model name for the STT pool.
            file: Audio file URL or path.
            language: Language hint (ISO-639-1).
            response_format: Output format ("json", "text", "srt", "vtt").
            prompt: Prompt to guide transcription.

        Returns:
            An ``AudioTranscriptionResponse`` with transcribed text.
        """
        request = CompletionRequest(
            model=model,
            messages=[{"role": "user", "content": file}],
            temperature=0.0,
        )

        response = _run_sync(self._client.mesh.route(request))

        content = ""
        if response.choices:
            msg = response.choices[0].message
            if msg and msg.content:
                content = msg.content

        return AudioTranscriptionResponse(
            text=content,
            model=response.model or model,
        )


class _AudioNamespace:
    """Namespace for ``client.audio``."""

    def __init__(self, client: MeshClient) -> None:
        self.speech = _AudioSpeechNamespace(client)
        self.transcriptions = _AudioTranscriptionsNamespace(client)


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
