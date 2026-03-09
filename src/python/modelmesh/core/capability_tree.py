"""Hierarchical capability tree for routing.

The capability tree organizes AI capabilities into a hierarchy where parent
nodes are categories and leaf nodes are concrete, routable capabilities.
For example: ``generation.text-generation.chat-completion``.

Pool targeting works at any level: requesting ``generation`` matches all
generation capabilities; requesting ``chat-completion`` matches only that
leaf.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = ["CapabilityTree", "CapabilityNode"]


@dataclass
class CapabilityNode:
    """A single node in the capability hierarchy.

    Each node has a name (its segment), an optional parent reference,
    and zero or more children. Leaf nodes represent concrete, routable
    capabilities.
    """

    name: str
    full_path: str
    parent: Optional[CapabilityNode] = field(default=None, repr=False)
    children: dict[str, CapabilityNode] = field(default_factory=dict)

    @property
    def is_leaf(self) -> bool:
        """True if this node has no children."""
        return len(self.children) == 0

    def get_all_leaves(self) -> list[str]:
        """Return full paths of all leaf descendants (including self if leaf)."""
        if self.is_leaf:
            return [self.full_path]
        leaves: list[str] = []
        for child in self.children.values():
            leaves.extend(child.get_all_leaves())
        return leaves


class CapabilityTree:
    """Hierarchical capability tree for routing.

    Manages a tree of capability nodes. Capabilities are registered as
    dot-notated paths (e.g. ``"generation.text-generation.chat-completion"``)
    and can be resolved to all matching leaf capabilities at any level.

    Example::

        tree = CapabilityTree()
        tree.register("generation.text-generation.chat-completion")
        tree.register("generation.text-generation.text-to-image")

        # Resolve at leaf level — returns only the exact match
        tree.resolve("generation.text-generation.chat-completion")
        # => ["generation.text-generation.chat-completion"]

        # Resolve at category level — returns all descendants
        tree.resolve("generation")
        # => ["generation.text-generation.chat-completion",
        #     "generation.text-generation.text-to-image"]
    """

    def __init__(self) -> None:
        self._roots: dict[str, CapabilityNode] = {}

    def register(self, path: str) -> None:
        """Register a capability path.

        Creates all intermediate nodes as needed. If the path is already
        registered, this is a no-op.

        Args:
            path: Dot-notated capability path
                  (e.g. ``"generation.text-generation.chat-completion"``).

        Raises:
            ValueError: If *path* is empty.
        """
        if not path:
            raise ValueError("Capability path must not be empty")

        segments = path.split(".")
        root_name = segments[0]

        if root_name not in self._roots:
            self._roots[root_name] = CapabilityNode(
                name=root_name, full_path=root_name
            )

        current = self._roots[root_name]
        for i, segment in enumerate(segments[1:], start=1):
            if segment not in current.children:
                child_path = ".".join(segments[: i + 1])
                child = CapabilityNode(
                    name=segment, full_path=child_path, parent=current
                )
                current.children[segment] = child
            current = current.children[segment]

    def resolve(self, path: str) -> list[str]:
        """Resolve a path to all matching leaf capabilities.

        If *path* points to a leaf node, returns ``[path]``. If it points
        to a category node, returns the full paths of all leaf descendants.
        If the path is not registered, returns an empty list.

        Args:
            path: Dot-notated capability path to resolve.

        Returns:
            List of full leaf-capability paths.
        """
        node = self._find_node(path)
        if node is None:
            return []
        return node.get_all_leaves()

    def contains(self, path: str) -> bool:
        """Check whether a capability path is registered."""
        return self._find_node(path) is not None

    def all_paths(self) -> list[str]:
        """Return all registered paths (both internal and leaf nodes)."""
        paths: list[str] = []
        for root in self._roots.values():
            self._collect_paths(root, paths)
        return paths

    def all_leaves(self) -> list[str]:
        """Return full paths of all leaf nodes across the entire tree."""
        leaves: list[str] = []
        for root in self._roots.values():
            leaves.extend(root.get_all_leaves())
        return leaves

    def _find_node(self, path: str) -> Optional[CapabilityNode]:
        """Traverse the tree to find the node at *path*."""
        segments = path.split(".")
        root_name = segments[0]
        if root_name not in self._roots:
            return None

        current = self._roots[root_name]
        for segment in segments[1:]:
            if segment not in current.children:
                return None
            current = current.children[segment]
        return current

    def _collect_paths(
        self, node: CapabilityNode, out: list[str]
    ) -> None:
        """Recursively collect all paths from *node* downward."""
        out.append(node.full_path)
        for child in node.children.values():
            self._collect_paths(child, out)
