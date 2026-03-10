/**
 * Pre-shipped Ollama provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with default model catalogue
 * and configuration for Ollama, a local inference server that exposes
 * an OpenAI-compatible REST API.
 *
 * Connector ID: "ollama.local.v1"
 *
 * Ollama runs locally and requires no API key. Set the OLLAMA_HOST
 * environment variable to override the default URL.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { ModelInfo, createDefaultModelInfo as createModelInfo } from '../../interfaces/provider';
import { RuntimeEnvironment } from '../../interfaces/runtime';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'llama3',
    name: 'Llama 3',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 8_192,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'codellama',
    name: 'Code Llama',
    capabilities: [
      'generation.text-generation.chat-completion',
      'generation.text-generation.code-generation',
    ],
    features: { system_prompt: true },
    contextWindow: 16_384,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'mistral',
    name: 'Mistral',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 8_192,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'gemma2',
    name: 'Gemma 2',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { system_prompt: true },
    contextWindow: 8_192,
    maxOutputTokens: 4_096,
  }),
];

export interface OllamaProviderConfig extends OpenAICompatibleConfig {}

export function createOllamaProviderConfig(
  partial?: Partial<OllamaProviderConfig>
): OllamaProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'http://localhost:11434',
    apiKey: '',
    models: [...DEFAULT_MODELS],
    capabilities: [
      'generation.text-generation.chat-completion',
      'generation.text-generation.code-generation',
    ],
    ...partial,
  });
}

export class OllamaProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'ollama.local.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;

  constructor(config?: Partial<OllamaProviderConfig>) {
    super(createOllamaProviderConfig(config));
  }
}
