/**
 * Pre-shipped AssemblyAI speech-to-text provider connector.
 *
 * Wraps AssemblyAI's transcription API as a ModelMesh provider so
 * speech-to-text capabilities can participate in capability pools.
 * Accepts an audio file URL in the last message's content, submits it
 * for transcription, polls until completion, and returns the transcript
 * as a CompletionResponse.
 *
 * Connector ID: "assemblyai.stt.v1"
 */

import { randomBytes } from 'crypto';
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
  createDefaultModelPricing as createModelPricing,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'assemblyai-best',
    name: 'AssemblyAI Best',
    capabilities: ['understanding.audio.speech-to-text'],
    features: { speaker_labels: true, punctuation: true },
    contextWindow: 0,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.015 }),
  }),
  createModelInfo({
    id: 'assemblyai-nano',
    name: 'AssemblyAI Nano',
    capabilities: ['understanding.audio.speech-to-text'],
    features: { speaker_labels: false, punctuation: true },
    contextWindow: 0,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.005 }),
  }),
];

export interface AssemblyAIProviderConfig extends BaseProviderConfig {
  pollInterval: number;
  maxPollAttempts: number;
}

export function createAssemblyAIProviderConfig(
  partial?: Partial<AssemblyAIProviderConfig>
): AssemblyAIProviderConfig {
  return {
    ...createBaseProviderConfig({
      baseUrl: 'https://api.assemblyai.com',
      models: [...DEFAULT_MODELS],
      capabilities: ['understanding.audio.speech-to-text'],
    }),
    pollInterval: 3.0,
    maxPollAttempts: 120,
    ...partial,
  } as AssemblyAIProviderConfig;
}

export class AssemblyAIProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'assemblyai.stt.v1';
  private _assemblyaiConfig: AssemblyAIProviderConfig;

  constructor(config?: Partial<AssemblyAIProviderConfig>) {
    const fullConfig = createAssemblyAIProviderConfig(config);
    super(fullConfig);
    this._assemblyaiConfig = fullConfig;
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/v2/transcript`;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this._config.apiKey) {
      headers['Authorization'] = this._config.apiKey;
    }
    return headers;
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    let audioUrl = '';
    if (request.messages.length > 0) {
      const lastMsg = request.messages[request.messages.length - 1];
      audioUrl = String(lastMsg.content || '').trim();
    }

    const payload: Record<string, any> = { audio_url: audioUrl };

    if (request.model === 'assemblyai-nano') {
      payload.speech_model = 'nano';
    } else {
      payload.speech_model = 'best';
    }

    return payload;
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    const status = data.status || '';
    const transcriptText = data.text || '';
    const errorMsg = data.error;

    let contentText: string;

    if (status === 'error' && errorMsg) {
      contentText = `Transcription error: ${errorMsg}`;
    } else if (!transcriptText) {
      contentText = 'No transcript generated.';
    } else {
      const parts: string[] = [transcriptText];

      const confidence = data.confidence;
      const audioDuration = data.audio_duration;
      if (confidence != null) {
        parts.push(`\n[Confidence: ${(confidence * 100).toFixed(0)}%]`);
      }
      if (audioDuration != null) {
        parts.push(`[Duration: ${audioDuration.toFixed(1)}s]`);
      }

      contentText = parts.join('\n');
    }

    const audioDuration = data.audio_duration || 0;
    const promptTokens = Math.max(1, Math.floor(audioDuration));
    const completionTokens = Math.max(1, Math.floor(contentText.length / 4));

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
      finishReason: 'stop',
    };

    return createCompletionResponse({
      id: data.id || `assemblyai-${randomBytes(6).toString('hex')}`,
      model: data.speech_model || 'assemblyai-best',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      }),
    });
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    const payload = this._buildRequestPayload(request);
    const headers = this._buildHeaders();
    const endpoint = this._getCompletionEndpoint();

    // Step 1: Submit the transcription job
    const submitData = await this._httpPost(endpoint, payload, headers);
    const transcriptId = submitData.id;

    if (!transcriptId) {
      const errorMsg = submitData.error || 'No transcript ID returned';
      throw new Error(`AssemblyAI submission failed: ${errorMsg}`);
    }

    // Step 2: Poll until completion
    const pollUrl = `${endpoint}/${transcriptId}`;
    for (let attempt = 0; attempt < this._assemblyaiConfig.maxPollAttempts; attempt++) {
      const pollData = await this._httpGetJson(pollUrl, headers);
      const status = pollData.status || '';

      if (status === 'completed') {
        const result = this._parseResponse(pollData);
        this.reportUsage(request.model, result.usage);
        return result;
      }

      if (status === 'error') {
        const result = this._parseResponse(pollData);
        this.reportUsage(request.model, result.usage);
        return result;
      }

      // Still processing, wait before next poll
      await this._sleep(this._assemblyaiConfig.pollInterval * 1000);
    }

    // Timed out
    throw new Error(
      `AssemblyAI transcription timed out after ` +
        `${this._assemblyaiConfig.maxPollAttempts} poll attempts`
    );
  }
}
