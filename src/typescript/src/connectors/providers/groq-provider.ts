/**
 * Pre-shipped Groq provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue
 * and configuration for the Groq API. This connector is registered as
 * "groq.api.v1" and requires only an API key to use.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo } from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'llama-3.3-70b-versatile',
    name: 'Llama 3.3 70B Versatile',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 32_768,
  }),
  createModelInfo({
    id: 'llama-3.1-8b-instant',
    name: 'Llama 3.1 8B Instant',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 128_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'gemma2-9b-it',
    name: 'Gemma 2 9B IT',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 8_192,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'mixtral-8x7b-32768',
    name: 'Mixtral 8x7B 32768',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 32_768,
    maxOutputTokens: 32_768,
  }),
  createModelInfo({
    id: 'whisper-large-v3-turbo',
    name: 'Whisper Large V3 Turbo',
    capabilities: ['understanding.audio.speech-to-text'],
    features: {},
    contextWindow: 0,
    maxOutputTokens: 0,
  }),
];

export interface GroqProviderConfig extends OpenAICompatibleConfig {}

export function createGroqProviderConfig(
  partial?: Partial<GroqProviderConfig>
): GroqProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'https://api.groq.com/openai',
    models: [...DEFAULT_MODELS],
    capabilities: [
      'generation.text-generation.chat-completion',
      'understanding.audio.speech-to-text',
    ],
    ...partial,
  });
}

export class GroqProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'groq.api.v1';

  constructor(config?: Partial<GroqProviderConfig>) {
    super(createGroqProviderConfig(config));
  }
}
