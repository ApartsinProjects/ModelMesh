/**
 * OpenAI-compatible provider for the CDK.
 *
 * Pre-configured provider for any API that follows the OpenAI chat
 * completions specification. No method overrides are needed because
 * BaseProvider defaults are already OpenAI-compatible. This class
 * adds optional organization and apiVersion configuration fields
 * and sets appropriate defaults.
 */

import { RuntimeEnvironment } from '../../interfaces/runtime';
import { BaseProvider, BaseProviderConfig, createBaseProviderConfig } from '../base-provider';

export interface OpenAICompatibleConfig extends BaseProviderConfig {
  organization?: string;
  apiVersion?: string;
}

export function createOpenAICompatibleConfig(
  partial?: Partial<OpenAICompatibleConfig>
): OpenAICompatibleConfig {
  return {
    ...createBaseProviderConfig(),
    organization: undefined,
    apiVersion: undefined,
    ...partial,
  };
}

/**
 * Provider for APIs that follow the OpenAI chat completions spec.
 *
 * This is the simplest specialized provider: BaseProvider already
 * implements OpenAI-compatible request/response handling, so this
 * class only adds organization/version header support and validates
 * the configuration.
 */
export class OpenAICompatibleProvider extends BaseProvider {
  static readonly RUNTIME = RuntimeEnvironment.NODE_ONLY;

  protected _oaiConfig: OpenAICompatibleConfig;

  constructor(config: OpenAICompatibleConfig) {
    if (!config.baseUrl) {
      config.baseUrl = 'https://api.openai.com';
    }
    super(config);
    this._oaiConfig = config;
  }

  protected _buildHeaders(): Record<string, string> {
    const headers = super._buildHeaders();
    if (this._oaiConfig.organization) {
      headers['OpenAI-Organization'] = this._oaiConfig.organization;
    }
    if (this._oaiConfig.apiVersion) {
      headers['OpenAI-Version'] = this._oaiConfig.apiVersion;
    }
    return headers;
  }
}
