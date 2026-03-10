/**
 * Browser-compatible base provider implementation.
 *
 * Identical interface and behavior to BaseProvider, but uses the Fetch API
 * instead of Node.js http/https modules. Works in any environment that
 * supports fetch() — browsers, Deno, Cloudflare Workers, Bun, etc.
 *
 * Supports an optional `proxyUrl` config field for CORS proxy support.
 * When set, all API URLs are prefixed with the proxy URL.
 */

import { RuntimeEnvironment } from '../interfaces/runtime';
import {
  ChatMessage,
  CompletionChoice,
  CompletionRequest,
  CompletionResponse,
  ErrorClassification,
  ModelInfo,
  ModelPricing,
  ProviderConnector,
  QuotaStatus,
  RateLimitStatus,
  TokenUsage,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../interfaces/provider';

export interface BrowserProviderConfig {
  baseUrl: string;
  apiKey: string;
  models: ModelInfo[];
  timeout: number;
  maxRetries: number;
  authMethod: string;
  retryableCodes: number[];
  nonRetryableCodes: number[];
  capabilities: string[];
  /** Optional CORS proxy URL prefix. When set, all API URLs are prefixed. */
  proxyUrl?: string;
}

export function createBrowserProviderConfig(
  partial?: Partial<BrowserProviderConfig>
): BrowserProviderConfig {
  return {
    baseUrl: '',
    apiKey: '',
    models: [],
    timeout: 30,
    maxRetries: 3,
    authMethod: 'api_key',
    retryableCodes: [429, 500, 502, 503],
    nonRetryableCodes: [400, 401, 403],
    capabilities: ['generation.text-generation.chat-completion'],
    ...partial,
  };
}

/**
 * Error class for HTTP errors with a status code.
 * Browser-compatible version (identical to Node HttpError).
 */
export class BrowserHttpError extends Error {
  public readonly statusCode: number;
  public readonly responseBody: string;
  public readonly headers: Record<string, string>;

  constructor(statusCode: number, responseBody: string, headers: Record<string, string> = {}) {
    super(`HTTP ${statusCode}: ${responseBody.substring(0, 200)}`);
    this.name = 'BrowserHttpError';
    this.statusCode = statusCode;
    this.responseBody = responseBody;
    this.headers = headers;
  }
}

/**
 * Browser-compatible base provider using the Fetch API.
 *
 * Drop-in replacement for BaseProvider that works in browsers.
 * Uses fetch() for HTTP requests and ReadableStream for SSE streaming.
 *
 * @example
 * class MyBrowserProvider extends BrowserBaseProvider {
 *   protected _getCompletionEndpoint(): string {
 *     return this._resolveUrl(`${this._config.baseUrl}/v1/chat/completions`);
 *   }
 * }
 *
 * const provider = new MyBrowserProvider(createBrowserProviderConfig({
 *   baseUrl: 'https://api.openai.com',
 *   apiKey: userEnteredKey,
 *   proxyUrl: 'http://localhost:3000/proxy/',
 * }));
 */
export class BrowserBaseProvider implements ProviderConnector {
  static readonly RUNTIME: RuntimeEnvironment = RuntimeEnvironment.UNIVERSAL;

  protected _config: BrowserProviderConfig;
  protected _requestCount: number = 0;
  protected _tokensUsed: number = 0;
  protected _modelsById: Map<string, ModelInfo>;

  constructor(config: BrowserProviderConfig) {
    this._config = config;
    this._modelsById = new Map();
    for (const m of config.models) {
      this._modelsById.set(m.id, m);
    }
  }

  // -- URL Resolution ---------------------------------------------------------

  /**
   * Resolve a URL through the optional CORS proxy.
   * If proxyUrl is set, prepends it to the target URL.
   */
  protected _resolveUrl(url: string): string {
    if (this._config.proxyUrl) {
      const proxy = this._config.proxyUrl.replace(/\/+$/, '');
      return `${proxy}/${url}`;
    }
    return url;
  }

  // -- Model Execution -------------------------------------------------------

  async complete(request: CompletionRequest): Promise<CompletionResponse> {
    const payload = this._buildRequestPayload(request);
    const headers = this._buildHeaders();
    const endpoint = this._getCompletionEndpoint();

    let lastError: Error | null = null;
    for (let attempt = 0; attempt <= this._config.maxRetries; attempt++) {
      try {
        const data = await this._httpPost(endpoint, payload, headers);
        const result = this._parseResponse(data);
        this.reportUsage(request.model, result.usage);
        return result;
      } catch (exc: any) {
        lastError = exc;
        const classification = this.classifyError(exc);
        if (!classification.retryable || attempt === this._config.maxRetries) {
          throw exc;
        }
        let retryAfter: number = Math.pow(2, attempt);
        if (exc instanceof BrowserHttpError && exc.headers['retry-after']) {
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

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionResponse> {
    const payload = this._buildRequestPayload(request);
    payload.stream = true;
    const headers = this._buildHeaders();
    const endpoint = this._getCompletionEndpoint();

    // Use streaming fetch with ReadableStream
    for await (const line of this._httpPostStreamLines(endpoint, payload, headers)) {
      if (!line || !line.startsWith('data: ')) {
        continue;
      }
      const dataStr = line.substring(6);
      if (dataStr.trim() === '[DONE]') {
        break;
      }
      const chunk = this._parseSseChunk(dataStr);
      if (chunk !== null) {
        yield chunk;
      }
    }
  }

  // -- Capabilities ----------------------------------------------------------

  getCapabilities(): string[] {
    return [...this._config.capabilities];
  }

  supports(capability: string): boolean {
    return this._config.capabilities.includes(capability);
  }

  // -- Model Catalogue -------------------------------------------------------

  listModels(): ModelInfo[] {
    return [...this._config.models];
  }

  getModelInfo(modelId: string): ModelInfo {
    const info = this._modelsById.get(modelId);
    if (!info) {
      throw new Error(`Model not found: ${modelId}`);
    }
    return info;
  }

  // -- Quota & Rate Limits ---------------------------------------------------

  checkQuota(): QuotaStatus {
    return { used: this._requestCount };
  }

  getRateLimits(): RateLimitStatus {
    return {};
  }

  // -- Cost & Pricing --------------------------------------------------------

  getPricing(modelId: string): ModelPricing {
    const info = this.getModelInfo(modelId);
    if (!info.pricing) {
      throw new Error(`No pricing configured for model: ${modelId}`);
    }
    return info.pricing;
  }

  reportUsage(modelId: string, usage: TokenUsage): void {
    this._requestCount += 1;
    this._tokensUsed += usage.totalTokens;
  }

  // -- Error Classification --------------------------------------------------

  classifyError(error: Error): ErrorClassification {
    let statusCode: number | undefined;
    if (error instanceof BrowserHttpError) {
      statusCode = error.statusCode;
    }

    if (statusCode === undefined) {
      return { retryable: false, category: 'unknown', message: error.message };
    }

    if (this._config.retryableCodes.includes(statusCode)) {
      return {
        retryable: true,
        errorCode: statusCode,
        category: statusCode === 429 ? 'rate_limit' : 'server',
        message: error.message,
      };
    }

    if (this._config.nonRetryableCodes.includes(statusCode)) {
      const category = statusCode === 401 || statusCode === 403 ? 'auth' : 'client';
      return {
        retryable: false,
        errorCode: statusCode,
        category,
        message: error.message,
      };
    }

    return {
      retryable: false,
      errorCode: statusCode,
      category: 'unknown',
      message: error.message,
    };
  }

  isRetryable(error: Error): boolean {
    return this.classifyError(error).retryable;
  }

  // -- Protected Hooks -------------------------------------------------------

  protected _buildRequestPayload(request: CompletionRequest): Record<string, any> {
    const payload: Record<string, any> = {
      model: request.model,
      messages: request.messages,
    };
    if (request.temperature !== undefined) {
      payload.temperature = request.temperature;
    }
    if (request.maxTokens != null) {
      payload.max_tokens = request.maxTokens;
    }
    if (request.tools && request.tools.length > 0) {
      payload.tools = request.tools;
    }
    if (request.stream) {
      payload.stream = true;
    }
    return payload;
  }

  protected _parseResponse(data: Record<string, any>): CompletionResponse {
    const usageData = data.usage || {};
    const rawChoices = data.choices || [];
    const choices: CompletionChoice[] = [];
    for (const raw of rawChoices) {
      const msg = raw.message;
      choices.push({
        index: raw.index ?? 0,
        message: msg
          ? { role: msg.role || 'assistant', content: msg.content ?? undefined }
          : undefined,
        finishReason: raw.finish_reason ?? undefined,
      });
    }
    return createCompletionResponse({
      id: data.id || '',
      model: data.model || '',
      choices,
      usage: createTokenUsage({
        promptTokens: usageData.prompt_tokens || 0,
        completionTokens: usageData.completion_tokens || 0,
        totalTokens: usageData.total_tokens || 0,
      }),
    });
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

  protected _getCompletionEndpoint(): string {
    const base = this._config.baseUrl.replace(/\/+$/, '');
    return this._resolveUrl(`${base}/v1/chat/completions`);
  }

  protected _parseSseChunk(line: string): CompletionResponse | null {
    let data: Record<string, any>;
    try {
      data = JSON.parse(line);
    } catch {
      return null;
    }
    const rawChoices = data.choices || [];
    if (rawChoices.length === 0) {
      return null;
    }
    const choices: CompletionChoice[] = [];
    for (const raw of rawChoices) {
      const delta = raw.delta;
      choices.push({
        index: raw.index ?? 0,
        delta: delta
          ? { role: delta.role || 'assistant', content: delta.content ?? undefined }
          : undefined,
        finishReason: raw.finish_reason ?? undefined,
      });
    }
    return createCompletionResponse({
      id: data.id || '',
      model: data.model || '',
      choices,
      usage: createTokenUsage(),
    });
  }

  async close(): Promise<void> {
    // No-op by default
  }

  // -- HTTP Transport (Fetch API) ---------------------------------------------

  protected async _httpPost(
    url: string,
    payload: Record<string, any>,
    headers: Record<string, string>
  ): Promise<Record<string, any>> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this._config.timeout * 1000);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      const responseBody = await response.text();

      if (response.ok) {
        try {
          return JSON.parse(responseBody);
        } catch {
          throw new Error(`Invalid JSON response: ${responseBody.substring(0, 200)}`);
        }
      }

      const responseHeaders: Record<string, string> = {};
      response.headers.forEach((value, key) => {
        responseHeaders[key.toLowerCase()] = value;
      });
      throw new BrowserHttpError(response.status, responseBody, responseHeaders);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error(`Request timed out after ${this._config.timeout}s`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Stream SSE lines from a POST request using the Fetch API ReadableStream.
   * Yields individual lines as they arrive.
   */
  protected async *_httpPostStreamLines(
    url: string,
    payload: Record<string, any>,
    headers: Record<string, string>
  ): AsyncIterableIterator<string> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this._config.timeout * 1000);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!response.ok) {
        const responseBody = await response.text();
        const responseHeaders: Record<string, string> = {};
        response.headers.forEach((value, key) => {
          responseHeaders[key.toLowerCase()] = value;
        });
        throw new BrowserHttpError(response.status, responseBody, responseHeaders);
      }

      if (!response.body) {
        // Fallback: read entire response at once
        const text = await response.text();
        for (const line of text.split(/\r?\n/)) {
          yield line;
        }
        return;
      }

      // Stream using ReadableStream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Split on newlines
        const lines = buffer.split(/\r?\n/);
        // Keep the last partial line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          yield line;
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        yield buffer;
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error(`Request timed out after ${this._config.timeout}s`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  protected async _httpGetJson(
    url: string,
    headers: Record<string, string>
  ): Promise<Record<string, any>> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this._config.timeout * 1000);

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers,
        signal: controller.signal,
      });

      const responseBody = await response.text();

      if (response.ok) {
        try {
          return JSON.parse(responseBody);
        } catch {
          throw new Error(`Invalid JSON response: ${responseBody.substring(0, 200)}`);
        }
      }

      const responseHeaders: Record<string, string> = {};
      response.headers.forEach((value, key) => {
        responseHeaders[key.toLowerCase()] = value;
      });
      throw new BrowserHttpError(response.status, responseBody, responseHeaders);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error(`Request timed out after ${this._config.timeout}s`);
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  protected _sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
