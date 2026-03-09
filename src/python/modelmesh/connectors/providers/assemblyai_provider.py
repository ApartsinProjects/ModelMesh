"""Pre-shipped AssemblyAI speech-to-text provider connector.

Wraps AssemblyAI's transcription API as a ModelMesh provider so
speech-to-text capabilities can participate in capability pools.
Accepts an audio file URL in the last message's content, submits it
for transcription, polls until completion, and returns the transcript
as a CompletionResponse.

Connector ID: ``assemblyai.stt.v1``
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    ChatMessage,
    CompletionChoice,
    CompletionRequest,
    CompletionResponse,
    ModelInfo,
    ModelPricing,
    TokenUsage,
)

__all__ = [
    "AssemblyAIProviderConfig",
    "AssemblyAIProvider",
]

# -- Default model catalogue -------------------------------------------------

_DEFAULT_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="assemblyai-best",
        name="AssemblyAI Best",
        capabilities=["understanding.audio.speech-to-text"],
        features={"speaker_labels": True, "punctuation": True},
        context_window=0,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.015),
    ),
    ModelInfo(
        id="assemblyai-nano",
        name="AssemblyAI Nano",
        capabilities=["understanding.audio.speech-to-text"],
        features={"speaker_labels": False, "punctuation": True},
        context_window=0,
        max_output_tokens=0,
        pricing=ModelPricing(per_request=0.005),
    ),
]


@dataclass
class AssemblyAIProviderConfig(BaseProviderConfig):
    """Configuration for the pre-shipped AssemblyAI provider.

    Extends BaseProviderConfig with settings specific to the
    AssemblyAI transcription API.

    Attributes:
        base_url: AssemblyAI API base URL.  Defaults to
            ``"https://api.assemblyai.com"``.
        poll_interval: Seconds between polling attempts when waiting
            for transcription completion.  Defaults to ``3.0``.
        max_poll_attempts: Maximum number of polling attempts before
            timing out.  Defaults to ``120`` (6 minutes at 3s intervals).
        models: Model catalogue.  Defaults to the built-in list of
            AssemblyAI transcription models.
    """

    base_url: str = "https://api.assemblyai.com"
    poll_interval: float = 3.0
    max_poll_attempts: int = 120
    models: list[ModelInfo] = field(default_factory=lambda: list(_DEFAULT_MODELS))
    capabilities: list[str] = field(
        default_factory=lambda: ["understanding.audio.speech-to-text"]
    )


class AssemblyAIProvider(BaseProvider):
    """Pre-shipped provider connector for AssemblyAI's transcription API.

    AssemblyAI provides speech-to-text transcription with high
    accuracy.  This connector wraps the asynchronous transcription
    workflow (submit, poll, retrieve) behind the synchronous chat
    completions interface.

    The audio file URL is extracted from ``messages[-1].content``.
    The transcription is submitted, polled until completion, and the
    transcript text is returned as a CompletionResponse.

    Connector ID: ``assemblyai.stt.v1``

    Usage::

        provider = AssemblyAIProvider(AssemblyAIProviderConfig(
            api_key="...",
        ))
        response = await provider.complete(CompletionRequest(
            model="assemblyai-best",
            messages=[{"role": "user", "content": "https://example.com/audio.mp3"}],
        ))
    """

    CONNECTOR_ID: str = "assemblyai.stt.v1"

    def __init__(self, config: AssemblyAIProviderConfig | None = None) -> None:
        if config is None:
            config = AssemblyAIProviderConfig()
        super().__init__(config)
        self._assemblyai_config = config

    # -- Hook overrides -------------------------------------------------------

    def _get_completion_endpoint(self) -> str:
        """Return the AssemblyAI transcript endpoint."""
        base = self._config.base_url.rstrip("/")
        return f"{base}/v2/transcript"

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with AssemblyAI-specific authentication.

        AssemblyAI uses ``Authorization: {api_key}`` without the
        ``Bearer`` prefix.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = self._config.api_key
        return headers

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Translate a chat completion request to AssemblyAI's transcript format.

        Extracts the audio URL from the last message's content and
        sets the speech model based on the requested model ID.
        """
        audio_url = ""
        if request.messages:
            last_msg = request.messages[-1]
            if isinstance(last_msg, dict):
                audio_url = last_msg.get("content", "")
            else:
                audio_url = getattr(last_msg, "content", "")

        payload: dict = {"audio_url": audio_url.strip()}

        # Map model IDs to AssemblyAI speech_model values
        if request.model == "assemblyai-nano":
            payload["speech_model"] = "nano"
        else:
            # "assemblyai-best" or any other defaults to "best"
            payload["speech_model"] = "best"

        return payload

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Translate an AssemblyAI transcript response to CompletionResponse.

        Extracts the transcript text, confidence score, and audio
        duration from the completed transcription result.
        """
        status = data.get("status", "")
        transcript_text = data.get("text", "")
        error_msg = data.get("error")

        if status == "error" and error_msg:
            content_text = f"Transcription error: {error_msg}"
        elif not transcript_text:
            content_text = "No transcript generated."
        else:
            parts: list[str] = []
            parts.append(transcript_text)

            # Include metadata
            confidence = data.get("confidence")
            audio_duration = data.get("audio_duration")
            if confidence is not None:
                parts.append(f"\n[Confidence: {confidence:.2%}]")
            if audio_duration is not None:
                parts.append(f"[Duration: {audio_duration:.1f}s]")

            content_text = "\n".join(parts)

        # Estimate token usage from audio duration or text length
        audio_duration = data.get("audio_duration", 0) or 0
        prompt_tokens = max(1, int(audio_duration))
        completion_tokens = max(1, len(content_text) // 4)

        choice = CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=content_text),
            finish_reason="stop",
        )

        return CompletionResponse(
            id=data.get("id", f"assemblyai-{uuid.uuid4().hex[:12]}"),
            model=data.get("speech_model", "assemblyai-best"),
            choices=[choice],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    # -- Override complete() for two-step transcription workflow ---------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Submit audio for transcription and poll until complete.

        This overrides the standard ``complete()`` to implement
        AssemblyAI's asynchronous two-step workflow:

        1. POST to ``/v2/transcript`` to submit the transcription job
        2. GET ``/v2/transcript/{id}`` repeatedly until the status is
           ``completed`` or ``error``

        The polling uses :func:`asyncio.sleep` between attempts so
        other async tasks can make progress.
        """
        component = f"provider.{request.model}"
        self._trace(
            "DEBUG",
            component,
            f"Submitting transcription for model '{request.model}'",
            model=request.model,
        )

        payload = self._build_request_payload(request)
        headers = self._build_headers()
        endpoint = self._get_completion_endpoint()

        # Step 1: Submit the transcription job
        submit_data = await asyncio.to_thread(
            self._http_post, endpoint, payload, headers
        )
        transcript_id = submit_data.get("id")

        if not transcript_id:
            error_msg = submit_data.get("error", "No transcript ID returned")
            self._trace(
                "ERROR",
                component,
                f"Transcription submission failed: {error_msg}",
                error=error_msg,
                model=request.model,
            )
            raise RuntimeError(f"AssemblyAI submission failed: {error_msg}")

        self._trace(
            "DEBUG",
            component,
            f"Transcription submitted, polling id={transcript_id}",
            model=request.model,
            transcript_id=transcript_id,
        )

        # Step 2: Poll until completion
        poll_url = f"{endpoint}/{transcript_id}"
        for attempt in range(self._assemblyai_config.max_poll_attempts):
            poll_data = await asyncio.to_thread(
                self._http_get_json, poll_url, headers
            )
            status = poll_data.get("status", "")

            if status == "completed":
                self._trace(
                    "INFO",
                    component,
                    f"Transcription completed for id={transcript_id}",
                    model=request.model,
                    transcript_id=transcript_id,
                    attempts=attempt + 1,
                )
                result = self._parse_response(poll_data)
                self.report_usage(request.model, result.usage)
                return result

            if status == "error":
                error_msg = poll_data.get("error", "Unknown transcription error")
                self._trace(
                    "ERROR",
                    component,
                    f"Transcription failed for id={transcript_id}: {error_msg}",
                    error=error_msg,
                    model=request.model,
                    transcript_id=transcript_id,
                )
                result = self._parse_response(poll_data)
                self.report_usage(request.model, result.usage)
                return result

            # Still processing, wait before next poll
            await asyncio.sleep(self._assemblyai_config.poll_interval)

        # Timed out
        self._trace(
            "ERROR",
            component,
            f"Transcription timed out for id={transcript_id} "
            f"after {self._assemblyai_config.max_poll_attempts} attempts",
            model=request.model,
            transcript_id=transcript_id,
        )
        raise TimeoutError(
            f"AssemblyAI transcription timed out after "
            f"{self._assemblyai_config.max_poll_attempts} poll attempts"
        )

    def _http_get_json(self, url: str, headers: dict[str, str]) -> dict:
        """Send a synchronous HTTP GET and return parsed JSON.

        Called from async code via :func:`asyncio.to_thread`.
        """
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
