"""Streaming checkpoint mixin for resilient streaming.

Buffers streamed tokens and tracks stream progress so that a failed
stream can be resumed from the last checkpoint. Useful for long
streaming completions over unreliable connections.

Usage::

    class MyProvider(StreamingCheckpointMixin, ProviderConnector):
        async def stream(self, request):
            checkpoint = self.create_checkpoint(request)
            async for chunk in self._do_stream(request):
                checkpoint.record(chunk)
                yield chunk
            checkpoint.finalize()
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "StreamingCheckpointMixin",
    "StreamCheckpoint",
    "CheckpointConfig",
]


@dataclass
class CheckpointConfig:
    """Configuration for streaming checkpoints.

    Attributes:
        max_buffer_tokens: Maximum tokens to buffer per stream.
        checkpoint_interval: How often (in tokens) to snapshot.
        max_checkpoints: Maximum number of active checkpoints to retain.
    """

    max_buffer_tokens: int = 10000
    checkpoint_interval: int = 100
    max_checkpoints: int = 50


@dataclass
class StreamCheckpoint:
    """Tracks progress for a single streaming response.

    Attributes:
        request_id: Unique identifier for the originating request.
        model_id: Model that generated the stream.
        tokens_received: Total tokens received so far.
        content_buffer: Accumulated text content.
        started_at: When the stream began (monotonic).
        last_chunk_at: When the last chunk arrived.
        is_complete: Whether the stream finished normally.
        finish_reason: The finish reason from the final chunk.
    """

    request_id: str = ""
    model_id: str = ""
    tokens_received: int = 0
    content_buffer: str = ""
    started_at: float = 0.0
    last_chunk_at: float = 0.0
    is_complete: bool = False
    finish_reason: Optional[str] = None

    def record(self, content: str, token_count: int = 0) -> None:
        """Record a streaming chunk.

        Args:
            content: The text content of the chunk.
            token_count: Number of tokens in the chunk (estimated as
                word count if 0).
        """
        self.content_buffer += content
        self.tokens_received += token_count or max(1, len(content.split()))
        self.last_chunk_at = time.monotonic()

    def finalize(self, finish_reason: str = "stop") -> None:
        """Mark the stream as complete."""
        self.is_complete = True
        self.finish_reason = finish_reason
        self.last_chunk_at = time.monotonic()

    @property
    def duration(self) -> float:
        """Elapsed stream duration in seconds."""
        end = self.last_chunk_at or time.monotonic()
        return end - self.started_at if self.started_at else 0.0

    @property
    def tokens_per_second(self) -> float:
        """Average tokens per second throughput."""
        d = self.duration
        return self.tokens_received / d if d > 0 else 0.0

    def to_dict(self) -> dict:
        """Serialize checkpoint state to a dict."""
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "tokens_received": self.tokens_received,
            "content_length": len(self.content_buffer),
            "duration": round(self.duration, 3),
            "tokens_per_second": round(self.tokens_per_second, 1),
            "is_complete": self.is_complete,
            "finish_reason": self.finish_reason,
        }


class StreamingCheckpointMixin:
    """Mixin providing streaming checkpoint management.

    Maintains a bounded collection of active checkpoints keyed by
    request ID. Thread-safe.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cp_config = CheckpointConfig()
        self._checkpoints: dict[str, StreamCheckpoint] = {}
        self._cp_lock = threading.Lock()

    def configure_checkpoints(
        self,
        max_buffer_tokens: int = 10000,
        checkpoint_interval: int = 100,
        max_checkpoints: int = 50,
    ) -> None:
        """Configure streaming checkpoint parameters."""
        self._cp_config = CheckpointConfig(
            max_buffer_tokens=max_buffer_tokens,
            checkpoint_interval=checkpoint_interval,
            max_checkpoints=max_checkpoints,
        )

    def create_checkpoint(
        self,
        request_id: str,
        model_id: str = "",
    ) -> StreamCheckpoint:
        """Create and register a new streaming checkpoint.

        Args:
            request_id: Unique request identifier.
            model_id: The model generating the stream.

        Returns:
            A fresh StreamCheckpoint instance.
        """
        cp = StreamCheckpoint(
            request_id=request_id,
            model_id=model_id,
            started_at=time.monotonic(),
        )
        with self._cp_lock:
            # Evict oldest completed checkpoints if at capacity
            if len(self._checkpoints) >= self._cp_config.max_checkpoints:
                self._evict_completed()
            self._checkpoints[request_id] = cp
        return cp

    def get_checkpoint(self, request_id: str) -> Optional[StreamCheckpoint]:
        """Retrieve an active checkpoint by request ID."""
        with self._cp_lock:
            return self._checkpoints.get(request_id)

    def remove_checkpoint(self, request_id: str) -> None:
        """Remove a checkpoint after the stream completes."""
        with self._cp_lock:
            self._checkpoints.pop(request_id, None)

    def active_checkpoints(self) -> list[StreamCheckpoint]:
        """Return all active (incomplete) checkpoints."""
        with self._cp_lock:
            return [
                cp for cp in self._checkpoints.values()
                if not cp.is_complete
            ]

    def checkpoint_stats(self) -> dict:
        """Return summary statistics for all checkpoints."""
        with self._cp_lock:
            total = len(self._checkpoints)
            active = sum(
                1 for cp in self._checkpoints.values() if not cp.is_complete
            )
            return {
                "total": total,
                "active": active,
                "completed": total - active,
                "max_checkpoints": self._cp_config.max_checkpoints,
            }

    def _evict_completed(self) -> None:
        """Remove oldest completed checkpoints. Must hold lock."""
        completed = [
            (rid, cp)
            for rid, cp in self._checkpoints.items()
            if cp.is_complete
        ]
        # Sort by completion time (oldest first)
        completed.sort(key=lambda x: x[1].last_chunk_at)
        # Remove half of completed entries
        to_remove = max(1, len(completed) // 2)
        for rid, _ in completed[:to_remove]:
            del self._checkpoints[rid]
