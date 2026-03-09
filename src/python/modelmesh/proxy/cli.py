"""CLI entry point for the ModelMesh OpenAI-compatible proxy server.

Usage::

    python -m modelmesh.proxy --config modelmesh.yaml --port 8080 --host 0.0.0.0
    python -m modelmesh.proxy --token my-secret-token

All flags are optional; sensible defaults are applied when omitted.
"""
from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and start the proxy server.

    Args:
        argv: Command-line arguments. Defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(
        prog="modelmesh.proxy",
        description="ModelMesh OpenAI-compatible HTTP proxy server",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=(
            "Path to a ModelMesh YAML configuration file. "
            "If omitted, auto-detection from environment variables is used."
        ),
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Listen port (default: 8080)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Bearer token for authentication. When set, all requests must include Authorization: Bearer <token>.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args(argv)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Determine config source
    if args.config is not None:
        config = args.config
    else:
        # Auto-detect: build a minimal config from environment variables
        # by using the modelmesh.create() path internally.
        config = _build_auto_config()

    # Import here to avoid circular imports and allow the CLI module
    # to be parsed without triggering heavy imports.
    from modelmesh.proxy.server import ProxyServer

    server = ProxyServer(
        config=config,
        host=args.host,
        port=args.port,
        token=args.token,
    )

    print(
        f"ModelMesh proxy starting on {args.host}:{args.port}",
        file=sys.stderr,
    )

    server.start(block=True)


def _build_auto_config() -> dict:
    """Build a minimal auto-detected configuration dict.

    Detects providers from environment variables and creates default
    pools for common capabilities.
    """
    try:
        from modelmesh.config.auto_detect import detect_providers
    except ImportError:
        # If auto_detect is unavailable, return an empty config.
        return {
            "providers": {},
            "models": {},
            "pools": {},
            "observability": {"connector": "modelmesh.null.v1"},
        }

    detected = detect_providers()
    if not detected:
        print(
            "Warning: No providers detected from environment variables. "
            "Set API key env vars (e.g. OPENAI_API_KEY) or use --config.",
            file=sys.stderr,
        )
        return {
            "providers": {},
            "models": {},
            "pools": {},
            "observability": {"connector": "modelmesh.null.v1"},
        }

    # Build a config using the same logic as modelmesh.create()
    from modelmesh import _build_auto_config as _build

    return _build(
        capabilities=["chat-completion"],
        pool=None,
        detected_providers=detected,
        model_filter=None,
        strategy="stick-until-failure",
    )


if __name__ == "__main__":
    main()
