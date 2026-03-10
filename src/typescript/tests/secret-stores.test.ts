/**
 * Comprehensive tests for all secret store connectors.
 *
 * Tests cover: MemorySecretStore, EncryptedFileSecretStore, EnvSecretStore,
 * DotenvSecretStore, JsonSecretStore, KeyringSecretStore, BaseSecretStore,
 * custom secret store connectors, and configuration integration.
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { BaseSecretStore } from '@/cdk/base-secret-store';
import type { BaseSecretStoreConfig } from '@/cdk/base-secret-store';
import { EnvSecretStore } from '@/connectors/secret-stores/env-store';
import { DotenvSecretStore } from '@/connectors/secret-stores/dotenv-store';
import { JsonSecretStore } from '@/connectors/secret-stores/json-store';
import { MemorySecretStore } from '@/connectors/secret-stores/memory-store';
import { EncryptedFileSecretStore } from '@/connectors/secret-stores/encrypted-file-store';
import { KeyringSecretStore } from '@/connectors/secret-stores/keyring-store';
import { CONNECTOR_REGISTRY } from '@/connectors';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function tmpFile(ext: string): string {
  return path.join(os.tmpdir(), `modelmesh-test-${Date.now()}-${Math.random().toString(36).slice(2)}${ext}`);
}

// ---------------------------------------------------------------------------
// MemorySecretStore
// ---------------------------------------------------------------------------

describe('MemorySecretStore', () => {
  test('has correct connector ID', () => {
    expect(MemorySecretStore.CONNECTOR_ID).toBe('modelmesh.memory-secrets.v1');
  });

  test('creates with secrets', () => {
    const store = new MemorySecretStore({
      secrets: { KEY1: 'val1', KEY2: 'val2' },
    });
    expect(store.get('KEY1')).toBe('val1');
    expect(store.get('KEY2')).toBe('val2');
  });

  test('creates empty by default', () => {
    const store = new MemorySecretStore();
    expect(() => store.get('NONEXISTENT')).toThrow('Secret not found');
  });

  test('returns empty string when failOnMissing is false', () => {
    const store = new MemorySecretStore({ failOnMissing: false });
    expect(store.get('NONEXISTENT')).toBe('');
  });

  test('set and get', () => {
    const store = new MemorySecretStore();
    store.set('NEW_KEY', 'new_value');
    expect(store.get('NEW_KEY')).toBe('new_value');
  });

  test('set overwrites existing', () => {
    const store = new MemorySecretStore({ secrets: { KEY: 'old' } });
    store.set('KEY', 'new');
    expect(store.get('KEY')).toBe('new');
  });

  test('list returns sorted names', () => {
    const store = new MemorySecretStore({
      secrets: { B: '2', A: '1', C: '3' },
    });
    expect(store.list()).toEqual(['A', 'B', 'C']);
  });

  test('delete removes secret', () => {
    const store = new MemorySecretStore({ secrets: { KEY: 'val' } });
    store.delete('KEY');
    expect(() => store.get('KEY')).toThrow();
  });

  test('delete nonexistent throws', () => {
    const store = new MemorySecretStore();
    expect(() => store.delete('NONEXISTENT')).toThrow('Secret not found');
  });

  test('is drop-in replacement for any SecretStoreConnector', () => {
    const store = new MemorySecretStore({ secrets: { API_KEY: 'sk-test' } });
    // Can be used anywhere a SecretStoreConnector is expected
    const getKey = (s: { get(name: string): string }) => s.get('API_KEY');
    expect(getKey(store)).toBe('sk-test');
  });
});

// ---------------------------------------------------------------------------
// EncryptedFileSecretStore
// ---------------------------------------------------------------------------

describe('EncryptedFileSecretStore', () => {
  test('has correct connector ID', () => {
    expect(EncryptedFileSecretStore.CONNECTOR_ID).toBe('modelmesh.encrypted-file.v1');
  });

  test('in-memory mode without file', () => {
    const store = new EncryptedFileSecretStore({ passphrase: 'test' });
    store.set('KEY', 'value123');
    expect(store.get('KEY')).toBe('value123');
  });

  test('save and load with passphrase', () => {
    const filePath = tmpFile('.enc');
    try {
      // Create and save
      const store1 = new EncryptedFileSecretStore({
        filePath,
        passphrase: 'strong-pass-123',
      });
      store1.set('API_KEY', 'sk-test-12345');
      store1.set('SECRET', 'super-secret');
      store1.save();

      // Verify file exists and is JSON
      const raw = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      expect(raw.version).toBe(1);
      expect(raw.algorithm).toBe('aes-256-gcm');
      expect(raw.salt).toBeDefined();
      expect(raw.data).toBeDefined();

      // Load in new instance
      const store2 = new EncryptedFileSecretStore({
        filePath,
        passphrase: 'strong-pass-123',
      });
      expect(store2.get('API_KEY')).toBe('sk-test-12345');
      expect(store2.get('SECRET')).toBe('super-secret');
    } finally {
      if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    }
  });

  test('save and load with hex key', () => {
    const filePath = tmpFile('.enc');
    const hexKey = 'a'.repeat(64);
    try {
      const store1 = new EncryptedFileSecretStore({
        filePath,
        encryptionKey: hexKey,
      });
      store1.set('KEY', 'value');
      store1.save();

      const store2 = new EncryptedFileSecretStore({
        filePath,
        encryptionKey: hexKey,
      });
      expect(store2.get('KEY')).toBe('value');
    } finally {
      if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    }
  });

  test('wrong passphrase fails gracefully', () => {
    const filePath = tmpFile('.enc');
    try {
      const store1 = new EncryptedFileSecretStore({
        filePath,
        passphrase: 'correct-password',
      });
      store1.set('KEY', 'secret');
      store1.save();

      const store2 = new EncryptedFileSecretStore({
        filePath,
        passphrase: 'wrong-password',
        failOnMissing: false,
      });
      expect(store2.get('KEY')).toBe('');
    } finally {
      if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    }
  });

  test('invalid hex key length throws', () => {
    expect(() => {
      new EncryptedFileSecretStore({ encryptionKey: 'tooshort' });
    }).toThrow('64-character hex string');
  });

  test('list and delete', () => {
    const store = new EncryptedFileSecretStore({ passphrase: 'test' });
    store.set('A', '1');
    store.set('B', '2');
    expect(store.list()).toEqual(['A', 'B']);
    store.delete('A');
    expect(store.list()).toEqual(['B']);
  });

  test('delete nonexistent throws', () => {
    const store = new EncryptedFileSecretStore({ passphrase: 'test' });
    expect(() => store.delete('NOPE')).toThrow('Secret not found');
  });

  test('save without file path throws', () => {
    const store = new EncryptedFileSecretStore({ passphrase: 'test' });
    expect(() => store.save()).toThrow('No filePath configured');
  });

  test('encrypted file does not contain plaintext', () => {
    const filePath = tmpFile('.enc');
    try {
      const store = new EncryptedFileSecretStore({
        filePath,
        passphrase: 'test',
      });
      store.set('MY_SECRET', 'super-secret-value-12345');
      store.save();

      const content = fs.readFileSync(filePath, 'utf-8');
      expect(content).not.toContain('super-secret-value-12345');
      expect(content).not.toContain('MY_SECRET');
    } finally {
      if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    }
  });

  test('nonexistent file creates empty store', () => {
    const store = new EncryptedFileSecretStore({
      filePath: '/nonexistent/path/secrets.enc',
      passphrase: 'test',
      failOnMissing: false,
    });
    expect(store.get('KEY')).toBe('');
  });
});

// ---------------------------------------------------------------------------
// EnvSecretStore
// ---------------------------------------------------------------------------

describe('EnvSecretStore', () => {
  test('has correct connector ID', () => {
    expect(EnvSecretStore.CONNECTOR_ID).toBe('modelmesh.env.v1');
  });

  test('reads environment variables', () => {
    process.env.TEST_ENV_SS_KEY = 'test-value';
    try {
      const store = new EnvSecretStore();
      expect(store.get('TEST_ENV_SS_KEY')).toBe('test-value');
    } finally {
      delete process.env.TEST_ENV_SS_KEY;
    }
  });

  test('returns empty for missing when failOnMissing is false', () => {
    const store = new EnvSecretStore({ failOnMissing: false });
    expect(store.get('DEFINITELY_NOT_SET_12345')).toBe('');
  });

  test('throws for missing when failOnMissing is true', () => {
    const store = new EnvSecretStore({ failOnMissing: true });
    expect(() => store.get('DEFINITELY_NOT_SET_12345')).toThrow();
  });

  test('supports prefix', () => {
    process.env.MM_TEST_KEY = 'prefixed-value';
    try {
      const store = new EnvSecretStore({ prefix: 'MM_' });
      expect(store.get('TEST_KEY')).toBe('prefixed-value');
    } finally {
      delete process.env.MM_TEST_KEY;
    }
  });
});

// ---------------------------------------------------------------------------
// DotenvSecretStore
// ---------------------------------------------------------------------------

describe('DotenvSecretStore', () => {
  test('has correct connector ID', () => {
    expect(DotenvSecretStore.CONNECTOR_ID).toBe('modelmesh.dotenv.v1');
  });

  test('parses basic KEY=value lines', () => {
    const filePath = tmpFile('.env');
    fs.writeFileSync(filePath, 'API_KEY=sk-test123\nSECRET=mysecret\n');
    try {
      const store = new DotenvSecretStore({ filePath });
      expect(store.get('API_KEY')).toBe('sk-test123');
      expect(store.get('SECRET')).toBe('mysecret');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('handles comments and blank lines', () => {
    const filePath = tmpFile('.env');
    fs.writeFileSync(filePath, '# Comment\n\nKEY=value\n');
    try {
      const store = new DotenvSecretStore({ filePath });
      expect(store.get('KEY')).toBe('value');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('handles quoted values', () => {
    const filePath = tmpFile('.env');
    fs.writeFileSync(filePath, 'KEY1="double quoted"\nKEY2=\'single quoted\'\n');
    try {
      const store = new DotenvSecretStore({ filePath });
      expect(store.get('KEY1')).toBe('double quoted');
      expect(store.get('KEY2')).toBe('single quoted');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('env var override precedence', () => {
    const filePath = tmpFile('.env');
    fs.writeFileSync(filePath, 'MY_TEST_KEY=from-file\n');
    process.env.MY_TEST_KEY = 'from-env';
    try {
      const store = new DotenvSecretStore({ filePath, overrideEnv: false });
      expect(store.get('MY_TEST_KEY')).toBe('from-env');
    } finally {
      delete process.env.MY_TEST_KEY;
      fs.unlinkSync(filePath);
    }
  });

  test('file override precedence', () => {
    const filePath = tmpFile('.env');
    fs.writeFileSync(filePath, 'MY_TEST_KEY2=from-file\n');
    process.env.MY_TEST_KEY2 = 'from-env';
    try {
      const store = new DotenvSecretStore({ filePath, overrideEnv: true });
      expect(store.get('MY_TEST_KEY2')).toBe('from-file');
    } finally {
      delete process.env.MY_TEST_KEY2;
      fs.unlinkSync(filePath);
    }
  });

  test('missing file with failOnMissing false', () => {
    const store = new DotenvSecretStore({
      filePath: '/nonexistent/.env',
      failOnMissing: false,
    });
    expect(store.get('ANYTHING')).toBe('');
  });
});

// ---------------------------------------------------------------------------
// JsonSecretStore
// ---------------------------------------------------------------------------

describe('JsonSecretStore', () => {
  test('has correct connector ID', () => {
    expect(JsonSecretStore.CONNECTOR_ID).toBe('modelmesh.json-secrets.v1');
  });

  test('reads flat JSON', () => {
    const filePath = tmpFile('.json');
    fs.writeFileSync(filePath, JSON.stringify({ KEY1: 'val1', KEY2: 'val2' }));
    try {
      const store = new JsonSecretStore({ filePath });
      expect(store.get('KEY1')).toBe('val1');
      expect(store.get('KEY2')).toBe('val2');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('supports dot-notation for nested keys', () => {
    const filePath = tmpFile('.json');
    fs.writeFileSync(
      filePath,
      JSON.stringify({
        providers: { openai: { api_key: 'sk-test' } },
      })
    );
    try {
      const store = new JsonSecretStore({ filePath });
      expect(store.get('providers.openai.api_key')).toBe('sk-test');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('supports jsonPath scoping', () => {
    const filePath = tmpFile('.json');
    fs.writeFileSync(
      filePath,
      JSON.stringify({
        secrets: { production: { API_KEY: 'prod-key' } },
      })
    );
    try {
      const store = new JsonSecretStore({
        filePath,
        jsonPath: 'secrets.production',
      });
      expect(store.get('API_KEY')).toBe('prod-key');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('missing key throws when failOnMissing is true', () => {
    const filePath = tmpFile('.json');
    fs.writeFileSync(filePath, JSON.stringify({ KEY: 'val' }));
    try {
      const store = new JsonSecretStore({ filePath, failOnMissing: true });
      expect(() => store.get('MISSING')).toThrow();
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('missing key returns empty when failOnMissing is false', () => {
    const filePath = tmpFile('.json');
    fs.writeFileSync(filePath, JSON.stringify({ KEY: 'val' }));
    try {
      const store = new JsonSecretStore({ filePath, failOnMissing: false });
      expect(store.get('MISSING')).toBe('');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  test('converts numeric values to strings', () => {
    const filePath = tmpFile('.json');
    fs.writeFileSync(filePath, JSON.stringify({ PORT: 8080 }));
    try {
      const store = new JsonSecretStore({ filePath });
      expect(store.get('PORT')).toBe('8080');
    } finally {
      fs.unlinkSync(filePath);
    }
  });
});

// ---------------------------------------------------------------------------
// KeyringSecretStore
// ---------------------------------------------------------------------------

describe('KeyringSecretStore', () => {
  test('has correct connector ID', () => {
    expect(KeyringSecretStore.CONNECTOR_ID).toBe('modelmesh.keyring.v1');
  });

  test('default service name', () => {
    const store = new KeyringSecretStore();
    expect(store.keytarAvailable).toBeDefined();
  });

  test('custom service name', () => {
    const store = new KeyringSecretStore({ serviceName: 'my-app' });
    expect(store.keytarAvailable).toBeDefined();
  });

  test('get from empty cache throws when failOnMissing', () => {
    const store = new KeyringSecretStore({ failOnMissing: true });
    expect(() => store.get('MISSING')).toThrow();
  });

  test('get from empty cache returns empty when not failOnMissing', () => {
    const store = new KeyringSecretStore({ failOnMissing: false });
    expect(store.get('MISSING')).toBe('');
  });

  test('clearCache works', () => {
    const store = new KeyringSecretStore({ failOnMissing: false });
    store.clearCache();
    expect(store.get('KEY')).toBe('');
  });
});

// ---------------------------------------------------------------------------
// BaseSecretStore
// ---------------------------------------------------------------------------

describe('BaseSecretStore', () => {
  test('resolves from config secrets', () => {
    const store = new BaseSecretStore({ secrets: { KEY: 'val' } });
    expect(store.get('KEY')).toBe('val');
  });

  test('throws on missing when failOnMissing is true', () => {
    const store = new BaseSecretStore({ failOnMissing: true });
    expect(() => store.get('MISSING')).toThrow('Secret not found');
  });

  test('returns empty on missing when failOnMissing is false', () => {
    const store = new BaseSecretStore({ failOnMissing: false });
    expect(store.get('MISSING')).toBe('');
  });

  test('caching works', () => {
    const config: BaseSecretStoreConfig = {
      secrets: { K: 'original' },
      cacheEnabled: true,
    };
    const store = new BaseSecretStore(config);
    expect(store.get('K')).toBe('original');
    // Modify backing data
    config.secrets!['K'] = 'changed';
    // Should still return cached value
    expect(store.get('K')).toBe('original');
  });

  test('cache disabled returns fresh values', () => {
    const config: BaseSecretStoreConfig = {
      secrets: { K: 'original' },
      cacheEnabled: false,
    };
    const store = new BaseSecretStore(config);
    expect(store.get('K')).toBe('original');
  });

  test('clearCache works', () => {
    const config: BaseSecretStoreConfig = {
      secrets: { K: 'original' },
      cacheEnabled: true,
    };
    const store = new BaseSecretStore(config);
    store.get('K');
    store.clearCache();
    // After cache clear, re-resolves from backend
    expect(store.get('K')).toBe('original');
  });

  test('custom subclass with _resolve override', () => {
    class VaultStore extends BaseSecretStore {
      static readonly CONNECTOR_ID = 'mycompany.vault.v1';
      private _vault: Record<string, string>;

      constructor(vault: Record<string, string>) {
        super({});
        this._vault = vault;
      }

      protected _resolve(name: string): string | null {
        return this._vault[name] ?? null;
      }
    }

    const store = new VaultStore({ db_password: 's3cr3t', api_token: 'tok-123' });
    expect(store.get('db_password')).toBe('s3cr3t');
    expect(store.get('api_token')).toBe('tok-123');
  });
});

// ---------------------------------------------------------------------------
// ConnectorRegistry integration
// ---------------------------------------------------------------------------

describe('SecretStore ConnectorRegistry', () => {
  test('all stores are registered', () => {
    const expectedIds = [
      'modelmesh.env.v1',
      'modelmesh.dotenv.v1',
      'modelmesh.json-secrets.v1',
      'modelmesh.memory-secrets.v1',
      'modelmesh.encrypted-file.v1',
      'modelmesh.keyring.v1',
    ];
    for (const id of expectedIds) {
      expect(id in CONNECTOR_REGISTRY).toBe(true);
    }
  });

  test('registry classes match', () => {
    expect(CONNECTOR_REGISTRY['modelmesh.memory-secrets.v1']).toBe(MemorySecretStore);
    expect(CONNECTOR_REGISTRY['modelmesh.encrypted-file.v1']).toBe(EncryptedFileSecretStore);
    expect(CONNECTOR_REGISTRY['modelmesh.env.v1']).toBe(EnvSecretStore);
    expect(CONNECTOR_REGISTRY['modelmesh.keyring.v1']).toBe(KeyringSecretStore);
  });
});

// ---------------------------------------------------------------------------
// Interoperability tests
// ---------------------------------------------------------------------------

describe('SecretStore interoperability', () => {
  test('all stores share the same get interface', () => {
    const stores: Array<{ get(name: string): string }> = [
      new MemorySecretStore({ secrets: { K: 'v' }, failOnMissing: false }),
      new EnvSecretStore({ failOnMissing: false }),
      new BaseSecretStore({ secrets: { K: 'v' }, failOnMissing: false }),
    ];

    for (const store of stores) {
      const result = store.get('NONEXISTENT_KEY_12345');
      expect(typeof result).toBe('string');
    }
  });

  test('MemorySecretStore as drop-in replacement', () => {
    const getApiKey = (store: { get(name: string): string }) => store.get('API_KEY');
    const store = new MemorySecretStore({ secrets: { API_KEY: 'sk-memory' } });
    expect(getApiKey(store)).toBe('sk-memory');
  });
});
