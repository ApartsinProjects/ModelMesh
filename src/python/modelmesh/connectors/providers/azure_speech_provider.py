"""Pre-shipped Azure Speech TTS provider connector.

Extends BaseProvider with Microsoft Azure Speech Services API
translation. The Azure Cognitive Services Speech REST API accepts
SSML (Speech Synthesis Markup Language) XML and returns raw binary
audio data.

Key differences from OpenAI:
- Auth uses ``Ocp-Apim-Subscription-Key`` header.
- Endpoint is region-specific:
  ``https://{region}.tts.speech.microsoft.com/cognitiveservices/v1``.
- Content-Type is ``application/ssml+xml`` (not JSON).
- Request body is SSML XML, not JSON.
- Response is raw binary audio (not JSON).
- ``X-Microsoft-OutputFormat`` header controls audio format.

Connector ID: ``azure.tts.v1``
"""
from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

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
    "AzureSpeechProviderConfig",
    "AzureSpeechProvider",
]

# -- Defaults ----------------------------------------------------------------

_DEFAULT_REGION = "eastus"
_DEFAULT_VOICE = "en-US-JennyNeural"
_DEFAULT_LANGUAGE = "en-US"
_DEFAULT_OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="en-US-JennyNeural",
        name="Jenny (en-US, Female)",
        capabilities=["generation.audio.text-to-speech"],
        context_window=10_000,  # characters (Azure truncates at 10 min audio)
    ),
    ModelInfo(
        id="en-US-AndrewNeural",
        name="Andrew (en-US, Male)",
        capabilities=["generation.audio.text-to-speech"],
        context_window=10_000,
    ),
]


@dataclass
class AzureSpeechProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped Azure Speech TTS provider.

    Extends BaseProviderConfig with Azure-specific settings for the
    Cognitive Services Speech REST API.

    Attributes:
        region: Azure region for the Speech resource. Defaults to
            ``"eastus"``. Used to construct the endpoint URL.
        voice: Default voice short name. Defaults to
            ``"en-US-JennyNeural"``.
        language: SSML language attribute. Defaults to ``"en-US"``.
        output_format: Audio output format. Defaults to
            ``"audio-24khz-48kbitrate-mono-mp3"``.
        base_url: Auto-computed from region. Override only if using a
            custom endpoint.
        models: Model catalogue. Defaults to common English voices.
    """

    region: str = _DEFAULT_REGION
    voice: str = _DEFAULT_VOICE
    language: str = _DEFAULT_LANGUAGE
    output_format: str = _DEFAULT_OUTPUT_FORMAT
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["generation.audio.text-to-speech"]
    )

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = (
                f"https://{self.region}.tts.speech.microsoft.com"
            )


class AzureSpeechProvider(BaseProvider):
    """Pre-shipped provider connector for the Azure Speech TTS API.

    Azure Cognitive Services Speech uses a completely different API
    format than OpenAI, so this connector overrides all four protected
    hook methods on BaseProvider:

    - ``_get_completion_endpoint()`` -- returns the region-specific
      ``cognitiveservices/v1`` URL
    - ``_build_headers()`` -- uses ``Ocp-Apim-Subscription-Key`` for
      authentication and sets SSML content type
    - ``_build_request_payload()`` -- translates CompletionRequest
      into an SSML XML document
    - ``_parse_response()`` -- handles JSON error responses

    The connector bridges TTS into the chat completion interface:
    the text content of the first message is used as the speech text,
    and the model ID selects the Azure neural voice.

    Connector ID: ``azure.tts.v1``

    Usage::

        provider = AzureSpeechProvider(AzureSpeechProviderConfig(
            api_key="your-subscription-key",
            region="eastus",
            voice="en-US-JennyNeural",
        ))
        models = provider.list_models()
    """

    CONNECTOR_ID: str = "azure.tts.v1"

    def __init__(self, config: AzureSpeechProviderConfig | None = None) -> None:
        if config is None:
            config = AzureSpeechProviderConfig()
        super().__init__(config)
        self._azure_config = config

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the Azure Speech TTS endpoint.

        The endpoint is region-specific:
        ``https://{region}.tts.speech.microsoft.com/cognitiveservices/v1``
        """
        base = self._config.base_url.rstrip("/")
        return f"{base}/cognitiveservices/v1"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for the Azure Speech TTS API.

        Azure Speech requires:
        - ``Ocp-Apim-Subscription-Key`` for authentication
        - ``Content-Type: application/ssml+xml`` for the SSML body
        - ``X-Microsoft-OutputFormat`` for the desired audio format
        - ``User-Agent`` (required by Azure)
        """
        headers: dict[str, str] = {
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": self._azure_config.output_format,
            "User-Agent": "ModelMesh/1.0",
        }
        if self._config.api_key:
            headers["Ocp-Apim-Subscription-Key"] = self._config.api_key
        return headers

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a CompletionRequest to SSML XML.

        Extracts the text content from the first message, determines
        the voice from the model ID (or uses the configured default),
        and wraps everything in a valid SSML document.

        The SSML body is stored in the returned dict under the
        ``__ssml_body`` key so ``_http_post_ssml`` can extract it.
        """
        # Extract text from the first message content
        text = ""
        for msg in request.messages:
            content = (
                msg.get("content", "")
                if isinstance(msg, dict)
                else getattr(msg, "content", "")
            )
            if content:
                text = content
                break

        # Use model as voice name if it looks like an Azure voice;
        # otherwise fall back to configured default
        voice = request.model if request.model else self._azure_config.voice
        language = self._azure_config.language

        # Build SSML document
        ssml = (
            f"<speak version='1.0' xml:lang='{xml_escape(language)}'>"
            f"<voice xml:lang='{xml_escape(language)}' "
            f"name='{xml_escape(voice)}'>"
            f"{xml_escape(text)}"
            f"</voice></speak>"
        )

        return {"__ssml_body": ssml, "__text": text}

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Wrap error responses in a CompletionResponse.

        Since Azure Speech returns binary audio on success, this
        method is only called when the response is JSON (i.e., an
        error).
        """
        error_msg = data.get("error", {})
        if isinstance(error_msg, dict):
            error_msg = error_msg.get("message", str(data))
        else:
            error_msg = str(error_msg)

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

    def _http_post_ssml(
        self, url: str, ssml_body: str, headers: dict[str, str]
    ) -> bytes:
        """Send a synchronous HTTP POST with an SSML body and return raw audio.

        Unlike ``_http_post``, this method sends an SSML XML string
        (not JSON) and returns the raw response bytes (audio data).
        """
        body = ssml_body.encode("utf-8")
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
            f"Sending Azure TTS request for voice '{request.model}'",
            model=request.model,
        )

        payload = self._build_request_payload(request)
        headers = self._build_headers()
        endpoint = self._get_completion_endpoint()
        ssml_body = payload["__ssml_body"]
        start_time = _time.monotonic()

        last_error: Optional[Exception] = None
        for attempt in range(self._config.max_retries + 1):
            try:
                audio_bytes = await asyncio.to_thread(
                    self._http_post_ssml, endpoint, ssml_body, headers
                )

                # Calculate audio size for the response description
                audio_size_kb = len(audio_bytes) / 1024
                output_format = self._azure_config.output_format
                char_count = len(payload.get("__text", ""))

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
                    f"Azure TTS succeeded for voice '{request.model}'",
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
                        f"Non-retryable error for voice "
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
                    f"Retryable error for voice '{request.model}' "
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
