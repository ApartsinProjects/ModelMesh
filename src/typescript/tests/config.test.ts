/**
 * Tests for MeshConfig and auto-detect modules.
 */
import { MeshConfig } from '@/config/mesh-config';
import { detectProviders, PROVIDER_REGISTRY } from '@/config/auto-detect';
import type { DetectedProvider } from '@/config/auto-detect';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// ---------------------------------------------------------------------------
// MeshConfig
// ---------------------------------------------------------------------------

describe('MeshConfig', () => {
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

  it('should return empty objects for missing sections', () => {
    const cfg = new MeshConfig();
    expect(cfg.providers).toEqual({});
    expect(cfg.models).toEqual({});
    expect(cfg.pools).toEqual({});
    expect(cfg.secrets).toEqual({});
    expect(cfg.observability).toEqual({});
    expect(cfg.storage).toEqual({});
  });

  it('should support get with default', () => {
    const cfg = MeshConfig.fromDict({ foo: 'bar' });
    expect(cfg.get('foo')).toBe('bar');
    expect(cfg.get('missing', 'default')).toBe('default');
    expect(cfg.get('missing')).toBeUndefined();
  });

  // -- Merge ---------------------------------------------------------------

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

  // -- Validation ----------------------------------------------------------

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
});

// ---------------------------------------------------------------------------
// PROVIDER_REGISTRY
// ---------------------------------------------------------------------------

describe('PROVIDER_REGISTRY', () => {
  it('should have 18 entries', () => {
    expect(Object.keys(PROVIDER_REGISTRY).length).toBe(18);
  });

  it('should map env var names to provider entries', () => {
    expect(PROVIDER_REGISTRY.OPENAI_API_KEY).toBeDefined();
    expect(PROVIDER_REGISTRY.OPENAI_API_KEY.name).toBe('openai');
    expect(PROVIDER_REGISTRY.OPENAI_API_KEY.connector).toBe('openai.llm.v1');
  });

  it('should have default models with dot-notation capabilities', () => {
    for (const [envVar, entry] of Object.entries(PROVIDER_REGISTRY)) {
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
    expect(names).toContain('huggingface');
    expect(names).toContain('elevenlabs');
    expect(names).toContain('tavily');
    expect(names).toContain('serper');
    expect(names).toContain('jina');
    expect(names).toContain('firecrawl');
    expect(names).toContain('assemblyai');
  });
});
