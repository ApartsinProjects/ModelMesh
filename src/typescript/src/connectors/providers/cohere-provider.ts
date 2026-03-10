/**
 * Pre-shipped Cohere provider connector.
 *
 * Extends BaseProvider with Cohere v2 API translation. The Cohere v2
 * Chat API uses an OpenAI-compatible message format but has a different
 * response structure, so this connector overrides the key hook methods
 * to handle the translation.
 *
 * Key differences from OpenAI:
 * - Chat endpoint is /v2/chat (not /v1/chat/completions).
 * - Response wraps content in message.content[0].text (array of
 *   content blocks) instead of choices[0].message.content.
 * - Usage is reported under usage.billed_units with
 *   input_tokens and output_tokens.
 * - Finish reason values differ: "COMPLETE" -> "stop",
 *   "MAX_TOKENS" -> "length".
 *
 * Connector ID: "cohere.nlp.v1"
 */

import {
  BaseProvider,
  BaseProviderConfig,
  createBaseProviderConfig,
} from '../../cdk/base-provider';
import {
  CompletionChoice,
  CompletionRequest,
  CompletionResponse,
  ModelInfo,
  createDefaultModelInfo as createModelInfo,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'command-a-03-2025',
    name: 'Command A',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true },
    contextWindow: 256_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'command-r-plus-08-2024',
    name: 'Command R+',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true },
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'command-r-08-2024',
    name: 'Command R',
    capabilities: ['generation.text-generation.chat-completion'],
    features: {},
    contextWindow: 128_000,
    maxOutputTokens: 4_096,
  }),
  createModelInfo({
    id: 'embed-english-v3.0',
    name: 'Embed English v3.0',
    capabilities: ['representation.embeddings.text-embeddings'],
    features: {},
    contextWindow: 512,
    maxOutputTokens: 0,
  }),
  createModelInfo({
    id: 'rerank-english-v3.0',
    name: 'Rerank English v3.0',
    capabilities: ['retrieval.reranking'],
    features: {},
    contextWindow: 4_096,
    maxOutputTokens: 0,
  }),
];

const FINISH_REASON_MAP: Record<string, string> = {
  COMPLETE: 'stop',
  MAX_TOKENS: 'length',
};

export interface CohereProviderConfig extends BaseProviderConfig {}

export function createCohereProviderConfig(
  partial?: Partial<CohereProviderConfig>
): CohereProviderConfig {
  return createBaseProviderConfig({
    baseUrl: 'https://api.cohere.com',
    models: [...DEFAULT_MODELS],
    capabilities: [
      'generation.text-generation.chat-completion',
      'representation.embeddings.text-embeddings',
      'retrieval.reranking',
    ],
    ...partial,
  });
}

export class CohereProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'cohere.nlp.v1';

  constructor(config?: Partial<CohereProviderConfig>) {
    super(createCohereProviderConfig(config));
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/v2/chat`;
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    const payload: Record<string, any> = {
      model: request.model,
      messages: request.messages,
    };

    if (request.temperature !== undefined) {
      payload.temperature = request.temperature;
    }

    if (request.maxTokens != null) {
      payload.max_tokens = request.maxTokens;
    }

    if (request.topP != null && request.topP !== 1.0) {
      payload.p = request.topP;
    }

    if (request.stop && request.stop.length > 0) {
      payload.stop_sequences = request.stop;
    }

    if (request.tools && request.tools.length > 0) {
      payload.tools = request.tools;
    }

    if (request.stream) {
      payload.stream = true;
    }

    return payload;
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    const usageData = data.usage || {};
    const billed = usageData.billed_units || {};
    const inputTokens = billed.input_tokens || 0;
    const outputTokens = billed.output_tokens || 0;

    const messageData = data.message || {};
    const contentBlocks = messageData.content || [];

    const textParts: string[] = [];
    for (const block of contentBlocks) {
      if (typeof block === 'object' && block.type === 'text') {
        textParts.push(block.text || '');
      }
    }

    const contentText = textParts.length > 0 ? textParts.join('') : undefined;
    const role = messageData.role || 'assistant';

    const rawFinish = data.finish_reason || '';
    const finishReason = FINISH_REASON_MAP[rawFinish] || (rawFinish ? rawFinish.toLowerCase() : undefined);

    const choice: CompletionChoice = {
      index: 0,
      message: { role, content: contentText },
      finishReason,
    };

    return createCompletionResponse({
      id: data.id || '',
      model: data.model || '',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens: inputTokens,
        completionTokens: outputTokens,
        totalTokens: inputTokens + outputTokens,
      }),
    });
  }

  protected _parseSseChunk(line: string): CompletionResponse | null {
    let data: Record<string, any>;
    try {
      data = JSON.parse(line);
    } catch {
      return null;
    }

    const eventType = data.type || '';

    if (eventType === 'content-delta') {
      const delta = data.delta || {};
      const messageDelta = delta.message || {};
      const contentBlocks = messageDelta.content || {};
      const text = contentBlocks.text || '';

      return createCompletionResponse({
        id: '',
        model: '',
        choices: [
          {
            index: 0,
            delta: { role: 'assistant', content: text },
          },
        ],
        usage: createTokenUsage(),
      });
    }

    if (eventType === 'message-end') {
      const delta = data.delta || {};
      const rawFinish = delta.finish_reason || '';
      const finishReason = FINISH_REASON_MAP[rawFinish] || (rawFinish ? rawFinish.toLowerCase() : undefined);

      const usageData = delta.usage || {};
      const billed = usageData.billed_units || {};
      const inputTokens = billed.input_tokens || 0;
      const outputTokens = billed.output_tokens || 0;

      return createCompletionResponse({
        id: '',
        model: '',
        choices: [
          {
            index: 0,
            finishReason,
          },
        ],
        usage: createTokenUsage({
          promptTokens: inputTokens,
          completionTokens: outputTokens,
          totalTokens: inputTokens + outputTokens,
        }),
      });
    }

    return null;
  }
}
