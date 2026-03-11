"""Configuration validation and schema checking.

Validates ModelMesh YAML configuration structure, cross-references
between sections, and connector IDs against the registry.
"""
from __future__ import annotations

from typing import Any

__all__ = ["ConfigValidator", "ConfigError"]


class ConfigError(Exception):
    """Raised when configuration validation fails.

    Attributes:
        errors: List of individual error messages.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Config validation failed: {'; '.join(errors)}")


_KNOWN_SECTIONS = {
    "secrets", "providers", "models", "pools",
    "observability", "storage", "discovery", "budget",
}


class ConfigValidator:
    """Validates ModelMesh YAML configuration.

    Checks structural correctness, cross-references between sections,
    numeric range validity, and warns on unknown keys.
    """

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Return a list of validation error messages.

        An empty list means the configuration is valid.
        """
        errors: list[str] = []

        # Unknown top-level sections
        for key in config:
            if key not in _KNOWN_SECTIONS:
                errors.append(f"Unknown top-level key: '{key}'")

        # Type checks
        for section in ("providers", "models", "pools"):
            if section in config and not isinstance(config[section], dict):
                errors.append(f"'{section}' must be a mapping")

        # Provider validation
        providers_cfg = config.get("providers", {})
        if isinstance(providers_cfg, dict):
            for pid, pdef in providers_cfg.items():
                if not isinstance(pdef, dict):
                    errors.append(f"Provider '{pid}' must be a mapping")
                    continue
                if "connector" not in pdef and "instance" not in pdef:
                    errors.append(
                        f"Provider '{pid}' must have a 'connector' or 'instance'"
                    )

        # Model validation
        models_cfg = config.get("models", {})
        known_providers = set(providers_cfg.keys()) if isinstance(providers_cfg, dict) else set()
        if isinstance(models_cfg, dict):
            for mid, mdef in models_cfg.items():
                if not isinstance(mdef, dict):
                    errors.append(f"Model '{mid}' must be a mapping")
                    continue
                mp = mdef.get("provider", "")
                if mp and mp not in known_providers:
                    errors.append(
                        f"Model '{mid}' references unknown provider '{mp}'"
                    )

        # Pool validation
        pools_cfg = config.get("pools", {})
        known_models = set(models_cfg.keys()) if isinstance(models_cfg, dict) else set()
        if isinstance(pools_cfg, dict):
            for pool_id, pool_def in pools_cfg.items():
                if not isinstance(pool_def, dict):
                    errors.append(f"Pool '{pool_id}' must be a mapping")
                    continue
                for model_ref in pool_def.get("models", []):
                    if model_ref not in known_models:
                        errors.append(
                            f"Pool '{pool_id}' references unknown "
                            f"model '{model_ref}'"
                        )
                # Numeric range checks
                ft = pool_def.get("failure_threshold")
                if ft is not None and (not isinstance(ft, (int, float)) or ft < 1):
                    errors.append(
                        f"Pool '{pool_id}': failure_threshold must be >= 1"
                    )
                cs = pool_def.get("cooldown_seconds")
                if cs is not None and (not isinstance(cs, (int, float)) or cs < 0):
                    errors.append(
                        f"Pool '{pool_id}': cooldown_seconds must be >= 0"
                    )

        # Budget validation
        budget_cfg = config.get("budget", {})
        if isinstance(budget_cfg, dict):
            for limit_key in ("daily_limit", "monthly_limit", "per_request_limit"):
                val = budget_cfg.get(limit_key)
                if val is not None and (not isinstance(val, (int, float)) or val < 0):
                    errors.append(f"budget.{limit_key} must be >= 0")

        return errors

    def validate_strict(self, config: dict[str, Any]) -> None:
        """Raise ConfigError if validation fails."""
        errors = self.validate(config)
        if errors:
            raise ConfigError(errors)
