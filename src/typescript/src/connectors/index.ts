/**
 * Pre-shipped connector implementations for ModelMesh Lite.
 *
 * This module provides ready-to-use connectors for all connector
 * types: providers, secret stores, observability, rotation, and storage.
 * Each connector is registered in the CONNECTOR_REGISTRY dictionary,
 * which maps dot-notated connector IDs to their implementation classes.
 *
 * Usage:
 *
 *     import { CONNECTOR_REGISTRY } from './connectors';
 *     const ProviderClass = CONNECTOR_REGISTRY['openai.llm.v1'];
 *     const provider = new ProviderClass(config);
 */

// Providers
import { OpenAIProvider } from './providers/openai-provider';
import { AnthropicProvider } from './providers/anthropic-provider';
import { GeminiProvider } from './providers/gemini-provider';
import { GroqProvider } from './providers/groq-provider';
import { DeepSeekProvider } from './providers/deepseek-provider';
import { MistralProvider } from './providers/mistral-provider';
import { TogetherProvider } from './providers/together-provider';
import { OpenRouterProvider } from './providers/openrouter-provider';
import { XAIProvider } from './providers/xai-provider';
import { CohereProvider } from './providers/cohere-provider';
import { PerplexityProvider } from './providers/perplexity-provider';
import { ElevenLabsProvider } from './providers/elevenlabs-provider';
import { TavilyProvider } from './providers/tavily-provider';
import { SerperProvider } from './providers/serper-provider';
import { JinaProvider } from './providers/jina-provider';
import { FirecrawlProvider } from './providers/firecrawl-provider';
import { AssemblyAIProvider } from './providers/assemblyai-provider';
import { AzureSpeechProvider } from './providers/azure-speech-provider';

// Secret stores
import { EnvSecretStore } from './secret-stores/env-store';
import { DotenvSecretStore } from './secret-stores/dotenv-store';
import { JsonSecretStore } from './secret-stores/json-store';
import { MemorySecretStore } from './secret-stores/memory-store';
import { EncryptedFileSecretStore } from './secret-stores/encrypted-file-store';
import { KeyringSecretStore } from './secret-stores/keyring-store';

// Observability
import { NullObservabilityConnector } from './observability/null-connector';
import { ConsoleObservabilityConnector } from './observability/console-connector';
import { FileObservabilityConnector } from './observability/file-connector';
import { JsonLogConnector } from './observability/json-log-connector';
import { WebhookConnector } from './observability/webhook-connector';
import { CallbackConnector } from './observability/callback-connector';

// Rotation
import { StickUntilFailurePolicy } from './rotation/stick-until-failure';

// Storage
import { MemoryStorage } from './storage/memory-storage';
import { LocalFileStorage } from './storage/local-file-storage';
import { SqliteStorage } from './storage/sqlite-storage';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const CONNECTOR_REGISTRY: Record<string, any> = {
  // Providers
  [OpenAIProvider.CONNECTOR_ID]: OpenAIProvider,
  [AnthropicProvider.CONNECTOR_ID]: AnthropicProvider,
  [GeminiProvider.CONNECTOR_ID]: GeminiProvider,
  [GroqProvider.CONNECTOR_ID]: GroqProvider,
  [DeepSeekProvider.CONNECTOR_ID]: DeepSeekProvider,
  [MistralProvider.CONNECTOR_ID]: MistralProvider,
  [TogetherProvider.CONNECTOR_ID]: TogetherProvider,
  [OpenRouterProvider.CONNECTOR_ID]: OpenRouterProvider,
  [XAIProvider.CONNECTOR_ID]: XAIProvider,
  [CohereProvider.CONNECTOR_ID]: CohereProvider,
  [PerplexityProvider.CONNECTOR_ID]: PerplexityProvider,
  [ElevenLabsProvider.CONNECTOR_ID]: ElevenLabsProvider,
  [TavilyProvider.CONNECTOR_ID]: TavilyProvider,
  [SerperProvider.CONNECTOR_ID]: SerperProvider,
  [JinaProvider.CONNECTOR_ID]: JinaProvider,
  [FirecrawlProvider.CONNECTOR_ID]: FirecrawlProvider,
  [AssemblyAIProvider.CONNECTOR_ID]: AssemblyAIProvider,
  [AzureSpeechProvider.CONNECTOR_ID]: AzureSpeechProvider,

  // Secret stores
  [EnvSecretStore.CONNECTOR_ID]: EnvSecretStore,
  [DotenvSecretStore.CONNECTOR_ID]: DotenvSecretStore,
  [JsonSecretStore.CONNECTOR_ID]: JsonSecretStore,
  [MemorySecretStore.CONNECTOR_ID]: MemorySecretStore,
  [EncryptedFileSecretStore.CONNECTOR_ID]: EncryptedFileSecretStore,
  [KeyringSecretStore.CONNECTOR_ID]: KeyringSecretStore,

  // Observability
  [NullObservabilityConnector.CONNECTOR_ID]: NullObservabilityConnector,
  [ConsoleObservabilityConnector.CONNECTOR_ID]: ConsoleObservabilityConnector,
  [FileObservabilityConnector.CONNECTOR_ID]: FileObservabilityConnector,
  [JsonLogConnector.CONNECTOR_ID]: JsonLogConnector,
  [WebhookConnector.CONNECTOR_ID]: WebhookConnector,
  [CallbackConnector.CONNECTOR_ID]: CallbackConnector,

  // Rotation
  [StickUntilFailurePolicy.CONNECTOR_ID]: StickUntilFailurePolicy,

  // Storage
  [MemoryStorage.CONNECTOR_ID]: MemoryStorage,
  [LocalFileStorage.CONNECTOR_ID]: LocalFileStorage,
  [SqliteStorage.CONNECTOR_ID]: SqliteStorage,
};

// Re-export all connector modules
export * from './providers';
export * from './observability';
export * from './storage';
export * from './secret-stores';
export * from './rotation';
