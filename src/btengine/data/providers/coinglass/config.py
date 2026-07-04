"""CoinGlass configuration, sourced only from environment variables / .env.

No default ever contains a real credential. ``api_key`` has no default at
all: if it is not supplied via the ``COINGLASS_API_KEY`` environment
variable (or an explicit ``.env`` file), settings construction fails with a
structured :class:`~btengine.data.errors.ConfigurationError` rather than
silently starting up unauthenticated.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from btengine.data.errors import ConfigurationError


class CoinGlassSettings(BaseSettings):
    """Runtime configuration for the CoinGlass client, adapter, and cache."""

    model_config = SettingsConfigDict(
        env_prefix="COINGLASS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: SecretStr
    base_url: str = "https://open-api-v4.coinglass.com"
    timeout_seconds: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=5, ge=0)
    backoff_base_seconds: float = Field(default=0.5, gt=0)
    backoff_max_seconds: float = Field(default=30.0, gt=0)
    rate_limit_requests: int = Field(default=30, gt=0)
    rate_limit_period_seconds: float = Field(default=60.0, gt=0)

    @field_validator("api_key")
    @classmethod
    def _api_key_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("COINGLASS_API_KEY must not be blank")
        return value

    @field_validator("base_url")
    @classmethod
    def _base_url_must_be_https(cls, value: str) -> str:
        value = value.rstrip("/")
        if not value.startswith("https://"):
            raise ValueError("COINGLASS_BASE_URL must use https")
        return value


def load_coinglass_settings(**overrides: Any) -> CoinGlassSettings:
    """Build :class:`CoinGlassSettings`, converting missing/invalid config
    into a :class:`~btengine.data.errors.ConfigurationError` instead of
    letting a raw ``pydantic.ValidationError`` escape to the caller.
    """
    try:
        return CoinGlassSettings(**overrides)
    except ValidationError as exc:
        raise ConfigurationError(
            "Invalid or missing CoinGlass configuration. "
            "Set COINGLASS_API_KEY (and optional overrides) via environment "
            "variables or a .env file.",
            context={"errors": exc.errors()},
        ) from exc
