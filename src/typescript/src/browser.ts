/**
 * ModelMesh -- Browser entry point.
 *
 * Exports only browser-safe modules that have no dependency on Node.js
 * built-ins (fs, http, https, child_process, etc.). Use this entry point
 * when bundling for web pages, Deno, Cloudflare Workers, or any other
 * environment without Node.js APIs.
 *
 * Usage (browser bundler):
 *
 *   import { BrowserBaseProvider, ModelMesh, MeshClient } from '@modelmesh/core/browser';
 *
 * Or directly in a script tag via a bundler or CDN:
 *
 *   <script type="module">
 *     import { BrowserBaseProvider } from './browser.js';
 *   </script>
 */

// ---------------------------------------------------------------------------
// Core (browser-safe: no Node.js deps)
// ---------------------------------------------------------------------------

export { ModelMesh } from './core/mesh';
export { CapabilityTree } from './core/capability-tree';
export { CapabilityPool, createPoolModel } from './core/pool';
export type { PoolModel } from './core/pool';
export { Router } from './core/router';
export { StateManager } from './core/state-manager';
export { EventEmitter } from './core/event-emitter';

// ---------------------------------------------------------------------------
// Interfaces (pure types -- always browser-safe)
// ---------------------------------------------------------------------------

export * from './interfaces/provider';
export * from './interfaces/rotation';
export * from './interfaces/observability';
export * from './interfaces/storage';
export * from './interfaces/secret-store';
export * from './interfaces/discovery';
export * from './interfaces/runtime';

// ---------------------------------------------------------------------------
// Client (browser-safe: pure logic)
// ---------------------------------------------------------------------------

export { MeshClient } from './client/mesh-client';

// ---------------------------------------------------------------------------
// Connectors -- Browser-compatible storage & secret stores
// ---------------------------------------------------------------------------

export { MemoryStorage } from './connectors/storage/memory-storage';
export { LocalStorageStorage } from './connectors/storage/localstorage-storage';
export type { LocalStorageStorageConfig } from './connectors/storage/localstorage-storage';
export { SessionStorageStorage } from './connectors/storage/sessionstorage-storage';
export type { SessionStorageStorageConfig } from './connectors/storage/sessionstorage-storage';
export { IndexedDBStorage } from './connectors/storage/indexeddb-storage';
export type { IndexedDBStorageConfig } from './connectors/storage/indexeddb-storage';
export { MemorySecretStore } from './connectors/secret-stores/memory-store';
export type { MemorySecretStoreConfig } from './connectors/secret-stores/memory-store';
export { BrowserSecretStore } from './connectors/secret-stores/browser-store';
export type { BrowserSecretStoreConfig } from './connectors/secret-stores/browser-store';

// ---------------------------------------------------------------------------
// CDK -- Browser-compatible base classes
// ---------------------------------------------------------------------------

export {
  BrowserBaseProvider,
  BrowserProviderConfig,
  BrowserHttpError,
  createBrowserProviderConfig,
} from './cdk/browser-provider';

export {
  BaseRotationPolicy,
  BaseDeactivationPolicy,
  BaseRecoveryPolicy,
  BaseSelectionStrategy,
} from './cdk/base-rotation';
export type { BaseRotationConfig } from './cdk/base-rotation';

export { BaseSecretStore } from './cdk/base-secret-store';
export type { BaseSecretStoreConfig } from './cdk/base-secret-store';

export { BaseObservability } from './cdk/base-observability';
export type { BaseObservabilityConfig } from './cdk/base-observability';

// ---------------------------------------------------------------------------
// CDK -- Specialized (browser-safe subset)
// ---------------------------------------------------------------------------

export { ThresholdRotationPolicy } from './cdk/specialized/threshold-rotation';
export type { ThresholdRotationConfig } from './cdk/specialized/threshold-rotation';

export { ConsoleObservability } from './cdk/specialized/console-observability';
export type { ConsoleObservabilityConfig } from './cdk/specialized/console-observability';

// ---------------------------------------------------------------------------
// CDK -- Test helpers (browser-safe)
// ---------------------------------------------------------------------------

export {
  mockCompletionRequest,
  mockModelSnapshot,
  MockHttpClient,
  ConnectorTestHarness,
} from './cdk/helpers';
export type { MockHttpResponse, HttpCall, HarnessCall } from './cdk/helpers';

// ---------------------------------------------------------------------------
// Config -- browser-safe subset (no fromFile, no fs)
// ---------------------------------------------------------------------------

export { MeshConfig } from './config/mesh-config';

// ---------------------------------------------------------------------------
// Convenience: createBrowser()
// ---------------------------------------------------------------------------

import { ModelMesh } from './core/mesh';
import { MeshClient } from './client/mesh-client';
import { MeshConfig } from './config/mesh-config';
import {
  BrowserBaseProvider,
  createBrowserProviderConfig,
} from './cdk/browser-provider';
import type { BrowserProviderConfig } from './cdk/browser-provider';

/** Well-known short names mapped to full capability tree paths. */
const CAPABILITY_ALIASES: Record<string, string> = {
  'chat-completion': 'generation.text-generation.chat-completion',
  'text-generation': 'generation.text-generation',
  'text-embeddings': 'representation.embeddings.text-embeddings',
  'text-to-speech': 'generation.audio.text-to-speech',
  'speech-to-text': 'understanding.audio.speech-to-text',
  'text-to-image': 'generation.image.text-to-image',
  'image-to-text': 'representation.image.image-to-text',
  'code-generation': 'generation.text-generation.code-generation',
};

function resolveCapabilityPath(name: string): string {
  if (name.includes('.')) return name;
  return CAPABILITY_ALIASES[name] ?? name;
}

export interface BrowserCreateOptions {
  /** Provider configurations (keyed by connector ID). */
  providers: Record<string, {
    connector: string;
    config: Partial<BrowserProviderConfig>;
  }>;
  /** Model definitions (keyed by model ID). */
  models: Record<string, {
    provider: string;
    capabilities: string[];
  }>;
  /** Pool definitions (keyed by pool name). */
  pools?: Record<string, {
    capability: string;
    strategy?: string;
  }>;
  /** Observability config. */
  observability?: Record<string, unknown>;
}

/**
 * Create a ModelMesh instance configured for browser use.
 *
 * Unlike the Node.js `create()` function, this does not auto-detect
 * providers from environment variables (browsers have no `process.env`).
 * Instead, all configuration is passed explicitly.
 *
 * @param capabilities - Required capabilities (e.g. "chat-completion").
 * @param options - Full configuration with providers, models, and pools.
 * @returns Initialized ModelMesh instance.
 *
 * @example
 * const mesh = createBrowser('chat-completion', {
 *   providers: {
 *     'openai.llm.v1': {
 *       connector: 'openai.llm.v1',
 *       config: {
 *         baseUrl: 'https://api.openai.com',
 *         apiKey: userApiKey,
 *         proxyUrl: 'http://localhost:3000/proxy/',
 *       },
 *     },
 *   },
 *   models: {
 *     'openai.gpt-4o': {
 *       provider: 'openai.llm.v1',
 *       capabilities: ['generation.text-generation.chat-completion'],
 *     },
 *   },
 * });
 */
export function createBrowser(
  ...args: unknown[]
): ModelMesh {
  const capabilities: string[] = [];
  let options: BrowserCreateOptions | undefined;

  for (const arg of args) {
    if (typeof arg === 'string') {
      capabilities.push(arg);
    } else if (typeof arg === 'object' && arg !== null && !Array.isArray(arg)) {
      options = arg as BrowserCreateOptions;
    }
  }

  if (!options) {
    throw new Error(
      'Browser create() requires an options object with providers and models.'
    );
  }

  const poolsSection: Record<string, unknown> = {};
  if (options.pools) {
    for (const [name, pool] of Object.entries(options.pools)) {
      poolsSection[name] = {
        capability: resolveCapabilityPath(pool.capability),
        strategy: pool.strategy ?? 'stick-until-failure',
      };
    }
  } else {
    for (const cap of capabilities) {
      const capabilityPath = resolveCapabilityPath(cap);
      poolsSection[cap] = {
        capability: capabilityPath,
        strategy: 'stick-until-failure',
      };
    }
  }

  const providersSection: Record<string, unknown> = {};
  for (const [id, prov] of Object.entries(options.providers)) {
    providersSection[id] = {
      connector: prov.connector,
      enabled: true,
      config: prov.config,
    };
  }

  const mesh = new ModelMesh();
  mesh.initialize(new MeshConfig({
    providers: providersSection,
    models: options.models,
    pools: poolsSection,
    observability: options.observability ?? { connector: 'modelmesh.null.v1' },
  }));

  return mesh;
}
