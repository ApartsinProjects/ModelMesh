# OpenAIClient

Drop-in replacement for the OpenAI SDK. The client translates standard OpenAI API calls into capability-based routing through virtual model names. Applications use this client exactly as they would use the official OpenAI SDK; the library resolves virtual names to real models and providers transparently. Virtual model names map to configured capability pools -- a call to `chat.completions.create(model="text-generation", ...)` resolves to the best active model in the `text-generation` pool.

**Depends on:** [Router](Router.md)

---

## Python

```python
from __future__ import annotations
from typing import Any, Optional, BinaryIO, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


@dataclass
class CompletionResponse:
    """Normalized response returned from a chat completion."""
    id: str
    model: str
    choices: list[dict]
    usage: dict


@dataclass
class EmbeddingResponse:
    """Response returned from an embedding request."""
    data: list[dict]
    model: str
    usage: dict


@dataclass
class TranscriptionResponse:
    """Response returned from a speech-to-text request."""
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    segments: Optional[list[dict]] = None


@dataclass
class ImageResponse:
    """Response returned from an image generation request."""
    created: int
    data: list[dict]


class AudioSpeech:
    """Text-to-speech generation sub-client."""

    async def create(
        self,
        model: str,
        input: str,
        voice: str,
        response_format: str = "mp3",
        speed: float = 1.0,
        **kwargs: Any,
    ) -> bytes:
        """Generate speech audio from text.

        Routes to the best active model in the pool matching the
        virtual model name.

        Args:
            model: Virtual model name (resolves to a capability pool).
            input: Text to convert to speech.
            voice: Voice identifier for the output.
            response_format: Audio format (mp3, opus, aac, flac).
            speed: Playback speed multiplier.

        Returns:
            Raw audio bytes in the requested format.
        """
        ...


class AudioTranscriptions:
    """Speech-to-text transcription sub-client."""

    async def create(
        self,
        model: str,
        file: BinaryIO,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "json",
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> TranscriptionResponse:
        """Transcribe audio to text.

        Routes to the best active model in the pool matching the
        virtual model name.

        Args:
            model: Virtual model name (resolves to a capability pool).
            file: Audio file to transcribe.
            language: ISO-639-1 language code hint.
            prompt: Optional prompt to guide transcription.
            response_format: Output format (json, text, srt, vtt).
            temperature: Sampling temperature.

        Returns:
            Transcription result with text and optional metadata.
        """
        ...


class Audio:
    """Audio operations sub-client grouping speech and transcription."""
    speech: AudioSpeech
    transcriptions: AudioTranscriptions


class ChatCompletions:
    """Chat completion sub-client."""

    async def create(
        self,
        model: str,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Execute a chat completion request.

        Routes to the best active model in the pool matching the
        virtual model name. Supports both synchronous and streaming
        delivery modes.

        Args:
            model: Virtual model name (resolves to a capability pool).
            messages: Conversation messages in OpenAI format.
            temperature: Sampling temperature (0.0--2.0).
            max_tokens: Maximum tokens to generate.
            tools: Tool definitions for function calling.
            stream: If True, return a streaming response.

        Returns:
            The completion response from the selected model.
        """
        ...


class Embeddings:
    """Embedding generation sub-client."""

    async def create(
        self,
        model: str,
        input: str | list[str],
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings for the given input.

        Routes to the best active model in the pool matching the
        virtual model name.

        Args:
            model: Virtual model name (resolves to a capability pool).
            input: Text or list of texts to embed.
            encoding_format: Output format (float, base64).
            dimensions: Desired embedding dimensions (if supported).

        Returns:
            Embedding vectors with usage metadata.
        """
        ...


class Images:
    """Image generation sub-client."""

    async def generate(
        self,
        model: str,
        prompt: str,
        n: int = 1,
        size: str = "1024x1024",
        quality: str = "standard",
        response_format: str = "url",
        **kwargs: Any,
    ) -> ImageResponse:
        """Generate images from a text prompt.

        Routes to the best active model in the pool matching the
        virtual model name.

        Args:
            model: Virtual model name (resolves to a capability pool).
            prompt: Text description of the desired image.
            n: Number of images to generate.
            size: Image dimensions (e.g., "1024x1024").
            quality: Image quality (standard, hd).
            response_format: Output format (url, b64_json).

        Returns:
            Generated image data or URLs.
        """
        ...


class OpenAIClient:
    """Drop-in replacement for the OpenAI SDK.

    Translates standard OpenAI API calls into capability-based routing
    through virtual model names. Applications use this client exactly
    as they would use the official OpenAI SDK.
    """
    chat: ChatCompletions
    embeddings: Embeddings
    audio: Audio
    images: Images
```

## TypeScript

```typescript
/** Normalized response returned from a chat completion. */
interface CompletionResponse {
    id: string;
    model: string;
    choices: Record<string, unknown>[];
    usage: Record<string, number>;
}

/** Response returned from an embedding request. */
interface EmbeddingResponse {
    data: Record<string, unknown>[];
    model: string;
    usage: Record<string, number>;
}

/** Response returned from a speech-to-text request. */
interface TranscriptionResponse {
    text: string;
    language?: string;
    duration?: number;
    segments?: Record<string, unknown>[];
}

/** Response returned from an image generation request. */
interface ImageResponse {
    created: number;
    data: Record<string, unknown>[];
}

/** Text-to-speech generation sub-client. */
interface AudioSpeech {
    /** Generate speech audio from text. */
    create(params: {
        model: string;
        input: string;
        voice: string;
        response_format?: string;
        speed?: number;
    }): Promise<ArrayBuffer>;
}

/** Speech-to-text transcription sub-client. */
interface AudioTranscriptions {
    /** Transcribe audio to text. */
    create(params: {
        model: string;
        file: Blob;
        language?: string;
        prompt?: string;
        response_format?: string;
        temperature?: number;
    }): Promise<TranscriptionResponse>;
}

/** Audio operations sub-client. */
interface Audio {
    speech: AudioSpeech;
    transcriptions: AudioTranscriptions;
}

/** Chat completion sub-client. */
interface ChatCompletions {
    /** Execute a chat completion request. */
    create(params: {
        model: string;
        messages: Record<string, unknown>[];
        temperature?: number;
        max_tokens?: number;
        tools?: Record<string, unknown>[];
        stream?: boolean;
    }): Promise<CompletionResponse>;
}

/** Embedding generation sub-client. */
interface Embeddings {
    /** Generate embeddings for the given input. */
    create(params: {
        model: string;
        input: string | string[];
        encoding_format?: string;
        dimensions?: number;
    }): Promise<EmbeddingResponse>;
}

/** Image generation sub-client. */
interface Images {
    /** Generate images from a text prompt. */
    generate(params: {
        model: string;
        prompt: string;
        n?: number;
        size?: string;
        quality?: string;
        response_format?: string;
    }): Promise<ImageResponse>;
}

/** Drop-in replacement for the OpenAI SDK. */
interface OpenAIClient {
    chat: ChatCompletions;
    embeddings: Embeddings;
    audio: Audio;
    images: Images;
}
```
