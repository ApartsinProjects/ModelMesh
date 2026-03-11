/**
 * 09 - Capability Discovery
 * ==========================
 *
 * Shows how to explore available capabilities without memorizing
 * full dotted paths. The capabilities API lets you list, resolve,
 * search, and visualize the capability hierarchy.
 *
 * No API keys needed — this is pure introspection.
 */

import * as capabilities from '@nistrapa/modelmesh-core/capabilities';

function main(): void {
  // 1. List all registered capability aliases
  console.log('=== All Capabilities ===');
  const caps = capabilities.listAll();
  for (const cap of caps) {
    const fullPath = capabilities.resolve(cap);
    console.log(`  ${cap.padEnd(25)} → ${fullPath}`);
  }

  // 2. Resolve alias to full dotted path
  console.log('\n=== Resolve Alias ===');
  const alias = 'chat-completion';
  const path = capabilities.resolve(alias);
  console.log(`  '${alias}' → '${path}'`);

  // Already-dotted paths pass through unchanged
  console.log(`  '${path}' → '${capabilities.resolve(path)}'`);

  // Unknown aliases return unchanged
  const unknown = 'my-custom-capability';
  console.log(`  '${unknown}' → '${capabilities.resolve(unknown)}'`);

  // 3. Search by keyword
  console.log('\n=== Search ===');
  for (const keyword of ['text', 'audio', 'image']) {
    const matches = capabilities.search(keyword);
    console.log(`  '${keyword}': [${matches.join(', ')}]`);
  }

  // 4. Full hierarchy tree
  console.log('\n=== Capability Tree ===');
  const tree = capabilities.tree();
  console.log(JSON.stringify(tree, null, 2));
}

main();
