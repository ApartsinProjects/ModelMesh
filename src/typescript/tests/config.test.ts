/**
 * Tests for MeshConfig and auto-detect modules.
 */
import { MeshConfig } from '@/config/mesh-config';
import { detectProviders, PROVIDER_REGISTRY, LOCAL_PROVIDER_REGISTRY } from '@/config/auto-detect';
import type { DetectedProvider } from '@/config/auto-detect';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// ---------------------------------------------------------------------------
// MeshConfig
// ---------------------------------------------------------------------------

describe('MeshConfig', () => {
  // -- Construction -----------------------------------------------------------

  it('should create with default empty raw', () => {
    const cfg = new MeshConfig();
    expect(cfg.raw).toEqual({});
  });

  it('should create from a dictionary', () => {
    const raw = {
      providers: { 'openai.llm.v1': { enabled: true } },
      pools: { chat: { capability: 'generation.text-generation.chat-completion' } },
    };
    const cfg = MeshConfig.fromDict(raw);
    expect(cfg.providers).toEqual(raw.providers);
    expect(cfg.pools).toEqual(raw.pools);
  });

  it('should load from a JSON file', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'modelmesh-'));
    const filePath = path.join(tmpDir, 'config.json');
    const data = {
      providers: { 'openai.llm.v1': { enabled: true, config: { api_key: 'sk-test' } } },
      models: { 'openai.gpt-4o': { provider: 'openai.llm.v1' } },
      pools: { chat: { capability: 'generation.text-generation.chat-completion' } },
    };
    fs.writeFileSync(filePath, JSON.stringify(data));

    const cfg = MeshConfig.fromFile(filePath);
    expect(cfg.providers).toEqual(data.providers);
    expect(cfg.models).toEqual(data.models);
    expect(cfg.pools).toEqual(data.pools);

    // Cleanup
    fs.unlinkSync(filePath);
    fs.rmdirSync(tmpDir);
  });

  it('should load via fromJson alias', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'modelmesh-'));
    const filePath = path.join(tmpDir, 'config.json');
    fs.writeFileSync(filePath, JSON.stringify({ providers: { a: 1 } }));

    const cfg = MeshConfig.fromJson(filePath);
    expect(cfg.providers).toEqual({ a: 1 });

    fs.unlinkSync(filePath);
    fs.rmdirSync(tmpDir);
  });

  it('should throw for non-existent file', () => {
    expect(() => MeshConfig.fromFile('/nonexistent/path/config.json')).toThrow();
  });

  it('should throw for invalid JSON file', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'modelmesh-'));
    const filePath = path.join(tmpDir, 'bad.json');
    fs.writeFileSync(filePath, 'not valid json {{{');

    expect(() => MeshConfig.fromFile(filePath)).toThrow();

    fs.unlinkSync(filePath);
    fs.rmdirSync(tmpDir);
  });

  // -- Section accessors ------------------------------------------------------

  it('should return empty objects for missing sections', () => {
    const cfg = new MeshConfig();
    expect(cfg.providers).toEqual({});
    expect(cfg.models).toEqual({});
    expect(cfg.pools).toEqual({});
    expect(cfg.secrets).toEqual({});
    expect(cfg.observability).toEqual({});
    expect(cfg.storage).toEqual({});
  });

  it('should return providers section', () => {
    const cfg = MeshConfig.fromDict({ providers: { a: { enabled: true } } });
    expect(cfg.providers).toEqual({ a: { enabled: true } });
  });

  it('should return models section', () => {
    const cfg = MeshConfig.fromDict({ models: { 'openai.gpt-4o': { provider: 'openai' } } });
    expect(cfg.models).toEqual({ 'openai.gpt-4o': { provider: 'openai' } });
  });

  it('should return pools section', () => {
    const cfg = MeshConfig.fromDict({ pools: { chat: { capability: 'gen' } } });
    expect(cfg.pools).toEqual({ chat: { capability: 'gen' } });
  });

  it('should return secrets section', () => {
    const cfg = MeshConfig.fromDict({ secrets: { store: 'env' } });
    expect(cfg.secrets).toEqual({ store: 'env' });
  });

  it('should return observability section', () => {
    const cfg = MeshConfig.fromDict({ observability: { connector: 'console' } });
    expect(cfg.observability).toEqual({ connector: 'console' });
  });

  it('should return storage section', () => {
    const cfg = MeshConfig.fromDict({ storage: { type: 'memory' } });
    expect(cfg.storage).toEqual({ type: 'memory' });
  });

  // -- get() ------------------------------------------------------------------

  it('should support get with default', () => {
    const cfg = MeshConfig.fromDict({ foo: 'bar' });
    expect(cfg.get('foo')).toBe('bar');
    expect(cfg.get('missing', 'default')).toBe('default');
    expect(cfg.get('missing')).toBeUndefined();
  });

  it('should get nested objects', () => {
    const cfg = MeshConfig.fromDict({ nested: { key: 'value' } });
    const nested = cfg.get('nested') as Record<string, string>;
    expect(nested.key).toBe('value');
  });

  it('should return default for null-ish values', () => {
    const cfg = MeshConfig.fromDict({});
    expect(cfg.get('missing', 42)).toBe(42);
  });

  // -- Merge ------------------------------------------------------------------

  it('should merge top-level keys', () => {
    const base = MeshConfig.fromDict({
      providers: { a: 1 },
      pools: { x: 1 },
    });
    const merged = base.merge({ pools: { y: 2 } });
    expect((merged.providers as Record<string, number>).a).toBe(1);
    expect((merged.pools as Record<string, number>).x).toBe(1);
    expect((merged.pools as Record<string, number>).y).toBe(2);
  });

  it('should overwrite non-object keys on merge', () => {
    const base = MeshConfig.fromDict({ name: 'old' });
    const merged = base.merge({ name: 'new' });
    expect(merged.get('name')).toBe('new');
  });

  it('should not mutate original on merge', () => {
    const base = MeshConfig.fromDict({ providers: { a: 1 } });
    base.merge({ providers: { b: 2 } });
    expect(base.providers).toEqual({ a: 1 });
  });

  it('should overwrite arrays on merge', () => {
    const base = MeshConfig.fromDict({ tags: ['a', 'b'] });
    const merged = base.merge({ tags: ['c'] });
    expect(merged.get('tags')).toEqual(['c']);
  });

  it('should handle merging with null value', () => {
    const base = MeshConfig.fromDict({ providers: { a: 1 } });
    const merged = base.merge({ providers: null as unknown as Record<string, unknown> });
    expect(merged.get('providers')).toBeNull();
  });

  it('should add new keys on merge', () => {
    const base = MeshConfig.fromDict({ providers: {} });
    const merged = base.merge({ newKey: 'newValue' });
    expect(merged.get('newKey')).toBe('newValue');
  });

  it('should return a new MeshConfig instance on merge', () => {
    const base = MeshConfig.fromDict({ providers: {} });
    const merged = base.merge({});
    expect(merged).not.toBe(base);
    expect(merged).toBeInstanceOf(MeshConfig);
  });

  // -- Validation -------------------------------------------------------------

  it('should validate valid config', () => {
    const cfg = MeshConfig.fromDict({
      providers: { 'openai.llm.v1': { enabled: true } },
      models: { 'openai.gpt-4o': { provider: 'openai.llm.v1' } },
      pools: { chat: { capability: 'generation.text-generation.chat-completion' } },
    });
    expect(cfg.validate()).toEqual([]);
  });

  it('should catch invalid providers type', () => {
    const cfg = MeshConfig.fromDict({ providers: 'not-an-object' as unknown });
    const errors = cfg.validate();
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]).toContain('providers');
  });

  it('should catch invalid models type', () => {
    const cfg = MeshConfig.fromDict({ models: 42 as unknown });
    const errors = cfg.validate();
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]).toContain('models');
  });

  it('should catch invalid pools type', () => {
    const cfg = MeshConfig.fromDict({ pools: true as unknown });
    const errors = cfg.validate();
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]).toContain('pools');
  });

  it('should catch pool referencing unknown model', () => {
    const cfg = MeshConfig.fromDict({
      models: { 'openai.gpt-4o': { provider: 'openai.llm.v1' } },
      pools: { chat: { models: ['nonexistent-model'] } },
    });
    const errors = cfg.validate();
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]).toContain('nonexistent-model');
  });

  it('should pass validation when pool models reference known models', () => {
    const cfg = MeshConfig.fromDict({
      models: { 'openai.gpt-4o': { provider: 'openai.llm.v1' } },
      pools: { chat: { models: ['openai.gpt-4o'] } },
    });
    expect(cfg.validate()).toEqual([]);
  });

  it('should pass validation with no pools or models', () => {
    const cfg = MeshConfig.fromDict({ providers: {} });
    expect(cfg.validate()).toEqual([]);
  });

  it('should validate empty config', () => {
    const cfg = new MeshConfig();
    expect(cfg.validate()).toEqual([]);
  });

  it('should report multiple validation errors', () => {
    const cfg = MeshConfig.fromDict({
      providers: 'bad' as unknown,
      models: 123 as unknown,
      pools: false as unknown,
    });
    const errors = cfg.validate();
    expect(errors.length).toBe(3);
  });

  it('should catch multiple unknown model references', () => {
    const cfg = MeshConfig.fromDict({
      models: { 'openai.gpt-4o': { provider: 'openai.llm.v1' } },
      pools: {
        pool1: { models: ['unknown1'] },
        pool2: { models: ['unknown2'] },
      },
    });
    const errors = cfg.validate();
    expect(errors.length).toBe(2);
  });

  it('should validate pools without models array (capability-based)', () => {
    const cfg = MeshConfig.fromDict({
      models: { 'openai.gpt-4o': { provider: 'openai.llm.v1' } },
      pools: { chat: { capability: 'generation.text-generation' } },
    });
    expect(cfg.validate()).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// detectProviders
// ---------------------------------------------------------------------------

describe('detectProviders', () => {
  const ORIGINAL_ENV = { ...process.env };

  afterEach(() => {
    // Restore environment
    process.env = { ...ORIGINAL_ENV };
  });

  it('should detect provider from environment variable', () => {
    process.env.OPENAI_API_KEY = 'sk-test-key';
    const detected = detectProviders();
    const openai = detected.find((d) => d.name === 'openai');
    expect(openai).toBeDefined();
    expect(openai!.apiKey).toBe('sk-test-key');
    expect(openai!.connector).toBe('openai.llm.v1');
  });

  it('should detect multiple providers', () => {
    process.env.OPENAI_API_KEY = 'sk-openai';
    process.env.ANTHROPIC_API_KEY = 'sk-anthropic';
    const detected = detectProviders();
    const names = detected.map((d) => d.name);
    expect(names).toContain('openai');
    expect(names).toContain('anthropic');
  });

  it('should filter by provider names', () => {
    process.env.OPENAI_API_KEY = 'sk-openai';
    process.env.ANTHROPIC_API_KEY = 'sk-anthropic';
    const detected = detectProviders({ names: ['openai'] });
    expect(detected.length).toBe(1);
    expect(detected[0].name).toBe('openai');
  });

  it('should filter by multiple provider names', () => {
    process.env.OPENAI_API_KEY = 'sk-openai';
    process.env.ANTHROPIC_API_KEY = 'sk-anthropic';
    process.env.GROQ_API_KEY = 'sk-groq';
    const detected = detectProviders({ names: ['openai', 'groq'] });
    expect(detected.length).toBe(2);
    const names = detected.map(d => d.name);
    expect(names).toContain('openai');
    expect(names).toContain('groq');
  });

  it('should use explicit apiKeys over environment', () => {
    process.env.OPENAI_API_KEY = 'from-env';
    const detected = detectProviders({
      apiKeys: { OPENAI_API_KEY: 'from-arg' },
    });
    const openai = detected.find((d) => d.name === 'openai');
    expect(openai!.apiKey).toBe('from-arg');
  });

  it('should support provider name as apiKeys key', () => {
    const detected = detectProviders({
      apiKeys: { openai: 'sk-by-name' },
    });
    const openai = detected.find((d) => d.name === 'openai');
    expect(openai).toBeDefined();
    expect(openai!.apiKey).toBe('sk-by-name');
  });

  it('should return empty when no keys found', () => {
    // Remove all known keys
    for (const envVar of Object.keys(PROVIDER_REGISTRY)) {
      delete process.env[envVar];
    }
    for (const envVar of Object.keys(LOCAL_PROVIDER_REGISTRY)) {
      delete process.env[envVar];
    }
    const detected = detectProviders();
    expect(detected.length).toBe(0);
  });

  it('should include default models for detected providers', () => {
    process.env.OPENAI_API_KEY = 'sk-test';
    const detected = detectProviders();
    const openai = detected.find((d) => d.name === 'openai')!;
    expect(openai.defaultModels.length).toBeGreaterThan(0);
    expect(openai.defaultModels[0].id).toContain('openai.');
  });

  it('should include baseUrl for detected providers', () => {
    process.env.OPENAI_API_KEY = 'sk-test';
    const detected = detectProviders();
    const openai = detected.find(d => d.name === 'openai')!;
    expect(openai.baseUrl).toBe('https://api.openai.com');
  });

  it('should include envVar for detected providers', () => {
    process.env.ANTHROPIC_API_KEY = 'sk-test';
    const detected = detectProviders();
    const anthropic = detected.find(d => d.name === 'anthropic')!;
    expect(anthropic.envVar).toBe('ANTHROPIC_API_KEY');
  });

  it('should not detect providers without keys even if names specified', () => {
    delete process.env.OPENAI_API_KEY;
    const detected = detectProviders({ names: ['openai'] });
    expect(detected.length).toBe(0);
  });

  it('should detect local provider when host is set', () => {
    process.env.OLLAMA_HOST = 'http://my-server:11434';
    const detected = detectProviders();
    const ollama = detected.find(d => d.name === 'ollama');
    expect(ollama).toBeDefined();
    expect(ollama!.baseUrl).toBe('http://my-server:11434');
    expect(ollama!.apiKey).toBe('');
    delete process.env.OLLAMA_HOST;
  });

  it('should detect local provider via apiKeys', () => {
    const detected = detectProviders({
      apiKeys: { OLLAMA_HOST: 'http://custom:11434' },
    });
    const ollama = detected.find(d => d.name === 'ollama');
    expect(ollama).toBeDefined();
    expect(ollama!.baseUrl).toBe('http://custom:11434');
  });

  it('should detect local provider via name in apiKeys', () => {
    const detected = detectProviders({
      apiKeys: { ollama: 'http://by-name:11434' },
    });
    const ollama = detected.find(d => d.name === 'ollama');
    expect(ollama).toBeDefined();
    expect(ollama!.baseUrl).toBe('http://by-name:11434');
  });
});

// ---------------------------------------------------------------------------
// PROVIDER_REGISTRY
// ---------------------------------------------------------------------------

describe('PROVIDER_REGISTRY', () => {
  it('should have 17 entries', () => {
    expect(Object.keys(PROVIDER_REGISTRY).length).toBe(17);
  });

  it('should map env var names to provider entries', () => {
    expect(PROVIDER_REGISTRY.OPENAI_API_KEY).toBeDefined();
    expect(PROVIDER_REGISTRY.OPENAI_API_KEY.name).toBe('openai');
    expect(PROVIDER_REGISTRY.OPENAI_API_KEY.connector).toBe('openai.llm.v1');
  });

  it('should have default models with dot-notation capabilities', () => {
    for (const [_envVar, entry] of Object.entries(PROVIDER_REGISTRY)) {
      for (const model of entry.defaultModels) {
        for (const cap of model.capabilities) {
          expect(cap).toContain('.');
        }
      }
    }
  });

  it('should cover all major providers', () => {
    const names = Object.values(PROVIDER_REGISTRY).map((e) => e.name);
    expect(names).toContain('openai');
    expect(names).toContain('anthropic');
    expect(names).toContain('google');
    expect(names).toContain('groq');
    expect(names).toContain('mistral');
    expect(names).toContain('deepseek');
    expect(names).toContain('together');
    expect(names).toContain('openrouter');
    expect(names).toContain('xai');
    expect(names).toContain('cohere');
    expect(names).toContain('perplexity');
    expect(names).toContain('elevenlabs');
    expect(names).toContain('tavily');
    expect(names).toContain('serper');
    expect(names).toContain('jina');
    expect(names).toContain('firecrawl');
    expect(names).toContain('assemblyai');
  });

  it('should have unique provider names', () => {
    const names = Object.values(PROVIDER_REGISTRY).map(e => e.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it('should have unique connector IDs', () => {
    const connectors = Object.values(PROVIDER_REGISTRY).map(e => e.connector);
    expect(new Set(connectors).size).toBe(connectors.length);
  });

  it('should have non-empty baseUrl for all entries', () => {
    for (const entry of Object.values(PROVIDER_REGISTRY)) {
      expect(entry.baseUrl).toBeTruthy();
      expect(entry.baseUrl.startsWith('https://')).toBe(true);
    }
  });

  it('should have models with valid contextWindow', () => {
    for (const entry of Object.values(PROVIDER_REGISTRY)) {
      for (const model of entry.defaultModels) {
        expect(model.contextWindow).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it('should have models with valid maxOutputTokens', () => {
    for (const entry of Object.values(PROVIDER_REGISTRY)) {
      for (const model of entry.defaultModels) {
        expect(model.maxOutputTokens).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it('should have models with dot-prefixed IDs matching provider name', () => {
    for (const entry of Object.values(PROVIDER_REGISTRY)) {
      for (const model of entry.defaultModels) {
        expect(model.id.startsWith(entry.name + '.')).toBe(true);
      }
    }
  });
});

// ---------------------------------------------------------------------------
// LOCAL_PROVIDER_REGISTRY
// ---------------------------------------------------------------------------

describe('LOCAL_PROVIDER_REGISTRY', () => {
  it('should have 4 entries', () => {
    expect(Object.keys(LOCAL_PROVIDER_REGISTRY).length).toBe(4);
  });

  it('should contain all local provider env vars', () => {
    expect(LOCAL_PROVIDER_REGISTRY.OLLAMA_HOST).toBeDefined();
    expect(LOCAL_PROVIDER_REGISTRY.LMSTUDIO_HOST).toBeDefined();
    expect(LOCAL_PROVIDER_REGISTRY.VLLM_HOST).toBeDefined();
    expect(LOCAL_PROVIDER_REGISTRY.LOCALAI_HOST).toBeDefined();
  });

  it('should have correct connector IDs', () => {
    expect(LOCAL_PROVIDER_REGISTRY.OLLAMA_HOST.connector).toBe('ollama.local.v1');
    expect(LOCAL_PROVIDER_REGISTRY.LMSTUDIO_HOST.connector).toBe('lmstudio.local.v1');
    expect(LOCAL_PROVIDER_REGISTRY.VLLM_HOST.connector).toBe('vllm.local.v1');
    expect(LOCAL_PROVIDER_REGISTRY.LOCALAI_HOST.connector).toBe('localai.local.v1');
  });

  it('should detect providers when env var is set', () => {
    process.env.OLLAMA_HOST = 'http://localhost:11434';
    const detected = detectProviders();
    const names = detected.map((d: DetectedProvider) => d.name);
    expect(names).toContain('ollama');
    delete process.env.OLLAMA_HOST;
  });

  it('should have localhost baseUrls', () => {
    for (const entry of Object.values(LOCAL_PROVIDER_REGISTRY)) {
      expect(entry.baseUrl).toContain('localhost');
    }
  });

  it('should have unique connector IDs', () => {
    const connectors = Object.values(LOCAL_PROVIDER_REGISTRY).map(e => e.connector);
    expect(new Set(connectors).size).toBe(connectors.length);
  });

  it('should have unique provider names', () => {
    const names = Object.values(LOCAL_PROVIDER_REGISTRY).map(e => e.name);
    expect(new Set(names).size).toBe(names.length);
  });
});
