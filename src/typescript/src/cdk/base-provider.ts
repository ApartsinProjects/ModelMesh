/**
 * Base provider connector implementation.
 *
 * Implements a full provider interface with OpenAI-compatible default behavior.
 * Subclasses override protected hook methods to adapt to non-OpenAI APIs
 * without reimplementing transport, retries, or error classification.
 *
 * HTTP transport uses Node.js built-in http/https modules so the package
 * has zero external dependencies.
 */

import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';

import { RuntimeEnvironment } from '../interfaces/runtime';
import {
  ChatMessage,
  CompletionChoice,
  CompletionRequest,
  CompletionResponse,
  ErrorClassification,
  ModelInfo,
  ModelPricing,
  QuotaStatus,
  RateLimitStatus,
  TokenUsage,
  createDefaultCompletionResponse as createCompletionResponse,
  createDefaultTokenUsage as createTokenUsage,
} from '../interfaces/provider';

export interface BaseProviderConfig {
  baseUrl: string;
  apiKey: string;
  models: ModelInfo[];
  timeout: number;
  maxRetries: number;
  authMethod: string;
  retryableCodes: number[];
  nonRetryableCodes: number[];
  capabilities: string[];
}

export function createBaseProviderConfig(
  partial?: Partial<BaseProviderConfig>
): BaseProviderConfig {
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
 */
export class HttpError extends Error {
  public readonly statusCode: number;
  public readonly responseBody: string;
  public readonly headers: Record<string, string>;

  constructor(statusCode: number, responseBody: string, headers: Record<string, string> = {}) {
    super(`HTTP ${statusCode}: ${responseBody.substring(0, 200)}`);
    this.name = 'HttpError';
    this.statusCode = statusCode;
    this.responseBody = responseBody;
    this.headers = headers;
  }
}

/**
 * Base implementation of the ProviderConnector interface.
 *
 * Provides an OpenAI-compatible default behavior for all methods.
 * Subclasses override protected hook methods to adapt to non-OpenAI
 * APIs without reimplementing transport, retries, or error handling.
 */
export class BaseProvider {
  static readonly RUNTIME: RuntimeEnvironment = RuntimeEnvironment.NODE_ONLY;

  protected _config: BaseProviderConfig;
  protected _requestCount: number = 0;
  protected _tokensUsed: number = 0;
  protected _modelsByid: Map<string, ModelInfo>;

  constructor(config: BaseProviderConfig) {
    this._config = config;
    this._modelsByid = new Map();
    for (const m of config.models) {
      this._modelsByid.set(m.id, m);
    }
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

  async *stream(request: CompletionRequest): AsyncIterableIterator<CompletionResponse> {
    const payload = this._buildRequestPayload(request);
    payload.stream = true;
    const headers = this._buildHeaders();
    const endpoint = this._getCompletionEndpoint();

    const lines = await this._httpPostStream(endpoint, payload, headers);
    for (const line of lines) {
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
    const info = this._modelsByid.get(modelId);
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
    if (error instanceof HttpError) {
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
    return `${base}/v1/chat/completions`;
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

  // -- HTTP Transport (Node.js built-in) -------------------------------------

  protected _httpPost(
    url: string,
    payload: Record<string, any>,
    headers: Record<string, string>
  ): Promise<Record<string, any>> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify(payload);
      const parsedUrl = new URL(url);
      const transport = parsedUrl.protocol === 'https:' ? https : http;

      const options: http.RequestOptions = {
        method: 'POST',
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        headers: {
          ...headers,
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: this._config.timeout * 1000,
      };

      const req = transport.request(options, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const responseBody = Buffer.concat(chunks).toString('utf-8');
          const statusCode = res.statusCode || 0;
          if (statusCode >= 200 && statusCode < 300) {
            try {
              resolve(JSON.parse(responseBody));
            } catch {
              reject(new Error(`Invalid JSON response: ${responseBody.substring(0, 200)}`));
            }
          } else {
            const responseHeaders: Record<string, string> = {};
            for (const [key, value] of Object.entries(res.headers)) {
              if (typeof value === 'string') {
                responseHeaders[key.toLowerCase()] = value;
              }
            }
            reject(new HttpError(statusCode, responseBody, responseHeaders));
          }
        });
      });

      req.on('error', (err) => reject(err));
      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timed out after ${this._config.timeout}s`));
      });

      req.write(body);
      req.end();
    });
  }

  protected _httpPostStream(
    url: string,
    payload: Record<string, any>,
    headers: Record<string, string>
  ): Promise<string[]> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify(payload);
      const parsedUrl = new URL(url);
      const transport = parsedUrl.protocol === 'https:' ? https : http;

      const options: http.RequestOptions = {
        method: 'POST',
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        headers: {
          ...headers,
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: this._config.timeout * 1000,
      };

      const req = transport.request(options, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const responseBody = Buffer.concat(chunks).toString('utf-8');
          const statusCode = res.statusCode || 0;
          if (statusCode >= 200 && statusCode < 300) {
            resolve(responseBody.split(/\r?\n/));
          } else {
            const responseHeaders: Record<string, string> = {};
            for (const [key, value] of Object.entries(res.headers)) {
              if (typeof value === 'string') {
                responseHeaders[key.toLowerCase()] = value;
              }
            }
            reject(new HttpError(statusCode, responseBody, responseHeaders));
          }
        });
      });

      req.on('error', (err) => reject(err));
      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timed out after ${this._config.timeout}s`));
      });

      req.write(body);
      req.end();
    });
  }

  protected _httpPostRaw(
    url: string,
    payload: Record<string, any>,
    headers: Record<string, string>
  ): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      const body = JSON.stringify(payload);
      const parsedUrl = new URL(url);
      const transport = parsedUrl.protocol === 'https:' ? https : http;

      const options: http.RequestOptions = {
        method: 'POST',
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        headers: {
          ...headers,
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: this._config.timeout * 1000,
      };

      const req = transport.request(options, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const statusCode = res.statusCode || 0;
          if (statusCode >= 200 && statusCode < 300) {
            resolve(Buffer.concat(chunks));
          } else {
            const responseBody = Buffer.concat(chunks).toString('utf-8');
            const responseHeaders: Record<string, string> = {};
            for (const [key, value] of Object.entries(res.headers)) {
              if (typeof value === 'string') {
                responseHeaders[key.toLowerCase()] = value;
              }
            }
            reject(new HttpError(statusCode, responseBody, responseHeaders));
          }
        });
      });

      req.on('error', (err) => reject(err));
      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timed out after ${this._config.timeout}s`));
      });

      req.write(body);
      req.end();
    });
  }

  protected _httpGetJson(
    url: string,
    headers: Record<string, string>
  ): Promise<Record<string, any>> {
    return new Promise((resolve, reject) => {
      const parsedUrl = new URL(url);
      const transport = parsedUrl.protocol === 'https:' ? https : http;

      const options: http.RequestOptions = {
        method: 'GET',
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        headers,
        timeout: this._config.timeout * 1000,
      };

      const req = transport.request(options, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const responseBody = Buffer.concat(chunks).toString('utf-8');
          const statusCode = res.statusCode || 0;
          if (statusCode >= 200 && statusCode < 300) {
            try {
              resolve(JSON.parse(responseBody));
            } catch {
              reject(new Error(`Invalid JSON response: ${responseBody.substring(0, 200)}`));
            }
          } else {
            const responseHeaders: Record<string, string> = {};
            for (const [key, value] of Object.entries(res.headers)) {
              if (typeof value === 'string') {
                responseHeaders[key.toLowerCase()] = value;
              }
            }
            reject(new HttpError(statusCode, responseBody, responseHeaders));
          }
        });
      });

      req.on('error', (err) => reject(err));
      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timed out after ${this._config.timeout}s`));
      });

      req.end();
    });
  }

  protected _httpGetText(
    url: string,
    headers: Record<string, string>
  ): Promise<string | Record<string, any>> {
    return new Promise((resolve, reject) => {
      const parsedUrl = new URL(url);
      const transport = parsedUrl.protocol === 'https:' ? https : http;

      const options: http.RequestOptions = {
        method: 'GET',
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        headers,
        timeout: this._config.timeout * 1000,
      };

      const req = transport.request(options, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const responseBody = Buffer.concat(chunks).toString('utf-8');
          const statusCode = res.statusCode || 0;
          if (statusCode >= 200 && statusCode < 300) {
            try {
              resolve(JSON.parse(responseBody));
            } catch {
              resolve(responseBody);
            }
          } else {
            const responseHeaders: Record<string, string> = {};
            for (const [key, value] of Object.entries(res.headers)) {
              if (typeof value === 'string') {
                responseHeaders[key.toLowerCase()] = value;
              }
            }
            reject(new HttpError(statusCode, responseBody, responseHeaders));
          }
        });
      });

      req.on('error', (err) => reject(err));
      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Request timed out after ${this._config.timeout}s`));
      });

      req.end();
    });
  }

  protected _sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
