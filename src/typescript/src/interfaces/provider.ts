/**
 * Provider connector interface and associated data types.
 *
 * Defines the ProviderConnector interface and all request/response
 * data types used for OpenAI-compatible model execution.
 */

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

export interface ModelPricing {
  inputPer1kTokens: number;
  outputPer1kTokens: number;
  perRequest: number;
}

export interface ModelInfo {
  id: string;
  name: string;
  capabilities: string[];
  contextWindow: number;
  maxOutputTokens: number;
  pricing?: ModelPricing;
  features: Record<string, boolean>;
  delivery: Record<string, boolean>;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface ChatMessage {
  role: string;
  content?: string;
  toolCalls?: unknown[];
}

export interface CompletionChoice {
  index: number;
  message?: ChatMessage;
  delta?: ChatMessage;
  finishReason?: string;
}

export interface CompletionRequest {
  model: string;
  messages: Record<string, unknown>[];
  temperature: number;
  maxTokens?: number;
  stream: boolean;
  tools?: unknown[];
  topP: number;
  stop?: string[];
}

export interface CompletionResponse {
  id: string;
  model: string;
  choices: CompletionChoice[];
  usage: TokenUsage;
  created: number;
  object: string;
}

export interface QuotaStatus {
  used: number;
  limit?: number;
  remaining?: number;
  resetAt?: string;
}

export interface RateLimitStatus {
  requestsRemaining?: number;
  tokensRemaining?: number;
  resetAt?: string;
}

export interface ErrorClassification {
  retryable: boolean;
  errorCode?: number;
  message: string;
  category: string;
}

// ---------------------------------------------------------------------------
// Audio data types
// ---------------------------------------------------------------------------

/**
 * Request payload for text-to-speech synthesis.
 *
 * Matches the OpenAI audio speech API shape so callers can use
 * `client.audio.speech.create({ model, voice, input })`.
 */
export interface AudioSpeechRequest {
  /** Model ID (e.g. "tts-1", "eleven_multilingual_v2"). */
  model: string;
  /** Text to synthesize. */
  input: string;
  /** Voice identifier (provider-specific). */
  voice: string;
  /** Output audio format. */
  responseFormat?: string;
  /** Speech speed multiplier (0.25–4.0). */
  speed?: number;
}

/**
 * Response from a text-to-speech synthesis request.
 *
 * Wraps audio output metadata. The actual audio bytes are transport-
 * dependent (returned as a Buffer in Node.js, ArrayBuffer in browsers).
 */
export interface AudioSpeechResponse {
  /** Audio content as bytes. null if only metadata is returned. */
  audioData: Uint8Array | null;
  /** Audio format (e.g. "mp3", "wav", "opus"). */
  format: string;
  /** Size of audio data in bytes. */
  sizeBytes: number;
  /** Duration of audio in seconds (if known). */
  durationSeconds?: number;
  /** The model used. */
  model: string;
  /** Input character count. */
  inputCharacters: number;
}

/**
 * Request payload for speech-to-text transcription.
 *
 * Matches the OpenAI audio transcriptions API shape.
 */
export interface AudioTranscriptionRequest {
  /** Model ID (e.g. "whisper-1", "assemblyai-best"). */
  model: string;
  /** Audio file URL or base64-encoded audio data. */
  file: string;
  /** Language hint (ISO-639-1). */
  language?: string;
  /** Output format ("json", "text", "srt", "vtt"). */
  responseFormat?: string;
  /** Prompt to guide transcription. */
  prompt?: string;
}

/**
 * Response from a speech-to-text transcription request.
 */
export interface AudioTranscriptionResponse {
  /** Transcribed text. */
  text: string;
  /** Language detected. */
  language?: string;
  /** Audio duration in seconds. */
  durationSeconds?: number;
  /** Transcription confidence (0.0–1.0). */
  confidence?: number;
  /** The model used. */
  model: string;
}

// ---------------------------------------------------------------------------
// Abstract interface
// ---------------------------------------------------------------------------

export interface ProviderConnector {
  complete(request: CompletionRequest): Promise<CompletionResponse>;
  stream(request: CompletionRequest): AsyncIterableIterator<CompletionResponse>;
  getCapabilities(): string[];
  supports(capability: string): boolean;
  listModels(): ModelInfo[];
  getModelInfo(modelId: string): ModelInfo;
  checkQuota(): QuotaStatus;
  getRateLimits(): RateLimitStatus;
  getPricing(modelId: string): ModelPricing;
  reportUsage(modelId: string, usage: TokenUsage): void;
  classifyError(error: Error): ErrorClassification;
  isRetryable(error: Error): boolean;
  close(): Promise<void>;
}

// ---------------------------------------------------------------------------
// Helper factory functions for creating default data objects
// ---------------------------------------------------------------------------

export function createDefaultTokenUsage(
  overrides?: Partial<TokenUsage>
): TokenUsage {
  return { promptTokens: 0, completionTokens: 0, totalTokens: 0, ...overrides };
}

export function createDefaultCompletionRequest(
  overrides: Partial<CompletionRequest> & { model: string; messages: Record<string, unknown>[] }
): CompletionRequest {
  return {
    temperature: 1.0,
    stream: false,
    topP: 1.0,
    ...overrides,
  };
}

export function createDefaultCompletionResponse(
  overrides?: Partial<CompletionResponse>
): CompletionResponse {
  return {
    id: '',
    model: '',
    choices: [],
    usage: createDefaultTokenUsage(),
    created: 0,
    object: 'chat.completion',
    ...overrides,
  };
}

export function createDefaultModelInfo(
  overrides: Partial<ModelInfo> & { id: string; name: string }
): ModelInfo {
  return {
    capabilities: [],
    contextWindow: 0,
    maxOutputTokens: 0,
    features: {},
    delivery: { synchronous: true },
    ...overrides,
  };
}

export function createDefaultModelPricing(
  overrides?: Partial<ModelPricing>
): ModelPricing {
  return {
    inputPer1kTokens: 0,
    outputPer1kTokens: 0,
    perRequest: 0,
    ...overrides,
  };
}

/**
 * Default implementation of isRetryable -- delegates to classifyError.
 *
 * Matches the Python ProviderConnector.is_retryable() default behavior.
 * Provider implementors can use this as their isRetryable implementation:
 *
 *   isRetryable: (error) => defaultIsRetryable(this, error),
 */
export function defaultIsRetryable(
  connector: Pick<ProviderConnector, 'classifyError'>,
  error: Error
): boolean {
  return connector.classifyError(error).retryable;
}

/**
 * Create a default HealthReport with auto-populated timestamp.
 *
 * Matches the Python HealthReport.__post_init__() behavior where
 * timestamp defaults to the current time if not provided.
 */
export function createDefaultHealthReport(
  overrides: { providerId: string; available: boolean } & Record<string, unknown>
): {
  providerId: string;
  available: boolean;
  latencyMs?: number;
  statusCode?: number;
  error?: string;
  availabilityScore: number;
  timestamp: Date;
} {
  return {
    availabilityScore: 1.0,
    timestamp: new Date(),
    ...overrides,
  } as {
    providerId: string;
    available: boolean;
    latencyMs?: number;
    statusCode?: number;
    error?: string;
    availabilityScore: number;
    timestamp: Date;
  };
}

// ---------------------------------------------------------------------------
// Audio factory functions
// ---------------------------------------------------------------------------

export function createDefaultAudioSpeechRequest(
  overrides: Partial<AudioSpeechRequest> & { model: string; input: string; voice: string }
): AudioSpeechRequest {
  return {
    responseFormat: 'mp3',
    speed: 1.0,
    ...overrides,
  };
}

export function createDefaultAudioSpeechResponse(
  overrides?: Partial<AudioSpeechResponse>
): AudioSpeechResponse {
  return {
    audioData: null,
    format: 'mp3',
    sizeBytes: 0,
    model: '',
    inputCharacters: 0,
    ...overrides,
  };
}

export function createDefaultAudioTranscriptionRequest(
  overrides: Partial<AudioTranscriptionRequest> & { model: string; file: string }
): AudioTranscriptionRequest {
  return {
    responseFormat: 'json',
    ...overrides,
  };
}

export function createDefaultAudioTranscriptionResponse(
  overrides?: Partial<AudioTranscriptionResponse>
): AudioTranscriptionResponse {
  return {
    text: '',
    model: '',
    ...overrides,
  };
}

// Aliases for convenience
export const createModelInfo = createDefaultModelInfo;
export const createModelPricing = createDefaultModelPricing;
export const createTokenUsage = createDefaultTokenUsage;
export const createCompletionResponse = createDefaultCompletionResponse;
