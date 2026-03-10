/**
 * Tests for interface data types and factory functions.
 */
import {
  createDefaultTokenUsage,
  createDefaultCompletionRequest,
  createDefaultCompletionResponse,
  createDefaultModelInfo,
  createDefaultModelPricing,
} from '@/interfaces/provider';
import { ModelStatus, DeactivationReason, RecoveryTrigger } from '@/interfaces/rotation';
import { EventType, LogLevel, Severity } from '@/interfaces/observability';
import { SyncPolicy, SerializationFormat } from '@/interfaces/storage';

describe('Provider data types', () => {
  describe('TokenUsage factory', () => {
    it('should create default token usage with zeros', () => {
      const usage = createDefaultTokenUsage();
      expect(usage.promptTokens).toBe(0);
      expect(usage.completionTokens).toBe(0);
      expect(usage.totalTokens).toBe(0);
    });

    it('should apply overrides', () => {
      const usage = createDefaultTokenUsage({ promptTokens: 100, completionTokens: 50, totalTokens: 150 });
      expect(usage.promptTokens).toBe(100);
      expect(usage.completionTokens).toBe(50);
      expect(usage.totalTokens).toBe(150);
    });
  });

  describe('CompletionRequest factory', () => {
    it('should create request with defaults', () => {
      const req = createDefaultCompletionRequest({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'Hello' }],
      });
      expect(req.model).toBe('gpt-4o');
      expect(req.temperature).toBe(1.0);
      expect(req.stream).toBe(false);
      expect(req.topP).toBe(1.0);
    });

    it('should apply overrides', () => {
      const req = createDefaultCompletionRequest({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'Hello' }],
        temperature: 0.5,
        stream: true,
      });
      expect(req.temperature).toBe(0.5);
      expect(req.stream).toBe(true);
    });
  });

  describe('CompletionResponse factory', () => {
    it('should create empty response', () => {
      const resp = createDefaultCompletionResponse();
      expect(resp.id).toBe('');
      expect(resp.choices).toEqual([]);
      expect(resp.usage.totalTokens).toBe(0);
      expect(resp.object).toBe('chat.completion');
    });

    it('should apply overrides', () => {
      const resp = createDefaultCompletionResponse({
        id: 'test-123',
        model: 'gpt-4o',
        choices: [{ index: 0, message: { role: 'assistant', content: 'Hi' }, finishReason: 'stop' }],
      });
      expect(resp.id).toBe('test-123');
      expect(resp.model).toBe('gpt-4o');
      expect(resp.choices.length).toBe(1);
    });
  });

  describe('ModelInfo factory', () => {
    it('should create model info with defaults', () => {
      const info = createDefaultModelInfo({ id: 'gpt-4o', name: 'GPT-4o' });
      expect(info.id).toBe('gpt-4o');
      expect(info.name).toBe('GPT-4o');
      expect(info.capabilities).toEqual([]);
      expect(info.contextWindow).toBe(0);
      expect(info.features).toEqual({});
    });

    it('should apply overrides', () => {
      const info = createDefaultModelInfo({
        id: 'gpt-4o',
        name: 'GPT-4o',
        capabilities: ['generation.text-generation.chat-completion'],
        contextWindow: 128000,
        features: { vision: true },
      });
      expect(info.capabilities).toEqual(['generation.text-generation.chat-completion']);
      expect(info.contextWindow).toBe(128000);
      expect(info.features.vision).toBe(true);
    });
  });

  describe('ModelPricing factory', () => {
    it('should create default pricing', () => {
      const pricing = createDefaultModelPricing();
      expect(pricing.inputPer1kTokens).toBe(0);
      expect(pricing.outputPer1kTokens).toBe(0);
      expect(pricing.perRequest).toBe(0);
    });
  });
});

describe('Rotation enums', () => {
  it('should have ModelStatus values', () => {
    expect(ModelStatus.ACTIVE).toBe('active');
    expect(ModelStatus.STANDBY).toBe('standby');
  });

  it('should have DeactivationReason values', () => {
    expect(DeactivationReason.ERROR_THRESHOLD).toBeDefined();
    expect(DeactivationReason.QUOTA_EXHAUSTED).toBeDefined();
  });

  it('should have RecoveryTrigger values', () => {
    expect(RecoveryTrigger.COOLDOWN_EXPIRED).toBeDefined();
    expect(RecoveryTrigger.MANUAL).toBeDefined();
  });
});

describe('Observability enums', () => {
  it('should have EventType values', () => {
    expect(EventType.MODEL_ACTIVATED).toBe('model_activated');
    expect(EventType.MODEL_DEACTIVATED).toBe('model_deactivated');
    expect(EventType.MODEL_ROTATED).toBe('model_rotated');
  });

  it('should have Severity values', () => {
    expect(Severity.DEBUG).toBe('debug');
    expect(Severity.INFO).toBe('info');
    expect(Severity.WARNING).toBe('warning');
    expect(Severity.ERROR).toBe('error');
    expect(Severity.CRITICAL).toBe('critical');
  });

  it('should have LogLevel values', () => {
    expect(LogLevel.METADATA).toBe('metadata');
    expect(LogLevel.SUMMARY).toBe('summary');
    expect(LogLevel.FULL).toBe('full');
  });
});

describe('Storage enums', () => {
  it('should have SyncPolicy values', () => {
    expect(SyncPolicy.IN_MEMORY).toBe('in-memory');
    expect(SyncPolicy.IMMEDIATE).toBe('immediate');
  });

  it('should have SerializationFormat values', () => {
    expect(SerializationFormat.JSON).toBe('json');
  });
});
