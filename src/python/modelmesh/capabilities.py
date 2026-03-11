"""Capability discovery and introspection API.

Exposes the internal capability alias registry and tree through
a clean namespace so users don't have to memorize full dotted paths.

Usage::

    import modelmesh

    # List all known capability aliases
    caps = modelmesh.capabilities.list_all()

    # Resolve a short name to full path
    path = modelmesh.capabilities.resolve("chat")

    # Search by keyword
    matches = modelmesh.capabilities.search("text")
"""
from __future__ import annotations


_ALIASES: dict[str, str] = {
    "chat-completion": "generation.text-generation.chat-completion",
    "text-generation": "generation.text-generation",
    "text-embeddings": "representation.embeddings.text-embeddings",
    "text-to-speech": "generation.audio.text-to-speech",
    "speech-to-text": "understanding.audio.speech-to-text",
    "text-to-image": "generation.image.text-to-image",
    "image-to-text": "representation.image.image-to-text",
    "code-generation": "generation.text-generation.code-generation",
}


def _get_aliases() -> dict[str, str]:
    """Return the capability alias registry."""
    return dict(_ALIASES)


def list_all() -> list[str]:
    """Return all registered capability alias names.

    Returns:
        Sorted list of short alias names (e.g. ``"chat-completion"``,
        ``"text-embeddings"``).
    """
    return sorted(_get_aliases().keys())


def resolve(name: str) -> str:
    """Resolve a capability alias to its full dotted path.

    If *name* is already a dotted path (contains ``"."``), it is
    returned as-is. Otherwise, the alias registry is consulted.
    Unknown aliases are returned unchanged.

    Args:
        name: Short alias or full dotted path.

    Returns:
        Full capability path string.
    """
    if "." in name:
        return name
    aliases = _get_aliases()
    return aliases.get(name, name)


def search(keyword: str) -> list[str]:
    """Search capability aliases by keyword.

    Performs a case-insensitive substring match against both the
    alias name and its full path.

    Args:
        keyword: Search term.

    Returns:
        List of matching alias names.
    """
    keyword_lower = keyword.lower()
    aliases = _get_aliases()
    matches = []
    for alias, path in aliases.items():
        if keyword_lower in alias.lower() or keyword_lower in path.lower():
            matches.append(alias)
    return sorted(matches)


def tree() -> dict:
    """Build a hierarchical tree from all registered capability paths.

    Returns:
        Nested dict representing the capability hierarchy. Leaf
        nodes have an empty dict as their value.

    Example::

        >>> tree()
        {
            'generation': {
                'text-generation': {
                    'chat-completion': {},
                    'code-generation': {},
                },
                'audio': {'text-to-speech': {}},
                'image': {'text-to-image': {}},
            },
            ...
        }
    """
    aliases = _get_aliases()
    result: dict = {}
    for path in aliases.values():
        parts = path.split(".")
        node = result
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]
    return result


__all__ = [
    "list_all",
    "resolve",
    "search",
    "tree",
]
