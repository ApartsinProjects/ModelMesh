/**
 * Pre-shipped LM Studio provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with configuration for
 * LM Studio, a desktop application that serves locally-loaded models
 * via an OpenAI-compatible REST API.
 *
 * Connector ID: "lmstudio.local.v1"
 *
 * LM Studio runs locally and requires no API key. Models are loaded
 * by the user in the LM Studio GUI, so the default model list is
 * empty. Set the LMSTUDIO_HOST environment variable to override the
 * default URL.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface LMStudioProviderConfig extends OpenAICompatibleConfig {}

export function createLMStudioProviderConfig(
  partial?: Partial<LMStudioProviderConfig>
): LMStudioProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'http://localhost:1234',
    apiKey: '',
    models: [],
    capabilities: ['generation.text-generation.chat-completion'],
    ...partial,
  });
}

export class LMStudioProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'lmstudio.local.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;

  constructor(config?: Partial<LMStudioProviderConfig>) {
    super(createLMStudioProviderConfig(config));
  }
}
