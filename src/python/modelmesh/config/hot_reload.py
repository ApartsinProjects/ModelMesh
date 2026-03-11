"""Configuration hot-reload support.

Watches a YAML configuration file for changes and triggers a
re-initialization of the ModelMesh instance without dropping in-flight
requests. Uses file modification time polling (no OS-specific watchers)
for maximum portability.

Usage::

    from modelmesh.config.hot_reload import ConfigWatcher

    watcher = ConfigWatcher("modelmesh.yaml", mesh_instance)
    watcher.start()
    # ... mesh handles requests ...
    watcher.stop()
"""
from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from modelmesh.config.mesh_config import MeshConfig
    from modelmesh.core.mesh import ModelMesh

logger = logging.getLogger("modelmesh.config.hot_reload")

__all__ = ["ConfigWatcher", "reconfigure"]


def reconfigure(mesh: ModelMesh, new_config: MeshConfig) -> list[str]:
    """Apply a new configuration to a running ModelMesh instance.

    Validates the new config, shuts down the old mesh internals, and
    re-initializes with the updated configuration. Returns validation
    errors (empty list on success).

    This is a *graceful* operation: the mesh remains functional during
    the swap because ``initialize()`` replaces internal structures
    atomically (from the caller's perspective).

    Args:
        mesh: The running ModelMesh instance.
        new_config: The new configuration to apply.

    Returns:
        List of validation error strings. Empty means success.
    """
    from modelmesh.config.validation import ConfigValidator

    validator = ConfigValidator()
    errors = validator.validate(new_config.raw)
    if errors:
        logger.warning(
            "Hot-reload rejected: %d validation error(s)", len(errors)
        )
        return errors

    logger.info("Hot-reloading configuration...")
    try:
        # Shut down existing providers and pools
        mesh.shutdown()
        # Re-initialize with the new config
        mesh.initialize(new_config)
        logger.info("Hot-reload complete")
    except Exception as exc:
        logger.error("Hot-reload failed: %s", exc)
        return [f"Hot-reload initialization error: {exc}"]

    return []


class ConfigWatcher:
    """Polls a YAML file for changes and triggers hot-reload.

    Attributes:
        path: Absolute path to the configuration file.
        interval: Poll interval in seconds (default 5).
        on_reload: Optional callback invoked after successful reload,
            receives the list of validation errors (empty = success).
    """

    def __init__(
        self,
        path: str,
        mesh: ModelMesh,
        interval: float = 5.0,
        on_reload: Optional[Callable[[list[str]], None]] = None,
    ) -> None:
        self.path = os.path.abspath(path)
        self._mesh = mesh
        self.interval = interval
        self.on_reload = on_reload
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_mtime: float = 0.0

    def start(self) -> None:
        """Start the background watcher thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        try:
            self._last_mtime = os.path.getmtime(self.path)
        except OSError:
            self._last_mtime = 0.0

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, name="config-watcher", daemon=True
        )
        self._thread.start()
        logger.info("Config watcher started: %s (interval=%.1fs)", self.path, self.interval)

    def stop(self) -> None:
        """Stop the background watcher thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval * 2)
            self._thread = None
        logger.info("Config watcher stopped")

    @property
    def is_running(self) -> bool:
        """Whether the watcher thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while not self._stop_event.is_set():
            try:
                mtime = os.path.getmtime(self.path)
                if mtime > self._last_mtime:
                    self._last_mtime = mtime
                    logger.info("Config file changed, reloading...")
                    self._do_reload()
            except OSError:
                pass  # File temporarily unavailable
            except Exception:
                logger.debug("Watcher poll error", exc_info=True)

            self._stop_event.wait(self.interval)

    def _do_reload(self) -> None:
        """Load the file and apply the new configuration."""
        from modelmesh.config.mesh_config import MeshConfig

        try:
            new_config = MeshConfig.from_yaml(self.path)
        except Exception as exc:
            errors = [f"Failed to parse config file: {exc}"]
            logger.error(errors[0])
            if self.on_reload:
                self.on_reload(errors)
            return

        errors = reconfigure(self._mesh, new_config)
        if self.on_reload:
            self.on_reload(errors)
