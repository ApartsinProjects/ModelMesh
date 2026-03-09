"""HTTP API provider for the CDK.

Extends BaseProvider for REST APIs with custom request/response formats.
Subclasses must override ``_translate_request()`` and
``_translate_response()`` to convert between the ModelMesh canonical
format and the target API's schema.
"""
from __future__ import annotations

from dataclasses import dataclass

from modelmesh.cdk.base_provider import BaseProvider, BaseProviderConfig
from modelmesh.interfaces.provider import (
    CompletionRequest,
    CompletionResponse,
)

__all__ = [
    "HttpApiProviderConfig",
    "HttpApiProvider",
]


@dataclass
class HttpApiProviderConfig(BaseProviderConfig):
    """Configuration for an HTTP API provider.

    Extends BaseProviderConfig with HTTP method and content type
    settings for non-OpenAI REST APIs.
    """

    method: str = "POST"
    content_type: str = "application/json"


class HttpApiProvider(BaseProvider):
    """Provider for REST APIs with custom request/response formats.

    This specialized provider is designed for HTTP-based AI services
    that do not follow the OpenAI chat completions spec. Subclasses
    must implement two translation methods:

    - ``_translate_request(request)``: convert a ``CompletionRequest``
      into the API's native payload format.
    - ``_translate_response(data)``: convert the API's raw response
      into a ``CompletionResponse``.

    The base class ``complete()`` method handles retries, error
    classification, and usage reporting automatically. Subclasses
    only need to provide the two translation methods.

    Usage::

        class MyApiProvider(HttpApiProvider):
            def _translate_request(self, request):
                return {"prompt": request.messages[-1]["content"]}

            def _translate_response(self, data):
                return CompletionResponse(
                    id=data["id"], model=data["model"],
                    choices=data["results"],
                    usage=TokenUsage(total_tokens=data["tokens"]),
                )
    """

    def __init__(self, config: HttpApiProviderConfig) -> None:
        super().__init__(config)
        self._http_config = config

    def _translate_request(self, request: CompletionRequest) -> dict:
        """Translate a CompletionRequest into the target API's payload.

        Subclasses must override this method.

        Args:
            request: The canonical completion request.

        Returns:
            A dictionary suitable for JSON serialization and sending
            to the target API.

        Raises:
            NotImplementedError: If not overridden by a subclass.
        """
        raise NotImplementedError(
            "HttpApiProvider subclasses must override _translate_request()"
        )

    def _translate_response(self, data: dict) -> CompletionResponse:
        """Translate the target API's raw response into a CompletionResponse.

        Subclasses must override this method.

        Args:
            data: The parsed JSON response from the target API.

        Returns:
            A CompletionResponse instance.

        Raises:
            NotImplementedError: If not overridden by a subclass.
        """
        raise NotImplementedError(
            "HttpApiProvider subclasses must override _translate_response()"
        )

    def _build_request_payload(self, request: CompletionRequest) -> dict:
        """Delegate to ``_translate_request`` for custom APIs."""
        return self._translate_request(request)

    def _parse_response(self, data: dict) -> CompletionResponse:
        """Delegate to ``_translate_response`` for custom APIs."""
        return self._translate_response(data)

    def _build_headers(self) -> dict[str, str]:
        """Build headers using the configured content type."""
        headers = super()._build_headers()
        headers["Content-Type"] = self._http_config.content_type
        return headers
