/**
 * Tests for CapabilityTree.
 */
import { CapabilityTree } from '@/core/capability-tree';

describe('CapabilityTree', () => {
  let tree: CapabilityTree;

  beforeEach(() => {
    tree = new CapabilityTree();
  });

  it('should register and contain a path', () => {
    tree.register('generation.text-generation.chat-completion');
    expect(tree.contains('generation.text-generation.chat-completion')).toBe(true);
  });

  it('should register parent nodes automatically', () => {
    tree.register('generation.text-generation.chat-completion');
    expect(tree.contains('generation')).toBe(true);
    expect(tree.contains('generation.text-generation')).toBe(true);
  });

  it('should resolve a parent to all children', () => {
    tree.register('generation.text-generation.chat-completion');
    tree.register('generation.text-generation.code-generation');
    const resolved = tree.resolve('generation.text-generation');
    expect(resolved).toContain('generation.text-generation.chat-completion');
    expect(resolved).toContain('generation.text-generation.code-generation');
  });

  it('should resolve a leaf to itself', () => {
    tree.register('generation.text-generation.chat-completion');
    const resolved = tree.resolve('generation.text-generation.chat-completion');
    expect(resolved).toEqual(['generation.text-generation.chat-completion']);
  });

  it('should return empty for unknown paths', () => {
    const resolved = tree.resolve('unknown.path');
    expect(resolved).toEqual([]);
  });

  it('should return all registered paths', () => {
    tree.register('generation.text-generation.chat-completion');
    tree.register('representation.embeddings.text-embeddings');
    const paths = tree.allPaths();
    expect(paths).toContain('generation');
    expect(paths).toContain('generation.text-generation');
    expect(paths).toContain('generation.text-generation.chat-completion');
    expect(paths).toContain('representation');
    expect(paths).toContain('representation.embeddings');
    expect(paths).toContain('representation.embeddings.text-embeddings');
  });

  it('should return only leaves', () => {
    tree.register('generation.text-generation.chat-completion');
    tree.register('generation.text-generation.code-generation');
    tree.register('representation.embeddings.text-embeddings');
    const leaves = tree.allLeaves();
    expect(leaves).toContain('generation.text-generation.chat-completion');
    expect(leaves).toContain('generation.text-generation.code-generation');
    expect(leaves).toContain('representation.embeddings.text-embeddings');
    expect(leaves).not.toContain('generation');
    expect(leaves).not.toContain('generation.text-generation');
  });

  it('should handle duplicate registrations idempotently', () => {
    tree.register('generation.text-generation.chat-completion');
    tree.register('generation.text-generation.chat-completion');
    const leaves = tree.allLeaves();
    const chatLeaves = leaves.filter((l: string) => l === 'generation.text-generation.chat-completion');
    expect(chatLeaves.length).toBe(1);
  });

  it('should resolve root to all capabilities', () => {
    tree.register('generation.text-generation.chat-completion');
    tree.register('generation.image.text-to-image');
    const resolved = tree.resolve('generation');
    expect(resolved).toContain('generation.text-generation.chat-completion');
    expect(resolved).toContain('generation.image.text-to-image');
  });

  it('should handle single-segment paths', () => {
    tree.register('chat');
    expect(tree.contains('chat')).toBe(true);
    const resolved = tree.resolve('chat');
    expect(resolved).toEqual(['chat']);
  });

  it('should handle deeply nested paths', () => {
    tree.register('a.b.c.d.e');
    expect(tree.contains('a.b.c.d.e')).toBe(true);
    expect(tree.contains('a.b.c')).toBe(true);
    expect(tree.contains('a')).toBe(true);
  });
});
