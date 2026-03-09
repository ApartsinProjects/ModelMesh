"""ModelMesh HTTP Proxy -- OpenAI-compatible API server.

Exposes ModelMesh routing as a standard OpenAI API HTTP server so that
any tool, SDK, or application expecting the OpenAI REST API can route
through ModelMesh without code changes.

Quick start::

    from modelmesh.proxy.server import ProxyServer

    server = ProxyServer(config="modelmesh.yaml", port=8080)
    server.start()
"""
from __future__ import annotations

from modelmesh.proxy.server import ProxyServer

__all__ = ["ProxyServer"]
