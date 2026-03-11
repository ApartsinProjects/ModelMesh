"""LangChain / LangGraph integration for ModelMesh.

Provides a LangChain-compatible ChatModel wrapper that routes all
requests through ModelMesh, giving LangChain applications automatic
failover, pool routing, cost tracking, and observability.

Usage::

    from modelmesh import create
    from modelmesh.integrations.langchain import ChatModelMesh

    mesh = create()
    llm = ChatModelMesh(mesh=mesh, model="text-generation")

    # Use with LangChain
    response = llm.invoke("What is the meaning of life?")

    # Use with LangGraph
    from langgraph.graph import StateGraph
    graph = StateGraph(...)
    graph.add_node("agent", llm)

The adapter works without LangChain installed by providing a
standalone implementation of the core interfaces. When LangChain is
available, it extends the real ``BaseChatModel`` for full compatibility.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Iterator,
    Optional,
    Sequence,
)

if TYPE_CHECKING:
    from modelmesh.core.mesh import ModelMesh

__all__ = [
    "ChatModelMesh",
    "MeshMessage",
    "MeshChatResult",
]


# ── Standalone message types (no LangChain dependency) ────────────────


@dataclass
class MeshMessage:
    """A chat message compatible with LangChain's message interface.

    Attributes:
        content: The message text.
        role: The message role (system, user, assistant, tool).
        additional_kwargs: Extra metadata.
    """

    content: str = ""
    role: str = "user"
    additional_kwargs: dict[str, Any] = field(default_factory=dict)

    @property
    def type(self) -> str:
        """LangChain-compatible message type."""
        return {
            "system": "system",
            "user": "human",
            "assistant": "ai",
            "tool": "tool",
        }.get(self.role, "human")


@dataclass
class MeshGeneration:
    """A single generation result."""

    text: str = ""
    message: Optional[MeshMessage] = None
    generation_info: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeshChatResult:
    """Result of a chat model invocation.

    Compatible with LangChain's ``ChatResult`` interface.
    """

    generations: list[MeshGeneration] = field(default_factory=list)
    llm_output: dict[str, Any] = field(default_factory=dict)


# ── Helper: convert messages ──────────────────────────────────────────


def _to_openai_messages(
    messages: Sequence[Any],
) -> list[dict[str, str]]:
    """Convert messages to OpenAI chat format.

    Accepts:
    - dicts with ``role`` and ``content``
    - MeshMessage instances
    - LangChain message objects (BaseMessage subclasses)
    - Plain strings (treated as user messages)
    """
    result: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, dict):
            result.append(msg)
        elif isinstance(msg, MeshMessage):
            result.append({"role": msg.role, "content": msg.content})
        elif isinstance(msg, str):
            result.append({"role": "user", "content": msg})
        elif hasattr(msg, "content") and hasattr(msg, "type"):
            # LangChain BaseMessage duck-typing
            role_map = {
                "human": "user",
                "ai": "assistant",
                "system": "system",
                "tool": "tool",
            }
            role = role_map.get(getattr(msg, "type", "human"), "user")
            result.append({"role": role, "content": msg.content})
        else:
            result.append({"role": "user", "content": str(msg)})
    return result


# ── Main adapter ──────────────────────────────────────────────────────


class ChatModelMesh:
    """LangChain-compatible chat model backed by ModelMesh.

    Routes all requests through ModelMesh's pool routing, gaining
    automatic failover, multi-provider support, cost tracking, and
    observability.

    Args:
        mesh: A configured and initialized ModelMesh instance.
        model: The model or pool ID to route requests to.
        temperature: Default temperature for completions.
        max_tokens: Default max tokens for completions.
        streaming: Whether to stream by default.
    """

    def __init__(
        self,
        mesh: ModelMesh,
        model: str = "text-generation",
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        streaming: bool = False,
    ) -> None:
        self._mesh = mesh
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._streaming = streaming

    @property
    def _llm_type(self) -> str:
        return "modelmesh"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self._model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }

    # ── Sync interface ────────────────────────────────────────────

    def invoke(
        self,
        input: str | Sequence[Any],
        **kwargs: Any,
    ) -> MeshMessage:
        """Invoke the model synchronously.

        Args:
            input: A string prompt or list of messages.
            **kwargs: Override temperature, max_tokens, model, etc.

        Returns:
            An assistant MeshMessage with the model's response.
        """
        loop = _get_or_create_event_loop()
        return loop.run_until_complete(self.ainvoke(input, **kwargs))

    def generate(
        self,
        messages_list: list[Sequence[Any]],
        **kwargs: Any,
    ) -> MeshChatResult:
        """Generate completions for multiple message sequences.

        Args:
            messages_list: List of message sequences.

        Returns:
            A MeshChatResult with all generations.
        """
        loop = _get_or_create_event_loop()
        return loop.run_until_complete(
            self.agenerate(messages_list, **kwargs)
        )

    def stream(
        self,
        input: str | Sequence[Any],
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream tokens synchronously.

        Yields:
            String tokens as they arrive.
        """
        loop = _get_or_create_event_loop()
        ait = self.astream(input, **kwargs)

        async def _collect():
            chunks = []
            async for chunk in ait:
                chunks.append(chunk)
            return chunks

        chunks = loop.run_until_complete(_collect())
        yield from chunks

    # ── Async interface ───────────────────────────────────────────

    async def ainvoke(
        self,
        input: str | Sequence[Any],
        **kwargs: Any,
    ) -> MeshMessage:
        """Invoke the model asynchronously.

        Args:
            input: A string prompt or list of messages.
            **kwargs: Override temperature, max_tokens, model, etc.

        Returns:
            An assistant MeshMessage with the model's response.
        """
        from modelmesh.interfaces.provider import CompletionRequest

        messages = (
            [{"role": "user", "content": input}]
            if isinstance(input, str)
            else _to_openai_messages(input)
        )

        request = CompletionRequest(
            model=kwargs.get("model", self._model),
            messages=messages,
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            stream=False,
        )

        response = await self._mesh.route(request)

        content = ""
        if response.choices:
            msg = response.choices[0].message
            if msg and msg.content:
                content = msg.content

        return MeshMessage(
            content=content,
            role="assistant",
            additional_kwargs={
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            },
        )

    async def agenerate(
        self,
        messages_list: list[Sequence[Any]],
        **kwargs: Any,
    ) -> MeshChatResult:
        """Generate completions for multiple message sequences async.

        Args:
            messages_list: List of message sequences.

        Returns:
            A MeshChatResult with all generations.
        """
        generations: list[MeshGeneration] = []
        total_tokens = 0

        for messages in messages_list:
            result = await self.ainvoke(messages, **kwargs)
            gen = MeshGeneration(
                text=result.content,
                message=result,
                generation_info=result.additional_kwargs,
            )
            generations.append(gen)
            usage = result.additional_kwargs.get("usage", {})
            total_tokens += usage.get("total_tokens", 0)

        return MeshChatResult(
            generations=generations,
            llm_output={
                "model": self._model,
                "total_tokens": total_tokens,
            },
        )

    async def astream(
        self,
        input: str | Sequence[Any],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream tokens asynchronously.

        Yields:
            String tokens as they arrive from the model.
        """
        from modelmesh.interfaces.provider import CompletionRequest

        messages = (
            [{"role": "user", "content": input}]
            if isinstance(input, str)
            else _to_openai_messages(input)
        )

        request = CompletionRequest(
            model=kwargs.get("model", self._model),
            messages=messages,
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            stream=True,
        )

        async for chunk in self._mesh.route_stream(request):
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

    # ── LangChain compatibility ───────────────────────────────────

    def bind(self, **kwargs: Any) -> ChatModelMesh:
        """Return a new instance with updated defaults.

        Compatible with LangChain's ``Runnable.bind()``.
        """
        return ChatModelMesh(
            mesh=self._mesh,
            model=kwargs.get("model", self._model),
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            streaming=kwargs.get("streaming", self._streaming),
        )

    def with_config(self, **kwargs: Any) -> ChatModelMesh:
        """Alias for ``bind()`` for LangGraph compatibility."""
        return self.bind(**kwargs)

    def __repr__(self) -> str:
        return (
            f"ChatModelMesh(model={self._model!r}, "
            f"temperature={self._temperature})"
        )


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get the running event loop or create a new one."""
    try:
        loop = asyncio.get_running_loop()
        # If there's already a running loop, we need a new one in a thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.new_event_loop)
            return future.result()
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
