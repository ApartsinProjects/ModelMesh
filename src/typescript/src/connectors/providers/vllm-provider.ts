/**
 * Pre-shipped vLLM provider connector.
 *
 * Wraps the CDK's OpenAICompatibleProvider with configuration for
 * vLLM, a high-throughput inference engine that serves models via
 * an OpenAI-compatible REST API.
 *
 * Connector ID: "vllm.local.v1"
 *
 * vLLM runs locally and requires no API key. The model is specified
 * at server startup, so the default model list is empty. Set the
 * VLLM_HOST environment variable to override the default URL.
 */

import {
  OpenAICompatibleProvider,
  OpenAICompatibleConfig,
  createOpenAICompatibleConfig,
} from '../../cdk/specialized/openai-compatible';
import { RuntimeEnvironment } from '../../interfaces/runtime';

export interface VLLMProviderConfig extends OpenAICompatibleConfig {}

export function createVLLMProviderConfig(
  partial?: Partial<VLLMProviderConfig>
): VLLMProviderConfig {
  return createOpenAICompatibleConfig({
    baseUrl: 'http://localhost:8000',
    apiKey: '',
    models: [],
    capabilities: ['generation.text-generation.chat-completion'],
    ...partial,
  });
}

export class VLLMProvider extends OpenAICompatibleProvider {
  static readonly CONNECTOR_ID = 'vllm.local.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;

  constructor(config?: Partial<VLLMProviderConfig>) {
    super(createVLLMProviderConfig(config));
  }
}
