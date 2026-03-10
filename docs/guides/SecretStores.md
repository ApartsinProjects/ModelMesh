---
layout: default
title: "Secret Stores Guide"
---

# Secret Stores Guide

ModelMesh uses **secret store connectors** to resolve API keys and tokens at runtime. Instead of hardcoding credentials, you configure a secret store and reference secrets by name. ModelMesh ships with six built-in stores and supports custom implementations.

## Built-in Secret Stores

| Connector ID | Store | Backend | Best For |
|---|---|---|---|
| `modelmesh.env.v1` | EnvSecretStore | Environment variables | CI/CD, containers, serverless |
| `modelmesh.dotenv.v1` | DotenvSecretStore | `.env` files | Local development |
| `modelmesh.json-secrets.v1` | JsonSecretStore | JSON files | Structured configs |
| `modelmesh.memory-secrets.v1` | MemorySecretStore | In-memory dict | Testing, scripting, user-provided keys |
| `modelmesh.encrypted-file.v1` | EncryptedFileSecretStore | Encrypted JSON file | Shared configs, secure storage at rest |
| `modelmesh.keyring.v1` | KeyringSecretStore | OS keychain | Desktop apps, CLI tools |

## Quick Start

### Environment Variables (Default)

```python
import modelmesh

# Reads OPENAI_API_KEY, ANTHROPIC_API_KEY from environment
client = modelmesh.create("chat-completion")
```

### Memory Store (Testing / User-Provided Keys)

```python
from modelmesh.connectors.secret_stores import MemorySecretStore, MemorySecretStoreConfig

store = MemorySecretStore(MemorySecretStoreConfig(
    secrets={
        "OPENAI_API_KEY": "sk-abc...",
        "ANTHROPIC_API_KEY": "sk-ant...",
    }
))

# Use in configuration
config = {
    "secrets": {"connector": "modelmesh.memory-secrets.v1"},
    "providers": {...},
}
```

```typescript
import { MemorySecretStore } from '@modelmesh/core';

const store = new MemorySecretStore({
  secrets: {
    OPENAI_API_KEY: 'sk-abc...',
    ANTHROPIC_API_KEY: 'sk-ant...',
  },
});

// Runtime management
store.set('NEW_KEY', 'value123');
console.log(store.list());  // ['ANTHROPIC_API_KEY', 'NEW_KEY', 'OPENAI_API_KEY']
store.delete('NEW_KEY');
```

### Encrypted File Store

```python
from modelmesh.connectors.secret_stores import (
    EncryptedFileSecretStore,
    EncryptedFileSecretStoreConfig,
)

# Create and save encrypted secrets
store = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
    file_path="secrets.enc",
    passphrase="my-strong-passphrase",
))
store.set("OPENAI_API_KEY", "sk-abc...")
store.set("ANTHROPIC_API_KEY", "sk-ant...")
store.save()  # Writes AES-256-GCM encrypted file

# Later: load from encrypted file
store2 = EncryptedFileSecretStore(EncryptedFileSecretStoreConfig(
    file_path="secrets.enc",
    passphrase="my-strong-passphrase",
))
print(store2.get("OPENAI_API_KEY"))  # sk-abc...
```

```typescript
import { EncryptedFileSecretStore } from '@modelmesh/core';

// Create and save
const store = new EncryptedFileSecretStore({
  filePath: 'secrets.enc',
  passphrase: 'my-strong-passphrase',
});
store.set('OPENAI_API_KEY', 'sk-abc...');
store.save();

// Load later
const store2 = new EncryptedFileSecretStore({
  filePath: 'secrets.enc',
  passphrase: 'my-strong-passphrase',
});
console.log(store2.get('OPENAI_API_KEY'));
```

The encrypted file format is a JSON wrapper:

```json
{
  "version": 1,
  "algorithm": "aes-256-gcm",
  "salt": "<base64>",
  "data": "<base64 encrypted payload>"
}
```

Secrets are never stored in plaintext. The file is safe to commit to version control (though the passphrase should be kept separate).

### Dotenv Store

```python
from modelmesh.connectors.secret_stores import DotenvSecretStore, DotenvSecretStoreConfig

store = DotenvSecretStore(DotenvSecretStoreConfig(
    file_path=".env",
    override_env=False,  # env vars take precedence over file
))
api_key = store.get("OPENAI_API_KEY")
```

### JSON Store

```python
from modelmesh.connectors.secret_stores import JsonSecretStore, JsonSecretStoreConfig

store = JsonSecretStore(JsonSecretStoreConfig(
    file_path="secrets.json",
    json_path="providers",  # scope to nested object
))
# If secrets.json = {"providers": {"openai": {"key": "sk-..."}}}
key = store.get("openai.key")  # dot-notation traversal
```

### OS Keyring Store

```python
from modelmesh.connectors.secret_stores import KeyringSecretStore, KeyringSecretStoreConfig

store = KeyringSecretStore(KeyringSecretStoreConfig(
    service_name="modelmesh-prod",
))
if store.keyring_available:
    api_key = store.get("OPENAI_API_KEY")
```

```typescript
import { KeyringSecretStore } from '@modelmesh/core';

const store = new KeyringSecretStore({ serviceName: 'modelmesh-prod' });
// Async API (keytar is async)
const key = await store.getAsync('OPENAI_API_KEY');
// After preload, sync get() works
await store.preload(['OPENAI_API_KEY', 'ANTHROPIC_API_KEY']);
const key2 = store.get('OPENAI_API_KEY');  // from cache
```

## YAML Configuration

Secret stores are configured in the `secrets` section of `modelmesh.yaml`:

```yaml
secrets:
  connector: modelmesh.env.v1
  config:
    prefix: "MODELMESH_"
```

```yaml
secrets:
  connector: modelmesh.encrypted-file.v1
  config:
    file_path: secrets.enc
    passphrase: ${MODELMESH_ENCRYPTION_PASSPHRASE}
```

```yaml
secrets:
  connector: modelmesh.memory-secrets.v1
  config:
    secrets:
      OPENAI_API_KEY: sk-test-key-for-development
      ANTHROPIC_API_KEY: sk-ant-test-key
```

## Custom Secret Store Connectors

Implement the `SecretStoreConnector` interface to create a custom store:

### Python

```python
from modelmesh.cdk.base_secret_store import BaseSecretStore, BaseSecretStoreConfig

class VaultSecretStore(BaseSecretStore):
    """Custom connector for HashiCorp Vault."""

    CONNECTOR_ID = "mycompany.vault.v1"

    def __init__(self, vault_url: str, token: str):
        super().__init__(BaseSecretStoreConfig())
        self._client = VaultClient(vault_url, token)

    def _resolve(self, name: str) -> str | None:
        """Override to fetch from Vault."""
        try:
            return self._client.read_secret(name)
        except VaultError:
            return None
```

### TypeScript

```typescript
import { BaseSecretStore } from '@modelmesh/core';

class VaultSecretStore extends BaseSecretStore {
  static readonly CONNECTOR_ID = 'mycompany.vault.v1';

  constructor(private vaultUrl: string, private token: string) {
    super({});
  }

  protected _resolve(name: string): string | null {
    // Fetch from Vault API
    return this.vaultClient.readSecret(name) ?? null;
  }
}
```

### Registering Custom Stores

```python
from modelmesh.connectors import CONNECTOR_REGISTRY

CONNECTOR_REGISTRY[VaultSecretStore.CONNECTOR_ID] = VaultSecretStore
```

```typescript
import { CONNECTOR_REGISTRY } from '@modelmesh/core';

CONNECTOR_REGISTRY[VaultSecretStore.CONNECTOR_ID] = VaultSecretStore;
```

Once registered, the custom store can be referenced in YAML configuration:

```yaml
secrets:
  connector: mycompany.vault.v1
  config:
    vault_url: https://vault.internal.company.com
    token: ${VAULT_TOKEN}
```

## SecretManagement Interface

Some stores implement the optional `SecretManagement` interface for runtime credential management:

```python
from modelmesh.interfaces.secret_store import SecretManagement

# MemorySecretStore and EncryptedFileSecretStore implement this
store.set("NEW_KEY", "value")     # Add or update
names = store.list()               # List all secret names
store.delete("OLD_KEY")            # Remove a secret
```

This is useful for:
- CLI tools that provision credentials across environments
- Admin interfaces that manage API keys
- Testing scenarios that need dynamic secret injection

## Encryption Details

### EncryptedFileSecretStore

- **Algorithm**: AES-256-GCM (when `cryptography` package is installed in Python; always available in Node.js via `crypto` module)
- **Key derivation**: PBKDF2-HMAC-SHA256 with 600,000 iterations (configurable)
- **Salt**: Random 16-byte salt stored alongside encrypted data
- **Nonce**: Random 12-byte nonce per encryption
- **Fallback**: Python falls back to PBKDF2+XOR obfuscation if `cryptography` is not installed (with a different algorithm marker in the file)

### Key Options

| Option | Description |
|---|---|
| `passphrase` | Human-readable password. Key derived via PBKDF2. |
| `encryption_key` | Raw 32-byte key as 64-char hex string. |

If both are provided, `encryption_key` takes precedence.

## Security Best Practices

1. **Never hardcode API keys** in source code. Use environment variables or encrypted files.
2. **Use different stores per environment**: `.env` for development, encrypted file or cloud secret manager for production.
3. **Rotate keys regularly** and use the SecretManagement interface to update them.
4. **Keep passphrases separate** from encrypted files -- store the passphrase in an environment variable.
5. **Audit access** using observability connectors to log secret resolution events.
