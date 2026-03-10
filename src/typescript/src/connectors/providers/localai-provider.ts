/**
 * Pre-shipped LocalAI provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with configuration for
 * LocalAI, a self-hosted AI inference server that exposes an
 * OpenAI-compatible REST API and supports multiple model backends.
 *
 * Connector ID: "localai.local.v1"
 *
 * LocalAI runs locally and requires no API key. Models are loaded
 * from the model gallery or local files. Set the LOCALAI_HOST
 * environment variable to override the default URL.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface LocalAIProviderConfig extends OpenAICompatibleConfig {}

export function createLocalAIProviderConfig(
  partial?: Partial<LocalAIProviderConfig>
): LocalAIProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'http://localhost:8080',
    apiKey: '',
    models: [],
    capabilities: ['generation.text-generation.chat-completion'],
    ...partial,
  });
}

export class LocalAIProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'localai.local.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;

  constructor(config?: Partial<LocalAIProviderConfig>) {
    super(createLocalAIProviderConfig(config));
  }
}
