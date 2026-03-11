# Capability Discovery

ModelMesh uses a hierarchical capability system to route requests. Instead of memorizing full dotted paths like `generation.text-generation.chat-completion`, you can use short aliases and the discovery API. For the complete hierarchy tree, see [Model Capabilities](../ModelCapabilities.md). For how capabilities map to [pools and routing](../SystemConcept.md), see the architecture overview.

## Capability Aliases

| Alias | Full Path |
|-------|-----------|
| `chat-completion` | `generation.text-generation.chat-completion` |
| `text-generation` | `generation.text-generation` |
| `code-generation` | `generation.text-generation.code-generation` |
| `text-embeddings` | `representation.embeddings.text-embeddings` |
| `text-to-speech` | `generation.audio.text-to-speech` |
| `speech-to-text` | `understanding.audio.speech-to-text` |
| `text-to-image` | `generation.image.text-to-image` |
| `image-to-text` | `representation.image.image-to-text` |

## Discovery API

### Python

```python
import modelmesh

# List all aliases
caps = modelmesh.capabilities.list_all()
# ['chat-completion', 'code-generation', 'image-to-text', ...]

# Resolve alias → full path
path = modelmesh.capabilities.resolve("chat-completion")
# 'generation.text-generation.chat-completion'

# Dotted paths pass through unchanged
modelmesh.capabilities.resolve("generation.text-generation")
# 'generation.text-generation'

# Unknown aliases return unchanged
modelmesh.capabilities.resolve("custom-cap")
# 'custom-cap'

# Search by keyword (case-insensitive)
modelmesh.capabilities.search("text")
# ['text-embeddings', 'text-generation', 'text-to-image', 'text-to-speech']

# View the hierarchy tree
tree = modelmesh.capabilities.tree()
# {
#   'generation': {
#     'text-generation': {
#       'chat-completion': {},
#       'code-generation': {},
#     },
#     'audio': {'text-to-speech': {}},
#     'image': {'text-to-image': {}},
#   },
#   'representation': { ... },
#   'understanding': { ... },
# }
```

### TypeScript

```typescript
import * as capabilities from '@nistrapa/modelmesh-core/capabilities';

const caps = capabilities.listAll();
const path = capabilities.resolve('chat-completion');
const matches = capabilities.search('text');
const tree = capabilities.tree();
```

## Using Capabilities

When creating a client, the capability name determines which pool handles your requests:

```python
# These are equivalent:
client = modelmesh.create("chat-completion")
client = modelmesh.create("generation.text-generation.chat-completion")
```

When calling `create()`, ModelMesh resolves the capability to find or create a pool containing all models that support it.

## Hierarchy

The capability tree follows a three-level hierarchy:

```
Category
└── Domain
    └── Specific Capability
```

Categories:
- **generation** — Create new content (text, audio, images)
- **representation** — Transform content into structured forms (embeddings, descriptions)
- **understanding** — Analyze and interpret content (transcription, classification)

## Custom Capabilities

You can register custom capabilities in your YAML configuration:

```yaml
models:
  my-model:
    provider: my-provider
    capabilities:
      - generation.custom.my-capability

pools:
  my-pool:
    capability: generation.custom.my-capability
```

Custom capability paths don't need aliases — use the full dotted path directly.

---

See also: [FAQ](FAQ.md) · [Model Capabilities](../ModelCapabilities.md) · [System Configuration](../SystemConfiguration.md)
