"""Synchronous execution utilities for async coroutines.

Provides _run_sync() to bridge async internals with the synchronous public
API. Handles Jupyter/IPython event loop conflicts by running coroutines in
a separate thread when a loop is already active.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

__all__ = ["_run_sync"]


def _run_sync(coro):
    """Run an async coroutine synchronously.

    If no event loop is running, uses ``asyncio.run()``. If a loop is
    already active (e.g. inside Jupyter or an async framework), spins up
    a single-thread executor to avoid ``RuntimeError: This event loop is
    already running``.

    Args:
        coro: An awaitable coroutine.

    Returns:
        The coroutine's return value.

    Raises:
        Any exception raised by the coroutine.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run()
        return asyncio.run(coro)

    # A loop is already running (Jupyter, nested async, etc.).
    # Run in a separate thread with its own event loop.
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()
