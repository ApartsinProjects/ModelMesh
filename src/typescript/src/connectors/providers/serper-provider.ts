/**
 * Pre-shipped Serper (Google Search) provider connector.
 *
 * Wraps the Serper.dev Google Search API as a ModelMesh provider so web
 * search capabilities can participate in capability pools. The search
 * query is extracted from the last message's content, and results are
 * returned as formatted text in a CompletionResponse.
 *
 * Connector ID: "serper.search.v1"
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
    id: 'serper-google-search',
    name: 'Serper Google Search',
    capabilities: ['retrieval.semantic-search.web-search'],
    features: { answer_box: true, organic_results: true },
    contextWindow: 2048,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.001 }),
  }),
];

export interface SerperProviderConfig extends BaseProviderConfig {}

export function createSerperProviderConfig(
  partial?: Partial<SerperProviderConfig>
): SerperProviderConfig {
  return createBaseProviderConfig({
    baseUrl: 'https://google.serper.dev',
    models: [...DEFAULT_MODELS],
    capabilities: ['retrieval.semantic-search.web-search'],
    ...partial,
  });
}

export class SerperProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'serper.search.v1';

  constructor(config?: Partial<SerperProviderConfig>) {
    super(createSerperProviderConfig(config));
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/search`;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this._config.apiKey) {
      headers['X-API-KEY'] = this._config.apiKey;
    }
    return headers;
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    let query = '';
    if (request.messages.length > 0) {
      const lastMsg = request.messages[request.messages.length - 1];
      query = String(lastMsg.content || '');
    }

    return { q: query };
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    const parts: string[] = [];

    // Include the answer box if present
    const answerBox = data.answerBox;
    if (answerBox) {
      const answer = answerBox.answer || answerBox.snippet || '';
      if (answer) {
        parts.push(`Answer: ${answer}`);
        parts.push('');
      }
    }

    // Include knowledge graph if present
    const knowledgeGraph = data.knowledgeGraph;
    if (knowledgeGraph) {
      const kgTitle = knowledgeGraph.title || '';
      const kgDesc = knowledgeGraph.description || '';
      if (kgTitle) {
        parts.push(kgTitle);
      }
      if (kgDesc) {
        parts.push(kgDesc);
      }
      if (kgTitle || kgDesc) {
        parts.push('');
      }
    }

    // Format organic search results
    const organic = data.organic || [];
    if (organic.length > 0) {
      parts.push('Search Results:');
      for (let i = 0; i < organic.length; i++) {
        const result = organic[i];
        const title = result.title || 'Untitled';
        const link = result.link || '';
        const snippet = result.snippet || '';
        parts.push(`\n[${i + 1}] ${title}`);
        if (link) {
          parts.push(`    URL: ${link}`);
        }
        if (snippet) {
          parts.push(`    ${snippet}`);
        }
      }
    }

    const contentText = parts.length > 0 ? parts.join('\n') : 'No results found.';

    const queryText = (data.searchParameters || {}).q || '';
    const promptTokens = Math.max(1, Math.floor(queryText.length / 4));
    const completionTokens = Math.max(1, Math.floor(contentText.length / 4));

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
      finishReason: 'stop',
    };

    return createCompletionResponse({
      id: `serper-${randomBytes(6).toString('hex')}`,
      model: 'serper-google-search',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      }),
    });
  }
}
