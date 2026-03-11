"""Per-request timeout mixin for provider connectors.

Wraps async calls with ``asyncio.wait_for`` to enforce configurable
per-request timeouts. When a timeout fires, a ``RequestTimeoutError``
is raised and the underlying provider call is cancelled.

Usage::

    class MyProvider(TimeoutMixin, ProviderConnector):
        def __init__(self):
            super().__init__()
            self.configure_timeout(default=30.0, streaming=120.0)

        async def complete(self, request):
            return await self.with_timeout(self._do_complete(request))

        async def stream(self, request):
            async for chunk in self.with_stream_timeout(
                self._do_stream(request)
            ):
                yield chunk
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional, TypeVar

__all__ = [
    "TimeoutMixin",
    "RequestTimeoutError",
    "TimeoutConfig",
]

T = TypeVar("T")


class RequestTimeoutError(asyncio.TimeoutError):
    """Raised when a provider request exceeds the configured timeout.

    Attributes:
        timeout: The timeout value in seconds that was exceeded.
        operation: Description of the operation that timed out.
    """

    def __init__(self, timeout: float, operation: str = "request") -> None:
        self.timeout = timeout
        self.operation = operation
        super().__init__(
            f"{operation} timed out after {timeout:.1f}s"
        )


@dataclass
class TimeoutConfig:
    """Timeout configuration.

    Attributes:
        default: Timeout for non-streaming requests (seconds).
        streaming: Timeout for the *first chunk* of a streaming response.
        streaming_total: Overall timeout for the entire stream.
        connect: Connection establishment timeout (seconds).
    """

    default: float = 30.0
    streaming: float = 60.0
    streaming_total: float = 300.0
    connect: float = 10.0


class TimeoutMixin:
    """Mixin providing per-request timeout enforcement.

    All timeouts are in seconds. A value of ``0`` or ``None`` disables
    the timeout for that operation.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._timeout_config = TimeoutConfig()

    def configure_timeout(
        self,
        default: float = 30.0,
        streaming: float = 60.0,
        streaming_total: float = 300.0,
        connect: float = 10.0,
    ) -> None:
        """Configure timeout values."""
        self._timeout_config = TimeoutConfig(
            default=default,
            streaming=streaming,
            streaming_total=streaming_total,
            connect=connect,
        )

    @property
    def timeout_config(self) -> TimeoutConfig:
        """Current timeout configuration."""
        return self._timeout_config

    async def with_timeout(
        self,
        coro,
        timeout: Optional[float] = None,
        operation: str = "request",
    ):
        """Execute a coroutine with a timeout.

        Args:
            coro: The awaitable to execute.
            timeout: Override timeout (uses ``default`` if None).
            operation: Description for error messages.

        Returns:
            The result of the coroutine.

        Raises:
            RequestTimeoutError: If the timeout is exceeded.
        """
        t = timeout if timeout is not None else self._timeout_config.default
        if not t or t <= 0:
            return await coro

        try:
            return await asyncio.wait_for(coro, timeout=t)
        except asyncio.TimeoutError:
            raise RequestTimeoutError(t, operation)

    async def with_stream_timeout(
        self,
        aiter: AsyncIterator[T],
        first_chunk_timeout: Optional[float] = None,
        total_timeout: Optional[float] = None,
    ) -> AsyncIterator[T]:
        """Wrap a streaming async iterator with timeout enforcement.

        Args:
            aiter: The async iterator to wrap.
            first_chunk_timeout: Max wait for the first chunk (uses
                ``streaming`` config if None).
            total_timeout: Max total stream duration (uses
                ``streaming_total`` config if None).

        Yields:
            Items from the underlying async iterator.

        Raises:
            RequestTimeoutError: If either timeout is exceeded.
        """
        first_t = (
            first_chunk_timeout
            if first_chunk_timeout is not None
            else self._timeout_config.streaming
        )
        total_t = (
            total_timeout
            if total_timeout is not None
            else self._timeout_config.streaming_total
        )

        start = asyncio.get_event_loop().time()
        first_chunk = True
        ait = aiter.__aiter__()

        while True:
            # Calculate remaining time
            if total_t and total_t > 0:
                elapsed = asyncio.get_event_loop().time() - start
                remaining = total_t - elapsed
                if remaining <= 0:
                    raise RequestTimeoutError(total_t, "stream_total")
            else:
                remaining = None

            # Use first-chunk timeout for the initial chunk
            if first_chunk and first_t and first_t > 0:
                t = first_t
                if remaining is not None:
                    t = min(t, remaining)
            else:
                t = remaining

            try:
                if t and t > 0:
                    chunk = await asyncio.wait_for(
                        ait.__anext__(), timeout=t
                    )
                else:
                    chunk = await ait.__anext__()
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                op = "stream_first_chunk" if first_chunk else "stream_total"
                timeout_val = first_t if first_chunk else total_t
                raise RequestTimeoutError(timeout_val or 0, op)

            first_chunk = False
            yield chunk
