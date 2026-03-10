/**
 * ProxyServer -- OpenAI-compatible HTTP proxy backed by ModelMesh.
 *
 * Implements a zero-dependency HTTP server (Node.js built-in http module)
 * that translates incoming OpenAI REST API requests into ModelMesh routing
 * calls. Supports chat completions (streaming and non-streaming), models
 * listing, embeddings, audio speech, and audio transcriptions.
 */

import * as http from 'http';
import { ModelMesh } from '../core/mesh';
import { MeshConfig } from '../config/mesh-config';
import type {
  CompletionRequest,
  CompletionResponse,
} from '../interfaces/provider';

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

export interface ServerStatus {
  running: boolean;
  host: string;
  port: number;
  uptime_seconds: number;
  active_connections: number;
  total_requests: number;
}

// ---------------------------------------------------------------------------
// Serialization helpers
// ---------------------------------------------------------------------------

function completionResponseToDict(resp: CompletionResponse): Record<string, unknown> {
  const choices = resp.choices.map((choice) => {
    const c: Record<string, unknown> = {
      index: choice.index,
      finish_reason: choice.finishReason,
    };
    if (choice.message) {
      const msg: Record<string, unknown> = {
        role: choice.message.role,
        content: choice.message.content,
      };
      if (choice.message.toolCalls) {
        msg.tool_calls = choice.message.toolCalls;
      }
      c.message = msg;
    }
    if (choice.delta) {
      const d: Record<string, unknown> = {
        role: choice.delta.role,
        content: choice.delta.content,
      };
      if (choice.delta.toolCalls) {
        d.tool_calls = choice.delta.toolCalls;
      }
      c.delta = d;
    }
    return c;
  });

  return {
    id: resp.id || 'chatcmpl-' + Math.random().toString(36).slice(2, 14),
    object: resp.object,
    created: resp.created || Math.floor(Date.now() / 1000),
    model: resp.model,
    choices,
    usage: {
      prompt_tokens: resp.usage.promptTokens,
      completion_tokens: resp.usage.completionTokens,
      total_tokens: resp.usage.totalTokens,
    },
  };
}

// ---------------------------------------------------------------------------
// ProxyServer
// ---------------------------------------------------------------------------

/**
 * OpenAI-compatible HTTP proxy server backed by ModelMesh.
 *
 * Wraps a Node.js http.Server and translates OpenAI REST API requests into
 * ModelMesh routing calls. Zero external dependencies.
 *
 * Usage:
 *
 *   const server = new ProxyServer({
 *     config: meshConfig,
 *     port: 8080,
 *   });
 *   await server.start();
 *   // ...
 *   server.stop();
 */
export class ProxyServer {
  private _mesh: ModelMesh;
  private _host: string;
  private _port: number;
  private _token: string | undefined;
  private _server: http.Server | null = null;
  private _startTime: number | null = null;
  private _activeConnections = 0;
  private _totalRequests = 0;

  constructor(options: {
    config: MeshConfig | Record<string, unknown> | string;
    host?: string;
    port?: number;
    token?: string;
  }) {
    let meshConfig: MeshConfig;
    if (typeof options.config === 'string') {
      meshConfig = MeshConfig.fromFile(options.config);
    } else if (options.config instanceof MeshConfig) {
      meshConfig = options.config;
    } else {
      meshConfig = MeshConfig.fromDict(options.config);
    }

    this._mesh = new ModelMesh();
    this._mesh.initialize(meshConfig);
    this._host = options.host ?? '0.0.0.0';
    this._port = options.port ?? 8080;
    this._token = options.token;
  }

  /** The underlying ModelMesh instance. */
  get mesh(): ModelMesh {
    return this._mesh;
  }

  /**
   * Start the HTTP server.
   *
   * @param block - If true (default), returns a Promise that resolves
   *     when the server is listening. If false, starts immediately.
   */
  start(block = true): Promise<void> | void {
    this._server = http.createServer((req, res) => this._handleRequest(req, res));
    this._startTime = Date.now();

    if (block) {
      return new Promise<void>((resolve) => {
        this._server!.listen(this._port, this._host, () => {
          console.log(`ModelMesh proxy listening on ${this._host}:${this._port}`);
          resolve();
        });
      });
    } else {
      this._server.listen(this._port, this._host, () => {
        console.log(`ModelMesh proxy listening on ${this._host}:${this._port}`);
      });
    }
  }

  /** Stop the HTTP server and shut down the mesh. */
  stop(): void {
    if (this._server) {
      this._server.close();
      this._server = null;
    }
    this._startTime = null;
    this._mesh.shutdown();
  }

  /** Return a snapshot of the server's operational state. */
  getStatus(): ServerStatus {
    const uptime = this._startTime ? (Date.now() - this._startTime) / 1000 : 0;
    return {
      running: this._startTime !== null,
      host: this._host,
      port: this._port,
      uptime_seconds: Math.round(uptime * 100) / 100,
      active_connections: this._activeConnections,
      total_requests: this._totalRequests,
    };
  }

  // -- Internal helpers -----------------------------------------------------

  private _checkAuth(req: http.IncomingMessage, res: http.ServerResponse): boolean {
    if (!this._token) return true;
    const authHeader = req.headers.authorization ?? '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : authHeader;
    if (token === this._token) return true;
    this._sendJsonError(res, 401, 'Invalid or missing bearer token');
    return false;
  }

  private _sendJsonResponse(res: http.ServerResponse, status: number, body: unknown): void {
    const payload = JSON.stringify(body);
    res.writeHead(status, {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(payload).toString(),
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    });
    res.end(payload);
  }

  private _sendJsonError(res: http.ServerResponse, status: number, message: string): void {
    this._sendJsonResponse(res, status, {
      error: { message, type: 'error', code: status },
    });
  }

  private _readJsonBody(req: http.IncomingMessage): Promise<Record<string, unknown> | null> {
    return new Promise((resolve) => {
      const chunks: Buffer[] = [];
      req.on('data', (chunk: Buffer) => chunks.push(chunk));
      req.on('end', () => {
        try {
          const raw = Buffer.concat(chunks).toString('utf-8');
          if (!raw) { resolve(null); return; }
          resolve(JSON.parse(raw));
        } catch {
          resolve(null);
        }
      });
    });
  }

  private async _handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    this._activeConnections++;
    this._totalRequests++;

    try {
      if (req.method === 'OPTIONS') {
        res.writeHead(204, {
          'Content-Length': '0',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        });
        res.end();
        return;
      }

      if (!this._checkAuth(req, res)) return;

      const url = req.url ?? '';

      if (req.method === 'GET') {
        if (url === '/v1/models') {
          this._handleModels(res);
        } else if (url === '/health') {
          this._sendJsonResponse(res, 200, this.getStatus());
        } else {
          this._sendJsonError(res, 404, 'Not found: ' + url);
        }
      } else if (req.method === 'POST') {
        const body = await this._readJsonBody(req);
        if (url === '/v1/chat/completions') {
          await this._handleChatCompletions(body, res);
        } else if (url === '/v1/embeddings') {
          await this._handleEmbeddings(body, res);
        } else if (url === '/v1/audio/speech') {
          await this._handleGeneric(body, res);
        } else if (url === '/v1/audio/transcriptions') {
          await this._handleGeneric(body, res);
        } else {
          this._sendJsonError(res, 404, 'Not found: ' + url);
        }
      } else {
        this._sendJsonError(res, 405, 'Method not allowed');
      }
    } catch (err) {
      this._sendJsonError(res, 500, String(err));
    } finally {
      this._activeConnections--;
    }
  }

  private _handleModels(res: http.ServerResponse): void {
    const pools = this._mesh.pools;
    const createdTs = this._startTime ? Math.floor(this._startTime / 1000) : 0;
    const models = Object.keys(pools).map((poolId) => ({
      id: poolId,
      object: 'model',
      created: createdTs,
      owned_by: 'modelmesh',
    }));
    this._sendJsonResponse(res, 200, { object: 'list', data: models });
  }

  private async _handleChatCompletions(
    body: Record<string, unknown> | null,
    res: http.ServerResponse
  ): Promise<void> {
    if (!body) { this._sendJsonError(res, 400, 'Empty request body'); return; }

    const model = body.model as string;
    const messages = body.messages as Record<string, unknown>[];
    const stream = (body.stream as boolean) ?? false;

    if (!model) { this._sendJsonError(res, 400, 'Missing required field: model'); return; }
    if (!messages) { this._sendJsonError(res, 400, 'Missing required field: messages'); return; }

    const request: CompletionRequest = {
      model,
      messages,
      temperature: (body.temperature as number) ?? 1.0,
      maxTokens: body.max_tokens as number | undefined,
      stream,
      tools: body.tools as unknown[] | undefined,
      topP: (body.top_p as number) ?? 1.0,
      stop: body.stop as string[] | undefined,
    };

    if (stream) {
      await this._streamChatResponse(request, res);
    } else {
      await this._nonStreamChatResponse(request, res);
    }
  }

  private async _nonStreamChatResponse(
    request: CompletionRequest,
    res: http.ServerResponse
  ): Promise<void> {
    try {
      const response = await this._mesh.route(request);
      this._sendJsonResponse(res, 200, completionResponseToDict(response));
    } catch (err) {
      this._sendJsonError(res, 502, 'Routing error: ' + String(err));
    }
  }

  private async _streamChatResponse(
    request: CompletionRequest,
    res: http.ServerResponse
  ): Promise<void> {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Transfer-Encoding': 'chunked',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    });

    try {
      for await (const chunk of this._mesh.routeStream(request)) {
        const chunkDict = completionResponseToDict(chunk);
        chunkDict.object = 'chat.completion.chunk';
        const dataLine = 'data: ' + JSON.stringify(chunkDict) + '\n\n';
        res.write(dataLine);
      }
      res.write('data: [DONE]\n\n');
      res.end();
    } catch (err) {
      try {
        res.write('data: ' + JSON.stringify({ error: { message: String(err) } }) + '\n\n');
        res.end();
      } catch { /* ignore */ }
    }
  }

  private async _handleEmbeddings(
    body: Record<string, unknown> | null,
    res: http.ServerResponse
  ): Promise<void> {
    if (!body) { this._sendJsonError(res, 400, 'Empty request body'); return; }
    const model = body.model as string;
    if (!model) { this._sendJsonError(res, 400, 'Missing required field: model'); return; }

    let inputData = body.input;
    if (typeof inputData === 'string') inputData = [inputData];

    const request: CompletionRequest = {
      model,
      messages: (inputData as string[]).map((text) => ({ role: 'user', content: text })),
      temperature: 0.0,
      stream: false,
      topP: 1.0,
    };

    try {
      const response = await this._mesh.route(request);
      this._sendJsonResponse(res, 200, completionResponseToDict(response));
    } catch (err) {
      this._sendJsonError(res, 502, 'Routing error: ' + String(err));
    }
  }

  private async _handleGeneric(
    body: Record<string, unknown> | null,
    res: http.ServerResponse
  ): Promise<void> {
    if (!body) { this._sendJsonError(res, 400, 'Empty request body'); return; }
    const model = body.model as string;
    if (!model) { this._sendJsonError(res, 400, 'Missing required field: model'); return; }

    const request: CompletionRequest = {
      model,
      messages: [{ role: 'user', content: (body.input as string) ?? (body.text as string) ?? '' }],
      temperature: 1.0,
      stream: false,
      topP: 1.0,
    };

    try {
      const response = await this._mesh.route(request);
      this._sendJsonResponse(res, 200, completionResponseToDict(response));
    } catch (err) {
      this._sendJsonError(res, 502, 'Routing error: ' + String(err));
    }
  }
}
