/**
 * Pre-shipped OpenRouter provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue
 * and configuration for the OpenRouter gateway API. This connector is
 * registered as "openrouter.gateway.v1" and requires only an API key.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'auto',
    name: 'Auto (Best Available)',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'openai/gpt-4o',
    name: 'OpenAI GPT-4o',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 16_384,
  }),
  createModelInfo({
    id: 'anthropic/claude-sonnet-4',
    name: 'Anthropic Claude Sonnet 4',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 200_000,
    maxOutputTokens: 16_384,
  }),
  createModelInfo({
    id: 'google/gemini-2.0-flash-exp',
    name: 'Google Gemini 2.0 Flash Exp',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 1_000_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'meta-llama/llama-3.3-70b-instruct',
    name: 'Meta Llama 3.3 70B Instruct',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
];

export interface OpenRouterProviderConfig extends OpenAICompatibleConfig {
  httpReferer: string;
  xTitle: string;
}

export function createOpenRouterProviderConfig(
  partial?: Partial<OpenRouterProviderConfig>
): OpenRouterProviderConfig {
  return {
    ...createOpenAICompatibleConfig({
      baseUrl: 'https://openrouter.ai/api',
      models: [...DEFAULT_MODELS],
      capabilities: ['generation.text-generation.chat-completion'],
    }),
    httpReferer: '',
    xTitle: 'ModelMesh',
    ...partial,
  } as OpenRouterProviderConfig;
}

export class OpenRouterProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'openrouter.gateway.v1';
  private _orConfig: OpenRouterProviderConfig;

  constructor(config?: Partial<OpenRouterProviderConfig>) {
    const fullConfig = createOpenRouterProviderConfig(config);
    super(fullConfig);
    this._orConfig = fullConfig;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers = super._buildHeaders();
    if (this._orConfig.httpReferer) {
      headers['HTTP-Referer'] = this._orConfig.httpReferer;
    }
    if (this._orConfig.xTitle) {
      headers['X-Title'] = this._orConfig.xTitle;
    }
    return headers;
  }
}
