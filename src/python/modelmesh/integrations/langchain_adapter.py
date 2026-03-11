"""LangChain integration for ModelMesh.

Provides a LangChain-compatible ChatModel wrapper that routes all
requests through ModelMesh's pool routing, giving LangChain applications
automatic failover, multi-provider support, cost tracking, and
observability.

This module extends the core :class:`ChatModelMesh` adapter with
LangChain-native base class integration when LangChain is installed.
When LangChain is not available, it re-exports the standalone
:class:`ChatModelMesh` which provides the same API surface.

Usage::

    from modelmesh.integrations.langchain_adapter import ChatModelMesh

    llm = ChatModelMesh(mesh=mesh, model="text-generation")
    result = llm.invoke("Hello!")

    # With LangChain chains
    from langchain_core.prompts import ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages([("user", "{input}")])
    chain = prompt | llm
    result = chain.invoke({"input": "Hello!"})
"""
from __future__ import annotations

import asyncio
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Iterator,
    List,
    Optional,
    Sequence,
)

if TYPE_CHECKING:
    from modelmesh.core.mesh import ModelMesh

logger = logging.getLogger("modelmesh.integrations.langchain_adapter")

__all__ = [
    "ChatModelMesh",
]

# ── Optional LangChain imports ────────────────────────────────────────

try:
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import (
        AIMessage,
        AIMessageChunk,
        BaseMessage,
        HumanMessage,  # noqa: F401
        SystemMessage,  # noqa: F401
    )
    from langchain_core.outputs import ChatGeneration, ChatResult

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False


# ── Message conversion helpers ────────────────────────────────────────


def _messages_to_openai_format(
    messages: Sequence[Any],
) -> list[dict[str, str]]:
    """Convert messages to OpenAI chat format.

    Accepts:
    - Dicts with ``role`` and ``content``
    - LangChain BaseMessage subclasses
    - Plain strings (treated as user messages)
    """
    result: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, dict):
            result.append(msg)
        elif isinstance(msg, str):
            result.append({"role": "user", "content": msg})
        elif _LANGCHAIN_AVAILABLE and isinstance(msg, BaseMessage):
            role_map = {
                "human": "user",
                "ai": "assistant",
                "system": "system",
                "tool": "tool",
            }
            role = role_map.get(msg.type, "user")
            result.append({"role": role, "content": msg.content})
        elif hasattr(msg, "content") and hasattr(msg, "type"):
            # Duck-typed LangChain message
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


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get the running event loop or create a new one."""
    try:
        loop = asyncio.get_running_loop()
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


# ── Adapter implementation ────────────────────────────────────────────


if _LANGCHAIN_AVAILABLE:

    class ChatModelMesh(BaseChatModel):
        """LangChain-compatible chat model backed by ModelMesh.

        Routes all requests through ModelMesh's pool routing, gaining
        automatic failover, multi-provider support, cost tracking, and
        observability.

        When ``langchain-core`` is installed, this class extends
        ``BaseChatModel`` for full LangChain ecosystem compatibility,
        including chains, agents, and structured output.

        Args:
            mesh: A configured and initialized ModelMesh instance.
            model_name: The model or pool ID to route requests to.
            temperature: Default temperature for completions.
            max_tokens: Default max tokens for completions.
            streaming: Whether to stream by default.
        """

        mesh: Any  # ModelMesh instance (Any to avoid pydantic issues)
        model_name: str = "text-generation"
        temperature: float = 1.0
        max_tokens: Optional[int] = None
        streaming: bool = False

        class Config:
            arbitrary_types_allowed = True

        @property
        def _llm_type(self) -> str:
            """Return the type identifier for LangChain."""
            return "modelmesh"

        @property
        def _identifying_params(self) -> dict[str, Any]:
            """Return identifying parameters for LangChain."""
            return {
                "model_name": self.model_name,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

        def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
            """Generate a completion from the given messages.

            This is the core method that LangChain calls for
            non-streaming completions.

            Args:
                messages: List of LangChain messages.
                stop: Optional stop sequences.
                run_manager: LangChain callback manager.
                **kwargs: Additional parameters.

            Returns:
                A LangChain ChatResult with generations.
            """
            loop = _get_or_create_event_loop()
            return loop.run_until_complete(
                self._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
            )

        async def _agenerate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[Any] = None,
            **kwargs: Any,
        ) -> ChatResult:
            """Async generation -- the core implementation.

            Args:
                messages: List of LangChain messages.
                stop: Optional stop sequences.
                run_manager: LangChain callback manager.
                **kwargs: Additional parameters.

            Returns:
                A LangChain ChatResult with generations.
            """
            from modelmesh.interfaces.provider import CompletionRequest

            openai_messages = _messages_to_openai_format(messages)

            request = CompletionRequest(
                model=kwargs.get("model", self.model_name),
                messages=openai_messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stream=False,
                stop=stop,
            )

            response = await self.mesh.route(request)

            content = ""
            if response.choices:
                msg = response.choices[0].message
                if msg and msg.content:
                    content = msg.content

            ai_message = AIMessage(
                content=content,
                additional_kwargs={
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                },
            )

            generation = ChatGeneration(message=ai_message)

            return ChatResult(
                generations=[generation],
                llm_output={
                    "model": response.model,
                    "token_usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                },
            )

        def _stream(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> Iterator[AIMessageChunk]:
            """Stream tokens synchronously.

            Yields:
                AIMessageChunk instances as tokens arrive.
            """
            loop = _get_or_create_event_loop()

            async def _collect() -> list[AIMessageChunk]:
                chunks: list[AIMessageChunk] = []
                async for chunk in self._astream_impl(messages, stop=stop, **kwargs):
                    chunks.append(chunk)
                    if run_manager:
                        run_manager.on_llm_new_token(chunk.content)
                return chunks

            chunks = loop.run_until_complete(_collect())
            yield from chunks

        async def _astream_impl(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            **kwargs: Any,
        ) -> AsyncIterator[AIMessageChunk]:
            """Internal async stream implementation.

            Yields:
                AIMessageChunk instances as tokens arrive from the model.
            """
            from modelmesh.interfaces.provider import CompletionRequest

            openai_messages = _messages_to_openai_format(messages)

            request = CompletionRequest(
                model=kwargs.get("model", self.model_name),
                messages=openai_messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stream=True,
                stop=stop,
            )

            async for chunk in self.mesh.route_stream(request):
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield AIMessageChunk(content=delta.content)

        def __repr__(self) -> str:
            return (
                f"ChatModelMesh(model_name={self.model_name!r}, "
                f"temperature={self.temperature})"
            )

else:

    class ChatModelMesh:  # type: ignore[no-redef]
        """LangChain-compatible chat model backed by ModelMesh.

        This is the standalone fallback implementation used when
        ``langchain-core`` is not installed. It provides the same
        ``invoke()`` / ``ainvoke()`` API surface but does not extend
        LangChain's ``BaseChatModel``.

        To get full LangChain compatibility (chains, agents, structured
        output), install ``langchain-core``::

            pip install langchain-core

        Args:
            mesh: A configured and initialized ModelMesh instance.
            model_name: The model or pool ID to route requests to.
            temperature: Default temperature for completions.
            max_tokens: Default max tokens for completions.
            streaming: Whether to stream by default.
        """

        def __init__(
            self,
            mesh: ModelMesh,
            model_name: str = "text-generation",
            temperature: float = 1.0,
            max_tokens: Optional[int] = None,
            streaming: bool = False,
            **kwargs: Any,
        ) -> None:
            self.mesh = mesh
            self.model_name = model_name
            self.temperature = temperature
            self.max_tokens = max_tokens
            self.streaming = streaming

        @property
        def _llm_type(self) -> str:
            return "modelmesh"

        def invoke(
            self,
            input: str | Sequence[Any],
            **kwargs: Any,
        ) -> dict[str, Any]:
            """Invoke the model synchronously.

            Args:
                input: A string prompt or list of messages.
                **kwargs: Override temperature, max_tokens, model, etc.

            Returns:
                A dict with ``content`` and ``additional_kwargs``.
            """
            loop = _get_or_create_event_loop()
            return loop.run_until_complete(self.ainvoke(input, **kwargs))

        async def ainvoke(
            self,
            input: str | Sequence[Any],
            **kwargs: Any,
        ) -> dict[str, Any]:
            """Invoke the model asynchronously.

            Args:
                input: A string prompt or list of messages.
                **kwargs: Override temperature, max_tokens, model, etc.

            Returns:
                A dict with ``content`` and ``additional_kwargs``.
            """
            from modelmesh.interfaces.provider import CompletionRequest

            messages = (
                [{"role": "user", "content": input}]
                if isinstance(input, str)
                else _messages_to_openai_format(input)
            )

            request = CompletionRequest(
                model=kwargs.get("model", self.model_name),
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stream=False,
            )

            response = await self.mesh.route(request)

            content = ""
            if response.choices:
                msg = response.choices[0].message
                if msg and msg.content:
                    content = msg.content

            return {
                "content": content,
                "additional_kwargs": {
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                },
            }

        def __repr__(self) -> str:
            return (
                f"ChatModelMesh(model_name={self.model_name!r}, "
                f"temperature={self.temperature})"
            )
