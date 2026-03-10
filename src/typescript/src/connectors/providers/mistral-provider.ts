/**
 * Pre-shipped Mistral AI provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue
 * and configuration for the Mistral AI API. This connector is registered
 * as "mistral.api.v1" and requires only an API key to use.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'mistral-large-latest',
    name: 'Mistral Large',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'mistral-small-latest',
    name: 'Mistral Small',
    capabilities: [
      'generation.text-generation.chat-completion',
      'representation.embeddings.text-embeddings',
    ],
    features: { tool_calling: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'codestral-latest',
    name: 'Codestral',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 32_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'mistral-embed',
    name: 'Mistral Embed',
    capabilities: ['representation.embeddings.text-embeddings'],
    features: {},
    contextWindow: 8_192,
    maxOutputTokens: 0,
  }),
];

export interface MistralProviderConfig extends OpenAICompatibleConfig {}

export function createMistralProviderConfig(
  partial?: Partial<MistralProviderConfig>
): MistralProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'https://api.mistral.ai',
    models: [...DEFAULT_MODELS],
    capabilities: [
      'generation.text-generation.chat-completion',
      'representation.embeddings.text-embeddings',
    ],
    ...partial,
  });
}

export class MistralProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'mistral.api.v1';

  constructor(config?: Partial<MistralProviderConfig>) {
    super(createMistralProviderConfig(config));
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/v1/chat/completions`;
  }
}
