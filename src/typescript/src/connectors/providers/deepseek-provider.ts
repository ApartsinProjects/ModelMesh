/**
 * Pre-shipped DeepSeek provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
 * pricing, and configuration for the DeepSeek API. This connector is
 * registered as "deepseek.api.v1" and requires only an API key to use.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo, createDefaultModelPricing as createModelPricing } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'deepseek-chat',
    name: 'DeepSeek Chat',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, system_prompt: true },
    contextWindow: 64_000,
    maxOutputTokens: 8_192,
    pricing: createModelPricing({
      inputPer1kTokens: 0.00014,
      outputPer1kTokens: 0.00028,
    }),
  }),
  createModelInfo({
    id: 'deepseek-reasoner',
    name: 'DeepSeek Reasoner',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { reasoning: true, system_prompt: true },
    contextWindow: 64_000,
    maxOutputTokens: 8_192,
  }),
];

export interface DeepSeekProviderConfig extends OpenAICompatibleConfig {}

export function createDeepSeekProviderConfig(
  partial?: Partial<DeepSeekProviderConfig>
): DeepSeekProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'https://api.deepseek.com',
    models: [...DEFAULT_MODELS],
    capabilities: ['generation.text-generation.chat-completion'],
    ...partial,
  });
}

export class DeepSeekProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'deepseek.api.v1';

  constructor(config?: Partial<DeepSeekProviderConfig>) {
    super(createDeepSeekProviderConfig(config));
  }
}
