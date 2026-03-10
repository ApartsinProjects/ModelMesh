/**
 * Pre-shipped Tavily web search provider connector.
 *
 * Wraps the Tavily Search API as a ModelMesh provider so web search
 * capabilities can participate in capability pools. The search query
 * is extracted from the last message's content, and results are returned
 * as formatted text in a CompletionResponse.
 *
 * Connector ID: "tavily.search.v1"
 */

import { randomBytes } from 'crypto';
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
  createDefaultModelPricing as createModelPricing,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../../interfaces/provider';

const DEFAULT_MODELS: ModelInfo[] = [
  createModelInfo({
    id: 'tavily-search',
    name: 'Tavily Search (Advanced)',
    capabilities: ['retrieval.semantic-search.web-search'],
    features: { include_answer: true, search_depth: true },
    contextWindow: 400,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.01 }),
  }),
  createModelInfo({
    id: 'tavily-search-basic',
    name: 'Tavily Search (Basic)',
    capabilities: ['retrieval.semantic-search.web-search'],
    features: { include_answer: true, search_depth: false },
    contextWindow: 400,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.005 }),
  }),
];

export interface TavilyProviderConfig extends BaseProviderConfig {
  maxResults: number;
}

export function createTavilyProviderConfig(
  partial?: Partial<TavilyProviderConfig>
): TavilyProviderConfig {
  return {
    ...createBaseProviderConfig({
      baseUrl: 'https://api.tavily.com',
      models: [...DEFAULT_MODELS],
      capabilities: ['retrieval.semantic-search.web-search'],
    }),
    maxResults: 5,
    ...partial,
  } as TavilyProviderConfig;
}

export class TavilyProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'tavily.search.v1';
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;
  private _tavilyConfig: TavilyProviderConfig;

  constructor(config?: Partial<TavilyProviderConfig>) {
    const fullConfig = createTavilyProviderConfig(config);
    super(fullConfig);
    this._tavilyConfig = fullConfig;
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/search`;
  }

  protected _buildHeaders(): Record<string, string> {
    return { 'Content-Type': 'application/json' };
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    let query = '';
    if (request.messages.length > 0) {
      const lastMsg = request.messages[request.messages.length - 1];
      query = String(lastMsg.content || '');
    }

    const searchDepth = request.model === 'tavily-search-basic' ? 'basic' : 'advanced';

    return {
      api_key: this._config.apiKey,
      query,
      search_depth: searchDepth,
      include_answer: true,
      max_results: this._tavilyConfig.maxResults,
    };
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    const parts: string[] = [];

    const answer = data.answer;
    if (answer) {
      parts.push(`Answer: ${answer}`);
      parts.push('');
    }

    const results = data.results || [];
    if (results.length > 0) {
      parts.push('Sources:');
      for (let i = 0; i < results.length; i++) {
        const result = results[i];
        const title = result.title || 'Untitled';
        const url = result.url || '';
        const content = result.content || '';
        parts.push(`\n[${i + 1}] ${title}`);
        if (url) {
          parts.push(`    URL: ${url}`);
        }
        if (content) {
          parts.push(`    ${content}`);
        }
      }
    }

    const contentText = parts.length > 0 ? parts.join('\n') : 'No results found.';

    const queryChars = (data.query || '').length;
    const responseChars = contentText.length;
    const promptTokens = Math.max(1, Math.floor(queryChars / 4));
    const completionTokens = Math.max(1, Math.floor(responseChars / 4));

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
      finishReason: 'stop',
    };

    return createCompletionResponse({
      id: `tavily-${randomBytes(6).toString('hex')}`,
      model: data.query || 'tavily-search',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      }),
    });
  }
}
