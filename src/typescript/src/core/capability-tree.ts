/**
 * Hierarchical capability tree for routing.
 *
 * The capability tree organizes AI capabilities into a hierarchy where parent
 * nodes are categories and leaf nodes are concrete, routable capabilities.
 * For example: "generation.text-generation.chat-completion".
 *
 * Pool targeting works at any level: requesting "generation" matches all
 * generation capabilities; requesting "chat-completion" matches only that
 * leaf.
 */

/**
 * A single node in the capability hierarchy.
 *
 * Each node has a name (its segment), an optional parent reference,
 * and zero or more children. Leaf nodes represent concrete, routable
 * capabilities.
 */
export class CapabilityNode {
  readonly name: string;
  readonly fullPath: string;
  readonly parent: CapabilityNode | null;
  readonly children: Map<string, CapabilityNode>;

  constructor(
    name: string,
    fullPath: string,
    parent: CapabilityNode | null = null
  ) {
    this.name = name;
    this.fullPath = fullPath;
    this.parent = parent;
    this.children = new Map();
  }

  /** True if this node has no children. */
  get isLeaf(): boolean {
    return this.children.size === 0;
  }

  /** Return full paths of all leaf descendants (including self if leaf). */
  getAllLeaves(): string[] {
    if (this.isLeaf) {
      return [this.fullPath];
    }
    const leaves: string[] = [];
    for (const child of this.children.values()) {
      leaves.push(...child.getAllLeaves());
    }
    return leaves;
  }
}

/**
 * Hierarchical capability tree for routing.
 *
 * Manages a tree of capability nodes. Capabilities are registered as
 * dot-notated paths (e.g. "generation.text-generation.chat-completion")
 * and can be resolved to all matching leaf capabilities at any level.
 *
 * Example:
 *
 *   const tree = new CapabilityTree();
 *   tree.register("generation.text-generation.chat-completion");
 *   tree.register("generation.text-generation.text-to-image");
 *
 *   // Resolve at leaf level -- returns only the exact match
 *   tree.resolve("generation.text-generation.chat-completion");
 *   // => ["generation.text-generation.chat-completion"]
 *
 *   // Resolve at category level -- returns all descendants
 *   tree.resolve("generation");
 *   // => ["generation.text-generation.chat-completion",
 *   //     "generation.text-generation.text-to-image"]
 */
export class CapabilityTree {
  private readonly _roots: Map<string, CapabilityNode> = new Map();

  /**
   * Register a capability path.
   *
   * Creates all intermediate nodes as needed. If the path is already
   * registered, this is a no-op.
   *
   * @param path - Dot-notated capability path
   *               (e.g. "generation.text-generation.chat-completion").
   * @throws Error if path is empty.
   */
  register(path: string): void {
    if (!path) {
      throw new Error("Capability path must not be empty");
    }

    const segments = path.split(".");
    const rootName = segments[0];

    if (!this._roots.has(rootName)) {
      this._roots.set(rootName, new CapabilityNode(rootName, rootName));
    }

    let current = this._roots.get(rootName)!;
    for (let i = 1; i < segments.length; i++) {
      const segment = segments[i];
      if (!current.children.has(segment)) {
        const childPath = segments.slice(0, i + 1).join(".");
        const child = new CapabilityNode(segment, childPath, current);
        current.children.set(segment, child);
      }
      current = current.children.get(segment)!;
    }
  }

  /**
   * Resolve a path to all matching leaf capabilities.
   *
   * If path points to a leaf node, returns [path]. If it points
   * to a category node, returns the full paths of all leaf descendants.
   * If the path is not registered, returns an empty list.
   *
   * @param path - Dot-notated capability path to resolve.
   * @returns List of full leaf-capability paths.
   */
  resolve(path: string): string[] {
    const node = this._findNode(path);
    if (node === null) {
      return [];
    }
    return node.getAllLeaves();
  }

  /** Check whether a capability path is registered. */
  contains(path: string): boolean {
    return this._findNode(path) !== null;
  }

  /** Return all registered paths (both internal and leaf nodes). */
  allPaths(): string[] {
    const paths: string[] = [];
    for (const root of this._roots.values()) {
      this._collectPaths(root, paths);
    }
    return paths;
  }

  /** Return full paths of all leaf nodes across the entire tree. */
  allLeaves(): string[] {
    const leaves: string[] = [];
    for (const root of this._roots.values()) {
      leaves.push(...root.getAllLeaves());
    }
    return leaves;
  }

  /** Traverse the tree to find the node at path. */
  private _findNode(path: string): CapabilityNode | null {
    const segments = path.split(".");
    const rootName = segments[0];
    if (!this._roots.has(rootName)) {
      return null;
    }

    let current = this._roots.get(rootName)!;
    for (let i = 1; i < segments.length; i++) {
      const segment = segments[i];
      if (!current.children.has(segment)) {
        return null;
      }
      current = current.children.get(segment)!;
    }
    return current;
  }

  /** Recursively collect all paths from node downward. */
  private _collectPaths(node: CapabilityNode, out: string[]): void {
    out.push(node.fullPath);
    for (const child of node.children.values()) {
      this._collectPaths(child, out);
    }
  }
}
