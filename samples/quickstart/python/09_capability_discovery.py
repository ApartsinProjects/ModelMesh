"""
09 - Capability Discovery
==========================

Shows how to explore available capabilities without memorizing
full dotted paths. The capabilities API lets you list, resolve,
search, and visualize the capability hierarchy.

No API keys needed -- this is pure introspection.
"""

from __future__ import annotations

import json

import modelmesh


def main():
    # 1. List all registered capability aliases
    print("=== All Capabilities ===")
    caps = modelmesh.capabilities.list_all()
    for cap in caps:
        full_path = modelmesh.capabilities.resolve(cap)
        print(f"  {cap:25s} -> {full_path}")

    # 2. Resolve alias to full dotted path
    print("\n=== Resolve Alias ===")
    alias = "chat-completion"
    path = modelmesh.capabilities.resolve(alias)
    print(f"  '{alias}' -> '{path}'")

    # Already-dotted paths pass through unchanged
    print(f"  '{path}' -> '{modelmesh.capabilities.resolve(path)}'")

    # Unknown aliases return unchanged
    unknown = "my-custom-capability"
    print(f"  '{unknown}' -> '{modelmesh.capabilities.resolve(unknown)}'")

    # 3. Search by keyword
    print("\n=== Search ===")
    for keyword in ["text", "audio", "image"]:
        matches = modelmesh.capabilities.search(keyword)
        print(f"  '{keyword}': {matches}")

    # 4. Full hierarchy tree
    print("\n=== Capability Tree ===")
    tree = modelmesh.capabilities.tree()
    print(json.dumps(tree, indent=2))


if __name__ == "__main__":
    main()
