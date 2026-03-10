/**
 * Pre-shipped OpenAI provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue,
 * pricing, and configuration for the OpenAI API. This connector is
 * registered as "openai.llm.v1" and requires only an API key to use.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo, createDefaultModelPricing as createModelPricing } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'gpt-4o',
    name: 'GPT-4o',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 16_384,
    pricing: createModelPricing({
      inputPer1kTokens: 0.0025,
      outputPer1kTokens: 0.01,
    }),
  }),
  createModelInfo({
    id: 'gpt-4o-mini',
    name: 'GPT-4o Mini',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 16_384,
    pricing: createModelPricing({
      inputPer1kTokens: 0.00015,
      outputPer1kTokens: 0.0006,
    }),
  }),
  createModelInfo({
    id: 'gpt-4-turbo',
    name: 'GPT-4 Turbo',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
    pricing: createModelPricing({
      inputPer1kTokens: 0.01,
      outputPer1kTokens: 0.03,
    }),
  }),
  createModelInfo({
    id: 'gpt-3.5-turbo',
    name: 'GPT-3.5 Turbo',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: false, system_prompt: true },
    contextWindow: 16_385,
    maxOutputTokens: 4_096,
    pricing: createModelPricing({
      inputPer1kTokens: 0.0005,
      outputPer1kTokens: 0.0015,
    }),
  }),
];

export interface OpenAIProviderConfig extends OpenAICompatibleConfig {}

export function createOpenAIProviderConfig(
  partial?: Partial<OpenAIProviderConfig>
): OpenAIProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'https://api.openai.com',
    models: [...DEFAULT_MODELS],
    capabilities: ['generation.text-generation.chat-completion'],
    ...partial,
  });
}

export class OpenAIProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'openai.llm.v1';

  constructor(config?: Partial<OpenAIProviderConfig>) {
    super(createOpenAIProviderConfig(config));
  }
}
