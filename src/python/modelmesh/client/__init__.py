"""Client layer -- OpenAI SDK-compatible interface.

Re-exports the MeshClient class.
"""
from __future__ import annotations

from modelmesh.client.mesh_client import MeshClient

__all__ = [
    "MeshClient",
]
