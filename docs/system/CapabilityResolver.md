# CapabilityResolver

Maps a capability name to matching capability pools using the capability hierarchy. Traverses the `CapabilityTree` to find pools targeting the requested node or any of its ancestors. Results are ordered by specificity so that leaf-level pools (most specific) appear first.

**Depends on:** [CapabilityTree](CapabilityTree.md), [CapabilityPool](CapabilityPool.md).

---

## Python

```python
from __future__ import annotations


class CapabilityResolver:
    """Pipeline stage that resolves a capability name to matching pools."""

    _capability_tree: CapabilityTree
    _pools: list[CapabilityPool]

    def __init__(
        self,
        capability_tree: CapabilityTree,
        pools: list[CapabilityPool],
    ) -> None:
        self._capability_tree = capability_tree
        self._pools = pools

    def resolve(self, capability: str) -> list[CapabilityPool]:
        """Return all pools matching the capability, ordered by specificity
        (leaf pools first).

        Args:
            capability: A capability name or hierarchy path
                        (e.g., 'chat-completion' or
                        'generation.chat-completion').

        Returns:
            List of CapabilityPool instances matching the capability,
            ordered from most specific to least specific.

        Raises:
            CapabilityNotFoundError: If the capability does not exist in the
                                     hierarchy.
        """
        ...

    def get_matching_pools(self, node: str) -> list[CapabilityPool]:
        """Return pools registered at a specific hierarchy node.

        Args:
            node: Hierarchy node path (e.g., 'generation').

        Returns:
            List of CapabilityPool instances targeting the given node.
        """
        ...
```

---

## TypeScript

```typescript
class CapabilityResolver {
  private capabilityTree: CapabilityTree;
  private pools: CapabilityPool[];

  constructor(capabilityTree: CapabilityTree, pools: CapabilityPool[]) {
    this.capabilityTree = capabilityTree;
    this.pools = pools;
  }

  /** Return all pools matching the capability, ordered by specificity
   *  (leaf pools first). */
  resolve(capability: string): CapabilityPool[];

  /** Return pools registered at a specific hierarchy node. */
  getMatchingPools(node: string): CapabilityPool[];
}
```
