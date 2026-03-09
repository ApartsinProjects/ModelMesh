"""Pre-shipped ElevenLabs TTS provider connector.

Extends BaseProvider with ElevenLabs-specific API translation. The
ElevenLabs Text-to-Speech API is fundamentally different from OpenAI
chat completions: it accepts text input and returns binary audio data.
This connector bridges TTS into the OpenAI-compatible completion
interface.

Key differences from OpenAI:
- Auth uses ``xi-api-key`` header instead of ``Authorization: Bearer``.
- Endpoint is ``/v1/text-to-speech/{voice_id}``.
- Request payload is ``{"text": "...", "model_id": "...",
  "voice_settings": {...}}``.
- Response is raw binary audio (not JSON).
- ``_parse_response`` returns a CompletionResponse describing the
  audio output (size, format) since there is no text to return.

Connector ID: ``elevenlabs.tts.v1``
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    TokenUsage,
)

__all__ = [
    "ElevenLabsProviderConfig",
    "ElevenLabsProvider",
]

# -- Defaults ----------------------------------------------------------------

_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel

_DEFAULT_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
}

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="eleven_multilingual_v2",
        name="Eleven Multilingual v2",
        capabilities=["generation.audio.text-to-speech"],
        context_window=5_000,  # characters, not tokens
    ),
    ModelInfo(
        id="eleven_turbo_v2_5",
        name="Eleven Turbo v2.5",
        capabilities=["generation.audio.text-to-speech"],
        context_window=5_000,  # characters, not tokens
    ),
]


@dataclass
class ElevenLabsProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped ElevenLabs TTS provider.

    Extends BaseProviderConfig with voice selection and voice settings
    for the ElevenLabs Text-to-Speech API.

    Attributes:
        base_url: ElevenLabs API base URL. Defaults to
            ``"https://api.elevenlabs.io"``.
        voice_id: Default voice ID for TTS requests. Defaults to
            ``"21m00Tcm4TlvDq8ikWAM"`` (Rachel).
        voice_settings: Default voice settings applied to every
            request. Contains ``stability`` and ``similarity_boost``.
        output_format: Audio output format. Defaults to
            ``"mp3_44100_128"``.
        models: Model catalogue. Defaults to the built-in list of
            supported ElevenLabs models.
    """

    base_url: str = "https://api.elevenlabs.io"
    voice_id: str = _DEFAULT_VOICE_ID
    voice_settings: dict = field(
        default_factory=lambda: dict(_DEFAULT_VOICE_SETTINGS)
    )
    output_format: str = "mp3_44100_128"
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.audio.text-to-speech"]
    )


class ElevenLabsProvider(BaseProvider):
    """Pre-shipped provider connector for the ElevenLabs TTS API.

    ElevenLabs uses a completely different API format than OpenAI,
    so this connector overrides all four protected hook methods on
    BaseProvider:

    - ``_get_completion_endpoint()`` -- returns
      ``/v1/text-to-speech/{voice_id}``
    - ``_build_headers()`` -- uses ``xi-api-key`` for authentication
    - ``_build_request_payload()`` -- translates CompletionRequest
      to ElevenLabs TTS format (text, model_id, voice_settings)
    - ``_parse_response()`` -- wraps binary audio output in a
      CompletionResponse describing the result

    The connector bridges TTS into the chat completion interface:
    the text content of the first message is used as the speech text,
    and the model ID maps to an ElevenLabs model.

    Connector ID: ``elevenlabs.tts.v1``

    Usage::

        provider = ElevenLabsProvider(ElevenLabsProviderConfig(
            api_key="...",
            voice_id="21m00Tcm4TlvDq8ikWAM",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "elevenlabs.tts.v1"

    def __init__(self, config: ElevenLabsProviderConfig | None = None) -> None:
        if config is None:
            config = ElevenLabsProviderConfig()
        super().__init__(config)
        self._elevenlabs_config = config

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the ElevenLabs TTS endpoint.

        The ElevenLabs API uses ``/v1/text-to-speech/{voice_id}``
        with optional ``output_format`` query parameter.
        """
        base = self._config.base_url.rstrip("/")
        voice_id = self._elevenlabs_config.voice_id
        output_format = self._elevenlabs_config.output_format
        return f"{base}/v1/text-to-speech/{voice_id}?output_format={output_format}"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with ElevenLabs-specific authentication.

        ElevenLabs uses ``xi-api-key`` for authentication instead of
        the ``Authorization: Bearer`` scheme.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._config.api_key:
            headers["xi-api-key"] = self._config.api_key
        return headers

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a CompletionRequest to the ElevenLabs TTS format.

        Extracts the text content from the first message in the
        request and maps the model ID to an ElevenLabs model. Voice
        settings are taken from the provider configuration.
        """
        # Extract text from the first message content
        text = ""
        for msg in request.messages:
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if content:
                text = content
                break

        payload: dict = {
            "text": text,
            "model_id": request.model,
            "voice_settings": dict(self._elevenlabs_config.voice_settings),
        }

        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Wrap audio output metadata in a CompletionResponse.

        Since ElevenLabs returns binary audio, this method creates a
        CompletionResponse where the content describes the audio
        output (size and format). The actual audio bytes are handled
        by the transport layer.

        Note: This method receives parsed JSON data from the base
        class. For actual TTS requests, the ``_http_post_audio``
        method should be used instead, which handles binary responses.
        """
        # If we get JSON back, it's likely an error response
        error_msg = data.get("detail", {})
        if isinstance(error_msg, dict):
            error_msg = error_msg.get("message", "Unknown error")

        return CompletionResponse(
            id="",
            model="",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=f"TTS Error: {error_msg}",
                    ),
                    finish_reason="stop",
                )
            ],
            usage=TokenUsage(),
        )

    def _http_post_audio(
        self, url: str, payload: dict, headers: dict[str, str]
    ) -> bytes:
        """Send a synchronous HTTP POST and return raw binary audio.

        Unlike ``_http_post``, this method returns the raw response
        bytes (audio data) instead of parsing JSON.
        """
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
            return resp.read()

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a TTS request and return a response describing the audio.

        Overrides the base ``complete`` to handle binary audio
        responses. The audio bytes are captured and the response
        describes the output (size, format).
        """
        import asyncio
        import time as _time

        component = f"provider.{request.model}"
        self._trace(
            "DEBUG",
            component,
            f"Sending TTS request for model '{request.model}'",
            model=request.model,
        )

        payload = self._build_request_payload(request)
        headers = self._build_headers()
        endpoint = self._get_completion_endpoint()
        start_time = _time.monotonic()

        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                audio_bytes = await asyncio.to_thread(
                    self._http_post_audio, endpoint, payload, headers
                )

                # Calculate audio size for the response description
                audio_size_kb = len(audio_bytes) / 1024
                output_format = self._elevenlabs_config.output_format
                char_count = len(payload.get("text", ""))

                result = CompletionResponse(
                    id="",
                    model=request.model,
                    choices=[
                        CompletionChoice(
                            index=0,
                            message=ChatMessage(
                                role="assistant",
                                content=(
                                    f"Audio generated successfully. "
                                    f"Format: {output_format}, "
                                    f"Size: {audio_size_kb:.1f} KB, "
                                    f"Input characters: {char_count}"
                                ),
                            ),
                            finish_reason="stop",
                        )
                    ],
                    usage=TokenUsage(
                        prompt_tokens=char_count,
                        completion_tokens=0,
                        total_tokens=char_count,
                    ),
                )

                self.report_usage(request.model, result.usage)
                latency_ms = (_time.monotonic() - start_time) * 1000
                self._trace(
                    "INFO",
                    component,
                    f"TTS succeeded for model '{request.model}'",
                    model=request.model,
                    latency_ms=round(latency_ms, 2),
                    audio_size_kb=round(audio_size_kb, 1),
                    input_chars=char_count,
                )
                return result

            except Exception as exc:
                last_error = exc
                classification = self.classify_error(exc)
                if (
                    not classification.retryable
                    or attempt == self._config.max_retries
                ):
                    self._trace(
                        "ERROR",
                        component,
                        f"Non-retryable error for model "
                        f"'{request.model}': {exc}",
                        error=str(exc),
                        model=request.model,
                        attempt=attempt + 1,
                        category=classification.category,
                    )
                    raise
                self._trace(
                    "WARNING",
                    component,
                    f"Retryable error for model '{request.model}' "
                    f"(attempt {attempt + 1}): {exc}",
                    error=str(exc),
                    model=request.model,
                    attempt=attempt + 1,
                    category=classification.category,
                )
                retry_after: float = 2 ** attempt
                raw_retry = getattr(
                    getattr(exc, "headers", None), "get", lambda _: None
                )("Retry-After")
                if raw_retry is not None:
                    try:
                        retry_after = float(raw_retry)
                    except (ValueError, TypeError):
                        pass
                await asyncio.sleep(retry_after)

        raise last_error  # type: ignore[misc]
