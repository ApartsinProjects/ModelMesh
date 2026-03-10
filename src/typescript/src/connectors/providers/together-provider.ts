/**
 * Pre-shipped Together AI provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue
 * and configuration for the Together AI API. This connector is registered
 * as "together.api.v1" and requires only an API key to use.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'meta-llama/Llama-3.3-70B-Instruct-Turbo',
    name: 'Llama 3.3 70B Instruct Turbo',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'meta-llama/Llama-3.1-8B-Instruct-Turbo',
    name: 'Llama 3.1 8B Instruct Turbo',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'Qwen/Qwen2.5-72B-Instruct-Turbo',
    name: 'Qwen 2.5 72B Instruct Turbo',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'deepseek-ai/DeepSeek-V3',
    name: 'DeepSeek V3',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'BAAI/bge-large-en-v1.5',
    name: 'BGE Large EN v1.5',
    capabilities: ['representation.embeddings.text-embeddings'],
    features: {},
    contextWindow: 512,
    maxOutputTokens: 0,
  }),
  createModelInfo({
    id: 'stabilityai/stable-diffusion-xl-base-1.0',
    name: 'Stable Diffusion XL Base 1.0',
    capabilities: ['generation.image.text-to-image'],
    features: {},
    contextWindow: 0,
    maxOutputTokens: 0,
  }),
];

export interface TogetherProviderConfig extends OpenAICompatibleConfig {}

export function createTogetherProviderConfig(
  partial?: Partial<TogetherProviderConfig>
): TogetherProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'https://api.together.xyz',
    models: [...DEFAULT_MODELS],
    capabilities: [
      'generation.text-generation.chat-completion',
      'representation.embeddings.text-embeddings',
      'generation.image.text-to-image',
    ],
    ...partial,
  });
}

export class TogetherProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'together.api.v1';

  constructor(config?: Partial<TogetherProviderConfig>) {
    super(createTogetherProviderConfig(config));
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/v1/chat/completions`;
  }
}
