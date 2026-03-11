"""Framework integrations for ModelMesh.

Provides adapter modules that bridge ModelMesh with popular AI
frameworks like LangChain and LangGraph.

Two LangChain adapters are available:

- :mod:`modelmesh.integrations.langchain` -- Standalone adapter
  that works without LangChain installed.
- :mod:`modelmesh.integrations.langchain_adapter` -- Full LangChain
  ``BaseChatModel`` integration when ``langchain-core`` is installed,
  with automatic fallback to standalone mode.
"""
from __future__ import annotations

from modelmesh.integrations.langchain import ChatModelMesh
from modelmesh.integrations.langchain_adapter import (
    ChatModelMesh as ChatModelMeshAdapter,
)

__all__ = [
    "ChatModelMesh",
    "ChatModelMeshAdapter",
]
