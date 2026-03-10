/**
 * Pre-shipped Firecrawl web scraping provider connector.
 *
 * Wraps the Firecrawl API as a ModelMesh provider so web scraping and
 * crawling capabilities can participate in capability pools. The target
 * URL is extracted from the last message's content, and the scraped
 * markdown content is returned in a CompletionResponse.
 *
 * Connector ID: "firecrawl.scrape.v1"
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
    id: 'firecrawl-scrape',
    name: 'Firecrawl Scrape',
    capabilities: ['understanding.document-understanding.content-extraction'],
    features: { markdown_output: true, single_page: true },
    contextWindow: 0,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.001 }),
  }),
  createModelInfo({
    id: 'firecrawl-crawl',
    name: 'Firecrawl Crawl',
    capabilities: ['understanding.document-understanding.content-extraction'],
    features: { markdown_output: true, multi_page: true },
    contextWindow: 0,
    maxOutputTokens: 0,
    pricing: createModelPricing({ perRequest: 0.005 }),
  }),
];

export interface FirecrawlProviderConfig extends BaseProviderConfig {
  outputFormats: string[];
}

export function createFirecrawlProviderConfig(
  partial?: Partial<FirecrawlProviderConfig>
): FirecrawlProviderConfig {
  return {
    ...createBaseProviderConfig({
      baseUrl: 'https://api.firecrawl.dev',
      models: [...DEFAULT_MODELS],
      capabilities: ['understanding.document-understanding.content-extraction'],
    }),
    outputFormats: ['markdown'],
    ...partial,
  } as FirecrawlProviderConfig;
}

export class FirecrawlProvider extends BaseProvider {
  static readonly CONNECTOR_ID = 'firecrawl.scrape.v1';
  private _firecrawlConfig: FirecrawlProviderConfig;

  constructor(config?: Partial<FirecrawlProviderConfig>) {
    const fullConfig = createFirecrawlProviderConfig(config);
    super(fullConfig);
    this._firecrawlConfig = fullConfig;
  }

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return `${base}/v1/scrape`;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this._config.apiKey) {
      headers['Authorization'] = `Bearer ${this._config.apiKey}`;
    }
    return headers;
  }

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    let url = '';
    if (request.messages.length > 0) {
      const lastMsg = request.messages[request.messages.length - 1];
      url = String(lastMsg.content || '').trim();
    }

    return {
      url,
      formats: [...this._firecrawlConfig.outputFormats],
    };
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    const scrapeData = data.data || {};

    let contentText =
      scrapeData.markdown ||
      scrapeData.html ||
      scrapeData.rawHtml ||
      scrapeData.content ||
      '';

    if (!contentText) {
      contentText = 'No content extracted from the URL.';
    }

    // Include metadata if available
    const metadata = scrapeData.metadata || {};
    if (metadata && Object.keys(metadata).length > 0) {
      const metaParts: string[] = [];
      const title = metadata.title;
      const description = metadata.description;
      if (title) {
        metaParts.push(`Title: ${title}`);
      }
      if (description) {
        metaParts.push(`Description: ${description}`);
      }
      if (metaParts.length > 0) {
        contentText = metaParts.join('\n') + '\n\n' + contentText;
      }
    }

    const promptTokens = Math.max(1, Math.floor((scrapeData.url || '').length / 4));
    const completionTokens = Math.max(1, Math.floor(contentText.length / 4));

    const choice: CompletionChoice = {
      index: 0,
      message: { role: 'assistant', content: contentText },
      finishReason: 'stop',
    };

    return createCompletionResponse({
      id: `firecrawl-${randomBytes(6).toString('hex')}`,
      model: 'firecrawl-scrape',
      choices: [choice],
      usage: createTokenUsage({
        promptTokens,
        completionTokens,
        totalTokens: promptTokens + completionTokens,
      }),
    });
  }
}
