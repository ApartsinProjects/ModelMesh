/**
 * Capability discovery and introspection API.
 *
 * Exposes the internal capability alias registry through a clean
 * namespace so users don't have to memorize full dotted paths.
 *
 * @example
 * ```ts
 * import * as capabilities from '@modelmesh/core/capabilities';
 *
 * const caps = capabilities.listAll();
 * const path = capabilities.resolve('chat-completion');
 * const matches = capabilities.search('text');
 * const tree = capabilities.tree();
 * ```
 */

// Import the alias map — lazily to avoid circular deps in some bundlers
function getAliases(): Record<string, string> {
  // Inline the aliases to avoid circular dependency with index.ts
  return {
    'chat-completion': 'generation.text-generation.chat-completion',
    'text-generation': 'generation.text-generation',
    'text-embeddings': 'representation.embeddings.text-embeddings',
    'text-to-speech': 'generation.audio.text-to-speech',
    'speech-to-text': 'understanding.audio.speech-to-text',
    'text-to-image': 'generation.image.text-to-image',
    'image-to-text': 'representation.image.image-to-text',
    'code-generation': 'generation.text-generation.code-generation',
  };
}

/**
 * Return all registered capability alias names.
 *
 * @returns Sorted list of short alias names.
 */
export function listAll(): string[] {
  return Object.keys(getAliases()).sort();
}

/**
 * Resolve a capability alias to its full dotted path.
 *
 * If `name` is already a dotted path (contains "."), it is
 * returned as-is. Otherwise, the alias registry is consulted.
 * Unknown aliases are returned unchanged.
 *
 * @param name - Short alias or full dotted path.
 * @returns Full capability path string.
 */
export function resolve(name: string): string {
  if (name.includes('.')) return name;
  const aliases = getAliases();
  return aliases[name] ?? name;
}

/**
 * Search capability aliases by keyword.
 *
 * Performs a case-insensitive substring match against both the
 * alias name and its full path.
 *
 * @param keyword - Search term.
 * @returns List of matching alias names.
 */
export function search(keyword: string): string[] {
  const kw = keyword.toLowerCase();
  const aliases = getAliases();
  const matches: string[] = [];
  for (const [alias, path] of Object.entries(aliases)) {
    if (alias.toLowerCase().includes(kw) || path.toLowerCase().includes(kw)) {
      matches.push(alias);
    }
  }
  return matches.sort();
}

/**
 * Build a hierarchical tree from all registered capability paths.
 *
 * @returns Nested object representing the capability hierarchy.
 *     Leaf nodes have an empty object as their value.
 */
export function tree(): Record<string, unknown> {
  const aliases = getAliases();
  const result: Record<string, unknown> = {};
  for (const path of Object.values(aliases)) {
    const parts = path.split('.');
    let node = result;
    for (const part of parts) {
      if (!(part in node)) {
        (node as Record<string, unknown>)[part] = {};
      }
      node = (node as Record<string, unknown>)[part] as Record<string, unknown>;
    }
  }
  return result;
}
