"""Shared async HTTP client mixin with retries and authorization.

Provides an ``HttpClientMixin`` that can be composed into any class via
multiple inheritance.  The mixin manages HTTP GET and POST requests with
automatic retry on transient failures, authorization header injection,
and SSE streaming support.

HTTP transport uses :mod:`urllib.request` from the standard library so
the package has zero external dependencies.  Async methods delegate
blocking I/O to a thread via :func:`asyncio.to_thread`.

Typical usage::

    class MyService(HttpClientMixin):
        def __init__(self, base_url: str, token: str):
            self._http_auth_token = token
            self._init_http_client(base_url, timeout=30.0)

        async def fetch_models(self) -> dict:
            return await self._http_get("/v1/models")

        async def complete(self, payload: dict) -> dict:
            return await self._http_post("/v1/chat/completions", json=payload)

        async def close(self) -> None:
            await self._close_http_client()
"""
from __future__ import annotations

import asyncio
import json
import random
import urllib.error
import urllib.request
from typing import Any, AsyncIterator

__all__ = ["HttpClientMixin"]


class HttpClientMixin:
    """Shared async HTTP client with retries and authorization.

    Mix into any class via multiple inheritance.  Call
    :meth:`_init_http_client` during initialization to configure the
    base URL, timeout, retry policy, and default headers.  Then use
    :meth:`_http_get`, :meth:`_http_post`, and :meth:`_http_stream`
    to issue requests.

    The implementation uses :mod:`urllib.request` from the standard
    library.  Async methods execute blocking I/O in a thread via
    :func:`asyncio.to_thread`.

    Class-level attributes can be set before calling
    ``_init_http_client``:

    Attributes:
        _http_auth_token: Bearer token injected into the
            ``Authorization`` header of every request.  Set to
            ``None`` to skip authorization.
    """

    _http_base_url: str = ""
    _http_timeout: float = 30.0
    _http_max_retries: int = 3
    _http_auth_token: str | None = None
    _http_default_headers: dict[str, str] = {}
    _http_initialized: bool = False

    RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503})

    def _init_http_client(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Create the underlying HTTP client configuration.

        Args:
            base_url: Base URL for all requests
                (e.g. ``"https://api.openai.com/v1"``).
            timeout: Request timeout in seconds.  Defaults to ``30.0``.
            max_retries: Maximum retry attempts for transient failures.
                Defaults to ``3``.
            headers: Additional default headers merged into every
                request.
        """
        self._http_base_url = base_url.rstrip("/")
        self._http_timeout = timeout
        self._http_max_retries = max_retries

        default_headers: dict[str, str] = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        if self._http_auth_token:
            default_headers["Authorization"] = f"Bearer {self._http_auth_token}"

        self._http_default_headers = default_headers
        self._http_initialized = True

    async def _http_get(self, path: str, **kwargs: Any) -> Any:
        """Issue a GET request and return the parsed JSON body.

        Args:
            path: URL path appended to the base URL.
            **kwargs: Additional keyword arguments (currently unused,
                reserved for future extension).

        Returns:
            Parsed JSON response body.

        Raises:
            urllib.error.HTTPError: After retries are exhausted.
            AssertionError: If ``_init_http_client`` was not called.
        """
        return await self._request_with_retry("GET", path, **kwargs)

    async def _http_post(
        self, path: str, json_body: Any = None, **kwargs: Any
    ) -> Any:
        """Issue a POST request with a JSON body and return the response.

        Args:
            path: URL path appended to the base URL.
            json_body: Request body serialized as JSON.
            **kwargs: Additional keyword arguments (currently unused).

        Returns:
            Parsed JSON response body.

        Raises:
            urllib.error.HTTPError: After retries are exhausted.
            AssertionError: If ``_init_http_client`` was not called.
        """
        return await self._request_with_retry(
            "POST", path, json_body=json_body, **kwargs
        )

    async def _http_stream(
        self, path: str, json_body: Any = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        """Issue a streaming POST request and yield SSE data lines.

        Sends a POST request and reads the response as a
        server-sent event stream.  Each ``data: ...`` line is
        yielded with the ``data: `` prefix stripped.

        Args:
            path: URL path appended to the base URL.
            json_body: Request body serialized as JSON.
            **kwargs: Additional keyword arguments (currently unused).

        Yields:
            Individual data payloads from the SSE stream (without
            the ``data: `` prefix).
        """
        assert self._http_initialized, "Call _init_http_client first"
        url = f"{self._http_base_url}{path}"
        lines = await asyncio.to_thread(
            self._sync_post_stream, url, json_body
        )
        for line in lines:
            if line.startswith("data: "):
                yield line[6:]

    async def _close_http_client(self) -> None:
        """Close the HTTP client and release resources.

        For the stdlib-based implementation this is a no-op, but
        subclasses that swap in a connection-pooled client can
        override this method.
        """
        self._http_initialized = False

    async def _request_with_retry(
        self, method: str, path: str, json_body: Any = None, **kwargs: Any
    ) -> Any:
        """Execute a request with exponential backoff on transient errors.

        Args:
            method: HTTP method (``"GET"``, ``"POST"``, etc.).
            path: URL path appended to the base URL.
            json_body: Request body for POST requests.
            **kwargs: Reserved for future extension.

        Returns:
            Parsed JSON response body.

        Raises:
            urllib.error.HTTPError: When retries are exhausted or
                the error is non-retryable.
        """
        assert self._http_initialized, "Call _init_http_client first"
        url = f"{self._http_base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self._http_max_retries + 1):
            try:
                result = await asyncio.to_thread(
                    self._sync_request, method, url, json_body
                )
                return result
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in self.RETRYABLE_STATUS_CODES:
                    raise
                if attempt < self._http_max_retries:
                    delay = (2 ** attempt) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
            except Exception as exc:
                last_error = exc
                if attempt < self._http_max_retries:
                    delay = (2 ** attempt) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_error  # type: ignore[misc]

    # ── Synchronous Transport (stdlib) ────────────────────────────

    def _sync_request(
        self, method: str, url: str, json_body: Any = None
    ) -> Any:
        """Execute a synchronous HTTP request and return parsed JSON.

        Called from async code via :func:`asyncio.to_thread`.

        Args:
            method: HTTP method.
            url: Full URL.
            json_body: Optional JSON body for POST requests.

        Returns:
            Parsed JSON response body.
        """
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers=dict(self._http_default_headers),
            method=method,
        )

        with urllib.request.urlopen(req, timeout=self._http_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _sync_post_stream(
        self, url: str, json_body: Any = None
    ) -> list[str]:
        """Execute a synchronous streaming POST and return raw lines.

        Called from async code via :func:`asyncio.to_thread`.

        Args:
            url: Full URL.
            json_body: Optional JSON body.

        Returns:
            A list of raw response lines.
        """
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers=dict(self._http_default_headers),
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self._http_timeout) as resp:
            raw = resp.read().decode("utf-8")
        return raw.splitlines()
