---
layout: default
title: "Model Capability Taxonomy"
---

# Model Capability Taxonomy

**The complete capability hierarchy for ModelMesh Lite.** Models register at leaf nodes; pools target any node and include all descendants. The hierarchy is extensible — custom categories, subcategories, and leaf nodes follow the same routing, pooling, and inheritance rules as pre-shipped ones. For the programmatic discovery API, see [Capability Discovery](guides/Capabilities.html). For which providers support which capabilities, see [Connector Catalogue](ConnectorCatalogue.html).

---

## Capability Hierarchy

```
capability
│
├── generation
│   ├── text-generation
│   │   ├── chat-completion
│   │   ├── text-completion
│   │   └── code-generation
│   ├── structured-generation
│   │   ├── json-generation
│   │   ├── schema-constrained-output
│   │   └── function-call-generation
│   ├── image-generation
│   │   ├── text-to-image
│   │   ├── image-to-image
│   │   └── inpainting
│   ├── audio-generation
│   │   ├── text-to-speech
│   │   └── music-generation
│   └── video-generation
│       ├── text-to-video
│       └── image-to-video
│
├── understanding
│   ├── text-understanding
│   │   ├── summarization
│   │   ├── classification
│   │   ├── sentiment-analysis
│   │   └── entity-extraction
│   ├── vision-understanding
│   │   ├── image-captioning
│   │   ├── object-detection
│   │   └── ocr
│   ├── audio-understanding
│   │   ├── speech-to-text
│   │   ├── speaker-identification
│   │   └── audio-classification
│   └── document-understanding
│       ├── document-parsing
│       ├── table-extraction
│       └── form-extraction
│
├── transformation
│   ├── translation
│   ├── rewriting
│   ├── style-transfer
│   ├── image-editing
│   │   ├── background-removal
│   │   ├── upscaling
│   │   └── format-conversion
│   └── audio-processing
│       ├── noise-reduction
│       ├── voice-cloning
│       └── audio-separation
│
├── representation
│   ├── embeddings
│   │   ├── text-embeddings
│   │   ├── image-embeddings
│   │   └── multimodal-embeddings
│   ├── tokenization
│   └── feature-extraction
│
├── retrieval
│   ├── search
│   │   ├── semantic-search
│   │   ├── web-search
│   │   ├── image-search
│   │   └── code-search
│   ├── knowledge-graph
│   │   ├── graph-query
│   │   ├── entity-linking
│   │   └── relation-extraction
│   ├── rag
│   │   ├── retrieval-augmented-generation
│   │   └── grounded-generation
│   └── reranking
│
├── interaction
│   ├── tool-calling
│   ├── agent-execution
│   │   ├── single-step-agent
│   │   └── multi-step-agent
│   └── multi-turn-conversation
│
└── evaluation
    ├── content-moderation
    ├── toxicity-detection
    ├── factuality-checking
    └── quality-scoring
```

---

## Category Summary

| Category | Produces | Example leaves |
| --- | --- | --- |
| **generation** | new content | chat-completion, text-to-image, text-to-speech |
| **understanding** | analysis of input | summarization, ocr, speech-to-text |
| **transformation** | converted content | translation, background-removal, voice-cloning |
| **representation** | encoded data | text-embeddings, image-embeddings |
| **retrieval** | found information | semantic-search, grounded-generation, reranking |
| **interaction** | multi-step behavior | tool-calling, agent-execution |
| **evaluation** | quality assessment | content-moderation, factuality-checking |

---

## Routing Rules

- Models register at **leaf nodes** only.
- Pools can target **any node** (category, subcategory, or leaf) and include all descendants.
- Requesting a category (e.g., `understanding`) matches all models under that category.
- Requesting a leaf (e.g., `ocr`) matches only models registered at that leaf.
- A model registered at multiple leaves appears in multiple ancestor pools automatically.

---

## Predefined Capability Pools

| Pool | Hierarchy node | Input → Output |
| --- | --- | --- |
| `text-generation` | generation.text-generation | prompt → text |
| `structured-generation` | generation.structured-generation | prompt → JSON |
| `image-generation` | generation.image-generation | prompt → image |
| `embeddings` | representation.embeddings | text → vector |
| `speech-to-text` | understanding.audio-understanding.speech-to-text | audio → text |
| `text-to-speech` | generation.audio-generation.text-to-speech | text → audio |
| `vision-understanding` | understanding.vision-understanding | image → text |

Users add custom pools (e.g., `code-review`, `medical-summarization`, `long-context-analysis`) targeting any hierarchy node. See [SystemConcept.md — Capability-Based Model Pools](SystemConcept.html#capability-based-model-pools) for static and dynamic pool definitions.

---

## Extending the Hierarchy

Custom categories, subcategories, and leaf nodes can be added at any level (e.g., `compliance` → `pii-detection`, `regulatory-review`). Custom nodes follow the same routing, pooling, and inheritance rules as pre-shipped ones. Extension points are defined via [YAML configuration](SystemConfiguration.html) or at runtime through the API — see [Capability Discovery](guides/Capabilities.html) for both approaches.

---

See also: [System Concept](SystemConcept.html) · [Capability Discovery Guide](guides/Capabilities.html) · [Connector Catalogue](ConnectorCatalogue.html) · [FAQ](guides/FAQ.html)
