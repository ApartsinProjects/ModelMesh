/**
 * Pre-shipped Anthropic provider connector.
 *
 * Extends BaseProvider with Anthropic-specific API translation. The
 * Anthropic Messages API uses a different request/response format than
 * the OpenAI chat completions spec, so this connector overrides the
 * four key hook methods to handle the translation.
 *
 * Connector ID: "anthropic.claude.v1"
 */

import {
  BaseProvider,
  BaseProviderConfig,
  createBaseProviderConfig,
} from '../../cdk/base-provider';
import { RuntimeEnvironment } from '../../interfaces/runtime';
import {
  ChatMessage,
  CompletionChoice,
  CompletionRequest,
  CompletionResponse,
  ModelInfo,
  TokenUsage,
  createDefaultModelInfo as createModelInfo,
  createDefaultModelPricing as createModelPricing,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../../interfaces/provider';

const DEFAULT_ANTHROPIC_VERSION = '2023-06-01';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'claude-sonnet-4-20250514',
    name: 'Claude Sonnet 4',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true, system_prompt: true },
    contextWindow: 200_000,
    maxOutputTokens: 16_384,
    pricing: createModelPricing({
      inputPer1kTokens: 0.003,
      outputPer1kTokens: 0.015,
    }),
  }),
  createModelInfo({
    id: 'claude-haiku-4-5-20251001',
    name: 'Claude Haiku 4.5',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true, system_prompt: true },
    contextWindow: 200_000,
    maxOutputTokens: 8_192,
    pricing: createModelPricing({
      inputPer1kTokens: 0.0008,
      outputPer1kTokens: 0.004,
    }),
  }),
];

export interface AnthropicProviderConfig extends BaseProviderConfig {
  anthropicVersion: string;
}

export function createAnthropicProviderConfig(
  partial?: Partial<AnthropicProviderConfig>
): AnthropicProviderConfig {
  return {
    ...createBaseProviderConfig({
      baseUrl: 'https://api.anthropic.com',
      models: [...DEFAULT_MODELS],
      capabilities: ['generation.text-generation.chat-completion'],
    }),
    anthropicVersion: DEFAULT_ANTHROPIC_VERSION,
    ...partial,
  } as AnthropicProviderConfig;
}

const STOP_REASON_MAP: Record<string, string> = {
  end_turn: 'stop',
  max_tokens: 'length',
  stop_sequence: 'stop',
  tool_use: 'tool_calls',
};

export class AnthropicProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'anthropic.claude.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private _anthropicConfig: AnthropicProviderConfig;

  constructor(config?: Partial<AnthropicProviderConfig>) {
    const fullConfig = createAnthropicProviderConfig(config);
    super(fullConfig);
    this._anthropicConfig = fullConfig;
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/v1/messages`;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'anthropic-version': this._anthropicConfig.anthropicVersion,
    };
    if (this._config.apiKey) {
      headers['x-api-key'] = this._config.apiKey;
    }
    return headers;
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    const systemParts: string[] = [];
    const messages: Record<string, any>[] = [];

    for (const msg of request.messages) {
      const role = String(msg.role || '');
      const content = String(msg.content || '');

      if (role === 'system') {
        if (content) {
          systemParts.push(content);
        }
      } else {
        messages.push({ role, content });
      }
    }

    let maxTokens = request.maxTokens;
    if (maxTokens == null) {
      const modelInfo = this._modelsByid.get(request.model);
      maxTokens = modelInfo?.maxOutputTokens || 4096;
    }

    const payload: Record<string, any> = {
      model: request.model,
      messages,
      max_tokens: maxTokens,
    };

    if (systemParts.length > 0) {
      payload.system = systemParts.join('\n\n');
    }

    if (request.temperature !== undefined) {
      payload.temperature = request.temperature;
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
    const inputTokens = usageData.input_tokens || 0;
    const outputTokens = usageData.output_tokens || 0;

    const contentBlocks = data.content || [];
    const textParts: string[] = [];
    for (const block of contentBlocks) {
      if (typeof block === 'object' && block.type === 'text') {
        textParts.push(block.text || '');
      }
    }

    const contentText = textParts.length > 0 ? textParts.join('') : undefined;

    const stopReason = data.stop_reason;
    const finishReason = STOP_REASON_MAP[stopReason] || stopReason || undefined;

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
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

    if (eventType === 'content_block_delta') {
      const delta = data.delta || {};
      if (delta.type === 'text_delta') {
        const text = delta.text || '';
        return createCompletionResponse({
          id: '',
          model: '',
          choices: [
            {
              index: data.index || 0,
              delta: { role: 'assistant', content: text },
            },
          ],
          usage: createTokenUsage(),
        });
      }
    }

    if (eventType === 'message_delta') {
      const stopReason = (data.delta || {}).stop_reason;
      const finishReason = STOP_REASON_MAP[stopReason] || stopReason || undefined;
      const usageData = data.usage || {};

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
          promptTokens: 0,
          completionTokens: usageData.output_tokens || 0,
          totalTokens: usageData.output_tokens || 0,
        }),
      });
    }

    return null;
  }
}
