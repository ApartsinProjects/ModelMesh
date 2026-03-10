/**
 * CDK (Connector Development Kit) exports.
 *
 * Provides base implementations of all connector interfaces with sensible
 * defaults. Each base class handles boilerplate so that custom connectors
 * only override the methods that differ from the defaults.
 *
 * Also re-exports specialized pre-configured classes and test helpers.
 */

// -- Base classes ------------------------------------------------------------

export {
  BaseProvider,
  BaseProviderConfig,
  HttpError,
  createBaseProviderConfig,
} from './base-provider';

export {
  BaseRotationPolicy,
  BaseDeactivationPolicy,
  BaseRecoveryPolicy,
  BaseSelectionStrategy,
} from './base-rotation';
export type { BaseRotationConfig } from './base-rotation';

export { BaseSecretStore } from './base-secret-store';
export type { BaseSecretStoreConfig } from './base-secret-store';

export { BaseStorage } from './base-storage';
export type { BaseStorageConfig } from './base-storage';

export { BaseObservability } from './base-observability';
export type { BaseObservabilityConfig } from './base-observability';

export { BaseDiscovery } from './base-discovery';
export type { BaseDiscoveryConfig } from './base-discovery';

// -- Specialized classes -----------------------------------------------------

export {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from './specialized/openai-compatible';

export { ThresholdRotationPolicy } from './specialized/threshold-rotation';
export type { ThresholdRotationConfig } from './specialized/threshold-rotation';

export { ConsoleObservability } from './specialized/console-observability';
export type { ConsoleObservabilityConfig } from './specialized/console-observability';

export { KeyValueStorage } from './specialized/kv-storage';
export type { KeyValueStorageConfig } from './specialized/kv-storage';

export { FileSecretStore } from './specialized/file-secret-store';
export type { FileSecretStoreConfig } from './specialized/file-secret-store';

export { HttpHealthDiscovery } from './specialized/http-health-discovery';
export type { HttpHealthDiscoveryConfig } from './specialized/http-health-discovery';

// -- Browser provider -------------------------------------------------------

export {
  BrowserBaseProvider,
  BrowserHttpError,
  createBrowserProviderConfig,
} from './browser-provider';
export type { BrowserProviderConfig } from './browser-provider';

// -- Test helpers ------------------------------------------------------------

export {
  mockCompletionRequest,
  mockModelSnapshot,
  MockHttpClient,
  ConnectorTestHarness,
} from './helpers';
export type {
  MockHttpResponse,
  HttpCall,
  HarnessCall,
} from './helpers';
