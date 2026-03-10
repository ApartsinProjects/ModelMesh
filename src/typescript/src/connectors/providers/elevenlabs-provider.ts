/**
 * Pre-shipped ElevenLabs TTS provider connector.
 *
 * Extends BaseProvider with ElevenLabs-specific API translation. The
 * ElevenLabs Text-to-Speech API is fundamentally different from OpenAI
 * chat completions: it accepts text input and returns binary audio data.
 * This connector bridges TTS into the OpenAI-compatible completion
 * interface.
 *
 * Key differences from OpenAI:
 * - Auth uses xi-api-key header instead of Authorization: Bearer.
 * - Endpoint is /v1/text-to-speech/{voice_id}.
 * - Request payload is {"text": "...", "model_id": "...", "voice_settings": {...}}.
 * - Response is raw binary audio (not JSON).
 *
 * Connector ID: "elevenlabs.tts.v1"
 */

import {
  BaseProvider,
  BaseProviderConfig,
  HttpError,
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
import { RuntimeEnvironment } from '../../interfaces/runtime';

const DEFAULT_VOICE_ID = '21m00Tcm4TlvDq8ikWAM'; // Rachel

const DEFAULT_VOICE_SETTINGS = {
  stability: 0.5,
  similarity_boost: 0.75,
};

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'eleven_multilingual_v2',
    name: 'Eleven Multilingual v2',
    capabilities: ['generation.audio.text-to-speech'],
    features: {},
    contextWindow: 5_000,
    maxOutputTokens: 0,
  }),
  createModelInfo({
    id: 'eleven_turbo_v2_5',
    name: 'Eleven Turbo v2.5',
    capabilities: ['generation.audio.text-to-speech'],
    features: {},
    contextWindow: 5_000,
    maxOutputTokens: 0,
  }),
];

export interface ElevenLabsProviderConfig extends BaseProviderConfig {
  voiceId: string;
  voiceSettings: Record<string, number>;
  outputFormat: string;
}

export function createElevenLabsProviderConfig(
  partial?: Partial<ElevenLabsProviderConfig>
): ElevenLabsProviderConfig {
  return {
    ...createBaseProviderConfig({
      baseUrl: 'https://api.elevenlabs.io',
      models: [...DEFAULT_MODELS],
      capabilities: ['generation.audio.text-to-speech'],
    }),
    voiceId: DEFAULT_VOICE_ID,
    voiceSettings: { ...DEFAULT_VOICE_SETTINGS },
    outputFormat: 'mp3_44100_128',
    ...partial,
  } as ElevenLabsProviderConfig;
}

export class ElevenLabsProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'elevenlabs.tts.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private _elevenlabsConfig: ElevenLabsProviderConfig;

  constructor(config?: Partial<ElevenLabsProviderConfig>) {
    const fullConfig = createElevenLabsProviderConfig(config);
    super(fullConfig);
    this._elevenlabsConfig = fullConfig;
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    const voiceId = this._elevenlabsConfig.voiceId;
    const outputFormat = this._elevenlabsConfig.outputFormat;
    return `${base}/v1/text-to-speech/${voiceId}?output_format=${outputFormat}`;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this._config.apiKey) {
      headers['xi-api-key'] = this._config.apiKey;
    }
    return headers;
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    let text = '';
    for (const msg of request.messages) {
      const content = String(msg.content || '');
      if (content) {
        text = content;
        break;
      }
    }

    return {
      text,
      model_id: request.model,
      voice_settings: { ...this._elevenlabsConfig.voiceSettings },
    };
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    // If we get JSON back, it's likely an error response
    let errorMsg: string;
    const detail = data.detail;
    if (typeof detail === 'object' && detail !== null) {
      errorMsg = detail.message || 'Unknown error';
    } else {
      errorMsg = String(detail || 'Unknown error');
    }

    return createCompletionResponse({
      id: '',
      model: '',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: `TTS Error: ${errorMsg}`,
          },
          finishReason: 'stop',
        },
      ],
      usage: createTokenUsage(),
    });
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    const payload = this._buildRequestPayload(request);
    const headers = this._buildHeaders();
    const endpoint = this._getCompletionEndpoint();

    let lastError: Error | null = null;
    for (let attempt = 0; attempt <= this._config.maxRetries; attempt++) {
      try {
        const audioBytes = await this._httpPostRaw(endpoint, payload, headers);

        const audioSizeKb = audioBytes.length / 1024;
        const outputFormat = this._elevenlabsConfig.outputFormat;
        const charCount = (payload.text || '').length;

        const result = createCompletionResponse({
          id: '',
          model: request.model,
          choices: [
            {
              index: 0,
              message: {
                role: 'assistant',
                content:
                  `Audio generated successfully. ` +
                  `Format: ${outputFormat}, ` +
                  `Size: ${audioSizeKb.toFixed(1)} KB, ` +
                  `Input characters: ${charCount}`,
              },
              finishReason: 'stop',
            },
          ],
          usage: createTokenUsage({
            promptTokens: charCount,
            completionTokens: 0,
            totalTokens: charCount,
          }),
        });

        this.reportUsage(request.model, result.usage);
        return result;
      } catch (exc: any) {
        lastError = exc;
        const classification = this.classifyError(exc);
        if (!classification.retryable || attempt === this._config.maxRetries) {
          throw exc;
        }
        let retryAfter: number = Math.pow(2, attempt);
        if (exc instanceof HttpError && exc.headers['retry-after']) {
          const parsed = parseFloat(exc.headers['retry-after']);
          if (!isNaN(parsed)) {
            retryAfter = parsed;
          }
        }
        await this._sleep(retryAfter * 1000);
      }
    }
    throw lastError!;
  }
}
