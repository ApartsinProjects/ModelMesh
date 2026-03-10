/**
 * Pre-shipped Jina AI provider connector.
 *
 * Wraps multiple Jina AI services (Reader, Search, Embeddings, Reranker)
 * as a single ModelMesh provider. Different models route to different
 * Jina endpoints, allowing content extraction, web search, embedding
 * generation, and reranking through the unified chat completions interface.
 *
 * Connector ID: "jina.ai.v1"
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
  TokenUsage,
  createDefaultModelInfo as createModelInfo,
  createDefaultModelPricing as createModelPricing,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'jina-reader',
    name: 'Jina Reader',
    capabilities: ['understanding.document-understanding.content-extraction'],
    features: { url_extraction: true },
    contextWindow: 0,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.002 }),
  }),
  createModelInfo({
    id: 'jina-search',
    name: 'Jina Search',
    capabilities: ['retrieval.semantic-search.web-search'],
    features: { web_search: true },
    contextWindow: 2048,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.005 }),
  }),
  createModelInfo({
    id: 'jina-embeddings-v3',
    name: 'Jina Embeddings v3',
    capabilities: ['representation.embeddings.text-embeddings'],
    features: { embedding_generation: true },
    contextWindow: 8192,
    maxOutputTokens: 0,
    pricing: createModelPricing({ inputPer1kTokens: 0.00002 }),
  }),
  createModelInfo({
    id: 'jina-reranker-v2-base-multilingual',
    name: 'Jina Reranker v2 Base Multilingual',
    capabilities: ['retrieval.reranking'],
    features: { multilingual: true },
    contextWindow: 8192,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.002 }),
  }),
];

export interface JinaProviderConfig extends BaseProviderConfig {
  readerBaseUrl: string;
  searchBaseUrl: string;
}

export function createJinaProviderConfig(
  partial?: Partial<JinaProviderConfig>
): JinaProviderConfig {
  return {
    ...createBaseProviderConfig({
      baseUrl: 'https://api.jina.ai',
      models: [...DEFAULT_MODELS],
      capabilities: [
        'understanding.document-understanding.content-extraction',
        'retrieval.semantic-search.web-search',
        'representation.embeddings.text-embeddings',
        'retrieval.reranking',
      ],
    }),
    readerBaseUrl: 'https://r.jina.ai',
    searchBaseUrl: 'https://s.jina.ai',
    ...partial,
  } as JinaProviderConfig;
}

export class JinaProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'jina.ai.v1';
  private _jinaConfig: JinaProviderConfig;
  private _currentModel: string = '';

  constructor(config?: Partial<JinaProviderConfig>) {
    const fullConfig = createJinaProviderConfig(config);
    super(fullConfig);
    this._jinaConfig = fullConfig;
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/v1/embeddings`;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };
    if (this._config.apiKey) {
      headers['Authorization'] = `Bearer ${this._config.apiKey}`;
    }
    return headers;
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    let content = '';
    if (request.messages.length > 0) {
      const lastMsg = request.messages[request.messages.length - 1];
      content = String(lastMsg.content || '');
    }

    if (request.model === 'jina-embeddings-v3') {
      return {
        model: 'jina-embeddings-v3',
        input: [content],
      };
    } else if (request.model === 'jina-reranker-v2-base-multilingual') {
      let query = content;
      let documents: any[] = [];
      try {
        const parsed = JSON.parse(content);
        query = parsed.query || content;
        documents = parsed.documents || [];
      } catch {
        query = content;
        documents = [];
      }
      return {
        model: 'jina-reranker-v2-base-multilingual',
        query,
        documents,
      };
    } else {
      return { content };
    }
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    let contentText = '';

    if (data.data && Array.isArray(data.data)) {
      const items = data.data;
      if (items.length > 0 && 'embedding' in items[0]) {
        const embeddings = items.map((item: any) => item.embedding || []);
        contentText = JSON.stringify({ embeddings });
      } else if (items.length > 0 && 'relevance_score' in items[0]) {
        const parts: string[] = ['Reranked Results:'];
        for (let i = 0; i < items.length; i++) {
          const item = items[i];
          const score = item.relevance_score || 0.0;
          const doc = item.document || {};
          const text = typeof doc === 'object' ? doc.text || '' : String(doc);
          parts.push(`\n[${i + 1}] Score: ${score.toFixed(4)}`);
          if (text) {
            parts.push(`    ${text}`);
          }
        }
        contentText = parts.join('\n');
      } else {
        contentText = JSON.stringify(data);
      }
    } else if ('content' in data) {
      contentText = data.content || '';
    } else if ('results' in data) {
      const parts = ['Search Results:'];
      const results = data.results || [];
      for (let i = 0; i < results.length; i++) {
        const result = results[i];
        const title = result.title || 'Untitled';
        const url = result.url || '';
        const content = result.content || result.description || '';
        parts.push(`\n[${i + 1}] ${title}`);
        if (url) {
          parts.push(`    URL: ${url}`);
        }
        if (content) {
          parts.push(`    ${content}`);
        }
      }
      contentText = parts.join('\n');
    } else {
      contentText = JSON.stringify(data);
    }

    if (!contentText) {
      contentText = 'No results returned.';
    }

    const promptTokens = Math.max(1, Math.floor(contentText.length / 10));
    const completionTokens = Math.max(1, Math.floor(contentText.length / 4));

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
      finishReason: 'stop',
    };

    return createCompletionResponse({
      id: `jina-${randomBytes(6).toString('hex')}`,
      model: this._currentModel || 'jina',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      }),
    });
  }

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    this._currentModel = request.model;

    let content = '';
    if (request.messages.length > 0) {
      const lastMsg = request.messages[request.messages.length - 1];
      content = String(lastMsg.content || '');
    }

    if (request.model === 'jina-reader') {
      return this._handleReader(content);
    } else if (request.model === 'jina-search') {
      return this._handleSearch(content);
    } else {
      // Embeddings and Reranker use standard POST via BaseProvider
      // Set the correct endpoint for the model
      const base = this._config.baseUrl.replace(/\/+$/, '');
      if (request.model === 'jina-reranker-v2-base-multilingual') {
        this._currentEndpoint = `${base}/v1/rerank`;
      } else {
        this._currentEndpoint = `${base}/v1/embeddings`;
      }
      return super.complete(request);
    }
  }

  private _currentEndpoint: string = '';

  protected _getCompletionEndpointForModel(): string {
    if (this._currentEndpoint) {
      return this._currentEndpoint;
    }
    return this._getCompletionEndpoint();
  }

  private async _handleReader(url: string): Promise<CompletionResponse> {
    const readerUrl = `${this._jinaConfig.readerBaseUrl.replace(/\/+$/, '')}/${url}`;
    const headers = this._buildHeaders();
    const data = await this._httpGetText(readerUrl, headers);

    const contentText = typeof data === 'string' ? data : JSON.stringify(data);
    const promptTokens = Math.max(1, Math.floor(url.length / 4));
    const completionTokens = Math.max(1, Math.floor(contentText.length / 4));

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
      finishReason: 'stop',
    };

    const result = createCompletionResponse({
      id: `jina-reader-${randomBytes(6).toString('hex')}`,
      model: 'jina-reader',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      }),
    });
    this.reportUsage('jina-reader', result.usage);
    return result;
  }

  private async _handleSearch(query: string): Promise<CompletionResponse> {
    const encodedQuery = encodeURIComponent(query);
    const searchUrl = `${this._jinaConfig.searchBaseUrl.replace(/\/+$/, '')}/${encodedQuery}`;
    const headers = this._buildHeaders();
    const data = await this._httpGetText(searchUrl, headers);

    let contentText: string;
    if (typeof data === 'string') {
      contentText = data;
    } else if (typeof data === 'object') {
      const parsed = this._parseResponse(data as Record<string, any>);
      contentText = parsed.choices[0]?.message?.content || '';
    } else {
      contentText = String(data);
    }

    const promptTokens = Math.max(1, Math.floor(query.length / 4));
    const completionTokens = Math.max(1, Math.floor(contentText.length / 4));

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
      finishReason: 'stop',
    };

    const result = createCompletionResponse({
      id: `jina-search-${randomBytes(6).toString('hex')}`,
      model: 'jina-search',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      }),
    });
    this.reportUsage('jina-search', result.usage);
    return result;
  }
}
