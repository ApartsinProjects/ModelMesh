/**
 * Provider auto-detection from environment variables.
 *
 * Scans the environment for known API key variables and returns provider
 * configurations for use with the convenience layer. The registry maps
 * environment variable names to provider metadata, default models, and
 * connector IDs.
 */

import { ModelInfo, createDefaultModelInfo } from '../interfaces/provider';

export interface ProviderRegistryEntry {
  name: string;
  connector: string;
  baseUrl: string;
  defaultModels: ModelInfo[];
}

export interface DetectedProvider extends ProviderRegistryEntry {
  envVar: string;
  apiKey: string;
}

function m(
  id: string,
  name: string,
  capabilities: string[],
  contextWindow: number,
  maxOutputTokens: number
): ModelInfo {
  return createDefaultModelInfo({
    id,
    name,
    capabilities,
    contextWindow,
    maxOutputTokens,
  });
}

export const PROVIDER_REGISTRY: Record<string, ProviderRegistryEntry> = {
  OPENAI_API_KEY: {
    name: 'openai',
    connector: 'openai.llm.v1',
    baseUrl: 'https://api.openai.com',
    defaultModels: [
      m('openai.gpt-4o', 'GPT-4o', ['generation.text-generation.chat-completion'], 128000, 16384),
      m('openai.gpt-4o-mini', 'GPT-4o Mini', ['generation.text-generation.chat-completion'], 128000, 16384),
    ],
  },
  ANTHROPIC_API_KEY: {
    name: 'anthropic',
    connector: 'anthropic.claude.v1',
    baseUrl: 'https://api.anthropic.com',
    defaultModels: [
      m('anthropic.claude-sonnet-4-20250514', 'Claude Sonnet 4', ['generation.text-generation.chat-completion'], 200000, 16384),
      m('anthropic.claude-haiku-4-5-20251001', 'Claude Haiku 4.5', ['generation.text-generation.chat-completion'], 200000, 8192),
    ],
  },
  GOOGLE_API_KEY: {
    name: 'google',
    connector: 'google.gemini.v1',
    baseUrl: 'https://generativelanguage.googleapis.com',
    defaultModels: [
      m('google.gemini-2.0-flash', 'Gemini 2.0 Flash', ['generation.text-generation.chat-completion'], 1048576, 8192),
      m('google.gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite', ['generation.text-generation.chat-completion'], 1048576, 8192),
    ],
  },
  GROQ_API_KEY: {
    name: 'groq',
    connector: 'groq.api.v1',
    baseUrl: 'https://api.groq.com',
    defaultModels: [
      m('groq.llama-3.3-70b-versatile', 'Llama 3.3 70B Versatile', ['generation.text-generation.chat-completion'], 128000, 32768),
    ],
  },
  MISTRAL_API_KEY: {
    name: 'mistral',
    connector: 'mistral.api.v1',
    baseUrl: 'https://api.mistral.ai',
    defaultModels: [
      m('mistral.mistral-large-latest', 'Mistral Large', ['generation.text-generation.chat-completion'], 128000, 8192),
      m('mistral.mistral-small-latest', 'Mistral Small', ['generation.text-generation.chat-completion', 'representation.embeddings.text-embeddings'], 128000, 8192),
    ],
  },
  TOGETHER_API_KEY: {
    name: 'together',
    connector: 'together.api.v1',
    baseUrl: 'https://api.together.xyz',
    defaultModels: [
      m('together.meta-llama-3.1-8b-instruct-turbo', 'Llama 3.1 8B Instruct Turbo', ['generation.text-generation.chat-completion'], 131072, 4096),
    ],
  },
  OPENROUTER_API_KEY: {
    name: 'openrouter',
    connector: 'openrouter.gateway.v1',
    baseUrl: 'https://openrouter.ai',
    defaultModels: [
      m('openrouter.auto', 'OpenRouter Auto', ['generation.text-generation.chat-completion'], 128000, 4096),
    ],
  },
  DEEPSEEK_API_KEY: {
    name: 'deepseek',
    connector: 'deepseek.api.v1',
    baseUrl: 'https://api.deepseek.com',
    defaultModels: [
      m('deepseek.deepseek-chat', 'DeepSeek Chat', ['generation.text-generation.chat-completion'], 64000, 8192),
    ],
  },
  XAI_API_KEY: {
    name: 'xai',
    connector: 'xai.grok.v1',
    baseUrl: 'https://api.x.ai',
    defaultModels: [
      m('xai.grok-2', 'Grok-2', ['generation.text-generation.chat-completion'], 128000, 32768),
    ],
  },
  COHERE_API_KEY: {
    name: 'cohere',
    connector: 'cohere.nlp.v1',
    baseUrl: 'https://api.cohere.com',
    defaultModels: [
      m('cohere.command-a-03-2025', 'Command A', ['generation.text-generation.chat-completion'], 256000, 8192),
    ],
  },
  PERPLEXITY_API_KEY: {
    name: 'perplexity',
    connector: 'perplexity.search.v1',
    baseUrl: 'https://api.perplexity.ai',
    defaultModels: [
      m('perplexity.sonar', 'Sonar', ['retrieval.grounded-generation.web-search'], 128000, 8192),
    ],
  },
  ELEVENLABS_API_KEY: {
    name: 'elevenlabs',
    connector: 'elevenlabs.tts.v1',
    baseUrl: 'https://api.elevenlabs.io',
    defaultModels: [
      m('elevenlabs.eleven_multilingual_v2', 'Eleven Multilingual v2', ['generation.audio.text-to-speech'], 5000, 0),
    ],
  },
  TAVILY_API_KEY: {
    name: 'tavily',
    connector: 'tavily.search.v1',
    baseUrl: 'https://api.tavily.com',
    defaultModels: [
      m('tavily.tavily-search', 'Tavily Search', ['retrieval.semantic-search.web-search'], 400, 0),
    ],
  },
  SERPER_API_KEY: {
    name: 'serper',
    connector: 'serper.search.v1',
    baseUrl: 'https://google.serper.dev',
    defaultModels: [
      m('serper.serper-google-search', 'Google Search via Serper', ['retrieval.semantic-search.web-search'], 2048, 0),
    ],
  },
  JINA_API_KEY: {
    name: 'jina',
    connector: 'jina.ai.v1',
    baseUrl: 'https://api.jina.ai',
    defaultModels: [
      m('jina.jina-reader', 'Jina Reader', ['understanding.document-understanding.content-extraction'], 0, 0),
      m('jina.jina-embeddings-v3', 'Jina Embeddings v3', ['representation.embeddings.text-embeddings'], 8192, 0),
    ],
  },
  FIRECRAWL_API_KEY: {
    name: 'firecrawl',
    connector: 'firecrawl.scrape.v1',
    baseUrl: 'https://api.firecrawl.dev',
    defaultModels: [
      m('firecrawl.firecrawl-scrape', 'Firecrawl Scrape', ['understanding.document-understanding.content-extraction'], 0, 0),
    ],
  },
  ASSEMBLYAI_API_KEY: {
    name: 'assemblyai',
    connector: 'assemblyai.stt.v1',
    baseUrl: 'https://api.assemblyai.com',
    defaultModels: [
      m('assemblyai.assemblyai-best', 'AssemblyAI Best', ['understanding.audio.speech-to-text'], 0, 0),
    ],
  },
};

/**
 * Scan environment variables for known API keys.
 *
 * Returns a list of provider configuration objects for each detected
 * provider. Each object contains all fields from the registry entry
 * plus the resolved envVar and apiKey.
 *
 * @param options.names - Restrict detection to specific provider names.
 * @param options.apiKeys - Use these keys instead of environment variables.
 *     Keys can be environment variable names or provider names.
 */
export const LOCAL_PROVIDER_REGISTRY: Record<string, ProviderRegistryEntry> = {
  OLLAMA_HOST: {
    name: 'ollama',
    connector: 'ollama.local.v1',
    baseUrl: 'http://localhost:11434',
    defaultModels: [
      m('ollama.llama3', 'Llama 3', ['generation.text-generation.chat-completion'], 8192, 4096),
    ],
  },
  LMSTUDIO_HOST: {
    name: 'lmstudio',
    connector: 'lmstudio.local.v1',
    baseUrl: 'http://localhost:1234',
    defaultModels: [],
  },
  VLLM_HOST: {
    name: 'vllm',
    connector: 'vllm.local.v1',
    baseUrl: 'http://localhost:8000',
    defaultModels: [],
  },
  LOCALAI_HOST: {
    name: 'localai',
    connector: 'localai.local.v1',
    baseUrl: 'http://localhost:8080',
    defaultModels: [],
  },
};

export function detectProviders(options?: {
  names?: string[];
  apiKeys?: Record<string, string>;
}): DetectedProvider[] {
  const detected: DetectedProvider[] = [];
  const names = options?.names;
  const apiKeys = options?.apiKeys;

  for (const [envVar, info] of Object.entries(PROVIDER_REGISTRY)) {
    const providerName = info.name;

    // Filter by names if specified
    if (names && !names.includes(providerName)) continue;

    // Resolve the API key
    let key: string | undefined;
    if (apiKeys) {
      key = apiKeys[envVar] ?? apiKeys[providerName];
    }
    if (!key) {
      key = process.env[envVar];
    }

    if (key) {
      detected.push({
        ...info,
        envVar,
        apiKey: key,
      });
    }
  }

  // Detect local providers (host-based, not API-key-based)
  for (const [envVar, info] of Object.entries(LOCAL_PROVIDER_REGISTRY)) {
    const providerName = info.name;
    if (names && !names.includes(providerName)) continue;

    let host: string | undefined;
    if (apiKeys) {
      host = apiKeys[envVar] ?? apiKeys[providerName];
    }
    if (!host) {
      host = process.env[envVar];
    }
    if (host) {
      detected.push({
        ...info,
        baseUrl: host,
        envVar,
        apiKey: '',
      });
    }
  }

  return detected;
}
