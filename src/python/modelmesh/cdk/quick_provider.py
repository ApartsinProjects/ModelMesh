"""Quick provider -- minimal setup with auto-discovery.

Re-exports :class:`QuickProvider` and :class:`QuickProviderConfig` from
the specialized sub-package so they are importable directly from
``modelmesh.cdk``.  Also provides a convenience factory function
``create_quick_provider`` that constructs a provider from positional
arguments without importing the config class.
"""
from __future__ import annotations

from modelmesh.cdk.specialized.quick_provider import (
    QuickProvider,
    QuickProviderConfig,
)

__all__ = [
    "QuickProvider",
    "QuickProviderConfig",
    "create_quick_provider",
]


def create_quick_provider(
    base_url: str,
    api_key: str = "",
    **kwargs,
) -> QuickProvider:
    """Create a QuickProvider from positional arguments.

    This is a convenience factory that avoids importing
    ``QuickProviderConfig`` directly.  Any keyword arguments are
    forwarded to the config dataclass.

    Args:
        base_url: The API base URL (e.g. ``https://api.openai.com``).
        api_key: The API key for authentication.
        **kwargs: Additional keyword arguments forwarded to
            :class:`QuickProviderConfig`.

    Returns:
        A configured :class:`QuickProvider` instance.

    Example::

        provider = create_quick_provider(
            "https://api.openai.com",
            api_key="sk-...",
        )
    """
    config = QuickProviderConfig(base_url=base_url, api_key=api_key, **kwargs)
    return QuickProvider(config)
