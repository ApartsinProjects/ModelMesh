/**
 * HTTP health-check discovery for the CDK.
 *
 * Implements health probing via HTTP GET requests to provider
 * health endpoints. Measures latency and availability.
 */

import * as http from 'http';
import * as https from 'https';
import { BaseDiscovery, BaseDiscoveryConfig } from '../base-discovery';
import { ProbeResult } from '../../interfaces/discovery';

export interface HttpHealthDiscoveryConfig extends BaseDiscoveryConfig {
  /** Map of provider IDs to their health check URLs. */
  endpoints?: Record<string, string>;
  /** Request timeout in milliseconds. */
  timeoutMs?: number;
}

/**
 * Discovery connector that probes provider health via HTTP.
 *
 * @example
 * const discovery = new HttpHealthDiscovery({
 *   endpoints: {
 *     'openai.v1': 'https://api.openai.com/v1/models',
 *   },
 *   timeoutMs: 5000,
 * });
 * const result = await discovery.probe('openai.v1');
 */
export class HttpHealthDiscovery extends BaseDiscovery {
  private readonly _httpConfig: { endpoints: Record<string, string>; timeoutMs: number };

  constructor(config?: HttpHealthDiscoveryConfig) {
    super(config);
    this._httpConfig = {
      endpoints: config?.endpoints ?? {},
      timeoutMs: config?.timeoutMs ?? 5000,
    };
  }

  async probe(providerId: string): Promise<ProbeResult> {
    const url = this._httpConfig.endpoints[providerId];
    if (!url) {
      return { providerId, success: false, error: 'No endpoint configured' };
    }

    const start = Date.now();
    try {
      const statusCode = await this._httpGet(url);
      const latencyMs = Date.now() - start;
      return {
        providerId,
        success: statusCode >= 200 && statusCode < 400,
        latencyMs,
        statusCode,
      };
    } catch (err) {
      const latencyMs = Date.now() - start;
      return {
        providerId,
        success: false,
        latencyMs,
        error: String(err),
      };
    }
  }

  private _httpGet(url: string): Promise<number> {
    return new Promise((resolve, reject) => {
      const mod = url.startsWith('https') ? https : http;
      const req = mod.get(url, { timeout: this._httpConfig.timeoutMs }, (res) => {
        // Drain the response
        res.on('data', () => {});
        res.on('end', () => resolve(res.statusCode ?? 0));
      });
      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error(`Timeout after ${this._httpConfig.timeoutMs}ms`));
      });
    });
  }
}
