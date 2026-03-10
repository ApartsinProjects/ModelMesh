/**
 * MeshClient -- OpenAI SDK-compatible client backed by ModelMesh routing.
 *
 * Provides the same interface as the OpenAI SDK so that existing code
 * can migrate by changing two lines: the import and the client creation.
 * Supports client.chat.completions.create(), client.embeddings.create(),
 * client.models.list(), and ModelMesh extensions like client.poolStatus().
 */

import type { ModelMesh } from '../core/mesh';
import type { CapabilityPool } from '../core/pool';
import type {
  CompletionRequest,
  CompletionResponse,
  AudioSpeechRequest,
  AudioSpeechResponse,
  AudioTranscriptionRequest,
  AudioTranscriptionResponse,
} from '../interfaces/provider';
import {
  createDefaultAudioSpeechResponse,
  createDefaultAudioTranscriptionResponse,
} from '../interfaces/provider';

// ---------------------------------------------------------------------------
// Chat namespace
// ---------------------------------------------------------------------------

class ChatCompletions {
  private _client: MeshClient;

  constructor(client: MeshClient) {
    this._client = client;
  }

  /**
   * Create a chat completion.
   *
   * Accepts all standard OpenAI parameters. The `model` field is
   * a virtual model name that resolves to a capability pool.
   */
  async create(params: {
    model: string;
    messages: Record<string, unknown>[];
    temperature?: number;
    maxTokens?: number;
    stream?: boolean;
    tools?: unknown[];
    topP?: number;
    stop?: string[];
  }): Promise<CompletionResponse | AsyncIterableIterator<CompletionResponse>> {
    const request: CompletionRequest = {
      model: params.model,
      messages: params.messages,
      temperature: params.temperature ?? 1.0,
      maxTokens: params.maxTokens,
      stream: params.stream ?? false,
      tools: params.tools,
      topP: params.topP ?? 1.0,
      stop: params.stop,
    };

    const mesh = this._client.mesh;

    if (request.stream) {
      return mesh.routeStream(request);
    }

    return mesh.route(request);
  }
}

class ChatNamespace {
  readonly completions: ChatCompletions;

  constructor(client: MeshClient) {
    this.completions = new ChatCompletions(client);
  }
}

// ---------------------------------------------------------------------------
// Embeddings namespace
// ---------------------------------------------------------------------------

class EmbeddingsNamespace {
  private _client: MeshClient;

  constructor(client: MeshClient) {
    this._client = client;
  }

  /**
   * Create embeddings.
   *
   * Routes through the pool identified by model (e.g. "text-embeddings").
   */
  async create(params: {
    model: string;
    input: string | string[];
  }): Promise<CompletionResponse> {
    const inputs = typeof params.input === 'string' ? [params.input] : params.input;
    const request: CompletionRequest = {
      model: params.model,
      messages: inputs.map((text) => ({ role: 'user', content: text })),
      temperature: 0.0,
      stream: false,
      topP: 1.0,
    };
    return this._client.mesh.route(request);
  }
}

// ---------------------------------------------------------------------------
// Audio namespace
// ---------------------------------------------------------------------------

class AudioSpeechNamespace {
  private _client: MeshClient;

  constructor(client: MeshClient) {
    this._client = client;
  }

  /**
   * Create speech from text (text-to-speech).
   *
   * Routes through a pool with the `text-to-speech` capability.
   * The text is passed as a user message to the underlying provider.
   *
   * @param params - Speech synthesis parameters.
   * @returns Audio speech response with metadata.
   */
  async create(params: {
    model: string;
    input: string;
    voice: string;
    responseFormat?: string;
    speed?: number;
  }): Promise<AudioSpeechResponse> {
    const request: CompletionRequest = {
      model: params.model,
      messages: [{ role: 'user', content: params.input }],
      temperature: 0.0,
      stream: false,
      topP: 1.0,
    };

    const response = await this._client.mesh.route(request);

    const content = response.choices[0]?.message?.content ?? '';
    return createDefaultAudioSpeechResponse({
      format: params.responseFormat ?? 'mp3',
      model: response.model || params.model,
      inputCharacters: params.input.length,
      sizeBytes: response.usage?.completionTokens ?? 0,
    });
  }
}

class AudioTranscriptionsNamespace {
  private _client: MeshClient;

  constructor(client: MeshClient) {
    this._client = client;
  }

  /**
   * Transcribe audio to text (speech-to-text).
   *
   * Routes through a pool with the `speech-to-text` capability.
   * The audio URL is passed as a user message to the underlying provider.
   *
   * @param params - Transcription parameters.
   * @returns Transcription response with text and metadata.
   */
  async create(params: {
    model: string;
    file: string;
    language?: string;
    responseFormat?: string;
    prompt?: string;
  }): Promise<AudioTranscriptionResponse> {
    const request: CompletionRequest = {
      model: params.model,
      messages: [{ role: 'user', content: params.file }],
      temperature: 0.0,
      stream: false,
      topP: 1.0,
    };

    const response = await this._client.mesh.route(request);

    const content = response.choices[0]?.message?.content ?? '';
    return createDefaultAudioTranscriptionResponse({
      text: content,
      model: response.model || params.model,
    });
  }
}

class AudioNamespace {
  readonly speech: AudioSpeechNamespace;
  readonly transcriptions: AudioTranscriptionsNamespace;

  constructor(client: MeshClient) {
    this.speech = new AudioSpeechNamespace(client);
    this.transcriptions = new AudioTranscriptionsNamespace(client);
  }
}

// ---------------------------------------------------------------------------
// Models namespace
// ---------------------------------------------------------------------------

interface ModelEntry {
  id: string;
  object: string;
  owned_by: string;
}

interface ModelList {
  data: ModelEntry[];
  object: string;
}

class ModelsNamespace {
  private _client: MeshClient;

  constructor(client: MeshClient) {
    this._client = client;
  }

  /** List all available models. */
  list(): ModelList {
    const rawModels = this._client.mesh.listModels();
    const entries: ModelEntry[] = rawModels.map((m) => ({
      id: m.id,
      object: m.object ?? 'model',
      owned_by: m.owned_by ?? 'unknown',
    }));
    return { data: entries, object: 'list' };
  }
}

// ---------------------------------------------------------------------------
// MeshClient
// ---------------------------------------------------------------------------

/**
 * OpenAI SDK-compatible client backed by ModelMesh routing.
 *
 * Exposes the standard OpenAI namespaces (chat, embeddings, audio, models)
 * and ModelMesh extensions (mesh, poolStatus, activeProviders, rotate).
 */
export class MeshClient {
  private _mesh: ModelMesh;
  readonly chat: ChatNamespace;
  readonly embeddings: EmbeddingsNamespace;
  readonly audio: AudioNamespace;
  readonly models: ModelsNamespace;

  constructor(mesh: ModelMesh) {
    this._mesh = mesh;
    this.chat = new ChatNamespace(this);
    this.embeddings = new EmbeddingsNamespace(this);
    this.audio = new AudioNamespace(this);
    this.models = new ModelsNamespace(this);
  }

  /** Access the underlying ModelMesh instance for full control. */
  get mesh(): ModelMesh {
    return this._mesh;
  }

  /**
   * Return health status for pools.
   *
   * When *pool* is specified, returns just that pool's bare status
   * dict (matching the Python behavior). When omitted, returns a dict
   * mapping pool IDs to status dicts.
   */
  poolStatus(
    pool: string
  ): { active: number; standby: number; total: number; currentModel: string | null };
  poolStatus(): Record<
    string,
    { active: number; standby: number; total: number; currentModel: string | null }
  >;
  poolStatus(
    pool?: string
  ):
    | { active: number; standby: number; total: number; currentModel: string | null }
    | Record<string, { active: number; standby: number; total: number; currentModel: string | null }> {
    const allStatus = this._mesh.poolStatus();
    if (pool !== undefined) {
      if (!(pool in allStatus)) {
        throw new Error(`Pool '${pool}' not found`);
      }
      return allStatus[pool];
    }
    return allStatus;
  }

  /** Return the list of currently active provider connector IDs. */
  activeProviders(): string[] {
    return this._mesh.activeProviders();
  }

  /**
   * Describe the models and strategy behind each virtual model (pool).
   *
   * @param pool - If provided, describe only this pool. Otherwise all pools.
   * @returns Human-readable multi-line string showing pool composition.
   */
  describe(pool?: string): string {
    let pools = this._mesh.pools;
    if (pool !== undefined) {
      if (!(pool in pools)) {
        throw new Error(`Pool '${pool}' not found`);
      }
      pools = { [pool]: pools[pool] };
    }

    const lines: string[] = [];
    for (const [poolId, poolObj] of Object.entries(pools)) {
      const p = poolObj as CapabilityPool;
      const config = p.config ?? {};
      const strategy = (config as Record<string, unknown>).strategy ?? 'stick-until-failure';
      const cap = (config as Record<string, unknown>).capability ?? poolId;
      lines.push(`Pool "${poolId}" (strategy: ${strategy})`);
      lines.push(`  capability: ${cap}`);
      const models = p.models ?? [];
      for (let i = 0; i < models.length; i++) {
        const m = models[i];
        const marker = i === 0 && m.status === 'active' ? '\u2192' : ' ';
        lines.push(`  ${marker} ${m.modelId} [${m.providerId}] (${m.status})`);
      }
      if (models.length === 0) {
        lines.push('  (no models)');
      }
    }
    return lines.join('\n');
  }

  /**
   * Force an immediate rotation in a pool.
   *
   * @param pool - The pool ID to rotate.
   * @returns The model ID of the newly selected model, or null.
   */
  rotate(pool: string): string | null {
    return this._mesh.rotate(pool);
  }
}
