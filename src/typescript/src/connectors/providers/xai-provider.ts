/**
 * Pre-shipped xAI (Grok) provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue
 * and configuration for the xAI API. This connector is registered as
 * "xai.grok.v1" and requires only an API key to use.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'grok-2',
    name: 'Grok 2',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 32_768,
  }),
  createModelInfo({
    id: 'grok-2-mini',
    name: 'Grok 2 Mini',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 32_768,
  }),
];

export interface XAIProviderConfig extends OpenAICompatibleConfig {}

export function createXAIProviderConfig(
  partial?: Partial<XAIProviderConfig>
): XAIProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'https://api.x.ai',
    models: [...DEFAULT_MODELS],
    capabilities: ['generation.text-generation.chat-completion'],
    ...partial,
  });
}

export class XAIProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'xai.grok.v1';

  constructor(config?: Partial<XAIProviderConfig>) {
    super(createXAIProviderConfig(config));
  }
}
