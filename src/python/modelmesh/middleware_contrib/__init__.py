"""Contributed middleware for ModelMesh.

Ready-to-use middleware implementations for common cross-cutting
concerns like request correlation, distributed tracing, and
observability.

Usage::

    from modelmesh.middleware_contrib import CorrelationIdMiddleware
    from modelmesh.middleware_contrib import OpenTelemetryMiddleware

    client = modelmesh.create(
        "chat-completion",
        middleware=[
            CorrelationIdMiddleware(),
            OpenTelemetryMiddleware(),
        ],
    )
"""
from __future__ import annotations

from modelmesh.middleware_contrib.correlation import CorrelationIdMiddleware
from modelmesh.middleware_contrib.opentelemetry import OpenTelemetryMiddleware

__all__ = [
    "CorrelationIdMiddleware",
    "OpenTelemetryMiddleware",
]
