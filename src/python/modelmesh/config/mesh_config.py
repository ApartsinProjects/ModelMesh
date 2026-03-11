"""MeshConfig — declarative configuration object.

Holds the raw configuration dictionary and provides convenience methods
for loading from YAML files and accessing configuration sections.
Configuration can be built programmatically, loaded from a YAML file,
or constructed by the convenience layer's auto-detection logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["MeshConfig"]


@dataclass
class MeshConfig:
    """Declarative configuration for ModelMesh.

    The ``raw`` dict mirrors the YAML configuration structure::

        {
            "secrets": {"store": "modelmesh.env.v1"},
            "providers": { ... },
            "models": { ... },
            "pools": { ... },
            "observability": { ... },
            "storage": { ... },
        }

    Full schema reference: ``docs/SystemConfiguration.md``.

    Attributes:
        raw: The raw configuration dictionary.
    """

    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> MeshConfig:
        """Load configuration from a YAML file.

        Args:
            path: Path to a YAML configuration file.

        Returns:
            A ``MeshConfig`` populated from the file contents.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
        """
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(raw=data if data is not None else {})

    @classmethod
    def from_file(cls, path: str) -> MeshConfig:
        """Alias for :meth:`from_yaml` for API compatibility."""
        return cls.from_yaml(path)

    @classmethod
    def from_dict(cls, data: dict) -> MeshConfig:
        """Create a MeshConfig from a Python dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            A ``MeshConfig`` populated from the dictionary.
        """
        return cls(raw=data)

    # -- Section accessors ---------------------------------------------------

    @property
    def providers(self) -> dict[str, Any]:
        """The ``providers`` configuration section."""
        return self.raw.get("providers", {})

    @property
    def models(self) -> dict[str, Any]:
        """The ``models`` configuration section."""
        return self.raw.get("models", {})

    @property
    def pools(self) -> dict[str, Any]:
        """The ``pools`` configuration section."""
        return self.raw.get("pools", {})

    @property
    def secrets(self) -> dict[str, Any]:
        """The ``secrets`` configuration section."""
        return self.raw.get("secrets", {})

    @property
    def observability(self) -> dict[str, Any]:
        """The ``observability`` configuration section."""
        return self.raw.get("observability", {})

    @property
    def storage(self) -> dict[str, Any]:
        """The ``storage`` configuration section."""
        return self.raw.get("storage", {})

    # -- Utility methods -----------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Access a top-level configuration key with a default.

        Args:
            key: Top-level key name.
            default: Value to return if key is absent.
        """
        return self.raw.get(key, default)

    def merge(self, overrides: dict[str, Any]) -> MeshConfig:
        """Create a new MeshConfig with overrides applied.

        Performs a shallow merge: top-level keys from *overrides*
        replace or extend the corresponding keys in this config.

        Args:
            overrides: Dictionary of overrides.

        Returns:
            A new ``MeshConfig`` with merged values.
        """
        merged = {**self.raw}
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return MeshConfig(raw=merged)

    def validate(self) -> list[str]:
        """Run basic validation on the configuration.

        Returns:
            A list of validation error messages. An empty list means
            the configuration is valid.
        """
        errors: list[str] = []

        # Providers section
        if "providers" in self.raw and not isinstance(self.raw["providers"], dict):
            errors.append("'providers' must be a dict")

        # Models section
        if "models" in self.raw and not isinstance(self.raw["models"], dict):
            errors.append("'models' must be a dict")

        # Pools section
        if "pools" in self.raw and not isinstance(self.raw["pools"], dict):
            errors.append("'pools' must be a dict")

        # Check that pool models reference known model IDs
        if "pools" in self.raw and "models" in self.raw:
            known_models = set(self.raw["models"].keys())
            for pool_id, pool_def in self.raw.get("pools", {}).items():
                for model_ref in pool_def.get("models", []):
                    if model_ref not in known_models:
                        errors.append(
                            f"Pool '{pool_id}' references unknown model "
                            f"'{model_ref}'"
                        )

        return errors
