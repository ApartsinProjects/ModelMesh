/**
 * Pre-shipped Azure Speech TTS provider connector.
 *
 * Extends BaseProvider with Microsoft Azure Speech Services API
 * translation. The Azure Cognitive Services Speech REST API accepts
 * SSML (Speech Synthesis Markup Language) XML and returns raw binary
 * audio data.
 *
 * Key differences from OpenAI:
 * - Auth uses Ocp-Apim-Subscription-Key header.
 * - Endpoint is region-specific:
 *   https://{region}.tts.speech.microsoft.com/cognitiveservices/v1
 * - Content-Type is application/ssml+xml (not JSON).
 * - Request body is SSML XML, not JSON.
 * - Response is raw binary audio (not JSON).
 * - X-Microsoft-OutputFormat header controls audio format.
 *
 * Connector ID: "azure.tts.v1"
 */

import * as https from 'https';
import * as http from 'http';
import { URL } from 'url';
import {
  BaseProvider,
  BaseProviderConfig,
  HttpError,
  createBaseProviderConfig,
} from '../../cdk/base-provider';
import {
  CompletionRequest,
  CompletionResponse,
  ModelInfo,
  createDefaultModelInfo as createModelInfo,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../../interfaces/provider';

// -- Defaults ----------------------------------------------------------------

const DEFAULT_REGION = 'eastus';
const DEFAULT_VOICE = 'en-US-JennyNeural';
const DEFAULT_LANGUAGE = 'en-US';
const DEFAULT_OUTPUT_FORMAT = 'audio-24khz-48kbitrate-mono-mp3';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'en-US-JennyNeural',
    name: 'Jenny (en-US, Female)',
    capabilities: ['generation.audio.text-to-speech'],
    features: {},
    contextWindow: 10_000,
    maxOutputTokens: 0,
  }),
  createModelInfo({
    id: 'en-US-AndrewNeural',
    name: 'Andrew (en-US, Male)',
    capabilities: ['generation.audio.text-to-speech'],
    features: {},
    contextWindow: 10_000,
    maxOutputTokens: 0,
  }),
];

// -- Config ------------------------------------------------------------------

export interface AzureSpeechProviderConfig extends BaseProviderConfig {
  /** Azure region for the Speech resource. */
  region: string;
  /** Default voice short name (e.g. "en-US-JennyNeural"). */
  voice: string;
  /** SSML language attribute (e.g. "en-US"). */
  language: string;
  /** Audio output format header value. */
  outputFormat: string;
}

export function createAzureSpeechProviderConfig(
  partial?: Partial<AzureSpeechProviderConfig>
): AzureSpeechProviderConfig {
  const region = partial?.region ?? DEFAULT_REGION;
  const baseUrl =
    partial?.baseUrl ||
    `https://${region}.tts.speech.microsoft.com`;

  return {
    ...createBaseProviderConfig({
      baseUrl,
      models: [...DEFAULT_MODELS],
      capabilities: ['generation.audio.text-to-speech'],
    }),
    region,
    voice: DEFAULT_VOICE,
    language: DEFAULT_LANGUAGE,
    outputFormat: DEFAULT_OUTPUT_FORMAT,
    ...partial,
    // Ensure baseUrl is re-derived if region was overridden but baseUrl was not
    baseUrl: partial?.baseUrl || `https://${region}.tts.speech.microsoft.com`,
  } as AzureSpeechProviderConfig;
}

// -- Helpers -----------------------------------------------------------------

/** Escape XML special characters in text content. */
function xmlEscape(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

// -- Provider ----------------------------------------------------------------

export class AzureSpeechProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'azure.tts.v1';
  private _azureConfig: AzureSpeechProviderConfig;

  constructor(config?: Partial<AzureSpeechProviderConfig>) {
    const fullConfig = createAzureSpeechProviderConfig(config);
    super(fullConfig);
    this._azureConfig = fullConfig;
  }

  // -- Hook overrides --------------------------------------------------------

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/cognitiveservices/v1`;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/ssml+xml',
      'X-Microsoft-OutputFormat': this._azureConfig.outputFormat,
      'User-Agent': 'ModelMesh/1.0',
    };
    if (this._config.apiKey) {
      headers['Ocp-Apim-Subscription-Key'] = this._config.apiKey;
    }
    return headers;
  }

  protected _buildRequestPayload(
    request: CompletionRequest
  ): Record<string, any> {
    // Extract text from the first message
    let text = '';
    for (const msg of request.messages) {
      const content = String(msg.content || '');
      if (content) {
        text = content;
        break;
      }
    }

    // Use model as voice name if provided, otherwise configured default
    const voice = request.model || this._azureConfig.voice;
    const language = this._azureConfig.language;

    // Build SSML document
    const ssml =
      `<speak version='1.0' xml:lang='${xmlEscape(language)}'>` +
      `<voice xml:lang='${xmlEscape(language)}' ` +
      `name='${xmlEscape(voice)}'>` +
      `${xmlEscape(text)}` +
      `</voice></speak>`;

    return { __ssml_body: ssml, __text: text };
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    // If we get JSON back, it's an error response
    let errorMsg: string;
    const errorObj = data.error;
    if (typeof errorObj === 'object' && errorObj !== null) {
      errorMsg = errorObj.message || JSON.stringify(data);
    } else {
      errorMsg = String(errorObj || JSON.stringify(data));
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

  // -- Custom HTTP method for SSML -------------------------------------------

  private _httpPostSsml(
    url: string,
    ssmlBody: string,
    headers: Record<string, string>
  ): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      const parsed = new URL(url);
      const transport = parsed.protocol === 'https:' ? https : http;
      const body = Buffer.from(ssmlBody, 'utf-8');

      headers['Content-Length'] = String(body.length);

      const options: https.RequestOptions = {
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method: 'POST',
        headers,
        timeout: this._config.timeout * 1000,
      };

      const req = transport.request(options, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const responseBody = Buffer.concat(chunks);
          if (res.statusCode && res.statusCode >= 400) {
            const responseHeaders: Record<string, string> = {};
            for (const [key, val] of Object.entries(res.headers)) {
              if (typeof val === 'string') responseHeaders[key] = val;
            }
            reject(
              new HttpError(
                res.statusCode,
                responseBody.toString('utf-8'),
                responseHeaders
              )
            );
          } else {
            resolve(responseBody);
          }
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Request timed out'));
      });

      req.write(body);
      req.end();
    });
  }

  // -- Complete override -----------------------------------------------------

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    const payload = this._buildRequestPayload(request);
    const headers = this._buildHeaders();
    const endpoint = this._getCompletionEndpoint();
    const ssmlBody: string = payload.__ssml_body;

    let lastError: Error | null = null;
    for (let attempt = 0; attempt <= this._config.maxRetries; attempt++) {
      try {
        const audioBytes = await this._httpPostSsml(
          endpoint,
          ssmlBody,
          { ...headers }
        );

        const audioSizeKb = audioBytes.length / 1024;
        const outputFormat = this._azureConfig.outputFormat;
        const charCount = (payload.__text || '').length;

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
        if (
          !classification.retryable ||
          attempt === this._config.maxRetries
        ) {
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
