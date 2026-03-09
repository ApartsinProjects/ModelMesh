# CapabilityTree

In-memory representation of the capability hierarchy. The tree provides traversal operations for capability resolution, pool membership calculation, and model lookup. The default tree includes seven top-level categories with pre-defined subcategories and leaf nodes. Users extend the tree with custom categories and leaves through configuration or the runtime API. See [ModelCapabilities.md](../ModelCapabilities.md) for the complete default tree structure and routing rules.

**Depends on:** [ModelCapabilities.md](../ModelCapabilities.md)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class NodeType(Enum):
    """Classification of nodes in the capability hierarchy."""
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    LEAF = "leaf"


@dataclass
class CapabilityNode:
    """A single node in the capability hierarchy tree."""
    path: str
    name: str
    parent: Optional[str]
    children: list[str] = field(default_factory=list)
    is_leaf: bool = False


class CapabilityTree:
    """In-memory capability hierarchy for routing and pool membership.

    Provides traversal operations for capability resolution. Models
    register at leaf nodes; pools target any node and include all
    descendants. The tree is extensible with custom categories,
    subcategories, and leaf nodes.
    """

    def get_node(self, path: str) -> Optional[CapabilityNode]:
        """Return a node by its hierarchy path.

        Args:
            path: Dot-separated path (e.g., "generation.text-generation.chat-completion").

        Returns:
            The CapabilityNode at the given path, or None if not found.
        """
        ...

    def get_ancestors(self, node: str) -> list[CapabilityNode]:
        """Return all ancestor nodes from node to root.

        Args:
            node: Dot-separated path of the starting node.

        Returns:
            Ordered list of ancestors from immediate parent to root.
        """
        ...

    def get_descendants(self, node: str) -> list[CapabilityNode]:
        """Return all descendant nodes (subcategories and leaves).

        Args:
            node: Dot-separated path of the starting node.

        Returns:
            All nodes under the given node in the hierarchy.
        """
        ...

    def get_leaves(self, node: str) -> list[CapabilityNode]:
        """Return only leaf descendants (routable capabilities).

        Args:
            node: Dot-separated path of the starting node.

        Returns:
            Only leaf nodes under the given node. These are the nodes
            where models can register.
        """
        ...

    def add_node(self, parent: str, name: str) -> CapabilityNode:
        """Add a custom node under an existing parent.

        The new node's path is constructed as ``parent.name``. If the
        parent was previously a leaf, it is promoted to a subcategory.

        Args:
            parent: Dot-separated path of the parent node.
            name: Name for the new child node.

        Returns:
            The newly created CapabilityNode.

        Raises:
            KeyError: If the parent node does not exist.
        """
        ...

    def is_ancestor_of(self, ancestor: str, descendant: str) -> bool:
        """Return whether one node is an ancestor of another.

        Args:
            ancestor: Dot-separated path of the potential ancestor.
            descendant: Dot-separated path of the potential descendant.

        Returns:
            True if ancestor is a parent, grandparent, etc. of descendant.
        """
        ...

    def list_categories(self) -> list[CapabilityNode]:
        """Return all top-level category nodes.

        Returns:
            The seven default categories plus any custom top-level nodes.
        """
        ...
```

## TypeScript

```typescript
/** Classification of nodes in the capability hierarchy. */
enum NodeType {
    CATEGORY = "category",
    SUBCATEGORY = "subcategory",
    LEAF = "leaf",
}

/** A single node in the capability hierarchy tree. */
interface CapabilityNode {
    path: string;
    name: string;
    parent: string | null;
    children: string[];
    is_leaf: boolean;
}

/** In-memory capability hierarchy for routing and pool membership. */
class CapabilityTree {
    /** Return a node by its hierarchy path. */
    getNode(path: string): CapabilityNode | null {
        throw new Error("Not implemented");
    }

    /** Return all ancestor nodes from node to root. */
    getAncestors(node: string): CapabilityNode[] {
        throw new Error("Not implemented");
    }

    /** Return all descendant nodes (subcategories and leaves). */
    getDescendants(node: string): CapabilityNode[] {
        throw new Error("Not implemented");
    }

    /** Return only leaf descendants (routable capabilities). */
    getLeaves(node: string): CapabilityNode[] {
        throw new Error("Not implemented");
    }

    /** Add a custom node under an existing parent. */
    addNode(parent: string, name: string): CapabilityNode {
        throw new Error("Not implemented");
    }

    /** Return whether one node is an ancestor of another. */
    isAncestorOf(ancestor: string, descendant: string): boolean {
        throw new Error("Not implemented");
    }

    /** Return all top-level category nodes. */
    listCategories(): CapabilityNode[] {
        throw new Error("Not implemented");
    }
}
```

---

## Default Categories

The default capability tree ships with seven top-level categories. Each category contains subcategories and leaf nodes where models register. See [ModelCapabilities.md](../ModelCapabilities.md) for the full hierarchy.

| Category | Description | Example Leaves |
| --- | --- | --- |
| `generation` | Produces new content from prompts | chat-completion, text-to-image, text-to-speech |
| `understanding` | Analyzes and interprets input content | summarization, ocr, speech-to-text |
| `transformation` | Converts content between formats or styles | translation, background-removal, voice-cloning |
| `representation` | Encodes content into structured data | text-embeddings, image-embeddings |
| `retrieval` | Finds and retrieves information | semantic-search, grounded-generation, reranking |
| `interaction` | Enables multi-step and tool-using behavior | tool-calling, agent-execution |
| `evaluation` | Assesses content quality and safety | content-moderation, factuality-checking |
