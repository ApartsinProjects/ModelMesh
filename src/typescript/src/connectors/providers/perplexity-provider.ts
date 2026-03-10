/**
 * Pre-shipped Perplexity provider connector.
 *
 * Extends OpenAICompatibleProvider for the Perplexity Sonar API. Perplexity
 * uses an OpenAI-compatible request/response format, so no hook overrides
 * are needed. This connector primarily provides the model catalogue with
 * grounded-generation capabilities and sets the correct base URL.
 *
 * Connector ID: "perplexity.search.v1"
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'sonar-pro',
    name: 'Sonar Pro',
    capabilities: ['retrieval.grounded-generation.web-search'],
    features: {},
    contextWindow: 200_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'sonar',
    name: 'Sonar',
    capabilities: ['retrieval.grounded-generation.web-search'],
    features: {},
    contextWindow: 128_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'sonar-reasoning-pro',
    name: 'Sonar Reasoning Pro',
    capabilities: ['retrieval.grounded-generation.web-search'],
    features: { reasoning: true },
    contextWindow: 128_000,
    maxOutputTokens: 8_192,
  }),
];

export interface PerplexityProviderConfig extends OpenAICompatibleConfig {}

export function createPerplexityProviderConfig(
  partial?: Partial<PerplexityProviderConfig>
): PerplexityProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'https://api.perplexity.ai',
    models: [...DEFAULT_MODELS],
    capabilities: ['retrieval.grounded-generation.web-search'],
    ...partial,
  });
}

export class PerplexityProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'perplexity.search.v1';

  constructor(config?: Partial<PerplexityProviderConfig>) {
    super(createPerplexityProviderConfig(config));
  }
}
