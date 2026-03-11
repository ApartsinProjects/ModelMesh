/**
 * ModelMesh -- Capability-driven AI model routing.
 *
 * A single integration point for multiple AI providers with automatic
 * rotation to aggregate free tiers, minimize cost, and maintain service
 * continuity. Applications request capabilities; ModelMesh manages
 * providers, quotas, costs, and failover.
 *
 * Quick start:
 *
 *   import { create } from '@modelmesh/core';
 *
 *   const client = create('chat-completion');
 *   const response = await client.chat.completions.create({
 *     model: 'chat-completion',
 *     messages: [{ role: 'user', content: 'Hello!' }],
 *   });
 *   console.log(response.choices[0].message.content);
 */

// Core
export { ModelMesh } from './core/mesh';
export { CapabilityTree } from './core/capability-tree';
export { CapabilityPool, createPoolModel } from './core/pool';
export type { PoolModel } from './core/pool';
export { Router } from './core/router';
export { StateManager } from './core/state-manager';
export { EventEmitter } from './core/event-emitter';

// Interfaces
export * from './interfaces/provider';
export * from './interfaces/rotation';
export * from './interfaces/observability';
export * from './interfaces/storage';
export * from './interfaces/secret-store';
export * from './interfaces/discovery';

// CDK -- Base classes
export { BaseProvider, HttpError, createBaseProviderConfig } from './cdk/base-provider';
export type { BaseProviderConfig } from './cdk/base-provider';
export {
  BaseRotationPolicy,
  BaseDeactivationPolicy,
  BaseRecoveryPolicy,
  BaseSelectionStrategy,
} from './cdk/base-rotation';
export type { BaseRotationConfig } from './cdk/base-rotation';
export { BaseSecretStore } from './cdk/base-secret-store';
export type { BaseSecretStoreConfig } from './cdk/base-secret-store';
export { BaseStorage } from './cdk/base-storage';
export type { BaseStorageConfig } from './cdk/base-storage';
export { BaseObservability } from './cdk/base-observability';
export type { BaseObservabilityConfig } from './cdk/base-observability';
export { BaseDiscovery } from './cdk/base-discovery';
export type { BaseDiscoveryConfig } from './cdk/base-discovery';

// CDK -- Browser provider
export { BrowserBaseProvider, BrowserHttpError, createBrowserProviderConfig } from './cdk/browser-provider';
export type { BrowserProviderConfig } from './cdk/browser-provider';

// CDK -- Specialized classes
export { OpenAICompatibleProvider } from './cdk/specialized/openai-compatible';
export { ThresholdRotationPolicy } from './cdk/specialized/threshold-rotation';
export type { ThresholdRotationConfig } from './cdk/specialized/threshold-rotation';
export { ConsoleObservability } from './cdk/specialized/console-observability';
export type { ConsoleObservabilityConfig } from './cdk/specialized/console-observability';
export { KeyValueStorage } from './cdk/specialized/kv-storage';
export type { KeyValueStorageConfig } from './cdk/specialized/kv-storage';
export { FileSecretStore } from './cdk/specialized/file-secret-store';
export type { FileSecretStoreConfig } from './cdk/specialized/file-secret-store';
export { HttpHealthDiscovery } from './cdk/specialized/http-health-discovery';
export type { HttpHealthDiscoveryConfig } from './cdk/specialized/http-health-discovery';

// CDK -- Test helpers
export {
  mockCompletionRequest,
  mockModelSnapshot,
  MockHttpClient,
  ConnectorTestHarness,
} from './cdk/helpers';
export type { MockHttpResponse, HttpCall, HarnessCall } from './cdk/helpers';

// Config
export { MeshConfig } from './config/mesh-config';
export { detectProviders, PROVIDER_REGISTRY } from './config/auto-detect';
export type { DetectedProvider } from './config/auto-detect';

// Exceptions
export {
  ModelMeshError,
  RoutingError,
  NoActiveModelError,
  AllProvidersExhaustedError,
  ProviderError,
  AuthenticationError,
  RateLimitError,
  ProviderTimeoutError,
  ConfigurationError,
  BudgetExceededError,
} from './exceptions';

// Middleware
export { Middleware, MiddlewareStack, createMiddlewareContext } from './middleware';
export type { MiddlewareContext } from './middleware';

// Usage
export { UsageTracker } from './usage';
export type { ModelUsage, ProviderUsage, BudgetStatus } from './usage';

// Testing
export { MockClient, mockClient } from './testing';
export type { MockResponse, MockCall } from './testing';

// Capabilities
export * as capabilities from './capabilities';

// Client
export { MeshClient } from './client/mesh-client';

// Proxy
export { ProxyServer } from './proxy/server';
export type { ServerStatus } from './proxy/server';

// Connectors
export { CONNECTOR_REGISTRY } from './connectors';

// Runtime environment metadata
export { RuntimeEnvironment } from './interfaces/runtime';
export { detectRuntime, assertRuntimeCompatible } from './core/runtime-guard';

// Connectors -- Local / self-hosted providers
export { OllamaProvider, createOllamaProviderConfig } from './connectors/providers/ollama-provider';
export type { OllamaProviderConfig } from './connectors/providers/ollama-provider';
export { LMStudioProvider, createLMStudioProviderConfig } from './connectors/providers/lmstudio-provider';
export type { LMStudioProviderConfig } from './connectors/providers/lmstudio-provider';
export { VLLMProvider, createVLLMProviderConfig } from './connectors/providers/vllm-provider';
export type { VLLMProviderConfig } from './connectors/providers/vllm-provider';
export { LocalAIProvider, createLocalAIProviderConfig } from './connectors/providers/localai-provider';
export type { LocalAIProviderConfig } from './connectors/providers/localai-provider';

// Connectors -- Azure Speech TTS
export { AzureSpeechProvider, createAzureSpeechProviderConfig } from './connectors/providers/azure-speech-provider';
export type { AzureSpeechProviderConfig } from './connectors/providers/azure-speech-provider';

// Connectors -- Secret Stores
export { EnvSecretStore } from './connectors/secret-stores/env-store';
export type { EnvSecretStoreConfig } from './connectors/secret-stores/env-store';
export { DotenvSecretStore } from './connectors/secret-stores/dotenv-store';
export type { DotenvSecretStoreConfig } from './connectors/secret-stores/dotenv-store';
export { JsonSecretStore } from './connectors/secret-stores/json-store';
export type { JsonSecretStoreConfig } from './connectors/secret-stores/json-store';
export { MemorySecretStore } from './connectors/secret-stores/memory-store';
export type { MemorySecretStoreConfig } from './connectors/secret-stores/memory-store';
export { EncryptedFileSecretStore } from './connectors/secret-stores/encrypted-file-store';
export type { EncryptedFileSecretStoreConfig } from './connectors/secret-stores/encrypted-file-store';
export { KeyringSecretStore } from './connectors/secret-stores/keyring-store';
export type { KeyringSecretStoreConfig } from './connectors/secret-stores/keyring-store';

// Connectors -- Browser storage & secret stores
export { LocalStorageStorage } from './connectors/storage/localstorage-storage';
export type { LocalStorageStorageConfig } from './connectors/storage/localstorage-storage';
export { SessionStorageStorage } from './connectors/storage/sessionstorage-storage';
export type { SessionStorageStorageConfig } from './connectors/storage/sessionstorage-storage';
export { IndexedDBStorage } from './connectors/storage/indexeddb-storage';
export type { IndexedDBStorageConfig } from './connectors/storage/indexeddb-storage';
export { BrowserSecretStore } from './connectors/secret-stores/browser-store';
export type { BrowserSecretStoreConfig } from './connectors/secret-stores/browser-store';

// ---------------------------------------------------------------------------
// Convenience layer: create()
// ---------------------------------------------------------------------------

import { ModelMesh } from './core/mesh';
import { MeshClient } from './client/mesh-client';
import { MeshConfig } from './config/mesh-config';
import { detectProviders } from './config/auto-detect';

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

export interface CreateOptions {
  pool?: string;
  providers?: string[];
  models?: string[];
  strategy?: string;
  apiKeys?: Record<string, string>;
  config?: string | Record<string, unknown> | MeshConfig;
  /** Middleware instances to attach to the router. */
  middleware?: Middleware[];
}

/**
 * Create an OpenAI SDK-compatible client with ModelMesh routing.
 *
 * This is the primary entry point. It auto-detects available providers
 * from environment variables, builds capability pools, configures
 * rotation, and returns a MeshClient ready for use.
 *
 * @param capabilities - Required capabilities (e.g. "chat-completion").
 * @param options - Optional configuration overrides.
 * @returns MeshClient ready for use.
 *
 * @example
 * // Layer 0 -- single capability
 * const client = create('chat-completion');
 *
 * @example
 * // Layer 1 -- multi-capability with provider filter
 * const client = create('chat-completion', 'text-embeddings', {
 *   providers: ['openai', 'anthropic'],
 *   strategy: 'cost-first',
 * });
 *
 * @example
 * // Layer 2 -- full configuration
 * const client = create({ config: 'modelmesh.json' });
 */
export function create(...args: unknown[]): MeshClient {
  // Parse arguments: capabilities are strings, last arg may be options object
  const capabilities: string[] = [];
  let options: CreateOptions = {};

  for (const arg of args) {
    if (typeof arg === 'string') {
      capabilities.push(arg);
    } else if (typeof arg === 'object' && arg !== null && !Array.isArray(arg)) {
      options = arg as CreateOptions;
    }
  }

  const {
    pool,
    providers,
    models: modelFilter,
    strategy = 'stick-until-failure',
    apiKeys,
    config,
    middleware: middlewareList,
  } = options;

  const mesh = new ModelMesh();

  // Layer 2: Full configuration
  if (config !== undefined) {
    let meshConfig: MeshConfig;
    if (typeof config === 'string') {
      meshConfig = MeshConfig.fromFile(config);
    } else if (config instanceof MeshConfig) {
      meshConfig = config;
    } else {
      meshConfig = MeshConfig.fromDict(config);
    }
    mesh.initialize(meshConfig);
    const client = mesh.getClient();
    if (middlewareList && middlewareList.length > 0) {
      mesh.router.setMiddleware(new MiddlewareStack(middlewareList));
    }
    return client;
  }

  if (capabilities.length === 0 && pool === undefined) {
    throw new Error(
      'Specify capabilities, pool, or config. ' +
      "Example: create('chat-completion')"
    );
  }

  // Auto-detect available providers
  const detected = detectProviders({ names: providers, apiKeys });
  if (detected.length === 0) {
    throw new Error(
      'No providers detected. Set API key environment variables ' +
      '(e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY) or pass apiKeys.'
    );
  }

  // Build config from detected providers + capabilities/pool
  const providersSection: Record<string, unknown> = {};
  const modelsSection: Record<string, unknown> = {};
  const poolsSection: Record<string, unknown> = {};

  for (const prov of detected) {
    providersSection[prov.connector] = {
      connector: prov.connector,
      enabled: true,
      config: {
        api_key: prov.apiKey,
        base_url: prov.baseUrl ?? '',
      },
    };

    for (const modelInfo of prov.defaultModels) {
      const modelId = modelInfo.id;
      const modelCaps = [...modelInfo.capabilities];

      if (modelFilter && !modelFilter.includes(modelId)) continue;

      modelsSection[modelId] = {
        provider: prov.connector,
        capabilities: modelCaps,
      };
    }
  }

  if (pool !== undefined) {
    const capabilityPath = resolveCapabilityPath(pool);
    poolsSection[pool] = { capability: capabilityPath, strategy };
  } else {
    for (const cap of capabilities) {
      const capabilityPath = resolveCapabilityPath(cap);
      poolsSection[cap] = { capability: capabilityPath, strategy };
    }
  }

  mesh.initialize(new MeshConfig({
    providers: providersSection,
    models: modelsSection,
    pools: poolsSection,
    observability: { connector: 'modelmesh.null.v1' },
  }));
  const client = mesh.getClient();
  if (middlewareList && middlewareList.length > 0) {
    mesh.router.setMiddleware(new MiddlewareStack(middlewareList));
  }
  return client;
}
