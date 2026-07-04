"""Low-level CoinGlass HTTP client.

This is the only module in the codebase that knows CoinGlass's base URL,
auth header name, and response envelope shape. It wires authentication,
rate limiting, retrying, and logging around plain HTTP calls, and returns
the *raw* (JSON-decoded, envelope-unwrapped, but not yet schema-validated
or normalized) payload. Validation happens in :mod:`~btengine.data.validation`
and normalization in :mod:`mapper` — this client has no opinion on data shape
beyond the generic ``{code, msg, data}`` envelope every CoinGlass endpoint uses.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

import httpx

from btengine.data.errors import (
    AuthenticationError,
    InvalidResponseError,
    RateLimitExceededError,
    TransientProviderError,
)
from btengine.data.providers.coinglass import endpoints
from btengine.data.providers.coinglass.auth import CoinGlassAuthProvider
from btengine.data.providers.coinglass.config import CoinGlassSettings
from btengine.data.providers.coinglass.rate_limiter import TokenBucketRateLimiter
from btengine.data.providers.coinglass.retry import RetryPolicy

logger = logging.getLogger("btengine.data.coinglass.client")


class CoinGlassClient:
    """Authenticated, rate-limited, retrying HTTP client for CoinGlass."""

    def __init__(
        self,
        settings: CoinGlassSettings,
        auth_provider: CoinGlassAuthProvider,
        rate_limiter: TokenBucketRateLimiter,
        retry_policy: RetryPolicy,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._auth_provider = auth_provider
        self._rate_limiter = rate_limiter
        self._retry_policy = retry_policy
        self._http = httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CoinGlassClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get(self, endpoint: str, params: Mapping[str, Any] | None = None) -> Any:
        """Perform a rate-limited, retried GET against ``endpoint``.

        Returns the ``data`` field of CoinGlass's ``{code, msg, data}``
        envelope. Raises a subclass of
        :class:`~btengine.data.errors.DataLayerError` on any failure —
        never a raw ``httpx`` exception or an unhandled crash.
        """
        return self._retry_policy.run(lambda: self._do_request(endpoint, params))

    def verify_connection(self) -> None:
        """Confirm the configured credentials can reach CoinGlass.

        Calls the lightweight ``supported-coins`` endpoint (available on
        every plan tier). Returns normally on success; raises the same
        structured errors as any other call (e.g.
        :class:`~btengine.data.errors.AuthenticationError` for a bad key)
        so callers get an immediate, specific reason for a failed
        connection rather than a generic "it didn't work."
        """
        self.get(endpoints.SUPPORTED_COINS)

    def _do_request(self, endpoint: str, params: Mapping[str, Any] | None) -> Any:
        self._rate_limiter.acquire()
        logger.info(
            "coinglass request starting", extra={"endpoint": endpoint, "params": dict(params or {})}
        )
        try:
            response = self._http.get(
                endpoint, params=params, headers=self._auth_provider.auth_headers()
            )
        except httpx.TimeoutException as exc:
            logger.warning("coinglass request timed out", extra={"endpoint": endpoint})
            raise TransientProviderError(
                f"Timed out calling {endpoint}", endpoint=endpoint, cause=exc
            ) from exc
        except httpx.TransportError as exc:
            logger.warning("coinglass transport error", extra={"endpoint": endpoint, "error": str(exc)})
            raise TransientProviderError(
                f"Transport error calling {endpoint}: {exc}", endpoint=endpoint, cause=exc
            ) from exc

        return self._handle_response(endpoint, response)

    def _handle_response(self, endpoint: str, response: httpx.Response) -> Any:
        status = response.status_code

        if status in (401, 403):
            logger.error(
                "coinglass authentication failed", extra={"endpoint": endpoint, "status_code": status}
            )
            raise AuthenticationError(
                f"CoinGlass rejected credentials for {endpoint} (HTTP {status})",
                status_code=status,
                endpoint=endpoint,
            )

        if status == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            logger.warning(
                "coinglass rate limit exceeded",
                extra={"endpoint": endpoint, "retry_after_seconds": retry_after},
            )
            raise RateLimitExceededError(
                f"CoinGlass rate limit exceeded for {endpoint}",
                retry_after_seconds=retry_after,
                endpoint=endpoint,
            )

        if status >= 500:
            logger.warning(
                "coinglass server error", extra={"endpoint": endpoint, "status_code": status}
            )
            raise TransientProviderError(
                f"CoinGlass server error for {endpoint} (HTTP {status})",
                endpoint=endpoint,
                status_code=status,
            )

        if status >= 400:
            logger.error(
                "coinglass client error", extra={"endpoint": endpoint, "status_code": status}
            )
            raise InvalidResponseError(
                f"CoinGlass rejected the request to {endpoint} (HTTP {status})",
                endpoint=endpoint,
                payload_excerpt=response.text[:500],
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidResponseError(
                f"CoinGlass response for {endpoint} was not valid JSON",
                endpoint=endpoint,
                payload_excerpt=response.text[:500],
            ) from exc

        if not isinstance(body, dict) or "code" not in body:
            raise InvalidResponseError(
                f"CoinGlass response for {endpoint} did not match the expected "
                f"{{code, msg, data}} envelope",
                endpoint=endpoint,
                payload_excerpt=str(body)[:500],
            )

        code = str(body.get("code"))
        if code != "0":
            error = _error_for_body_code(code, endpoint=endpoint, body=body)
            logger.warning(
                "coinglass returned an error envelope",
                extra={"endpoint": endpoint, "code": code, "body_msg": body.get("msg")},
            )
            raise error

        logger.info("coinglass request succeeded", extra={"endpoint": endpoint})
        return body.get("data")


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _error_for_body_code(code: str, *, endpoint: str, body: dict[str, Any]) -> Exception:
    """Map CoinGlass's documented in-body error codes to a structured error.

    CoinGlass sometimes signals an error via this ``code`` field with the
    outer HTTP status still 200, so these are checked independently of the
    HTTP-status branches above rather than assuming the two always agree.
    """
    msg = body.get("msg")
    excerpt = str(body)[:500]
    if code == "401":
        return AuthenticationError(
            f"CoinGlass rejected credentials for {endpoint}: {msg}", status_code=401, endpoint=endpoint
        )
    if code == "429":
        return RateLimitExceededError(
            f"CoinGlass rate limit exceeded for {endpoint}: {msg}",
            retry_after_seconds=None,
            endpoint=endpoint,
        )
    if code in ("408", "500"):
        return TransientProviderError(
            f"CoinGlass server-side error for {endpoint} (code={code}): {msg}", endpoint=endpoint
        )
    # 400 (bad params), 404 (not found), 405 (unsupported method), 422
    # (semantically invalid params), and any unrecognized code are all
    # non-retryable request problems.
    return InvalidResponseError(
        f"CoinGlass returned an error envelope for {endpoint}: code={code} msg={msg}",
        endpoint=endpoint,
        payload_excerpt=excerpt,
    )
