/**
 * Pre-shipped Google Gemini provider connector.
 *
 * Extends BaseProvider with Gemini-specific API translation. The
 * Google Generative Language API uses a different request/response format
 * than the OpenAI chat completions spec, so this connector overrides the
 * four key hook methods to handle the translation.
 *
 * Key differences from OpenAI:
 * - API key is passed as a ?key= query parameter (not in headers).
 * - System messages go in a top-level systemInstruction field.
 * - Role mapping: "assistant" -> "model", "user" -> "user".
 * - Response wraps content in candidates[].content.parts[].
 *
 * Connector ID: "google.gemini.v1"
 */

import {
  BaseProvider,
  BaseProviderConfig,
  createBaseProviderConfig,
} from '../../cdk/base-provider';
import { RuntimeEnvironment } from '../../interfaces/runtime';
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
    id: 'gemini-2.5-flash-preview-05-20',
    name: 'Gemini 2.5 Flash Preview',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true },
    contextWindow: 1_000_000,
    maxOutputTokens: 65_536,
  }),
  createModelInfo({
    id: 'gemini-2.0-flash',
    name: 'Gemini 2.0 Flash',
    capabilities: ['generation.text-generation.chat-completion'],
    features: { tool_calling: true, vision: true },
    contextWindow: 1_000_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'gemini-2.0-flash-lite',
    name: 'Gemini 2.0 Flash Lite',
    capabilities: ['generation.text-generation.chat-completion'],
    features: {},
    contextWindow: 1_000_000,
    maxOutputTokens: 8_192,
  }),
  createModelInfo({
    id: 'text-embedding-004',
    name: 'Text Embedding 004',
    capabilities: ['representation.embeddings.text-embeddings'],
    features: {},
    contextWindow: 2_048,
    maxOutputTokens: 0,
  }),
];

export interface GeminiProviderConfig extends BaseProviderConfig {}

export function createGeminiProviderConfig(
  partial?: Partial<GeminiProviderConfig>
): GeminiProviderConfig {
  return createBaseProviderConfig({
    baseUrl: 'https://generativelanguage.googleapis.com',
    models: [...DEFAULT_MODELS],
    capabilities: [
      'generation.text-generation.chat-completion',
      'representation.embeddings.text-embeddings',
    ],
    ...partial,
  });
}

const ROLE_TO_GEMINI: Record<string, string> = {
  assistant: 'model',
  user: 'user',
};

const ROLE_FROM_GEMINI: Record<string, string> = {
  model: 'assistant',
  user: 'user',
};

const FINISH_REASON_MAP: Record<string, string> = {
  STOP: 'stop',
  MAX_TOKENS: 'length',
  SAFETY: 'content_filter',
};

export class GeminiProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'google.gemini.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private _currentModel: string = '';

  constructor(config?: Partial<GeminiProviderConfig>) {
    super(createGeminiProviderConfig(config));
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    const model = this._currentModel || 'gemini-2.0-flash';
    const apiKey = this._config.apiKey || '';
    return `${base}/v1beta/models/${model}:generateContent?key=${apiKey}`;
  }

  protected _buildHeaders(): Record<string, string> {
    return { 'Content-Type': 'application/json' };
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    this._currentModel = request.model;

    const systemParts: string[] = [];
    const contents: Record<string, any>[] = [];

    for (const msg of request.messages) {
      const role = String(msg.role || '');
      const content = String(msg.content || '');

      if (role === 'system') {
        if (content) {
          systemParts.push(content);
        }
      } else {
        const geminiRole = ROLE_TO_GEMINI[role] || role;
        contents.push({
          role: geminiRole,
          parts: [{ text: content }],
        });
      }
    }

    const payload: Record<string, any> = { contents };

    if (systemParts.length > 0) {
      payload.systemInstruction = {
        parts: [{ text: systemParts.join('\n\n') }],
      };
    }

    const generationConfig: Record<string, any> = {};
    if (request.temperature !== undefined) {
      generationConfig.temperature = request.temperature;
    }
    if (request.maxTokens != null) {
      generationConfig.maxOutputTokens = request.maxTokens;
    }
    if (request.topP != null && request.topP !== 1.0) {
      generationConfig.topP = request.topP;
    }
    if (request.stop && request.stop.length > 0) {
      generationConfig.stopSequences = request.stop;
    }

    if (Object.keys(generationConfig).length > 0) {
      payload.generationConfig = generationConfig;
    }

    if (request.tools && request.tools.length > 0) {
      payload.tools = request.tools;
    }

    return payload;
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    const usageData = data.usageMetadata || {};
    const promptTokens = usageData.promptTokenCount || 0;
    const completionTokens = usageData.candidatesTokenCount || 0;
    const totalTokens = usageData.totalTokenCount || 0;

    const candidates = data.candidates || [];
    const choices: CompletionChoice[] = [];

    for (let i = 0; i < candidates.length; i++) {
      const candidate = candidates[i];
      const contentData = candidate.content || {};
      const parts = contentData.parts || [];

      const textParts: string[] = [];
      for (const part of parts) {
        if (typeof part === 'object' && 'text' in part) {
          textParts.push(part.text);
        }
      }

      const contentText = textParts.length > 0 ? textParts.join('') : undefined;

      const rawFinish = candidate.finishReason || '';
      const finishReason = FINISH_REASON_MAP[rawFinish] || (rawFinish ? rawFinish.toLowerCase() : undefined);

      const geminiRole = contentData.role || 'model';
      const role = ROLE_FROM_GEMINI[geminiRole] || geminiRole;

      choices.push({
        index: i,
        message: { role, content: contentText },
        finishReason,
      });
    }

    return createCompletionResponse({
      id: '',
      model: this._currentModel,
      choices,
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens,
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

    const candidates = data.candidates || [];
    if (candidates.length === 0) {
      return null;
    }

    const choices: CompletionChoice[] = [];
    for (const candidate of candidates) {
      const contentData = candidate.content || {};
      const parts = contentData.parts || [];

      const textParts: string[] = [];
      for (const part of parts) {
        if (typeof part === 'object' && 'text' in part) {
          textParts.push(part.text);
        }
      }

      const text = textParts.length > 0 ? textParts.join('') : '';

      const rawFinish = candidate.finishReason;
      const finishReason = rawFinish ? (FINISH_REASON_MAP[rawFinish] || undefined) : undefined;

      choices.push({
        index: candidate.index || 0,
        delta: { role: 'assistant', content: text },
        finishReason,
      });
    }

    const usageData = data.usageMetadata || {};
    return createCompletionResponse({
      id: '',
      model: this._currentModel,
      choices,
      usage: createTokenUsage({
        promptTokens: usageData.promptTokenCount || 0,
        completionTokens: usageData.candidatesTokenCount || 0,
        totalTokens: usageData.totalTokenCount || 0,
      }),
    });
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    this._currentModel = request.model;
    return super.complete(request);
  }

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionResponse> {
    this._currentModel = request.model;
    yield* super.stream(request);
  }
}
