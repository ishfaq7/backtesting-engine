"""Structured error hierarchy for the data layer.

Every failure mode that can occur while talking to a market data provider,
validating its responses, or reading/writing the local cache is represented
by a typed exception here. Callers should never need to catch a bare
``Exception`` or inspect a string message to know what went wrong; each
error carries the structured context (endpoint, HTTP status, retry hints,
offending field, etc.) needed to react programmatically.
"""

from __future__ import annotations

from typing import Any


class DataLayerError(Exception):
    """Base class for every exception raised by ``btengine.data``."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r}, context={self.context!r})"


class ConfigurationError(DataLayerError):
    """Required configuration (e.g. an API key) is missing or invalid."""


class AuthenticationError(DataLayerError):
    """The provider rejected the request as unauthenticated/unauthorized."""

    def __init__(self, message: str, *, status_code: int, endpoint: str) -> None:
        super().__init__(message, context={"status_code": status_code, "endpoint": endpoint})
        self.status_code = status_code
        self.endpoint = endpoint


class RateLimitExceededError(DataLayerError):
    """The provider (or the local limiter) rejected a request due to rate limits."""

    def __init__(self, message: str, *, retry_after_seconds: float | None, endpoint: str) -> None:
        super().__init__(
            message,
            context={"retry_after_seconds": retry_after_seconds, "endpoint": endpoint},
        )
        self.retry_after_seconds = retry_after_seconds
        self.endpoint = endpoint


class TransientProviderError(DataLayerError):
    """A retryable failure: timeout, connection error, or 5xx response."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        status_code: int | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, context={"endpoint": endpoint, "status_code": status_code})
        self.endpoint = endpoint
        self.status_code = status_code
        self.__cause__ = cause


class InvalidResponseError(DataLayerError):
    """The raw API response did not match the expected shape/contract."""

    def __init__(self, message: str, *, endpoint: str, payload_excerpt: str | None = None) -> None:
        super().__init__(message, context={"endpoint": endpoint, "payload_excerpt": payload_excerpt})
        self.endpoint = endpoint
        self.payload_excerpt = payload_excerpt


class NormalizationError(DataLayerError):
    """A validated raw record could not be mapped into the canonical schema."""

    def __init__(self, message: str, *, field: str | None = None, raw_value: Any = None) -> None:
        super().__init__(message, context={"field": field, "raw_value": raw_value})
        self.field = field
        self.raw_value = raw_value


class UnsupportedInstrumentError(DataLayerError):
    """The requested symbol/exchange/timeframe is not supported by the provider."""


class CacheError(DataLayerError):
    """Reading from or writing to the local repository/cache failed."""
