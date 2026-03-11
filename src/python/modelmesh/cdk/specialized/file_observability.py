"""File-based observability for the CDK.

Extends BaseObservability to write all output (events, logs, stats, traces)
to a file as JSON-Lines format. Each line is a self-contained JSON object
with a "type" field indicating the record type.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from modelmesh.cdk.base_observability import (
    BaseObservability,
    BaseObservabilityConfig,
)
from modelmesh.interfaces.observability import TraceEntry

__all__ = [
    "FileObservabilityConfig",
    "FileObservability",
]


@dataclass
class FileObservabilityConfig(BaseObservabilityConfig):
    """Configuration for file-based observability output.

    Attributes:
        file_path: Path to the log file. Defaults to "modelmesh.log".
        append: Whether to append to existing file. Defaults to True.
        flush_each_line: Whether to flush after every write. Defaults to True.
        max_file_size_bytes: Max file size before rotation (0 = no limit).
            Defaults to 0.
    """

    file_path: str = "modelmesh.log"
    append: bool = True
    flush_each_line: bool = True
    max_file_size_bytes: int = 0


class FileObservability(BaseObservability):
    """Observability connector that writes JSON-Lines to a file.

    All output (events, request/response logs, aggregate statistics,
    and traces) is written as one-JSON-object-per-line. The file can be
    consumed by log aggregation tools or parsed for analysis.

    Usage::

        obs = FileObservability(FileObservabilityConfig(
            file_path="/var/log/modelmesh.log",
            log_level="summary",
        ))
    """

    def __init__(self, config: FileObservabilityConfig) -> None:
        super().__init__(config)
        self._file_config = config
        self._file = None
        self._open_file()

    def _open_file(self) -> None:
        """Open (or re-open) the log file."""
        mode = "a" if self._file_config.append else "w"
        # Ensure parent directory exists
        parent = os.path.dirname(self._file_config.file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._file = open(self._file_config.file_path, mode, encoding="utf-8")

    def _write(self, line: str) -> None:
        """Write a formatted JSON line to the log file."""
        if self._file is None or self._file.closed:
            self._open_file()

        # Check rotation
        if self._file_config.max_file_size_bytes > 0:
            try:
                pos = self._file.tell()
                if pos >= self._file_config.max_file_size_bytes:
                    self._rotate_file()
            except (OSError, IOError):
                pass

        self._file.write(line + "\n")
        if self._file_config.flush_each_line:
            self._file.flush()

    def _rotate_file(self) -> None:
        """Rotate the log file by renaming current to .1 and opening new."""
        if self._file and not self._file.closed:
            self._file.close()

        rotated = self._file_config.file_path + ".1"
        try:
            if os.path.exists(rotated):
                os.remove(rotated)
            os.rename(self._file_config.file_path, rotated)
        except OSError:
            pass

        self._open_file()

    def trace(self, entry: TraceEntry) -> None:
        """Write a trace entry as a JSON line to the log file."""
        line = json.dumps(
            {
                "type": "trace",
                "severity": entry.severity.value,
                "timestamp": entry.timestamp.isoformat(),
                "component": entry.component,
                "message": entry.message,
                "metadata": entry.metadata,
                "error": entry.error,
            },
            default=str,
        )
        if self._config.redact_secrets:
            line = self._redact(line)
        self._write(line)

    def close(self) -> None:
        """Close the log file."""
        if self._file and not self._file.closed:
            self._file.close()

    def __del__(self) -> None:
        self.close()
